from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import AIMode, BusinessConnection, Conversation, Generation


class AccessService:
    async def conversation(
        self, db: AsyncSession, user_id: str, conversation_id: str
    ) -> Conversation:
        c = await db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )
        if not c:
            raise HTTPException(404, "CONVERSATION_NOT_FOUND")
        return c

    async def require_generation(self, db, user_id, conversation_id):
        c = await self.conversation(db, user_id, conversation_id)
        if c.ai_mode != AIMode.copilot:
            raise HTTPException(409, "CONVERSATION_AI_DISABLED")
        bc = await db.scalar(
            select(BusinessConnection).where(
                BusinessConnection.id == c.business_connection_id,
                BusinessConnection.user_id == user_id,
            )
        )
        if not bc or not bc.is_enabled or not bc.can_reply:
            raise HTTPException(409, "BUSINESS_CONNECTION_INACTIVE")
        return c, bc

    async def send(self, db, user_id, conversation_id, generation_id):
        c, bc = await self.require_generation(db, user_id, conversation_id)
        g = await db.scalar(
            select(Generation).where(
                Generation.id == generation_id,
                Generation.user_id == user_id,
                Generation.conversation_id == conversation_id,
            )
        )
        if not g:
            raise HTTPException(404, "GENERATION_NOT_FOUND")
        return c, bc, g
