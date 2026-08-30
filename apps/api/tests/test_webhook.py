from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import (
    AIMode,
    Base,
    BusinessConnection,
    Conversation,
    Message,
    ProcessedUpdate,
    User,
)
from app.services.webhook import WebhookService

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


async def connected_user(db, connection_id="connection-1"):
    user = User(telegram_user_id=100, first_name="Owner")
    db.add(user)
    await db.flush()
    connection = BusinessConnection(
        user_id=user.id,
        telegram_business_connection_id=connection_id,
        telegram_user_id=100,
        is_enabled=True,
        can_reply=True,
    )
    db.add(connection)
    await db.commit()
    return user, connection


def message_update(update_id, message_id, date=1_700_000_000, text="private text"):
    return {
        "update_id": update_id,
        "business_message": {
            "business_connection_id": "connection-1",
            "message_id": message_id,
            "date": date,
            "chat": {"id": 200, "type": "private", "first_name": "Contact"},
            "from": {"id": 200},
            "text": text,
        },
    }


async def test_ai_off_discovers_conversation_without_retaining_text(db):
    await connected_user(db)

    await WebhookService().process(db, message_update(1, 10))

    conversation = await db.scalar(select(Conversation))
    message = await db.scalar(select(Message))
    assert conversation.ai_mode == AIMode.off
    assert conversation.display_name == "Contact"
    assert message.text is None
    assert await db.get(ProcessedUpdate, 1)


async def test_duplicate_update_is_idempotent(db):
    await connected_user(db)
    service = WebhookService()
    payload = message_update(1, 10)

    await service.process(db, payload)
    await service.process(db, payload)

    assert len((await db.scalars(select(Message))).all()) == 1
    assert len((await db.scalars(select(ProcessedUpdate))).all()) == 1


async def test_out_of_order_message_does_not_move_conversation_backwards(db):
    await connected_user(db)
    service = WebhookService()
    await service.process(db, message_update(1, 11, date=1_700_000_100))
    await service.process(db, message_update(2, 10, date=1_700_000_000))

    conversation = await db.scalar(select(Conversation))
    assert conversation.last_message_at.replace(tzinfo=timezone.utc) == datetime.fromtimestamp(
        1_700_000_100, timezone.utc
    )


async def test_edit_and_delete_update_retained_copilot_text(db):
    await connected_user(db)
    service = WebhookService()
    await service.process(db, message_update(1, 10))
    conversation = await db.scalar(select(Conversation))
    conversation.ai_mode = AIMode.copilot
    await db.commit()

    edited = message_update(2, 10, text="edited text")
    edited["edited_business_message"] = edited.pop("business_message")
    await service.process(db, edited)
    message = await db.scalar(select(Message))
    assert message.text == "edited text"

    await service.process(
        db,
        {
            "update_id": 3,
            "deleted_business_messages": {
                "business_connection_id": "connection-1",
                "chat": {"id": 200},
                "message_ids": [10],
            },
        },
    )
    await db.refresh(message)
    assert message.text is None
    assert message.deleted_at is not None


async def test_delete_is_scoped_to_business_connection(db):
    user, connection = await connected_user(db)
    other = BusinessConnection(
        user_id=user.id,
        telegram_business_connection_id="connection-2",
        telegram_user_id=100,
        is_enabled=True,
        can_reply=True,
    )
    db.add(other)
    await db.flush()
    other_conversation = Conversation(
        user_id=user.id,
        business_connection_id=other.id,
        telegram_chat_id=200,
        ai_mode=AIMode.copilot,
    )
    db.add(other_conversation)
    await db.flush()
    other_message = Message(
        user_id=user.id,
        conversation_id=other_conversation.id,
        telegram_message_id=10,
        direction="incoming",
        sender_type="contact",
        text="must survive",
        telegram_created_at=datetime.now(timezone.utc),
    )
    db.add(other_message)
    await db.commit()

    await WebhookService().process(
        db,
        {
            "update_id": 1,
            "deleted_business_messages": {
                "business_connection_id": connection.telegram_business_connection_id,
                "chat": {"id": 200},
                "message_ids": [10],
            },
        },
    )

    await db.refresh(other_message)
    assert other_message.text == "must survive"
    assert other_message.deleted_at is None
