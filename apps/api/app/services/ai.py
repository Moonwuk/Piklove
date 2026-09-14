from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import Generation, Memory, Message, StyleProfile
from app.services.quota import reserve_quota
from app.services.schemas import (
    AIConversationContext,
    ContextMessage,
    ConversationAnalysis,
    ConversationContext,
    MemoryItem,
    ReplySuggestions,
    UserStyleContext,
)


class NoContextMessages(ValueError):
    """The conversation retains no message text to build a suggestion from."""


class AIProviderNotConfigured(RuntimeError):
    """Provider credentials or model names are missing from the environment."""


class AIProviderUnavailable(RuntimeError):
    """The provider call failed, timed out, or returned output we cannot use."""


class LLMProvider(Protocol):
    async def analyze_conversation(
        self, context: AIConversationContext
    ) -> ConversationAnalysis: ...
    async def generate_replies(
        self, context: AIConversationContext, analysis: ConversationAnalysis
    ) -> ReplySuggestions: ...
    async def summarize_conversation(self, context: AIConversationContext) -> str: ...


class OpenAIProvider:
    required_settings = ("openai_api_key", "openai_reply_model", "openai_analysis_model")

    def __init__(self):
        self.settings = get_settings()
        missing = [
            name for name in self.required_settings if not getattr(self.settings, name)
        ]
        if missing:
            raise AIProviderNotConfigured(
                f"missing OpenAI configuration: {', '.join(missing)}"
            )
        self.client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            timeout=self.settings.openai_timeout_seconds,
            max_retries=self.settings.openai_max_retries,
        )

    async def _structured(self, model, prompt, context, schema):
        try:
            response = await self.client.responses.parse(
                model=model,
                store=self.settings.openai_store,
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context.model_dump_json()},
                ],
                text_format=schema,
            )
        except ValidationError as error:
            raise AIProviderUnavailable(
                "provider returned malformed structured output"
            ) from error
        except OpenAIError as error:
            raise AIProviderUnavailable(type(error).__name__) from error
        if response.output_parsed is None:
            raise AIProviderUnavailable("provider returned no structured output")
        return response.output_parsed

    async def analyze_conversation(self, context):
        prompt = Path(__file__).parents[1].joinpath("prompts/conversation_analyzer.md").read_text()
        return await self._structured(
            self.settings.openai_analysis_model, prompt, context, ConversationAnalysis
        )

    async def generate_replies(self, context, analysis):
        prompt_file = Path(__file__).parents[1].joinpath("prompts/reply_generator.md")
        prompt = prompt_file.read_text() + "\nAnalysis:\n" + analysis.model_dump_json()
        return await self._structured(
            self.settings.openai_reply_model, prompt, context, ReplySuggestions
        )

    async def summarize_conversation(self, context):
        return ""


class AIContextBuilder:
    async def build(
        self, db: AsyncSession, user_id: str, conversation
    ) -> AIConversationContext:
        settings = get_settings()
        style = await db.get(StyleProfile, user_id)
        memories = (
            await db.scalars(
                select(Memory).where(
                    Memory.user_id == user_id,
                    Memory.conversation_id == conversation.id,
                )
            )
        ).all()
        messages = (
            await db.scalars(
                select(Message)
                .where(
                    Message.user_id == user_id,
                    Message.conversation_id == conversation.id,
                    Message.deleted_at.is_(None),
                    Message.text.is_not(None),
                )
                .order_by(Message.telegram_created_at.desc())
                .limit(settings.ai_recent_messages_limit)
            )
        ).all()
        messages = list(reversed(messages))
        context_messages = [
            ContextMessage(
                direction=message.direction.value,
                text=message.text,
                telegram_created_at=message.telegram_created_at,
            )
            for message in messages
        ]
        return AIConversationContext(
            user_style=UserStyleContext.model_validate(style, from_attributes=True)
            if style
            else UserStyleContext(),
            conversation=ConversationContext(
                id=conversation.id, display_name=conversation.display_name or ""
            ),
            summary=conversation.summary,
            memory=[
                MemoryItem(category=memory.category, value=memory.value)
                for memory in memories
            ],
            recent_messages=context_messages,
            new_messages=context_messages[-3:],
        )


class SuggestionService:
    def __init__(self, provider):
        self.provider = provider
        self.builder = AIContextBuilder()

    async def generate(self, db: AsyncSession, user_id: str, conversation):
        last = await db.scalar(
            select(Message)
            .where(
                Message.user_id == user_id,
                Message.conversation_id == conversation.id,
                Message.deleted_at.is_(None),
                Message.text.is_not(None),
            )
            .order_by(Message.telegram_message_id.desc())
            .limit(1)
        )
        if not last:
            raise NoContextMessages("conversation has no retained messages")
        context = await self.builder.build(db, user_id, conversation)
        # Reserve atomically immediately before the first potentially billable
        # provider call. A failed provider call still consumes the reservation.
        await reserve_quota(db, user_id)
        analysis = await self.provider.analyze_conversation(context)
        suggestions = await self.provider.generate_replies(context, analysis)
        now = datetime.now(timezone.utc)
        generation = Generation(
            user_id=user_id,
            conversation_id=conversation.id,
            source_last_message_id=last.telegram_message_id,
            analysis_json=analysis.model_dump(),
            suggestions_json=suggestions.model_dump(),
            provider="openai",
            model=get_settings().openai_reply_model,
            expires_at=now + timedelta(seconds=get_settings().generation_ttl_seconds),
        )
        db.add(generation)
        await db.commit()
        return generation
