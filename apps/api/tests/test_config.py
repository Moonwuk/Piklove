import pytest
from pydantic import ValidationError

from app.config import Settings


def production_settings(**overrides):
    values = {
        "environment": "production",
        "telegram_bot_token": "bot-token",
        "telegram_webhook_secret": "webhook-secret",
        "openai_api_key": "openai-key",
        "openai_reply_model": "reply-model",
        "openai_analysis_model": "analysis-model",
        "openai_summary_model": "summary-model",
        "session_secret": "a-long-random-production-secret",
        "cookie_secure": True,
        "web_origin": "https://app.example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_development_defaults_remain_available():
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.llm_provider == "deepseek"
    assert settings.effective_llm_timeout_seconds == 30
    assert settings.effective_llm_max_retries == 1


def test_llm_settings_take_precedence_over_legacy_openai_settings():
    settings = Settings(
        _env_file=None,
        llm_api_key="new-key",
        llm_reply_model="new-model",
        llm_timeout_seconds=12,
        llm_max_retries=0,
        openai_api_key="legacy-key",
        openai_reply_model="legacy-model",
        openai_timeout_seconds=45,
        openai_max_retries=3,
    )
    assert settings.effective_llm_api_key == "new-key"
    assert settings.effective_reply_model == "new-model"
    assert settings.effective_llm_timeout_seconds == 12
    assert settings.effective_llm_max_retries == 0


@pytest.mark.parametrize(
    "override",
    [
        {"openai_timeout_seconds": 0},
        {"openai_max_retries": -1},
        {"openai_max_retries": 4},
        {"llm_timeout_seconds": 0},
        {"llm_max_retries": -1},
        {"llm_max_retries": 4},
    ],
)
def test_rejects_unbounded_openai_request_configuration(override):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **override)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"session_secret": "development-secret-change-me"}, "SESSION_SECRET"),
        ({"telegram_webhook_secret": "dev-secret"}, "TELEGRAM_WEBHOOK_SECRET"),
        ({"cookie_secure": False}, "COOKIE_SECURE"),
        ({"web_origin": "http://app.example.com"}, "WEB_ORIGIN"),
        ({"openai_api_key": ""}, "llm_api_key"),
    ],
)
def test_production_rejects_unsafe_configuration(override, message):
    with pytest.raises(ValidationError, match=message):
        production_settings(**override)


def test_production_accepts_complete_secure_configuration():
    assert production_settings().environment == "production"
