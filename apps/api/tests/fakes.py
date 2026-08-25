from app.services.schemas import (
    AIConversationContext,
    ConversationAnalysis,
    ReplyOption,
    ReplySuggestions,
)


class FakeLLMProvider:
    def __init__(self) -> None:
        self.analyze_calls = 0
        self.reply_calls = 0

    async def analyze_conversation(self, context: AIConversationContext) -> ConversationAnalysis:
        self.analyze_calls += 1
        return ConversationAnalysis(
            stage="rapport",
            engagement="medium",
            tone="warm",
            boundary_detected=False,
            question_requires_answer=True,
            meeting_signal=False,
            recommended_action="answer_question",
        )

    async def generate_replies(
        self,
        context: AIConversationContext,
        analysis: ConversationAnalysis,
    ) -> ReplySuggestions:
        self.reply_calls += 1
        return ReplySuggestions(
            options=[
                ReplyOption(id="1", tone="natural", text="Natural reply"),
                ReplyOption(id="2", tone="playful", text="Playful reply"),
                ReplyOption(id="3", tone="direct", text="Direct reply"),
            ]
        )

    async def summarize_conversation(self, context: AIConversationContext) -> str:
        return ""


class FakeTelegramGateway:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_business_message(
        self, business_connection_id: str, chat_id: int, text: str
    ) -> dict:
        self.sent.append(
            {
                "business_connection_id": business_connection_id,
                "chat_id": chat_id,
                "text": text,
            }
        )
        return {"message_id": 9001, "date": 1_700_000_000}

    async def get_business_connection(self, business_connection_id: str) -> dict:
        return {"id": business_connection_id, "is_enabled": True}
