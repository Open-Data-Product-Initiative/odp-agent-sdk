"""Select compact context artifacts for agent-facing workflows."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Union


@dataclass(frozen=True)
class ContextArtifact:
    """Selected context artifact content."""

    format: str
    path: Path
    content: str


def select_context_artifact(
    yaml_path: Union[str, Path],
    *,
    preferred: Sequence[str] = ("gcf", "toon", "yaml"),
) -> ContextArtifact:
    """Return the first available context artifact for a YAML file."""
    path = Path(yaml_path)
    for format_name in preferred:
        candidate = _candidate_path(path, format_name)
        if candidate.is_file():
            return ContextArtifact(
                format=format_name,
                path=candidate,
                content=candidate.read_text(encoding="utf-8"),
            )
    raise FileNotFoundError(f"No context artifact found for {path}")


def list_context_artifacts(yaml_path: Union[str, Path]) -> List[Dict[str, object]]:
    """Return metadata for compact sibling context artifacts."""
    path = Path(yaml_path)
    artifacts: List[Dict[str, object]] = []
    for format_name in ("gcf", "toon"):
        candidate = _candidate_path(path, format_name)
        if candidate.is_file():
            raw = candidate.read_bytes()
            artifacts.append(
                {
                    "format": format_name,
                    "path": str(candidate),
                    "byte_size": len(raw),
                    "line_count": _line_count(raw.decode("utf-8", errors="replace")),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "preferred": len(artifacts) == 0,
                }
            )
    return artifacts


def _candidate_path(yaml_path: Path, format_name: str) -> Path:
    if format_name == "yaml":
        return yaml_path
    if format_name in {"gcf", "toon"}:
        return yaml_path.with_suffix(f".{format_name}")
    raise ValueError(f"Unsupported context format: {format_name}")


def _line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)
