from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.api.deps import current_user_id
from app.db.session import get_db
from app.services.accounts import ensure_account_records

router = APIRouter(prefix="/settings")


class Style(BaseModel):
    tone: Literal["natural", "playful", "romantic", "confident", "caring"]
    humor_level: int = Field(ge=0, le=10)
    flirt_level: int = Field(ge=0, le=10)
    message_length: Literal["short", "medium", "long"]
    emoji_level: Literal["none", "low", "medium", "high"]
    directness: int = Field(ge=0, le=10)
    custom_instructions: str | None = Field(None, max_length=500)

    @field_validator("custom_instructions")
    @classmethod
    def normalize_custom_instructions(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


@router.get("/style")
async def get_style(user_id=Depends(current_user_id), db=Depends(get_db)):
    return Style.model_validate(await ensure_account_records(db, user_id), from_attributes=True)


@router.put("/style")
async def put_style(body: Style, user_id=Depends(current_user_id), db=Depends(get_db)):
    style = await ensure_account_records(db, user_id)
    for key, value in body.model_dump().items():
        setattr(style, key, value)
    await db.commit()
    return body
