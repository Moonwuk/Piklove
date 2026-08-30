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
    assert Settings(_env_file=None).environment == "development"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"session_secret": "development-secret-change-me"}, "SESSION_SECRET"),
        ({"telegram_webhook_secret": "dev-secret"}, "TELEGRAM_WEBHOOK_SECRET"),
        ({"cookie_secure": False}, "COOKIE_SECURE"),
        ({"web_origin": "http://app.example.com"}, "WEB_ORIGIN"),
        ({"openai_api_key": ""}, "openai_api_key"),
    ],
)
def test_production_rejects_unsafe_configuration(override, message):
    with pytest.raises(ValidationError, match=message):
        production_settings(**override)


def test_production_accepts_complete_secure_configuration():
    assert production_settings().environment == "production"
