from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root .env (works when running from backend/)
_ROOT_DIR = Path(__file__).resolve().parents[3]
_ENV_FILE = _ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        extra="ignore",
    )

    app_env: str = "development"
    app_port: int = 8000
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:15432/ai_support"
    )
    database_replica_url: str | None = (
        "postgresql+asyncpg://analytics_reader:analytics_pass@localhost:15433/ai_support"
    )
    redis_url: str = "redis://localhost:6379/0"
    redis_chat_memory_url: str = "redis://localhost:6379/1"
    redis_session_ttl_seconds: int = 86400  # 24 hours
    redis_chat_memory_ttl_seconds: int = 1800  # 30 minutes
    redis_user_context_ttl_seconds: int = 604800  # 7 days
    rate_limit_user_messages_per_minute: int = 10
    rate_limit_ip_requests_per_minute: int = 1000
    redis_queue_url: str = "redis://localhost:6379/2"
    queue_max_retry_attempts: int = 3
    queue_retry_base_seconds: int = 1
    queue_consumer_block_ms: int = 5000
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    chat_greeting_message: str = (
        "Hi there! Welcome to AI Customer Support. How can we help you today?"
    )
    chat_inactivity_trigger_seconds: int = 30
    chat_history_message_limit: int = 10
    openai_api_key: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    backup_dir: str = "./backups/postgres"
    backup_retention_days: int = 35
    wal_archive_dir: str = "./backups/wal_archive"


settings = Settings()
