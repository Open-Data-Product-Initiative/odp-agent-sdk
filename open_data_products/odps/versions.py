"""ODPS version markers and bundled schema lookup."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import json

ODPS_V41 = "4.1"
ODPS_V42 = "4.2"
ODPS_V41_SCHEMA_URI = "https://opendataproducts.org/v4.1/schema/odps.json"
ODPS_V42_SCHEMA_URI = "https://opendataproducts.org/v4.2/schema/odps.json"

_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "data" / "schema"
_SCHEMA_PATHS = {
    ODPS_V41: _SCHEMA_DIRECTORY / "odps-v4.1.json",
    ODPS_V42: _SCHEMA_DIRECTORY / "odps-v4.2.json",
}


def normalize_version(value: object) -> Optional[str]:
    """Return a supported ODPS version marker, if one was supplied."""
    text = str(value).strip().lower()
    if text in {"4.1", "v4.1"}:
        return ODPS_V41
    if text in {"4.2", "v4.2"}:
        return ODPS_V42
    return None


def detect_version(document: Dict[str, Any]) -> Optional[str]:
    """Detect the ODPS version from a document marker or schema URI."""
    version = normalize_version(document.get("version", ""))
    schema = str(document.get("schema", "")).lower()
    schema_version = (
        ODPS_V42
        if "/v4.2/" in schema
        else ODPS_V41
        if "/v4.1/" in schema
        else None
    )
    if version and schema_version and version != schema_version:
        return None
    return version or schema_version


def schema_path(version: str) -> Path:
    """Return the bundled canonical JSON schema path for ``version``."""
    try:
        return _SCHEMA_PATHS[version]
    except KeyError as exc:
        raise ValueError("Unsupported ODPS version: {0}".format(version)) from exc


def load_schema(version: str) -> Dict[str, Any]:
    """Load the bundled canonical JSON schema for ``version``."""
    with schema_path(version).open(encoding="utf-8") as schema_file:
        return json.load(schema_file)
