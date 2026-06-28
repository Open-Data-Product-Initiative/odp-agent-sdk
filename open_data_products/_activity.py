"""Activity logging helpers for SDK command evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

SENSITIVE_KEY_PARTS = (
    "key",
    "token",
    "secret",
    "password",
    "authorization",
    "credential",
)
WORKSPACE_MARKERS = (
    ".open-data-products",
    "portfolio.yaml",
    "recipes.config.yaml",
    "generation.config.yaml",
    ".git",
)
DEFAULT_ACTIVITY_LOG = Path(".open-data-products") / "activity.log"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUPS = 5


@dataclass
class ActivityEvent:
    """One SDK activity log event."""

    timestamp: str
    level: str
    source: str
    command: str
    exit_code: Optional[int]
    duration_ms: Optional[int]
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActivityContext:
    """Mutable command context used to enrich one terminal activity event."""

    details: Dict[str, Any] = field(default_factory=dict)
    warning: bool = False
    message: Optional[str] = None

    def add_details(self, **details: Any) -> None:
        """Merge non-None details into the activity context."""
        for key, value in details.items():
            if value is not None:
                self.details[key] = value


def utc_timestamp() -> str:
    """Return a UTC timestamp formatted for activity logs."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sanitize_activity_details(value: Any) -> Any:
    """Return safe activity details with sensitive fields redacted."""
    if isinstance(value, Mapping):
        safe: Dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in SENSITIVE_KEY_PARTS):
                safe[key_text] = "[REDACTED]"
            else:
                safe[key_text] = sanitize_activity_details(item)
        return safe
    if isinstance(value, list):
        return [sanitize_activity_details(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_activity_details(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def format_activity_line(event: ActivityEvent) -> str:
    """Render one activity event as one fixed-format line."""
    message = json.dumps(str(event.message), ensure_ascii=True)[1:-1]
    details = json.dumps(
        sanitize_activity_details(event.details),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f"{event.timestamp} [{event.level}] source={event.source} "
        f"command={event.command} exit_code={event.exit_code} "
        f'duration_ms={event.duration_ms} message="{message}" '
        f"details={details}\n"
    )


def find_activity_log_path(start: Optional[Path] = None) -> Path:
    """Return the workspace-local activity log path for a starting directory."""
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        if any((directory / marker).exists() for marker in WORKSPACE_MARKERS):
            return directory / DEFAULT_ACTIVITY_LOG
    return current / DEFAULT_ACTIVITY_LOG


def activity_logging_disabled() -> bool:
    """Return whether activity logging is disabled by environment."""
    return os.environ.get("OPEN_DATA_PRODUCTS_ACTIVITY_LOG") == "0"


def resolve_activity_log_path() -> Optional[Path]:
    """Return the active log path after environment precedence."""
    if activity_logging_disabled():
        return None
    configured = os.environ.get("OPEN_DATA_PRODUCTS_ACTIVITY_LOG_PATH")
    if configured:
        return Path(configured)
    return find_activity_log_path()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def write_activity_event(
    event: ActivityEvent,
    *,
    log_path: Optional[Path] = None,
    max_bytes: Optional[int] = None,
    backups: Optional[int] = None,
) -> None:
    """Write one activity event using stdlib rotating file logging."""
    path = log_path or resolve_activity_log_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=(
            max_bytes
            if max_bytes is not None
            else _env_int(
                "OPEN_DATA_PRODUCTS_ACTIVITY_LOG_MAX_BYTES", DEFAULT_MAX_BYTES
            )
        ),
        backupCount=(
            backups
            if backups is not None
            else _env_int("OPEN_DATA_PRODUCTS_ACTIVITY_LOG_BACKUPS", DEFAULT_BACKUPS)
        ),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    try:
        record = logging.LogRecord(
            name="open_data_products.activity",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg=format_activity_line(event).rstrip("\n"),
            args=(),
            exc_info=None,
        )
        handler.emit(record)
    finally:
        handler.close()


__all__ = [
    "ActivityContext",
    "ActivityEvent",
    "activity_logging_disabled",
    "find_activity_log_path",
    "format_activity_line",
    "resolve_activity_log_path",
    "sanitize_activity_details",
    "utc_timestamp",
    "write_activity_event",
]
