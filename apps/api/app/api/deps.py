from fastapi import Cookie,Depends,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.security.session import read_session
async def current_user_id(session: str|None=Cookie(None),db:AsyncSession=Depends(get_db)):
    user_id=read_session(session or "")
    if not user_id: raise HTTPException(401,"AUTH_REQUIRED")
    return user_id
