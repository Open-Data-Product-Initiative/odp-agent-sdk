"""Tests for portfolio workspace rendering."""

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from open_data_products._io import load_mapping
from open_data_products.cli import main
from open_data_products.portfolio import (
    build_portfolio,
    explain_portfolio,
    refresh_portfolio,
    render_portfolio_build_prompt,
    render_portfolio,
    sync_portfolio,
)

PORTFOLIO_PLAN_YAML = """
metadata:
  id: generated-demo
  name: Generated Demo Portfolio
  description: Portfolio generated from source lanes.
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
products:
  - productReference:
      id: PR-CUSTOMER
      productID: customer-product
      productVersion: "4.1"
      name:
        en: Customer Product
      description:
        en: Customer analytics product.
      status: production
      visibility: internal
      type: dataset
    odpsProduct:
      schema: https://opendataproducts.org/v4.1/schema/odps.json
      version: "4.1"
      product:
        details:
          en:
            name: Customer Product
            productID: customer-product
            description: Full product generated from source lanes.
            visibility: internal
            status: production
            type: dataset
graphEdges:
  - source: UC-RETENTION
    target: PR-CUSTOMER
    type: uses
    confidence: high
warnings:
  - Review generated pricing evidence.
"""

PORTFOLIO_DRIFT_PLAN_YAML = """
metadata:
  id: generated-demo
  name: Generated Demo Portfolio
  description: Portfolio generated from source lanes.
businessObjectives:
  - id: OBJ-RETENTION-DRIFT
    name:
      en: Improve Retention
    description:
      en: Reduce customer churn.
    status: active
    priority: high
useCases:
  - id: UC-RETENTION-DRIFT
    name:
      en: Retention Workflow
    description:
      en: Help teams intervene before churn.
    status: active
    priority: high
  - id: UC-RENEWAL
    name:
      en: Renewal Save Workflow
    description:
      en: Help teams save renewal risk.
    status: active
    priority: medium
signals:
  - id: SIG-CHURN-DRIFT
    name:
      en: Churn Signal
    description:
      en: Market signal for retention risk.
    type: market
    confidence: high
products:
  - productReference:
      id: PR-CUSTOMER-DRIFT
      productID: customer-product-drift
      productVersion: "4.1"
      name:
        en: Customer Product
      description:
        en: Customer analytics product.
      status: production
      visibility: internal
      type: dataset
    odpsProduct:
      schema: https://opendataproducts.org/v4.1/schema/odps.json
      version: "4.1"
      product:
        details:
          en:
            name: Customer Product
            productID: customer-product-drift
            description: Full product generated from source lanes.
            visibility: internal
            status: production
            type: dataset
graphEdges:
  - source: UC-RETENTION-DRIFT
    target: PR-CUSTOMER-DRIFT
    type: uses
    confidence: high
  - source: UC-RENEWAL
    target: PR-CUSTOMER-DRIFT
    type: uses
    confidence: medium
warnings:
  - Review generated pricing evidence.
"""

PORTFOLIO_SCHEMA_DRIFT_PLAN_YAML = """
metadata:
  id: generated-demo
  name: Generated Demo Portfolio
  description: Portfolio generated from source lanes.
businessObjectives:
  - id: OBJ-EXPANSION
    name:
      en: Expand Retention Growth
    description:
      en: Increase customer retention outcomes.
    status: proposed
useCases:
  - id: UC-EXPANSION
    name:
      en: Retention Expansion Workflow
    description:
      en: Help account teams identify expansion opportunities.
    status: proposed
signals:
  - id: SIG-EXPANSION
    name:
      en: Portfolio Expansion Signal
    description:
      en: Product teams discussed a new portfolio opportunity.
    type: portfolio
    confidence: medium
products:
  - productReference:
      id: PR-EXPANSION
      productID: expansion-product
      productVersion: "4.1"
      name:
        en: Expansion Product
      description:
        en: Expansion analytics product.
      status: proposed
      visibility: internal
      type: dataset
    odpsProduct:
      schema: https://opendataproducts.org/v4.1/schema/odps.json
      version: "4.1"
      product:
        details:
          en:
            name: Expansion Product
            productID: expansion-product
            description: Full product generated from source lanes.
            visibility: internal
            status: proposed
            type: dataset
        pricingPlans:
          - en:
              name:
                en: Internal Starter
              priceCurrency: USD
              price: "0.00"
              billingDuration: month
              unit: account
              description:
                en: Pilot access.
        dataAccess:
          API:
            name:
              en: Internal API
            description:
              en: Internal API access for account teams.
            outputPortType: API
graphEdges:
  - source: UC-EXPANSION
    target: PR-EXPANSION
    type: informs
    confidence: medium
"""

PORTFOLIO_DELTA_PLAN_YAML = """
metadata:
  id: generated-demo
  name: Generated Demo Portfolio
  description: Portfolio generated from source lanes.
useCases:
  - id: UC-RENEWAL
    name:
      en: Renewal Save Workflow
    description:
      en: Help teams save renewal risk.
    status: active
    priority: medium
graphEdges:
  - source: UC-RENEWAL
    target: PR-CUSTOMER
    type: uses
    confidence: medium
"""


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


def write_source_lanes(root: Path) -> None:
    """Write source lane folders used by portfolio build tests."""
    (root / "objectives").mkdir(parents=True)
    (root / "use-cases").mkdir(parents=True)
    (root / "signals").mkdir(parents=True)
    (root / "products").mkdir(parents=True)
    (root / "objectives" / "retention-objective.md").write_text(
        "Business objective: Reduce churn risk and protect renewals\n",
        encoding="utf-8",
    )
    (root / "use-cases" / "retention.md").write_text(
        "Use case: Retention Workflow\n",
        encoding="utf-8",
    )
    (root / "signals" / "market.txt").write_text(
        "Signal: churn pressure is rising\n",
        encoding="utf-8",
    )
    (root / "products" / "customer.md").write_text(
        "Product discussion: Customer Product\n",
        encoding="utf-8",
    )


def fake_portfolio_client(prompt: str, model: str) -> str:
    """Return a deterministic portfolio plan and assert source lanes are present."""
    assert model == "test-model"
    assert "Business objective: Reduce churn risk and protect renewals" in prompt
    assert "Use case: Retention Workflow" in prompt
    assert "Signal: churn pressure is rising" in prompt
    assert "Product discussion: Customer Product" in prompt
    return PORTFOLIO_PLAN_YAML


def drifting_portfolio_client(prompt: str, model: str) -> str:
    """Return drifted IDs once the added renewal source is present."""
    assert model == "test-model"
    if "Use case: Renewal Save Workflow" in prompt:
        return PORTFOLIO_DRIFT_PLAN_YAML
    return PORTFOLIO_PLAN_YAML


def schema_drift_portfolio_client(prompt: str, model: str) -> str:
    """Return a plan with common LLM enum and relationship drift."""
    assert model == "test-model"
    return PORTFOLIO_SCHEMA_DRIFT_PLAN_YAML


def delta_portfolio_client(prompt: str, model: str) -> str:
    """Return only artifacts derived from a new source document."""
    assert model == "test-model"
    assert "Use case: Renewal Save Workflow" in prompt
    assert "Business objective: Reduce churn risk and protect renewals" not in prompt
    assert "Use case: Retention Workflow" not in prompt
    assert "Signal: churn pressure is rising" not in prompt
    assert "Product discussion: Customer Product" not in prompt
    return PORTFOLIO_DELTA_PLAN_YAML


def full_refresh_portfolio_client(prompt: str, model: str) -> str:
    """Assert all source documents are included in a forced full refresh."""
    assert model == "test-model"
    assert "Business objective: Reduce churn risk and protect renewals" in prompt
    assert "Use case: Renewal Save Workflow" in prompt
    assert "Use case: Retention Workflow" in prompt
    assert "Signal: churn pressure is rising" in prompt
    assert "Product discussion: Customer Product" in prompt
    return PORTFOLIO_DRIFT_PLAN_YAML


def test_render_portfolio_creates_missing_parent_and_artifact_detail_views(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)
    output = tmp_path / "deep" / "browser" / "index.html"

    result = render_portfolio(workspace, output_path=output)

    html = output.read_text(encoding="utf-8")
    assert result["html"] == str(output)
    assert "validationResults" in result
    assert "catalog" in result["validationResults"]
    assert "graph" in result["validationResults"]
    assert "products" in result["validationResults"]
    assert "Business Objectives" in html
    assert "Use Cases" in html
    assert "Signals" in html
    assert "Products" in html
    assert "Graph" in html
    assert "About" in html
    assert 'id="tab-overview"' in html
    assert 'for="tab-graph"' in html
    assert 'class="tab-panel graph-panel"' in html
    assert "Recommended next actions" in html
    assert "Suggested follow-ups are derived from warnings" not in html
    assert "Portfolio versions" in html
    assert '<section class="overview-section" aria-label="Portfolio status">' in html
    assert '<section class="overview-section" aria-label="Portfolio versions">' in html
    assert '<div class="overview-card-grid">' in html
    assert 'class="action-card overview-card status-card"' in html
    assert 'class="action-card overview-card versions-card"' in html
    assert ".overview-section {" in html
    assert "margin-top: 28px;" in html
    assert "Show all" in html
    assert "table-layout: fixed" in html
    assert "overflow-wrap: anywhere" in html
    assert 'class="graph-explorer-frame"' in html
    assert "vis-network@9.1.9" in html
    assert "new vis.Network" in html
    assert "workspace-main" in html
    assert "filter-panel" in html
    assert ".topbar{display:none!important;}" in html
    assert "Open Data Product Graphs Explorer" not in html
    assert "<footer" in html
    assert "Catalog YAML" in html
    assert "Graph YAML" in html
    assert "Improve Retention" in html
    assert "Retention Workflow" in html
    assert "Churn Signal" in html
    assert "Full product details from product discussions." in html
    assert "Internal Starter" in html
    assert "Best effort" in html
    assert "Generated ODPS products are drafts" in html
    assert "Human review and acceptance are required" in html
    assert "quick start from source material" in html
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
    assert "validationResults" in summary
    assert "catalog" in summary["validationResults"]


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
    assert "validationResults" in render_payload

    assert main(["portfolio", "explain", str(workspace), "--json"]) == 0
    explain_payload = json.loads(capsys.readouterr().out)

    assert explain_payload["kind"] == "PortfolioExplain"
    assert explain_payload["workspace"] == str(workspace)
    assert explain_payload["productReferenceCount"] == 1


def test_build_portfolio_creates_workspace_artifacts_from_source_lanes(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)

    result = build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=fake_portfolio_client,
        model="test-model",
    )

    assert result["kind"] == "PortfolioBuild"
    assert result["workspace"] == str(workspace)
    assert result["html"] == str(workspace / "index.html")
    assert result["sourceCounts"] == {
        "objectives": 1,
        "useCases": 1,
        "signals": 1,
        "products": 1,
    }
    assert result["artifactCounts"]["productReferences"] == 1
    assert result["artifactCounts"]["odpsProducts"] == 1
    assert result["warnings"] == ["Review generated pricing evidence."]
    assert "validationResults" in result
    assert "catalog" in result["validationResults"]
    assert "graph" in result["validationResults"]
    assert len(result["validationResults"]["products"]) == 1
    assert (workspace / "portfolio.yaml").exists()
    assert (workspace / "portfolio-state.yaml").exists()
    assert (workspace / "odpc" / "catalog.yaml").exists()
    assert (
        workspace / "odpc" / "fragments" / "product_reference_PR-CUSTOMER.yaml"
    ).exists()
    assert (workspace / "odps" / "products" / "customer-product.yaml").exists()
    assert (workspace / "odpg" / "graph.yaml").exists()
    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "Generated Demo Portfolio" in html
    assert "Full product generated from source lanes." in html
    catalog_text = (workspace / "odpc" / "catalog.yaml").read_text(encoding="utf-8")
    assert "$ref: ../odps/products/customer-product.yaml" in catalog_text
    state_text = (workspace / "portfolio-state.yaml").read_text(encoding="utf-8")
    assert "sha256" in state_text


def test_build_portfolio_uses_user_title_and_persists_it_across_reruns(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)

    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        title="Board Approved Portfolio",
        client=drifting_portfolio_client,
        model="test-model",
    )

    html = (workspace / "index.html").read_text(encoding="utf-8")
    portfolio_text = (workspace / "portfolio.yaml").read_text(encoding="utf-8")
    catalog_text = (workspace / "odpc" / "catalog.yaml").read_text(encoding="utf-8")
    state_text = (workspace / "portfolio-state.yaml").read_text(encoding="utf-8")
    assert "Board Approved Portfolio" in html
    assert "Board Approved Portfolio" in portfolio_text
    assert "Board Approved Portfolio" in catalog_text
    assert "title: Board Approved Portfolio" in state_text
    assert "Generated Demo Portfolio" not in html

    build_portfolio(
        workspace,
        client=drifting_portfolio_client,
        model="test-model",
    )

    rerun_html = (workspace / "index.html").read_text(encoding="utf-8")
    rerun_catalog = (workspace / "odpc" / "catalog.yaml").read_text(encoding="utf-8")
    assert "Board Approved Portfolio" in rerun_html
    assert "Board Approved Portfolio" in rerun_catalog
    assert "Generated Demo Portfolio" not in rerun_html


def test_build_portfolio_normalizes_generated_plan_to_schema_shapes(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)

    result = build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=schema_drift_portfolio_client,
        model="test-model",
    )

    assert result["valid"] is True
    catalog = (workspace / "odpc" / "catalog.yaml").read_text(encoding="utf-8")
    assert "status: proposed" not in catalog
    assert "status: draft" in catalog
    assert "type: operational" in catalog
    assert "origin: internal" in catalog
    assert "method: generated portfolio source lanes" in catalog
    assert "observedAt:" in catalog

    product = (workspace / "odps" / "products" / "expansion-product.yaml").read_text(
        encoding="utf-8"
    )
    assert "visibility: organisation" in product
    assert "status: draft" in product
    assert "pricingPlans:" in product
    assert "declarative:" in product
    assert "unit: On-request" in product
    assert "name: Internal Starter" in product
    assert "description: Pilot access." in product
    assert "dataAccess:" in product
    assert "outputPortType: API" in product
    product_document = load_mapping(
        workspace / "odps" / "products" / "expansion-product.yaml"
    )
    schema = load_mapping(Path("open_data_products/odps/data/schema/odps.json"))
    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(product_document),
        key=lambda error: list(error.path),
    )
    assert schema_errors == []

    graph = (workspace / "odpg" / "graph.yaml").read_text(encoding="utf-8")
    assert "description:" in graph
    assert "$ref: ../odpc/fragments/use_case_UC-EXPANSION.yaml" in graph
    assert "from: UC-EXPANSION" in graph
    assert "to: PR-EXPANSION" in graph
    assert "source: UC-EXPANSION" not in graph
    assert "target: PR-EXPANSION" not in graph
    assert "type: relatedTo" in graph


def test_portfolio_build_prompt_defines_schema_and_linking_rules() -> None:
    lanes = {
        "objectives": [
            {
                "path": "inputs/objectives/retention.md",
                "text": "Business objective: Improve Retention",
                "sha256": "obj",
            }
        ],
        "useCases": [
            {
                "path": "inputs/use-cases/retention.md",
                "text": "Use case: Retention Workflow",
                "sha256": "abc",
            }
        ],
        "signals": [],
        "products": [],
    }

    prompt = render_portfolio_build_prompt(lanes)

    assert "Return only YAML" in prompt
    assert "metadata:" in prompt
    assert "businessObjectives:" in prompt
    assert "useCases:" in prompt
    assert "signals:" in prompt
    assert "products:" in prompt
    assert "productReference:" in prompt
    assert "odpsProduct:" in prompt
    assert "graphEdges:" in prompt
    assert "warnings:" in prompt
    assert "productReference.productID must match odpsProduct" in prompt
    assert 'productModel.$ref must be "../odps/products/<productID>.yaml"' in prompt
    assert "Graph edge source and target values must use generated stable IDs" in prompt
    assert "Do not invent confident facts" in prompt
    assert "ODPS v4.1 product component rules" in prompt
    assert "productStrategy:" in prompt
    assert "dataHolder:" in prompt
    assert "paymentGateways:" in prompt
    assert "license:" in prompt
    assert "scope:" in prompt
    assert "SLA must be an object, never a list" in prompt
    assert "dataQuality must be an object, never a list" in prompt
    assert "dataAccess must be a named mapping of access method objects" in prompt
    assert (
        "pricingPlans.declarative.en must be a list of pricing plan objects" in prompt
    )
    assert "#/product/SLA/declarative/default" in prompt
    assert "#/product/dataQuality/declarative/default" in prompt
    assert "#/product/dataAccess/API" in prompt
    assert "#/product/paymentGateways/default" in prompt
    assert "scopeOfUse" not in prompt
    assert "Never use array-index reference paths" in prompt
    assert "Do not emit dataOps" in prompt
    assert "x-* extension fields are allowed" in prompt
    assert "inputs/objectives/retention.md" in prompt
    assert "Business objective: Improve Retention" in prompt
    assert "inputs/use-cases/retention.md" in prompt
    assert "Use case: Retention Workflow" in prompt


def test_portfolio_cli_build_emits_one_final_json_report(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)

    from open_data_products import generation

    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: fake_portfolio_client,
    )

    assert (
        main(
            [
                "portfolio",
                "build",
                "--objectives",
                str(sources / "objectives"),
                "--use-cases",
                str(sources / "use-cases"),
                "--signals",
                str(sources / "signals"),
                "--products",
                str(sources / "products"),
                "--title",
                "CLI Controlled Portfolio",
                "--model",
                "test-model",
                "--output",
                str(workspace),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == "PortfolioBuild"
    assert payload["workspace"] == str(workspace)
    assert payload["html"] == str(workspace / "index.html")
    assert payload["sourceCounts"]["objectives"] == 1
    assert payload["artifactCounts"]["graphEdges"] == 1
    assert "validationResults" in payload
    assert (workspace / "index.html").exists()
    assert "CLI Controlled Portfolio" in (workspace / "index.html").read_text(
        encoding="utf-8"
    )


def test_portfolio_cli_build_workspace_rerun_uses_saved_sources(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=drifting_portfolio_client,
        model="test-model",
    )
    (sources / "use-cases" / "renewal.md").write_text(
        "Use case: Renewal Save Workflow\n",
        encoding="utf-8",
    )

    from open_data_products import generation

    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: drifting_portfolio_client,
    )

    assert (
        main(
            [
                "portfolio",
                "build",
                str(workspace),
                "--model",
                "test-model",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == "PortfolioBuild"
    assert payload["sourceCounts"]["useCases"] == 2
    assert payload["sourceChanges"]["useCases"]["created"] == [
        str(sources / "use-cases" / "renewal.md")
    ]
    assert payload["snapshot"] is not None


def test_refresh_portfolio_uses_state_sources_and_snapshots_previous_html(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=fake_portfolio_client,
        model="test-model",
    )
    original_html = (workspace / "index.html").read_text(encoding="utf-8")
    (sources / "use-cases" / "renewal.md").write_text(
        "Use case: Renewal Save Workflow\n",
        encoding="utf-8",
    )

    result = refresh_portfolio(
        workspace,
        client=delta_portfolio_client,
        model="test-model",
    )

    assert result["kind"] == "PortfolioRefresh"
    assert result["sourceCounts"]["objectives"] == 1
    assert result["sourceCounts"]["useCases"] == 2
    assert result["processedSourceCounts"]["objectives"] == 0
    assert result["processedSourceCounts"]["useCases"] == 1
    assert result["processedSourceCounts"]["signals"] == 0
    assert result["processedSourceCounts"]["products"] == 0
    assert result["sourceChanges"]["useCases"]["created"] == [
        str(sources / "use-cases" / "renewal.md")
    ]
    assert "validationResults" in result
    assert result["snapshot"] is not None
    snapshot_html = Path(str(result["snapshot"])) / "index.html"
    assert snapshot_html.exists()
    assert snapshot_html.read_text(encoding="utf-8") == original_html
    latest_html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "Retention Workflow" in latest_html
    assert "Renewal Save Workflow" in latest_html
    assert "Customer Product" in latest_html
    assert "Portfolio versions" in latest_html
    assert "versions/" in latest_html
    assert "PortfolioRefresh" in (
        Path(str(result["snapshot"])) / "report.json"
    ).read_text(encoding="utf-8")


def test_refresh_portfolio_all_sources_forces_full_source_processing(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=fake_portfolio_client,
        model="test-model",
    )
    (sources / "use-cases" / "renewal.md").write_text(
        "Use case: Renewal Save Workflow\n",
        encoding="utf-8",
    )

    result = refresh_portfolio(
        workspace,
        client=full_refresh_portfolio_client,
        model="test-model",
        all_sources=True,
    )

    assert result["sourceCounts"]["useCases"] == 2
    assert result["processedSourceCounts"]["objectives"] == 1
    assert result["processedSourceCounts"]["useCases"] == 2
    assert result["processedSourceCounts"]["signals"] == 1
    assert result["processedSourceCounts"]["products"] == 1


def test_refresh_portfolio_reports_removed_sources_as_warnings(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    removed_source = sources / "signals" / "market.txt"
    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=fake_portfolio_client,
        model="test-model",
    )
    removed_source.unlink()

    result = refresh_portfolio(
        workspace,
        client=drifting_portfolio_client,
        model="test-model",
    )

    assert result["removed"] == [str(removed_source)]
    assert result["sourceChanges"]["signals"]["removed"] == [str(removed_source)]
    assert f"Source file no longer present: {removed_source}" in result["warnings"]


def test_build_portfolio_rerun_uses_saved_sources_and_preserves_existing_ids(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=drifting_portfolio_client,
        model="test-model",
    )
    (sources / "use-cases" / "renewal.md").write_text(
        "Use case: Renewal Save Workflow\n",
        encoding="utf-8",
    )

    result = build_portfolio(
        workspace,
        client=drifting_portfolio_client,
        model="test-model",
    )

    assert result["kind"] == "PortfolioBuild"
    assert result["sourceCounts"]["objectives"] == 1
    assert result["sourceCounts"]["useCases"] == 2
    assert result["removed"] == []
    assert result["snapshot"] is not None
    assert result["sourceChanges"]["useCases"]["created"] == [
        str(sources / "use-cases" / "renewal.md")
    ]
    catalog_text = (workspace / "odpc" / "catalog.yaml").read_text(encoding="utf-8")
    assert "OBJ-RETENTION\n" in catalog_text
    assert "OBJ-RETENTION-DRIFT" not in catalog_text
    assert "UC-RETENTION\n" in catalog_text
    assert "UC-RETENTION-DRIFT" not in catalog_text
    assert "SIG-CHURN\n" in catalog_text
    assert "SIG-CHURN-DRIFT" not in catalog_text
    assert "PR-CUSTOMER\n" in catalog_text
    assert "PR-CUSTOMER-DRIFT" not in catalog_text
    assert "productID: customer-product\n" in catalog_text
    assert "customer-product-drift" not in catalog_text
    graph_text = (workspace / "odpg" / "graph.yaml").read_text(encoding="utf-8")
    assert "from: UC-RETENTION\n" in graph_text
    assert "to: PR-CUSTOMER\n" in graph_text
    assert "to: PR-CUSTOMER-DRIFT" not in graph_text
    state_text = (workspace / "portfolio-state.yaml").read_text(encoding="utf-8")
    assert "identityRegistry" in state_text


def test_portfolio_cli_refresh_emits_one_final_json_report(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=fake_portfolio_client,
        model="test-model",
    )

    from open_data_products import generation

    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: fake_portfolio_client,
    )

    assert (
        main(
            [
                "portfolio",
                "refresh",
                str(workspace),
                "--model",
                "test-model",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == "PortfolioRefresh"
    assert payload["workspace"] == str(workspace)
    assert payload["snapshot"] is not None
    assert "validationResults" in payload


def test_sync_portfolio_rebuilds_catalog_and_html_from_yaml_fragments(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=fake_portfolio_client,
        model="test-model",
    )
    original_html = (workspace / "index.html").read_text(encoding="utf-8")
    fragment = workspace / "odpc" / "fragments" / "use_case_UC-RETENTION.yaml"
    fragment.write_text(
        """
useCase:
  id: UC-RETENTION
  name:
    en: Retention Workflow Updated
  description:
    en: Updated directly in the YAML fragment.
  status: active
  priority: high
""",
        encoding="utf-8",
    )

    result = sync_portfolio(workspace)

    assert result["kind"] == "PortfolioSync"
    assert result["snapshot"] is not None
    assert result["artifactCounts"]["useCases"] == 1
    assert result["artifactCounts"]["productReferences"] == 1
    assert "validationResults" in result
    snapshot_html = Path(str(result["snapshot"])) / "index.html"
    assert snapshot_html.read_text(encoding="utf-8") == original_html
    catalog_text = (workspace / "odpc" / "catalog.yaml").read_text(encoding="utf-8")
    assert "Retention Workflow Updated" in catalog_text
    latest_html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "Retention Workflow Updated" in latest_html
    assert "Updated directly in the YAML fragment." in latest_html
    state_text = (workspace / "portfolio-state.yaml").read_text(encoding="utf-8")
    assert "identityRegistry" in state_text
    assert "sourceLanePaths" in state_text


def test_sync_portfolio_propagates_linked_odps_product_details(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=fake_portfolio_client,
        model="test-model",
    )
    product_path = workspace / "odps" / "products" / "customer-product.yaml"
    product = yaml.safe_load(product_path.read_text(encoding="utf-8"))
    product["product"]["details"]["en"]["name"] = "Customer Product Curated"
    product["product"]["details"]["en"][
        "description"
    ] = "Curated ODPS product description."
    product_path.write_text(
        yaml.safe_dump(product, sort_keys=False),
        encoding="utf-8",
    )

    result = sync_portfolio(workspace)

    assert result["kind"] == "PortfolioSync"
    fragment_text = (
        workspace / "odpc" / "fragments" / "product_reference_PR-CUSTOMER.yaml"
    ).read_text(encoding="utf-8")
    catalog_text = (workspace / "odpc" / "catalog.yaml").read_text(encoding="utf-8")
    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "Customer Product Curated" in fragment_text
    assert "Curated ODPS product description." in fragment_text
    assert "Customer Product Curated" in catalog_text
    assert "Customer Product Curated" in html
    assert "Curated ODPS product description." in html


def test_sync_portfolio_repairs_odps_data_access_from_yaml(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=fake_portfolio_client,
        model="test-model",
    )
    product_path = workspace / "odps" / "products" / "customer-product.yaml"
    product = yaml.safe_load(product_path.read_text(encoding="utf-8"))
    product["product"]["dataAccess"] = {
        "description": {"en": "Internal access during pilot."}
    }
    product["product"]["details"]["en"][
        "useCases"
    ] = "Retention risk workflow and renewal planning"
    product["product"]["details"]["en"]["SLA"] = {"updateFrequency": "daily"}
    product["product"]["SLA"] = [
        {
            "en": {
                "objective": "Daily freshness target during pilot",
                "availability": "Best-effort availability",
                "description": "Daily freshness target during pilot with best-effort availability.",
            }
        }
    ]
    product["product"]["dataQuality"] = {
        "policyDescription": {"en": "Data quality checks pending agreement."}
    }
    product["product"]["x-dataOps"] = [
        {
            "infrastructure": [{"platform": "best-effort"}],
            "updateFrequency": [{"value": 1, "unit": "days"}],
        }
    ]
    product["product"]["pricingPlans"] = {
        "declarative": {
            "en": [
                {
                    "plan": {"en": "Internal Starter Plan"},
                    "priceAmount": 0,
                    "billingDuration": "month",
                    "unit": "request",
                    "priceCurrency": "USD",
                }
            ]
        }
    }
    product_path.write_text(
        yaml.safe_dump(product, sort_keys=False),
        encoding="utf-8",
    )

    result = sync_portfolio(workspace)

    assert result["valid"] is True
    product_text = product_path.read_text(encoding="utf-8")
    assert "dataAccess:" in product_text
    assert "API:" in product_text
    assert "default:" in product_text
    assert "outputPortType: API" in product_text
    assert "x-dataOps:" in product_text
    assert "\n  dataOps:" not in product_text
    assert "- infrastructure:" in product_text
    assert "updateFrequency" in product_text
    assert "SLA:" in product_text
    assert "availability:" not in product_text
    assert "Daily freshness target during pilot" in product_text
    assert "useCaseTitle: Retention risk workflow and renewal planning" in product_text
    assert "policyDescription:" not in product_text
    assert "priceAmount:" not in product_text
    assert "plan:" not in product_text
    assert "name: Internal Starter Plan" in product_text
    assert "price: '0'" in product_text
    product_document = load_mapping(product_path)
    schema = load_mapping(Path("open_data_products/odps/data/schema/odps.json"))
    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(product_document),
        key=lambda error: list(error.path),
    )
    assert schema_errors == []


def test_portfolio_cli_sync_emits_one_final_json_report(
    tmp_path: Path,
    capsys,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=fake_portfolio_client,
        model="test-model",
    )

    assert main(["portfolio", "sync", str(workspace), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == "PortfolioSync"
    assert payload["workspace"] == str(workspace)
    assert payload["snapshot"] is not None
    assert "validationResults" in payload


def test_portfolio_helpers_are_public_exports() -> None:
    from open_data_products import build_portfolio as public_build_portfolio
    from open_data_products import explain_portfolio as public_explain_portfolio
    from open_data_products import refresh_portfolio as public_refresh_portfolio
    from open_data_products import render_portfolio as public_render_portfolio
    from open_data_products import sync_portfolio as public_sync_portfolio

    assert public_build_portfolio is build_portfolio
    assert public_refresh_portfolio is refresh_portfolio
    assert public_render_portfolio is render_portfolio
    assert public_sync_portfolio is sync_portfolio
    assert public_explain_portfolio is explain_portfolio
