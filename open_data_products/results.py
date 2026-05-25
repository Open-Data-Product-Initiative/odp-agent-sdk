"""Shared result types for agent-oriented SDK workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ValidationResult:
    """Common validation result across Open Data Products specifications."""

    valid: bool
    spec: str
    kind: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)
    path: Optional[str] = None
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class Resource:
    """Bundled SDK resource such as a schema, vocabulary, or JSONL index."""

    id: str
    spec: str
    type: str
    path: str
    description: str

    def to_dict(self) -> Dict[str, str]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class Reference:
    """A discovered document reference useful for agent traversal."""

    ref: str
    pointer: str
    ref_type: str
    source_spec: str
    target_spec: Optional[str] = None
    source_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Return a JSON-serializable representation."""
        return asdict(self)
