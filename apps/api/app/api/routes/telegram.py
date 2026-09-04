import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id
from app.config import get_settings
from app.db.base import BusinessConnection
from app.db.session import get_db
from app.services.webhook import WebhookService

router = APIRouter(prefix="/telegram")


@router.post("/webhook")
async def webhook(
    payload: dict,
    x_telegram_bot_api_secret_token: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    secret = get_settings().telegram_webhook_secret
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, secret
    ):
        raise HTTPException(401, "INVALID_WEBHOOK_SECRET")
    await WebhookService().process(db, payload)
    return {"ok": True}


@router.get("/connection")
async def connection(user_id=Depends(current_user_id), db: AsyncSession = Depends(get_db)):
    c = await db.scalar(
        select(BusinessConnection)
        .where(BusinessConnection.user_id == user_id)
        .order_by(BusinessConnection.created_at.desc())
    )
    return {"connected": bool(c and c.is_enabled), "can_reply": bool(c and c.can_reply)}
