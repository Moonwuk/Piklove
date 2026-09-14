from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes.account import erase_memory
from app.api.routes.conversations import CustomBody, _replay_attempt
from app.api.routes.settings import Style
from app.db.base import (
    AIMode,
    Base,
    BusinessConnection,
    Conversation,
    Generation,
    Memory,
    ProcessedUpdate,
    SendAttempt,
    SendStatus,
    User,
)
from app.db.session import enforce_sqlite_foreign_keys
from app.services.schemas import ConversationAnalysis, ReplySuggestions
from app.services.webhook import WebhookService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    enforce_sqlite_foreign_keys(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


async def create_generation(db):
    user = User(telegram_user_id=123)
    db.add(user)
    await db.flush()
    connection = BusinessConnection(
        user_id=user.id,
        telegram_business_connection_id="business-1",
        telegram_user_id=123,
        is_enabled=True,
        can_reply=True,
        rights_json={},
    )
    db.add(connection)
    await db.flush()
    conversation = Conversation(
        user_id=user.id,
        business_connection_id=connection.id,
        telegram_chat_id=456,
        ai_mode=AIMode.copilot,
        summary="derived summary",
        summary_version=2,
    )
    db.add(conversation)
    await db.flush()
    generation = Generation(
        user_id=user.id,
        conversation_id=conversation.id,
        source_last_message_id=1,
        analysis_json={},
        suggestions_json={"options": []},
        provider="test",
        model="test",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.add(generation)
    await db.commit()
    return user, conversation, generation


def test_custom_send_rejects_whitespace_only_text():
    with pytest.raises(ValidationError):
        CustomBody(generation_id="generation", text="   \n\t ")


def test_style_rejects_values_the_product_does_not_support():
    with pytest.raises(ValidationError):
        Style(
            tone="anything",
            humor_level=5,
            flirt_level=3,
            message_length="short",
            emoji_level="low",
            directness=5,
            custom_instructions=None,
        )


def test_structured_ai_output_rejects_extra_and_blank_values():
    valid_analysis = {
        "stage": "rapport",
        "engagement": "high",
        "tone": "warm",
        "boundary_detected": False,
        "question_requires_answer": False,
        "meeting_signal": False,
        "recommended_action": "continue_topic",
    }
    with pytest.raises(ValidationError):
        ConversationAnalysis.model_validate({**valid_analysis, "unexpected": "data"})

    with pytest.raises(ValidationError):
        ReplySuggestions.model_validate(
            {
                "options": [
                    {"id": "one", "tone": "natural", "text": "   "},
                    {"id": "two", "tone": "playful", "text": "Two"},
                    {"id": "three", "tone": "direct", "text": "Three"},
                ]
            }
        )


@pytest.mark.anyio
async def test_idempotency_key_cannot_replay_a_different_request(db):
    user, conversation, generation = await create_generation(db)
    db.add(
        SendAttempt(
            user_id=user.id,
            conversation_id=conversation.id,
            generation_id=generation.id,
            idempotency_key="same-key",
            status=SendStatus.sent,
            telegram_message_id=99,
        )
    )
    await db.commit()

    replay = await _replay_attempt(db, user.id, "same-key", conversation.id, generation.id)
    assert replay == {"status": SendStatus.sent, "telegram_message_id": 99}

    with pytest.raises(HTTPException) as error:
        await _replay_attempt(db, user.id, "same-key", conversation.id, "different-generation")
    assert error.value.status_code == 409
    assert error.value.detail == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.anyio
async def test_clear_all_memory_is_one_atomic_server_operation(db):
    user, conversation, _ = await create_generation(db)
    db.add(
        Memory(
            user_id=user.id,
            conversation_id=conversation.id,
            category="preference",
            value="synthetic",
        )
    )
    await db.commit()

    await erase_memory(user_id=user.id, db=db)

    await db.refresh(conversation)
    assert conversation.summary is None
    assert conversation.summary_version == 3
    assert await db.scalar(select(func.count()).select_from(Memory)) == 0
    assert await db.scalar(select(func.count()).select_from(Generation)) == 0


@pytest.mark.anyio
async def test_webhook_retries_once_after_onboarding_integrity_race(db, monkeypatch):
    real_commit = db.commit
    attempts = 0

    async def flaky_commit():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise IntegrityError("synthetic race", {}, Exception("unique conflict"))
        await real_commit()

    monkeypatch.setattr(db, "commit", flaky_commit)
    payload = {
        "update_id": 77,
        "business_connection": {
            "id": "connection-race",
            "user": {"id": 900, "first_name": "Owner"},
            "is_enabled": True,
            "rights": {"can_reply": True},
        },
    }

    await WebhookService().process(db, payload)

    assert attempts == 2
    assert await db.scalar(select(User).where(User.telegram_user_id == 900))
    assert await db.get(ProcessedUpdate, 77)
