from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ConversationAnalysis(BaseModel):
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
    id: str
    tone: Literal["natural", "playful", "direct"]
    text: str = Field(min_length=1, max_length=4096)


class ReplySuggestions(BaseModel):
    options: list[ReplyOption]

    @field_validator("options")
    @classmethod
    def exactly_three(cls, v):
        if len(v) != 3 or len({x.id for x in v}) != 3:
            raise ValueError("exactly three unique options required")
        return v


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
