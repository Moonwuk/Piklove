import asyncio

from app.services.schemas import (
    AIConversationContext,
    ConversationContext,
    UserStyleContext,
)
from tests.fakes import FakeLLMProvider, FakeTelegramGateway


def context() -> AIConversationContext:
    return AIConversationContext(
        user_style=UserStyleContext(),
        conversation=ConversationContext(id="conversation-1"),
        summary=None,
        memory=[],
        recent_messages=[],
        new_messages=[],
    )


def test_fake_llm_returns_exactly_three_structured_options():
    async def scenario():
        provider = FakeLLMProvider()
        analysis = await provider.analyze_conversation(context())
        suggestions = await provider.generate_replies(context(), analysis)
        assert [option.tone for option in suggestions.options] == [
            "natural",
            "playful",
            "direct",
        ]
        assert provider.analyze_calls == 1
        assert provider.reply_calls == 1

    asyncio.run(scenario())


def test_fake_telegram_records_server_owned_recipient_fields():
    async def scenario():
        gateway = FakeTelegramGateway()
        result = await gateway.send_business_message("bc-1", 42, "Selected reply")
        assert result["message_id"] == 9001
        assert gateway.sent == [
            {
                "business_connection_id": "bc-1",
                "chat_id": 42,
                "text": "Selected reply",
            }
        ]

    asyncio.run(scenario())
