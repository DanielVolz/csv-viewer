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
    NETSPEED_CURRENT_DIR: str = "/app/data"
    NETSPEED_HISTORY_DIR: str = "/app/data"

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
    # API behavior
    SEARCH_TIMEOUT_SECONDS: int = 20
    SEARCH_MAX_RESULTS: int = 20000

    # Archive retention (OpenSearch archive_netspeed)
    ARCHIVE_RETENTION_YEARS: int = 4

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
    # Optional split layout from env (host paths). If unset, fallback to CSV_FILES_DIR.
    s.NETSPEED_CURRENT_DIR = os.environ.get("NETSPEED_CURRENT_DIR", s.CSV_FILES_DIR)
    s.NETSPEED_HISTORY_DIR = os.environ.get("NETSPEED_HISTORY_DIR", s.CSV_FILES_DIR)

    # Normalize host-style paths to container paths if necessary.
    # We assume CSV_FILES_DIR (host) is mounted at /app/data inside container.
    try:
        import pathlib
        host_base = os.environ.get("CSV_FILES_DIR", s.CSV_FILES_DIR)
        container_base = "/app/data"
        def _normalize(p: str) -> str:
            pp = pathlib.Path(p)
            if pp.exists():
                return str(pp)
            if host_base and p.startswith(host_base):
                candidate = container_base + p[len(host_base):]
                if pathlib.Path(candidate).exists():
                    return candidate
            return p
        s.NETSPEED_CURRENT_DIR = _normalize(s.NETSPEED_CURRENT_DIR)
        s.NETSPEED_HISTORY_DIR = _normalize(s.NETSPEED_HISTORY_DIR)
    except Exception:
        pass

    # Compose service URLs
    redis_port = os.environ.get("REDIS_PORT", 6379)
    opensearch_port = os.environ.get("OPENSEARCH_PORT", 9200)
    # Prefer explicit env overrides for URLs to allow dev/prod separation by hostname
    explicit_redis = os.environ.get("REDIS_URL")
    explicit_os = os.environ.get("OPENSEARCH_URL")
    if explicit_redis:
        s.REDIS_URL = explicit_redis
    else:
        s.REDIS_URL = s.REDIS_URL.format(REDIS_PORT=redis_port)
    if explicit_os:
        s.OPENSEARCH_URL = explicit_os
    else:
        s.OPENSEARCH_URL = s.OPENSEARCH_URL.format(OPENSEARCH_PORT=opensearch_port)

    # Use value from Settings (no env override)
    # If left empty, UI will hide rebuild controls

    # Clamp/archive retention to a sane range if misconfigured
    try:
        if s.ARCHIVE_RETENTION_YEARS is None:
            s.ARCHIVE_RETENTION_YEARS = 4
        else:
            s.ARCHIVE_RETENTION_YEARS = max(1, int(s.ARCHIVE_RETENTION_YEARS))
    except Exception:
        s.ARCHIVE_RETENTION_YEARS = 4

    return s


# Create a global settings instance
settings = get_settings()
