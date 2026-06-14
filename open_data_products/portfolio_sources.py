"""Portfolio source lane collection and change tracking helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PORTFOLIO_SOURCE_SUFFIXES = (".md", ".txt", ".yaml", ".yml", ".json")


def collect_source_lanes(
    *,
    objectives: Optional[Path],
    use_cases: Optional[Path],
    signals: Optional[Path],
    products: Optional[Path],
) -> Dict[str, List[Dict[str, str]]]:
    """Collect source files grouped by portfolio source lane."""
    lanes = {
        "objectives": objectives,
        "useCases": use_cases,
        "signals": signals,
        "products": products,
    }
    return {name: collect_source_files(path) for name, path in lanes.items()}


def resolve_source_lane_paths(
    previous_state: Dict[str, Any],
    *,
    objectives: Optional[Path],
    use_cases: Optional[Path],
    signals: Optional[Path],
    products: Optional[Path],
) -> Dict[str, str]:
    """Resolve explicit or saved source lane paths."""
    saved = previous_state.get("sourceLanePaths")
    if not isinstance(saved, dict):
        saved = {}
    lanes = {
        "objectives": objectives or saved.get("objectives"),
        "useCases": use_cases or saved.get("useCases"),
        "signals": signals or saved.get("signals"),
        "products": products or saved.get("products"),
    }
    return {name: str(path) for name, path in lanes.items() if path is not None}


def collect_source_files(path: Optional[Path]) -> List[Dict[str, str]]:
    """Collect source file text and hashes from one path."""
    if path is None:
        return []
    if not path.exists():
        raise FileNotFoundError(f"Portfolio source path not found: {path}")
    paths = [path] if path.is_file() else sorted(iter_source_files(path))
    files = []
    for source_path in paths:
        text = source_path.read_text(encoding="utf-8")
        files.append(
            {
                "path": str(source_path),
                "text": text,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return files


def source_changes(
    previous_state: Dict[str, Any],
    lanes: Dict[str, List[Dict[str, str]]],
) -> Dict[str, Any]:
    """Compare saved source hashes with current source lanes."""
    previous_sources = previous_state.get("sources")
    if not isinstance(previous_sources, dict):
        previous_sources = {}
    lane_changes: Dict[str, Dict[str, List[str]]] = {}
    removed: List[str] = []
    for lane_name, files in lanes.items():
        previous_by_path = source_hashes(previous_sources.get(lane_name))
        current_by_path = {
            source["path"]: source["sha256"]
            for source in files
            if "path" in source and "sha256" in source
        }
        created = sorted(set(current_by_path) - set(previous_by_path))
        deleted = sorted(set(previous_by_path) - set(current_by_path))
        changed = sorted(
            path
            for path, sha in current_by_path.items()
            if path in previous_by_path and previous_by_path[path] != sha
        )
        unchanged = sorted(
            path
            for path, sha in current_by_path.items()
            if path in previous_by_path and previous_by_path[path] == sha
        )
        lane_changes[lane_name] = {
            "created": created,
            "updated": changed,
            "unchanged": unchanged,
            "removed": deleted,
        }
        removed.extend(deleted)
    return {"lanes": lane_changes, "removed": sorted(removed)}


def source_hashes(value: Any) -> Dict[str, str]:
    """Return source hashes keyed by source path."""
    if not isinstance(value, list):
        return {}
    hashes = {}
    for item in value:
        if isinstance(item, dict) and item.get("path") and item.get("sha256"):
            hashes[str(item["path"])] = str(item["sha256"])
    return hashes


def source_hashes_by_lane(state: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Return source hashes grouped by lane from a saved state document."""
    sources = state.get("sources") if isinstance(state, dict) else None
    if not isinstance(sources, dict):
        return {}
    return {
        str(lane): source_hashes(files)
        for lane, files in sources.items()
        if source_hashes(files)
    }


def changed_source_lanes(
    lanes: Dict[str, List[Dict[str, str]]],
    changes: Dict[str, Any],
) -> Dict[str, List[Dict[str, str]]]:
    """Return current source lane files that were created or updated."""
    lane_changes = changes.get("lanes")
    if not isinstance(lane_changes, dict):
        return {name: [] for name in lanes}
    changed_lanes: Dict[str, List[Dict[str, str]]] = {}
    for lane_name, files in lanes.items():
        lane_change = lane_changes.get(lane_name)
        if not isinstance(lane_change, dict):
            changed_lanes[lane_name] = []
            continue
        changed_paths = set(lane_change.get("created", [])) | set(
            lane_change.get("updated", [])
        )
        changed_lanes[lane_name] = [
            source for source in files if source.get("path") in changed_paths
        ]
    return changed_lanes


def source_change_warnings(changes: Dict[str, Any]) -> List[str]:
    """Return user-facing warnings for removed source files."""
    removed = changes.get("removed")
    if not isinstance(removed, list):
        return []
    return [f"Source file no longer present: {path}" for path in removed]


def iter_source_files(path: Path) -> Iterable[Path]:
    """Yield supported source files below a folder."""
    for child in path.rglob("*"):
        if child.is_file() and child.suffix.lower() in PORTFOLIO_SOURCE_SUFFIXES:
            yield child
