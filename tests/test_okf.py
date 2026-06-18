"""Tests for Open Knowledge Format adapter helpers."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from open_data_products.cli import main


def _write_concept(path: Path, frontmatter: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")


def test_okf_validate_accepts_minimal_bundle_and_reports_links(tmp_path: Path) -> None:
    from open_data_products.okf import validate_okf_bundle

    bundle = tmp_path / "bundle"
    _write_concept(
        bundle / "tables" / "orders.md",
        "type: BigQuery Table\ntitle: Orders\ndescription: Orders table.\n",
        "See [customers](/tables/customers.md) and [missing](/tables/missing.md).\n",
    )
    _write_concept(
        bundle / "tables" / "customers.md",
        "type: BigQuery Table\ntitle: Customers\n",
        "# Schema\n| Column | Type |\n|---|---|\n",
    )
    (bundle / "index.md").write_text(
        "# Bundle\n* [Orders](tables/orders.md) - Orders table.\n",
        encoding="utf-8",
    )

    result = validate_okf_bundle(bundle)

    assert result.valid is True
    assert result.concept_count == 2
    assert result.errors == []
    assert result.warnings == [
        "tables/orders.md: link target not found: /tables/missing.md"
    ]
    assert [concept.id for concept in result.concepts] == [
        "tables/customers",
        "tables/orders",
    ]


def test_okf_validate_rejects_missing_type(tmp_path: Path) -> None:
    from open_data_products.okf import validate_okf_bundle

    bundle = tmp_path / "bundle"
    _write_concept(bundle / "metrics" / "revenue.md", "title: Revenue\n", "Body\n")

    result = validate_okf_bundle(bundle)

    assert result.valid is False
    assert result.errors == ["metrics/revenue.md: frontmatter.type is required"]


def test_okf_import_writes_generation_source_documents(tmp_path: Path) -> None:
    from open_data_products.okf import import_okf_bundle

    bundle = tmp_path / "bundle"
    _write_concept(
        bundle / "playbooks" / "freshness.md",
        "type: Playbook\ntitle: Freshness Alert\ndescription: Triage freshness.\n",
        "# Steps\nCheck the pipeline dashboard.\n",
    )

    written = import_okf_bundle(bundle, tmp_path / "source_docs")

    assert [path.name for path in written] == ["playbooks_freshness.md"]
    content = written[0].read_text(encoding="utf-8")
    assert "OKF concept: playbooks/freshness" in content
    assert "Check the pipeline dashboard." in content


def test_okf_export_catalog_creates_concept_bundle(tmp_path: Path) -> None:
    from open_data_products.okf import export_okf_bundle, validate_okf_bundle

    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        yaml.safe_dump(
            {
                "catalog": {
                    "metadata": {"name": {"en": "Airport Portfolio"}},
                    "useCases": [
                        {
                            "id": "UC-001",
                            "name": {"en": "Delay Monitoring"},
                            "description": {"en": "Monitor departure delays."},
                            "status": "active",
                        }
                    ],
                    "productReferences": [
                        {
                            "id": "PR-001",
                            "productID": "airport-ops",
                            "productVersion": "1.0.0",
                            "name": {"en": "Airport Ops"},
                            "description": {"en": "Operational product."},
                            "productModel": {
                                "standard": "ODPS",
                                "version": "4.1",
                                "format": "yaml",
                                "$ref": "products/airport-ops.yaml",
                            },
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    written = export_okf_bundle(catalog, tmp_path / "okf")

    assert {path.relative_to(tmp_path / "okf").as_posix() for path in written} >= {
        "index.md",
        "product-references/pr-001.md",
        "use-cases/uc-001.md",
    }
    product = (tmp_path / "okf" / "product-references" / "pr-001.md").read_text(
        encoding="utf-8"
    )
    assert "type: ODPC ProductReference" in product
    assert "resource: products/airport-ops.yaml" in product
    assert validate_okf_bundle(tmp_path / "okf").valid is True


def test_okf_cli_validate_import_export_and_summary(
    tmp_path: Path, capsys: object
) -> None:
    bundle = tmp_path / "bundle"
    _write_concept(
        bundle / "tables" / "orders.md",
        "type: BigQuery Table\ntitle: Orders\n",
        "Orders body.\n",
    )

    assert main(["okf-validate", str(bundle), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["concept_count"] == 1

    assert main(["okf-summary", str(bundle), "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["concepts"][0]["id"] == "tables/orders"

    assert main(["okf-import", str(bundle), "--output", str(tmp_path / "docs")]) == 0
    assert (tmp_path / "docs" / "tables_orders.md").is_file()

    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        "catalog:\n  metadata:\n    name:\n      en: Test\n  signals:\n"
        "    - id: SIG-1\n      name:\n        en: Signal\n",
        encoding="utf-8",
    )
    assert (
        main(["okf-export", str(catalog), "--output", str(tmp_path / "exported")]) == 0
    )
    assert (tmp_path / "exported" / "signals" / "sig-1.md").is_file()


def test_okf_mcp_tools_are_safe_and_do_not_return_bodies(tmp_path: Path) -> None:
    from open_data_products.mcp.tools import TOOLS

    bundle = tmp_path / "bundle"
    _write_concept(
        bundle / "tables" / "orders.md",
        "type: BigQuery Table\ntitle: Orders\n",
        "Secret body text should stay out of summaries.\n",
    )
    tools = {tool["name"]: tool for tool in TOOLS}

    assert tools["validate_okf_bundle"]["class"] == "safe"
    assert tools["list_okf_concepts"]["class"] == "safe"
    payload = json.loads(
        tools["list_okf_concepts"]["handler"]({"path": str(bundle)})["content"][0][
            "text"
        ]
    )

    assert payload["concepts"] == [
        {
            "id": "tables/orders",
            "path": "tables/orders.md",
            "type": "BigQuery Table",
            "title": "Orders",
            "description": "",
            "resource": "",
            "tags": [],
        }
    ]
    assert "Secret body text" not in json.dumps(payload)
