from pathlib import Path

import yaml

from open_data_products.odpg import (
    agent_context,
    analyze_graph,
    build_graph_explorer_html,
    build_graph,
    collect_relationship_types,
    convert_file,
    convert_graph,
    generate_graph_explorer,
    load_graph,
    search_graph_objects,
    summarize_graph,
    traverse_graph,
    validate_graph,
    write_graph,
)
from open_data_products.odpg.cli import (
    convert_main,
    generate_main,
    search_main,
    validate_main,
)


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
    assert 'id="filter-node-types"' in html
    assert 'id="filter-edge-types"' in html
    assert 'id="filter-confidence"' in html


def test_generate_graph_explorer_creates_output_parent_directory(tmp_path):
    output = tmp_path / "output" / "graph-explorer.html"

    generate_graph_explorer(output_file=output)

    assert output.exists()
    assert "ODPG Graph Explorer" in output.read_text(encoding="utf-8")


def test_build_graph_explorer_html_returns_document():
    html = build_graph_explorer_html(load_graph())

    assert html.startswith("\n<!DOCTYPE html>")
    assert "GRAPH-AVIATION-001" in html
    assert "const NODE_TYPES =" in html
    assert "const CONFIDENCE_LEVELS =" in html
    assert '"id": "edge-0"' in html
    assert 'produces: "#059669"' in html


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


def test_build_graph_converts_odpc_fragments_to_nodes_and_generates_edges(tmp_path):
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    (fragments / "product.yaml").write_text(
        """
productReference:
  id: customer-analytics-product
  name:
    en: Customer Analytics Product
  description:
    en: Trusted customer analytics for retention decisions.
""",
        encoding="utf-8",
    )
    (fragments / "use-case.yaml").write_text(
        """
useCase:
  id: customer-retention
  name:
    en: Customer Retention
  description:
    en: Improve retention decisions with trusted customer analytics.
""",
        encoding="utf-8",
    )
    (fragments / "objective.yaml").write_text(
        """
businessObjective:
  id: reduce-churn
  name:
    en: Reduce Churn
  description:
    en: Reduce preventable customer churn.
""",
        encoding="utf-8",
    )
    (fragments / "signal.yaml").write_text(
        """
signal:
  id: churn-risk-score
  name:
    en: Churn Risk Score
  description:
    en: Risk score used by retention teams.
""",
        encoding="utf-8",
    )
    prompts = []

    def fake_client(prompt, model):
        prompts.append(prompt)
        assert model == "test-model"
        return """
edges:
  - from: customer-retention
    to: customer-analytics-product
    type: dependsOn
    confidence: high
  - from: reduce-churn
    to: churn-risk-score
    type: measures
    confidence: medium
"""

    graph = build_graph(
        fragments,
        graph_id="customer-graph",
        name="Customer Graph",
        client=fake_client,
        model="test-model",
    )

    assert prompts
    assert "customer-analytics-product" in prompts[0]
    assert "Do not create nodes" in prompts[0]
    assert validate_graph(graph).valid
    assert graph["graph"]["metadata"]["id"] == "customer-graph"
    assert graph["graph"]["metadata"]["name"] == {"en": "Customer Graph"}
    assert graph["graph"]["nodes"] == [
        {
            "id": "customer-analytics-product",
            "type": "DataProduct",
            "$ref": "product.yaml",
        },
        {"id": "customer-retention", "type": "UseCase", "$ref": "use-case.yaml"},
        {
            "id": "reduce-churn",
            "type": "BusinessObjective",
            "$ref": "objective.yaml",
        },
        {"id": "churn-risk-score", "type": "Signal", "$ref": "signal.yaml"},
    ]
    assert graph["graph"]["edges"][0]["type"] == "dependsOn"


def test_build_graph_rejects_llm_edges_for_unknown_nodes(tmp_path):
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    (fragments / "product.yaml").write_text(
        """
productReference:
  id: customer-analytics-product
  name:
    en: Customer Analytics Product
""",
        encoding="utf-8",
    )

    def fake_client(prompt, model):
        return """
edges:
  - from: unknown-node
    to: customer-analytics-product
    type: relatedTo
    confidence: low
"""

    try:
        build_graph(fragments, client=fake_client)
    except ValueError as exc:
        assert "unknown node id" in str(exc)
    else:
        raise AssertionError("build_graph accepted an edge with an unknown node id")


def test_write_graph_creates_output_parent_directory(tmp_path):
    output = tmp_path / "deep" / "graph.yaml"
    graph = {
        "schema": "https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml",
        "version": "1.0",
        "kind": "Graph",
        "graph": {
            "metadata": {
                "id": "empty-test",
                "name": {"en": "Empty Test"},
                "description": {"en": "Empty graph for writer coverage."},
            },
            "nodes": [],
            "edges": [],
        },
    }

    write_graph(output, graph)

    assert yaml.safe_load(output.read_text(encoding="utf-8")) == graph


def test_convert_jsonld_to_valid_odpg_graph():
    document = convert_graph(
        {
            "@graph": [
                {
                    "@id": "product/orders",
                    "@type": "DataProduct",
                    "supports": {"@id": "objective/retention"},
                },
                {"@id": "objective/retention", "@type": "BusinessObjective"},
            ]
        },
        "jsonld",
        graph_id="orders-graph",
        name="Orders Graph",
    )

    result = validate_graph(document)

    assert result.valid
    assert document["graph"]["metadata"]["id"] == "orders-graph"
    assert document["graph"]["nodes"][0]["type"] == "DataProduct"
    assert document["graph"]["edges"][0]["type"] == "supports"


def test_convert_graphson_file_writes_yaml(tmp_path):
    source = tmp_path / "graph.graphson"
    output = tmp_path / "deep" / "converted" / "graph.yaml"
    source.write_text(
        """
{
  "vertices": [
    {"id": "product-orders", "label": "DataProduct"},
    {"id": "use-case-retention", "label": "UseCase"}
  ],
  "edges": [
    {
      "outV": "use-case-retention",
      "inV": "product-orders",
      "label": "uses"
    }
  ]
}
""",
        encoding="utf-8",
    )

    document = convert_file(source, output_path=output, name="Converted")
    written = yaml.safe_load(output.read_text(encoding="utf-8"))

    assert document == written
    assert validate_graph(written).valid
    assert written["graph"]["edges"][0]["confidence"] == "medium"


def test_convert_graphml_and_cypher_formats():
    graphml = """\
<graphml>
  <key id="label" for="node" attr.name="type"/>
  <key id="edgeType" for="edge" attr.name="type"/>
  <graph edgedefault="directed">
    <node id="dp"><data key="label">DataProduct</data></node>
    <node id="uc"><data key="label">UseCase</data></node>
    <edge source="uc" target="dp"><data key="edgeType">uses</data></edge>
  </graph>
</graphml>
"""
    cypher = """
CREATE (u:UseCase {id: 'delay-risk'})
CREATE (p:DataProduct {id: 'flight-ops'})
CREATE (u)-[:uses]->(p)
"""

    graphml_doc = convert_graph(graphml, "graphml")
    cypher_doc = convert_graph(cypher, "cypher")

    assert validate_graph(graphml_doc).valid
    assert validate_graph(cypher_doc).valid
    assert graphml_doc["graph"]["edges"][0]["type"] == "uses"
    assert cypher_doc["graph"]["nodes"][0]["id"] == "delay-risk"


def test_convert_cli_entry_point(tmp_path):
    source = tmp_path / "graph.ttl"
    output = tmp_path / "deep" / "converted" / "graph.yaml"
    source.write_text(
        """
<product/orders> a <DataProduct> .
<objective/retention> a <BusinessObjective> .
<product/orders> <supports> <objective/retention> .
""",
        encoding="utf-8",
    )

    assert (
        convert_main(["--input", str(source), "--output", str(output), "--json"]) == 0
    )
    assert output.exists()
    assert validate_graph(yaml.safe_load(output.read_text(encoding="utf-8"))).valid
