from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.config import get_settings
from app.db.base import Message


async def clear_expired_raw_text(db):
    cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().raw_message_retention_days)
    result = await db.execute(
        update(Message)
        .where(Message.telegram_created_at < cutoff, Message.text.is_not(None))
        .values(text=None)
    )
    await db.commit()
    return result.rowcount
