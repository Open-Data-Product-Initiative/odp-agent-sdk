"""Internal file-loading helpers shared across ODP specs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import yaml


def load_mapping(
    path: Path,
    *,
    yaml_loader: Optional[Type[yaml.SafeLoader]] = None,
    root_name: str = "Document",
) -> Dict[str, Any]:
    """Load a JSON or YAML document that must have a mapping root."""
    with path.open(encoding="utf-8") as handle:
        if path.suffix.lower() == ".json":
            data = json.load(handle)
        else:
            loader = yaml_loader or yaml.SafeLoader
            data = yaml.load(handle, Loader=loader)
    if not isinstance(data, dict):
        raise ValueError(f"{root_name} must contain an object at the document root")
    return data


def load_jsonl_records(path: Path) -> List[Dict[str, Any]]:
    """Load newline-delimited JSON objects from ``path``."""
    records: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: record is not an object")
            records.append(record)
    return records
