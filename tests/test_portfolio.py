"""Tests for portfolio workspace rendering."""

import json
import sys
import types
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml
from jsonschema import Draft202012Validator

from open_data_products._io import load_mapping
from open_data_products.cli import main
from open_data_products import obfuscate_personal_data
from open_data_products.portfolio import (
    PortfolioBuildRequest,
    PortfolioBuildResult,
    PortfolioPipeline,
    PortfolioSourceLanes,
    _chunk_localization_strings,
    _reduce_source_lanes_for_prompt,
    build_portfolio,
    explain_portfolio,
    inspect_portfolio_intake,
    localize_portfolio,
    parse_portfolio_plan,
    refresh_portfolio,
    render_portfolio_executive_summary_prompt,
    render_portfolio_build_prompt,
    render_portfolio,
    sync_portfolio,
)
from open_data_products.generation.models import (
    PortfolioPrivacySettings,
    PortfolioSourceBudget,
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
executiveSummary:
  portfolioPosition:
    headline: Retention is the strongest near-term leadership topic.
    narrative: >
      The portfolio connects a retention objective, a retention workflow,
      churn pressure signals, and a customer product candidate.
  priorityBriefing:
    recommendation: Fund retention workflow validation first. Validate partner expansion next. Strengthen signal coverage before final prioritization.
    primaryFocus:
      label: Priority 1
      title: "Focus first: Retention workflow validation"
      message: Retention is the clearest funding candidate because it connects a business objective, an operational use case, and a candidate product.
      action: Fund validation of the retention workflow before assigning capacity to other portfolio paths.
      rationaleTitle: Why this is first
      rationale:
        - Strongest objective, use case, and product alignment
        - "Clear business outcome: reduce preventable churn"
        - Best current evidence for near-term delivery
      confidence: high
      evidenceType: direct
      evidence:
        - type: businessObjective
          label: Reduce preventable churn
          id: OBJ-RETENTION
        - type: useCase
          label: Retention risk workflow
          id: UC-RETENTION
        - type: productReference
          label: Customer health signals
          id: PR-CUSTOMER
    secondaryFocus:
      label: Priority 2
      title: "Validate next: Partner expansion"
      message: Partner expansion has enough evidence to stay in the leadership discussion, but it is not ready to compete with retention for first delivery funding.
      action: Validate the business case before assigning delivery capacity.
      rationaleTitle: Why this is second
      rationale:
        - Has objective and use case alignment
        - Candidate product exists
        - Evidence is inferred, not yet strong enough for first priority
      confidence: medium
      evidenceType: inferred
      evidence:
        - type: businessObjective
          label: Improve partner-led expansion planning
          id: OBJ-PARTNER-EXPANSION
        - type: useCase
          label: Partner expansion planning
          id: UC-PARTNER-EXPANSION
        - type: productReference
          label: Partner performance signals
          id: PR-PARTNER
    blocker:
      label: Risk
      title: "Do not ignore: Signal coverage risk"
      message: Signal coverage looks thin. This may make prioritization look more certain than it is.
      action: Improve signal coverage before using this portfolio view for final prioritization.
      rationaleTitle: Why this matters
      rationale:
        - Weak evidence can distort funding decisions
        - Thin signals reduce confidence
        - Leadership may over-prioritize incomplete paths
      confidence: low
      evidenceType: inferred
      evidence:
        - type: signal
          label: Churn market demand
          id: SIG-CHURN
    readinessCheck:
      label: Readiness check
      title: "Before build starts: Commercial readiness review"
      message: The customer health product still needs human review before production commitment.
      action: Confirm ownership, value model, operating model, and delivery readiness.
      checklist:
        - Business owner confirmed
        - Value model reviewed
        - Delivery owner assigned
        - Operating model clear
        - Production readiness reviewed
      confidence: medium
      evidenceType: inferred
      evidence:
        - type: productReference
          label: Customer health signals
          id: PR-CUSTOMER
  swot:
    strengths:
      - id: STR-RETENTION-DEMAND
        statement: Retention has clear objective and use-case pull.
        decisionImplication: Treat retention as the strongest candidate for first delivery funding.
        evidenceRefs:
          - type: businessObjective
            id: OBJ-RETENTION
          - type: useCase
            id: UC-RETENTION
        confidence: high
        inference: false
    weaknesses:
      - id: WEAK-OWNERSHIP-GAP
        statement: Product ownership evidence needs review before delivery commitment.
        decisionImplication: Confirm ownership, value model, and delivery readiness before moving into build.
        evidenceRefs:
          - type: productReference
            id: PR-CUSTOMER
        confidence: medium
        inference: true
    opportunities:
      - id: OPP-RETENTION-REVIEW
        statement: Leadership can use the portfolio to prioritize retention interventions.
        decisionImplication: Validate the next growth case before assigning delivery capacity.
        evidenceRefs:
          - type: signal
            id: SIG-CHURN
        confidence: medium
        inference: true
    threats:
      - id: THREAT-THIN-SIGNALS
        statement: Thin market signal coverage could overstate portfolio confidence.
        decisionImplication: Strengthen signal coverage before using this view for final prioritization.
        evidenceRefs:
          - type: signal
            id: SIG-CHURN
        confidence: low
        inference: true
  leadershipDecisions:
    - id: DECIDE-RETENTION-FUNDING
      question: Should leadership fund the retention product as the next delivery priority?
      decisionType: invest
      urgency: high
      evidenceRefs:
        - type: businessObjective
          id: OBJ-RETENTION
        - type: productReference
          id: PR-CUSTOMER
  evidenceGaps:
    - id: GAP-OWNER
      statement: Product owner and accountable business sponsor are not explicit.
      evidenceRefs:
        - type: productReference
          id: PR-CUSTOMER
  confidenceNotes:
    - Priority items marked as inferred need human review before business action.
  leadershipSummary:
    recommendedFirstMove: Fund retention workflow validation
    secondGrowthPath: Validate partner expansion evidence
    mainRisk: Signal coverage may be too thin for prioritization confidence
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
        license:
          scope:
            definition: Internal product use for retention and expansion planning.
            restrictions: No external redistribution or resale; contact-level activation view restricted to approved marketing users with consent awareness controls; user-level product behavior aggregated to account level unless clear approved use case requires contact-level detail.
        SLA:
          declarative:
            default:
              dimensions:
                - dimension: refreshTimeliness
                  objective: 100
                  unit: percent
                - dimension: dataFreshness
                  objective: 24
                  unit: hours
            premium: name
        dataQuality:
          declarative:
            premium:
              description: Enhanced checks include CRM and billing reconciliation.
              dimensions:
                - dimension: reconciliation
                  displayTitle: Source Reconciliation
                  objective: 98
                  unit: percentage
                  weight: 20
                  description: Active account count reconciles with CRM and billing within agreed tolerance.
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

EXECUTIVE_SUMMARY_YAML = """
schema: https://opendataproducts.org/sdk/portfolio-executive-summary/v1
kind: PortfolioExecutiveSummary
metadata:
  generatedAt: "2026-06-28T00:00:00Z"
  generatedBy: open-data-products
  sdkVersion: "0.0.0"
  model: test-model
  workspaceTitle: Generated Demo Portfolio
portfolioPosition:
  headline: Retention is the strongest near-term leadership topic.
  narrative: >
    The portfolio connects a retention objective, a retention workflow,
    churn pressure signals, and a customer product candidate.
priorityBriefing:
  recommendation: Fund retention workflow validation first. Validate partner expansion next. Strengthen signal coverage before final prioritization.
  primaryFocus:
    label: Priority 1
    title: "Focus first: Retention workflow validation"
    message: Retention is the clearest funding candidate because it connects a business objective, an operational use case, and a candidate product.
    action: Fund validation of the retention workflow before assigning capacity to other portfolio paths.
    rationaleTitle: Why this is first
    rationale:
      - Strongest objective, use case, and product alignment
      - "Clear business outcome: reduce preventable churn"
      - Best current evidence for near-term delivery
    confidence: high
    evidenceType: direct
    evidence:
      - type: businessObjective
        label: Reduce preventable churn
        id: OBJ-RETENTION
      - type: useCase
        label: Retention risk workflow
        id: UC-RETENTION
      - type: productReference
        label: Customer health signals
        id: PR-CUSTOMER
  secondaryFocus:
    label: Priority 2
    title: "Validate next: Partner expansion"
    message: Partner expansion has enough evidence to stay in the leadership discussion, but it is not ready to compete with retention for first delivery funding.
    action: Validate the business case before assigning delivery capacity.
    rationaleTitle: Why this is second
    rationale:
      - Has objective and use case alignment
      - Candidate product exists
      - Evidence is inferred, not yet strong enough for first priority
    confidence: medium
    evidenceType: inferred
    evidence:
      - type: businessObjective
        label: Improve partner-led expansion planning
        id: OBJ-PARTNER-EXPANSION
      - type: useCase
        label: Partner expansion planning
        id: UC-PARTNER-EXPANSION
      - type: productReference
        label: Partner performance signals
        id: PR-PARTNER
  blocker:
    label: Risk
    title: "Do not ignore: Signal coverage risk"
    message: Signal coverage looks thin. This may make prioritization look more certain than it is.
    action: Improve signal coverage before using this portfolio view for final prioritization.
    rationaleTitle: Why this matters
    rationale:
      - Weak evidence can distort funding decisions
      - Thin signals reduce confidence
      - Leadership may over-prioritize incomplete paths
    confidence: low
    evidenceType: inferred
    evidence:
      - type: signal
        label: Churn market demand
        id: SIG-CHURN
  readinessCheck:
    label: Readiness check
    title: "Before build starts: Commercial readiness review"
    message: The customer health product still needs human review before production commitment.
    action: Confirm ownership, value model, operating model, and delivery readiness.
    checklist:
      - Business owner confirmed
      - Value model reviewed
      - Delivery owner assigned
      - Operating model clear
      - Production readiness reviewed
    confidence: medium
    evidenceType: inferred
    evidence:
      - type: productReference
        label: Customer health signals
        id: PR-CUSTOMER
swot:
  strengths:
    - id: STR-RETENTION-DEMAND
      statement: Retention has clear objective and use-case pull.
      decisionImplication: Treat retention as the strongest candidate for first delivery funding.
      evidenceRefs:
        - type: businessObjective
          id: OBJ-RETENTION
        - type: useCase
          id: UC-RETENTION
      confidence: high
      inference: false
  weaknesses:
    - id: WEAK-OWNERSHIP-GAP
      statement: Product ownership evidence needs review before delivery commitment.
      decisionImplication: Confirm ownership, value model, and delivery readiness before moving into build.
      evidenceRefs:
        - type: productReference
          id: PR-CUSTOMER
      confidence: medium
      inference: true
  opportunities:
    - id: OPP-RETENTION-REVIEW
      statement: Leadership can use the portfolio to prioritize retention interventions.
      decisionImplication: Validate the next growth case before assigning delivery capacity.
      evidenceRefs:
        - type: signal
          id: SIG-CHURN
      confidence: medium
      inference: true
  threats:
    - id: THREAT-THIN-SIGNALS
      statement: Thin market signal coverage could overstate portfolio confidence.
      decisionImplication: Strengthen signal coverage before using this view for final prioritization.
      evidenceRefs:
        - type: signal
          id: SIG-CHURN
      confidence: low
      inference: true
leadershipDecisions:
  - id: DECIDE-RETENTION-FUNDING
    question: Should leadership fund the retention product as the next delivery priority?
    decisionType: invest
    urgency: high
    evidenceRefs:
      - type: businessObjective
        id: OBJ-RETENTION
      - type: productReference
        id: PR-CUSTOMER
evidenceGaps:
  - id: GAP-OWNER
    statement: Product owner and accountable business sponsor are not explicit.
    evidenceRefs:
      - type: productReference
        id: PR-CUSTOMER
confidenceNotes:
  - Priority items marked as inferred need human review before business action.
leadershipSummary:
  recommendedFirstMove: Fund retention workflow validation
  secondGrowthPath: Validate partner expansion evidence
  mainRisk: Signal coverage may be too thin for prioritization confidence
"""

EXECUTIVE_SUMMARY_DELTA_YAML = """
schema: https://opendataproducts.org/sdk/portfolio-executive-summary/v1
kind: PortfolioExecutiveSummary
metadata:
  generatedAt: "2026-06-28T00:00:00Z"
  generatedBy: open-data-products
  sdkVersion: "0.0.0"
  model: test-model
  workspaceTitle: Generated Demo Portfolio
portfolioPosition:
  headline: Renewal is now a leadership review topic.
  narrative: New renewal evidence changes the portfolio discussion.
priorityBriefing:
  recommendation: Include renewal in the next leadership review after validating the new workflow evidence.
swot:
  strengths:
    - id: STR-RENEWAL-DEMAND
      statement: Renewal has explicit workflow demand.
      evidenceRefs:
        - type: useCase
          id: UC-RENEWAL
      confidence: medium
      inference: false
  weaknesses: []
  opportunities: []
  threats: []
leadershipDecisions:
  - id: DECIDE-RENEWAL
    question: Should leadership include renewal in the next portfolio review?
    decisionType: validate
    urgency: medium
    evidenceRefs:
      - type: useCase
        id: UC-RENEWAL
evidenceGaps: []
confidenceNotes:
  - Delta refresh summary is grounded in changed renewal evidence.
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
    (workspace / "versions" / "2026-06-07T12-30-00Z" / "report.json").write_text(
        json.dumps(
            {
                "kind": "PortfolioRefresh",
                "created": ["odpc/fragments/use_case_UC-RETENTION.yaml"],
                "updated": ["index.html", "odpg/graph.yaml"],
                "unchanged": ["portfolio-state.yaml"],
                "removed": ["old-source.md"],
                "sourceChanges": {
                    "useCases": {
                        "created": ["new-use-case.md"],
                        "updated": [],
                        "removed": [],
                    },
                    "signals": {
                        "created": [],
                        "updated": ["signal.txt"],
                        "removed": [],
                    },
                },
                "artifactCounts": {
                    "businessObjectives": 1,
                    "useCases": 1,
                    "signals": 1,
                    "productReferences": 1,
                    "odpsProducts": 1,
                    "graphEdges": 1,
                },
                "warnings": ["Review generated pricing evidence."],
                "valid": False,
            },
            indent=2,
        )
        + "\n",
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


def write_sample_executive_summary(workspace: Path) -> None:
    """Write a machine-readable executive summary fixture."""
    (workspace / "executive-summary.yaml").write_text(
        EXECUTIVE_SUMMARY_YAML,
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


def _write_minimal_text_pdf(path: Path, lines: list) -> None:
    """Write a tiny PDF-like fixture with embedded text stream operators."""
    escaped_lines = [
        str(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        for line in lines
    ]
    text_operators = "\n".join(f"({line}) Tj" for line in escaped_lines)
    content = f"BT\n/F1 12 Tf\n72 720 Td\n{text_operators}\nET\n"
    payload = "\n".join(
        [
            "%PDF-1.4",
            "1 0 obj",
            f"<< /Length {len(content.encode('latin-1'))} >>",
            "stream",
            content,
            "endstream",
            "endobj",
            "%%EOF",
            "",
        ]
    )
    path.write_bytes(payload.encode("latin-1"))


def _write_minimal_xlsx(path: Path, sheets: list) -> None:
    """Write a tiny XLSX workbook fixture with inline string cells."""
    workbook_sheets = []
    relationships = []
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
</Types>
""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdWorkbook" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
""",
        )
        for index, (name, rows) in enumerate(sheets, start=1):
            workbook_sheets.append(
                f'<sheet name="{_xml_escape(str(name))}" sheetId="{index}" r:id="rId{index}"/>'
            )
            relationships.append(
                f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            )
            archive.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _minimal_xlsx_sheet(rows),
            )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    %s
  </sheets>
</workbook>
""" % "\n    ".join(workbook_sheets),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  %s
</Relationships>
""" % "\n  ".join(relationships),
        )


def _minimal_xlsx_sheet(rows: list) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_xlsx_column_name(column_index)}{row_index}"
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{_xml_escape(str(value))}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
        "  <sheetData>\n"
        f'    {"".join(row_xml)}\n'
        "  </sheetData>\n"
        "</worksheet>\n"
    )


def _xlsx_column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_customer_product_spec(workspace: Path) -> Path:
    """Write an ODPS product spec linked by the staged product reference."""
    product_path = workspace / "odps" / "products" / "customer-product.yaml"
    product_path.parent.mkdir(parents=True, exist_ok=True)
    product_path.write_text(
        """
schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      name: Customer Product
      productID: customer-product
      description: Customer analytics product.
      visibility: internal
      status: production
      type: dataset
""",
        encoding="utf-8",
    )
    return product_path


def test_portfolio_source_helpers_collect_and_compare_lane_changes(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import (
        changed_source_lanes,
        collect_source_lanes,
        source_changes,
        source_change_warnings,
        source_hashes_by_lane,
    )

    sources = tmp_path / "sources"
    write_source_lanes(sources)

    initial_lanes = collect_source_lanes(
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
    )
    previous_state = {"sources": initial_lanes}

    (sources / "use-cases" / "retention.md").write_text(
        "Use case: Retention Workflow with updated renewal handling\n",
        encoding="utf-8",
    )
    (sources / "signals" / "market.txt").unlink()
    (sources / "products" / "orders.json").write_text(
        '{"product": "Orders"}\n',
        encoding="utf-8",
    )
    updated_lanes = collect_source_lanes(
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
    )

    changes = source_changes(previous_state, updated_lanes)
    changed_lanes = changed_source_lanes(updated_lanes, changes)
    retention_id = f"{sources / 'use-cases' / 'retention.md'}#file-1"
    market_id = f"{sources / 'signals' / 'market.txt'}#file-1"
    orders_id = f"{sources / 'products' / 'orders.json'}#file-1"

    assert retention_id in source_hashes_by_lane(previous_state)["useCases"]
    assert changes["lanes"]["useCases"]["updated"] == [
        str(sources / "use-cases" / "retention.md")
    ]
    assert changes["lanes"]["useCases"]["updatedSourceIds"] == [retention_id]
    assert changes["lanes"]["signals"]["removed"] == [
        str(sources / "signals" / "market.txt")
    ]
    assert changes["lanes"]["signals"]["removedSourceIds"] == [market_id]
    assert changes["lanes"]["products"]["created"] == [
        str(sources / "products" / "orders.json")
    ]
    assert changes["lanes"]["products"]["createdSourceIds"] == [orders_id]
    assert changed_lanes["products"][0]["sourceId"] == orders_id
    assert [source["path"] for source in changed_lanes["products"]] == [
        str(sources / "products" / "orders.json")
    ]
    assert source_change_warnings(changes) == [
        f"Source file no longer present: {sources / 'signals' / 'market.txt'}"
    ]


def test_portfolio_source_helpers_extract_eml_and_warn_for_msg_without_extra(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products.portfolio_sources import (
        collect_source_lanes,
        source_extraction_warnings,
    )

    sources = tmp_path / "sources"
    (sources / "use-cases").mkdir(parents=True)
    (sources / "use-cases" / "retention-request.eml").write_text(
        "\r\n".join(
            [
                "Subject: Retention reporting",
                "From: Customer Lead <customer@example.com>",
                "To: Products <products@example.com>",
                "Date: Mon, 01 Jun 2026 10:00:00 +0000",
                "Content-Type: text/plain; charset=utf-8",
                "",
                "Please provide weekly churn reporting by segment.",
            ]
        ),
        encoding="utf-8",
    )
    msg_path = sources / "use-cases" / "outlook-request.msg"
    msg_path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1fake-msg")
    monkeypatch.setitem(sys.modules, "extract_msg", None)

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=sources / "use-cases",
        signals=None,
        products=None,
    )

    use_cases = lanes["useCases"]
    assert [source["path"] for source in use_cases] == [
        str(sources / "use-cases" / "retention-request.eml")
    ]
    assert use_cases[0]["sourceType"] == "eml"
    assert (
        use_cases[0]["sourceId"]
        == f"{sources / 'use-cases' / 'retention-request.eml'}#message-1"
    )
    assert use_cases[0]["sourceUnit"] == "message"
    assert use_cases[0]["title"] == "Retention reporting"
    assert "Please provide weekly churn reporting by segment." in use_cases[0]["text"]
    assert source_extraction_warnings(lanes) == [
        (
            f"Skipped Outlook .msg source {msg_path}: install "
            "open-data-products[email] to enable .msg extraction."
        )
    ]


def test_portfolio_source_helpers_extract_msg_with_email_extra(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products.portfolio_sources import (
        collect_source_lanes,
        source_extraction_warnings,
    )

    class FakeMessage:
        subject = "Outlook retention request"
        sender = "Customer Lead <customer@example.com>"
        to = "Products <products@example.com>"
        date = "2026-06-01 10:00:00+00:00"
        body = "Please include Outlook requests in portfolio intake."

        def __init__(self, path: str) -> None:
            self.path = path

        def close(self) -> None:
            pass

    fake_extract_msg = types.SimpleNamespace(Message=FakeMessage)
    monkeypatch.setitem(sys.modules, "extract_msg", fake_extract_msg)

    sources = tmp_path / "sources"
    (sources / "use-cases").mkdir(parents=True)
    msg_path = sources / "use-cases" / "outlook-request.msg"
    msg_path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1fake-msg")

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=sources / "use-cases",
        signals=None,
        products=None,
    )

    assert source_extraction_warnings(lanes) == []
    use_cases = lanes["useCases"]
    assert len(use_cases) == 1
    assert use_cases[0]["path"] == str(msg_path)
    assert use_cases[0]["sourceType"] == "msg"
    assert use_cases[0]["detectionMethod"] == "ole-compound-header"
    assert use_cases[0]["sourceUnit"] == "message"
    assert use_cases[0]["title"] == "Outlook retention request"
    assert use_cases[0]["sourceId"] == f"{msg_path}#message-1"
    assert "Subject: Outlook retention request" in use_cases[0]["text"]
    assert "From: Customer Lead <customer@example.com>" in use_cases[0]["text"]
    assert "Please include Outlook requests" in use_cases[0]["text"]


def test_portfolio_source_helpers_detect_types_from_content_before_extension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products.portfolio_sources import (
        collect_source_lanes,
        source_extraction_warnings,
    )

    sources = tmp_path / "sources"
    (sources / "use-cases").mkdir(parents=True)
    renamed_eml = sources / "use-cases" / "customer-request.txt"
    renamed_eml.write_text(
        "\r\n".join(
            [
                "Subject: Segment data request",
                "From: Customer <customer@example.com>",
                "Content-Type: text/plain; charset=utf-8",
                "",
                "Can we get a weekly segment extract?",
            ]
        ),
        encoding="utf-8",
    )
    renamed_msg = sources / "use-cases" / "outlook-request.txt"
    renamed_msg.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1fake-msg")
    monkeypatch.setitem(sys.modules, "extract_msg", None)

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=sources / "use-cases",
        signals=None,
        products=None,
    )

    assert [source["path"] for source in lanes["useCases"]] == [str(renamed_eml)]
    assert lanes["useCases"][0]["sourceType"] == "eml"
    assert lanes["useCases"][0]["detectionMethod"] == "rfc822-headers"
    assert lanes["useCases"][0]["title"] == "Segment data request"
    assert source_extraction_warnings(lanes) == [
        (
            f"Skipped Outlook .msg source {renamed_msg}: install "
            "open-data-products[email] to enable .msg extraction."
        )
    ]


def test_portfolio_source_helpers_scan_extensionless_supported_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products.portfolio_sources import (
        collect_source_lanes,
        source_extraction_warnings,
    )

    sources = tmp_path / "sources"
    (sources / "use-cases").mkdir(parents=True)
    msg_path = sources / "use-cases" / "outlook-request"
    msg_path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1fake-msg")
    monkeypatch.setitem(sys.modules, "extract_msg", None)

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=sources / "use-cases",
        signals=None,
        products=None,
    )

    assert lanes["useCases"] == []
    assert source_extraction_warnings(lanes) == [
        (
            f"Skipped Outlook .msg source {msg_path}: install "
            "open-data-products[email] to enable .msg extraction."
        )
    ]


def test_portfolio_source_helpers_detect_ooxml_from_container(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import collect_source_lanes

    sources = tmp_path / "sources"
    (sources / "objectives").mkdir(parents=True)
    (sources / "products").mkdir(parents=True)
    docx_path = sources / "objectives" / "strategy-notes"
    pptx_path = sources / "products" / "product-deck.txt"
    with ZipFile(docx_path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Improve retention</w:t></w:r></w:p>
    <w:p><w:r><w:t>Prioritize churn reporting</w:t></w:r></w:p>
  </w:body>
</w:document>
""",
        )
    with ZipFile(pptx_path, "w") as archive:
        archive.writestr("ppt/presentation.xml", "<p:presentation />")
        archive.writestr(
            "ppt/slides/slide1.xml",
            """
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:t>Customer analytics product</a:t></a:r></a:p></p:txBody></p:sp>
    <p:sp><p:txBody><a:p><a:r><a:t>Weekly segment reporting</a:t></a:r></a:p></p:txBody></p:sp>
  </p:spTree></p:cSld>
</p:sld>
""",
        )
        archive.writestr(
            "ppt/slides/slide2.xml",
            """
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:t>Renewal risk signal</a:t></a:r></a:p></p:txBody></p:sp>
  </p:spTree></p:cSld>
</p:sld>
""",
        )

    lanes = collect_source_lanes(
        objectives=sources / "objectives",
        use_cases=None,
        signals=None,
        products=sources / "products",
    )

    assert lanes["objectives"][0]["sourceType"] == "docx"
    assert lanes["objectives"][0]["sourceId"] == f"{docx_path}#document-1"
    assert lanes["objectives"][0]["detectionMethod"] == "ooxml-container"
    assert "Improve retention" in lanes["objectives"][0]["text"]
    assert "Prioritize churn reporting" in lanes["objectives"][0]["text"]
    assert len(lanes["products"]) == 1
    assert lanes["products"][0]["sourceType"] == "pptx"
    assert lanes["products"][0]["sourceId"] == f"{pptx_path}#deck-1"
    assert lanes["products"][0]["sourceUnit"] == "deck"
    assert lanes["products"][0]["sourceUnitId"] == "1"
    assert lanes["products"][0]["detectionMethod"] == "ooxml-container"
    assert "Slide 1:" in lanes["products"][0]["text"]
    assert "Customer analytics product" in lanes["products"][0]["text"]
    assert "Weekly segment reporting" in lanes["products"][0]["text"]
    assert "Slide 2:" in lanes["products"][0]["text"]
    assert "Renewal risk signal" in lanes["products"][0]["text"]


def test_portfolio_source_helpers_extract_xlsx_as_one_workbook_source(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import collect_source_lanes

    sources = tmp_path / "sources"
    (sources / "products").mkdir(parents=True)
    xlsx_path = sources / "products" / "portfolio-input.xlsx"
    _write_minimal_xlsx(
        xlsx_path,
        [
            (
                "Candidates",
                [
                    ["product", "need"],
                    ["Customer Health", "retention visibility"],
                    ["Renewal Risk", "weekly review"],
                ],
            ),
            (
                "Signals",
                [
                    ["signal", "priority"],
                    ["churn pressure", "high"],
                ],
            ),
        ],
    )

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=None,
        signals=None,
        products=sources / "products",
    )

    assert len(lanes["products"]) == 1
    assert lanes["products"][0]["sourceType"] == "xlsx"
    assert lanes["products"][0]["sourceId"] == f"{xlsx_path}#workbook-1"
    assert lanes["products"][0]["sourceUnit"] == "workbook"
    assert lanes["products"][0]["sourceUnitId"] == "1"
    assert lanes["products"][0]["detectionMethod"] == "ooxml-container"
    text = lanes["products"][0]["text"]
    assert "Sheet: Candidates" in text
    assert "Columns: product, need" in text
    assert "| Customer Health | retention visibility |" in text
    assert "Sheet: Signals" in text
    assert "Columns: signal, priority" in text
    assert "| churn pressure | high |" in text


def test_portfolio_source_helpers_detect_xlsx_from_container_before_extension(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import collect_source_lanes

    sources = tmp_path / "sources"
    (sources / "signals").mkdir(parents=True)
    xlsx_path = sources / "signals" / "signals-table.txt"
    _write_minimal_xlsx(
        xlsx_path,
        [
            (
                "Signals",
                [
                    ["signal", "confidence"],
                    ["renewal risk", "high"],
                ],
            )
        ],
    )

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=None,
        signals=sources / "signals",
        products=None,
    )

    assert len(lanes["signals"]) == 1
    assert lanes["signals"][0]["sourceType"] == "xlsx"
    assert lanes["signals"][0]["detectionMethod"] == "ooxml-container"
    assert lanes["signals"][0]["sourceUnit"] == "workbook"
    assert "| renewal risk | high |" in lanes["signals"][0]["text"]


def test_portfolio_source_helpers_limits_xlsx_rows_per_sheet(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import collect_source_lanes

    sources = tmp_path / "sources"
    (sources / "use-cases").mkdir(parents=True)
    xlsx_path = sources / "use-cases" / "requests.xlsx"
    rows = [["id", "request"]]
    rows.extend([str(index), f"Request {index}"] for index in range(1, 56))
    _write_minimal_xlsx(xlsx_path, [("Requests", rows)])

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=sources / "use-cases",
        signals=None,
        products=None,
    )

    text = lanes["useCases"][0]["text"]
    assert "Sheet: Requests" in text
    assert "Rows: 55" in text
    assert "Rows included: 50" in text
    assert "| 50 | Request 50 |" in text
    assert "Request 51" not in text
    assert "Rows omitted: 5" in text


def test_portfolio_source_helpers_warn_for_png_without_vision(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import (
        collect_source_lanes,
        source_extraction_warnings,
    )

    sources = tmp_path / "sources"
    (sources / "products").mkdir(parents=True)
    image_path = sources / "products" / "whiteboard.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-image")

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=None,
        signals=None,
        products=sources / "products",
    )

    assert lanes["products"] == []
    assert source_extraction_warnings(lanes) == [
        (
            f"Skipped image source {image_path}: OCR or vision extraction "
            "is not enabled."
        )
    ]


def test_portfolio_source_helpers_detect_jpeg_from_content_before_extension(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import (
        collect_source_lanes,
        source_extraction_warnings,
    )

    sources = tmp_path / "sources"
    (sources / "signals").mkdir(parents=True)
    image_path = sources / "signals" / "signal-photo.txt"
    image_path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=None,
        signals=sources / "signals",
        products=None,
    )

    assert lanes["signals"] == []
    assert source_extraction_warnings(lanes) == [
        (
            f"Skipped image source {image_path}: OCR or vision extraction "
            "is not enabled."
        )
    ]


def test_portfolio_source_helpers_extract_text_pdf(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import collect_source_lanes

    sources = tmp_path / "sources"
    (sources / "objectives").mkdir(parents=True)
    pdf_path = sources / "objectives" / "strategy.pdf"
    _write_minimal_text_pdf(
        pdf_path,
        ["Improve retention", "Prioritize churn reporting"],
    )

    lanes = collect_source_lanes(
        objectives=sources / "objectives",
        use_cases=None,
        signals=None,
        products=None,
    )

    assert len(lanes["objectives"]) == 1
    assert lanes["objectives"][0]["sourceType"] == "pdf"
    assert lanes["objectives"][0]["sourceId"] == f"{pdf_path}#document-1"
    assert lanes["objectives"][0]["sourceUnit"] == "document"
    assert lanes["objectives"][0]["sourceUnitId"] == "1"
    assert lanes["objectives"][0]["detectionMethod"] == "pdf-header"
    assert "Improve retention" in lanes["objectives"][0]["text"]
    assert "Prioritize churn reporting" in lanes["objectives"][0]["text"]


def test_portfolio_source_helpers_warn_for_image_only_pdf(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import (
        collect_source_lanes,
        source_extraction_warnings,
    )

    sources = tmp_path / "sources"
    (sources / "signals").mkdir(parents=True)
    pdf_path = sources / "signals" / "scan.pdf"
    _write_minimal_text_pdf(pdf_path, [])

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=None,
        signals=sources / "signals",
        products=None,
    )

    assert lanes["signals"] == []
    assert source_extraction_warnings(lanes) == [
        (
            f"Skipped PDF source {pdf_path}: no embedded text found; "
            "OCR or vision extraction is not enabled."
        )
    ]


def test_portfolio_source_helpers_detect_pdf_from_content_before_extension(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import collect_source_lanes

    sources = tmp_path / "sources"
    (sources / "products").mkdir(parents=True)
    pdf_path = sources / "products" / "product-brief.txt"
    _write_minimal_text_pdf(pdf_path, ["Customer analytics product"])

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=None,
        signals=None,
        products=sources / "products",
    )

    assert len(lanes["products"]) == 1
    assert lanes["products"][0]["sourceType"] == "pdf"
    assert lanes["products"][0]["detectionMethod"] == "pdf-header"
    assert "Customer analytics product" in lanes["products"][0]["text"]


def test_portfolio_intake_zip_fixture_matches_embedded_expectations(
    tmp_path: Path,
) -> None:
    fixture_zip = Path(__file__).with_name("intake-test-1.zip")
    with ZipFile(fixture_zip) as archive:
        archive.extractall(tmp_path)

    fixture_root = tmp_path / "sdk-intake-test-materials"
    assertions = json.loads(
        (
            fixture_root / "expected-output-checks" / "suggested_assertions.json"
        ).read_text(encoding="utf-8")
    )

    result = inspect_portfolio_intake(
        objectives=fixture_root / "sources" / "objectives",
        use_cases=fixture_root / "sources" / "use-cases",
        signals=fixture_root / "sources" / "signals",
        products=fixture_root / "sources" / "products",
    )

    sources = result["sources"]
    assert isinstance(sources, list)
    source_by_name = {Path(str(source["path"])).name: source for source in sources}
    source_types = {str(source["sourceType"]) for source in sources}

    assert set(assertions["must_extract_types"]).issubset(source_types)
    lane_names = {"use-cases": "useCases"}
    for lane, filenames in assertions["lane_expectations"].items():
        report_lane = lane_names.get(lane, lane)
        lane_sources = {
            Path(str(source["path"])).name
            for source in sources
            if source["lane"] == report_lane
        }
        assert set(filenames).issubset(lane_sources)

    text_pdf = source_by_name["board-objectives-text-pdf.pdf"]
    assert text_pdf["sourceType"] == "pdf"
    assert text_pdf["detectionMethod"] == "pdf-header"
    assert text_pdf["status"] == "included"

    renamed_deck = source_by_name["strategy-priorities-no-extension"]
    assert renamed_deck["sourceType"] == "pptx"
    assert renamed_deck["detectionMethod"] == "ooxml-container"
    assert renamed_deck["sourceUnit"] == "deck"

    warnings = "\n".join(str(item) for item in result["warnings"])
    assert "misleading-office-file.docx" in warnings
    assert "outlook-request.msg" in warnings
    assert "scanned-kpi-note-image-only.pdf" in warnings
    assert "product-whiteboard.jpg" in warnings
    assert "product-sketch.png" in warnings
    assert "board-objectives-text-pdf.pdf" not in warnings
    assert result["sourceExtraction"]["skippedSourceCount"] == 5
    assert result["llmCallCount"] == 0


def test_portfolio_long_content_zip_fixture_matches_embedded_expectations(
    tmp_path: Path,
) -> None:
    fixture_zip = Path(__file__).with_name("intake-test-2.zip")
    with ZipFile(fixture_zip) as archive:
        archive.extractall(tmp_path)

    fixture_root = tmp_path / "sdk-long-content-test-materials"
    assertions = json.loads(
        (
            fixture_root / "expected-output-checks" / "suggested_assertions.json"
        ).read_text(encoding="utf-8")
    )

    result = inspect_portfolio_intake(
        objectives=fixture_root / "sources" / "objectives",
        use_cases=fixture_root / "sources" / "use-cases",
        signals=fixture_root / "sources" / "signals",
        products=fixture_root / "sources" / "products",
    )

    sources = result["sources"]
    assert isinstance(sources, list)
    source_by_name = {Path(str(source["path"])).name: source for source in sources}
    lanes = {str(source["lane"]) for source in sources}

    assert result["llmCallCount"] == 0
    assert result["sourceExtraction"]["skippedSourceCount"] == 0
    assert result["sourceBudget"]["method"] == "deterministic-chunk-budget"
    assert result["sourceBudget"]["estimatedInputChars"] > 200000
    assert (
        result["sourceBudget"]["chunkCount"]
        > result["sourceBudget"]["includedChunkCount"]
    )
    assert result["sourceBudget"]["omittedChunkCount"] > 0
    assert result["sourceBudget"]["reducedSourceCount"] > 0
    assert result["sourcePrivacy"]["enabled"] is True
    assert result["sourcePrivacy"]["replacementCounts"]["email"] > 0
    assert "Personal data obfuscation is best effort" in "\n".join(
        str(item) for item in result["warnings"]
    )

    assert {"objectives", "useCases", "signals", "products"}.issubset(lanes)
    assert "lose_lane_assignment" in assertions["must_not"]
    assert "drop_source_path_metadata" in assertions["must_not"]
    assert all(source["path"] for source in sources)

    long_strategy = source_by_name["long-strategy-document-with-headings.docx"]
    assert long_strategy["sourceType"] == "docx"
    assert long_strategy["detectionMethod"] == "ooxml-container"
    assert long_strategy["chunkCount"] > long_strategy["includedChunkCount"]
    assert long_strategy["omittedChunkCount"] > 0
    assert long_strategy["status"] == "reduced"

    email_thread = source_by_name["long-email-thread-with-quoted-history.eml"]
    assert email_thread["sourceType"] == "eml"
    assert email_thread["detectionMethod"] == "rfc822-headers"
    assert email_thread["chunkCount"] > email_thread["includedChunkCount"]
    assert email_thread["omittedChunkCount"] > 0

    transcript = source_by_name["very-long-teams-transcript.txt"]
    assert transcript["sourceType"] == "txt"
    assert transcript["detectionMethod"] == "extension"
    assert transcript["chunkCount"] > 1

    many_small_notes = [
        source
        for source in sources
        if Path(str(source["path"])).name.startswith("use-case-note-")
    ]
    assert len(many_small_notes) == 40
    assert all(source["status"] == "included" for source in many_small_notes)


def test_portfolio_edge_case_zip_fixture_matches_embedded_expectations(
    tmp_path: Path,
) -> None:
    fixture_zip = Path(__file__).with_name("intake-test-3.zip")
    with ZipFile(fixture_zip) as archive:
        archive.extractall(tmp_path)

    fixture_root = tmp_path / "sdk-edge-case-test-materials"
    assertions = json.loads(
        (
            fixture_root / "expected-output-checks" / "suggested_assertions.json"
        ).read_text(encoding="utf-8")
    )

    result = inspect_portfolio_intake(
        objectives=fixture_root / "sources" / "objectives",
        use_cases=fixture_root / "sources" / "use-cases",
        signals=fixture_root / "sources" / "signals",
        products=fixture_root / "sources" / "products",
    )

    sources = result["sources"]
    assert isinstance(sources, list)
    source_by_name = {Path(str(source["path"])).name: source for source in sources}
    warnings = "\n".join(str(item) for item in result["warnings"])
    skipped_sources = result["sourceExtraction"]["skippedSources"]
    skipped_by_name = {
        Path(str(source["path"])).name: source for source in skipped_sources
    }

    assert result["llmCallCount"] == 0
    assert result["sourceExtraction"]["skippedSourceCount"] == 7
    assert (
        "All warnings appear in default --json output."
        in assertions["high_value_assertions"]
    )
    assert all(source["path"] for source in skipped_sources)
    assert all(source["warning"] for source in skipped_sources)

    latin1 = source_by_name["latin1-customer-objective.txt"]
    assert "Café objective" in latin1["preview"]
    assert latin1["status"] == "included"

    bom = source_by_name["UTF8-BOM-strategy-notes.md"]
    assert not bom["preview"].startswith("\ufeff")

    control_chars = source_by_name["control-chars.txt"]
    assert "\x00" not in control_chars["preview"]
    assert "\x07" not in control_chars["preview"]

    multilingual = source_by_name["arabic-vietnamese-finnish.md"]
    assert "تحسين جودة الخدمات الحكومية" in multilingual["preview"]
    assert "Nâng cao khả năng phát hiện nhu cầu dữ liệu" in multilingual["preview"]
    assert "Päätöksenteko tarvitsee parempaa tilannekuvaa" in multilingual["preview"]

    assert source_by_name["duplicate-content.md"]["lane"] == "products"
    assert any(
        source["lane"] == "objectives"
        for source in sources
        if Path(str(source["path"])).name == "duplicate-content.md"
    )
    assert "nested-product-note.md" in source_by_name
    assert source_by_name["nested-product-note.md"]["lane"] == "products"

    semicolon_csv = source_by_name["semicolon-latin1.csv"]
    assert "Columns: kpi, description, owner" in semicolon_csv["preview"]

    assert "corrupt-office-container.docx" in skipped_by_name
    assert "corrupt-workbook.xlsx" in skipped_by_name
    assert "corrupt-presentation.pptx" in skipped_by_name
    assert "realistic-outlook-placeholder.msg" in skipped_by_name
    assert "image-only-signal.pdf" in skipped_by_name
    assert "password-protected.pdf" in skipped_by_name
    assert "zero-byte.pdf" in skipped_by_name
    assert "pdf-bytes-named-docx.docx" not in skipped_by_name
    assert source_by_name["pdf-bytes-named-docx.docx"]["sourceType"] == "pdf"
    assert (
        source_by_name["pdf-bytes-named-docx.docx"]["detectionMethod"] == "pdf-header"
    )

    hidden_sensitive_text = "hidden sensitive"
    combined_preview = "\n".join(str(source["preview"]) for source in sources)
    assert hidden_sensitive_text not in combined_preview.lower()
    assert "HEADER SHOULD NOT BE EXTRACTED" not in combined_preview
    assert "FOOTER SHOULD NOT BE EXTRACTED" not in combined_preview
    assert "ATTACHMENT SHOULD NOT BE EXTRACTED" not in combined_preview
    assert "OCR_ONLY_SLIDE_TEXT" not in combined_preview
    assert "Skipped" in warnings


def test_portfolio_source_helpers_extract_csv_as_one_source_record(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import collect_source_lanes

    sources = tmp_path / "sources"
    (sources / "signals").mkdir(parents=True)
    csv_path = sources / "signals" / "churn-signals.csv"
    csv_path.write_text(
        "segment,churn_rate,priority\n"
        "enterprise,0.12,high\n"
        "midmarket,0.08,medium\n",
        encoding="utf-8",
    )

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=None,
        signals=sources / "signals",
        products=None,
    )

    assert len(lanes["signals"]) == 1
    assert lanes["signals"][0]["sourceType"] == "csv"
    assert lanes["signals"][0]["sourceId"] == f"{csv_path}#table-1"
    assert lanes["signals"][0]["sourceUnit"] == "table"
    assert lanes["signals"][0]["sourceUnitId"] == "1"
    assert lanes["signals"][0]["detectionMethod"] == "csv-sniffer"
    assert "Columns: segment, churn_rate, priority" in lanes["signals"][0]["text"]
    assert "| enterprise | 0.12 | high |" in lanes["signals"][0]["text"]
    assert "| midmarket | 0.08 | medium |" in lanes["signals"][0]["text"]


def test_portfolio_source_helpers_detect_csv_from_content_before_extension(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import collect_source_lanes

    sources = tmp_path / "sources"
    (sources / "products").mkdir(parents=True)
    csv_path = sources / "products" / "product-candidates.txt"
    csv_path.write_text(
        "product,need\n" "Customer Health,retention visibility\n",
        encoding="utf-8",
    )

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=None,
        signals=None,
        products=sources / "products",
    )

    assert len(lanes["products"]) == 1
    assert lanes["products"][0]["sourceType"] == "csv"
    assert lanes["products"][0]["detectionMethod"] == "csv-sniffer"
    assert lanes["products"][0]["sourceUnit"] == "table"
    assert "| Customer Health | retention visibility |" in lanes["products"][0]["text"]


def test_portfolio_source_helpers_limits_csv_rows_in_source_text(
    tmp_path: Path,
) -> None:
    from open_data_products.portfolio_sources import collect_source_lanes

    sources = tmp_path / "sources"
    (sources / "use-cases").mkdir(parents=True)
    csv_path = sources / "use-cases" / "requests.csv"
    rows = ["id,request"]
    rows.extend(f"{index},Request {index}" for index in range(1, 56))
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    lanes = collect_source_lanes(
        objectives=None,
        use_cases=sources / "use-cases",
        signals=None,
        products=None,
    )

    text = lanes["useCases"][0]["text"]
    assert "Rows: 55" in text
    assert "Rows included: 50" in text
    assert "| 50 | Request 50 |" in text
    assert "Request 51" not in text
    assert "Rows omitted: 5" in text


def _is_executive_summary_prompt(prompt: str) -> bool:
    return prompt.startswith("# Create Portfolio Executive Summary")


def fake_portfolio_client(prompt: str, model: str) -> str:
    """Return deterministic staged portfolio generation outputs."""
    return staged_portfolio_client(prompt, model)


def staged_portfolio_client(prompt: str, model: str) -> str:
    """Return one fragment per source document, then graph edges and summary."""
    assert model == "test-model"
    assert not prompt.startswith("Create one Open Data Products portfolio plan")
    if prompt.startswith("# Generate ODPC Business Objective"):
        assert "retention-objective.md" in prompt
        return """businessObjectives:
- id: OBJ-RETENTION
  name:
    en: Improve Retention
  description:
    en: Reduce customer churn.
  status: active
  priority: high
"""
    if prompt.startswith("# Generate ODPC Use Case"):
        if "Renewal Save Workflow" in prompt:
            return """useCases:
- id: UC-RENEWAL
  name:
    en: Renewal Save Workflow
  description:
    en: Help teams act on renewal risk.
  status: active
  priority: high
"""
        assert "retention.md" in prompt
        return """useCases:
- id: UC-RETENTION
  name:
    en: Retention Workflow
  description:
    en: Help teams intervene before churn.
  status: active
  priority: high
"""
    if prompt.startswith("# Generate ODPC Signal"):
        if "regional retention pressure is rising" in prompt:
            return """signals:
- id: regional-retention-pressure
  name:
    en: Regional Retention Pressure
  description:
    en: Regional retention pressure is rising.
  type: market
  confidence: medium
  source:
    origin: internal
    method: regional signal note
  observedAt: "2026-05-20T00:00:00Z"
"""
        if "priority accounts" in prompt:
            return """signals:
- id: daily-retention-briefing
  name:
    en: Daily Retention Briefing
  description:
    en: Product usage is down, support tickets are up, and renewal activity has slowed for several priority accounts.
  type: operational
  confidence: medium
  source:
    origin: internal
    method: account briefing
  observedAt: "2026-05-20T00:00:00Z"
"""
        assert "market.txt" in prompt
        return """signals:
- id: churn-signal
  name:
    en: Churn Signal
  description:
    en: Market signal for retention risk.
  type: market
  confidence: high
  source:
    origin: internal
    method: market note
  observedAt: "2026-05-20T00:00:00Z"
"""
    if prompt.startswith("# Generate ODPS Data Product"):
        assert "customer.md" in prompt
        return """productReferences:
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
"""
    if prompt.startswith("# Extract ODPS Product Facts"):
        assert "customer.md" in prompt
        return """product:
  productID: customer-health-signals
  name: Customer Product
  description: Customer analytics product.
  visibility: organisation
  status: production
  type: dataset
evidenceGaps: []
"""
    if prompt.startswith("# Generate Minimal ODPS Product YAML"):
        return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      productID: customer-health-signals
      name: Customer Product
      description: Customer analytics product.
      visibility: organisation
      status: production
      type: dataset
      valueProposition: Customer analytics product.
"""
    if prompt.startswith("# Draft ODPS Product Components"):
        return """components:
  SLA:
    declarative:
      default:
        name:
          en: Default SLA
        dimensions:
          - dimension: uptime
            objective: 99
            unit: percent
  dataQuality:
    declarative:
      default:
        dimensions:
          - dimension: completeness
            objective: 95
            unit: percentage
  pricingPlans:
    declarative:
      en:
        - name: Internal Review
          priceCurrency: XXX
          price: "0"
          billingDuration: month
          unit: On-request
  dataAccess:
    API:
      outputPortType: API
      format: JSON
      authenticationMethod: OAuth
  license:
    scope:
      definition: Internal use.
      restrictions: No external redistribution.
      geographicalArea:
        - EU
      permanent: false
      exclusive: false
      rights:
        - Display
    termination:
      noticePeriod: 30
      terminationConditions: Access ends when approved use ends.
    governance:
      ownership: Business owner governs use.
      audit: Access reviewed periodically.
draftedComponents:
  - SLA
  - dataQuality
  - pricingPlans
  - dataAccess
  - license
reviewNotes: []
evidenceGaps: []
"""
    if prompt.startswith("# Assemble ODPS Product YAML"):
        return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      productID: customer-health-signals
      name: Customer Product
      description: Customer analytics product.
      visibility: organisation
      status: production
      type: dataset
      valueProposition: Customer analytics product.
  SLA:
    declarative:
      default:
        name:
          en: Default SLA
        dimensions:
          - dimension: uptime
            objective: 99
            unit: percent
  dataQuality:
    declarative:
      default:
        dimensions:
          - dimension: completeness
            objective: 95
            unit: percentage
  pricingPlans:
    declarative:
      en:
        - name: Internal Review
          priceCurrency: XXX
          price: "0"
          billingDuration: month
          unit: On-request
  dataAccess:
    API:
      outputPortType: API
      format: JSON
      authenticationMethod: OAuth
  license:
    scope:
      definition: Internal use.
      restrictions: No external redistribution.
      geographicalArea:
        - EU
      permanent: false
      exclusive: false
      rights:
        - Display
    termination:
      noticePeriod: 30
      terminationConditions: Access ends when approved use ends.
    governance:
      ownership: Business owner governs use.
      audit: Access reviewed periodically.
"""
    if prompt.startswith("# Infer ODPG Edges"):
        assert "OBJ-RETENTION" in prompt
        assert "UC-RETENTION" in prompt
        assert "churn-signal" in prompt
        assert "PR-CUSTOMER" in prompt
        assert "Business objective: Reduce churn risk" not in prompt
        if "UC-RENEWAL" in prompt:
            return """edges:
- from: UC-RETENTION
  to: PR-CUSTOMER
  type: uses
  confidence: high
- from: UC-RENEWAL
  to: PR-CUSTOMER
  type: uses
  confidence: medium
"""
        return """edges:
- from: UC-RETENTION
  to: PR-CUSTOMER
  type: uses
  confidence: high
"""
    if _is_executive_summary_prompt(prompt):
        assert "Normalized portfolio evidence:" in prompt
        assert "UC-RETENTION" in prompt
        assert "Business objective: Reduce churn risk" not in prompt
        if "Renewal Save Workflow" in prompt:
            return EXECUTIVE_SUMMARY_DELTA_YAML
        return EXECUTIVE_SUMMARY_YAML
    raise AssertionError(f"unexpected prompt: {prompt[:120]}")


def drifting_portfolio_client(prompt: str, model: str) -> str:
    """Return drifted IDs once the added renewal source is present."""
    return staged_portfolio_client(prompt, model)


def schema_drift_portfolio_client(prompt: str, model: str) -> str:
    """Return a plan with common LLM enum and relationship drift."""
    return staged_portfolio_client(prompt, model)


def repairable_portfolio_client(prompt: str, model: str) -> str:
    """Return malformed YAML first, then a repaired portfolio plan."""
    return staged_portfolio_client(prompt, model)


def repairable_executive_summary_client(prompt: str, model: str) -> str:
    """Return malformed Executive Summary YAML, then a repaired summary."""
    assert model == "test-model"
    if _is_executive_summary_prompt(prompt):
        return """
schema: https://opendataproducts.org/sdk/portfolio-executive-summary/v1
kind: PortfolioExecutiveSummary
portfolioPosition:
  headline: "Broken summary
  narrative: Broken summary.
priorityBriefing:
  recommendation: Review the portfolio.
  primaryFocus:
    label: Priority 1
"""
    if prompt.startswith("# Repair Portfolio Executive Summary YAML"):
        assert "Executive Summary YAML could not be parsed" in prompt
        assert "Malformed executive summary YAML:" in prompt
        return EXECUTIVE_SUMMARY_YAML
    return staged_portfolio_client(prompt, model)


def delta_portfolio_client(prompt: str, model: str) -> str:
    """Return only artifacts derived from a new source document."""
    return staged_portfolio_client(prompt, model)


def full_refresh_portfolio_client(prompt: str, model: str) -> str:
    """Assert all source documents are included in a forced full refresh."""
    return staged_portfolio_client(prompt, model)


def collapsed_signal_portfolio_client(prompt: str, model: str) -> str:
    """Return no new signal even though the changed signal source is present."""
    return staged_portfolio_client(prompt, model)


def renamed_signal_portfolio_client(prompt: str, model: str) -> str:
    """Return a renamed signal derived from the changed signal source."""
    return staged_portfolio_client(prompt, model)


def overbroad_signal_delta_portfolio_client(prompt: str, model: str) -> str:
    """Return portfolio-wide objects even though only one signal changed."""
    return staged_portfolio_client(prompt, model)


def fake_localization_client(prompt: str, model: str) -> str:
    """Return deterministic localized HTML string bundles."""
    assert model == "test-model"
    assert prompt.startswith("# Localize Portfolio HTML")
    assert (
        "Do not translate IDs, file paths, URLs, YAML keys, or enum values." in prompt
    )
    if "Target language: fi" in prompt:
        return """
language: fi
translations:
  Data Products Portfolio: Datatuotteiden portfolio
  Generated workspace summary: Luodun työtilan yhteenveto
  Executive Summary: Johdon yhteenveto
  Overview: Yleiskatsaus
  Products: Tuotteet
  Customer Product: Asiakastuote
  Full product details from product discussions.: Tuotekeskusteluista johdetut täydet tuotetiedot.
"""
    if "Target language: sv" in prompt:
        return """
language: sv
translations:
  Data Products Portfolio: Dataproduktportfölj
  Generated workspace summary: Sammanfattning av skapad arbetsyta
  Executive Summary: Ledningssammanfattning
  Overview: Översikt
  Products: Produkter
  Customer Product: Kundprodukt
  Full product details from product discussions.: Fullständiga produktdetaljer från produktdiskussioner.
"""
    if "Target language: ar" in prompt:
        return """
language: ar
translations:
  Data Products Portfolio: محفظة منتجات البيانات
  Generated workspace summary: ملخص مساحة العمل المنشأة
  Executive Summary: الملخص التنفيذي
  Overview: نظرة عامة
  Products: المنتجات
  Customer Product: منتج العملاء
  Full product details from product discussions.: تفاصيل المنتج الكاملة المستخلصة من مناقشات المنتج.
"""
    raise AssertionError(prompt)


def repairable_localization_client(prompt: str, model: str) -> str:
    """Return malformed localization YAML first, then repaired translations."""
    assert model == "test-model"
    if prompt.startswith("# Repair Portfolio Localization YAML"):
        assert "mapping values are not allowed here" in prompt
        return """
language: fi
translations:
  Data Products Portfolio: Datatuotteiden portfolio
  Products: Tuotteet
  Customer Product: Asiakastuote
  "This portfolio was generated with the Open Data Products SDK and is grounded in the OpenDataProducts.org standards family: ODPC for catalog objects, ODPS for product specifications, ODPG for graph relationships, and ODPV for shared vocabulary where used.": "Tämä portfolio luotiin Open Data Products SDK:lla ja perustuu OpenDataProducts.org-standardiperheeseen: ODPC luettelokohteille, ODPS tuotemäärityksille, ODPG graafisuhteille ja ODPV sanastolle, kun sitä käytetään."
"""
    assert prompt.startswith("# Localize Portfolio HTML")
    return """
language: fi
translations:
  Data Products Portfolio: Datatuotteiden portfolio
  Products: Tuotteet
  Customer Product: Asiakastuote
  This portfolio was generated with the Open Data Products SDK and is grounded in the OpenDataProducts.org standards family: ODPC for catalog objects, ODPS for product specifications, ODPG for graph relationships, and ODPV for shared vocabulary where used.: Tämä portfolio luotiin Open Data Products SDK:lla ja perustuu OpenDataProducts.org-standardiperheeseen: ODPC luettelokohteille, ODPS tuotemäärityksille, ODPG graafisuhteille ja ODPV sanastolle, kun sitä käytetään.
"""


def test_chunk_localization_strings_keeps_translation_batches_small() -> None:
    chunks = _chunk_localization_strings(
        [
            "Short one",
            "Short two",
            "Long translated text should start a new batch",
            "Short three",
        ],
        max_chars=32,
        max_items=2,
    )

    assert chunks == [
        ["Short one", "Short two"],
        ["Long translated text should start a new batch"],
        ["Short three"],
    ]


def test_render_portfolio_creates_missing_parent_and_artifact_detail_views(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)
    write_sample_executive_summary(workspace)
    output = tmp_path / "deep" / "browser" / "index.html"

    result = render_portfolio(workspace, output_path=output)

    html = output.read_text(encoding="utf-8")
    assert result["html"] == str(output)
    assert "validationResults" in result
    assert "catalog" in result["validationResults"]
    assert "graph" in result["validationResults"]
    assert "products" in result["validationResults"]
    icon_dir = output.parent / "assets" / "executive_summary_icons"
    assert (icon_dir / "priority_1_trophy.png").exists()
    assert (icon_dir / "priority_2_growth.png").exists()
    assert (icon_dir / "risk_warning.png").exists()
    assert (icon_dir / "readiness_clipboard.png").exists()
    assert str(icon_dir / "priority_1_trophy.png") in result["created"]
    assert 'aria-label="Data products portfolio">Data Products Portfolio</a>' in html
    assert (
        'aria-label="Open Data Products portfolio">Open Data Products Portfolio</a>'
        not in html
    )
    assert "Business Objectives" in html
    objective_section = html[
        html.index(
            '<section class="tab-panel objectives-panel" id="objectives">'
        ) : html.index('<section class="tab-panel use-cases-panel" id="use-cases">')
    ]
    assert "Improve Retention" in objective_section
    assert "OBJ-RETENTION" not in objective_section
    assert "Use Cases" in html
    assert "Signals" in html
    assert "Products" in html
    assert "Graph" in html
    assert "About" in html
    assert "Executive Summary" in html
    assert 'id="tab-overview"' in html
    assert 'id="tab-executive-summary"' in html
    assert 'for="tab-executive-summary"' in html
    assert 'class="tab-panel executive-summary-panel"' in html
    assert 'for="tab-graph"' in html
    assert 'class="tab-panel graph-panel"' in html
    assert "Retention is the strongest near-term leadership topic." in html
    assert "executive-dashboard-intro" in html
    assert "Recommended decision" in html
    assert (
        "Fund retention workflow validation first. Validate partner expansion next. "
        "Strengthen signal coverage before final prioritization." in html
    )
    assert "decision-card-grid" in html
    assert 'src="assets/executive_summary_icons/priority_1_trophy.png"' in html
    assert 'src="assets/executive_summary_icons/priority_2_growth.png"' in html
    assert 'src="assets/executive_summary_icons/risk_warning.png"' in html
    assert 'src="assets/executive_summary_icons/readiness_clipboard.png"' in html
    assert '<span class="decision-card-icon" aria-hidden="true"><img' in html
    assert "Priority 1" in html
    assert "Retention validation" in html
    assert "Retention is the strongest first funding candidate." in html
    assert "Fund validation first." in html
    assert 'class="metadata-badge confidence-badge confidence-high"' in html
    assert 'class="status-dot"' in html
    assert 'class="metadata-badge evidence-badge evidence-direct"' in html
    assert "High" in html
    assert "Direct" in html
    assert "Priority 2" in html
    assert "Partner expansion" in html
    assert "Partner expansion is promising but not yet first priority." in html
    assert "Validate the business case next." in html
    assert 'class="metadata-badge confidence-badge confidence-medium"' in html
    assert 'class="metadata-badge evidence-badge evidence-inferred"' in html
    assert "Medium" in html
    assert "Inferred" in html
    assert "Risk" in html
    assert "Signal coverage" in html
    assert "Thin signal coverage may overstate prioritization confidence." in html
    assert "Improve coverage before final prioritization." in html
    assert 'class="metadata-badge confidence-badge confidence-low"' in html
    assert "Low" in html
    assert "Readiness" in html
    assert "Commercial review" in html
    assert "The product still needs business readiness review." in html
    assert "Confirm readiness before build." in html
    assert "Leadership decisions" in html
    assert "Should leadership fund the retention product" in html
    assert "What needs attention" not in html
    assert "Where to invest next" not in html
    assert "What could block progress" not in html
    assert "What is working" not in html
    assert "Strengths" not in html
    assert "Weaknesses" not in html
    assert "Opportunities" not in html
    assert "Threats" not in html
    assert "Decision implication" not in html
    assert (
        "Treat retention as the strongest candidate for first delivery funding."
        not in html
    )
    assert "executive-meta" not in html
    assert "Basis</span>" not in html
    assert "Confidence: High · Evidence: Direct" not in html
    assert "Confidence: Medium · Evidence: Inferred" not in html
    assert "Confidence: Low · Evidence: Inferred" not in html
    assert "Objective: Reduce preventable churn" in html
    assert "Use case: Retention risk workflow" in html
    assert "Candidate product: Customer health signals" in html
    assert "Objective: Improve partner-led expansion planning" in html
    assert "Use case: Partner expansion planning" in html
    assert "Candidate product: Partner performance signals" in html
    assert "Signal: Churn market demand" in html
    assert "Evidence gaps" in html
    assert "Confidence notes" in html
    first_card = html.split('<article class="decision-card primary-focus">', 1)[
        1
    ].split("</article>", 1)[0]
    visible_first_card = first_card.split('<div class="decision-details-dropdown">', 1)[
        0
    ]
    assert "Why this is first" not in visible_first_card
    assert "Objective: Reduce preventable churn" not in visible_first_card
    assert "OBJ-RETENTION" not in visible_first_card
    assert "Show more" in html
    assert "Show less" in html
    assert "Show details" not in html
    assert "Technical evidence" in html
    assert "OBJ-RETENTION" in html
    assert "Inference" not in html
    assert "swot-grid" not in html
    assert "leadership-summary-bar" not in html
    assert "--space-1: 4px;" in html
    assert "--space-6: 24px;" in html
    assert "--space-16: 64px;" in html
    intro_css = html.split(".executive-dashboard-intro {", 1)[1].split("}", 1)[0]
    assert "padding: var(--space-8);" in intro_css
    assert "margin-bottom: var(--space-6);" in intro_css
    recommendation_css = html.split(".leadership-recommendation {", 1)[1].split("}", 1)[
        0
    ]
    assert "padding: var(--space-6);" in recommendation_css
    assert "margin: 0 0 var(--space-8);" in recommendation_css
    dashboard_css = html.split(".decision-card-grid {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in dashboard_css
    assert "align-items: start;" in dashboard_css
    assert "gap: var(--space-8);" in dashboard_css
    secondary_css = html.split(".secondary-focus {", 1)[1].split("}", 1)[0]
    assert "border-top-color: #3b82f6;" in secondary_css
    assert "border-top-color: #0f766e;" not in secondary_css
    assert ".metadata-badge {" in html
    assert ".confidence-high .status-dot" in html
    assert ".confidence-medium .status-dot" in html
    assert ".confidence-low .status-dot" in html
    assert ".decision-details-label-open" in html
    assert ".decision-details-toggle:checked ~ .decision-card-footer" in html
    assert ".decision-details-dropdown" in html
    assert 'class="decision-details-toggle"' in first_card
    assert '<label class="decision-details-trigger"' in first_card
    assert first_card.index('<div class="decision-card-footer">') < first_card.index(
        '<div class="decision-details-dropdown">'
    )
    footer_html = first_card.split('<div class="decision-card-footer">', 1)[1].split(
        '<div class="decision-details-dropdown">', 1
    )[0]
    assert '<label class="decision-details-trigger"' in footer_html
    assert "decision-details-dropdown" not in footer_html
    assert "Recommended next actions" in html
    assert "Suggested follow-ups are derived from warnings" not in html
    assert "What changed since last version" in html
    assert "Portfolio changes" not in html
    assert (
        '<section class="overview-section" aria-label="What changed since last version">'
        in html
    )
    assert "Latest portfolio snapshot" in html
    assert "PortfolioRefresh" in html
    assert "1 artifact was created." in html
    assert "2 artifacts were updated." in html
    assert "1 artifact was removed." in html
    assert "New use case source evidence was added." in html
    assert "Signal source evidence was updated." in html
    assert "Validation needs review" in html
    assert "Portfolio versions" in html
    assert "Portfolio status" not in html
    assert (
        '<section class="overview-section" aria-label="Portfolio status">' not in html
    )
    assert '<section class="overview-section" aria-label="Portfolio versions">' in html
    assert '<div class="overview-card-grid">' in html
    assert 'class="action-card overview-card versions-card"' in html
    assert ".overview-section {" in html
    assert "margin-top: var(--space-8);" in html
    assert "Show all" in html
    assert "table-layout: fixed" in html
    assert "overflow-wrap: anywhere" in html
    assert 'class="graph-explorer-frame"' in html
    assert "This tab embeds the generated ODPG graph explorer" not in html
    assert "vis-network@9.1.9" in html
    assert "new vis.Network" in html
    assert "workspace-main" in html
    assert "filter-panel" in html
    assert ".topbar{display:none!important;}" in html
    assert "id=&quot;btn-fullscreen-canvas&quot;" in html
    assert "aria-label=&quot;Fullscreen graph workspace&quot;" in html
    assert (
        "const fullscreenTarget = document.querySelector(&quot;.workspace&quot;);"
        in html
    )
    assert "fullscreenTarget.requestFullscreen()" in html
    assert "Open Data Product Graphs Explorer" not in html
    assert "<footer" in html
    assert "Draft portfolio generated with the Data Products SDK." in html
    assert "Review status" in html
    assert "Next actions" in html
    assert "Evidence" in html
    assert "Artifacts" in html
    assert "Human acceptance required" in html
    assert "Review executive decisions" in html
    assert "Resolve evidence gaps" in html
    assert "Approve product specs" in html
    assert "Compare previous snapshot" in html
    assert "Portfolio versions" in html
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


def test_render_portfolio_shows_missing_executive_summary_state(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)

    render_portfolio(workspace)

    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "Executive Summary" in html
    assert "executive-summary.yaml" in html
    assert "Executive summary has not been generated" in html
    assert "Strengths" not in html


def test_explain_portfolio_reports_counts_and_browser_entrypoint(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "portfolio"
    write_sample_workspace(workspace)
    write_sample_executive_summary(workspace)
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
    assert summary["hasExecutiveSummary"] is True
    assert summary["priorityItemCount"] == 4
    assert summary["swotItemCount"] == 4
    assert summary["leadershipDecisionCount"] == 1
    assert summary["evidenceGapCount"] == 1
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
    assert str(workspace / "index.html") in render_payload["created"]
    assert (
        str(workspace / "assets" / "executive_summary_icons" / "priority_1_trophy.png")
        in render_payload["created"]
    )
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
    assert result["llmCallCount"] == 10
    assert result["llmPhases"] == [
        "objective",
        "useCase",
        "signal",
        "productReference",
        "odpsProductFacts",
        "odpsProductMinimal",
        "odpsProductComponents",
        "odpsProductAssemble",
        "graph",
        "executiveSummary",
    ]
    assert result["artifactCounts"]["productReferences"] == 1
    assert result["artifactCounts"]["odpsProducts"] == 1
    assert result["artifactCounts"]["priorityItems"] == 4
    assert result["artifactCounts"]["swotItems"] == 4
    assert result["artifactCounts"]["leadershipDecisions"] == 1
    assert result["warnings"] == []
    assert "validationResults" in result
    assert "catalog" in result["validationResults"]
    assert "graph" in result["validationResults"]
    assert len(result["validationResults"]["products"]) == 1
    assert (workspace / "portfolio.yaml").exists()
    assert (workspace / "executive-summary.yaml").exists()
    assert (workspace / "portfolio-state.yaml").exists()
    assert (workspace / "odpc" / "catalog.yaml").exists()
    assert (
        workspace / "odpc" / "fragments" / "product_reference_pr-customer.yaml"
    ).exists()
    assert (workspace / "odps" / "products" / "customer-product.yaml").exists()
    generated_product = load_mapping(
        workspace / "odps" / "products" / "customer-product.yaml"
    )
    assert (
        generated_product["product"]["details"]["en"]["productID"] == "customer-product"
    )
    assert not (
        workspace / "odps" / "products" / "customer-health-signals.yaml"
    ).exists()
    assert (workspace / "odpg" / "graph.yaml").exists()
    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "Portfolio" in html
    assert "Executive Summary" in html
    assert "Retention is the strongest near-term leadership topic." in html
    assert "Customer analytics product." in html
    summary_doc = load_mapping(workspace / "executive-summary.yaml")
    assert summary_doc["kind"] == "PortfolioExecutiveSummary"
    assert summary_doc["metadata"]["model"] == "test-model"
    assert summary_doc["swot"]["strengths"][0]["evidenceRefs"] == [
        {"type": "businessObjective", "id": "OBJ-RETENTION"},
        {"type": "useCase", "id": "UC-RETENTION"},
    ]
    catalog_text = (workspace / "odpc" / "catalog.yaml").read_text(encoding="utf-8")
    assert "$ref: ../odps/products/customer-product.yaml" in catalog_text
    portfolio_text = (workspace / "portfolio.yaml").read_text(encoding="utf-8")
    assert "executiveSummary: executive-summary.yaml" in portfolio_text
    assert "swot:" not in portfolio_text
    state_text = (workspace / "portfolio-state.yaml").read_text(encoding="utf-8")
    assert "sha256" in state_text


def test_portfolio_pipeline_builds_workspace_from_typed_source_lanes(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)

    result = PortfolioPipeline().build(
        PortfolioBuildRequest(
            workspace=workspace,
            source_lanes=PortfolioSourceLanes(
                objectives=sources / "objectives",
                use_cases=sources / "use-cases",
                signals=sources / "signals",
                products=sources / "products",
            ),
            client=fake_portfolio_client,
            model="test-model",
        )
    )

    assert isinstance(result, PortfolioBuildResult)
    assert result["kind"] == "PortfolioBuild"
    assert result.workspace == str(workspace)
    assert result.valid is True
    assert result.phases == [
        "objective",
        "useCase",
        "signal",
        "productReference",
        "odpsProductFacts",
        "odpsProductMinimal",
        "odpsProductComponents",
        "odpsProductAssemble",
        "graph",
        "executiveSummary",
    ]
    assert result.artifacts["counts"]["productReferences"] == 1
    assert result.source_budget["method"] == "deterministic-chunk-budget"
    assert result.to_dict()["workspace"] == str(workspace)


def test_portfolio_pipeline_accepts_lane_aliases_and_bundled_mode(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)

    result = PortfolioPipeline().build(
        PortfolioBuildRequest(
            workspace=workspace,
            source_lanes={
                "objectives": sources / "objectives",
                "use-cases": sources / "use-cases",
                "signals": sources / "signals",
                "products": sources / "products",
            },
            client=fake_portfolio_client,
            model="test-model",
            processing_mode="bundled",
        )
    )

    assert result["sourceCounts"] == {
        "objectives": 1,
        "useCases": 1,
        "signals": 1,
        "products": 1,
    }
    assert result["llmCallCount"] == 10
    assert result.valid is True


def test_build_portfolio_continues_after_one_product_source_fails(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    (sources / "products" / "aaa-bad-product.md").write_text(
        "Product discussion: malformed source that fails product reference generation.\n",
        encoding="utf-8",
    )

    def partially_failing_client(prompt: str, model: str) -> str:
        if (
            prompt.startswith("# Generate ODPS Data Product")
            and "aaa-bad-product.md" in prompt
        ):
            return "productReferences: []\n"
        return staged_portfolio_client(prompt, model)

    result = build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=partially_failing_client,
        model="test-model",
    )

    warnings = "\n".join(str(item) for item in result["warnings"])
    assert "Created fallback product reference for aaa-bad-product.md" in warnings
    assert "No artifacts generated for kind: product-reference" in warnings
    assert result["artifactCounts"]["productReferences"] == 2
    assert result["artifactCounts"]["odpsProducts"] == 2
    assert result["artifactCounts"]["leadershipDecisions"] == 1
    assert (workspace / "executive-summary.yaml").exists()
    assert (
        workspace / "odpc" / "fragments" / "product_reference_pr-customer.yaml"
    ).exists()
    assert (workspace / "odps" / "products" / "customer-product.yaml").exists()
    assert (
        workspace
        / "odpc"
        / "fragments"
        / "product_reference_product-discussion-malformed-source-that-fails-product-reference-generation.yaml"
    ).exists()
    portfolio_doc = load_mapping(workspace / "portfolio.yaml")
    assert any(
        "Created fallback product reference for aaa-bad-product.md" in str(item)
        for item in portfolio_doc["warnings"]
    )
    fallback_reference = load_mapping(
        workspace
        / "odpc"
        / "fragments"
        / "product_reference_product-discussion-malformed-source-that-fails-product-reference-generation.yaml"
    )["productReference"]
    assert fallback_reference["tags"] == ["fallback-generated", "needs-review"]
    assert fallback_reference["x-generation"]["fallback"] is True
    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "Review portfolio warnings" in html
    assert "Needs review" in html
    assert "Fallback generated" in html
    assert "Fallback reason:" in html


def test_build_portfolio_reports_skipped_msg_sources_without_counting_warning_lane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    msg_path = sources / "use-cases" / "outlook-request.msg"
    msg_path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1fake-msg")
    monkeypatch.setitem(sys.modules, "extract_msg", None)

    result = build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=fake_portfolio_client,
        model="test-model",
    )
    state = yaml.safe_load((workspace / "portfolio-state.yaml").read_text())

    assert "__warnings" not in result["sourceCounts"]
    assert "__warnings" not in result["processedSourceCounts"]
    assert "__warnings" not in state["sources"]
    assert "sourceId" in state["sources"]["useCases"][0]
    assert (
        f"Skipped Outlook .msg source {msg_path}: install "
        "open-data-products[email] to enable .msg extraction."
    ) in result["warnings"]
    assert result["sourceExtraction"] == {
        "warnings": [
            (
                f"Skipped Outlook .msg source {msg_path}: install "
                "open-data-products[email] to enable .msg extraction."
            )
        ],
        "skippedSourceCount": 1,
    }


def test_build_portfolio_reports_selected_context_format(tmp_path: Path) -> None:
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
        context_format="gcf",
    )

    assert result["contextFormat"] == "gcf"


def test_build_portfolio_generates_lanes_before_graph_and_summary(
    tmp_path: Path,
) -> None:
    """Test source-lane builds generate fragments before graph and summary."""
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)

    prompts = []

    def client(prompt: str, model: str) -> str:
        prompts.append(prompt.splitlines()[0])
        return staged_portfolio_client(prompt, model)

    result = build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=client,
        model="test-model",
    )

    assert prompts == [
        "# Generate ODPC Business Objective Fragments",
        "# Generate ODPC Use Case Fragments",
        "# Generate ODPC Signal Fragments",
        "# Generate ODPS Data Product Fragments",
        "# Extract ODPS Product Facts",
        "# Generate Minimal ODPS Product YAML",
        "# Draft ODPS Product Components",
        "# Assemble ODPS Product YAML",
        "# Infer ODPG Edges from ODPC Fragments",
        "# Create Portfolio Executive Summary",
    ]
    assert result["llmCallCount"] == 10
    assert result["llmPhases"] == [
        "objective",
        "useCase",
        "signal",
        "productReference",
        "odpsProductFacts",
        "odpsProductMinimal",
        "odpsProductComponents",
        "odpsProductAssemble",
        "graph",
        "executiveSummary",
    ]
    assert (workspace / "odpc" / "fragments" / "signal_churn-signal.yaml").exists()
    assert "UC-RETENTION" in (workspace / "odpg" / "graph.yaml").read_text(
        encoding="utf-8"
    )
    assert "Executive Summary" in (workspace / "index.html").read_text(encoding="utf-8")


def test_sync_portfolio_preserves_existing_executive_summary_without_generation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)
    write_sample_executive_summary(workspace)

    result = sync_portfolio(workspace)

    summary_text = (workspace / "executive-summary.yaml").read_text(encoding="utf-8")
    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert result["kind"] == "PortfolioSync"
    assert "Retention is the strongest near-term leadership topic." in summary_text
    assert "Retention is the strongest near-term leadership topic." in html
    assert result["artifactCounts"]["priorityItems"] == 4
    assert result["artifactCounts"]["swotItems"] == 4


def test_render_portfolio_reports_priority_briefing_validation_errors(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)
    (workspace / "executive-summary.yaml").write_text(
        EXECUTIVE_SUMMARY_YAML.replace(
            """    evidence:
      - type: businessObjective
        label: Reduce preventable churn
        id: OBJ-RETENTION
      - type: useCase
        label: Retention risk workflow
        id: UC-RETENTION
      - type: productReference
        label: Customer health signals
        id: PR-CUSTOMER
""",
            "",
        ),
        encoding="utf-8",
    )

    result = render_portfolio(workspace)

    assert result["validationResults"]["executiveSummary"]["valid"] is False
    assert any(
        "priorityBriefing.primaryFocus.evidence is required" in error
        for error in result["validationResults"]["executiveSummary"]["errors"]
    )


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
    assert "status: active" in catalog
    assert "type: market" in catalog
    assert "origin: internal" in catalog
    assert "method: market note" in catalog
    assert "observedAt:" in catalog

    graph = (workspace / "odpg" / "graph.yaml").read_text(encoding="utf-8")
    assert "description:" in graph
    assert "$ref: use_case_uc-retention.yaml" in graph
    assert "type: Signal" in graph
    assert "type: KPI" not in graph
    assert "from: UC-RETENTION" in graph
    assert "to: PR-CUSTOMER" in graph
    assert "source: UC-RETENTION" not in graph
    assert "target: PR-CUSTOMER" not in graph
    assert "type: uses" in graph


def test_portfolio_build_prompt_defines_schema_and_linking_rules() -> None:
    lanes = {
        "objectives": [
            {
                "path": "sources/objectives/retention.md",
                "text": "Business objective: Improve Retention",
                "sha256": "obj",
            }
        ],
        "useCases": [
            {
                "path": "sources/use-cases/retention.md",
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
    assert "executiveSummary:" not in prompt
    assert "portfolioPosition:" not in prompt
    assert "priorityBriefing:" not in prompt
    assert "Do not emit executiveSummary in this phase" in prompt
    assert "warnings:" in prompt
    assert "productReference.productID must match odpsProduct" in prompt
    assert 'productModel.$ref must be "../odps/products/<productID>.yaml"' in prompt
    assert "Graph edge source and target values must use generated stable IDs" in prompt


def test_reduce_source_lanes_chunks_and_reports_budget_metadata() -> None:
    lanes = {
        "objectives": [
            {
                "path": "sources/objectives/retention.md",
                "sourceId": "sources/objectives/retention.md#file-1",
                "text": "alpha\n\nbravo\n\ncharlie\n\ndelta",
                "sha256": "obj",
            }
        ],
        "useCases": [
            {
                "path": "sources/use-cases/retention.md",
                "sourceId": "sources/use-cases/retention.md#file-1",
                "text": "echo",
                "sha256": "uc",
            }
        ],
        "signals": [],
        "products": [],
    }

    reduced, budget = _reduce_source_lanes_for_prompt(
        lanes,
        max_source_chars=12,
        max_prompt_chars=22,
    )

    assert reduced["objectives"][0]["text"] == "alpha\n\nbravo\n\ncharlie"
    assert reduced["objectives"][0]["chunkCount"] == "3"
    assert reduced["objectives"][0]["includedChunkCount"] == "2"
    assert reduced["objectives"][0]["omittedChunkCount"] == "1"
    assert reduced["useCases"][0]["text"] == "echo"
    assert budget["method"] == "deterministic-chunk-budget"
    assert budget["budgetScope"] == "per-source"
    assert budget["chunkCount"] == 4
    assert budget["includedChunkCount"] == 3
    assert budget["omittedChunkCount"] == 1
    assert budget["reducedSourceCount"] == 1
    assert budget["warnings"] == [
        "Content omitted from prompt: 1 chunks over context budget"
    ]


def test_build_portfolio_reduces_long_source_before_lane_llm_calls(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    tail_marker = "TAIL_MARKER_SHOULD_NOT_REACH_LLM"
    (sources / "objectives" / "retention-objective.md").write_text(
        "Business objective: Improve Retention\n\n"
        + ("Relevant retention context.\n\n" * 900)
        + tail_marker,
        encoding="utf-8",
    )
    prompts = []

    def client(prompt: str, model: str) -> str:
        prompts.append(prompt)
        return staged_portfolio_client(prompt, model)

    result = build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=client,
        model="test-model",
    )

    assert tail_marker not in prompts[0]
    assert result["sourceBudget"]["method"] == "deterministic-chunk-budget"
    assert result["sourceBudget"]["omittedChunkCount"] > 0
    assert result["sourceBudget"]["warnings"] == [
        f"Content omitted from prompt: {result['sourceBudget']['omittedChunkCount']} chunks over context budget"
    ]
    assert result["promptBudget"]["method"] == "final-prompt-char-gate"
    assert result["promptBudget"]["checkedPromptCount"] > 0
    assert (
        result["promptBudget"]["maxObservedPromptChars"]
        <= result["promptBudget"]["maxPromptChars"]
    )


def test_build_portfolio_blocks_llm_call_when_rendered_prompt_exceeds_budget(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    calls = []

    def client(prompt: str, model: str) -> str:
        calls.append(prompt)
        return staged_portfolio_client(prompt, model)

    with pytest.raises(ValueError) as excinfo:
        build_portfolio(
            workspace,
            objectives=sources / "objectives",
            use_cases=sources / "use-cases",
            signals=sources / "signals",
            products=sources / "products",
            client=client,
            model="test-model",
            source_budget=PortfolioSourceBudget(
                max_source_chars=40,
                max_prompt_chars=100,
            ),
        )

    assert calls == []
    assert "Portfolio prompt exceeds configured budget" in str(excinfo.value)
    assert "maxPromptChars=100" in str(excinfo.value)


def test_obfuscate_personal_data_masks_emails_and_phone_numbers() -> None:
    result = obfuscate_personal_data(
        "Contact Ada at ada@example.com or +358 40 123 4567. "
        "Email ada@example.com again if needed. Review 2026-06-30."
    )

    assert "ada@example.com" not in result["text"]
    assert "+358 40 123 4567" not in result["text"]
    assert result["text"].count("[EMAIL_1]") == 2
    assert "[PHONE_1]" in result["text"]
    assert "2026-06-30" in result["text"]
    assert result["replacementCounts"] == {"email": 1, "phone": 1}
    assert {
        "type": "email",
        "placeholder": "[EMAIL_1]",
        "confidence": "high",
    } in result["replacements"]
    assert {
        "type": "phone",
        "placeholder": "[PHONE_1]",
        "confidence": "high",
    } in result["replacements"]


def test_build_portfolio_obfuscates_personal_data_before_llm_calls(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    (sources / "use-cases" / "retention.md").write_text(
        "Use case: Retention workflow\n"
        "Contact ada@example.com or +358 40 123 4567 about weekly churn review.",
        encoding="utf-8",
    )
    prompts = []

    def client(prompt: str, model: str) -> str:
        prompts.append(prompt)
        return staged_portfolio_client(prompt, model)

    result = build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=client,
        model="test-model",
    )

    assert "ada@example.com" not in "\n".join(prompts)
    assert "+358 40 123 4567" not in "\n".join(prompts)
    assert "[EMAIL_1]" in prompts[1]
    assert "[PHONE_1]" in prompts[1]
    assert result["sourcePrivacy"]["enabled"] is True
    assert result["sourcePrivacy"]["replacementCounts"] == {"email": 1, "phone": 1}
    assert result["sourcePrivacy"]["sourceCount"] == 4
    assert result["sourcePrivacy"]["warnings"] == [
        "Personal data obfuscation is best effort; review before external LLM use."
    ]


def test_build_portfolio_can_disable_personal_data_obfuscation(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)
    (sources / "use-cases" / "retention.md").write_text(
        "Use case: Retention workflow\n"
        "Contact ada@example.com about weekly churn review.",
        encoding="utf-8",
    )
    prompts = []

    def client(prompt: str, model: str) -> str:
        prompts.append(prompt)
        return staged_portfolio_client(prompt, model)

    result = build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=client,
        model="test-model",
        source_privacy=PortfolioPrivacySettings(obfuscate_personal_data=False),
    )

    assert "ada@example.com" in "\n".join(prompts)
    assert result["sourcePrivacy"]["enabled"] is False
    assert result["sourcePrivacy"]["replacementCounts"] == {}
    assert result["sourcePrivacy"]["warnings"] == [
        "Personal data obfuscation is disabled for portfolio document intake."
    ]
    assert (
        "Personal data obfuscation is disabled for portfolio document intake."
        in result["warnings"]
    )


def test_inspect_portfolio_intake_reports_extraction_and_budget(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    write_source_lanes(sources)
    (sources / "use-cases" / "long.md").write_text(
        "Use case: Expansion\n\n" + ("Detailed workflow evidence.\n\n" * 20),
        encoding="utf-8",
    )

    result = inspect_portfolio_intake(
        use_cases=sources / "use-cases",
        source_budget=PortfolioSourceBudget(max_source_chars=40, max_prompt_chars=120),
    )

    assert result["kind"] == "PortfolioIntake"
    assert result["llmCallCount"] == 0
    assert result["sourceCounts"]["useCases"] == 2
    assert result["sourceBudget"]["maxSourceChars"] == 40
    assert result["sourceBudget"]["maxPromptChars"] == 120
    assert result["sourceBudget"]["omittedChunkCount"] > 0
    long_source = [
        source
        for source in result["sources"]
        if source["path"] == str(sources / "use-cases" / "long.md")
    ][0]
    assert long_source["lane"] == "useCases"
    assert long_source["sourceType"] == "md"
    assert long_source["extractedChars"] > 120
    assert long_source["chunkCount"] > long_source["includedChunkCount"]
    assert long_source["status"] == "reduced"


def test_portfolio_executive_summary_prompt_uses_normalized_evidence() -> None:
    plan = parse_portfolio_plan(PORTFOLIO_PLAN_YAML)
    prompt = render_portfolio_executive_summary_prompt(plan)

    assert prompt.startswith("# Create Portfolio Executive Summary")
    assert "Return only YAML" in prompt
    assert "kind: PortfolioExecutiveSummary" in prompt
    assert "priorityBriefing:" in prompt
    assert "dashboardTitle: Retention validation" in prompt
    assert "leadershipDecisions:" in prompt
    assert "Normalized portfolio evidence:" in prompt
    assert "businessObjectives:" in prompt
    assert "graphEdges:" in prompt
    assert (
        "executiveSummary:" not in prompt.split("Normalized portfolio evidence:", 1)[1]
    )
    assert "sources/objectives/retention.md" not in prompt
    assert "Business objective: Improve Retention" not in prompt


def test_parse_portfolio_plan_accepts_open_markdown_yaml_fence() -> None:
    plan = parse_portfolio_plan("""```yaml
metadata:
  id: generated-demo
  name: Generated Demo Portfolio
businessObjectives: []
""")

    assert plan["metadata"]["id"] == "generated-demo"
    assert plan["businessObjectives"] == []


def test_parse_portfolio_plan_reports_truncated_yaml() -> None:
    with pytest.raises(ValueError) as exc_info:
        parse_portfolio_plan("""
metadata:
  id: generated-demo
products:
  - productReference:
      productModel:
        $ref: "#
""")

    assert "Portfolio plan YAML could not be parsed" in str(exc_info.value)
    assert "truncated" in str(exc_info.value)


def test_build_portfolio_repairs_malformed_plan_yaml(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    workspace = tmp_path / "generated" / "portfolio"
    write_source_lanes(sources)

    result = build_portfolio(
        workspace,
        objectives=sources / "objectives",
        use_cases=sources / "use-cases",
        signals=sources / "signals",
        products=sources / "products",
        client=repairable_portfolio_client,
        model="test-model",
    )

    assert result["valid"] is True
    assert result["llmCallCount"] == 10
    assert result["llmPhases"] == [
        "objective",
        "useCase",
        "signal",
        "productReference",
        "odpsProductFacts",
        "odpsProductMinimal",
        "odpsProductComponents",
        "odpsProductAssemble",
        "graph",
        "executiveSummary",
    ]
    assert "portfolioRepair" not in result["llmPhases"]
    assert (workspace / "portfolio.yaml").exists()
    assert "Customer Product" in (workspace / "index.html").read_text(encoding="utf-8")


def test_build_portfolio_repairs_malformed_executive_summary_yaml(
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
        client=repairable_executive_summary_client,
        model="test-model",
    )

    assert result["valid"] is True
    assert result["llmCallCount"] == 11
    assert result["llmPhases"] == [
        "objective",
        "useCase",
        "signal",
        "productReference",
        "odpsProductFacts",
        "odpsProductMinimal",
        "odpsProductComponents",
        "odpsProductAssemble",
        "graph",
        "executiveSummary",
        "executiveSummaryRepair",
    ]
    summary_doc = load_mapping(workspace / "executive-summary.yaml")
    assert (
        "Executive Summary YAML required syntax repair."
        in summary_doc["confidenceNotes"]
    )


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
                "--context-format",
                "gcf",
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
    assert payload["contextFormat"] == "gcf"
    assert payload["artifactCounts"]["graphEdges"] == 1
    assert "validationResults" in payload
    assert (workspace / "index.html").exists()
    assert "CLI Controlled Portfolio" in (workspace / "index.html").read_text(
        encoding="utf-8"
    )


def test_localize_portfolio_writes_i18n_and_localized_html_without_touching_yaml(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)
    write_sample_executive_summary(workspace)
    (workspace / "portfolio-i18n.yaml").write_text(
        """
defaultLanguage: en
languages:
  - en
  - fi
translations:
  fi:
    html:
      This tab embeds the generated ODPG graph explorer without the standalone explorer header and footer.: Vanha teksti
""",
        encoding="utf-8",
    )
    product_path = workspace / "odps" / "products" / "customer-product.yaml"
    summary_path = workspace / "executive-summary.yaml"
    original_product_yaml = product_path.read_text(encoding="utf-8")
    original_summary_yaml = summary_path.read_text(encoding="utf-8")

    result = localize_portfolio(
        workspace,
        languages=["fi", "sv"],
        client=fake_localization_client,
        model="test-model",
    )

    assert result["kind"] == "PortfolioLocalize"
    assert result["languages"] == ["fi", "sv"]
    assert result["defaultLanguage"] == "en"
    assert result["html"] == {
        "en": str(workspace / "index.html"),
        "fi": str(workspace / "index.fi.html"),
        "sv": str(workspace / "index.sv.html"),
    }
    qa = result["localizationQa"]
    assert qa["sourceStringCount"] > 0
    assert qa["languages"]["fi"]["sourceStringCount"] == qa["sourceStringCount"]
    assert qa["languages"]["fi"]["presentStringCount"] > 0
    assert qa["languages"]["fi"]["changedStringCount"] > 0
    assert 0 < qa["languages"]["fi"]["coverage"] <= 1
    assert 0 < qa["languages"]["fi"]["changedCoverage"] <= 1
    assert "validationResults" in result
    assert product_path.read_text(encoding="utf-8") == original_product_yaml
    assert summary_path.read_text(encoding="utf-8") == original_summary_yaml

    i18n = load_mapping(workspace / "portfolio-i18n.yaml")
    assert i18n["defaultLanguage"] == "en"
    assert i18n["languages"] == ["en", "fi", "sv"]
    assert i18n["translations"]["fi"]["html"]["Products"] == "Tuotteet"
    assert "customer-product" not in i18n["translations"]["fi"]["html"]
    assert (
        "This tab embeds the generated ODPG graph explorer without the standalone explorer header and footer."
        not in i18n["translations"]["fi"]["html"]
    )

    english_html = (workspace / "index.html").read_text(encoding="utf-8")
    finnish_html = (workspace / "index.fi.html").read_text(encoding="utf-8")
    swedish_html = (workspace / "index.sv.html").read_text(encoding="utf-8")
    assert '<html lang="en"' in english_html
    assert '<html lang="fi"' in finnish_html
    assert '<html lang="sv"' in swedish_html
    assert 'class="language-selector"' in english_html
    assert 'href="index.fi.html"' in english_html
    assert 'href="index.html"' in finnish_html
    assert "Tuotteet" in finnish_html
    assert "Johdon yhteenveto" in finnish_html
    assert "Retention is the strongest near-term leadership topic." in finnish_html
    assert "Asiakastuote" in finnish_html
    assert "customer-product" in finnish_html
    assert "Ledningssammanfattning" in swedish_html
    assert "Kundprodukt" in swedish_html
    assert "customer-product" in swedish_html

    english_style = english_html.split("<style>", 1)[1].split("</style>", 1)[0]
    finnish_style = finnish_html.split("<style>", 1)[1].split("</style>", 1)[0]
    assert finnish_style == english_style

    english_script = english_html.split("<script>", 1)[1].split("</script>", 1)[0]
    finnish_script = finnish_html.split("<script>", 1)[1].split("</script>", 1)[0]
    assert finnish_script == english_script


def test_localize_portfolio_marks_rtl_language_pages(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)

    result = localize_portfolio(
        workspace,
        languages=["ar-AE"],
        client=fake_localization_client,
        model="test-model",
    )

    assert result["html"]["ar-AE"] == str(workspace / "index.ar-AE.html")
    english_html = (workspace / "index.html").read_text(encoding="utf-8")
    arabic_html = (workspace / "index.ar-AE.html").read_text(encoding="utf-8")

    assert '<html lang="en" dir="ltr">' in english_html
    assert '<html lang="ar-AE" dir="rtl">' in arabic_html
    assert "محفظة منتجات البيانات" in arabic_html
    assert 'html[dir="rtl"]' in arabic_html


def test_portfolio_cli_localize_emits_one_final_json_report(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)

    from open_data_products import generation

    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: fake_localization_client,
    )

    assert (
        main(
            [
                "portfolio",
                "localize",
                str(workspace),
                "--languages",
                "fi,sv",
                "--model",
                "test-model",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == "PortfolioLocalize"
    assert payload["languages"] == ["fi", "sv"]
    assert payload["html"]["fi"] == str(workspace / "index.fi.html")
    assert (workspace / "index.fi.html").exists()


def test_localize_portfolio_repairs_malformed_translation_yaml(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)

    result = localize_portfolio(
        workspace,
        languages=["fi"],
        client=repairable_localization_client,
        model="test-model",
    )

    assert result["kind"] == "PortfolioLocalize"
    assert (
        "Portfolio localization YAML required syntax repair for fi."
        in result["warnings"]
    )
    i18n = load_mapping(workspace / "portfolio-i18n.yaml")
    assert i18n["translations"]["fi"]["html"]["Products"] == "Tuotteet"
    html = (workspace / "index.fi.html").read_text(encoding="utf-8")
    assert "Asiakastuote" in html


def test_portfolio_cli_build_defaults_to_validation_warning_mode(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from open_data_products import generation, portfolio

    def fake_build_portfolio(*args, **kwargs):
        return {
            "spec": "portfolio",
            "kind": "PortfolioBuild",
            "workspace": str(tmp_path / "workspace"),
            "html": str(tmp_path / "workspace" / "index.html"),
            "validationResults": {
                "products": [
                    {
                        "valid": False,
                        "errors": ["/product/license/scope/restrictions is too long"],
                    }
                ]
            },
            "created": [],
            "updated": [],
            "unchanged": [],
            "valid": False,
        }

    monkeypatch.setattr(generation, "create_generation_client", lambda settings: None)
    monkeypatch.setattr(portfolio, "build_portfolio", fake_build_portfolio)

    assert (
        main(
            [
                "portfolio",
                "build",
                "--output",
                str(tmp_path / "workspace"),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["valid"] is False
    assert payload["validationMode"] == "warn"


def test_portfolio_cli_build_passes_configured_source_budget(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from open_data_products import generation, portfolio

    config = tmp_path / "generation.config.yaml"
    config.write_text(
        """
provider: ollama
model: qwen2.5
portfolio:
  sourceBudget:
    maxSourceChars: 40
    maxPromptChars: 80
providers:
  ollama:
    type: ollama
    model: qwen2.5
""",
        encoding="utf-8",
    )
    captured = {}

    def fake_build_portfolio(*args, **kwargs):
        captured.update(kwargs)
        return {
            "spec": "portfolio",
            "kind": "PortfolioBuild",
            "workspace": str(tmp_path / "workspace"),
            "html": str(tmp_path / "workspace" / "index.html"),
            "validationResults": {},
            "created": [],
            "updated": [],
            "unchanged": [],
            "valid": True,
        }

    monkeypatch.setattr(generation, "create_generation_client", lambda settings: None)
    monkeypatch.setattr(portfolio, "build_portfolio", fake_build_portfolio)

    assert (
        main(
            [
                "portfolio",
                "build",
                "--config",
                str(config),
                "--output",
                str(tmp_path / "workspace"),
                "--json",
            ]
        )
        == 0
    )
    json.loads(capsys.readouterr().out)

    assert captured["source_budget"].max_source_chars == 40
    assert captured["source_budget"].max_prompt_chars == 80


def test_portfolio_cli_build_passes_configured_privacy_setting(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from open_data_products import generation, portfolio

    config = tmp_path / "generation.config.yaml"
    config.write_text(
        """
provider: ollama
model: qwen2.5
portfolio:
  privacy:
    obfuscatePersonalData: false
providers:
  ollama:
    type: ollama
    model: qwen2.5
""",
        encoding="utf-8",
    )
    captured = {}

    def fake_build_portfolio(*args, **kwargs):
        captured.update(kwargs)
        return {
            "spec": "portfolio",
            "kind": "PortfolioBuild",
            "workspace": str(tmp_path / "workspace"),
            "html": str(tmp_path / "workspace" / "index.html"),
            "validationResults": {},
            "created": [],
            "updated": [],
            "unchanged": [],
            "valid": True,
        }

    monkeypatch.setattr(generation, "create_generation_client", lambda settings: None)
    monkeypatch.setattr(portfolio, "build_portfolio", fake_build_portfolio)

    assert (
        main(
            [
                "portfolio",
                "build",
                "--config",
                str(config),
                "--output",
                str(tmp_path / "workspace"),
                "--json",
            ]
        )
        == 0
    )
    json.loads(capsys.readouterr().out)

    assert captured["source_privacy"].obfuscate_personal_data is False


def test_portfolio_cli_build_prints_warnings_in_text_output(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from open_data_products import generation, portfolio

    def fake_build_portfolio(*args, **kwargs):
        return {
            "spec": "portfolio",
            "kind": "PortfolioBuild",
            "workspace": str(tmp_path / "workspace"),
            "html": str(tmp_path / "workspace" / "index.html"),
            "validationResults": {},
            "created": [],
            "updated": [],
            "unchanged": [],
            "warnings": [
                "Personal data obfuscation is disabled for portfolio document intake."
            ],
            "valid": True,
        }

    monkeypatch.setattr(generation, "create_generation_client", lambda settings: None)
    monkeypatch.setattr(portfolio, "build_portfolio", fake_build_portfolio)

    assert (
        main(
            [
                "portfolio",
                "build",
                "--output",
                str(tmp_path / "workspace"),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out

    assert (
        "Warning: Personal data obfuscation is disabled for portfolio document intake."
        in output
    )


def test_portfolio_cli_intake_emits_budget_report(
    tmp_path: Path,
    capsys,
) -> None:
    sources = tmp_path / "sources"
    write_source_lanes(sources)
    config = tmp_path / "generation.config.yaml"
    config.write_text(
        """
provider: ollama
model: qwen2.5
portfolio:
  sourceBudget:
    maxSourceChars: 40
    maxPromptChars: 120
providers:
  ollama:
    type: ollama
    model: qwen2.5
""",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "portfolio",
                "intake",
                "--config",
                str(config),
                "--objectives",
                str(sources / "objectives"),
                "--use-cases",
                str(sources / "use-cases"),
                "--signals",
                str(sources / "signals"),
                "--products",
                str(sources / "products"),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == "PortfolioIntake"
    assert payload["llmCallCount"] == 0
    assert payload["sourceCounts"]["objectives"] == 1
    assert payload["sourceCounts"]["useCases"] == 1
    assert payload["sourceCounts"]["signals"] == 1
    assert payload["sourceCounts"]["products"] == 1
    assert payload["sourceBudget"]["maxSourceChars"] == 40
    assert payload["sourceBudget"]["maxPromptChars"] == 120
    assert {source["lane"] for source in payload["sources"]} == {
        "objectives",
        "useCases",
        "signals",
        "products",
    }


def test_portfolio_cli_build_strict_validation_returns_nonzero_for_invalid_report(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    from open_data_products import generation, portfolio

    def fake_build_portfolio(*args, **kwargs):
        return {
            "spec": "portfolio",
            "kind": "PortfolioBuild",
            "workspace": str(tmp_path / "workspace"),
            "html": str(tmp_path / "workspace" / "index.html"),
            "validationResults": {
                "products": [
                    {
                        "valid": False,
                        "errors": ["/product/license/scope/restrictions is too long"],
                    }
                ]
            },
            "created": [],
            "updated": [],
            "unchanged": [],
            "valid": False,
        }

    monkeypatch.setattr(generation, "create_generation_client", lambda settings: None)
    monkeypatch.setattr(portfolio, "build_portfolio", fake_build_portfolio)

    assert (
        main(
            [
                "portfolio",
                "build",
                "--output",
                str(tmp_path / "workspace"),
                "--strict-validation",
                "--json",
            ]
        )
        == 1
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["valid"] is False
    assert payload["validationMode"] == "strict"


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
    assert "Renewal is now a leadership review topic." in latest_html
    summary = load_mapping(workspace / "executive-summary.yaml")
    assert (
        summary["portfolioPosition"]["headline"]
        == "Renewal is now a leadership review topic."
    )
    assert result["artifactCounts"]["swotItems"] == 1
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


def test_refresh_portfolio_preserves_changed_signal_source_as_draft_signal(
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
    (sources / "signals" / "regional.md").write_text(
        "Signal: regional retention pressure is rising\n",
        encoding="utf-8",
    )

    result = refresh_portfolio(
        workspace,
        client=collapsed_signal_portfolio_client,
        model="test-model",
    )

    assert result["sourceChanges"]["signals"]["created"] == [
        str(sources / "signals" / "regional.md")
    ]
    assert result["artifactCounts"]["signals"] == 2
    catalog_text = (workspace / "odpc" / "catalog.yaml").read_text(encoding="utf-8")
    graph_text = (workspace / "odpg" / "graph.yaml").read_text(encoding="utf-8")
    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "regional-retention-pressure" in catalog_text
    assert "Regional" in catalog_text
    assert "Regional retention pressure is rising" in catalog_text
    assert "regional-retention-pressure" in graph_text
    assert "Regional" in html


def test_refresh_portfolio_does_not_duplicate_renamed_signal_from_changed_source(
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
    (sources / "signals" / "regional.md").write_text(
        "Product usage is down, support tickets are up, and renewal activity has slowed for several priority accounts.\n",
        encoding="utf-8",
    )

    result = refresh_portfolio(
        workspace,
        client=renamed_signal_portfolio_client,
        model="test-model",
    )

    assert result["artifactCounts"]["signals"] == 2
    catalog = load_mapping(workspace / "odpc" / "catalog.yaml")["catalog"]
    signal_ids = [item["id"] for item in catalog["signals"]]
    assert "daily-retention-briefing" in signal_ids
    assert "regional-retention-pressure" not in signal_ids


def test_refresh_portfolio_ignores_overbroad_delta_objects_from_unchanged_lanes(
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
    (sources / "signals" / "regional.txt").write_text(
        "Signal: regional retention pressure is rising\n",
        encoding="utf-8",
    )

    result = refresh_portfolio(
        workspace,
        client=overbroad_signal_delta_portfolio_client,
        model="test-model",
    )
    localize_portfolio(
        workspace,
        languages=["fi"],
        client=fake_localization_client,
        model="test-model",
    )

    assert result["processedSourceCounts"]["objectives"] == 0
    assert result["processedSourceCounts"]["useCases"] == 0
    assert result["processedSourceCounts"]["signals"] == 1
    assert result["processedSourceCounts"]["products"] == 0
    assert result["artifactCounts"]["businessObjectives"] == 1
    assert result["artifactCounts"]["useCases"] == 1
    assert result["artifactCounts"]["signals"] == 2
    assert result["artifactCounts"]["productReferences"] == 1

    catalog = load_mapping(workspace / "odpc" / "catalog.yaml")["catalog"]
    assert len(catalog["businessObjectives"]) == 1
    assert len(catalog["useCases"]) == 1
    assert len(catalog["signals"]) == 2
    assert len(catalog["productReferences"]) == 1
    assert "OBJ-RETENTION-EXTRA" not in (workspace / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Customer Product Duplicate" not in (workspace / "index.fi.html").read_text(
        encoding="utf-8"
    )


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
    assert "churn-signal\n" in catalog_text
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
    product_path = write_customer_product_spec(workspace)
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


def test_render_portfolio_formats_odps_component_dimensions_for_humans(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)
    product_path = workspace / "odps" / "products" / "customer-product.yaml"
    product = yaml.safe_load(product_path.read_text(encoding="utf-8"))
    product["product"]["pricingPlans"] = {
        "declarative": {
            "en": [
                {
                    "name": "Internal Starter",
                    "description": "Internal use during pilot.",
                    "priceCurrency": "XXX",
                    "price": "0",
                    "billingDuration": "month",
                    "unit": "On-request",
                    "access": {"$ref": "#/product/dataAccess/API"},
                    "SLA": {"$ref": "#/product/SLA/declarative/default"},
                    "dataQuality": {
                        "$ref": "#/product/dataQuality/declarative/default"
                    },
                }
            ]
        }
    }
    product["product"]["SLA"] = {
        "declarative": {
            "default": {
                "name": {"en": "The Basic SLA"},
                "description": {"en": "Daily refresh for weekly review."},
                "dimensions": [
                    {
                        "dimension": "updateFrequency",
                        "displaytitle": {"en": "Data Freshness"},
                        "objective": 1440,
                        "unit": "minutes",
                        "weight": 60,
                    },
                    {
                        "dimension": "uptime",
                        "displaytitle": {"en": "Availability"},
                        "objective": 95,
                        "unit": "percent",
                        "weight": 40,
                    },
                ],
            }
        }
    }
    product["product"]["dataAccess"] = {
        "API": {
            "description": {"en": "Internal API access during pilot."},
            "outputPortType": "API",
        }
    }
    product["product"]["dataQuality"] = {
        "declarative": {
            "default": {
                "description": "Required field completeness and valid score range.",
                "dimensions": [
                    {
                        "dimension": "completeness",
                        "displayTitle": "Account ID Completeness",
                        "objective": 100,
                        "unit": "percentage",
                        "weight": 40,
                        "description": "Account ID must not be null.",
                    }
                ],
            }
        }
    }
    product["product"]["license"] = {
        "scope": {
            "definition": "Internal product use for customer success.",
            "restrictions": "No external redistribution.",
        }
    }
    product_path.write_text(
        yaml.safe_dump(product, sort_keys=False),
        encoding="utf-8",
    )

    render_portfolio(workspace)

    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert "Internal Starter" in html
    assert 'class="product-marketplace-segments"' in html
    assert 'class="market-plan-card"' in html
    assert '<section class="market-segment"><h4>Pricing</h4>' in html
    assert '<section class="market-segment"><h4>Data Quality</h4>' in html
    assert '<section class="market-segment"><h4>SLA</h4>' in html
    assert '<section class="market-segment"><h4>Licensing</h4>' in html
    assert "The Basic SLA" in html
    assert "Data Freshness" in html
    assert "Availability" in html
    assert "Account ID Completeness" in html
    assert "Internal product use for customer success." in html
    assert "No external redistribution." in html
    assert "Included SLA" not in html
    assert "Included Data Quality" not in html
    assert "Included Access" not in html
    assert '<section class="component-section"><h4>SLA</h4>' not in html
    assert '<section class="component-section"><h4>Data Quality</h4>' not in html
    assert "1440 minutes" in html
    assert "95 percent" in html
    assert "100 percentage" in html
    assert "<dt>priceCurrency</dt>" not in html
    assert "<dt>billingDuration</dt>" not in html
    assert "&#x27;dimension&#x27;" not in html
    assert "[{" not in html
    assert "<dt>dimensions</dt>" not in html


def test_render_portfolio_uses_product_cards_with_detail_modals(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)

    render_portfolio(workspace)

    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert '<div class="product-grid">' in html
    assert 'class="card product product-card"' in html
    assert 'class="product-detail-button"' in html
    assert 'data-modal-target="product-modal-customer-product"' in html
    assert 'id="product-modal-customer-product"' in html
    assert 'class="product-modal"' in html
    assert "product-modal-panel" in html
    assert "product-card-counters" in html
    assert "document.addEventListener" in html
    assert "data-modal-close" in html
    assert '<details class="odp-detail" open>' not in html


def test_render_portfolio_matches_generated_product_id_suffix(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    write_sample_workspace(workspace)
    catalog_path = workspace / "odpc" / "catalog.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    reference = catalog["catalog"]["productReferences"][0]
    reference["productID"] = "customer-product-product"
    reference.pop("productModel")
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")

    render_portfolio(workspace)

    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert 'class="product-detail-button"' in html
    assert 'data-modal-target="product-modal-customer-product"' in html
    assert 'id="product-modal-customer-product"' in html
    assert "No linked ODPS detail" not in html


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
    product_path = write_customer_product_spec(workspace)
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
    from open_data_products import PortfolioBuildRequest as public_build_request
    from open_data_products import PortfolioBuildResult as public_build_result
    from open_data_products import PortfolioPipeline as public_pipeline
    from open_data_products import PortfolioSourceLanes as public_source_lanes
    from open_data_products import build_portfolio as public_build_portfolio
    from open_data_products import explain_portfolio as public_explain_portfolio
    from open_data_products import localize_portfolio as public_localize_portfolio
    from open_data_products import refresh_portfolio as public_refresh_portfolio
    from open_data_products import render_portfolio as public_render_portfolio
    from open_data_products import sync_portfolio as public_sync_portfolio

    assert public_build_request is PortfolioBuildRequest
    assert public_build_result is PortfolioBuildResult
    assert public_pipeline is PortfolioPipeline
    assert public_source_lanes is PortfolioSourceLanes
    assert public_build_portfolio is build_portfolio
    assert public_localize_portfolio is localize_portfolio
    assert public_refresh_portfolio is refresh_portfolio
    assert public_render_portfolio is render_portfolio
    assert public_sync_portfolio is sync_portfolio
    assert public_explain_portfolio is explain_portfolio
