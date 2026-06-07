"""Tests for portfolio workspace rendering."""

import json
from pathlib import Path

from open_data_products.cli import main
from open_data_products.portfolio import explain_portfolio, render_portfolio


def write_sample_workspace(workspace: Path) -> None:
    """Write a small portfolio workspace with linked ODPC, ODPS, and ODPG files."""
    (workspace / "odpc").mkdir(parents=True)
    (workspace / "odps" / "products").mkdir(parents=True)
    (workspace / "odpg").mkdir(parents=True)
    (workspace / "versions" / "2026-06-07T12-30-00Z").mkdir(parents=True)
    (workspace / "versions" / "2026-06-07T12-30-00Z" / "index.html").write_text(
        "<!doctype html><title>Previous Portfolio</title>",
        encoding="utf-8",
    )
    (workspace / "portfolio.yaml").write_text(
        """
metadata:
  id: demo-portfolio
  name: Demo Portfolio
  generatedAt: "2026-06-07T13:00:00Z"
  sdkVersion: "0.2.0"
sources:
  useCases:
    count: 1
  signals:
    count: 1
  products:
    count: 1
versions:
  - id: "2026-06-07T12-30-00Z"
    type: refresh
    summary: Previous snapshot
    html: versions/2026-06-07T12-30-00Z/index.html
""",
        encoding="utf-8",
    )
    (workspace / "odpc" / "catalog.yaml").write_text(
        """
schema: https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml
version: "1.0"
kind: Catalog
catalog:
  metadata:
    id: CAT-DEMO
    name:
      en: Demo Catalog
    description:
      en: Demo catalog from sources.
  businessObjectives:
    - id: OBJ-RETENTION
      name:
        en: Improve Retention
      description:
        en: Reduce customer churn.
      status: active
      priority: high
  useCases:
    - id: UC-RETENTION
      name:
        en: Retention Workflow
      description:
        en: Help teams intervene before churn.
      status: active
      priority: high
  signals:
    - id: SIG-CHURN
      name:
        en: Churn Signal
      description:
        en: Market signal for retention risk.
      type: market
      confidence: high
  productReferences:
    - id: PR-CUSTOMER
      productID: customer-product
      productVersion: "4.1"
      name:
        en: Customer Product
      description:
        en: Customer analytics product.
      status: production
      visibility: internal
      type: dataset
      productModel:
        standard: ODPS
        version: "4.1"
        format: yaml
        $ref: ../odps/products/customer-product.yaml
""",
        encoding="utf-8",
    )
    (workspace / "odps" / "products" / "customer-product.yaml").write_text(
        """
schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      name: Customer Product
      productID: customer-product
      description: Full product details from product discussions.
      visibility: internal
      status: production
      type: dataset
  pricingPlans:
    declarative:
      en:
        - name: Internal Starter
          priceCurrency: USD
          price: "0"
          unit: request
  SLA:
    declarative:
      - dimension: availability
        objective: Best effort
  dataQuality:
    declarative:
      - dimension: freshness
        objective: Daily
""",
        encoding="utf-8",
    )
    (workspace / "odpg" / "graph.yaml").write_text(
        """
schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: "1.0"
kind: Graph
graph:
  metadata:
    id: GRAPH-DEMO
    name:
      en: Demo Graph
  nodes:
    - id: UC-RETENTION
      type: UseCase
      label:
        en: Retention Workflow
    - id: PR-CUSTOMER
      type: DataProduct
      label:
        en: Customer Product
  edges:
    - source: UC-RETENTION
      target: PR-CUSTOMER
      type: uses
      confidence: high
""",
        encoding="utf-8",
    )


def test_render_portfolio_creates_missing_parent_and_artifact_detail_views(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)
    output = tmp_path / "deep" / "browser" / "index.html"

    result = render_portfolio(workspace, output_path=output)

    html = output.read_text(encoding="utf-8")
    assert result["html"] == str(output)
    assert "Business Objectives" in html
    assert "Use Cases" in html
    assert "Signals" in html
    assert "Products" in html
    assert "Graph" in html
    assert "About" in html
    assert "Improve Retention" in html
    assert "Retention Workflow" in html
    assert "Churn Signal" in html
    assert "Full product details from product discussions." in html
    assert "Internal Starter" in html
    assert "Best effort" in html
    assert "Open Data Products SDK" in html
    assert "ODPC" in html
    assert "ODPS" in html
    assert "ODPG" in html
    assert "2026-06-07T12-30-00Z" in html
    assert "versions/2026-06-07T12-30-00Z/index.html" in html


def test_explain_portfolio_reports_counts_and_browser_entrypoint(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "portfolio"
    write_sample_workspace(workspace)
    render_portfolio(workspace)

    summary = explain_portfolio(workspace)

    assert summary["workspace"] == str(workspace)
    assert summary["html"] == str(workspace / "index.html")
    assert summary["businessObjectiveCount"] == 1
    assert summary["useCaseCount"] == 1
    assert summary["signalCount"] == 1
    assert summary["productReferenceCount"] == 1
    assert summary["productSpecCount"] == 1
    assert summary["graphNodeCount"] == 2
    assert summary["graphEdgeCount"] == 1
    assert summary["versionCount"] == 1


def test_portfolio_cli_render_and_explain_emit_final_json_report(
    tmp_path: Path,
    capsys,
) -> None:
    workspace = tmp_path / "portfolio"
    write_sample_workspace(workspace)

    assert main(["portfolio", "render", str(workspace), "--json"]) == 0
    render_payload = json.loads(capsys.readouterr().out)

    assert render_payload["kind"] == "PortfolioRender"
    assert render_payload["workspace"] == str(workspace)
    assert render_payload["html"] == str(workspace / "index.html")
    assert render_payload["created"] == [str(workspace / "index.html")]

    assert main(["portfolio", "explain", str(workspace), "--json"]) == 0
    explain_payload = json.loads(capsys.readouterr().out)

    assert explain_payload["kind"] == "PortfolioExplain"
    assert explain_payload["workspace"] == str(workspace)
    assert explain_payload["productReferenceCount"] == 1


def test_portfolio_helpers_are_public_exports() -> None:
    from open_data_products import explain_portfolio as public_explain_portfolio
    from open_data_products import render_portfolio as public_render_portfolio

    assert public_render_portfolio is render_portfolio
    assert public_explain_portfolio is explain_portfolio
