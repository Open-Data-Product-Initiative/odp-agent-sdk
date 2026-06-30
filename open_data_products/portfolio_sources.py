"""Portfolio source lane collection and change tracking helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .source_documents.documents import detect_source_type
from .source_documents import PORTFOLIO_DOCUMENT_SUFFIXES, load_source_documents

PORTFOLIO_SOURCE_SUFFIXES = PORTFOLIO_DOCUMENT_SUFFIXES
SOURCE_WARNING_KEY = "__warnings"


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
    collected: Dict[str, List[Dict[str, str]]] = {}
    warnings: List[str] = []
    for name, path in lanes.items():
        records = collect_source_records(path)
        warnings.extend(source_extraction_warnings({name: records}))
        collected[name] = [
            source for source in records if source.get("skipped") != "true"
        ]
    if warnings:
        collected[SOURCE_WARNING_KEY] = [{"warning": item} for item in warnings]
    return collected


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
    return [
        source
        for source in collect_source_records(path)
        if source.get("skipped") != "true"
    ]


def collect_source_records(path: Optional[Path]) -> List[Dict[str, str]]:
    """Collect source records, including skipped records with warnings."""
    if path is None:
        return []
    if not path.exists():
        raise FileNotFoundError(f"Portfolio source path not found: {path}")
    paths = [path] if path.is_file() else sorted(iter_source_files(path))
    files: List[Dict[str, str]] = []
    for source_path in paths:
        for record in load_source_documents(source_path):
            files.append(record)
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
        if lane_name == SOURCE_WARNING_KEY:
            continue
        previous_items = _source_items(previous_sources.get(lane_name))
        previous_by_id = source_hashes(previous_items)
        previous_paths = {
            source_id: _source_path(item, source_id)
            for source_id, item in _source_items_by_id(previous_items).items()
        }
        current_by_id = {
            _source_identity(source): source["sha256"]
            for source in files
            if "path" in source and "sha256" in source
        }
        current_paths = {
            _source_identity(source): _source_path(source, _source_identity(source))
            for source in files
        }
        created_ids = sorted(set(current_by_id) - set(previous_by_id))
        deleted_ids = sorted(set(previous_by_id) - set(current_by_id))
        changed_ids = sorted(
            source_id
            for source_id, sha in current_by_id.items()
            if source_id in previous_by_id and previous_by_id[source_id] != sha
        )
        unchanged_ids = sorted(
            source_id
            for source_id, sha in current_by_id.items()
            if source_id in previous_by_id and previous_by_id[source_id] == sha
        )
        lane_changes[lane_name] = {
            "created": [current_paths[source_id] for source_id in created_ids],
            "updated": [current_paths[source_id] for source_id in changed_ids],
            "unchanged": [current_paths[source_id] for source_id in unchanged_ids],
            "removed": [previous_paths[source_id] for source_id in deleted_ids],
            "createdSourceIds": created_ids,
            "updatedSourceIds": changed_ids,
            "unchangedSourceIds": unchanged_ids,
            "removedSourceIds": deleted_ids,
        }
        removed.extend(previous_paths[source_id] for source_id in deleted_ids)
    return {"lanes": lane_changes, "removed": sorted(removed)}


def source_hashes(value: Any) -> Dict[str, str]:
    """Return source hashes keyed by source ID, falling back to path."""
    hashes = {}
    for item in _source_items(value):
        if not item.get("sha256"):
            continue
        source_id = _source_identity(item)
        if source_id:
            hashes[source_id] = str(item["sha256"])
    return hashes


def source_hashes_by_lane(state: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Return source hashes grouped by lane from a saved state document."""
    sources = state.get("sources") if isinstance(state, dict) else None
    if not isinstance(sources, dict):
        return {}
    return {
        str(lane): source_hashes(files)
        for lane, files in sources.items()
        if lane != SOURCE_WARNING_KEY and source_hashes(files)
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
        if lane_name == SOURCE_WARNING_KEY:
            continue
        lane_change = lane_changes.get(lane_name)
        if not isinstance(lane_change, dict):
            changed_lanes[lane_name] = []
            continue
        changed_source_ids = set(lane_change.get("createdSourceIds", [])) | set(
            lane_change.get("updatedSourceIds", [])
        )
        changed_lanes[lane_name] = [
            source for source in files if _source_identity(source) in changed_source_ids
        ]
    return changed_lanes


def source_change_warnings(changes: Dict[str, Any]) -> List[str]:
    """Return user-facing warnings for removed source files."""
    removed = changes.get("removed")
    if not isinstance(removed, list):
        return []
    return [f"Source file no longer present: {path}" for path in removed]


def source_extraction_warnings(lanes: Dict[str, List[Dict[str, str]]]) -> List[str]:
    """Return source extraction warnings stored on skipped source records."""
    warnings: List[str] = []
    for files in lanes.values():
        for source in files:
            warning = source.get("warning")
            if warning:
                warnings.append(str(warning))
    return list(dict.fromkeys(warnings))


def _source_identity(source: Dict[str, Any]) -> str:
    source_id = source.get("sourceId")
    if source_id:
        return str(source_id)
    path = source.get("path")
    if not path:
        return ""
    source_unit = source.get("sourceUnit") or "file"
    source_unit_id = source.get("sourceUnitId") or "1"
    return f"{path}#{source_unit}-{source_unit_id}"


def _source_items(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _source_items_by_id(value: Any) -> Dict[str, Dict[str, Any]]:
    return {
        source_id: item
        for item in _source_items(value)
        for source_id in [_source_identity(item)]
        if source_id
    }


def _source_path(source: Dict[str, Any], fallback: str) -> str:
    return str(source.get("path") or fallback)


def iter_source_files(path: Path) -> Iterable[Path]:
    """Yield supported source files below a folder."""
    for child in path.rglob("*"):
        if not child.is_file():
            continue
        if child.suffix.lower() in PORTFOLIO_SOURCE_SUFFIXES:
            yield child
            continue
        source_type, _detection_method = detect_source_type(child)
        if source_type in PORTFOLIO_SOURCE_SUFFIXES:
            yield child
