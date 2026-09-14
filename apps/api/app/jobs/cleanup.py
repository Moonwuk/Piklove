from datetime import datetime, timedelta, timezone

from sqlalchemy import text, update

from app.config import get_settings
from app.db.base import Message


async def clear_expired_raw_text(db):
    if db.bind and db.bind.dialect.name == "postgresql":
        # Every API worker runs the lightweight loop, but only one process may
        # execute a sweep at a time. The lock is released by the commit below.
        acquired = await db.scalar(text("SELECT pg_try_advisory_xact_lock(72194501)"))
        if not acquired:
            await db.rollback()
            return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().raw_message_retention_days)
    result = await db.execute(
        update(Message)
        .where(Message.telegram_created_at < cutoff, Message.text.is_not(None))
        .values(text=None)
    )
    await db.commit()
    return result.rowcount
