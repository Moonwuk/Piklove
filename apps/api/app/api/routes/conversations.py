from datetime import datetime,timezone
from fastapi import APIRouter,Depends,Header,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import delete,select
from app.api.deps import current_user_id
from app.db.base import *
from app.db.session import get_db
from app.integrations.telegram.client import TelegramClient
from app.services.access import AccessService
from app.services.ai import OpenAIProvider,SuggestionService
from app.services.schemas import ReplySuggestions
router=APIRouter(prefix="/conversations"); access=AccessService()
class ModeBody(BaseModel): mode:AIMode
class SendBody(BaseModel): generation_id:str; option_id:str
class CustomBody(BaseModel): generation_id:str; text:str=Field(min_length=1,max_length=4096)
def view(c): return {"id":c.id,"display_name":c.display_name,"username":c.username,"ai_mode":c.ai_mode,"last_message_at":c.last_message_at}
@router.get("")
async def listing(user_id=Depends(current_user_id),db=Depends(get_db)):
 return [view(c) for c in (await db.scalars(select(Conversation).where(Conversation.user_id==user_id).order_by(Conversation.last_message_at.desc()))).all()]
@router.get("/{conversation_id}")
async def detail(conversation_id:str,user_id=Depends(current_user_id),db=Depends(get_db)):
 c=await access.conversation(db,user_id,conversation_id); msgs=(await db.scalars(select(Message).where(Message.user_id==user_id,Message.conversation_id==c.id,Message.deleted_at.is_(None)).order_by(Message.telegram_created_at))).all(); return {**view(c),"messages":[{"id":m.id,"direction":m.direction,"text":m.text,"created_at":m.telegram_created_at} for m in msgs]}
@router.patch("/{conversation_id}/ai-mode")
async def mode(conversation_id:str,body:ModeBody,user_id=Depends(current_user_id),db=Depends(get_db)):
 c=await access.conversation(db,user_id,conversation_id); c.ai_mode=body.mode; await db.commit(); return view(c)
@router.post("/{conversation_id}/suggestions")
async def suggestions(conversation_id:str,user_id=Depends(current_user_id),db=Depends(get_db)):
 c,_=await access.require_generation(db,user_id,conversation_id)
 try:g=await SuggestionService(OpenAIProvider()).generate(db,user_id,c)
 except ValueError as e: raise HTTPException(409,"NO_CONTEXT_MESSAGES") from e
 return {"generation_id":g.id,"analysis":{"stage":g.analysis_json["stage"],"engagement":g.analysis_json["engagement"]},**g.suggestions_json}
async def _send(conversation_id,generation_id,text,user_id,db,idempotency_key):
 c,bc,g=await access.send(db,user_id,conversation_id,generation_id); now=datetime.now(timezone.utc)
 if g.expires_at.replace(tzinfo=timezone.utc) <= now: raise HTTPException(409,"GENERATION_EXPIRED")
 if g.sent_at: raise HTTPException(409,"GENERATION_ALREADY_SENT")
 newer=await db.scalar(select(Message).where(Message.user_id==user_id,Message.conversation_id==c.id,Message.direction==Direction.incoming,Message.telegram_message_id>g.source_last_message_id,Message.deleted_at.is_(None)).limit(1))
 if newer: raise HTTPException(409,"SUGGESTION_STALE")
 existing=await db.scalar(select(SendAttempt).where(SendAttempt.user_id==user_id,SendAttempt.idempotency_key==idempotency_key))
 if existing: return {"status":existing.status,"telegram_message_id":existing.telegram_message_id}
 attempt=SendAttempt(user_id=user_id,conversation_id=c.id,generation_id=g.id,idempotency_key=idempotency_key,status=SendStatus.pending); db.add(attempt); await db.commit()
 try: result=await TelegramClient().send_business_message(bc.telegram_business_connection_id,c.telegram_chat_id,text)
 except Exception:
  attempt.status=SendStatus.unknown; await db.commit(); raise HTTPException(502,"TELEGRAM_SEND_UNKNOWN") from None
 attempt.status=SendStatus.sent; attempt.telegram_message_id=result["message_id"]; g.sent_at=now; db.add(Message(user_id=user_id,conversation_id=c.id,telegram_message_id=result["message_id"],direction=Direction.outgoing,sender_type=SenderType.owner,text=text,content_type="text",telegram_created_at=datetime.fromtimestamp(result.get("date",int(now.timestamp())),timezone.utc))); await db.commit(); return {"status":"sent","telegram_message_id":result["message_id"]}
@router.post("/{conversation_id}/send")
async def send(conversation_id:str,body:SendBody,idempotency_key:str=Header(...,alias="Idempotency-Key"),user_id=Depends(current_user_id),db=Depends(get_db)):
 _,_,g=await access.send(db,user_id,conversation_id,body.generation_id); options=ReplySuggestions.model_validate(g.suggestions_json).options; option=next((x for x in options if x.id==body.option_id),None)
 if not option: raise HTTPException(422,"SUGGESTION_NOT_FOUND")
 return await _send(conversation_id,g.id,option.text,user_id,db,idempotency_key)
@router.post("/{conversation_id}/send-custom")
async def custom(conversation_id:str,body:CustomBody,idempotency_key:str=Header(...,alias="Idempotency-Key"),user_id=Depends(current_user_id),db=Depends(get_db)): return await _send(conversation_id,body.generation_id,body.text.strip(),user_id,db,idempotency_key)
@router.delete("/{conversation_id}/memory",status_code=204)
async def memory(conversation_id:str,user_id=Depends(current_user_id),db=Depends(get_db)):
 c=await access.conversation(db,user_id,conversation_id); c.summary=None; c.summary_version+=1; await db.execute(delete(Memory).where(Memory.user_id==user_id,Memory.conversation_id==c.id)); await db.execute(delete(Generation).where(Generation.user_id==user_id,Generation.conversation_id==c.id)); await db.commit()
