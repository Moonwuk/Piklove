import httpx

from app.config import Settings, get_settings
from app.integrations.llm.errors import LLMNotConfigured
from app.integrations.llm.providers import DeepSeekProvider, OllamaCloudProvider


def create_llm_provider(
    settings: Settings | None = None, client: httpx.AsyncClient | None = None
) -> DeepSeekProvider | OllamaCloudProvider:
    settings = settings or get_settings()
    if not settings.effective_llm_api_key:
        raise LLMNotConfigured
    if not settings.effective_analysis_model or not settings.effective_reply_model:
        raise LLMNotConfigured
    if settings.llm_provider == "deepseek":
        return DeepSeekProvider(settings, client)
    return OllamaCloudProvider(settings, client)
