from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import *
from app.services.logging import safe_log_event


class WebhookService:
    event_names = (
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
    )

    async def process(self, db: AsyncSession, payload: dict):
        update_id = payload.get("update_id")
        if update_id is not None and await db.get(ProcessedUpdate, update_id):
            return

        event = next((name for name in self.event_names if name in payload), "unknown")
        try:
            if event == "business_connection":
                await self._connection(db, payload[event])
            elif event in ("business_message", "edited_business_message"):
                await self._message(db, payload[event], event == "edited_business_message")
            elif event == "deleted_business_messages":
                await self._deleted(db, payload[event])

            if update_id is not None:
                db.add(ProcessedUpdate(update_id=update_id, event_type=event))
            await db.commit()
        except IntegrityError:
            # A concurrent worker processed the same update (or message) first.
            # The work is already applied; rolling back and returning ok keeps
            # Telegram from retrying a duplicate forever.
            await db.rollback()
            safe_log_event(event, error_code="DUPLICATE_UPDATE_CONCURRENT")
            return
        safe_log_event(event)

    async def _connection(self, db, data):
        telegram_user_id = data["user"]["id"]
        user = await db.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
        if not user:
            # The owner may connect the Business Bot before ever opening the Mini
            # App. Persist the account now so the connection is claimable at
            # first login instead of being dropped (onboarding trap).
            profile = data.get("user") or {}
            user = User(
                telegram_user_id=telegram_user_id,
                telegram_username=profile.get("username"),
                first_name=profile.get("first_name"),
            )
            db.add(user)
            await db.flush()

        row = await db.scalar(
            select(BusinessConnection).where(
                BusinessConnection.telegram_business_connection_id == data["id"]
            )
        )
        rights = data.get("rights") or {}
        enabled = bool(data.get("is_enabled"))
        if not row:
            row = BusinessConnection(
                user_id=user.id,
                telegram_business_connection_id=data["id"],
                telegram_user_id=telegram_user_id,
            )
            db.add(row)
        row.user_id = user.id
        row.is_enabled = enabled
        row.can_reply = enabled and bool(rights.get("can_reply", False))
        row.rights_json = rights
        row.disconnected_at = None if enabled else datetime.now(timezone.utc)

    async def _message(self, db, data, edited):
        connection = await db.scalar(
            select(BusinessConnection).where(
                BusinessConnection.telegram_business_connection_id
                == data.get("business_connection_id"),
                BusinessConnection.is_enabled.is_(True),
            )
        )
        if not connection:
            return

        chat = data["chat"]
        conversation = await db.scalar(
            select(Conversation).where(
                Conversation.user_id == connection.user_id,
                Conversation.business_connection_id == connection.id,
                Conversation.telegram_chat_id == chat["id"],
            )
        )
        if not conversation:
            conversation = Conversation(
                user_id=connection.user_id,
                business_connection_id=connection.id,
                telegram_chat_id=chat["id"],
                telegram_peer_user_id=chat.get("id") if chat.get("type") == "private" else None,
                display_name=" ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
                or chat.get("title"),
                username=chat.get("username"),
                ai_mode=AIMode.off,
            )
            db.add(conversation)
            await db.flush()

        timestamp = datetime.fromtimestamp(data["date"], timezone.utc)
        if conversation.last_message_at is None or timestamp > conversation.last_message_at.replace(
            tzinfo=timezone.utc
        ):
            conversation.last_message_at = timestamp

        sender = data.get("from", {})
        outgoing = sender.get("id") == connection.telegram_user_id
        message = await db.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.telegram_message_id == data["message_id"],
            )
        )
        retained_text = data.get("text") if conversation.ai_mode == AIMode.copilot else None
        if message:
            if edited:
                message.text = retained_text
                message.content_type = "text" if "text" in data else "unsupported"
            message.deleted_at = None
            return

        db.add(
            Message(
                user_id=connection.user_id,
                conversation_id=conversation.id,
                telegram_message_id=data["message_id"],
                direction=Direction.outgoing if outgoing else Direction.incoming,
                sender_type=SenderType.owner if outgoing else SenderType.contact,
                text=retained_text,
                content_type="text" if "text" in data else "unsupported",
                telegram_created_at=timestamp,
            )
        )

    async def _deleted(self, db, data):
        connection = await db.scalar(
            select(BusinessConnection).where(
                BusinessConnection.telegram_business_connection_id
                == data.get("business_connection_id")
            )
        )
        if not connection:
            return
        conversation = await db.scalar(
            select(Conversation).where(
                Conversation.user_id == connection.user_id,
                Conversation.business_connection_id == connection.id,
                Conversation.telegram_chat_id == data["chat"]["id"],
            )
        )
        if conversation:
            await db.execute(
                update(Message)
                .where(
                    Message.user_id == connection.user_id,
                    Message.conversation_id == conversation.id,
                    Message.telegram_message_id.in_(data["message_ids"]),
                )
                .values(deleted_at=datetime.now(timezone.utc), text=None)
            )
