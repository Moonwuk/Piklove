from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import current_user_id
from app.config import get_settings
from app.db.base import Subscription
from app.db.session import get_db


class BillingProvider(Protocol):
    async def create_invoice(self, user_id: str) -> str: ...


class TelegramStarsProvider:
    async def create_invoice(self, user_id: str) -> str:
        raise NotImplementedError


router = APIRouter(prefix="/billing")


@router.get("/subscription")
async def subscription(user_id=Depends(current_user_id), db=Depends(get_db)):
    s = await db.scalar(
        select(Subscription).where(Subscription.user_id == user_id, Subscription.status == "active")
    )
    return {"plan": s.plan if s else "free", "status": s.status if s else "active"}


@router.post("/subscribe")
async def subscribe(user_id=Depends(current_user_id)):
    if not get_settings().enable_billing:
        raise HTTPException(503, "BILLING_DISABLED")
    raise HTTPException(501, "TELEGRAM_STARS_SETUP_REQUIRED")
