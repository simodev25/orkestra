"""Orkestra platform configuration."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Orkestra"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://orkestra:orkestra@localhost:5432/orkestra"
    DATABASE_URL_SYNC: str = "postgresql://orkestra:orkestra@localhost:5432/orkestra"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "orkestra-dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Authentication
    API_KEYS: str = "test-orkestra-api-key"  # comma-separated valid API keys
    AUTH_ENABLED: bool = True
    PUBLIC_PATHS: str = "/api/health,/api/metrics,/docs,/openapi.json,/redoc"

    # Storage
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_PATH: str = "./storage/documents"

    # LLM Provider
    LLM_PROVIDER: str = "ollama"
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "mistral-small-latest"
    OPENAI_BASE_URL: str = "https://api.mistral.ai/v1"

    # Observability
    LOG_LEVEL: str = "INFO"
    PROMETHEUS_ENABLED: bool = False
    OTEL_ENDPOINT: str = ""

    # Obot MCP source of truth
    OBOT_BASE_URL: str = ""
    OBOT_API_KEY: str = ""
    OBOT_TIMEOUT_SECONDS: float = 8.0
    OBOT_USE_MOCK: bool = True
    OBOT_FALLBACK_TO_MOCK: bool = True

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3300,http://localhost:5173"

    # Encryption
    FERNET_KEY: str = ""  # Auto-generates in dev if empty; set in production

    @field_validator("FERNET_KEY", mode="after")
    @classmethod
    def warn_empty_fernet_key(cls, v: str) -> str:
        """Log a warning when FERNET_KEY is empty — ephemeral key is dev-only."""
        if not v:
            import logging
            logging.getLogger("orkestra.config").warning(
                "FERNET_KEY is not set. Secrets are encrypted with an ephemeral key "
                "that changes on every restart. Set ORKESTRA_FERNET_KEY in production."
            )
        return v

    class Config:
        env_file = ".env"
        env_prefix = "ORKESTRA_"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
