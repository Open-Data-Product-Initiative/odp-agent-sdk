# Maysano and SDK Integration Analysis

This note analyzes how the Maysano / MLG platform described in
`docs/development/maysano.md` could connect with the Open Data Products Python
SDK at a business level.

The source architecture document names the platform **MLG - Minimum Lovable
Governance**. This analysis treats Maysano as the product or company wrapper
around that platform.

## Executive Summary

This is an exploration document, not a final strategy. The current evidence is
enough to identify promising connection points between Maysano and the SDK, but
not enough to choose one commercial model.

The central hypothesis worth testing is:

> Maysano could become the operating layer for managing data products across
> business, governance, quality, lifecycle, and collaboration workflows. The SDK
> could become the standards execution layer underneath: validation, generation,
> contracts, catalogs, graphs, vocabulary, recipes, and agent-ready automation.

The question is not simply "can Maysano integrate the SDK?" The better question
is whether the SDK helps Maysano create clearer business value, reduce
duplicated standards logic, and tell a stronger open-standards story.

The most useful next step is to test a few concrete workflows before deciding
whether Maysano should be a commercial operating layer, a reference
implementation, an SDK-powered governance add-on, or a separate but aligned
product.

One especially important possibility is an open-source adoption path: companies
can start with the SDK because it is easier to approve, cheaper to try, and
closer to technical teams. When those teams need collaboration, governance,
portfolio visibility, permissions, lifecycle controls, and managed operating
workflows, Maysano can become the natural next step.

That means the first commercial motion may not be "buy Maysano." It may be
"adopt ODPS and prove value with the SDK." Maysano then becomes an easier
conversation because it uses the same standards and extends the same artifacts
into an operating platform.

This adoption motion can be turned into a live prospect meeting. The customer
can bring a few sanitized, non-sensitive business excerpts from common
artifacts such as PowerPoint decks, meeting notes, business objectives, pain
points, KPI notes, product ideas, backlog items, or catalog descriptions. Slide
decks should be reduced to selected slide text, speaker notes, or a short
business summary before the SDK run. The material is first classified into
rough source lanes, then the SDK is run to produce a first visible portfolio
draft. If the customer cannot bring material, the same meeting can use a
prepared example pack that shows the same business-to-portfolio conversion.

## What Maysano Already Provides

The Maysano / MLG architecture describes a full-stack TypeScript application
with a React frontend, Express backend, PostgreSQL database, Drizzle ORM,
shared types, and an AI/agent stack via OpenRouter.

At business level, the platform already covers many operating-layer concerns:

- Data product lifecycle management with authoring, versioning, publishing,
  immutable snapshots, and draft-to-production lifecycle states.
- ODPS 4.1-aligned data product records.
- Reusable governance components such as SLA profiles, data quality profiles,
  access profiles, pricing plans, KPIs, and templates.
- Business alignment through objectives, use cases, KPI links, product links,
  focus areas, and objective-to-product graph data.
- Role-based operating model with configurable permissions.
- Data integration and lineage through SQL data sources and OpenMetadata.
- Data quality monitoring through DQOps checks, incidents, scores, trends, and
  reports.
- GitHub workflows for repository links, specification pushes, pull requests,
  and synchronization.
- AI-assisted product specification building, validation, strategy generation,
  and contextual assistant workflows.
- Consumer catalog and feedback features.
- Multi-tenant and multi-environment hosting through organization scoping and
  hostname-based database routing.
- Observability around HTTP requests and AI tool execution.

That makes Maysano a business operating platform, not just a document editor.
It owns workflow, collaboration, operating model, governance process, and user
experience.

## What the SDK Adds

The SDK has grown beyond basic ODPS validation. It now provides a broader
execution layer for the Open Data Products standards family:

- Cross-spec loading, validation, explanation, reference resolution, summaries,
  and resource discovery.
- ODPS product artifact handling.
- ODPC catalog build, summary, search, HTML, TOON, and GCF artifact workflows.
- ODPG graph build, traversal, analysis, conversion, agent context, and static
  explorer generation.
- ODPV vocabulary search, resolution, explanation, relationship checks, and
  context packets.
- ODPR recipe listing, validation, dry-run planning, guarded execution, and
  starter workflows.
- Portfolio workspace workflows that connect objectives, use cases, signals,
  and products.
- Data Contract resolution, validation, schema extraction, alignment checks,
  reports, and export support.
- LLM-assisted generation of product references, signals, graphs, and ODPS
  product drafts.
- MCP server and ARWS manifest surfaces for agent hosts.
- Resource discovery for schemas, templates, prompts, vocabularies, guidance,
  and bundled standards assets.

The SDK is therefore a standards automation layer. It gives agents, CLIs, CI
jobs, and host applications a predictable way to operate on Open Data Product
artifacts.

## Exploration Options

Because the product strategy is still open, there are several plausible models.
They should be evaluated as options, not assumed as decisions.

### Option 1: Maysano as the Commercial Operating Layer

In this model, Maysano becomes the enterprise product for operating data
products, while the SDK remains the open execution layer for standards,
automation, and agents.

Why it could work:

- Strongest strategic upside.
- Clear separation between open execution layer and paid operating layer.
- Gives buyers a complete platform while keeping standards portable.
- Lets Maysano sell workflow, governance, collaboration, quality evidence, and
  lifecycle management instead of only standards compliance.

Risks:

- Requires a clearer product strategy and commercial positioning.
- Creates pressure to maintain a strong boundary between open SDK capabilities
  and paid platform capabilities.
- Needs proof that customers want an operating layer, not only tools and
  templates.

### Option 2: SDK as the Open-Source Adoption Funnel

In this model, the SDK is the easiest way for companies to get started with
Open Data Products. It gives technical teams immediate value through local
validation, generation, catalog, graph, contract, portfolio, CLI, and agent
workflows. Maysano then becomes the upgrade path when the organization needs a
shared operating layer.

Why it could work:

- Open-source tools are often easier to try than enterprise platforms.
- Developers and data teams can adopt the SDK without a procurement process.
- Successful SDK usage creates internal proof that the standards are useful.
- Maysano can sell the missing enterprise layer: collaboration, permissions,
  review workflows, lifecycle management, dashboards, evidence, and portfolio
  operations.
- The SDK creates demand from the bottom up, while Maysano monetizes the
  organizational need that appears after adoption grows.

Risks:

- The upgrade path must be obvious, or SDK users may never connect their work
  to Maysano.
- The SDK must stay useful on its own; otherwise the open-source motion looks
  like a restricted trial.
- Maysano must offer capabilities that are clearly beyond what teams can
  comfortably manage with CLI tools, GitHub, and scripts.

### Option 3: Maysano as a Reference Implementation

In this model, Maysano primarily demonstrates what an ODPS-aligned platform can
look like when built around the SDK and Open Data Products standards.

Why it could work:

- Lower strategic risk.
- Useful for demos, sales conversations, workshops, documentation, and
  ecosystem credibility.
- Helps expose gaps in the SDK without requiring a full commercial commitment.
- Gives the standards family a practical product example.

Risks:

- Weaker revenue story unless later productized.
- Could become a demo app rather than a serious operating product.
- May not justify deep engineering investment without a clear adoption path.

### Option 4: Maysano as an SDK-Powered Governance Add-On

In this model, Maysano stays focused on governance workflows and selectively
uses SDK capabilities where they reduce duplicated work or improve evidence.

Why it could work:

- Practical middle path.
- Lets the team integrate validation, portfolio, graph, and contract workflows
  incrementally.
- Avoids committing to a full platform positioning too early.
- Produces useful proof points quickly.

Risks:

- The integration may remain shallow.
- Business positioning may be less distinctive.
- Maysano could look like another governance tool with an ODPS export feature.

### Option 5: Maysano and SDK as Separate but Aligned Products

In this model, Maysano and the SDK share standards, examples, and messaging,
but neither depends deeply on the other.

Why it could work:

- Keeps product boundaries clean.
- Preserves the SDK as an independent open-source toolchain.
- Lets Maysano evolve its product UX without being blocked by SDK roadmap
  decisions.

Risks:

- Misses the strongest business synergy.
- Can lead to duplicate standards logic.
- Makes the combined story harder to explain if both products solve adjacent
  problems separately.

## Evaluation Criteria

The integration should be judged by business and operating value, not only by
technical neatness.

Useful criteria:

- Does it make Maysano easier to sell or explain?
- Does it increase SDK adoption or credibility?
- Does it create a clear path from open-source SDK adoption to Maysano demand?
- Does it reduce duplicated standards engineering?
- Does it create a stronger open-standard portability story?
- Does it produce visible business value for data product teams, governance
  teams, or data leaders?
- Does it support AI-assisted governance safely?
- Does it work across the TypeScript/Node and Python runtime boundary without
  fragile coupling?
- Does it create reusable workflows that can be shown in demos, pilots, and
  customer onboarding?
- Does it support a live kickstart meeting where customer-provided or example
  business text becomes a standards-based portfolio draft?
- Does it keep both products useful independently?
- Does it avoid hiding the SDK's open-source value inside one platform?

## Strategic Integration Model

If the exploration validates a deeper connection, the cleanest split would be:

| Layer | Maysano responsibility | SDK responsibility |
| --- | --- | --- |
| Business operating model | Users, roles, permissions, orgs, lifecycle, review, publishing | Validate and explain standards artifacts used in the process |
| Product management | Product records, assignments, discussions, feedback, dashboards | ODPS artifact generation, validation, summaries, and references |
| Governance | Reusable SLA, quality, access, pricing, KPI, and template components | Standards alignment, vocabulary checks, recipe workflows, contract reports |
| Portfolio management | Business objectives, use cases, signals, KPIs, product links | Portfolio build, refresh, sync, render, localize, and explain workflows |
| Graph reasoning | Objective-product graph views and operational graph data | ODPG build, traversal, analysis, context extraction, and explorer generation |
| Data contracts | OpenMetadata browsing, schema mapping, contract save workflows | Product-contract resolution, alignment, validation, and reports |
| AI assistant | User-facing assistant, context, permissions, streaming UX | MCP tools, schemas, resources, validation, summaries, and deterministic checks |
| Git workflow | Repo connections, PRs, sync, publishing UX | Standard artifact generation and validation before push |

This split is a candidate model, not a final decision. Its advantage is that it
avoids duplication: Maysano remains the operating product, while the SDK remains
the standards engine.

## Open-Source Adoption Funnel

The SDK being open source is not only a technical distribution detail. It could
become the main business entry point.

Many companies are more willing to start with an open-source SDK than with a
new governance platform. A technical team can install the SDK, validate
artifacts, generate ODPS drafts, build catalogs and graphs, test contract
alignment, and create portfolio outputs without a sales cycle. That lowers the
barrier to experimenting with Open Data Products.

The commercial opportunity appears when local usage becomes organizational:

- Multiple teams start producing data product artifacts.
- Governance teams need consistency, review, evidence, and lifecycle states.
- Leaders need portfolio visibility across products, use cases, objectives,
  signals, quality, and contracts.
- Teams need shared permissions, comments, approvals, assignments, dashboards,
  and publication workflows.
- Platform teams need integration with GitHub, OpenMetadata, DQOps, and
  enterprise environments.

That is where Maysano can offer more than the SDK should provide. The SDK helps
teams start. Maysano helps organizations operate.

The upgrade story could be:

1. Start with the SDK locally or in CI.
2. Generate and validate open-standard artifacts.
3. Use GitHub and generated review outputs for early collaboration.
4. When the work spreads across teams, move to Maysano for operating workflows,
   governance, permissions, portfolio visibility, and evidence management.

This model keeps the SDK valuable independently while making Maysano the
natural answer to the question: "What do we use when this becomes a real
operating process?"

### Sell ODPS First, Then Maysano

The adoption motion should start by selling the value of ODPS, not by forcing a
platform decision too early.

The sequence could be:

1. Sell the standard.
   Help the customer understand why ODPS matters: common structure, portable
   data product descriptions, better governance evidence, reusable product
   definitions, and a shared language across business and technical teams.

2. Prove the standard with the SDK.
   Use the open-source SDK to turn their existing business material into draft
   ODPS-aligned artifacts and a first portfolio view. This makes ODPS practical
   instead of theoretical.

3. Let the customer experience the operating gap.
   Once the draft exists, the next questions become obvious: who owns these
   products, who approves changes, how are versions managed, how do quality
   checks connect, how do teams collaborate, and how does leadership track the
   portfolio?

4. Introduce Maysano as the natural next step.
   Maysano does not ask the customer to abandon the SDK work. It uses the same
   standards and turns the same artifacts into governed workflows, shared
   ownership, lifecycle management, evidence, dashboards, and portfolio
   operations.

This lowers the perceived risk of adopting Maysano. The customer does not jump
from nothing into a platform. They first see their own data product portfolio
take shape through ODPS and the SDK. Maysano then feels like the operating
layer for something they already understand.

### Starter Offer: Guided Portfolio Draft

The adoption funnel needs a clear first action. The first offer should not ask
companies to start by designing a governance operating model. It should ask for
sanitized business input, classify it into source lanes, and return a visible
portfolio draft quickly.

Example offer:

> Bring sanitized, non-sensitive excerpts from business notes, meeting notes,
> PowerPoint decks, product needs, current objectives, product ideas, pain
> points, and existing data product descriptions. We classify them into source
> lanes, run the SDK workflow, and show you a first portfolio draft.

The point is to make the first step feel immediate:

1. Collect input excerpts.
   Ask for sanitized excerpts from meeting notes, PowerPoint decks, strategy
   notes, backlog items, business objectives, product requests, KPI notes, data
   quality concerns, and existing product descriptions. For slide decks, use
   selected slide text, speaker notes, or a short summary of the relevant
   slides. Do not use personal data, credentials, confidential contracts,
   regulated records, or raw customer data.

2. Convert the input into SDK source lanes.
   Sort the material into objectives, use cases, signals, and product notes.
   This is a guided human step before the SDK run. The first version does not
   need to be perfect; it only needs enough structure to create a draft.

3. Run the SDK workflow.
   Use SDK generation and portfolio commands to create draft artifacts,
   validate them, and render a reviewable portfolio page.

4. Review the draft with the customer.
   Show the first portfolio view: objectives, use cases, candidate data
   products, signals, gaps, and likely next questions.

5. Identify what becomes hard without an operating layer.
   Use the review to surface the natural Maysano needs: ownership, lifecycle
   states, assignments, review workflow, permissions, evidence, quality
   tracking, GitHub workflow, portfolio governance, and recurring updates.

This gives the SDK a simple adoption promise:

> Start with the material you already have. Get a standards-based data product
> portfolio draft quickly.

It gives Maysano a natural upgrade promise:

> When the draft becomes a real operating process across teams, Maysano gives
> you the shared workspace, governance workflow, lifecycle, evidence, and
> portfolio management layer.

This should be treated as a productized onboarding motion, not only a demo. It
could become a guide, workshop script, landing-page CTA, CLI recipe, sample
dataset, or consultant playbook.

### Live Prospect Meeting

The starter offer becomes more convincing if the SDK is run during the prospect
meeting. This changes the meeting from a platform presentation into a business
working session.

The meeting should have two modes.

**Mode A: Customer material**

This is the preferred path. The customer brings a few sanitized, non-sensitive
excerpts from common business artifacts, such as PowerPoint slide text,
speaker notes, meeting notes, strategy notes, business objectives, use case
ideas, pain points, KPI notes, data product ideas, catalog descriptions,
quality issues, or backlog items.

During the meeting, the material is reviewed quickly and manually placed into
rough source lanes: objectives, use cases, signals, candidate product notes,
quality concerns, and open questions. The SDK is then used to generate a first
standards-based portfolio draft from those structured lanes.

The value is not that the first output is perfect. The value is that the
customer sees their own business language become a structured data product
conversation. That makes the output easier to discuss, correct, prioritize, and
own.

**Mode B: Prepared example material**

This is the fallback path. If the customer cannot provide material, the meeting
uses a prepared example pack. The example pack should be realistic, slightly
messy, and business-oriented. It should include incomplete ownership, vague KPI
language, unclear product boundaries, quality concerns, overlapping use cases,
and missing lifecycle evidence.

The example pack should demonstrate the same flow:

1. Start from messy business input.
2. Convert the input into source lanes.
3. Run the SDK workflow.
4. Generate a portfolio draft.
5. Review objectives, use cases, candidate products, signals, gaps, and next
   questions.
6. Show where Maysano becomes useful when the draft needs ownership,
   permissions, review workflow, lifecycle control, evidence, and portfolio
   management.

This keeps the meeting useful even when the customer is not ready to share
anything. It also gives sales, partners, and consultants a repeatable demo
script.

Suggested prospect wording:

> Bring a few sanitized, non-sensitive business notes if you have them. If not,
> we will use realistic example material and show the same process.

Suggested meeting promise:

> Bring a few sanitized business notes or slide excerpts. We will classify them
> into source lanes, run the SDK, and show what your first data product
> portfolio could look like.

### Example Material Packs

The prepared example material should be simple enough to understand quickly,
but realistic enough to trigger business discussion.

#### Example Pack 1: Customer Experience

Input themes:

- Reduce service complaints.
- Improve customer journey visibility.
- Understand digital service usage.
- Connect call center complaints with digital service data.
- Give leadership a monthly satisfaction view.

Possible portfolio outputs:

- Customer Service Performance data product.
- Digital Service Journey data product.
- Complaint Resolution Insights data product.

Likely gaps:

- No clear product owner.
- KPI definitions are unclear.
- Data quality evidence is missing.
- No lifecycle or approval process exists.

#### Example Pack 2: Finance and Budget

Input themes:

- Improve budget forecasting.
- Reduce manual Excel reporting.
- Standardize department budget updates.
- Give leadership early warning signals.

Possible portfolio outputs:

- Budget Forecasting data product.
- Department Spend Signals data product.
- Financial Planning KPI data product.

Likely gaps:

- Source ownership is unclear.
- Refresh SLA is missing.
- Access rules are needed.
- Contract alignment is missing.

#### Example Pack 3: Open Data or Public Sector

Input themes:

- Improve public dataset value.
- Identify high-value datasets.
- Link datasets to strategic themes.
- Track publishing quality and reuse.

Possible portfolio outputs:

- High-Value Dataset Portfolio.
- Dataset Reuse Signals data product.
- Open Data Quality Evidence data product.

Likely gaps:

- Value signals are not standardized.
- Dataset ownership is unclear.
- Quality rules are missing.
- Portfolio governance is needed.

The live meeting should stay business-led. The SDK is used as evidence that the
method is executable, not as the main story.

Recommended flow:

1. Open with the business promise.
   Explain that the session starts from business material and shows how the
   customer can move toward a data product portfolio.

2. Review the input.
   Classify the material into objectives, use cases, signals, candidate
   products, quality concerns, and open questions.

3. Run the SDK.
   Generate draft artifacts, validate what can be validated, and produce a
   reviewable portfolio output.

4. Review the portfolio draft.
   Discuss which objectives are correct, which use cases matter, which products
   are real, which products are missing, and which gaps block progress.

5. Surface the operating gap.
   Ask who owns the products, who approves changes, how lifecycle is managed,
   how quality evidence is tracked, how contracts are reviewed, and how
   leadership sees progress.

6. Introduce Maysano.
   Position Maysano as the operating layer around the standards: ownership,
   permissions, assignments, review workflow, lifecycle, evidence, dashboards,
   and portfolio management.

7. Close with a scoped next step.
   Recommend one business area, one domain, or one strategic theme for a short
   follow-up pilot.

The meeting should not promise a final portfolio in one session. It should
promise a first visible draft that helps business, data, and governance teams
start the right conversation.

### Additional Packaging Motions

The ODPS-first path can be packaged in several ways. These are not competing
technical architectures. They are different commercial entry motions that all
use the same basic pattern: start with ODPS and the SDK, then move to Maysano
when the work becomes operational.

#### Assessment-to-Platform

Start with a lightweight ODPS readiness assessment. The customer provides
product docs, contracts, catalogs, meeting notes, strategy slides, quality
reports, or backlog items. The SDK is used to identify what can already be
represented as ODPS-aligned artifacts and where the gaps are.

Maysano becomes the follow-on platform for managing the remediation workflow:
owners, assignments, lifecycle states, missing evidence, contract gaps, quality
issues, and portfolio-level reporting.

This works when the buyer already knows governance is messy but does not yet
know where to start.

#### Workshop-to-Workspace

Sell a focused workshop such as a two-hour or half-day Data Product Portfolio
Sprint. During the session, use the customer's own notes and objectives to
produce a first ODPS-aligned portfolio draft with the SDK.

Maysano becomes the workspace for continuing after the workshop: review,
ownership, versioning, comments, approvals, evidence management, and recurring
updates.

This works when the buyer needs to see momentum before committing to a
platform.

#### GitHub-First

Start with developers and platform engineers. They use the SDK in GitHub,
local development, and CI to validate ODPS YAML, generate artifacts, review
changes through pull requests, and keep product definitions close to source
control.

Maysano becomes the business-facing layer when product owners, governance
teams, and leadership need a shared interface for the same artifacts.

This works when the customer has strong engineering practices and wants
standards to fit existing delivery workflows.

#### Compliance Evidence

Start by generating evidence from existing product material: ownership,
purpose, SLA, quality commitments, access rules, contract alignment, lifecycle
state, and missing governance details.

Maysano becomes the system of record for that evidence. The SDK proves that the
evidence can be expressed in open-standard artifacts; Maysano manages the
ongoing process around it.

This works when the buyer is driven by auditability, regulation, risk, or
internal governance pressure.

#### Data Contract Bridge

Start from schemas, data contracts, and quality promises. Use the SDK to check
whether product descriptions and contracts align, then show where the product
promise does not yet match the technical contract.

Maysano becomes the operating layer for managing the product, contract, data
quality profile, owner workflow, and remediation actions together.

This works when the customer already has data contract or data quality
initiatives but lacks a product operating model.

#### AI-Governance Starter

Start with the promise that AI can help draft product descriptions, portfolio
views, and governance material, but only if the outputs are validated against
standards. The SDK provides that safer AI drafting and validation path.

Maysano becomes the controlled workspace where AI-assisted work is reviewed,
assigned, approved, versioned, and connected to real operating evidence.

This works when the buyer is interested in AI but concerned about uncontrolled
or unverifiable governance output.

#### Partner Playbook

Package the SDK workflows as repeatable delivery assets for consultants,
implementation partners, or internal enablement teams. A partner can run the
portfolio draft, assessment, contract bridge, or GitHub-first workflow as a
client engagement.

Maysano becomes the platform the customer adopts after the initial engagement,
so the work does not end as static slides or exported files.

This works when growth depends on partner-led delivery or advisory services.

#### Maturity Ladder

Frame adoption as levels:

| Level | Customer behavior | Offer |
| --- | --- | --- |
| 1 | Learns ODPS concepts | Guides, examples, templates |
| 2 | Tries ODPS with real material | SDK portfolio draft and validation |
| 3 | Uses standards in delivery | GitHub, CI, contracts, generated artifacts |
| 4 | Needs shared operation | Maysano workflows, permissions, lifecycle, evidence |
| 5 | Runs continuous governance | Maysano portfolio operations and improvement loops |

This works because it makes the upgrade path explicit. The customer does not
need to jump directly to the platform; they move when their maturity requires
it.

#### Internal Champion

Help one data product lead, architect, or governance owner use the SDK to prove
ODPS value internally. The champion gets a portfolio draft, validation report,
or contract alignment story they can show to others.

Maysano becomes relevant when other teams ask to join and the champion needs a
shared operating layer instead of local scripts and files.

This works when the first buyer is not a budget owner but can create internal
pull.

#### Migration from Spreadsheets

Start with the reality that many data product portfolios live in Excel,
Confluence, PowerPoint, Jira, email, or fragmented catalog notes. Use the SDK
workflow to convert that messy material into ODPS-aligned drafts and a first
portfolio view.

Maysano becomes the replacement for the messy coordination layer: structured
records, lifecycle, ownership, review, evidence, and portfolio visibility.

This works when the customer already feels pain from manual coordination but is
not ready for a large governance transformation.

## High-Value Connection Points

### 1. Canonical ODPS Validation

Maysano currently has ODPS-specific validation and knowledge-base logic in the
platform architecture. The SDK should become the canonical standards validator
where practical.

Business benefit:

- Reduces duplicated standards logic.
- Keeps Maysano aligned with the latest SDK interpretation of ODPS and related
  standards.
- Makes validation results reusable across UI, API, CI, GitHub, and agents.
- Improves buyer confidence because validation is based on a public SDK rather
  than hidden platform-only rules.

### 2. Standard Artifact Export and Import

Maysano can store rich platform records in PostgreSQL while using the SDK to
export and validate portable ODPS, ODPC, ODPG, ODPV, ODPR, and Data Contract
artifacts.

Business benefit:

- Customers are not locked into an opaque database model.
- GitHub workflows become more meaningful because exported artifacts are
  standard, validated, and reviewable.
- Enterprises can adopt Maysano without giving up open-standard portability.
- Procurement and architecture teams get a clearer interoperability story.

### 3. Portfolio Workflow

Maysano already models objectives, use cases, KPIs, signals, and data products.
That is close to the SDK portfolio workflow, which builds connected portfolio
workspaces from objectives, use cases, signals, and products.

Business benefit:

- Maysano can move from product-by-product management to portfolio-level value
  management.
- Executives can see how products support objectives and use cases.
- Product teams can generate review pages and summaries from current operating
  state.
- Portfolio evidence can be exported, refreshed, localized, and reviewed
  outside the Maysano UI when needed.

### 4. Graph-Based Governance and Strategy

Maysano has objective-to-product graph data. The SDK can strengthen that into
an ODPG-aligned graph workflow with build, analysis, traversal, conversion, and
static explorer generation.

Business benefit:

- Makes dependencies, gaps, and governance relationships easier to inspect.
- Turns product strategy into a navigable evidence graph.
- Supports agent-assisted analysis around impact, ownership, quality, and
  value realization.
- Gives Maysano a standards-based graph story instead of a platform-only visual
  feature.

### 5. Data Contract Alignment

Maysano integrates with OpenMetadata, browses schemas, maps fields, and
generates or saves contracts. The SDK can add product-contract alignment checks,
schema summaries, external contract validation, and product-level reports.

Business benefit:

- Bridges the gap between product descriptions and technical data contracts.
- Gives platform users earlier warnings when a product promise does not match
  the underlying contract.
- Makes quality, SLA, access, and schema commitments more auditable.
- Strengthens the GitHub and CI story because contracts can be validated before
  merge or publish.

### 6. Agent-Ready Assistant Grounding

Maysano already has an AI assistant and agent/tool-execution stack. The SDK
adds deterministic tools that the assistant can call for standards-aware
answers and checks.

Business benefit:

- Reduces reliance on prompt-only standards knowledge.
- Lets the assistant validate, summarize, search vocabulary, inspect catalogs,
  explain artifacts, and plan recipes using SDK-backed tools.
- Creates a safer AI story: the assistant can recommend changes, but SDK
  validation and dry-run planning can check them.
- Makes Maysano attractive for organizations that want AI-assisted governance
  without uncontrolled AI writes.

### 7. Recipe-Driven Operating Patterns

ODPR recipes could encode repeatable Maysano operating workflows, such as:

- Create product from source notes.
- Validate ODPS completeness.
- Link product to objectives and use cases.
- Check contract alignment.
- Build or refresh portfolio.
- Generate graph review artifacts.
- Prepare GitHub pull request evidence.
- Run pre-publish governance checks.

Business benefit:

- Converts best practices into repeatable workflows.
- Makes onboarding easier for new customers.
- Gives consultants and implementation partners packaged playbooks.
- Creates a path from lightweight platform adoption to mature operating model.

## Business Benefits of Integration

### Benefits for Maysano

- Stronger standards credibility: Maysano can claim alignment with an executable
  open standards toolchain, not just ODPS-inspired fields.
- Lower standards-maintenance burden: validation, vocabulary, graph, contract,
  catalog, and recipe logic can come from the SDK.
- Better AI reliability: assistant workflows can be grounded in SDK resources
  and deterministic checks.
- Better enterprise sales story: business users get workflow; architects get
  portable artifacts; governance teams get repeatable controls.
- Stronger ecosystem position: Maysano becomes the operating layer around open
  data product standards.
- Faster roadmap execution: new SDK capabilities can become platform features
  without rebuilding every standards function inside Maysano.

### Benefits for the SDK

- Real product host: the SDK gets a concrete enterprise operating environment.
- Stronger proof of value: SDK workflows become visible business workflows, not
  only CLI examples.
- Better feedback loop: Maysano can reveal where SDK APIs, commands, recipes,
  and validation outputs need to improve for real platform use.
- Broader adoption path: some users will start with the SDK; others will start
  with Maysano and later use SDK automation in CI, GitHub, or agents.
- Better narrative: the SDK becomes the execution layer that powers an actual
  data product operating model.

## Recommended Business Positioning

At this stage, positioning should remain exploratory. The team should avoid
claiming that Maysano is already the commercial operating layer until that has
been validated through concrete workflows and market feedback.

The working hypothesis should avoid saying only that "Maysano integrates the
SDK." That sounds like a technical feature.

Stronger positioning:

> Maysano turns open data product standards into an enterprise operating layer.
> The SDK makes those standards executable through validation, generation,
> contracts, catalogs, graphs, recipes, and agent-ready automation.

Alternative short form:

> Maysano manages the business of data products. The SDK executes the standards
> behind them.

This makes the relationship clear:

- Maysano is the product experience and operating model.
- The SDK is the standards execution layer.
- Together they create a standards-based data product operating system.

Exploratory version:

> We are testing whether Maysano can productize the SDK's standards execution
> layer into a practical operating layer for governed data products.

That wording leaves room to learn without overcommitting the strategy.

## Suggested Exploration Roadmap

The next step should not be a full integration program. It should be a small
set of workflow tests that reveal whether the connection creates enough value.

### Phase 1: Validate the Standards Foundation

- Use SDK validation for ODPS artifacts where Maysano currently relies on
  custom validator logic.
- Add export/import paths for ODPS product artifacts.
- Generate SDK-compatible summaries for products and product versions.
- Add validation evidence to publish and GitHub push workflows.

Question to answer:

> Does the SDK reduce duplicated standards work and improve trust in Maysano's
> product lifecycle?

### Phase 2: Test Portfolio and Graph Value

- Map Maysano objectives, use cases, signals, and products into SDK portfolio
  lanes.
- Use SDK portfolio build, refresh, render, and explain workflows for review
  outputs.
- Use SDK ODPG workflows to build or validate graph artifacts.
- Add graph analysis outputs to governance and strategy views.

Question to answer:

> Does the SDK create portfolio-level business value that Maysano does not
> already provide through its own UI and database?

### Phase 3: Test Contracts and Quality Alignment

- Use SDK product contract commands around generated or saved data contracts.
- Add product-contract alignment reports to product detail and publish flows.
- Connect DQOps quality evidence to ODPS quality commitments where possible.
- Store validation and alignment results as product evidence.

Question to answer:

> Does standards-based contract alignment make Maysano's governance workflow
> more credible and actionable?

### Phase 4: Test Agent and Recipe Automation

- Expose selected SDK capabilities to the Maysano assistant through controlled
  backend tools or MCP.
- Keep write operations behind explicit platform permissions and review states.
- Add ODPR recipes for repeatable operating workflows.
- Use dry-run plans before any automated writes, GitHub pushes, or publish
  actions.

Question to answer:

> Can Maysano safely turn SDK capabilities into repeatable operating workflows
> without creating risky automated write paths?

## Best Next Experiment

The best next experiment is not to integrate everything. It is to prove the
connection through three workflows:

0. **Portfolio draft from messy business input**
   Take sanitized excerpts from meeting notes, PowerPoint decks, business
   objectives, product requests, pain points, KPI notes, or catalog
   descriptions. Classify them into SDK source lanes and render a first
   portfolio draft. If the customer cannot provide material, use a prepared
   example pack with realistic business input. This tests whether the
   open-source SDK can create immediate business-visible value before Maysano is
   introduced as the operating layer.

1. **ODPS validation in the Maysano lifecycle**
   Export a Maysano product as an ODPS artifact, validate it with the SDK, and
   show the result in a publish or review flow.

2. **Portfolio generation from Maysano operating data**
   Map a small set of objectives, use cases, signals, and products into SDK
   portfolio inputs, then build and render a reviewable portfolio workspace.

3. **Product-contract alignment**
   Take a Maysano product and a generated or saved data contract, then use the
   SDK to produce an alignment report that can be attached to the product.

These workflows are valuable because they test the main integration claims:

- The SDK can reduce duplicated standards logic.
- Maysano can turn SDK outputs into business-facing evidence.
- The runtime boundary between TypeScript and Python is manageable.
- The combined story is stronger than either product alone.
- Open-source SDK usage can create a credible path toward Maysano adoption.

If these workflows produce a compelling demo and reduce real engineering
duplication, then it becomes reasonable to explore Maysano as the commercial
operating layer. If they do not, the safer path is to keep Maysano and the SDK
separate but aligned.

## Main Risks

### Duplicate Standards Logic

If Maysano keeps its own ODPS validator, knowledge base, graph model, contract
checks, and AI generation rules while the SDK evolves separately, the two
systems will drift.

Mitigation:

- Let Maysano own platform workflows and persistence.
- Let the SDK own standards interpretation and validation wherever practical.
- Keep adapter boundaries explicit.

### Runtime Boundary Between TypeScript and Python

Maysano is TypeScript/Node. The SDK is Python. Direct in-process reuse is not
the natural boundary.

Mitigation:

- Start with CLI or service-style calls for validation and artifact generation.
- Use JSON output as the integration contract.
- Consider a dedicated SDK service only when usage volume or latency requires
  it.
- Use MCP or ARWS where agent-host integration is the real need.

### Customer Input Sensitivity

The live kickstart meeting depends on customer-provided business material, but
prospects may hesitate to share internal content. There is also a risk that
they share more sensitive content than intended, especially when decks or
exports include hidden notes, screenshots, names, or operational details.

Mitigation:

- Ask only for non-sensitive business-level material.
- For PowerPoint decks, use selected slide text, speaker notes, or a sanitized
  summary instead of the full deck when possible.
- Accept pasted text during the meeting instead of requesting documents in
  advance when needed.
- Provide a prepared example pack when the customer cannot share material.
- State clearly that no personal data, credentials, confidential contracts,
  regulated records, or raw customer data should be used.
- Keep the first workflow focused on structure, portfolio logic, and gaps, not
  deep analysis of sensitive details.

### Over-Automating AI Actions

Maysano has an assistant and the SDK has agent-ready surfaces. Combining them
too aggressively could create unsafe write paths.

Mitigation:

- Start with read-only and validation capabilities.
- Use dry-run recipes before execution.
- Require Maysano permissions and lifecycle state checks for writes.
- Keep publish, GitHub push, and contract-changing actions explicit.

### Confusing Product Boundaries

If the SDK is presented as part of Maysano only, its open-source ecosystem value
gets hidden. If Maysano is presented as just a UI for the SDK, its enterprise
operating-layer value gets undersold.

Mitigation:

- Message the SDK as the open standards execution layer.
- Message Maysano as the enterprise operating layer.
- Keep both useful independently, but stronger together.

## Conclusion

The current conclusion should remain conditional. The most promising business
relationship is not "SDK inside Maysano" in a narrow technical sense. The
stronger hypothesis is:

> Maysano could productize the SDK's standards execution capabilities into a
> business operating layer for data products.

If validated, that would give Maysano an open, credible, automatable standards
foundation and give the SDK a real enterprise workflow environment. Together
they could cover the path from business objective to governed data product,
contract, quality evidence, graph, catalog, portfolio review, and agent-assisted
operation.

If the validation does not show enough business value, the better outcome is to
keep Maysano and the SDK separate but aligned, with shared standards,
interoperable artifacts, and selective integration points.
