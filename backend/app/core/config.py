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
    redis_session_ttl_seconds: int = 1800  # 30 minutes
    session_cleanup_interval_seconds: int = 3600
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
    chat_ai_processing_delay_seconds: float = 6.0
    chat_typing_still_working_after_seconds: int = 5
    chat_ws_heartbeat_interval_seconds: int = 25
    chat_ws_pong_timeout_seconds: int = 10
    chat_ws_max_connections: int = 10000
    chat_ws_replay_buffer_size: int = 100
    chat_ws_shutdown_timeout_seconds: float = 5.0
    chat_memory_cached_messages: int = 50
    storage_provider: str = "local"
    storage_bucket: str = "ai-support-uploads"
    storage_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    gcs_credentials_path: str | None = None
    upload_local_dir: str = "./uploads"
    upload_signing_secret: str = "dev-upload-signing-secret-change-me"
    upload_max_file_size_bytes: int = 10 * 1024 * 1024
    upload_max_files_per_message: int = 3
    upload_chunk_size_bytes: int = 1024 * 1024
    upload_signed_url_ttl_seconds: int = 3600
    openai_api_key: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    backup_dir: str = "./backups/postgres"
    backup_retention_days: int = 35
    wal_archive_dir: str = "./backups/wal_archive"


settings = Settings()
