from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import Subscription, UsageEvent

PRO_PLAN = "pro"


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


async def resolve_plan(db: AsyncSession, user_id: str) -> str:
    sub = await db.scalar(
        select(Subscription).where(Subscription.user_id == user_id, Subscription.status == "active")
    )
    return (sub.plan if sub else "free") or "free"


async def usage_this_month(db: AsyncSession, user_id: str) -> int:
    count = await db.scalar(
        select(func.count(UsageEvent.id)).where(
            UsageEvent.user_id == user_id,
            UsageEvent.type == "ai_generation",
            UsageEvent.created_at >= _month_start(datetime.now(timezone.utc)),
        )
    )
    return int(count or 0)


def monthly_limit(plan: str) -> int:
    s = get_settings()
    return s.pro_monthly_generations if plan == PRO_PLAN else s.free_generations


async def quota_state(db: AsyncSession, user_id: str) -> dict:
    plan = await resolve_plan(db, user_id)
    used = await usage_this_month(db, user_id)
    limit = monthly_limit(plan)
    return {"plan": plan, "used": used, "limit": limit}


async def ensure_quota(db: AsyncSession, user_id: str) -> dict:
    """Raise 402 before any billable LLM call when the monthly quota is spent."""
    state = await quota_state(db, user_id)
    if state["used"] >= state["limit"]:
        raise HTTPException(
            402,
            {
                "code": "QUOTA_EXCEEDED",
                "used": state["used"],
                "limit": state["limit"],
                "plan": state["plan"],
            },
        )
    return state
