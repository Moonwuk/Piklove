from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["opening", "rapport", "flirting", "meeting_discussion", "inactive", "boundary"]
    engagement: Literal["low", "medium", "high", "unknown"]
    tone: Literal["neutral", "warm", "playful", "flirty", "serious", "negative"]
    boundary_detected: bool
    question_requires_answer: bool
    meeting_signal: bool
    recommended_action: Literal[
        "answer_question",
        "continue_topic",
        "ask_followup",
        "light_humor",
        "light_flirt",
        "suggest_meeting",
        "clarify_meeting",
        "respect_boundary",
        "end_conversation",
    ]


class ReplyOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    tone: Literal["natural", "playful", "direct"]
    text: str = Field(min_length=1, max_length=4096)

    @field_validator("id", "text")
    @classmethod
    def trim_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must contain non-whitespace characters")
        return value


class ReplySuggestions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: list[ReplyOption]

    @field_validator("options")
    @classmethod
    def exactly_three(cls, value):
        if len(value) != 3 or len({item.id for item in value}) != 3:
            raise ValueError("exactly three unique options required")
        return value


class UserStyleContext(BaseModel):
    tone: str = "natural"
    humor_level: int = 5
    flirt_level: int = 3
    message_length: str = "short"
    emoji_level: str = "low"
    directness: int = 5
    custom_instructions: str | None = None


class ConversationContext(BaseModel):
    id: str
    display_name: str | None = None


class MemoryItem(BaseModel):
    category: str
    value: str


class ContextMessage(BaseModel):
    direction: Literal["incoming", "outgoing"]
    text: str
    telegram_created_at: datetime


class AIConversationContext(BaseModel):
    user_style: UserStyleContext
    conversation: ConversationContext
    summary: str | None = None
    memory: list[MemoryItem]
    recent_messages: list[ContextMessage]
    new_messages: list[ContextMessage]
