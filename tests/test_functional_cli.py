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
    assert "Core document commands:" in help_text
    assert "ODPC catalog commands:" in help_text
    assert "resources --id odpc.objects" in help_text
    assert "MCP search_objects" in help_text
    assert "ODPV vocabulary commands:" in help_text
    assert "resources --id odpv.terms" in help_text
    assert "MCP search_terms" in help_text
    assert "Discovery and agent commands:" in help_text
    assert "ODPC catalog commands:" in help_text
    assert "odpc-summary" in help_text
    assert "odpc-search" in help_text
    assert "ODPV vocabulary commands:" in help_text
    assert "odpv-summary" in help_text
    assert "odpv-search" in help_text
    assert "ODPG graph commands:" in help_text
    assert "odpg-generate" in help_text
    assert "Product/Data Contract commands:" in help_text
    assert "Examples:" in help_text
    assert "open-data-products validate product.yaml --json" in help_text
    assert (
        "open-data-products product contract-report product.yaml contract.yaml --json"
        in help_text
    )
    assert "open-data-products resources --id odpc.objects --json" in help_text
    assert "open-data-products resources --id odpv.terms --json" in help_text
    assert (
        "open-data-products odpg-generate graph.yaml --output graph-explorer.html --json"
        in help_text
    )
    assert "validate" in help_text
    assert "product" in help_text


def test_product_cli_help_uses_compact_command_metavar_and_examples(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["product", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "usage: open-data-products product [-h] PRODUCT_COMMAND ..." in help_text
    assert "{check-contract,resolve-contracts" not in help_text
    assert "Data Contract workflow commands:" in help_text
    assert "Examples:" in help_text
    assert (
        "open-data-products product resolve-contracts product.yaml --json" in help_text
    )
    assert (
        "open-data-products product audit product.yaml --contract contract.yaml --json"
        in help_text
    )


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


def test_unified_cli_odpc_commands(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
schema: https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml
version: '1.0'
kind: Catalog
catalog:
  metadata:
    id: CAT-001
    name:
      en: Customer Data Product Catalog
    description:
      en: Catalog for customer-facing data products.
  productReferences:
    - id: PRODUCT-001
      productID: PRODUCT-001
      productVersion: '1.0'
      name:
        en: Customer Product
      description:
        en: Customer product reference.
      productModel:
        standard: ODPS
        version: '4.0'
        format: yaml
        $ref: ./product.yaml
""",
        encoding="utf-8",
    )

    assert main(["odpc-summary", str(catalog), "--json"]) == 0
    summary_payload = _json_output(capsys)
    assert summary_payload["spec"] == "odpc"
    assert summary_payload["catalogId"] == "CAT-001"
    assert summary_payload["productReferenceCount"] == 1

    assert main(["odpc-search", "catalog data", "--limit", "1", "--json"]) == 0
    search_payload = _json_output(capsys)
    assert search_payload["spec"] == "odpc"
    assert len(search_payload["matches"]) == 1

    assert main(["odpc-artifacts", str(tmp_path), "--check", "--json"]) == 1
    artifact_check_payload = _json_output(capsys)
    assert artifact_check_payload["spec"] == "odpc"
    assert artifact_check_payload["in_sync"] is False
    assert artifact_check_payload["changed"] == ["odpc.json"]

    assert main(["odpc-artifacts", str(tmp_path), "--json"]) == 0
    artifact_payload = _json_output(capsys)
    assert artifact_payload["artifact_count"] == 1

    assert main(["odpc-artifacts", str(tmp_path), "--check", "--json"]) == 0
    assert _json_output(capsys)["in_sync"] is True


def test_unified_cli_builds_odpc_catalog_from_fragments(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    output = tmp_path / "catalog.yaml"
    html_output = tmp_path / "catalog.html"
    (fragments / "product.yaml").write_text(
        """
schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      name: Agent Ready Product
      productID: agent-ready-product
      visibility: public
""",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "odpc-build",
                str(fragments),
                "--output",
                str(output),
                "--html",
                str(html_output),
                "--id",
                "CAT-CLI",
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)
    assert payload["spec"] == "odpc"
    assert payload["kind"] == "Catalog"
    assert payload["output"] == str(output)
    assert payload["html"] == str(html_output)
    assert payload["productReferenceCount"] == 1

    assert output.read_text(encoding="utf-8").startswith(
        "schema: https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml\n"
    )
    html = html_output.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "Agent Ready Product" in html


def test_unified_cli_odpv_commands(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["odpv-summary", "--json"]) == 0
    summary_payload = _json_output(capsys)
    assert summary_payload["spec"] == "odpv"
    assert summary_payload["kind"] == "Vocabulary"
    assert summary_payload["term_count"] == 59

    assert (
        main(["odpv-search", "governance policy risk", "--limit", "2", "--json"]) == 0
    )
    search_payload = _json_output(capsys)
    assert search_payload["spec"] == "odpv"
    assert len(search_payload["matches"]) == 2

    assert main(["odpv-resolve", "reusable data asset", "--json"]) == 0
    resolve_payload = _json_output(capsys)
    assert resolve_payload["match"]["id"] == "DataProduct"
    assert resolve_payload["match"]["matchType"] == "alias"

    assert main(["odpv-explain", "DataProduct", "--json"]) == 0
    assert _json_output(capsys)["id"] == "DataProduct"

    assert (
        main(
            [
                "odpv-relationship",
                "DataProduct",
                "supports",
                "UseCase",
                "--json",
            ]
        )
        == 0
    )
    assert _json_output(capsys)["compatible"] is True

    assert main(["odpv-context", "DataProduct", "--json"]) == 0
    assert _json_output(capsys)["contextType"] == "odpv.term"


def test_unified_cli_odpg_reasoning_commands(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    assert main(["odpg-summary", str(ODPG_GRAPH)]) == 0
    assert _json_output(capsys)["nodeCount"] == 9

    assert (
        main(["odpg-traverse", str(ODPG_GRAPH), "--start", "AGENT-AVIATION-001"]) == 0
    )
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

    output = tmp_path / "graph-explorer.html"
    assert (
        main(
            [
                "odpg-generate",
                str(ODPG_GRAPH),
                "--output",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)
    assert payload["spec"] == "odpg"
    assert payload["generated"] is True
    assert output.exists()


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

    assert (
        main(["product", "check-contract", str(product), str(contract), "--json"]) == 1
    )
    check_payload = _json_output(capsys)
    assert check_payload["product"]["valid"] is True
    assert check_payload["contract"]["passed"] is False
    assert check_payload["summary"].startswith("Product valid; Data Contract invalid")

    assert (
        main(["product", "align-contract", str(product), str(contract), "--json"]) == 1
    )
    alignment_payload = _json_output(capsys)
    assert alignment_payload["contract_valid"] is False
    assert alignment_payload["summary"].startswith(
        "Product valid; Data Contract invalid"
    )

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
