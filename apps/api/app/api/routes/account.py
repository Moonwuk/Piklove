from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, update

from app.api.deps import current_user_id
from app.db.base import Conversation, Generation, Memory, User
from app.db.session import get_db

router = APIRouter(prefix="/account")


@router.delete("/memory", status_code=204)
async def erase_memory(user_id=Depends(current_user_id), db=Depends(get_db)):
    """Atomically clear all AI-derived state while preserving chat metadata.

    Doing this server-side avoids a partial result when the Mini App loses its
    connection midway through one DELETE request per conversation.
    """
    await db.execute(
        update(Conversation)
        .where(Conversation.user_id == user_id)
        .values(
            summary=None,
            summary_version=Conversation.summary_version + 1,
            summary_updated_at=None,
            summary_message_cursor=None,
        )
    )
    await db.execute(delete(Memory).where(Memory.user_id == user_id))
    await db.execute(delete(Generation).where(Generation.user_id == user_id))
    await db.commit()


@router.delete("/data", status_code=204)
async def erase(
    response: Response, user_id=Depends(current_user_id), db=Depends(get_db)
):
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    response.delete_cookie("session", path="/")
