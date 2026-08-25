from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Protocol
from openai import AsyncOpenAI
from sqlalchemy import select
from app.config import get_settings
from app.db.base import Generation,Memory,Message,StyleProfile,UsageEvent
from app.services.schemas import *
class LLMProvider(Protocol):
    async def analyze_conversation(self,context:AIConversationContext)->ConversationAnalysis: ...
    async def generate_replies(self,context:AIConversationContext,analysis:ConversationAnalysis)->ReplySuggestions: ...
    async def summarize_conversation(self,context:AIConversationContext)->str: ...
class OpenAIProvider:
    def __init__(self): self.s=get_settings(); self.client=AsyncOpenAI(api_key=self.s.openai_api_key)
    async def _structured(self,model,prompt,context,schema):
        response=await self.client.responses.parse(model=model,store=self.s.openai_store,input=[{"role":"system","content":prompt},{"role":"user","content":context.model_dump_json()}],text_format=schema)
        return response.output_parsed
    async def analyze_conversation(self,context): return await self._structured(self.s.openai_analysis_model,Path(__file__).parents[1].joinpath("prompts/conversation_analyzer.md").read_text(),context,ConversationAnalysis)
    async def generate_replies(self,context,analysis):
        combined=context.model_copy(); prompt=Path(__file__).parents[1].joinpath("prompts/reply_generator.md").read_text()+"\nAnalysis:\n"+analysis.model_dump_json()
        return await self._structured(self.s.openai_reply_model,prompt,combined,ReplySuggestions)
    async def summarize_conversation(self,context): return ""
class AIContextBuilder:
    async def build(self,db,user_id,conversation)->AIConversationContext:
        s=get_settings(); style=await db.get(StyleProfile,user_id); memories=(await db.scalars(select(Memory).where(Memory.user_id==user_id,Memory.conversation_id==conversation.id))).all(); messages=(await db.scalars(select(Message).where(Message.user_id==user_id,Message.conversation_id==conversation.id,Message.deleted_at.is_(None),Message.text.is_not(None)).order_by(Message.telegram_created_at.desc()).limit(s.ai_recent_messages_limit))).all(); messages=list(reversed(messages)); ctx=[ContextMessage(direction=m.direction.value,text=m.text,telegram_created_at=m.telegram_created_at) for m in messages]
        return AIConversationContext(user_style=UserStyleContext.model_validate(style,from_attributes=True) if style else UserStyleContext(),conversation=ConversationContext(id=conversation.id,display_name=conversation.display_name),summary=conversation.summary,memory=[MemoryItem(category=m.category,value=m.value) for m in memories],recent_messages=ctx,new_messages=ctx[-3:])
class SuggestionService:
    def __init__(self,provider): self.provider=provider; self.builder=AIContextBuilder()
    async def generate(self,db,user_id,conversation):
        last=await db.scalar(select(Message).where(Message.conversation_id==conversation.id,Message.deleted_at.is_(None)).order_by(Message.telegram_message_id.desc()).limit(1))
        if not last: raise ValueError("conversation has no retained messages")
        context=await self.builder.build(db,user_id,conversation); analysis=await self.provider.analyze_conversation(context); suggestions=await self.provider.generate_replies(context,analysis); now=datetime.now(timezone.utc); g=Generation(user_id=user_id,conversation_id=conversation.id,source_last_message_id=last.telegram_message_id,analysis_json=analysis.model_dump(),suggestions_json=suggestions.model_dump(),provider="openai",model=get_settings().openai_reply_model,expires_at=now+timedelta(seconds=get_settings().generation_ttl_seconds)); db.add_all([g,UsageEvent(user_id=user_id,type="ai_generation",quantity=1,event_metadata={})]); await db.commit(); return g
