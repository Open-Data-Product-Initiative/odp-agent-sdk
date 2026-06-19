"""Functional tests for the stdio MCP JSON-RPC handler surface."""

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from open_data_products.mcp.server import handle

pytestmark = pytest.mark.functional

REPO_ROOT = Path(__file__).resolve().parents[1]
ODPS_PRODUCT = (
    REPO_ROOT / "examples" / "apps" / "pricing_402_builder" / "priced_product.yaml"
)
ODPG_GRAPH = REPO_ROOT / "open_data_products" / "odpg" / "data" / "graph" / "graph.yaml"
RECIPE_CONFIG = REPO_ROOT / "examples" / "recipes" / "config" / "recipes.config.yaml"


def _call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    response = handle(
        {
            "jsonrpc": "2.0",
            "id": name,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert response is not None
    assert "error" not in response
    result = response["result"]
    assert result.get("isError") is not True
    assert result["content"][0]["type"] == "text"
    assert result["content"][0]["text"]
    return result


def test_mcp_initialize_and_list_tools() -> None:
    initialize = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert initialize is not None
    assert initialize["result"]["serverInfo"]["name"] == "open-data-products"

    listed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert listed is not None
    tool_names = {tool["name"] for tool in listed["result"]["tools"]}
    assert tool_names >= {
        "validate_document",
        "explain_document",
        "resolve_references",
        "list_resources",
        "get_resource",
        "get_config",
        "validate_config",
        "load_summary",
        "catalog_artifacts",
        "search_terms",
        "resolve_vocabulary_term",
        "explain_vocabulary_term",
        "check_vocabulary_relationship",
        "vocabulary_term_context",
        "search_objects",
        "search_graph_objects",
        "summarize_graph",
        "traverse_graph",
        "analyze_graph",
        "agent_context",
        "resolve_product_contracts",
        "validate_product_contracts",
        "check_product_contract_alignment",
        "generate_product_contract_report",
        "summarize_product_contract_risks",
        "validate_data_contract",
        "summarize_data_contract",
        "extract_data_contract_schema",
        "list_recipes",
        "validate_recipe",
        "plan_recipe_run",
        "search_recipe_guidance",
    }


def test_mcp_manifest_is_json_serializable_and_preserves_tool_contracts() -> None:
    from open_data_products.mcp.manifest import generate_agent_manifest
    from open_data_products.mcp.tools import TOOLS

    manifest = generate_agent_manifest()
    json.dumps(manifest)

    manifest_tools = manifest["tools"]
    assert [tool["name"] for tool in manifest_tools] == [tool["name"] for tool in TOOLS]
    assert all(tool["class"] == "safe" for tool in manifest_tools)
    assert all("handler" not in tool for tool in manifest_tools)
    assert all(tool["inputSchema"]["type"] == "object" for tool in manifest_tools)
    assert {tool["name"] for tool in manifest_tools} >= {
        "validate_document",
        "generate_product_contract_report",
        "extract_data_contract_schema",
        "plan_recipe_run",
    }


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("validate_document", {"path": str(ODPS_PRODUCT)}),
        ("explain_document", {"path": str(ODPS_PRODUCT)}),
        ("resolve_references", {"path": str(ODPG_GRAPH), "limit": 2}),
        ("list_resources", {}),
        ("get_resource", {"id": "odpv.terms"}),
        ("get_config", {"domain": "generation"}),
        ("get_config", {"domain": "recipes", "path": str(RECIPE_CONFIG)}),
        ("validate_config", {"domain": "generation"}),
        ("validate_config", {"domain": "recipes", "path": str(RECIPE_CONFIG)}),
        ("list_recipes", {"config_path": str(RECIPE_CONFIG)}),
        ("validate_recipe", {"config_path": str(RECIPE_CONFIG)}),
        ("plan_recipe_run", {"config_path": str(RECIPE_CONFIG)}),
        ("search_recipe_guidance", {"query": "localization", "limit": 1}),
        ("load_summary", {"path": str(ODPS_PRODUCT)}),
        ("catalog_artifacts", {}),
        ("search_terms", {"query": "data product", "limit": 1}),
        ("resolve_vocabulary_term", {"query": "reusable data asset"}),
        ("explain_vocabulary_term", {"term": "DataProduct"}),
        (
            "check_vocabulary_relationship",
            {"source": "DataProduct", "verb": "supports", "target": "UseCase"},
        ),
        ("vocabulary_term_context", {"term": "DataProduct"}),
        ("search_objects", {"query": "business objective", "limit": 1}),
        ("search_graph_objects", {"query": "data product", "limit": 1}),
        ("summarize_graph", {"path": str(ODPG_GRAPH)}),
        (
            "traverse_graph",
            {"path": str(ODPG_GRAPH), "start": "AGENT-AVIATION-001", "depth": 1},
        ),
        ("analyze_graph", {"path": str(ODPG_GRAPH)}),
        (
            "agent_context",
            {"path": str(ODPG_GRAPH), "node": "AGENT-AVIATION-001", "depth": 1},
        ),
    ],
)
def test_mcp_tool_calls_work_functionally(
    tool_name: str, arguments: Dict[str, Any]
) -> None:
    _call_tool(tool_name, arguments)


def test_mcp_load_summary_exposes_context_sidecar_references(tmp_path: Path) -> None:
    graph = tmp_path / "graph.yaml"
    graph.write_text("schema: odpg\nkind: Graph\n", encoding="utf-8")
    graph.with_suffix(".gcf").write_text("@0 Graph|x", encoding="utf-8")

    result = _call_tool("load_summary", {"path": str(graph)})
    payload = json.loads(result["content"][0]["text"])

    assert payload["context_artifacts"][0]["format"] == "gcf"
    assert payload["context_artifacts"][0]["path"] == str(graph.with_suffix(".gcf"))
    assert "content" not in result["content"][0]["text"]


def test_mcp_recipe_plan_uses_default_recipe_from_config() -> None:
    result = _call_tool("plan_recipe_run", {"config_path": str(RECIPE_CONFIG)})
    payload = json.loads(result["content"][0]["text"])

    assert payload["mode"] == "dry-run"
    assert payload["canRun"] is True
    assert payload["recipe"]["id"] == "RCP-CI-VALIDATE-001"
    assert payload["recipeSelection"] == {
        "source": "config-default",
        "path": "workflows/ci-validate-catalog.yaml",
        "defaultRecipe": "workflows/ci-validate-catalog.yaml",
    }


def test_mcp_unknown_tool_returns_json_rpc_error() -> None:
    response = handle(
        {
            "jsonrpc": "2.0",
            "id": "missing",
            "method": "tools/call",
            "params": {"name": "missing_tool", "arguments": {}},
        }
    )

    assert response is not None
    assert response["error"]["code"] == -32601


def test_mcp_contract_tools_work_functionally(tmp_path: Path) -> None:
    product = tmp_path / "product.yaml"
    contract = tmp_path / "orders.contract.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: '4.0'
product:
  name: Orders
  productID: orders
  visibility: public
  status: production
  type: dataset
  datasets:
    orders:
      fields:
        order_id:
          type: string
  contract:
    type: DCS
    spec:
      name: Orders
      models:
        orders:
          fields:
            order_id:
              type: string
              required: true
""",
        encoding="utf-8",
    )
    contract.write_text(
        """
name: Orders
models:
  orders:
    fields:
      order_id:
        type: string
        required: true
""",
        encoding="utf-8",
    )

    for tool_name, arguments in [
        ("resolve_product_contracts", {"path": str(product)}),
        ("validate_product_contracts", {"path": str(product)}),
        (
            "check_product_contract_alignment",
            {"path": str(product), "contract": str(contract)},
        ),
        ("generate_product_contract_report", {"path": str(product)}),
        ("summarize_product_contract_risks", {"path": str(product)}),
        ("validate_data_contract", {"contract": str(contract)}),
        ("summarize_data_contract", {"contract": str(contract)}),
        ("extract_data_contract_schema", {"contract": str(contract)}),
    ]:
        _call_tool(tool_name, arguments)
