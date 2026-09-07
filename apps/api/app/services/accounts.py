from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import StyleProfile, Subscription


async def ensure_account_records(db: AsyncSession, user_id: str) -> StyleProfile | None:
    """Create the per-user singletons this account is missing, commit, return its profile.

    These cannot be created only where login inserts the User row: the webhook
    already creates the User when the Business Bot is connected before the owner
    first opens the Mini App, so login finds an existing row and skips that
    branch. Accounts onboarded in that order then had no style profile at all
    and the settings screen answered 500. Calling this on read as well as on
    login also repairs accounts created before the fix.
    """
    if not await db.get(StyleProfile, user_id):
        db.add(StyleProfile(user_id=user_id))
    if not await db.scalar(select(Subscription).where(Subscription.user_id == user_id)):
        db.add(Subscription(user_id=user_id))
    try:
        await db.commit()
    except IntegrityError:
        # A concurrent request inserted the same singletons first; theirs stand.
        await db.rollback()
    return await db.get(StyleProfile, user_id)
