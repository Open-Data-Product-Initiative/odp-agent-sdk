# Portfolio Executive Summary Plan

This plan describes how to add a non-decorative Executive Summary tab to the
portfolio workspace. The tab should help leadership review the current
portfolio, discuss business decisions, and see a ranked focus model grounded in
the generated portfolio evidence.

The important boundary is that the Executive Summary is a machine-readable
portfolio artifact first and an HTML tab second. The browser view renders the
artifact; it is not the source of truth.

Implementation status: this plan now reflects the implemented v1 behavior.
The remaining value of this document is to preserve the contract and the
reasoning behind the design.

## Goal

Add a new `Executive Summary` tab to generated portfolio HTML and store its
content as a separate YAML artifact in the workspace:

```text
<workspace>/
  executive-summary.yaml
  index.html
  portfolio.yaml
  portfolio-state.yaml
  odpc/
  odps/
  odpg/
```

The summary should provide:

- a concise business position for the current portfolio;
- a ranked leadership focus model with Priority 1, Priority 2, risk, and
  readiness check;
- leadership decision questions;
- evidence gaps;
- confidence notes.

The result must be suitable for leadership discussion, but it must remain
inspectable by machines and reviewable by humans.

Implemented behavior:

- LLM-backed build and refresh run Executive Summary generation as a second
  phase after normalized portfolio artifacts are available.
- The generated summary is written to `executive-summary.yaml`.
- `portfolio.yaml` references the summary through `artifacts.executiveSummary`
  and does not duplicate the summary body.
- The HTML renderer reads the YAML artifact and renders the Executive Summary
  tab from it.
- Reports include `llmCallCount` and `llmPhases` so callers can see how many
  model calls were made and why.

## Non-Goals

- Do not create a separate leadership report page in v1.
- Do not store Executive Summary content only in HTML.
- Do not store the canonical content only in `portfolio-state.yaml`.
- Do not present all findings as equal tiles when the evidence supports a
  priority sequence.
- Do not make `portfolio render` or `portfolio sync` call an LLM.
- Do not claim that the summary is a final business strategy or accepted
  management recommendation.

## Workspace Contract

Add `executive-summary.yaml` as a package-level artifact.

Recommended shape:

```yaml
schema: https://opendataproducts.org/sdk/portfolio-executive-summary/v1
kind: PortfolioExecutiveSummary
metadata:
  generatedAt: "2026-06-28T00:00:00Z"
  generatedBy: open-data-products
  sdkVersion: "0.0.0"
  model: qwen2.5
  workspaceTitle: Customer Intelligence Portfolio
portfolioPosition:
  headline: Retention products are the strongest near-term portfolio theme.
  narrative: >
    The current portfolio is centered on retention and partner expansion.
    It has useful demand signals, but ownership and commercial readiness need
    review before leadership commits delivery capacity.
priorityBriefing:
  recommendation: Fund retention workflow validation first. Validate partner expansion next. Strengthen signal coverage before final prioritization.
  primaryFocus:
    label: Priority 1
    title: "Focus first: Retention workflow validation"
    dashboardTitle: Retention validation
    message: Retention is the clearest funding candidate because it connects a business objective, an operational use case, and a candidate product.
    dashboardMessage: Retention is the strongest first funding candidate.
    action: Fund validation of the retention workflow before assigning capacity to other portfolio paths.
    dashboardAction: Fund validation first.
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
        id: OBJ-REDUCE-CHURN
  secondaryFocus:
    label: Priority 2
    title: "Validate next: Partner expansion"
    dashboardTitle: Partner expansion
    message: Partner expansion has enough evidence to stay in the leadership discussion, but it is not ready to compete with retention for first delivery funding.
    dashboardMessage: Partner expansion is promising but not yet first priority.
    action: Validate the business case before assigning delivery capacity.
    dashboardAction: Validate the business case next.
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
  blocker:
    label: Risk
    title: "Do not ignore: Signal coverage risk"
    dashboardTitle: Signal coverage
    message: Signal coverage looks thin. This may make prioritization look more certain than it is.
    dashboardMessage: Thin signal coverage may overstate prioritization confidence.
    action: Improve signal coverage before using this portfolio view for final prioritization.
    dashboardAction: Improve coverage before final prioritization.
    rationaleTitle: Why this matters
    rationale:
      - Weak evidence can distort funding decisions
    confidence: low
    evidenceType: inferred
    evidence:
      - type: signal
        label: Churn market demand
        id: SIG-CHURN-MARKET-DEMAND
  readinessCheck:
    label: Readiness check
    title: "Before build starts: Commercial readiness review"
    dashboardTitle: Commercial review
    message: The customer health product still needs human review before production commitment.
    dashboardMessage: The product still needs business readiness review.
    action: Confirm ownership, value model, operating model, and delivery readiness.
    dashboardAction: Confirm readiness before build.
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
        id: PR-CUSTOMER-HEALTH-SIGNALS
swot:
  strengths:
    - id: STR-RETENTION-DEMAND
      statement: Retention has clear business demand and use-case pull.
      evidenceRefs:
        - type: businessObjective
          id: OBJ-REDUCE-CHURN
        - type: useCase
          id: UC-RETENTION-RISK-WORKFLOW
        - type: signal
          id: SIG-CHURN-MARKET-DEMAND
      confidence: high
      inference: false
  weaknesses:
    - id: WEAK-OWNERSHIP-GAP
      statement: Product ownership evidence is not explicit enough for a delivery decision.
      evidenceRefs:
        - type: productReference
          id: PR-CUSTOMER-HEALTH-SIGNALS
      confidence: medium
      inference: true
  opportunities:
    - id: OPP-EXECUTIVE-REVIEW
      statement: The portfolio can support an executive retention review workflow.
      evidenceRefs:
        - type: useCase
          id: UC-RETENTION-RISK-WORKFLOW
      confidence: medium
      inference: true
  threats:
    - id: THREAT-WEAK-SIGNAL-COVERAGE
      statement: Thin signal coverage may lead to over-prioritizing one product theme.
      evidenceRefs:
        - type: signal
          id: SIG-CHURN-MARKET-DEMAND
      confidence: low
      inference: true
leadershipDecisions:
  - id: DECIDE-RETENTION-INVESTMENT
    question: Should leadership fund the retention data product as the next delivery priority?
    decisionType: invest
    urgency: high
    evidenceRefs:
      - type: businessObjective
        id: OBJ-REDUCE-CHURN
      - type: productReference
        id: PR-CUSTOMER-HEALTH-SIGNALS
evidenceGaps:
  - id: GAP-OWNER
    statement: Product owner and accountable business sponsor are not clear.
    evidenceRefs:
      - type: productReference
        id: PR-CUSTOMER-HEALTH-SIGNALS
confidenceNotes:
  - Priority items marked as inferred need human review before business action.
```

`portfolio.yaml` should not duplicate the full summary. It may include a
reference:

```yaml
artifacts:
  executiveSummary: executive-summary.yaml
```

`portfolio-state.yaml` may track generation metadata and source hashes, but it
must not become the canonical source for the summary content.

## Generation Model

Use the existing LLM-backed portfolio build and refresh flow to create or
refresh `executive-summary.yaml`, but keep generation phased.

Implemented phase sequence:

1. `portfolio`: source lanes are sent to the model to produce normalized
   portfolio artifacts only.
2. `portfolioRepair`: optional one-shot YAML syntax repair for malformed
   portfolio output.
3. `executiveSummary`: the normalized portfolio plan is sent to the model to
   produce one `PortfolioExecutiveSummary` YAML document.
4. `executiveSummaryRepair`: optional one-shot YAML syntax repair for malformed
   Executive Summary output.

The normal LLM-backed build or refresh path makes two model calls:

- `portfolio`
- `executiveSummary`

Repair calls are counted only when needed. Refresh with no source changes,
`portfolio render`, and `portfolio sync` make zero model calls.

The model prompt must require:

- valid YAML matching the required shape;
- short, leadership-readable language;
- a `priorityBriefing` object with a recommendation, primary focus, secondary
  focus, blocker, and readiness check;
- optional `dashboardTitle`, `dashboardMessage`, and `dashboardAction` fields
  for compact card rendering;
- business-facing evidence labels plus technical IDs for traceability;
- confidence values: `high`, `medium`, or `low`;
- `evidenceType: inferred` when the statement is a reasoned conclusion rather
  than a direct fact from artifacts;
- evidence gaps instead of invented certainty when source material is thin.

The model prompt must forbid:

- priority claims without supporting evidence;
- generic business claims such as "strong governance" unless artifacts prove
  them;
- revenue, cost, customer, compliance, or risk claims that are not present in
  source material;
- recommendations phrased as final decisions.

The summary should be generated from the normalized portfolio plan, not raw
source files alone. That keeps the summary aligned with the artifacts that will
actually be written to the workspace.

The first-phase portfolio prompt must explicitly forbid `executiveSummary`.
The second-phase Executive Summary prompt must remove any existing
`executiveSummary` value from the normalized evidence before sending context to
the model. This prevents recursive summary drift and keeps the source of truth
clear.

## Deterministic Behavior

`portfolio render` and `portfolio sync` must stay deterministic.

Rules:

- If `executive-summary.yaml` exists, load it and render the Executive Summary
  tab.
- If it does not exist, render the tab with a clear missing-analysis state.
- Do not fabricate priority findings from heuristics during render or sync.
- `portfolio sync` may preserve, validate, and re-render an existing
  `executive-summary.yaml`, but it must not infer a new one from edited YAML.
- `portfolio refresh` regenerates the summary because it is LLM-backed and the
  portfolio evidence may have changed.

Build and refresh reports expose call accounting:

```yaml
llmCallCount: 2
llmPhases:
  - portfolio
  - executiveSummary
```

When repair is needed, the relevant repair phase appears in order:

```yaml
llmCallCount: 3
llmPhases:
  - portfolio
  - executiveSummary
  - executiveSummaryRepair
```

The fallback state should be useful but honest:

```text
Executive summary has not been generated for this workspace yet. Run a
LLM-backed portfolio build or refresh to create executive-summary.yaml.
```

The fallback can show deterministic portfolio facts such as object counts and
validation state, but those facts must not be labeled as leadership priorities.

## HTML Renderer

Add `Executive Summary` as a new top-level tab:

```text
Overview
Executive Summary
Objectives
Use Cases
Products
Signals
Graph
About
```

The tab should render:

- portfolio position headline and narrative;
- a compact recommended leadership decision;
- four compact decision cards in a 2x2 grid;
- visually distinct Priority 1, Priority 2, Risk, and Readiness treatments;
- PNG icon badges copied from `images/portfolio/` into generated workspaces
  under `assets/executive_summary_icons/`;
- blue-family treatment for both priority cards, with stronger emphasis on
  Priority 1;
- amber/orange treatment for risk and slate-violet treatment for readiness;
- leadership decisions;
- evidence gaps;
- confidence notes.

Each priority card should display:

- title;
- main finding;
- action;
- meaningful icon badge;
- confidence and evidence badges, not plain metadata text;
- collapsed details containing rationale or checklist bullets, business-facing
  evidence labels, and technical evidence IDs;
- a dropdown trigger that stays in the card footer and changes state text from
  `Show more` to `Show less`.

Confidence badges should show only High, Medium, or Low with a green, amber, or
red status dot. Evidence badges should show Direct or Inferred with a neutral
blue icon treatment.

Implemented card icons:

- Priority 1: `priority_1_trophy.png`
- Priority 2: `priority_2_growth.png`
- Risk: `risk_warning.png`
- Readiness: `readiness_clipboard.png`

The generated HTML references the copied workspace assets with relative paths
so the static portfolio can be opened locally without external dependencies.

The renderer must escape all model content. It should resolve evidence labels
from ODPC fragments, ODPS products, graph nodes, or explicit priority evidence
labels where possible. Unknown references should stay collapsed as technical
evidence so reviewers can see broken or stale links without cluttering the
leadership view.

The tab must not read like a marketing page. It should read like decision
support.

The renderer keeps `priorityBriefing` as the primary v1 layout source. Legacy
`swot` content may still exist in the YAML for compatibility and counts, but
the default UI must not render a SWOT grid or present all findings as equal
tiles.

## Machine Readability

Tools and agents should be able to inspect `executive-summary.yaml` without
parsing HTML.

Implemented API and report shape:

- `load_portfolio_workspace(...)` includes an `executive_summary` mapping.
- `explain_portfolio(...)` includes compact metadata such as
  `hasExecutiveSummary`, `priorityItemCount`, `leadershipDecisionCount`, and
  `evidenceGapCount`. Legacy `swotItemCount` may remain for compatibility while
  legacy SWOT is still accepted.
- JSON reports for build and refresh include compact artifact counts and LLM
  call accounting. `portfolio.yaml` references `executive-summary.yaml` through
  `artifacts.executiveSummary`.

Do not return the full Executive Summary body from lightweight report surfaces
unless the specific command is intended to inspect that artifact.

## Validation

Add a small internal validator for `executive-summary.yaml`.

Validation should check:

- required top-level keys;
- known priority briefing keys: `primaryFocus`, `secondaryFocus`, `blocker`,
  and `readinessCheck`;
- non-empty `title`, `message`, and `action` for each priority item;
- valid confidence values;
- evidence exists for each priority item;
- evidence reference objects include `type`, `label`, and `id` when possible;
- leadership decisions include `question`, `decisionType`, and `urgency`.

Validation should warn, not fail the whole portfolio render, when the summary is
missing. Invalid YAML should fail because the workspace cannot load it safely.

## Localization

`portfolio localize` should translate the rendered Executive Summary tab as
part of the normal HTML localization flow.

It should not rewrite `executive-summary.yaml` in v1. The canonical summary
remains in the default language. Localized HTML pages are presentation outputs,
the same as the rest of the current portfolio localization behavior.

## Tests

Focused tests in `tests/test_portfolio.py` cover:

- build writes `executive-summary.yaml` from model output;
- build makes two model calls in the normal path: `portfolio` and
  `executiveSummary`;
- malformed portfolio YAML triggers `portfolioRepair`;
- malformed Executive Summary YAML triggers `executiveSummaryRepair`;
- the first-phase portfolio prompt forbids `executiveSummary`;
- the second-phase Executive Summary prompt uses normalized portfolio evidence,
  not raw source text;
- render loads `executive-summary.yaml` and displays the Executive Summary tab;
- render shows Priority 1, Priority 2, risk, and readiness as compact 2x2
  decision cards;
- render copies Executive Summary card PNG icons into the output asset folder
  and references them from the card badges;
- card details use `Show more` and `Show less`, remain aligned in the card
  footer, and are collapsed by default;
- render shows a missing-analysis state when the YAML file does not exist;
- sync preserves and renders an existing summary without calling an LLM;
- invalid summary YAML fails with a clear error;
- priority items without evidence references are reported as validation warnings;
- localized portfolio HTML includes visible Executive Summary strings;
- `explain_portfolio` reports compact Executive Summary counts.

Keep fake model responses explicit so the schema remains locked.

## Implementation Notes

Implemented code touch points:

- `open_data_products/portfolio.py`
  - prompt rendering;
  - plan parsing and normalization;
  - artifact writing;
  - workspace loading;
  - summary validation;
  - HTML tab inputs, nav, CSS, and renderer;
  - `explain_portfolio` counts.
- `tests/test_portfolio.py`
  - fake model payloads;
  - render/sync/build/explain/localize assertions.
- `docs/development/portfolio.md`
  - workspace contract;
  - renderer behavior;
  - validation and localization notes.

Avoid adding a new CLI command in v1. The artifact is part of the portfolio
package generated by the existing workflow.

## Acceptance Criteria

The feature is ready when:

- `portfolio build` and `portfolio refresh` write `executive-summary.yaml`;
- normal LLM-backed build or refresh reports `llmCallCount: 2` and
  `llmPhases: [portfolio, executiveSummary]`;
- malformed YAML repair reports the relevant repair phase;
- `portfolio render` and `portfolio sync` are deterministic and never call a
  model;
- generated `index.html` includes the `Executive Summary` tab;
- the Executive Summary tab leads with the recommended leadership decision and
  compact decision cards;
- evidence and technical IDs are hidden in collapsed details by default;
- missing Executive Summary content produces an honest missing-analysis state;
- agents can read the summary from YAML without parsing HTML;
- `pytest -q` passes;
- `python3 -c "import open_data_products"` passes;
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
  passes.
