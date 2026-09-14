import json
from datetime import datetime, timezone

import httpx
import pytest

from app.config import Settings
from app.integrations.llm.errors import LLMError, LLMInvalidResponse, LLMTimeout
from app.integrations.llm.factory import create_llm_provider
from app.integrations.llm.providers import DeepSeekProvider, OllamaCloudProvider
from app.services.schemas import (
    AIConversationContext,
    ContextMessage,
    ConversationContext,
    UserStyleContext,
)


def settings(provider="deepseek", retries=0):
    return Settings(
        _env_file=None,
        llm_provider=provider,
        llm_api_key="test-key",
        llm_analysis_model="analysis-model",
        llm_reply_model="reply-model",
        llm_max_retries=retries,
    )


def context():
    message = ContextMessage(
        direction="incoming",
        text="Synthetic test message",
        telegram_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return AIConversationContext(
        user_style=UserStyleContext(),
        conversation=ConversationContext(id="synthetic", display_name="Test"),
        memory=[],
        recent_messages=[message],
        new_messages=[message],
    )


ANALYSIS = {
    "stage": "rapport",
    "engagement": "high",
    "tone": "warm",
    "boundary_detected": False,
    "question_requires_answer": False,
    "meeting_signal": False,
    "recommended_action": "continue_topic",
}
REPLIES = {
    "options": [
        {"id": "one", "tone": "natural", "text": "One"},
        {"id": "two", "tone": "playful", "text": "Two"},
        {"id": "three", "tone": "direct", "text": "Three"},
    ]
}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("provider_class", "provider_name", "base_url", "path"),
    [
        (DeepSeekProvider, "deepseek", "https://api.deepseek.com", "/chat/completions"),
        (OllamaCloudProvider, "ollama_cloud", "https://ollama.com", "/api/chat"),
    ],
)
async def test_provider_contract(provider_class, provider_name, base_url, path):
    requests = []

    async def handler(request):
        requests.append(request)
        request_body = json.loads(request.content)
        content = json.dumps(ANALYSIS if request_body["model"] == "analysis-model" else REPLIES)
        body = (
            {"choices": [{"message": {"content": content}}]}
            if provider_name == "deepseek"
            else {"message": {"content": content}}
        )
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": "Bearer test-key"},
        transport=httpx.MockTransport(handler),
    ) as client:
        provider = provider_class(settings(provider_name), client)
        analysis = await provider.analyze_conversation(context())
        replies = await provider.generate_replies(context(), analysis)

    assert analysis.model_dump() == ANALYSIS
    assert replies.model_dump() == REPLIES
    assert len(requests) == 2
    assert requests[0].url == f"{base_url}{path}"
    assert requests[1].url == f"{base_url}{path}"
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "analysis-model"
    assert payload["stream"] is False
    assert "Synthetic test message" in payload["messages"][1]["content"]
    if provider_name == "deepseek":
        assert payload["response_format"] == {"type": "json_object"}
    else:
        assert "format" not in payload
    reply_payload = json.loads(requests[1].content)
    assert reply_payload["model"] == "reply-model"
    assert json.dumps(ANALYSIS, separators=(",", ":")) in reply_payload["messages"][1]["content"]


@pytest.mark.anyio
@pytest.mark.parametrize("content", ["", "not json", '{"stage":"rapport"}', '{"extra":1}'])
async def test_provider_rejects_empty_or_invalid_output(content):
    async def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    async with httpx.AsyncClient(
        base_url="https://api.deepseek.com", transport=httpx.MockTransport(handler)
    ) as client:
        provider = DeepSeekProvider(settings(), client)
        with pytest.raises(LLMInvalidResponse):
            await provider.analyze_conversation(context())


@pytest.mark.anyio
async def test_provider_retries_timeout_within_budget():
    attempts = 0

    async def handler(request):
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(
        base_url="https://api.deepseek.com", transport=httpx.MockTransport(handler)
    ) as client:
        provider = DeepSeekProvider(settings(retries=1), client)
        with pytest.raises(LLMTimeout):
            await provider.analyze_conversation(context())

    assert attempts == 2


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [401, 429, 500])
async def test_provider_maps_http_failures_without_exposing_response(status_code):
    async def handler(request):
        return httpx.Response(status_code, text="sensitive upstream response")

    async with httpx.AsyncClient(
        base_url="https://api.deepseek.com", transport=httpx.MockTransport(handler)
    ) as client:
        provider = DeepSeekProvider(settings(), client)
        with pytest.raises(LLMError) as error:
            await provider.analyze_conversation(context())

    assert "sensitive upstream response" not in str(error.value)


@pytest.mark.anyio
async def test_factory_selects_configured_provider():
    deepseek = create_llm_provider(settings("deepseek"))
    ollama = create_llm_provider(settings("ollama_cloud"))
    try:
        assert isinstance(deepseek, DeepSeekProvider)
        assert isinstance(ollama, OllamaCloudProvider)
        assert deepseek.client.base_url == httpx.URL("https://api.deepseek.com")
        assert ollama.client.base_url == httpx.URL("https://ollama.com")
        assert deepseek.client.headers["Authorization"] == "Bearer test-key"
        assert deepseek.client.timeout.read == 30
    finally:
        await deepseek.aclose()
        await ollama.aclose()
