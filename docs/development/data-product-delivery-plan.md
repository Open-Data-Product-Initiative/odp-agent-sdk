# AI-Assisted Data Product Delivery Plan

This plan describes a proposed ODPR-backed SDK feature that generates a
delivery-ready recipe for building, validating, governing, and operating a data
product. The output should help product owners, developers, data engineers,
platform teams, and AI agents move from structured business context to
developer-controlled implementation work.

The important boundary is that the SDK should plan the data product foundation,
not default to dashboard, report, or BI screen generation.

Implementation status: proposed.

## Positioning

Data product standards describe what the product is. Data contracts describe
producer-consumer expectations. Data mesh describes ownership and
decentralization. AI coding agents help implement work faster.

The weak middle layer is the repeatable delivery recipe:

- What ingredients exist?
- What is missing?
- What needs preparation?
- What must be built?
- What checks must pass?
- How will the product be consumed?
- How will it be operated?
- What are AI agents allowed to do?
- Where must developers approve?

ODPR should fill the gap between data product specification and data product
delivery. It should turn data product context into a repeatable recipe for
human and AI-assisted delivery.

The best claim is not that ODPR invents recipes. The better claim is that ODPR
standardizes the missing recipe layer between product specification and
controlled AI-assisted data product delivery.

## Industry Fit

The SDK should position the standards family this way:

- ODPS: product definition.
- ODCS or data contracts: interface and producer-consumer commitments.
- ODPG: product relationships and portfolio graph.
- ODPR: delivery and operating recipe.
- SDK: execution support and automation.

Data contracts already connect business meaning and technical implementation
through schema, quality rules, SLA, and behavior. They focus heavily on
producer-consumer agreements, often at the dataset or interface level. They do
not usually describe the full data product delivery recipe across objectives,
use cases, signals, access, lifecycle, relationships, readiness, AI-agent
context, and operational work.

Data product thinking has moved toward reusable, governed, value-driven assets
with ownership, lifecycle, quality, contracts, policies, and measurable value.
That supports this direction because a data product is more than a dataset or
dashboard. It needs product structure and operating logic.

AI coding agents create new urgency. Agents need strong project context,
architecture rules, interface specs, workflows, and policies to work safely.
AGENTS.md-style files provide repo-level instructions, but ODPR should provide
data-product-specific context and delivery recipes instead of generic project
instructions, random prompt files, or workflow automation alone.

## Operational Value

The industry does not need another document format for its own sake. ODPR has
value only if it becomes executable or at least operational through the SDK.

The SDK workflow should therefore produce outputs such as:

- readiness score
- missing ingredients
- open questions
- delivery steps
- validation gates
- test plan
- AI-agent brief
- developer review checklist
- backlog items
- CI validation hooks later

Business intent is rich but unstructured. Specifications structure the product.
Recipes structure the path to delivery. AI agents accelerate the work.
Developers control the result.

## Goal

Add a CLI workflow that turns structured product context into a Markdown plan
package backed by an ODPR delivery recipe. The package should cover the data
product's purpose, ownership, interfaces, access,
contracts, quality rules, SLA expectations, lifecycle, dependencies,
validation needs, test needs, operational readiness, risks, open questions, and
AI-agent context.

The plan should close the gap between business intent and delivery-ready data
product work. It should be useful before implementation starts and should keep
developers in control of any code changes.

## Non-Goals

- Do not generate dashboards by default.
- Do not generate BI layouts or chart recommendations in v1.
- Do not make automatic code changes.
- Do not deploy data products automatically.
- Do not create tickets or backlog items in external systems without explicit
  approval.
- Do not treat a consumption interface as the product definition.

## Core Flow

```text
business context
  -> structured data product specification
  -> validation output
  -> data product delivery plan
  -> AI-agent brief
  -> developer-controlled implementation
```

## Proposed CLI

Keep the workflow under the existing unified CLI contract:

```bash
open-data-products build-plan generate \
  --input ./product-context/ \
  --output ./data-product-plan/ \
  --target codex
```

The command should accept structured ODPS, ODPC, and ODPG context where
available. Missing or weak fields should become open questions, risks, and
readiness gaps rather than hidden assumptions.

ODPR should be the recipe layer behind the generated plan. The SDK may render
Markdown for human review, but the underlying structure should remain
operational enough for validation, repeat runs, and future CI hooks.

## Output Package

The command should write a folder of reviewable Markdown artifacts:

```text
data-product-plan/
  README.md
  product-summary.md
  delivery-plan.md
  product-interface-plan.md
  access-plan.md
  contract-plan.md
  quality-plan.md
  sla-plan.md
  lifecycle-plan.md
  product-relationship-plan.md
  validation-plan.md
  test-plan.md
  operational-readiness.md
  developer-review-checklist.md
  risk-register.md
  open-questions.md
  ai-agent-brief.md
  backlog-items.md
```

## Product Boundary

A dashboard is a consumption layer. A data product is a managed product with
ownership, purpose, access, quality, SLA, lifecycle, and consumers.

Possible consumers include:

- AI agents
- APIs
- applications
- notebooks
- analytical tools
- catalogs
- workflows
- dashboards
- other data products

The generated delivery plan should help teams build the product foundation.
Dashboards may appear only as one possible consumer interface when the
structured product context clearly requires them.

## Product Summary

The generated `product-summary.md` should summarize:

- product name
- product purpose
- business objective
- value statement
- product owner
- accountable domain
- consumers
- use cases
- signals
- expected outcomes
- product type
- maturity status

## Product Interface Plan

The generated `product-interface-plan.md` should describe the interfaces the
data product needs. Examples include:

- API access
- file-based access
- event stream
- query endpoint
- semantic layer
- catalog entry
- AI-agent readable context
- embedded application access
- downstream product dependency

The SDK should not assume the interface is a dashboard.

## Access Plan

The generated `access-plan.md` should describe:

- who needs access
- why access is needed
- access method
- authentication needs
- authorization needs
- public, internal, restricted, or confidential access level
- access approval process
- consumer onboarding needs

## Contract Plan

The generated `contract-plan.md` should describe:

- expected schema
- consumer expectations
- producer commitments
- allowed changes
- breaking change handling
- versioning needs
- compatibility expectations
- contract validation tasks

## Quality Plan

The generated `quality-plan.md` should describe:

- required quality dimensions
- validation rules
- blocking checks
- warning checks
- freshness expectations
- completeness expectations
- accuracy expectations
- monitoring needs
- issue escalation path

## SLA Plan

The generated `sla-plan.md` should describe:

- availability expectation
- refresh expectation
- response expectation
- incident response expectation
- support model
- escalation owner
- measurement method

## Lifecycle Plan

The generated `lifecycle-plan.md` should describe:

- product status
- development stage
- review stage
- publication stage
- operation stage
- deprecation rules
- versioning rules
- change management process

## Product Relationship Plan

The generated `product-relationship-plan.md` should describe:

- upstream data products
- downstream data products
- shared objectives
- shared signals
- dependencies
- possible conflicts
- portfolio-level gaps

## Validation Plan

The generated `validation-plan.md` should describe:

- specification validation
- contract validation
- quality validation
- access validation
- SLA validation
- relationship validation
- documentation validation
- readiness validation

## Test Plan

The generated `test-plan.md` should include:

- schema tests
- contract tests
- quality rule tests
- access tests
- SLA tests
- lifecycle tests
- integration tests
- consumer acceptance tests
- AI-agent context tests

## AI-Agent Brief

The generated `ai-agent-brief.md` should prepare a coding agent to assist with
delivery without taking control away from developers.

It should include:

- product context
- required product interfaces
- access requirements
- contract expectations
- quality rules
- SLA rules
- lifecycle rules
- dependencies
- validation requirements
- test requirements
- constraints
- open questions
- instruction to produce a plan before code
- instruction to avoid changing unrelated files

The brief should not ask the agent to create a dashboard unless the product
specification clearly requires one.

## Backlog Items

The generated `backlog-items.md` should focus on data product work. Example
items:

- Define accountable product owner.
- Confirm product consumers.
- Implement access component.
- Add contract validation.
- Add quality rules.
- Add SLA monitoring.
- Add lifecycle status.
- Add product relationship links.
- Add catalog metadata.
- Add AI-agent context package.
- Create consumer onboarding documentation.
- Add automated validation to CI.

## Readiness Scoring

The SDK should score readiness for data product delivery, not dashboard
delivery. Suggested scoring areas:

- ownership readiness
- objective readiness
- use case readiness
- signal readiness
- access readiness
- contract readiness
- quality readiness
- SLA readiness
- lifecycle readiness
- relationship readiness
- operational readiness
- AI-agent context readiness

## Risk Detection

The SDK should identify risks such as:

- product owner missing
- consumer unclear
- value unclear
- access model missing
- contract missing
- quality rules weak
- SLA missing
- lifecycle undefined
- upstream dependency unclear
- downstream dependency unclear
- product confused with dashboard
- AI-agent context incomplete

## Open Questions

The SDK should turn missing or ambiguous input into explicit questions. Example
questions:

- Who owns this data product?
- Which consumers use this product?
- Which business objective does this product support?
- Which signals prove product value?
- What interfaces should this product expose?
- What access model applies?
- What contract must consumers rely on?
- What quality rules must block delivery?
- What SLA must be measured?
- What lifecycle stage is this product in?
- Which products depend on this product?
- Which AI agents or workflows need this product context?

## MVP Scope

The MVP should include:

- CLI command for data product delivery plan generation
- ODPS, ODPC, and ODPG input support
- validation output support
- Markdown output
- data product readiness scoring
- open questions
- risk register
- backlog items
- generic AI-agent brief
- deterministic non-LLM mode

The MVP should exclude:

- dashboard generation
- BI layout generation
- chart recommendations
- automatic code changes
- automatic deployment
- automatic ticket creation without approval

## Acceptance Criteria

The MVP is complete when:

- the SDK generates a data product delivery plan from a valid product spec
- the generated plan is backed by an ODPR recipe structure rather than a
  one-off prompt response
- the plan focuses on product interfaces, access, contracts, quality, SLA,
  lifecycle, and relationships
- the plan does not assume dashboard delivery
- the SDK generates an AI-agent brief for developer-controlled implementation
- missing product fields become open questions
- weak product context becomes risks
- output is deterministic in non-LLM mode
- tests cover complete and incomplete product specs
- documentation explains that dashboards are possible consumers, not the
  product itself
- documentation explains ODPR as the missing recipe layer between product
  specification and controlled AI-assisted delivery

## Key Sentence

ODPR turns data product context into a repeatable recipe for human and
AI-assisted delivery, while the SDK makes that recipe operational and keeps
developers in control.
