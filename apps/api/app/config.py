from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./piklove.db"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    telegram_webhook_secret: str = "dev-secret"
    openai_api_key: str = ""
    openai_reply_model: str = ""
    openai_analysis_model: str = ""
    openai_summary_model: str = ""
    openai_store: bool = False
    session_secret: str = "development-secret-change-me"
    web_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    init_data_max_age_seconds: int = 300
    raw_message_retention_days: int = 30
    message_debounce_seconds: int = 4
    ai_recent_messages_limit: int = 20
    generation_ttl_seconds: int = 900
    free_generations: int = 20
    pro_monthly_generations: int = 1000
    enable_billing: bool = False
    enable_summaries: bool = True
    enable_memory_extraction: bool = False
    enable_edit_before_send: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
