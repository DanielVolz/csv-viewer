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
    OPENSEARCH_STARTUP_GRACE_SECONDS: float = 30.0
    OPENSEARCH_RETRY_BASE_SECONDS: int = 5
    OPENSEARCH_RETRY_MAX_SECONDS: int = 60
    OPENSEARCH_RETRY_MAX_ATTEMPTS: int = 5
    OPENSEARCH_WAIT_FOR_AVAILABILITY: bool = True

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
    env_wait = os.environ.get("OPENSEARCH_WAIT_FOR_AVAILABILITY")
    if env_wait is not None:
        try:
            s.OPENSEARCH_WAIT_FOR_AVAILABILITY = str(env_wait).strip().lower() not in {"0", "false", "no"}
        except Exception:
            s.OPENSEARCH_WAIT_FOR_AVAILABILITY = True

    env_grace = os.environ.get("OPENSEARCH_STARTUP_GRACE_SECONDS")
    if env_grace is not None:
        try:
            s.OPENSEARCH_STARTUP_GRACE_SECONDS = max(0.0, float(env_grace))
        except Exception:
            s.OPENSEARCH_STARTUP_GRACE_SECONDS = 0.0

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
                parent = raw_path.parent if raw_path != container_base else container_base
                if str(parent).strip() == "" or parent == pathlib.Path(""):
                    parent = container_base

                if raw_path.exists():
                    return str(raw_path), parent

                if parent == pathlib.Path("/") and raw_path != pathlib.Path("/") and raw_path.suffix == "":
                    parent = raw_path

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

                return str(raw_path), parent

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

        env_base_dir = os.environ.get("CSV_FILES_DIR")

        def _normalize_base_candidate(raw: Optional[str]) -> Optional[pathlib.Path]:
            if not raw:
                return None
            raw_path = pathlib.Path(raw)
            if raw_path.exists():
                return raw_path
            raw_pure = PurePosixPath(str(raw))
            known_suffixes = [
                PurePosixPath("netspeed"),
                PurePosixPath("history/netspeed"),
                PurePosixPath("history"),
                PurePosixPath("data"),
            ]
            for fallback in known_suffixes:
                suffix_parts = fallback.parts
                if not suffix_parts or len(raw_pure.parts) < len(suffix_parts):
                    continue
                if tuple(part.lower() for part in raw_pure.parts[-len(suffix_parts):]) == tuple(part.lower() for part in suffix_parts):
                    if fallback == PurePosixPath("netspeed"):
                        return container_base / "netspeed"
                    if fallback == PurePosixPath("history/netspeed"):
                        return container_base / "history" / "netspeed"
                    if fallback == PurePosixPath("history"):
                        return container_base / "history"
                    if fallback == PurePosixPath("data"):
                        return container_base
            return raw_path

        base_candidates: list[pathlib.Path | None] = []

        if env_base_dir:
            base_candidate = _normalize_base_candidate(env_base_dir)
            base_candidates.append(base_candidate)

        base_candidates.extend([
            current_parent,
            history_parent,
            pathlib.Path(normalized_current) if normalized_current else None,
            pathlib.Path(normalized_history) if normalized_history else None,
        ])

        base_candidates.append(container_base)

        def _sanitize_base(path: Optional[pathlib.Path]) -> Optional[pathlib.Path]:
            if path is None:
                return None
            candidate = pathlib.Path(path)
            if str(candidate).strip() == "":
                return None
            if candidate == pathlib.Path("/"):
                return None
            name_lower = candidate.name.lower()
            if name_lower.endswith(".csv"):
                candidate = candidate.parent
            elif name_lower in {"netspeed", "history"}:
                parent_path = candidate.parent
                candidate = parent_path if parent_path != pathlib.Path("") else candidate
            if candidate == pathlib.Path("/"):
                return None
            return candidate

        base_dir: Optional[pathlib.Path] = None
        for cand in base_candidates:
            sanitized = _sanitize_base(cand)
            if sanitized is not None:
                base_dir = sanitized
                break

        if base_dir is None:
            base_dir = container_base

        s.CSV_FILES_DIR = str(base_dir)

        explicit_roots: list[pathlib.Path] = []

        def _register_explicit(raw_value: Optional[str], normalized_value: str) -> None:
            if not raw_value:
                return
            try:
                candidate = pathlib.Path(normalized_value)
            except Exception:
                return
            if str(candidate).strip() == "" or candidate == pathlib.Path("/"):
                return
            explicit_roots.append(candidate)
            try:
                parent = candidate.parent
                if parent != pathlib.Path("/") and str(parent).strip():
                    explicit_roots.append(parent)
            except Exception:
                pass

        _register_explicit(env_current, normalized_current)
        _register_explicit(env_history, normalized_history)
        _register_explicit(env_base_dir, str(base_dir))

        if explicit_roots:
            dedup_roots: list[str] = []
            seen_root: set[str] = set()
            for root in explicit_roots:
                root_str = str(root)
                if root_str in seen_root:
                    continue
                seen_root.add(root_str)
                dedup_roots.append(root_str)
            s._explicit_data_roots = tuple(dedup_roots)
        else:
            s._explicit_data_roots = tuple()
    except Exception:
        s.NETSPEED_CURRENT_DIR = f"{container_base_str}/netspeed"
        s.NETSPEED_HISTORY_DIR = f"{container_base_str}/history/netspeed"
        s.CSV_FILES_DIR = container_base_str
        s._explicit_data_roots = tuple()

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
