from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import StyleProfile, Subscription

DEFAULT_SUBSCRIPTION_PROVIDER = "telegram_stars"


async def ensure_account_records(db: AsyncSession, user_id: str) -> StyleProfile | None:
    """Create the account's default style and subscription records idempotently.

    A Business Bot webhook can create the User before the Mini App login. The
    account records therefore need to be repaired on login and on settings reads.
    The unique subscription constraint makes concurrent requests safe.
    """
    if not await db.get(StyleProfile, user_id):
        db.add(StyleProfile(user_id=user_id))
    if not await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.provider == DEFAULT_SUBSCRIPTION_PROVIDER,
        )
    ):
        db.add(
            Subscription(
                user_id=user_id,
                provider=DEFAULT_SUBSCRIPTION_PROVIDER,
            )
        )
    try:
        await db.commit()
    except IntegrityError:
        # Another request inserted one of the account singletons first.
        await db.rollback()
    return await db.get(StyleProfile, user_id)
