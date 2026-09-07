from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import Generation, Memory, Message, StyleProfile, UsageEvent
from app.services.quota import ensure_quota
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
    #: Settings that must be present before any request is worth attempting.
    #: An empty model name is a configuration mistake, not an upstream fault —
    #: catching it here keeps it out of the 502 bucket.
    required_settings = ("openai_api_key", "openai_reply_model", "openai_analysis_model")

    def __init__(self):
        self.s = get_settings()
        missing = [name for name in self.required_settings if not getattr(self.s, name)]
        if missing:
            raise AIProviderNotConfigured(f"missing OpenAI configuration: {', '.join(missing)}")
        self.client = AsyncOpenAI(
            api_key=self.s.openai_api_key,
            # Without an explicit budget the SDK waits 600s per call, so a
            # stalled provider would pin a Mini App request for ten minutes.
            timeout=self.s.openai_timeout_seconds,
            max_retries=self.s.openai_max_retries,
        )

    async def _structured(self, model, prompt, context, schema):
        try:
            response = await self.client.responses.parse(
                model=model,
                store=self.s.openai_store,
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context.model_dump_json()},
                ],
                text_format=schema,
            )
        except ValidationError as e:
            # The model answered off-schema (e.g. two reply options instead of
            # three). ValidationError subclasses ValueError, so left uncaught it
            # would surface to the client as the unrelated NO_CONTEXT_MESSAGES.
            raise AIProviderUnavailable("provider returned malformed structured output") from e
        except OpenAIError as e:
            # Bad model name, rejected key, rate limit, timeout, connection
            # failure: upstream faults, not defects in this service. Only the
            # exception type is carried over — provider messages can quote the
            # request, and conversation text must never reach logs or clients.
            raise AIProviderUnavailable(type(e).__name__) from e
        if response.output_parsed is None:
            raise AIProviderUnavailable("provider returned no structured output")
        return response.output_parsed

    async def analyze_conversation(self, context):
        prompt = Path(__file__).parents[1].joinpath("prompts/conversation_analyzer.md").read_text()
        return await self._structured(
            self.s.openai_analysis_model, prompt, context, ConversationAnalysis
        )

    async def generate_replies(self, context, analysis):
        prompt_file = Path(__file__).parents[1].joinpath("prompts/reply_generator.md")
        prompt = prompt_file.read_text() + "\nAnalysis:\n" + analysis.model_dump_json()
        return await self._structured(self.s.openai_reply_model, prompt, context, ReplySuggestions)

    async def summarize_conversation(self, context):
        return ""


class AIContextBuilder:
    async def build(self, db: AsyncSession, user_id: str, conversation) -> AIConversationContext:
        s = get_settings()
        style = await db.get(StyleProfile, user_id)
        memories = (
            await db.scalars(
                select(Memory).where(
                    Memory.user_id == user_id, Memory.conversation_id == conversation.id
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
                .limit(s.ai_recent_messages_limit)
            )
        ).all()
        messages = list(reversed(messages))
        ctx = [
            ContextMessage(
                direction=m.direction.value,
                text=m.text,
                telegram_created_at=m.telegram_created_at,
            )
            for m in messages
        ]
        return AIConversationContext(
            user_style=UserStyleContext.model_validate(style, from_attributes=True)
            if style
            else UserStyleContext(),
            conversation=ConversationContext(
                id=conversation.id, display_name=conversation.display_name or ""
            ),
            summary=conversation.summary,
            memory=[MemoryItem(category=m.category, value=m.value) for m in memories],
            recent_messages=ctx,
            new_messages=ctx[-3:],
        )


class SuggestionService:
    def __init__(self, provider):
        self.provider = provider
        self.builder = AIContextBuilder()

    async def generate(self, db: AsyncSession, user_id: str, conversation):
        # Reject before any billable LLM call when the monthly quota is spent.
        await ensure_quota(db, user_id)
        last = await db.scalar(
            select(Message)
            .where(
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
        analysis = await self.provider.analyze_conversation(context)
        suggestions = await self.provider.generate_replies(context, analysis)
        now = datetime.now(timezone.utc)
        g = Generation(
            user_id=user_id,
            conversation_id=conversation.id,
            source_last_message_id=last.telegram_message_id,
            analysis_json=analysis.model_dump(),
            suggestions_json=suggestions.model_dump(),
            provider="openai",
            model=get_settings().openai_reply_model,
            expires_at=now + timedelta(seconds=get_settings().generation_ttl_seconds),
        )
        db.add(g)
        db.add(UsageEvent(user_id=user_id, type="ai_generation", quantity=1, event_metadata={}))
        await db.commit()
        return g
