"""Application configuration and environment variable management."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings loaded from environment variables.

    Environment variables use the SHORTVIDEOCLI_ prefix.

    For example:
        SHORTVIDEOCLI_LOG_LEVEL=DEBUG
        SHORTVIDEOCLI_DATABASE_URL=sqlite:///shortvideocli.db
    """

    model_config = SettingsConfigDict(
        env_prefix="SHORTVIDEOCLI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "testing", "production"] = "development"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_file: Path = Path("logs/app.log")

    # Database
    database_url: str = "sqlite+aiosqlite:///shortvideocli.db"

    # External API credentials
    youtube_api_key: SecretStr | None = None
    youtube_client_id: SecretStr | None = None
    youtube_client_secret: SecretStr | None = None
    openai_api_key: SecretStr | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance.

    Caching avoids repeatedly parsing environment variables and the .env file.
    Clear the cache in tests if settings need to be reloaded.
    """
    return Settings()
