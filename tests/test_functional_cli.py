"""Functional tests for the unified command line interface."""

from pathlib import Path
from typing import Any, Dict

import pytest

from open_data_products.cli import main

pytestmark = pytest.mark.functional

REPO_ROOT = Path(__file__).resolve().parents[1]
ODPS_PRODUCT = REPO_ROOT / "apps" / "pricing_402_builder" / "priced_product.yaml"
ODPG_GRAPH = REPO_ROOT / "open_data_products" / "odpg" / "data" / "graph" / "graph.yaml"


def _json_output(capsys: pytest.CaptureFixture[str]) -> Dict[str, Any]:
    import json

    return json.loads(capsys.readouterr().out)


def test_unified_cli_document_workflow(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(ODPS_PRODUCT), "--json"]) == 0
    validate_payload = _json_output(capsys)
    assert validate_payload["valid"] is True
    assert validate_payload["spec"] == "odps"

    assert main(["explain", str(ODPS_PRODUCT), "--json"]) == 0
    explain_payload = _json_output(capsys)
    assert explain_payload["spec"] == "odps"
    assert "summary" in explain_payload

    assert main(["summary", str(ODPS_PRODUCT)]) == 0
    summary_payload = _json_output(capsys)
    assert summary_payload["spec"] == "odps"
    assert "sha256" in summary_payload


def test_unified_cli_resources_and_manifest(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["resources", "--json"]) == 0
    resources_payload = capsys.readouterr().out
    assert "odpv.terms" in resources_payload

    assert main(["manifest", "--json"]) == 0
    manifest_payload = _json_output(capsys)
    assert manifest_payload["name"] == "open-data-products"
    assert {tool["name"] for tool in manifest_payload["tools"]} >= {
        "validate_document",
        "search_terms",
        "agent_context",
    }


def test_unified_cli_odpg_reasoning_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["odpg-summary", str(ODPG_GRAPH)]) == 0
    assert _json_output(capsys)["nodeCount"] == 9

    assert main(["odpg-traverse", str(ODPG_GRAPH), "--start", "AGENT-AVIATION-001"]) == 0
    assert _json_output(capsys)["start"] == "AGENT-AVIATION-001"

    assert main(["odpg-analyze", str(ODPG_GRAPH)]) == 0
    assert "analysis" in _json_output(capsys)

    assert (
        main(
            [
                "odpg-agent-context",
                str(ODPG_GRAPH),
                "--node",
                "AGENT-AVIATION-001",
            ]
        )
        == 0
    )
    assert _json_output(capsys)["focusNode"]["id"] == "AGENT-AVIATION-001"
