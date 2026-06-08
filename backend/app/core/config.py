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
    openai_api_key: str | None = None

    backup_dir: str = "./backups/postgres"
    backup_retention_days: int = 35
    wal_archive_dir: str = "./backups/wal_archive"


settings = Settings()
