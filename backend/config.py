from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings.

    These settings can be overridden with environment variables.
    """
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "CSV Data Viewer"

    # File Settings
    CSV_FILES_DIR: str = "/app/data"  # Default, can be overridden by environment variable

    # Database Settings
    REDIS_URL: str = "redis://redis:{REDIS_PORT}"
    OPENSEARCH_URL: str = "http://opensearch:{OPENSEARCH_PORT}"
    OPENSEARCH_PASSWORD: Optional[str] = None

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: Optional[int] = None  # Will be set from environment variable
    RELOAD: bool = True
    WORKERS: int = 1

    # Logging
    LOG_LEVEL: str = "INFO"

    # SSH username (used for simple gating of rebuild UI). Leave empty to disable rebuild UI.
    # Explicitly set environment variable SSH_USERNAME=volzd to enable.

    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"]
    CORS_METHODS: list[str] = ["*"]
    CORS_HEADERS: list[str] = ["*"]

    class Config:
        case_sensitive = True


def get_settings() -> Settings:
    """Build a fresh settings instance (no cache so env changes are picked up)."""
    import os
    s = Settings()

    # Dynamic ports / paths
    s.PORT = int(os.environ.get("BACKEND_PORT", 8000))
    s.CSV_FILES_DIR = "/app/data"

    # Compose service URLs
    redis_port = os.environ.get("REDIS_PORT", 6379)
    opensearch_port = os.environ.get("OPENSEARCH_PORT", 9200)
    s.REDIS_URL = s.REDIS_URL.format(REDIS_PORT=redis_port)
    s.OPENSEARCH_URL = s.OPENSEARCH_URL.format(OPENSEARCH_PORT=opensearch_port)

    # Use value from Settings (no env override)
    # If left empty, UI will hide rebuild controls

    return s


# Create a global settings instance
settings = get_settings()
