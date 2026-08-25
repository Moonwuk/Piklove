from fastapi import APIRouter,Depends
from sqlalchemy import delete
from app.api.deps import current_user_id
from app.db.base import User
from app.db.session import get_db
router=APIRouter(prefix="/account")
@router.delete("/data",status_code=204)
async def erase(user_id=Depends(current_user_id),db=Depends(get_db)): await db.execute(delete(User).where(User.id==user_id)); await db.commit()
