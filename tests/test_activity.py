"""Tests for SDK activity logging helpers."""

import json
from pathlib import Path

from open_data_products._activity import (
    ActivityEvent,
    find_activity_log_path,
    format_activity_line,
    sanitize_activity_details,
    write_activity_event,
)


def test_format_activity_line_is_one_readable_parseable_line() -> None:
    event = ActivityEvent(
        timestamp="2026-06-28T16:20:14Z",
        level="WARNING",
        source="cli",
        command="portfolio.sync",
        exit_code=0,
        duration_ms=297,
        message='Portfolio sync "completed"\nwith validation warnings',
        details={"workspace": "portfolio/", "warnings": 4, "errors": 0},
    )

    line = format_activity_line(event)

    assert line.count("\n") == 1
    assert line.startswith("2026-06-28T16:20:14Z [WARNING] source=cli")
    assert "command=portfolio.sync exit_code=0 duration_ms=297" in line
    assert 'message="Portfolio sync \\"completed\\"\\nwith validation warnings"' in line
    assert 'details={"errors":0,"warnings":4,"workspace":"portfolio/"}' in line


def test_sanitize_activity_details_redacts_sensitive_keys() -> None:
    details = sanitize_activity_details(
        {
            "provider": "openai",
            "apiKey": "sk-secret",
            "nested": {"password": "secret", "safe": "value"},
            "items": [{"token": "abc"}, {"count": 2}],
        }
    )

    assert details == {
        "provider": "openai",
        "apiKey": "[REDACTED]",
        "nested": {"password": "[REDACTED]", "safe": "value"},
        "items": [{"token": "[REDACTED]"}, {"count": 2}],
    }


def test_find_activity_log_path_uses_nearest_workspace_marker(tmp_path: Path) -> None:
    parent = tmp_path / "project"
    child = parent / "work" / "nested"
    child.mkdir(parents=True)
    (parent / ".git").mkdir()
    (child.parent / "generation.config.yaml").write_text("providers: {}\n")

    assert find_activity_log_path(child) == (
        child.parent / ".open-data-products" / "activity.log"
    )


def test_write_activity_event_rotates_file(tmp_path: Path) -> None:
    log_path = tmp_path / "activity.log"
    event = ActivityEvent(
        timestamp="2026-06-28T16:20:14Z",
        level="SUCCESS",
        source="cli",
        command="validate",
        exit_code=0,
        duration_ms=1,
        message="Document validation passed",
        details={"document": "product.yaml"},
    )

    for _ in range(4):
        write_activity_event(event, log_path=log_path, max_bytes=120, backups=2)

    assert log_path.is_file()
    assert (tmp_path / "activity.log.1").is_file()
    assert "command=validate" in log_path.read_text(encoding="utf-8")


def test_format_activity_details_remain_json_parseable() -> None:
    event = ActivityEvent(
        timestamp="2026-06-28T16:20:14Z",
        level="SUCCESS",
        source="cli",
        command="validate",
        exit_code=0,
        duration_ms=1,
        message="Document validation passed",
        details={"z": 1, "a": "b"},
    )

    details_text = format_activity_line(event).split(" details=", 1)[1]

    assert json.loads(details_text) == {"a": "b", "z": 1}
