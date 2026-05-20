from pathlib import Path

from open_data_products.odpg import (
    agent_context,
    analyze_graph,
    build_graph_explorer_html,
    collect_relationship_types,
    generate_graph_explorer,
    load_graph,
    search_graph_objects,
    summarize_graph,
    traverse_graph,
    validate_graph,
)
from open_data_products.odpg.cli import generate_main, search_main, validate_main


def test_bundled_graph_loads_and_validates():
    graph = load_graph()

    result = validate_graph(graph)

    assert result.valid
    assert result.errors == []
    assert result.warnings == []
    assert graph["kind"] == "Graph"
    assert graph["graph"]["metadata"]["id"] == "GRAPH-AVIATION-001"
    assert len(graph["graph"]["nodes"]) == 9
    assert len(graph["graph"]["edges"]) == 13


def test_relationship_types_keep_odpg_order():
    graph = load_graph()

    relationship_types = collect_relationship_types(graph)

    assert relationship_types[:4] == ["uses", "supports", "contributesTo", "measures"]
    assert "governedBy" in relationship_types


def test_search_graph_objects_by_id_and_keywords():
    exact = search_graph_objects(object_id="DataProduct")
    keyword = search_graph_objects("strategic graph opportunity")

    assert exact[0]["id"] == "DataProduct"
    assert keyword[0]["id"] == "StrategicOpportunity"


def test_search_graph_objects_honors_limit():
    matches = search_graph_objects("data", limit=1)

    assert len(matches) == 1


def test_generate_graph_explorer_writes_html(tmp_path):
    output = tmp_path / "graph-explorer.html"

    generate_graph_explorer(output_file=output)

    html = output.read_text(encoding="utf-8")
    assert "ODPG Graph Explorer" in html
    assert "Aviation Data Product Value Graph" in html
    assert "vis-network" in html


def test_build_graph_explorer_html_returns_document():
    html = build_graph_explorer_html(load_graph())

    assert html.startswith("\n<!DOCTYPE html>")
    assert "GRAPH-AVIATION-001" in html


def test_cli_entry_points(tmp_path):
    output = tmp_path / "graph-explorer.html"
    graph = Path("open_data_products/odpg/data/graph/graph.yaml")

    assert validate_main([str(graph)]) == 0
    assert search_main(["--id", "DataProduct", "--json"]) == 0
    assert generate_main(["--output", str(output)]) == 0
    assert output.exists()


def test_upstream_toolkit_summary_traverse_analyze_and_agent_context():
    graph = load_graph()

    summary = summarize_graph(graph)
    paths = traverse_graph(graph, "AGENT-AVIATION-001", 2)
    reverse_paths = traverse_graph(graph, "OBJ-AVIATION-001", 1, reverse=True)
    analysis = analyze_graph(graph)
    context = agent_context(graph, "AGENT-AVIATION-001", 2)

    assert summary["id"] == "GRAPH-AVIATION-001"
    assert summary["nodeCount"] == 9
    assert summary["edgeTypes"]["uses"] == 4
    assert paths[0]["start"] == "AGENT-AVIATION-001"
    assert any(path["end"] == "API-AVIATION-001" for path in paths)
    assert any(path["end"] == "DP-AVIATION-001" for path in reverse_paths)
    assert analysis["unsupportedBusinessObjectives"] == []
    assert "DP-AVIATION-002" in analysis["ungovernedAssets"]
    assert context["focusNode"]["id"] == "AGENT-AVIATION-001"
    assert any(node["id"] == "POL-AVIATION-001" for node in context["relatedNodes"])
    assert context["governanceSignals"]


def test_graph_analysis_helpers_ignore_malformed_items():
    from open_data_products.odpg.graph import _graph_edges, _graph_nodes, _node_by_id

    graph = load_graph()
    graph["graph"]["nodes"].append("not-a-node")
    graph["graph"]["edges"].append("not-an-edge")

    summary = summarize_graph(graph)
    analysis = analyze_graph(graph)
    context = agent_context(graph, "AGENT-AVIATION-001", 1)

    assert summary["nodeCount"] == 9
    assert summary["edgeCount"] == 13
    assert len(_graph_nodes(graph)) == 9
    assert len(_graph_edges(graph)) == 13
    assert _node_by_id(graph)["AGENT-AVIATION-001"]["type"] == "Agent"
    assert "DP-AVIATION-002" in analysis["ungovernedAssets"]
    assert context["focusNode"]["id"] == "AGENT-AVIATION-001"


def test_validation_reports_upstream_warnings_and_confidence_errors():
    graph = load_graph()
    graph["graph"]["nodes"].append(
        {
            "id": "CUSTOM-001",
            "type": "CustomNode",
            "$ref": "../custom/custom-node.yaml",
        }
    )
    graph["graph"]["edges"].append(
        {
            "from": "CUSTOM-001",
            "to": "DP-AVIATION-001",
            "type": "customRelation",
            "confidence": "certain",
        }
    )

    result = validate_graph(graph)

    assert not result.valid
    assert any("non-core node type" in warning for warning in result.warnings)
    assert any("non-core edge type" in warning for warning in result.warnings)
    assert any("invalid confidence" in error for error in result.errors)


def test_invalid_graph_reports_missing_reference():
    graph = load_graph()
    graph["graph"]["edges"] = [
        {
            "from": "missing",
            "to": "DP-AVIATION-001",
            "type": "uses",
            "confidence": "high",
        }
    ]

    result = validate_graph(graph)

    assert not result.valid
    assert any("source does not match any node id" in error for error in result.errors)
