import asyncio
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import Subscription, UsageEvent

PRO_PLAN = "pro"
_sqlite_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


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


def _quota_exceeded(state: dict) -> HTTPException:
    return HTTPException(
        402,
        {
            "code": "QUOTA_EXCEEDED",
            "used": state["used"],
            "limit": state["limit"],
            "plan": state["plan"],
        },
    )


async def _reserve_locked(db: AsyncSession, user_id: str) -> dict:
    state = await quota_state(db, user_id)
    if state["used"] >= state["limit"]:
        raise _quota_exceeded(state)
    db.add(
        UsageEvent(
            user_id=user_id,
            type="ai_generation",
            quantity=1,
            event_metadata={"status": "reserved"},
        )
    )
    await db.commit()
    return {**state, "used": state["used"] + 1}


async def reserve_quota(db: AsyncSession, user_id: str) -> dict:
    """Atomically reserve one generation before invoking the paid provider.

    PostgreSQL serializes reservations for a user with a transaction-scoped
    advisory lock. SQLite is supported for local development and tests with an
    equivalent in-process lock; it is not a production deployment target.

    A reservation is intentionally charged even if a later provider call fails:
    the upstream request may already have incurred cost, so automatically
    refunding it would allow retries to bypass the configured spend ceiling.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:user_id, 0))"),
            {"user_id": user_id},
        )
        return await _reserve_locked(db, user_id)

    async with _sqlite_locks[user_id]:
        return await _reserve_locked(db, user_id)
