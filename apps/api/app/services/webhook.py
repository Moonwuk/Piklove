from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import (
    AIMode,
    BusinessConnection,
    Conversation,
    Direction,
    Message,
    ProcessedUpdate,
    SenderType,
    User,
)
from app.services.logging import safe_log_event


class WebhookService:
    async def process(self, db: AsyncSession, payload: dict):
        uid = payload.get("update_id")
        if uid is not None and await db.get(ProcessedUpdate, uid):
            return
        event = next(
            (
                x
                for x in (
                    "business_connection",
                    "business_message",
                    "edited_business_message",
                    "deleted_business_messages",
                )
                if x in payload
            ),
            "unknown",
        )
        if event == "business_connection":
            await self._connection(db, payload[event])
        elif event in ("business_message", "edited_business_message"):
            await self._message(db, payload[event], event.startswith("edited"))
        elif event == "deleted_business_messages":
            await self._deleted(db, payload[event])
        if uid is not None:
            db.add(ProcessedUpdate(update_id=uid, event_type=event))
        await db.commit()
        safe_log_event(event)

    async def _connection(self, db, data):
        telegram_user_id = data["user"]["id"]
        user = await db.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
        if not user:
            return
        row = await db.scalar(
            select(BusinessConnection).where(
                BusinessConnection.telegram_business_connection_id == data["id"]
            )
        )
        rights = data.get("rights") or {}
        enabled = bool(data.get("is_enabled"))
        can_reply = enabled and bool(rights.get("can_reply", False))
        if not row:
            row = BusinessConnection(
                user_id=user.id,
                telegram_business_connection_id=data["id"],
                telegram_user_id=telegram_user_id,
            )
            db.add(row)
        row.is_enabled = enabled
        row.can_reply = can_reply
        row.rights_json = rights
        row.disconnected_at = None if enabled else datetime.now(UTC)

    async def _message(self, db, data, edited):
        bc = await db.scalar(
            select(BusinessConnection).where(
                BusinessConnection.telegram_business_connection_id
                == data.get("business_connection_id"),
                BusinessConnection.is_enabled.is_(True),
            )
        )
        if not bc:
            return
        chat = data["chat"]
        conv = await db.scalar(
            select(Conversation).where(
                Conversation.user_id == bc.user_id,
                Conversation.business_connection_id == bc.id,
                Conversation.telegram_chat_id == chat["id"],
            )
        )
        if not conv:
            conv = Conversation(
                user_id=bc.user_id,
                business_connection_id=bc.id,
                telegram_chat_id=chat["id"],
                telegram_peer_user_id=chat.get("id") if chat.get("type") == "private" else None,
                display_name=" ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
                or chat.get("title"),
                username=chat.get("username"),
                ai_mode=AIMode.off,
            )
            db.add(conv)
            await db.flush()
        ts = datetime.fromtimestamp(data["date"], UTC)
        conv.last_message_at = ts
        sender = data.get("from", {})
        outgoing = sender.get("id") == bc.telegram_user_id
        msg = await db.scalar(
            select(Message).where(
                Message.conversation_id == conv.id,
                Message.telegram_message_id == data["message_id"],
            )
        )
        text = data.get("text") if conv.ai_mode == AIMode.copilot else None
        if msg:
            msg.text = text if edited else msg.text
            msg.deleted_at = None
        else:
            db.add(
                Message(
                    user_id=bc.user_id,
                    conversation_id=conv.id,
                    telegram_message_id=data["message_id"],
                    direction=Direction.outgoing if outgoing else Direction.incoming,
                    sender_type=SenderType.owner if outgoing else SenderType.contact,
                    text=text,
                    content_type="text" if "text" in data else "unsupported",
                    telegram_created_at=ts,
                )
            )

    async def _deleted(self, db, data):
        bc = await db.scalar(
            select(BusinessConnection).where(
                BusinessConnection.telegram_business_connection_id
                == data.get("business_connection_id")
            )
        )
        if not bc:
            return
        conv = await db.scalar(
            select(Conversation).where(
                Conversation.user_id == bc.user_id,
                Conversation.telegram_chat_id == data["chat"]["id"],
            )
        )
        if conv:
            await db.execute(
                update(Message)
                .where(
                    Message.user_id == bc.user_id,
                    Message.conversation_id == conv.id,
                    Message.telegram_message_id.in_(data["message_ids"]),
                )
                .values(deleted_at=datetime.now(UTC), text=None)
            )
