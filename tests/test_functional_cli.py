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


def test_unified_cli_help_uses_compact_command_metavar(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "usage: open-data-products [-h] COMMAND ..." in help_text
    assert "{validate,explain,refs" not in help_text
    assert "validate" in help_text
    assert "product" in help_text


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


def test_unified_cli_contract_workflow(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
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

    assert main(["product", "resolve-contracts", str(product), "--json"]) == 0
    assert _json_output(capsys)["references"][0]["inline_spec"] is not None

    assert main(["product", "contract-schema", str(contract), "--json"]) == 0
    assert _json_output(capsys)["field_count"] == 1

    assert main(["product", "contract-report", str(product), "--json"]) == 0
    report_payload = _json_output(capsys)
    assert report_payload["summaries"][0]["name"] == "Orders"
    assert report_payload["summaries"][0]["field_count"] == 1
    assert report_payload["alignments"][0]["passed"] is True

    assert main(["product", "check-contract", str(product), str(contract), "--json"]) == 1
    check_payload = _json_output(capsys)
    assert check_payload["product"]["valid"] is True
    assert check_payload["contract"]["passed"] is False
    assert check_payload["summary"].startswith("Product valid; Data Contract invalid")

    assert (
        main(["product", "align-contract", str(product), str(contract), "--json"])
        == 1
    )
    alignment_payload = _json_output(capsys)
    assert alignment_payload["contract_valid"] is False
    assert alignment_payload["summary"].startswith("Product valid; Data Contract invalid")

    assert (
        main(["product", "audit", str(product), "--contract", str(contract), "--json"])
        == 1
    )
    audit_payload = _json_output(capsys)
    assert audit_payload["contract_count"] == 1
    assert audit_payload["validations"][0]["passed"] is False
    assert audit_payload["findings"][0]["severity"] == "error"
    assert audit_payload["summary"].startswith(
        "Product valid; 1 Data Contract reference"
    )
