"""Shared search helpers for bundled ODP guidance records."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

Record = Dict[str, Any]
TextBuilder = Callable[[Record], str]


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
