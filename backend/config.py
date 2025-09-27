from pydantic_settings import BaseSettings
from typing import Optional, Tuple


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
    OPENSEARCH_STARTUP_TIMEOUT_SECONDS: int = 45
    OPENSEARCH_STARTUP_POLL_SECONDS: float = 3.0
    OPENSEARCH_RETRY_BASE_SECONDS: int = 5
    OPENSEARCH_RETRY_MAX_SECONDS: int = 60
    OPENSEARCH_RETRY_MAX_ATTEMPTS: int = 5

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
    container_base_str = "/app/data"
    s.CSV_FILES_DIR = container_base_str
    env_current = os.environ.get("NETSPEED_CURRENT_DIR")
    env_history = os.environ.get("NETSPEED_HISTORY_DIR")

    # Normalize host-style paths to container paths if necessary.
    # We prefer explicit NETSPEED_* env values and fall back to known container layout.
    try:
        import pathlib
        from pathlib import PurePosixPath

        container_base = pathlib.Path(container_base_str)

        def _normalize_path(raw_value: Optional[str], fallbacks: list[pathlib.Path]) -> Tuple[str, pathlib.Path]:
            """Convert a potentially host-style path to the container layout.

            Returns a tuple of (normalized_path, container_parent).
            """
            if raw_value:
                raw_path = pathlib.Path(raw_value)
                if raw_path.exists():
                    return str(raw_path), raw_path.parent

                raw_pure = PurePosixPath(str(raw_value))
                for fallback in fallbacks:
                    try:
                        rel = PurePosixPath(fallback.relative_to(container_base))
                    except Exception:
                        rel = PurePosixPath()
                    rel_parts = rel.parts
                    if not rel_parts:
                        continue
                    if len(raw_pure.parts) >= len(rel_parts) and raw_pure.parts[-len(rel_parts):] == rel_parts:
                        normalized = container_base.joinpath(*rel_parts)
                        return str(normalized), normalized.parent

            primary = fallbacks[0] if fallbacks else container_base
            return str(primary), primary.parent if primary != container_base else container_base

        current_defaults = [container_base / "netspeed", container_base]
        history_defaults = [
            container_base / "history" / "netspeed",
            container_base / "history",
            container_base,
        ]

        normalized_current, current_parent = _normalize_path(env_current, current_defaults)
        normalized_history, history_parent = _normalize_path(env_history, history_defaults)

        s.NETSPEED_CURRENT_DIR = normalized_current
        s.NETSPEED_HISTORY_DIR = normalized_history

        # Derive base data directory from available parents (prefer current parent)
        base_parent = current_parent or history_parent or container_base
        s.CSV_FILES_DIR = str(base_parent)
    except Exception:
        s.NETSPEED_CURRENT_DIR = f"{container_base_str}/netspeed"
        s.NETSPEED_HISTORY_DIR = f"{container_base_str}/history/netspeed"
        s.CSV_FILES_DIR = container_base_str

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
