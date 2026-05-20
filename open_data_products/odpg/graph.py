"""ODPG graph loading, validation, search, and explorer generation helpers."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, DefaultDict, Dict, FrozenSet, List, Optional, Set, Tuple, Union, cast

from open_data_products._io import load_jsonl_records, load_mapping
from open_data_products._search import search_records
from open_data_products.results import ValidationResult

from . import _explorer_template

DEFAULT_GRAPH_YAML = Path(__file__).resolve().parent / "data" / "graph" / "graph.yaml"
DEFAULT_SCHEMA_YAML = Path(__file__).resolve().parent / "data" / "schema" / "odpg.yaml"
DEFAULT_OBJECTS_JSONL = (
    Path(__file__).resolve().parent / "data" / "graph" / "objects.jsonl"
)


# --- ODPG relationship model (ODPG spec literals; graphs may add domain-specific types) ---
# Edge `type` values are shown exactly as in YAML (e.g. contributesTo, governedBy, uses).
ODPG_CORE_EDGE_TYPES_ORDERED: Tuple[str, ...] = (
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
)

ODPG_EDGE_DESCRIPTIONS: Dict[str, str] = {
    "uses": "A node uses another node as part of execution or operation",
    "supports": "A node supports a business objective",
    "contributesTo": "A node contributes toward an outcome or objective",
    "measures": "A KPI measures an objective or outcome",
    "tracks": "A node tracks or provides KPI-related information",
    "dependsOn": "A node depends on another node",
    "produces": "A node produces data, outputs, or services",
    "consumes": "A node consumes data, APIs, or outputs",
    "governedBy": "A node is governed by a policy or control",
    "ownedBy": "A node is owned by a person, team, or domain",
    "alignsWith": "A node aligns strategically or semantically with another node",
    "alignWith": "A node aligns strategically or semantically with another node",
    "relatedTo": "A generic semantic relationship",
    "impacts": "A node impacts another node",
    "derivedFrom": "A node originates from another node",
    "exposes": "A node exposes an API or interface",
    "monitors": "A node monitors another node",
    "identifies": "A node identifies an opportunity or condition",
}

ODPG_EDGE_DESCRIPTIONS_LOWER: Dict[str, str] = {
    k.lower(): v for k, v in ODPG_EDGE_DESCRIPTIONS.items()
}

ODPG_CORE_EDGE_TYPES_LOWER: FrozenSet[str] = frozenset(
    s.lower() for s in ODPG_CORE_EDGE_TYPES_ORDERED
)

_ODPG_LEGEND_COLOR_BY_LOWER: Dict[str, str] = {
    "uses": "#16a34a",
    "supports": "#ea580c",
    "contributesto": "#0284c7",
    "measures": "#0d9488",
    "tracks": "#14b8a6",
    "dependson": "#6366f1",
    "produces": "#059669",
    "consumes": "#a855f7",
    "governedby": "#db2777",
    "ownedby": "#ca8a04",
    "alignswith": "#f97316",
    "alignwith": "#f97316",
    "relatedto": "#64748b",
    "impacts": "#dc2626",
    "derivedfrom": "#78716c",
    "exposes": "#7c3aed",
    "monitors": "#0891b2",
    "identifies": "#475569",
}

DEFAULT_CONFIDENCE_VALUES: FrozenSet[str] = frozenset(("high", "medium", "low"))
CORE_NODE_TYPES: FrozenSet[str] = frozenset(
    (
        "DataProduct",
        "UseCase",
        "BusinessObjective",
        "KPI",
        "Domain",
        "Dataset",
        "API",
        "Policy",
        "Workflow",
        "Agent",
        "Capability",
        "StrategicOpportunity",
    )
)


def load_graph(path: Optional[Union[Path, str]] = None) -> Dict[str, Any]:
    """Load an ODPG graph from YAML."""
    graph_path = Path(path) if path is not None else DEFAULT_GRAPH_YAML
    if not graph_path.is_file():
        raise FileNotFoundError(f"Graph YAML not found: {graph_path}")
    return load_mapping(graph_path, root_name="ODPG graph")


load_graph_from_yaml = load_graph


def load_schema(path: Optional[Union[Path, str]] = None) -> Dict[str, Any]:
    """Load ODPG schema YAML from ``path`` or bundled package data."""
    schema_path = Path(path) if path is not None else DEFAULT_SCHEMA_YAML
    return load_mapping(schema_path, root_name="ODPG schema")


def graph_payload(document: Dict[str, Any]) -> Dict[str, Any]:
    """Return the ODPG graph container, accepting legacy flat examples."""
    payload = document.get("graph")
    return payload if isinstance(payload, dict) else document


def graph_metadata(document: Dict[str, Any]) -> Dict[str, Any]:
    """Return ODPG graph metadata."""
    payload = graph_payload(document)
    metadata = payload.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def localized_text(value: Any) -> str:
    """Return a display string for ODPG localized values."""
    if isinstance(value, dict):
        return str(value.get("en") or next(iter(value.values()), ""))
    return "" if value is None else str(value)


def validate_graph(graph: Dict[str, Any]) -> ValidationResult:
    """Validate an ODPG graph document using upstream toolkit semantics."""
    errors: List[str] = []
    warnings: List[str] = []

    for field in ("schema", "version", "kind"):
        if field not in graph:
            errors.append(f"Missing required root field: {field}")

    if graph.get("kind") != "Graph":
        errors.append("Invalid root field kind: expected Graph")

    payload = graph_payload(graph)
    metadata = graph_metadata(graph)
    nodes = payload.get("nodes")
    edges = payload.get("edges")

    if "graph" in graph and not isinstance(graph.get("graph"), dict):
        errors.append("Root field graph must be an object")

    if not isinstance(nodes, list):
        errors.append("Missing or invalid graph.nodes array")
        nodes = []
    if not isinstance(edges, list):
        errors.append("Missing or invalid graph.edges array")
        edges = []

    for field in ("id", "name", "description"):
        if field not in metadata:
            errors.append(f"Missing required metadata field: graph.metadata.{field}")

    node_ids: Set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"Node at index {index} must be an object")
            continue
        node_id = node.get("id")
        node_type = node.get("type")
        if not node_id:
            errors.append(f"Node at index {index} is missing required field: id")
        elif str(node_id) in node_ids:
            errors.append(f"Duplicate node id found: {node_id}")
        else:
            node_ids.add(str(node_id))
        if not node_type:
            errors.append(f"Node {node_id or index} is missing required field: type")
        elif str(node_type) not in CORE_NODE_TYPES:
            warnings.append(
                f"Node {node_id or index} uses non-core node type: {node_type}"
            )
        if not _node_ref(node):
            errors.append(f"Node {node_id or index} is missing required field: $ref")

    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"Edge at index {index} must be an object")
            continue
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        edge_type = str(edge.get("type") or "")
        confidence = str(edge.get("confidence") or "")
        if not source:
            errors.append(f"Edge at index {index} is missing required field: from")
        elif source not in node_ids:
            errors.append(f"Edge source does not match any node id: {source}")
        if not target:
            errors.append(f"Edge at index {index} is missing required field: to")
        elif target not in node_ids:
            errors.append(f"Edge target does not match any node id: {target}")
        if not edge_type:
            errors.append(f"Edge {source}->{target} is missing required field: type")
        elif edge_type not in ODPG_CORE_EDGE_TYPES_ORDERED:
            warnings.append(
                f"Edge {source}->{target} uses non-core edge type: {edge_type}"
            )
        if not confidence:
            errors.append(
                f"Edge {source}->{target} is missing required field: confidence"
            )
        elif confidence not in DEFAULT_CONFIDENCE_VALUES:
            errors.append(
                f"Edge {source}->{target} has invalid confidence: {confidence}. "
                "Use high, medium, or low."
            )

    kind = str(graph.get("kind", "Graph"))
    return ValidationResult(
        valid=not errors,
        spec="odpg",
        kind=kind,
        errors=errors,
        warnings=warnings,
    )


def _ref_to_display_name(ref: str) -> str:
    base = Path(ref).name
    if base.endswith((".yaml", ".yml")):
        base = base.rsplit(".", 1)[0]
    base = base.replace("-", " ").replace("_", " ")
    return " ".join(w.capitalize() for w in base.split()) if base else ""


def _node_ref(node: Dict[str, Any]) -> str:
    return str(node.get("$ref") or node.get("ref") or "")


def _edge_type_raw(edge: dict) -> str:
    return str(edge.get("type", "")).strip()


def collect_relationship_types(graph: dict) -> List[str]:
    """Types present in the graph: ODPG spec order (camelCase literals), then other types A–Z."""
    seen_lower_to_raw: Dict[str, str] = {}
    for edge in graph_payload(graph).get("edges") or []:
        raw = _edge_type_raw(edge)
        if not raw:
            continue
        lo = raw.lower()
        if lo not in seen_lower_to_raw:
            seen_lower_to_raw[lo] = raw
    ordered_core: List[str] = []
    for spec in ODPG_CORE_EDGE_TYPES_ORDERED:
        lo = spec.lower()
        if lo in seen_lower_to_raw:
            ordered_core.append(seen_lower_to_raw[lo])
    extras = sorted(
        (
            seen_lower_to_raw[lo]
            for lo in seen_lower_to_raw
            if lo not in ODPG_CORE_EDGE_TYPES_LOWER
        ),
        key=str.lower,
    )
    return ordered_core + extras


def _edge_relationship_label(edge: dict) -> str:
    """Edge label exactly as authored in YAML `type` (ODPG stabilization spec)."""
    return _edge_type_raw(edge)


def _edge_vis_tooltip(edge: dict, display: str) -> str:
    lines = [f"Type: {display}", f"Confidence: {edge['confidence']}"]
    desc = ODPG_EDGE_DESCRIPTIONS_LOWER.get(display.lower(), "")
    if desc:
        lines.append(desc)
    return "\n".join(lines)


def _edge_legend_color(type_display: str) -> str:
    return _ODPG_LEGEND_COLOR_BY_LOWER.get(type_display.lower(), "#94a3b8")


def _edge_line_dashed(type_display: str, edge: dict) -> bool:
    if edge.get("dashed") is True:
        return True
    return type_display.lower() == "governedby"


def _build_legend_relationship_html(relationship_types: List[str], graph: dict) -> str:
    edges = graph_payload(graph).get("edges") or []

    def sample_edge(label_raw: str) -> Dict[str, Any]:
        lo = label_raw.lower()
        for e in edges:
            if _edge_type_raw(e).lower() == lo:
                return cast(Dict[str, Any], e)
        return {}

    blocks: List[str] = []
    for label_raw in relationship_types:
        edge_sample = sample_edge(label_raw)
        color = _edge_legend_color(label_raw)
        dash = (
            ' stroke-dasharray="4 3"'
            if _edge_line_dashed(label_raw, edge_sample)
            else ""
        )
        safe_label = html.escape(label_raw)
        blocks.append(
            f'              <div class="legend-edge-item">\n'
            f'                <svg viewBox="0 0 44 14" width="44" height="14" aria-hidden="true">'
            f'<line x1="2" y1="7" x2="34" y2="7" stroke="{color}" stroke-width="2"{dash}/>'
            f'<polygon points="40,7 32,3 32,11" fill="{color}"/></svg>\n'
            f"                <span>{safe_label}</span>\n"
            f"              </div>"
        )
    if not blocks:
        blocks.append(
            '              <p class="panel-placeholder" style="margin:0;font-size:12px">No edges in graph.</p>'
        )
    return "\n".join(blocks)


def build_html(graph: dict) -> str:
    payload = graph_payload(graph)
    metadata = graph_metadata(graph)
    relationship_types = collect_relationship_types(graph)
    odpg_supported_ordered_json = json.dumps(
        list(ODPG_CORE_EDGE_TYPES_ORDERED), ensure_ascii=False
    )
    odpg_descriptions_json = json.dumps(
        ODPG_EDGE_DESCRIPTIONS_LOWER, ensure_ascii=False
    )
    graph_title = localized_text(metadata.get("name")) or "ODPG Graph Explorer"
    graph_meta = (
        f"{metadata.get('id')} · ODPG {graph.get('version')} · {graph.get('kind')}"
    )

    vis_nodes = []
    for node in payload["nodes"]:
        ref = _node_ref(node)
        display_name = _ref_to_display_name(ref)
        vis_nodes.append(
            {
                "id": node["id"],
                "label": node["id"],
                "title": (
                    f"ID: {node['id']}\n" f"Type: {node['type']}\n" f"Ref: {ref}"
                ),
                "group": node["type"],
                "ref": ref,
                "type": node["type"],
                "displayName": display_name,
            }
        )

    vis_edges = []
    for edge in payload["edges"]:
        display = _edge_relationship_label(edge)
        conf = str(edge["confidence"]).lower()
        ec = _edge_legend_color(display)
        vis_edges.append(
            {
                "from": edge["from"],
                "to": edge["to"],
                "label": f"{display}\n({conf})",
                "title": _edge_vis_tooltip(edge, display),
                "arrows": "to",
                "confidence": edge["confidence"],
                "dashes": _edge_line_dashed(display, edge),
                "color": {
                    "color": ec,
                    "highlight": ec,
                    "hover": ec,
                    "inherit": False,
                },
            }
        )

    legend_edges_html = _build_legend_relationship_html(relationship_types, graph)

    return _explorer_template.render_explorer(
        graph_title=graph_title,
        graph_meta=graph_meta,
        relationship_types=relationship_types,
        vis_nodes=vis_nodes,
        vis_edges=vis_edges,
        legend_edges_html=legend_edges_html,
        odpg_supported_ordered_json=odpg_supported_ordered_json,
        odpg_descriptions_json=odpg_descriptions_json,
    )


def build_adjacency(
    document: Dict[str, Any],
    reverse: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:
    """Build edge adjacency lists for ODPG traversal."""
    adjacency: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for edge in graph_payload(document).get("edges") or []:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        key = target if reverse else source
        adjacency[key].append(edge)
    return dict(adjacency)


def summarize_graph(document: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize ODPG graph metadata, node/edge counts, types, and confidence."""
    payload = graph_payload(document)
    metadata = graph_metadata(document)
    nodes = [n for n in payload.get("nodes") or [] if isinstance(n, dict)]
    edges = [e for e in payload.get("edges") or [] if isinstance(e, dict)]

    node_types: DefaultDict[str, int] = defaultdict(int)
    edge_types: DefaultDict[str, int] = defaultdict(int)
    confidence_values: DefaultDict[str, int] = defaultdict(int)

    for node in nodes:
        node_types[str(node.get("type") or "unknown")] += 1
    for edge in edges:
        edge_types[str(edge.get("type") or "unknown")] += 1
        confidence_values[str(edge.get("confidence") or "unknown")] += 1

    return {
        "id": metadata.get("id"),
        "name": localized_text(metadata.get("name")),
        "description": localized_text(metadata.get("description")),
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "nodeTypes": dict(sorted(node_types.items())),
        "edgeTypes": dict(sorted(edge_types.items())),
        "confidenceValues": dict(sorted(confidence_values.items())),
    }


def traverse_graph(
    document: Dict[str, Any],
    start: str,
    depth: int,
    relationship: Optional[str] = None,
    reverse: bool = False,
) -> List[Dict[str, Any]]:
    """Discover ODPG relationship paths from a node."""
    adjacency = build_adjacency(document, reverse=reverse)
    paths: List[Dict[str, Any]] = []
    queue: Deque[Tuple[str, List[Dict[str, Any]]]] = deque([(start, [])])
    seen = {(start, 0)}

    while queue:
        node_id, path = queue.popleft()
        if len(path) >= depth:
            continue
        for edge in adjacency.get(node_id, []):
            if relationship and edge.get("type") != relationship:
                continue
            next_node = str(edge.get("from") if reverse else edge.get("to"))
            next_path = path + [edge]
            paths.append(
                {
                    "start": start,
                    "end": next_node,
                    "depth": len(next_path),
                    "relationships": [
                        {
                            "from": item.get("from"),
                            "to": item.get("to"),
                            "type": item.get("type"),
                            "confidence": item.get("confidence"),
                        }
                        for item in next_path
                    ],
                }
            )
            state = (next_node, len(next_path))
            if state not in seen:
                seen.add(state)
                queue.append((next_node, next_path))

    return paths


def analyze_graph(document: Dict[str, Any]) -> Dict[str, Any]:
    """Run ODPG strategic and governance analysis checks."""
    payload = graph_payload(document)
    nodes = [n for n in payload.get("nodes") or [] if isinstance(n, dict)]
    edges = [e for e in payload.get("edges") or [] if isinstance(e, dict)]
    node_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}

    incoming: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    outgoing: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        outgoing[str(edge.get("from") or "")].append(edge)
        incoming[str(edge.get("to") or "")].append(edge)

    orphan_kpis = [
        node_id
        for node_id, node in node_by_id.items()
        if node.get("type") == "KPI"
        and not any(
            edge.get("type") == "measures" for edge in outgoing.get(node_id, [])
        )
    ]
    unsupported_objectives = [
        node_id
        for node_id, node in node_by_id.items()
        if node.get("type") == "BusinessObjective"
        and not any(
            edge.get("type") in {"supports", "contributesTo", "alignsWith", "alignWith"}
            for edge in incoming.get(node_id, [])
        )
    ]
    ungoverned_assets = [
        node_id
        for node_id, node in node_by_id.items()
        if node.get("type") in {"DataProduct", "API", "Dataset", "Workflow", "Agent"}
        and not any(
            edge.get("type") == "governedBy" for edge in outgoing.get(node_id, [])
        )
    ]
    weak_relationships = [
        {
            "from": edge.get("from"),
            "to": edge.get("to"),
            "type": edge.get("type"),
            "confidence": edge.get("confidence"),
        }
        for edge in edges
        if edge.get("confidence") == "low"
    ]
    potential_opportunities = [
        node_id
        for node_id, node in node_by_id.items()
        if node.get("type") == "UseCase"
        and any(edge.get("type") == "uses" for edge in outgoing.get(node_id, []))
        and not any(
            edge.get("type") in {"supports", "contributesTo"}
            for edge in outgoing.get(node_id, [])
        )
    ]

    return {
        "orphanKpis": orphan_kpis,
        "unsupportedBusinessObjectives": unsupported_objectives,
        "ungovernedAssets": ungoverned_assets,
        "lowConfidenceRelationships": weak_relationships,
        "useCasesWithoutStrategicContribution": potential_opportunities,
    }


def agent_context(document: Dict[str, Any], node_id: str, depth: int) -> Dict[str, Any]:
    """Extract trusted ODPG graph context around a focus node."""
    payload = graph_payload(document)
    nodes = [n for n in payload.get("nodes") or [] if isinstance(n, dict)]
    node_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    forward_paths = traverse_graph(document, node_id, depth)
    reverse_paths = traverse_graph(document, node_id, depth, reverse=True)
    related_ids = {node_id}
    for path in forward_paths + reverse_paths:
        related_ids.add(str(path.get("end")))

    return {
        "focusNode": node_by_id.get(node_id, {"id": node_id}),
        "relatedNodes": [
            node_by_id[node] for node in sorted(related_ids) if node in node_by_id
        ],
        "forwardPaths": forward_paths,
        "reversePaths": reverse_paths,
        "governanceSignals": [
            path
            for path in forward_paths
            if any(
                item.get("type") == "governedBy"
                for item in path.get("relationships", [])
            )
        ],
    }


def load_graph_object_records(
    path: Optional[Union[Path, str]] = None,
) -> List[Dict[str, Any]]:
    """Load ODPG graph object records from JSONL."""
    records_path = Path(path) if path is not None else DEFAULT_OBJECTS_JSONL
    return load_jsonl_records(records_path)


def searchable_text(record: Dict[str, Any]) -> str:
    """Flatten an ODPG graph object record into searchable lowercase text."""
    values: List[str] = []
    for value in record.values():
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif isinstance(value, dict):
            values.extend(str(item) for item in value.values())
        else:
            values.append(str(value))
    return " ".join(values).lower()


def search_graph_objects(
    query: Optional[str] = None,
    *,
    object_id: Optional[str] = None,
    records: Optional[List[Dict[str, Any]]] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Search bundled ODPG graph object records by keyword or exact object id."""
    source_records = records if records is not None else load_graph_object_records()
    return search_records(
        source_records,
        query,
        object_id=object_id,
        limit=limit,
        searchable_text=searchable_text,
    )


def render_graph_object_records(records: List[Dict[str, Any]]) -> str:
    """Render ODPG graph object records as compact text."""
    if not records:
        return "No matching ODPG graph objects found.\n"

    sections = []
    for record in records:
        description = record.get("description") or record.get("purpose", "")
        sections.append(
            "\n".join(
                [
                    f"{record.get('id', '(missing id)')}",
                    f"  Type: {record.get('objectType', '(missing type)')}",
                    f"  Description: {description}",
                ]
            )
        )
    return "\n\n".join(sections) + "\n"


def build_graph_explorer_html(graph: Dict[str, Any]) -> str:
    """Build the standalone ODPG graph explorer HTML document."""
    return build_html(graph)


def generate_graph_explorer(
    graph_yaml: Optional[Union[Path, str]] = None,
    output_file: Union[Path, str] = "graph-explorer.html",
) -> Path:
    """Generate a standalone ODPG graph explorer HTML file."""
    graph = load_graph(graph_yaml)
    result = validate_graph(graph)
    if not result.valid:
        raise ValueError("; ".join(result.errors))

    html_out = build_graph_explorer_html(graph)
    output_path = Path(output_file)
    output_path.write_text(html_out, encoding="utf-8")

    return output_path


def explain_graph(
    graph: Dict[str, Any],
    *,
    path: Union[str, Path] = "(memory)",
) -> str:
    """Render an ODPG graph summary for humans and AI agents."""
    payload = graph_payload(graph)
    metadata = graph_metadata(graph)
    relationship_types = collect_relationship_types(graph)
    node_types = sorted(
        {
            str(node.get("type"))
            for node in payload.get("nodes", [])
            if isinstance(node, dict) and node.get("type")
        }
    )
    graph_name = localized_text(metadata.get("name")) or "(unnamed)"
    lines = [
        f"File: {path}",
        f"Schema: {graph.get('schema', '(missing)')}",
        f"ODPG version: {graph.get('version', '(missing)')}",
        f"Graph id: {metadata.get('id', '(missing)')}",
        f"Graph name: {graph_name}",
        f"Kind: {graph.get('kind', '(missing)')}",
        f"Nodes: {len(payload.get('nodes', []))}",
        f"Edges: {len(payload.get('edges', []))}",
    ]
    if node_types:
        lines.append(f"Node types: {', '.join(node_types)}")
    if relationship_types:
        lines.append(f"Relationship types: {', '.join(relationship_types)}")
    refs = [
        _node_ref(node)
        for node in payload.get("nodes", [])
        if isinstance(node, dict) and _node_ref(node)
    ]
    if refs:
        lines.append(f"Node references: {len(refs)}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate graph-explorer.html from an ODPG graph YAML file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="graph_yaml",
        type=Path,
        default=DEFAULT_GRAPH_YAML,
        metavar="PATH",
        help="Path to graph YAML file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("graph-explorer.html"),
        metavar="PATH",
        help="Output HTML file path",
    )
    args = parser.parse_args()
    generate_graph_explorer(args.graph_yaml, args.output)
