from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings.
    
    These settings can be overridden with environment variables.
    """
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "CSV Data Viewer"

    # File Settings
    CSV_FILES_DIR: str = "/app/data"

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
    
    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"]
    CORS_METHODS: list[str] = ["*"]
    CORS_HEADERS: list[str] = ["*"]
    
    class Config:
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    
    # Set PORT from environment variable BACKEND_PORT with fallback to 8000
    import os
    settings.PORT = int(os.environ.get("BACKEND_PORT", 8000))
    
    # Format Redis and OpenSearch URLs with environment variables
    redis_port = os.environ.get("REDIS_PORT", 6379)
    opensearch_port = os.environ.get("OPENSEARCH_PORT", 9200)
    
    settings.REDIS_URL = settings.REDIS_URL.format(REDIS_PORT=redis_port)
    settings.OPENSEARCH_URL = settings.OPENSEARCH_URL.format(OPENSEARCH_PORT=opensearch_port)
    
    return settings


# Create a global settings instance
settings = get_settings()
