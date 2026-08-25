from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.telegram.client import TelegramClient, TelegramGateway
from app.security.session import read_session
from app.services.ai import LLMProvider, OpenAIProvider, SuggestionService


def get_telegram_gateway() -> TelegramGateway:
    """Return the Telegram adapter used by explicit user-triggered sends.

    Kept as a FastAPI dependency so tests never need to patch global state and
    route code never constructs an external gateway directly.
    """

    return TelegramClient()


def get_llm_provider() -> LLMProvider:
    """Return the configured backend-only LLM provider."""

    return OpenAIProvider()


def get_suggestion_service(
    provider: LLMProvider = Depends(get_llm_provider),
) -> SuggestionService:
    return SuggestionService(provider)


async def current_user_id(session: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    user_id = read_session(session or "")
    if not user_id:
        raise HTTPException(401, "AUTH_REQUIRED")
    return user_id
