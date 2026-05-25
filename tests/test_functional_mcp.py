"""Functional tests for the stdio MCP JSON-RPC handler surface."""

from pathlib import Path
from typing import Any, Dict

import pytest

from open_data_products.mcp.server import handle

pytestmark = pytest.mark.functional

REPO_ROOT = Path(__file__).resolve().parents[1]
ODPS_PRODUCT = REPO_ROOT / "examples" / "apps" / "pricing_402_builder" / "priced_product.yaml"
ODPG_GRAPH = REPO_ROOT / "open_data_products" / "odpg" / "data" / "graph" / "graph.yaml"


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
    }


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("validate_document", {"path": str(ODPS_PRODUCT)}),
        ("explain_document", {"path": str(ODPS_PRODUCT)}),
        ("resolve_references", {"path": str(ODPG_GRAPH), "limit": 2}),
        ("list_resources", {}),
        ("get_resource", {"id": "odpv.terms"}),
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
