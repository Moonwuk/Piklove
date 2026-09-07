"""Concurrency checks that exercise PostgreSQL transaction semantics.

Set TEST_DATABASE_URL to run these tests locally. CI supplies a dedicated,
ephemeral database; the module deliberately recreates its schema per test.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import (
    AIMode,
    Base,
    BusinessConnection,
    Conversation,
    Generation,
    SendAttempt,
    UsageEvent,
    User,
)
from app.services.quota import reserve_quota

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def postgres(monkeypatch):
    engine = create_async_engine(DATABASE_URL, pool_size=5)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setenv("FREE_GENERATIONS", "1")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        yield maker
    finally:
        get_settings.cache_clear()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.anyio
async def test_quota_reservation_is_atomic(postgres):
    async with postgres() as db:
        user = User(telegram_user_id=101)
        db.add(user)
        await db.commit()
        user_id = user.id

    ready = asyncio.Event()

    async def reserve():
        async with postgres() as db:
            await ready.wait()
            try:
                await reserve_quota(db, user_id)
                return "reserved"
            except HTTPException as exc:
                return exc.status_code

    tasks = [asyncio.create_task(reserve()) for _ in range(2)]
    ready.set()
    assert sorted(await asyncio.gather(*tasks), key=str) == [402, "reserved"]

    async with postgres() as db:
        events = (
            await db.scalars(
                select(UsageEvent).where(
                    UsageEvent.user_id == user_id, UsageEvent.type == "ai_generation"
                )
            )
        ).all()
        assert len(events) == 1


@pytest.mark.anyio
async def test_generation_can_reach_telegram_only_once(postgres, monkeypatch):
    now = datetime.now(timezone.utc)
    async with postgres() as db:
        user = User(telegram_user_id=202)
        db.add(user)
        await db.flush()
        connection = BusinessConnection(
            user_id=user.id,
            telegram_business_connection_id="business-1",
            telegram_user_id=202,
            is_enabled=True,
            can_reply=True,
            rights_json={},
        )
        db.add(connection)
        await db.flush()
        conversation = Conversation(
            user_id=user.id,
            business_connection_id=connection.id,
            telegram_chat_id=303,
            ai_mode=AIMode.copilot,
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
            expires_at=now + timedelta(minutes=5),
        )
        db.add(generation)
        await db.commit()
        ids = user.id, conversation.id, generation.id

    calls = 0

    class CountingTelegram:
        async def send_business_message(self, business_connection_id, chat_id, text):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.05)
            return {"message_id": 404, "date": int(now.timestamp())}

    monkeypatch.setattr("app.api.routes.conversations.TelegramClient", lambda: CountingTelegram())
    from app.api.routes.conversations import _send

    ready = asyncio.Event()

    async def send(key):
        async with postgres() as db:
            await ready.wait()
            try:
                result = await _send(*ids[1:], "hello", ids[0], db, key)
                return result["status"]
            except HTTPException as exc:
                return exc.status_code

    tasks = [asyncio.create_task(send(key)) for key in ("key-1", "key-2")]
    ready.set()
    results = await asyncio.gather(*tasks)
    assert sorted(results, key=str) == [409, "sent"]
    assert calls == 1

    async with postgres() as db:
        attempts = (await db.scalars(select(SendAttempt))).all()
        assert len(attempts) == 1
