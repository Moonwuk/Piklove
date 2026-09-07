"""Every provider failure mode must surface as a named error, never a 500.

Before this, only a missing API key was handled. Anything else the OpenAI SDK
raised — rejected key, unknown model name, rate limit, timeout — escaped as
INTERNAL_ERROR, and an off-schema answer escaped as a pydantic ValidationError,
which the route mistook for the unrelated NO_CONTEXT_MESSAGES because
ValidationError subclasses ValueError.
"""

from types import SimpleNamespace

import anyio
import httpx
import openai
import pytest

from app.config import get_settings
from app.services.ai import AIProviderNotConfigured, AIProviderUnavailable, OpenAIProvider
from app.services.schemas import AIConversationContext, ConversationContext, UserStyleContext

CREDENTIALS = ("OPENAI_API_KEY", "OPENAI_REPLY_MODEL", "OPENAI_ANALYSIS_MODEL")


@pytest.fixture(autouse=True)
def isolated_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def provider(monkeypatch):
    for name in CREDENTIALS:
        monkeypatch.setenv(name, "configured")
    get_settings.cache_clear()
    return OpenAIProvider()


def context():
    return AIConversationContext(
        user_style=UserStyleContext(),
        conversation=ConversationContext(id="conversation-1", display_name="Contact"),
        memory=[],
        recent_messages=[],
        new_messages=[],
    )


def stub_responses(provider, parse):
    """Replace the SDK client with one whose responses.parse runs `parse`."""
    provider.client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    return provider


@pytest.mark.parametrize("blank", CREDENTIALS)
def test_incomplete_configuration_is_refused_before_any_request(monkeypatch, blank):
    for name in CREDENTIALS:
        monkeypatch.setenv(name, "" if name == blank else "configured")
    get_settings.cache_clear()

    with pytest.raises(AIProviderNotConfigured, match=blank.lower()):
        OpenAIProvider()


def test_request_budget_is_bounded(provider):
    """The SDK default is 600s and two retries — long enough to pin a request."""
    settings = get_settings()
    assert provider.client.timeout == settings.openai_timeout_seconds
    assert provider.client.max_retries == settings.openai_max_retries
    assert settings.openai_timeout_seconds <= 60


def test_provider_exception_becomes_unavailable(provider):
    timeout = openai.APITimeoutError(
        request=httpx.Request("POST", "https://api.openai.com/v1/responses")
    )

    async def parse(**_kwargs):
        raise timeout

    async def exercise():
        with pytest.raises(AIProviderUnavailable, match="APITimeoutError"):
            await stub_responses(provider, parse).analyze_conversation(context())

    anyio.run(exercise)


def test_provider_exception_carries_no_message_content(provider):
    """Provider errors can quote the request; only the type may be propagated."""
    secret = "private conversation text"

    async def parse(**_kwargs):
        raise openai.OpenAIError(secret)

    async def exercise():
        with pytest.raises(AIProviderUnavailable) as caught:
            await stub_responses(provider, parse).analyze_conversation(context())
        return str(caught.value)

    assert secret not in anyio.run(exercise)


def test_off_schema_output_is_not_reported_as_missing_context(provider):
    async def parse(*, text_format, **_kwargs):
        # Mirror the SDK: the model's answer is validated against the requested
        # schema. An empty object satisfies neither of ours.
        return text_format.model_validate({})

    async def exercise():
        with pytest.raises(AIProviderUnavailable, match="malformed"):
            await stub_responses(provider, parse).analyze_conversation(context())

    anyio.run(exercise)


def test_missing_structured_output_is_unavailable(provider):
    async def parse(**_kwargs):
        return SimpleNamespace(output_parsed=None)

    async def exercise():
        with pytest.raises(AIProviderUnavailable, match="no structured output"):
            await stub_responses(provider, parse).analyze_conversation(context())

    anyio.run(exercise)
