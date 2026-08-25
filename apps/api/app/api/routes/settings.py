from fastapi import APIRouter,Depends
from pydantic import BaseModel,Field
from app.api.deps import current_user_id
from app.db.base import StyleProfile
from app.db.session import get_db
router=APIRouter(prefix="/settings")
class Style(BaseModel):
 tone:str; humor_level:int=Field(ge=0,le=10); flirt_level:int=Field(ge=0,le=10); message_length:str; emoji_level:str; directness:int=Field(ge=0,le=10); custom_instructions:str|None=Field(None,max_length=500)
@router.get("/style")
async def get_style(user_id=Depends(current_user_id),db=Depends(get_db)): return Style.model_validate(await db.get(StyleProfile,user_id),from_attributes=True)
@router.put("/style")
async def put_style(body:Style,user_id=Depends(current_user_id),db=Depends(get_db)):
 s=await db.get(StyleProfile,user_id)
 for k,v in body.model_dump().items():setattr(s,k,v)
 await db.commit(); return body
