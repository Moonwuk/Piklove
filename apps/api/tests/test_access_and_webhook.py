import asyncio

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base, BusinessConnection, Conversation, Message, User
from app.services.access import AccessService
from app.services.webhook import WebhookService


async def make_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)()


def test_tenant_cannot_access_another_users_conversation():
    async def scenario():
        engine, db = await make_session()
        try:
            owner = User(telegram_user_id=100, first_name="Owner")
            attacker = User(telegram_user_id=200, first_name="Attacker")
            db.add_all([owner, attacker])
            await db.flush()
            connection = BusinessConnection(
                user_id=owner.id,
                telegram_business_connection_id="bc-owner",
                telegram_user_id=100,
                is_enabled=True,
                can_reply=True,
            )
            db.add(connection)
            await db.flush()
            conversation = Conversation(
                user_id=owner.id,
                business_connection_id=connection.id,
                telegram_chat_id=300,
            )
            db.add(conversation)
            await db.commit()

            try:
                await AccessService().conversation(db, attacker.id, conversation.id)
            except HTTPException as error:
                assert error.status_code == 404
                assert error.detail == "CONVERSATION_NOT_FOUND"
            else:
                raise AssertionError("cross-tenant conversation access was allowed")
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(scenario())


def test_duplicate_ai_off_message_is_metadata_only_and_idempotent():
    async def scenario():
        engine, db = await make_session()
        try:
            user = User(telegram_user_id=100, first_name="Owner")
            db.add(user)
            await db.flush()
            db.add(
                BusinessConnection(
                    user_id=user.id,
                    telegram_business_connection_id="bc-owner",
                    telegram_user_id=100,
                    is_enabled=True,
                    can_reply=True,
                )
            )
            await db.commit()

            update = {
                "update_id": 55,
                "business_message": {
                    "business_connection_id": "bc-owner",
                    "message_id": 77,
                    "date": 1_700_000_000,
                    "from": {"id": 200, "first_name": "Contact"},
                    "chat": {"id": 200, "type": "private", "first_name": "Contact"},
                    "text": "private raw content",
                },
            }
            service = WebhookService()
            await service.process(db, update)
            await service.process(db, update)

            assert await db.scalar(select(func.count()).select_from(Conversation)) == 1
            assert await db.scalar(select(func.count()).select_from(Message)) == 1
            message = await db.scalar(select(Message))
            assert message.text is None
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(scenario())
