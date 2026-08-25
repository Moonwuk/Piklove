from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import current_user_id
from app.config import get_settings
from app.db.base import StyleProfile,Subscription,User
from app.db.session import get_db
from app.security.session import create_session
from app.security.telegram_init_data import InitDataError,validate_init_data
router=APIRouter(prefix="/auth")
class AuthBody(BaseModel): init_data:str
@router.post("/telegram")
async def telegram(body:AuthBody,response:Response,db:AsyncSession=Depends(get_db)):
 try: tg=validate_init_data(body.init_data,get_settings().telegram_bot_token,get_settings().init_data_max_age_seconds)
 except InitDataError as e: raise HTTPException(401,"INVALID_TELEGRAM_AUTH") from e
 user=await db.scalar(select(User).where(User.telegram_user_id==tg["id"]))
 if not user:
  user=User(telegram_user_id=tg["id"],telegram_username=tg.get("username"),first_name=tg.get("first_name"),language_code=tg.get("language_code")); db.add(user); await db.flush(); db.add_all([StyleProfile(user_id=user.id),Subscription(user_id=user.id)]); await db.commit()
 response.set_cookie("session",create_session(user.id),httponly=True,secure=get_settings().cookie_secure,samesite="lax",max_age=2592000); return {"user":{"id":user.id,"first_name":user.first_name}}
@router.get("/me")
async def me(user_id=Depends(current_user_id),db=Depends(get_db)):
 u=await db.get(User,user_id); return {"id":u.id,"first_name":u.first_name,"username":u.telegram_username}
@router.post("/logout",status_code=204)
async def logout(response:Response): response.delete_cookie("session")
