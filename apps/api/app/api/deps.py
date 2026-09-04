from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import User, UserStatus
from app.db.session import get_db
from app.security.session import read_session


async def current_user_id(session: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    user_id = read_session(session or "")
    if not user_id:
        raise HTTPException(401, "AUTH_REQUIRED")
    # The session is a signed cookie that outlives account state changes
    # (blocked/deleted users, erased accounts) — re-check the user on every
    # request so stale sessions fail closed with 401, not a 500.
    user = await db.get(User, user_id)
    if not user or user.status != UserStatus.active:
        raise HTTPException(401, "AUTH_REQUIRED")
    return user_id
