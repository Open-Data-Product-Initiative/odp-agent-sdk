"""Portfolio plan transformation and artifact conversion helpers."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ._io import load_mapping
from ._portfolio_normalization import (
    _normalize_enum,
    normalize_generated_odps_product as _normalize_generated_odps_product,
)
from ._portfolio_values import (
    as_list as _list,
    count as _count,
    path_id as _path_id,
    text as _text,
    title_from_text as _title_from_text,
)
from ._portfolio_rendering import EXECUTIVE_SUMMARY_SWOT_BUCKETS
from ._portfolio_workspace import (
    empty_catalog as _empty_catalog,
    empty_graph as _empty_graph,
    load_optional_mapping as _load_optional_mapping,
    load_product_specs as _load_product_specs,
    product_details as _product_details,
    write_yaml as _write_yaml,
)
from .odpc import load_catalog
from .odpg import load_graph

ODPC_STATUSES = {"draft", "active", "paused", "completed", "retired"}
ODPC_STATUS_ALIASES = {
    "proposed": "draft",
    "planned": "draft",
    "planning": "draft",
    "development": "active",
    "testing": "active",
    "acceptance": "active",
    "production": "active",
    "sunset": "retired",
    "deprecated": "retired",
    "archived": "retired",
}
ODPC_SIGNAL_TYPES = {
    "demand",
    "competitive",
    "market",
    "technology",
    "policy",
    "operational",
    "quality",
    "usage",
    "risk",
    "gap",
}
ODPC_SIGNAL_TYPE_ALIASES = {
    "portfolio": "operational",
    "product": "operational",
    "business": "demand",
    "commercial": "market",
}
ODPG_EDGE_TYPES = {
    "uses",
    "supports",
    "contributesTo",
    "measures",
    "tracks",
    "dependsOn",
    "produces",
    "consumes",
    "governedBy",
    "ownedBy",
    "alignsWith",
    "alignWith",
    "relatedTo",
    "impacts",
    "derivedFrom",
    "exposes",
    "monitors",
    "identifies",
}
ODPG_EDGE_TYPE_ALIASES = {
    "informs": "relatedTo",
    "influences": "impacts",
    "enables": "supports",
    "needs": "uses",
}


def _reconcile_plan_identity(
    plan: Dict[str, Any],
    previous_state: Dict[str, Any],
) -> Dict[str, Any]:
    registry = previous_state.get("identityRegistry")
    if not isinstance(registry, dict):
        return plan

    reconciled = deepcopy(plan)
    id_remap: Dict[str, str] = {}
    for collection, registry_key in (
        ("businessObjectives", "businessObjectives"),
        ("useCases", "useCases"),
        ("signals", "signals"),
    ):
        previous_by_fingerprint = _registry_by_fingerprint(registry.get(registry_key))
        for item in _list(reconciled, collection):
            previous = previous_by_fingerprint.get(_artifact_fingerprint(item))
            if not previous:
                continue
            proposed_id = _text(item.get("id"))
            stable_id = _text(previous.get("id"))
            if proposed_id and stable_id and proposed_id != stable_id:
                id_remap[proposed_id] = stable_id
                item["id"] = stable_id

    previous_products = _registry_by_fingerprint(registry.get("products"))
    for product in _list(reconciled, "products"):
        reference = product.get("productReference")
        odps_product = product.get("odpsProduct")
        if not isinstance(reference, dict):
            continue
        previous = previous_products.get(_artifact_fingerprint(reference))
        if not previous:
            continue
        proposed_id = _text(reference.get("id"))
        stable_id = _text(previous.get("id"))
        if proposed_id and stable_id and proposed_id != stable_id:
            id_remap[proposed_id] = stable_id
            reference["id"] = stable_id
        proposed_product_id = _text(reference.get("productID"))
        stable_product_id = _text(previous.get("productID"))
        if proposed_product_id and stable_product_id:
            if proposed_product_id != stable_product_id:
                id_remap[proposed_product_id] = stable_product_id
            reference["productID"] = stable_product_id
            _set_odps_product_id(odps_product, stable_product_id)

    for edge in _list(reconciled, "graphEdges"):
        for key in ("source", "target"):
            value = _text(edge.get(key))
            if value in id_remap:
                edge[key] = id_remap[value]

    return reconciled


def _identity_registry(plan: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    return {
        "businessObjectives": [
            _registry_entry(item, "id") for item in _list(plan, "businessObjectives")
        ],
        "useCases": [_registry_entry(item, "id") for item in _list(plan, "useCases")],
        "signals": [_registry_entry(item, "id") for item in _list(plan, "signals")],
        "products": [_product_registry_entry(item) for item in _list(plan, "products")],
    }


def _registry_entry(item: Dict[str, Any], id_key: str) -> Dict[str, str]:
    return {
        "fingerprint": _artifact_fingerprint(item),
        id_key: _text(item.get(id_key)),
    }


def _product_registry_entry(product: Dict[str, Any]) -> Dict[str, str]:
    reference = product.get("productReference")
    if not isinstance(reference, dict):
        reference = {}
    return {
        "fingerprint": _artifact_fingerprint(reference),
        "id": _text(reference.get("id")),
        "productID": _text(reference.get("productID")),
    }


def _registry_by_fingerprint(value: Any) -> Dict[str, Dict[str, str]]:
    if not isinstance(value, list):
        return {}
    entries = {}
    for item in value:
        if isinstance(item, dict):
            fingerprint = _text(item.get("fingerprint"))
            if fingerprint:
                entries[fingerprint] = {str(key): str(val) for key, val in item.items()}
    return entries


def _artifact_fingerprint(item: Dict[str, Any]) -> str:
    return _normalize_identity_text(_text(item.get("name") or item.get("id")))


def _normalize_identity_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _set_odps_product_id(value: Any, product_id: str) -> None:
    if not isinstance(value, dict):
        return
    product = value.get("product")
    if not isinstance(product, dict):
        return
    details = product.get("details")
    if isinstance(details, dict):
        english = details.get("en")
        if isinstance(english, dict):
            english["productID"] = product_id
            return
    product["productID"] = product_id


def _normalize_portfolio_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deepcopy(plan)
    for item in _list(normalized, "businessObjectives"):
        item["status"] = _normalize_enum(
            item.get("status"), ODPC_STATUSES, ODPC_STATUS_ALIASES, "draft"
        )
    for item in _list(normalized, "useCases"):
        item["status"] = _normalize_enum(
            item.get("status"), ODPC_STATUSES, ODPC_STATUS_ALIASES, "draft"
        )
    for item in _list(normalized, "signals"):
        item["type"] = _normalize_enum(
            item.get("type"), ODPC_SIGNAL_TYPES, ODPC_SIGNAL_TYPE_ALIASES, "operational"
        )
        if not isinstance(item.get("source"), dict):
            item["source"] = {
                "origin": "internal",
                "method": "generated portfolio source lanes",
            }
        if not _text(item.get("observedAt")):
            item["observedAt"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

    for product in _list(normalized, "products"):
        reference = product.get("productReference")
        if isinstance(reference, dict):
            reference["status"] = _normalize_enum(
                reference.get("status"), ODPC_STATUSES, ODPC_STATUS_ALIASES, "draft"
            )
        _normalize_generated_odps_product(product.get("odpsProduct"))

    for edge in _list(normalized, "graphEdges"):
        source = _text(edge.get("source") or edge.get("from"))
        target = _text(edge.get("target") or edge.get("to"))
        edge_type = _normalize_enum(
            edge.get("type"), ODPG_EDGE_TYPES, ODPG_EDGE_TYPE_ALIASES, "relatedTo"
        )
        confidence = _normalize_enum(
            edge.get("confidence"), {"high", "medium", "low"}, {}, "medium"
        )
        edge.clear()
        edge["source"] = source
        edge["target"] = target
        edge["type"] = edge_type
        edge["confidence"] = confidence

    return normalized


def _catalog_from_fragments(root: Path) -> Dict[str, Any]:
    existing = _load_optional_mapping(root / "odpc" / "catalog.yaml")
    catalog_root = existing.get("catalog") if isinstance(existing, dict) else {}
    metadata = {}
    if isinstance(catalog_root, dict) and isinstance(
        catalog_root.get("metadata"), dict
    ):
        metadata = catalog_root["metadata"]
    catalog: Dict[str, Any] = {"metadata": metadata or _default_catalog_metadata(root)}
    fragments = _fragment_collections(root / "odpc" / "fragments")
    for key in ("businessObjectives", "useCases", "signals", "productReferences"):
        if fragments[key]:
            catalog[key] = fragments[key]
    return {
        "schema": existing.get(
            "schema", "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml"
        ),
        "version": str(existing.get("version") or "1.0"),
        "kind": existing.get("kind", "Catalog"),
        "catalog": catalog,
    }


def _sync_product_references_from_odps(
    root: Path,
    catalog: Dict[str, Any],
    product_specs: Dict[str, Dict[str, Any]],
) -> List[Tuple[Path, str]]:
    catalog_root = catalog.get("catalog")
    if not isinstance(catalog_root, dict):
        return []
    writes: List[Tuple[Path, str]] = []
    for reference in _list(catalog_root, "productReferences"):
        product_id = _text(reference.get("productID") or reference.get("id"))
        product_info = product_specs.get(product_id)
        if not product_info:
            continue
        document = product_info.get("document")
        if not isinstance(document, dict):
            continue
        details = _product_details(document)
        product_path = product_info.get("path")
        if _merge_product_reference_details(
            reference,
            details,
            document=document,
            product_path=product_path if isinstance(product_path, Path) else None,
        ):
            writes.append(
                _write_yaml(
                    _product_reference_fragment_path(root, reference),
                    {"productReference": reference},
                )
            )
    return writes


def _product_reference_fragment_path(root: Path, reference: Dict[str, Any]) -> Path:
    """Return the existing fragment path for one logical product reference."""
    fragments_dir = root / "odpc" / "fragments"
    reference_id = _fragment_identity(reference)
    if reference_id:
        for path in _fragment_paths(fragments_dir):
            document = load_mapping(path, root_name="ODPC fragment")
            candidate = document.get("productReference")
            if (
                isinstance(candidate, dict)
                and _fragment_identity(candidate) == reference_id
            ):
                return path
    return fragments_dir / f"product_reference_{_file_id(reference)}.yaml"


def _merge_product_reference_details(
    reference: Dict[str, Any],
    details: Dict[str, Any],
    *,
    document: Dict[str, Any],
    product_path: Optional[Path],
) -> bool:
    changed = False
    for source_key, target_key in (
        ("name", "name"),
        ("description", "description"),
        ("valueProposition", "valueProposition"),
    ):
        value = _text(details.get(source_key))
        if value and reference.get(target_key) != {"en": value}:
            reference[target_key] = {"en": value}
            changed = True
    for key in ("status", "type"):
        value = _text(details.get(key))
        if value and reference.get(key) != value:
            reference[key] = value
            changed = True
    visibility = _odpc_product_visibility(details.get("visibility"))
    if visibility and reference.get("visibility") != visibility:
        reference["visibility"] = visibility
        changed = True
    if product_path is not None:
        expected_model = {
            "standard": "ODPS",
            "version": _text(document.get("version"), "4.2"),
            "format": "yaml",
            "$ref": "../odps/products/{0}".format(product_path.name),
        }
        if reference.get("productModel") != expected_model:
            reference["productModel"] = expected_model
            changed = True
    return changed


def _odpc_product_visibility(value: Any) -> str:
    visibility = _text(value)
    if visibility in {"public", "internal", "restricted", "private"}:
        return visibility
    if visibility == "organisation":
        return "internal"
    if visibility == "invitation":
        return "restricted"
    return ""


def _default_catalog_metadata(root: Path) -> Dict[str, Any]:
    portfolio = _load_optional_mapping(root / "portfolio.yaml")
    metadata = portfolio.get("metadata") if isinstance(portfolio, dict) else {}
    name = (
        metadata.get("name", "Portfolio") if isinstance(metadata, dict) else "Portfolio"
    )
    description = (
        metadata.get("description", "Portfolio synced from YAML artifacts.")
        if isinstance(metadata, dict)
        else "Portfolio synced from YAML artifacts."
    )
    return {
        "id": (
            metadata.get("id", "CAT-PORTFOLIO")
            if isinstance(metadata, dict)
            else "CAT-PORTFOLIO"
        ),
        "name": {"en": name},
        "description": {"en": description},
    }


def _apply_catalog_title(
    catalog: Dict[str, Any], title: Optional[str]
) -> Dict[str, Any]:
    if not title:
        return catalog
    catalog_root = catalog.setdefault("catalog", {})
    if not isinstance(catalog_root, dict):
        return catalog
    metadata = catalog_root.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        catalog_root["metadata"] = metadata
    metadata["name"] = {"en": title}
    return catalog


def _fragment_collections(fragments_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    collections: Dict[str, List[Dict[str, Any]]] = {
        "businessObjectives": [],
        "useCases": [],
        "signals": [],
        "productReferences": [],
    }
    if not fragments_dir.exists():
        return collections
    keys = {
        "businessObjective": "businessObjectives",
        "useCase": "useCases",
        "signal": "signals",
        "productReference": "productReferences",
    }
    selected: Dict[str, Dict[str, Tuple[int, str, Dict[str, Any]]]] = {
        key: {} for key in collections
    }
    anonymous: Dict[str, List[Dict[str, Any]]] = {key: [] for key in collections}
    for path in _fragment_paths(fragments_dir):
        document = load_mapping(path, root_name="ODPC fragment")
        for source_key, target_key in keys.items():
            value = document.get(source_key)
            if isinstance(value, dict):
                identity = _fragment_identity(value)
                if not identity:
                    anonymous[target_key].append(value)
                    continue
                candidate = (path.stat().st_mtime_ns, str(path), value)
                existing = selected[target_key].get(identity)
                if existing is None or candidate[:2] > existing[:2]:
                    selected[target_key][identity] = candidate
    for target_key in collections:
        collections[target_key] = [
            candidate[2]
            for candidate in sorted(
                selected[target_key].values(), key=lambda candidate: candidate[1]
            )
        ] + anonymous[target_key]
    return collections


def _fragment_paths(fragments_dir: Path) -> List[Path]:
    """Return supported fragment paths in stable order."""
    return sorted(
        [
            *fragments_dir.glob("*.yaml"),
            *fragments_dir.glob("*.yml"),
            *fragments_dir.glob("*.json"),
        ]
    )


def _fragment_identity(value: Dict[str, Any]) -> str:
    """Return a logical identity shared by equivalent fragment files."""
    return _text(value.get("id") or value.get("productID"))


def _plan_from_catalog(catalog: Dict[str, Any]) -> Dict[str, Any]:
    catalog_root = catalog.get("catalog") if isinstance(catalog, dict) else {}
    if not isinstance(catalog_root, dict):
        catalog_root = {}
    return {
        "businessObjectives": _list(catalog_root, "businessObjectives"),
        "useCases": _list(catalog_root, "useCases"),
        "signals": _list(catalog_root, "signals"),
        "products": [
            {"productReference": item}
            for item in _list(catalog_root, "productReferences")
        ],
    }


def _plan_from_workspace(root: Path) -> Dict[str, Any]:
    catalog_path = root / "odpc" / "catalog.yaml"
    catalog = load_catalog(catalog_path) if catalog_path.exists() else _empty_catalog()
    plan = _plan_from_catalog(catalog)
    product_specs = _load_product_specs(root)
    for product in _list(plan, "products"):
        reference = product.get("productReference")
        if not isinstance(reference, dict):
            continue
        product_id = _text(reference.get("productID") or reference.get("id"))
        product_info = product_specs.get(product_id)
        if isinstance(product_info, dict):
            document = product_info.get("document")
            if isinstance(document, dict):
                product["odpsProduct"] = document

    graph_path = root / "odpg" / "graph.yaml"
    graph = load_graph(graph_path) if graph_path.exists() else _empty_graph()
    graph_payload = graph.get("graph") if isinstance(graph, dict) else {}
    if isinstance(graph_payload, dict):
        edges = []
        for edge in _list(graph_payload, "edges"):
            edges.append(
                {
                    "source": _text(edge.get("source") or edge.get("from")),
                    "target": _text(edge.get("target") or edge.get("to")),
                    "type": _text(edge.get("type"), "relatedTo"),
                    "confidence": _text(edge.get("confidence"), "medium"),
                }
            )
        if edges:
            plan["graphEdges"] = edges
    return plan


def _merge_portfolio_plans(
    existing: Dict[str, Any],
    delta: Dict[str, Any],
) -> Dict[str, Any]:
    merged = deepcopy(existing) if isinstance(existing, dict) else {}
    if not isinstance(delta, dict):
        return merged
    metadata = delta.get("metadata")
    if isinstance(metadata, dict) and not isinstance(merged.get("metadata"), dict):
        merged["metadata"] = metadata
    executive_summary = delta.get("executiveSummary")
    if isinstance(executive_summary, dict):
        merged["executiveSummary"] = executive_summary
    for collection in ("businessObjectives", "useCases", "signals"):
        merged[collection] = _merge_items_by_id(
            _list(merged, collection), _list(delta, collection)
        )
    merged["products"] = _merge_products(
        _list(merged, "products"), _list(delta, "products")
    )
    merged["graphEdges"] = _merge_graph_edges(
        _list(merged, "graphEdges"), _list(delta, "graphEdges")
    )
    warnings = [
        *_string_list(merged.get("warnings")),
        *_string_list(delta.get("warnings")),
    ]
    if warnings:
        merged["warnings"] = list(dict.fromkeys(warnings))
    return merged


def _filter_delta_plan_by_changed_lanes(
    delta: Dict[str, Any],
    process_lanes: Dict[str, List[Dict[str, str]]],
    existing: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(delta, dict):
        return {}
    filtered: Dict[str, Any] = {}
    for key in ("metadata", "warnings", "executiveSummary"):
        value = delta.get(key)
        if value is not None:
            filtered[key] = value

    lane_collections = (
        ("objectives", "businessObjectives"),
        ("useCases", "useCases"),
        ("signals", "signals"),
        ("products", "products"),
    )
    accepted_ids: Set[str] = set()
    for lane, collection in lane_collections:
        if process_lanes.get(lane):
            items = _list(delta, collection)
            if items:
                filtered[collection] = items
                accepted_ids.update(_plan_item_ids(collection, items))

    existing_ids = _plan_ids(existing)
    discarded_ids = _plan_ids(delta) - accepted_ids
    graph_edges = []
    for edge in _list(delta, "graphEdges"):
        source = _text(edge.get("source") or edge.get("from"))
        target = _text(edge.get("target") or edge.get("to"))
        if not ({source, target} & accepted_ids):
            continue
        if ({source, target} & discarded_ids) - accepted_ids:
            continue
        if (
            source in accepted_ids | existing_ids
            and target in accepted_ids | existing_ids
        ):
            graph_edges.append(edge)
    if graph_edges:
        filtered["graphEdges"] = graph_edges
    return filtered


def _plan_ids(plan: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for collection in ("businessObjectives", "useCases", "signals", "products"):
        ids.update(_plan_item_ids(collection, _list(plan, collection)))
    return ids


def _plan_item_ids(collection: str, items: List[Dict[str, Any]]) -> Set[str]:
    ids: Set[str] = set()
    for item in items:
        if collection == "products":
            reference = item.get("productReference")
            if isinstance(reference, dict):
                for key in ("id", "productID"):
                    item_id = _text(reference.get(key))
                    if item_id:
                        ids.add(item_id)
            continue
        item_id = _text(item.get("id"))
        if item_id:
            ids.add(item_id)
    return ids


def _merge_items_by_id(
    existing: List[Dict[str, Any]],
    delta: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged = {
        (_text(item.get("id")) or _artifact_fingerprint(item)): item
        for item in existing
    }
    for item in delta:
        key = _text(item.get("id")) or _artifact_fingerprint(item)
        merged[key] = item
    return list(merged.values())


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _merge_products(
    existing: List[Dict[str, Any]],
    delta: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged = {_product_merge_key(item): item for item in existing}
    for item in delta:
        merged[_product_merge_key(item)] = item
    return list(merged.values())


def _product_merge_key(product: Dict[str, Any]) -> str:
    reference = product.get("productReference")
    if isinstance(reference, dict):
        return _text(
            reference.get("productID") or reference.get("id")
        ) or _artifact_fingerprint(reference)
    return _artifact_fingerprint(product)


def _merge_graph_edges(
    existing: List[Dict[str, Any]],
    delta: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged = {_graph_edge_key(item): item for item in existing}
    for item in delta:
        merged[_graph_edge_key(item)] = item
    return list(merged.values())


def _graph_edge_key(edge: Dict[str, Any]) -> str:
    source = _text(edge.get("source") or edge.get("from"))
    target = _text(edge.get("target") or edge.get("to"))
    edge_type = _text(edge.get("type"), "relatedTo")
    return f"{source}|{edge_type}|{target}"


def _ensure_changed_signal_source_coverage(
    plan: Dict[str, Any],
    lanes: Dict[str, List[Dict[str, str]]],
    source_changes: Dict[str, Any],
) -> Dict[str, Any]:
    lane_changes = source_changes.get("lanes")
    if not isinstance(lane_changes, dict):
        return plan
    signal_changes = lane_changes.get("signals")
    if not isinstance(signal_changes, dict):
        return plan
    changed_paths = {
        str(path)
        for key in ("created", "updated")
        for path in signal_changes.get(key, [])
    }
    if not changed_paths:
        return plan

    covered = deepcopy(plan) if isinstance(plan, dict) else {}
    signals = _list(covered, "signals")
    existing_ids = {_text(item.get("id")) for item in signals}
    for source in lanes.get("signals", []):
        if source.get("path") not in changed_paths:
            continue
        if _signal_source_is_represented(signals, source):
            continue
        signal = _draft_signal_from_source(source, existing_ids)
        existing_ids.add(_text(signal.get("id")))
        signals.append(signal)
        warnings = covered.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(
                f"Draft signal created from changed source {source['path']} because the model did not return a separate signal artifact."
            )
    if signals:
        covered["signals"] = signals
    return covered


def _signal_source_is_represented(
    signals: List[Dict[str, Any]],
    source: Dict[str, str],
) -> bool:
    source_key = _normalize_identity_text(Path(source["path"]).stem.replace("-", " "))
    source_title = _normalize_identity_text(_source_signal_title(source))
    source_terms = _meaningful_terms(source.get("text", ""))
    for signal in signals:
        identity = _normalize_identity_text(
            " ".join(
                [
                    _text(signal.get("id")),
                    _text(signal.get("name")),
                    _text(signal.get("description")),
                ]
            )
        )
        if source_key and source_key in identity:
            return True
        if source_title and source_title in identity:
            return True
        if _term_overlap(source_terms, _meaningful_terms(identity)) >= 4:
            return True
    return False


def _draft_signal_from_source(
    source: Dict[str, str],
    existing_ids: set,
) -> Dict[str, Any]:
    title = _source_signal_title(source)
    signal_id = _unique_signal_id(Path(source["path"]).stem, existing_ids)
    return {
        "id": signal_id,
        "name": {"en": title},
        "description": {"en": _source_signal_description(source)},
        "type": "operational",
        "confidence": "medium",
        "source": {
            "origin": "internal",
            "method": "generated from changed signal source",
        },
    }


def _unique_signal_id(stem: str, existing_ids: set) -> str:
    base = f"SIG-{_path_id(stem).upper()}"
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _source_signal_title(source: Dict[str, str]) -> str:
    text = source.get("text", "")
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("#").strip()
        if not line:
            continue
        lowered = line.casefold()
        if lowered.startswith("signal:"):
            line = line.split(":", 1)[1].strip()
        if line:
            return _title_from_text(line)
    return _title_from_text(Path(source["path"]).stem.replace("-", " "))


def _source_signal_description(source: Dict[str, str]) -> str:
    text = source.get("text", "")
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.casefold().startswith("signal:"):
            line = line.split(":", 1)[1].strip()
        if line:
            lines.append(line)
        if len(" ".join(lines)) >= 220:
            break
    description = " ".join(lines).strip()
    return description or f"Draft signal created from {source['path']}."


def _meaningful_terms(value: str) -> set:
    stopwords = {
        "and",
        "are",
        "for",
        "from",
        "has",
        "have",
        "inside",
        "into",
        "that",
        "the",
        "this",
        "use",
        "uses",
        "with",
    }
    terms = set()
    current = []
    for char in value.casefold():
        if char.isalnum():
            current.append(char)
        elif current:
            term = "".join(current)
            if len(term) >= 4 and term not in stopwords:
                terms.add(term)
            current = []
    if current:
        term = "".join(current)
        if len(term) >= 4 and term not in stopwords:
            terms.add(term)
    return terms


def _term_overlap(left: set, right: set) -> int:
    return len(left & right)


def _catalog_document(plan: Dict[str, Any]) -> Dict[str, Any]:
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    catalog: Dict[str, Any] = {
        "metadata": {
            "id": metadata.get("id", "CAT-PORTFOLIO"),
            "name": {"en": metadata.get("name", "Generated Portfolio")},
            "description": {
                "en": metadata.get(
                    "description", "Generated from portfolio source lanes."
                )
            },
        }
    }
    collections = (
        ("businessObjectives", "businessObjectives"),
        ("useCases", "useCases"),
        ("signals", "signals"),
    )
    for source_key, target_key in collections:
        items = _list(plan, source_key)
        if items:
            catalog[target_key] = items
    return {
        "schema": "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml",
        "version": "1.0",
        "kind": "Catalog",
        "catalog": catalog,
    }


def _graph_document(plan: Dict[str, Any]) -> Dict[str, Any]:
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    nodes = []
    nodes.extend(
        _graph_nodes(
            _list(plan, "businessObjectives"),
            "BusinessObjective",
            "business_objective",
        )
    )
    nodes.extend(_graph_nodes(_list(plan, "useCases"), "UseCase", "use_case"))
    nodes.extend(_graph_nodes(_list(plan, "signals"), "Signal", "signal"))
    for product in _list(plan, "products"):
        reference = product.get("productReference")
        if isinstance(reference, dict):
            nodes.append(_graph_node(reference, "DataProduct", "product_reference"))
    return {
        "schema": "https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml",
        "version": "1.0",
        "kind": "Graph",
        "graph": {
            "metadata": {
                "id": f"{metadata.get('id', 'portfolio')}-graph",
                "name": {"en": metadata.get("name", "Generated Portfolio")},
                "description": {
                    "en": metadata.get(
                        "description",
                        "Generated portfolio relationship graph.",
                    )
                },
            },
            "nodes": nodes,
            "edges": [_graph_edge(edge) for edge in _list(plan, "graphEdges")],
        },
    }


def _graph_nodes(
    items: List[Dict[str, Any]],
    node_type: str,
    fragment_prefix: str,
) -> List[Dict[str, Any]]:
    return [_graph_node(item, node_type, fragment_prefix) for item in items]


def _graph_node(
    item: Dict[str, Any],
    node_type: str,
    fragment_prefix: str,
) -> Dict[str, Any]:
    item_id = _text(item.get("id") or item.get("productID"))
    return {
        "id": item_id,
        "type": node_type,
        "$ref": f"../odpc/fragments/{fragment_prefix}_{_path_id(item_id)}.yaml",
    }


def _graph_edge(edge: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "from": _text(edge.get("source") or edge.get("from")),
        "to": _text(edge.get("target") or edge.get("to")),
        "type": _text(edge.get("type"), "relatedTo"),
        "confidence": _text(edge.get("confidence"), "medium"),
    }


def _artifact_counts(plan: Dict[str, Any]) -> Dict[str, int]:
    counts = {
        "businessObjectives": len(_list(plan, "businessObjectives")),
        "useCases": len(_list(plan, "useCases")),
        "signals": len(_list(plan, "signals")),
        "productReferences": len(_list(plan, "products")),
        "odpsProducts": sum(
            1
            for product in _list(plan, "products")
            if isinstance(product.get("odpsProduct"), dict)
        ),
        "graphEdges": len(_list(plan, "graphEdges")),
    }
    counts.update(_executive_summary_counts(plan.get("executiveSummary")))
    return counts


def _workspace_artifact_counts(data: Dict[str, Any]) -> Dict[str, int]:
    catalog = data["catalog"].get("catalog", {})
    graph = data["graph"].get("graph", {})
    counts = {
        "businessObjectives": _count(catalog, "businessObjectives"),
        "useCases": _count(catalog, "useCases"),
        "signals": _count(catalog, "signals"),
        "productReferences": _count(catalog, "productReferences"),
        "odpsProducts": len(data["products"]),
        "graphNodes": _count(graph, "nodes"),
        "graphEdges": _count(graph, "edges"),
    }
    counts.update(_executive_summary_counts(data.get("executive_summary")))
    return counts


def _executive_summary_counts(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {
            "priorityItems": 0,
            "swotItems": 0,
            "leadershipDecisions": 0,
            "evidenceGaps": 0,
        }
    briefing = (
        value.get("priorityBriefing")
        if isinstance(value.get("priorityBriefing"), dict)
        else {}
    )
    priority_count = sum(
        1
        for key in ("primaryFocus", "secondaryFocus", "blocker", "readinessCheck")
        if isinstance(briefing.get(key), dict)
    )
    swot = value.get("swot") if isinstance(value.get("swot"), dict) else {}
    swot_count = sum(
        len(_list(swot, bucket)) for bucket in EXECUTIVE_SUMMARY_SWOT_BUCKETS
    )
    return {
        "priorityItems": priority_count,
        "swotItems": swot_count,
        "leadershipDecisions": len(_list(value, "leadershipDecisions")),
        "evidenceGaps": len(_list(value, "evidenceGaps")),
    }


def _file_id(item: Dict[str, Any]) -> str:
    return _path_id(_text(item.get("id") or item.get("productID"), "item"))
