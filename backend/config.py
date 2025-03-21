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
    REDIS_URL: str = "redis://redis:6379"
    OPENSEARCH_URL: str = "http://opensearch:9200"
    OPENSEARCH_PASSWORD: Optional[str] = None

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
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
    return Settings()


# Create a global settings instance
settings = get_settings()
