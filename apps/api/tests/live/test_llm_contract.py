import os
from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.integrations.llm import create_llm_provider
from app.services.schemas import (
    AIConversationContext,
    ContextMessage,
    ConversationContext,
    UserStyleContext,
)

pytestmark = pytest.mark.skipif(
    os.getenv("LLM_LIVE_TEST") != "1",
    reason="set LLM_LIVE_TEST=1 to call the configured provider with synthetic data",
)


@pytest.mark.anyio
async def test_configured_provider_contract():
    settings = Settings()
    provider = create_llm_provider(settings)
    message = ContextMessage(
        direction="incoming",
        text="Hi! This is synthetic contract-test data. How is your day?",
        telegram_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    context = AIConversationContext(
        user_style=UserStyleContext(),
        conversation=ConversationContext(id="synthetic-live-test", display_name="Test Contact"),
        memory=[],
        recent_messages=[message],
        new_messages=[message],
    )
    try:
        analysis = await provider.analyze_conversation(context)
        suggestions = await provider.generate_replies(context, analysis)
    finally:
        await provider.aclose()

    assert len(suggestions.options) == 3
