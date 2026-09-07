from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id
from app.config import get_settings
from app.db.base import User
from app.db.session import get_db
from app.security.session import create_session
from app.security.telegram_init_data import InitDataError, validate_init_data
from app.services.accounts import ensure_account_records

router = APIRouter(prefix="/auth")


class AuthBody(BaseModel):
    init_data: str


@router.post("/telegram")
async def telegram(body: AuthBody, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        tg = validate_init_data(
            body.init_data,
            get_settings().telegram_bot_token,
            get_settings().init_data_max_age_seconds,
        )
    except InitDataError as e:
        raise HTTPException(401, "INVALID_TELEGRAM_AUTH") from e

    user = await db.scalar(select(User).where(User.telegram_user_id == tg["id"]))
    if not user:
        user = User(
            telegram_user_id=tg["id"],
            telegram_username=tg.get("username"),
            first_name=tg.get("first_name"),
            language_code=tg.get("language_code"),
        )
        db.add(user)
        try:
            # The webhook may have created this user a moment ago (Business Bot
            # connected before the first Mini App open) — fall back to a re-read.
            await db.flush()
        except IntegrityError:
            await db.rollback()
            user = await db.scalar(select(User).where(User.telegram_user_id == tg["id"]))
            if not user:
                raise HTTPException(500, "AUTH_FAILED") from None

    # Read what the response needs before committing: the rollback inside
    # ensure_account_records would expire the instance and force a reload.
    user_id, first_name = user.id, user.first_name
    await ensure_account_records(db, user_id)

    response.set_cookie(
        "session",
        create_session(user_id),
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite=get_settings().cookie_samesite,
        max_age=2592000,
    )
    return {"user": {"id": user_id, "first_name": first_name}}


@router.get("/me")
async def me(user_id=Depends(current_user_id), db=Depends(get_db)):
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(401, "AUTH_REQUIRED")
    return {"id": u.id, "first_name": u.first_name, "username": u.telegram_username}


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie("session")
