"""Search bundled ODPR recipe guidance records."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, List, Mapping, Optional, Sequence, Union

PathLike = Union[str, Path]
DEFAULT_RECIPE_GUIDANCE = (
    Path(__file__).resolve().parent / "data" / "recipes" / "recipes.jsonl"
)


def load_recipe_guidance(path: Optional[PathLike] = None) -> List[Dict[str, object]]:
    """Load bundled ODPR recipe guidance records."""
    source = Path(path) if path else DEFAULT_RECIPE_GUIDANCE
    text = source.read_text(encoding="utf-8")
    return _parse_json_objects(text)


def get_recipe_guidance(
    guidance_id: str,
    *,
    path: Optional[PathLike] = None,
) -> Dict[str, object]:
    """Return one ODPR recipe guidance record by id."""
    for record in load_recipe_guidance(path):
        if record.get("id") == guidance_id:
            return record
    raise KeyError(f"Unknown ODPR recipe guidance record: {guidance_id}")


def search_recipe_guidance(
    query: str,
    *,
    limit: int = 5,
    path: Optional[PathLike] = None,
) -> List[Dict[str, object]]:
    """Search bundled ODPR recipe guidance records."""
    terms = [term.lower() for term in query.split() if term.strip()]
    if not terms:
        return load_recipe_guidance(path)[:limit]
    scored = []
    for record in load_recipe_guidance(path):
        haystack = _record_text(record).lower()
        score = sum(haystack.count(term) for term in terms)
        if score:
            scored.append((score, str(record.get("id", "")), record))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [record for _, _, record in scored[:limit]]


def _parse_json_objects(text: str) -> List[Dict[str, object]]:
    decoder = json.JSONDecoder()
    index = 0
    records: List[Dict[str, object]] = []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        value, index = decoder.raw_decode(text, index)
        if not isinstance(value, dict):
            raise ValueError("ODPR recipe guidance records must be JSON objects.")
        records.append(value)
    return records


def _record_text(record: Mapping[str, object]) -> str:
    parts: List[str] = []
    for value in record.values():
        _append_text(parts, value)
    return " ".join(parts)


def _append_text(parts: List[str], value: object) -> None:
    if isinstance(value, str):
        parts.append(value)
    elif isinstance(value, Mapping):
        for child in value.values():
            _append_text(parts, child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            _append_text(parts, child)
