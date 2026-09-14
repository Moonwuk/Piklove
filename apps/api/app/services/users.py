from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import StyleProfile, Subscription


async def ensure_user_defaults(db: AsyncSession, user_id: str) -> None:
    """Provision records required by authenticated user flows."""
    if await db.get(StyleProfile, user_id) is None:
        db.add(StyleProfile(user_id=user_id))

    subscription = await db.scalar(
        select(Subscription.id).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
        )
    )
    if subscription is None:
        db.add(Subscription(user_id=user_id))
