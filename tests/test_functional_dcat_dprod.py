"""Functional release coverage for DCAT catalog and DPROD interoperability."""

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from rdflib import Graph

from open_data_products import (
    discover_dcat_catalog,
    discover_dprod_catalog,
    export_odps_to_dprod,
    validate_dprod,
    wrap_dcat_resource,
    wrap_dprod_resource,
)
from open_data_products._io import load_mapping
from open_data_products.cli import main
from open_data_products.mcp.server import handle

pytestmark = pytest.mark.functional

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "dcat-dprod"
DCAT_CATALOG = FIXTURES / "valid-catalog.ttl"
DPROD_PRODUCT = FIXTURES / "valid-product.ttl"
INVALID_DPROD_PRODUCT = FIXTURES / "invalid-owner.ttl"
UNSAFE_JSONLD = FIXTURES / "unsafe-remote-context.jsonld"
ODPS_PRODUCT = REPO_ROOT / "tests" / "fixtures" / "odps_v42_profiles.yaml"
DCAT_DATASET = "https://fixtures.example.test/datasets/air-quality"
DPROD_ID = "https://fixtures.example.test/products/air-quality"


def _json_output(capsys: pytest.CaptureFixture[str]) -> Dict[str, Any]:
    """Read one JSON response emitted by the unified CLI."""
    return json.loads(capsys.readouterr().out)


def _mcp_payload(name: str, arguments: Dict[str, str]) -> Dict[str, Any]:
    """Call one MCP tool and return its JSON payload."""
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
    assert response["result"].get("isError") is not True
    return json.loads(response["result"]["content"][0]["text"])


def test_dcat_and_dprod_public_api_workflows_use_versioned_fixtures(
    tmp_path: Path,
) -> None:
    """Public APIs preserve source boundaries and produce valid local artifacts."""
    dcat_inventory = discover_dcat_catalog(str(DCAT_CATALOG))
    dcat_draft = wrap_dcat_resource(
        str(DCAT_CATALOG), DCAT_DATASET, str(tmp_path / "dcat-air.yaml")
    )
    dprod_validation = validate_dprod(str(DPROD_PRODUCT))
    dprod_inventory = discover_dprod_catalog(str(DPROD_PRODUCT))
    dprod_draft = wrap_dprod_resource(
        str(DPROD_PRODUCT), DPROD_ID, str(tmp_path / "dprod-air.yaml")
    )
    dprod_export = export_odps_to_dprod(load_mapping(ODPS_PRODUCT))

    assert DCAT_DATASET in {resource.id for resource in dcat_inventory.resources}
    assert dcat_draft.validation.valid is True
    assert dcat_draft.output is not None
    assert Path(dcat_draft.output).is_file()
    assert dprod_validation.conforms is True
    assert [product.id for product in dprod_inventory.products] == [DPROD_ID]
    assert dprod_draft.validation.valid is True
    assert dprod_draft.output is not None
    assert Path(dprod_draft.output).is_file()
    assert dprod_export.validation.conforms is True
    graph = Graph()
    graph.parse(data=dprod_export.turtle, format="turtle")
    assert len(graph) > 0


def test_dcat_and_dprod_cli_workflows_generate_parseable_release_artifacts(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """CLI workflows return JSON and create only explicitly requested outputs."""
    dcat_report = tmp_path / "dcat-report.html"
    dcat_draft = tmp_path / "dcat-air.yaml"
    dprod_draft = tmp_path / "dprod-air.yaml"
    dprod_export = tmp_path / "dprod-export"

    assert (
        main(
            [
                "portfolio",
                "discover-dcat",
                str(DCAT_CATALOG),
                "--output",
                str(dcat_report),
                "--json",
            ]
        )
        == 0
    )
    assert DCAT_DATASET in {
        resource["id"] for resource in _json_output(capsys)["resources"]
    }
    assert dcat_report.is_file()

    assert (
        main(
            [
                "product",
                "wrap-dcat",
                "--input",
                str(DCAT_CATALOG),
                "--resource",
                DCAT_DATASET,
                "--output",
                str(dcat_draft),
                "--json",
            ]
        )
        == 0
    )
    assert _json_output(capsys)["results"][0]["validation"]["valid"] is True
    assert dcat_draft.is_file()

    assert main(["dprod-validate", str(DPROD_PRODUCT), "--json"]) == 0
    assert _json_output(capsys)["conforms"] is True

    assert main(["portfolio", "discover-dprod", str(DPROD_PRODUCT), "--json"]) == 0
    assert _json_output(capsys)["products"][0]["id"] == DPROD_ID

    assert (
        main(
            [
                "product",
                "wrap-dprod",
                "--input",
                str(DPROD_PRODUCT),
                "--resource",
                DPROD_ID,
                "--output",
                str(dprod_draft),
                "--json",
            ]
        )
        == 0
    )
    assert _json_output(capsys)["validation"]["valid"] is True
    assert dprod_draft.is_file()

    assert (
        main(
            [
                "product",
                "export-dprod",
                "--input",
                str(ODPS_PRODUCT),
                "--output",
                str(dprod_export),
                "--json",
            ]
        )
        == 0
    )
    assert _json_output(capsys)["validation"]["conforms"] is True
    assert dprod_export.with_suffix(".ttl").is_file()
    assert dprod_export.with_suffix(".jsonld").is_file()


def test_dcat_and_dprod_mcp_workflows_redact_local_paths_and_write_selected_outputs(
    tmp_path: Path,
) -> None:
    """MCP safe and state-changing tools keep local paths out of responses."""
    dcat_draft = tmp_path / "dcat-air.yaml"
    dprod_draft = tmp_path / "dprod-air.yaml"
    dprod_export = tmp_path / "dprod-export"

    dcat_inventory = _mcp_payload(
        "discover_dcat_catalog", {"source": str(DCAT_CATALOG)}
    )
    dcat_wrap = _mcp_payload(
        "wrap_dcat_resource",
        {
            "source": str(DCAT_CATALOG),
            "resource": DCAT_DATASET,
            "output": str(dcat_draft),
        },
    )
    dprod_validation = _mcp_payload("validate_dprod", {"source": str(DPROD_PRODUCT)})
    dprod_inventory = _mcp_payload(
        "discover_dprod_catalog", {"source": str(DPROD_PRODUCT)}
    )
    dprod_wrap = _mcp_payload(
        "wrap_dprod_resource",
        {
            "source": str(DPROD_PRODUCT),
            "resource": DPROD_ID,
            "output": str(dprod_draft),
        },
    )
    dprod_written = _mcp_payload(
        "export_dprod", {"source": str(ODPS_PRODUCT), "output": str(dprod_export)}
    )

    assert DCAT_DATASET in {resource["id"] for resource in dcat_inventory["resources"]}
    assert dcat_wrap["validation"]["valid"] is True
    assert dprod_validation["conforms"] is True
    assert dprod_inventory["products"][0]["id"] == DPROD_ID
    assert dprod_wrap["validation"]["valid"] is True
    assert dprod_written["validation"]["conforms"] is True
    assert dcat_draft.is_file()
    assert dprod_draft.is_file()
    assert dprod_export.with_suffix(".ttl").is_file()
    assert dprod_export.with_suffix(".jsonld").is_file()
    for payload in (
        dcat_inventory,
        dcat_wrap,
        dprod_validation,
        dprod_inventory,
        dprod_wrap,
        dprod_written,
    ):
        assert str(tmp_path) not in json.dumps(payload)
        assert str(FIXTURES) not in json.dumps(payload)


def test_dcat_and_dprod_negative_paths_reject_unsafe_or_nonconformant_sources(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Unsafe JSON-LD and invalid DPROD sources cannot silently create drafts."""
    with pytest.raises(ValueError, match="Remote JSON-LD contexts"):
        discover_dcat_catalog(str(UNSAFE_JSONLD))

    invalid = validate_dprod(str(INVALID_DPROD_PRODUCT))
    assert invalid.conforms is False
    with pytest.raises(ValueError, match="does not conform"):
        wrap_dprod_resource(
            str(INVALID_DPROD_PRODUCT), DPROD_ID, str(tmp_path / "invalid.yaml")
        )

    assert main(["dprod-validate", str(INVALID_DPROD_PRODUCT), "--json"]) == 1
    assert _json_output(capsys)["conforms"] is False


def test_functional_report_records_dcat_and_dprod_release_coverage() -> None:
    """The public report describes DPROD/DCAT fixtures, commands, and limits."""
    report = (REPO_ROOT / "docs" / "reports" / "functional-test-report.md").read_text(
        encoding="utf-8"
    )

    for expected in (
        "tests/test_functional_dcat_dprod.py",
        "tests/test_dcat_catalog.py",
        "tests/test_dprod.py",
        "DCAT catalog intelligence",
        "DPROD 1.0 Beta 2 interoperability",
        "valid-catalog.ttl",
        "valid-product.ttl",
        "Apache Jena",
        "installed-wheel",
    ):
        assert expected in report
