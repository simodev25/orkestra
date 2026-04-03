"""Orkestra platform configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Orkestra"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://orkestra:orkestra@localhost:5432/orkestra"
    DATABASE_URL_SYNC: str = "postgresql://orkestra:orkestra@localhost:5432/orkestra"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "orkestra-dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Storage
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_PATH: str = "./storage/documents"

    # Observability
    LOG_LEVEL: str = "INFO"
    PROMETHEUS_ENABLED: bool = False

    class Config:
        env_file = ".env"
        env_prefix = "ORKESTRA_"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
