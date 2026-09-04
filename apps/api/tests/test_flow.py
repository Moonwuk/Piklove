"""End-to-end API flow tests through the real HTTP surface (TestClient).

Telegram/OpenAI adapters are replaced with fakes; auth, ACL, quota and send
logic run for real. SQLite in-memory per test.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.main import app

TG_TOKEN = "test-bot-token"
WEBHOOK_SECRET = "whsec"


def sign_init_data(tg_id: int, now: int | None = None) -> str:
    d = {
        "auth_date": str(now or int(time.time())),
        "query_id": "q",
        "user": json.dumps({"id": tg_id, "first_name": "Owner"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
    secret = hmac.new(b"WebAppData", TG_TOKEN.encode(), hashlib.sha256).digest()
    d["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(d)


def message_update(update_id, message_id, chat_id=200, text="hello", date=None):
    return {
        "update_id": update_id,
        "business_message": {
            "business_connection_id": "conn-1",
            "message_id": message_id,
            "date": date or int(time.time()),
            "chat": {"id": chat_id, "type": "private", "first_name": "Contact"},
            "from": {"id": chat_id},
            "text": text,
        },
    }


def connection_update(update_id=0, tg_id=100):
    return {
        "update_id": update_id,
        "business_connection": {
            "id": "conn-1",
            "user": {"id": tg_id, "first_name": "Owner", "username": "owner"},
            "is_enabled": True,
            "rights": {"can_reply": True},
        },
    }


class FakeTelegram:
    async def send_business_message(self, bc_id, chat_id, text):
        return {"message_id": 4242, "date": int(time.time())}

    async def get_business_connection(self, bc_id):
        return {}


class FakeProvider:
    async def analyze_conversation(self, ctx):
        from app.services.schemas import ConversationAnalysis

        return ConversationAnalysis(
            stage="rapport",
            engagement="high",
            tone="warm",
            boundary_detected=False,
            question_requires_answer=False,
            meeting_signal=False,
            recommended_action="continue_topic",
        )

    async def generate_replies(self, ctx, analysis):
        from app.services.schemas import ReplyOption, ReplySuggestions

        return ReplySuggestions(
            options=[
                ReplyOption(id="opt-1", tone="natural", text="natural reply"),
                ReplyOption(id="opt-2", tone="playful", text="playful reply"),
                ReplyOption(id="opt-3", tone="direct", text="direct reply"),
            ]
        )

    async def summarize_conversation(self, ctx):
        return ""


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def client(monkeypatch):
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with maker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    from app.db import session as session_module

    app.dependency_overrides[session_module.get_db] = override_get_db
    monkeypatch.setattr(session_module, "SessionLocal", maker)

    async def _init_schema():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    import anyio

    anyio.run(_init_schema)

    # Route every get_settings() call (including module-level imports) through
    # env vars + cache invalidation instead of patching each module's binding.
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TG_TOKEN)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("OPENAI_REPLY_MODEL", "m")
    monkeypatch.setenv("OPENAI_ANALYSIS_MODEL", "m")
    monkeypatch.setenv("OPENAI_SUMMARY_MODEL", "m")
    monkeypatch.setenv("FREE_GENERATIONS", "2")

    import app.config as config_module

    monkeypatch.setattr("app.api.routes.conversations.TelegramClient", lambda: FakeTelegram())
    monkeypatch.setattr("app.api.routes.conversations.OpenAIProvider", lambda: FakeProvider())

    config_module.get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    config_module.get_settings.cache_clear()


def _auth(client, tg_id=100):
    r = client.post("/api/v1/auth/telegram", json={"init_data": sign_init_data(tg_id)})
    assert r.status_code == 200, r.text
    return r.headers["set-cookie"].split(";")[0]


def _webhook(client, payload):
    return client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )


def _make_conversation_with_text(client):
    """Webhook a business message so a conversation exists with retained text."""
    _webhook(client, connection_update())
    # Turn copilot ON for the owner's conversation by authenticating first.
    cookie = _auth(client)
    # Owner message from the contact while copilot still OFF -> text discarded.
    _webhook(client, message_update(1, 10, text="secret-should-not-persist"))
    # Enable copilot via API.
    r = client.get("/api/v1/conversations", headers={"Cookie": cookie})
    conv_id = r.json()[0]["id"]
    r = client.patch(
        f"/api/v1/conversations/{conv_id}/ai-mode",
        json={"mode": "copilot"},
        headers={"Cookie": cookie},
    )
    assert r.status_code == 200
    # New message arrives while copilot is ON -> text retained.
    _webhook(client, message_update(2, 11, text="please reply to me"))
    return cookie, conv_id


def test_connection_update_before_first_login_creates_user(client):
    """Onboarding trap regression: Business Bot connected before Mini App open."""
    r = _webhook(client, connection_update())
    assert r.status_code == 200

    # The owner now opens the Mini App for the first time.
    cookie = _auth(client, tg_id=100)

    r = client.get("/api/v1/telegram/connection", headers={"Cookie": cookie})
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is True
    assert body["can_reply"] is True

    r = client.get("/api/v1/conversations", headers={"Cookie": cookie})
    assert r.status_code == 200


def test_ai_off_discards_text_and_quota_blocks_after_limit(client):
    cookie, conv_id = _make_conversation_with_text(client)

    # Privacy: message received while AI OFF must not be readable.
    r = client.get(f"/api/v1/conversations/{conv_id}", headers={"Cookie": cookie})
    texts = [m["text"] for m in r.json()["messages"]]
    assert "secret" not in " ".join(t or "" for t in texts)
    assert "please reply" in " ".join(t or "" for t in texts)

    # Quota: free_generations=2 in this fixture.
    r = client.post(f"/api/v1/conversations/{conv_id}/suggestions", headers={"Cookie": cookie})
    assert r.status_code == 200
    gen = r.json()
    assert len(gen["options"]) == 3

    r = client.post(f"/api/v1/conversations/{conv_id}/suggestions", headers={"Cookie": cookie})
    assert r.status_code == 200

    r = client.post(f"/api/v1/conversations/{conv_id}/suggestions", headers={"Cookie": cookie})
    assert r.status_code == 402
    assert r.json()["error"]["code"] == "QUOTA_EXCEEDED"

    # Usage endpoint reflects the burn-down.
    r = client.get("/api/v1/billing/usage", headers={"Cookie": cookie})
    assert r.json() == {"plan": "free", "used": 2, "limit": 2}


def test_send_one_time_only_and_duplicate_idempotency_key(client):
    cookie, conv_id = _make_conversation_with_text(client)
    # Two generations so quota does not block the race test.
    r = client.post(f"/api/v1/conversations/{conv_id}/suggestions", headers={"Cookie": cookie})
    gen = r.json()

    headers = {"Cookie": cookie, "Idempotency-Key": "idem-fixed-key-1"}
    r = client.post(
        f"/api/v1/conversations/{conv_id}/send",
        json={"generation_id": gen["generation_id"], "option_id": "opt-1"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent"

    # Same idempotency key replays the recorded outcome.
    r2 = client.post(
        f"/api/v1/conversations/{conv_id}/send",
        json={"generation_id": gen["generation_id"], "option_id": "opt-1"},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json() == r.json()

    # Different key, same generation: must be rejected (one-time send).
    r3 = client.post(
        f"/api/v1/conversations/{conv_id}/send",
        json={"generation_id": gen["generation_id"], "option_id": "opt-2"},
        headers={"Cookie": cookie, "Idempotency-Key": "idem-fixed-key-2"},
    )
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "GENERATION_ALREADY_SENT"


def test_acl_other_user_cannot_read_conversation(client):
    _make_conversation_with_text(client)
    cookie_a = _auth(client, tg_id=100)
    r = client.get("/api/v1/conversations", headers={"Cookie": cookie_a})
    conv_id = r.json()[0]["id"]

    # A different Telegram user has no conversations.
    cookie_b = _auth(client, tg_id=999)
    r = client.get("/api/v1/conversations", headers={"Cookie": cookie_b})
    assert r.json() == []

    r = client.get(f"/api/v1/conversations/{conv_id}", headers={"Cookie": cookie_b})
    assert r.status_code == 404


def test_deleted_account_session_fails_closed(client):
    cookie = _auth(client)
    r = client.delete("/api/v1/account/data", headers={"Cookie": cookie})
    assert r.status_code == 204
    # Session must now be rejected with 401 (not 500) on any route.
    r = client.get("/api/v1/auth/me", headers={"Cookie": cookie})
    assert r.status_code == 401


def test_webhook_requires_secret(client):
    r = client.post("/api/v1/telegram/webhook", json=message_update(9, 90))
    assert r.status_code == 401
    r = client.post(
        "/api/v1/telegram/webhook",
        json=message_update(9, 90),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert r.status_code == 401
