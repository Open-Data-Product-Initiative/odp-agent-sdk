"""Functional tests for the stdio MCP JSON-RPC handler surface."""

from pathlib import Path
from typing import Any, Dict

import pytest

from open_data_products.mcp.server import handle

pytestmark = pytest.mark.functional

REPO_ROOT = Path(__file__).resolve().parents[1]
ODPS_PRODUCT = REPO_ROOT / "apps" / "pricing_402_builder" / "priced_product.yaml"
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
        "search_terms",
        "search_objects",
        "search_graph_objects",
        "summarize_graph",
        "traverse_graph",
        "analyze_graph",
        "agent_context",
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
        ("search_terms", {"query": "data product", "limit": 1}),
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
