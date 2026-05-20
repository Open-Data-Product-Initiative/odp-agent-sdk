"""Shared search helpers for bundled ODP guidance records."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

Record = Dict[str, Any]
TextBuilder = Callable[[Record], str]


def searchable_record_text(record: Record) -> str:
    """Flatten a guidance record into searchable lowercase text."""
    return " ".join(_flatten_record_values(record.values())).lower()


def search_records(
    records: List[Record],
    query: Optional[str] = None,
    *,
    object_id: Optional[str] = None,
    limit: Optional[int] = None,
    searchable_text: TextBuilder,
) -> List[Record]:
    """Search records by exact id or all query terms."""
    if object_id:
        wanted = object_id.lower()
        matches = [
            record for record in records if str(record.get("id", "")).lower() == wanted
        ]
        return _limit(matches, limit)

    terms = [term.lower() for term in (query or "").split() if term.strip()]
    if not terms:
        return _limit(records, limit)

    matches = [
        record
        for record in records
        if all(term in searchable_text(record) for term in terms)
    ]
    return _limit(matches, limit)


def _limit(records: List[Record], limit: Optional[int]) -> List[Record]:
    return records[:limit] if limit is not None else records


def _flatten_record_values(values: Iterable[Any]) -> Iterable[str]:
    for value in values:
        if isinstance(value, dict):
            yield from _flatten_record_values(value.values())
        elif isinstance(value, list):
            yield from (str(item) for item in value)
        else:
            yield str(value)
