# SDK Workflow Recipes GUI Plan

This plan describes a proposed web app for SDK workflow recipes. It is not
implemented yet.

The existing [SDK Workflow Recipes Plan](sdk-workflow-profiles-plan.md)
describes the recipe contract: named, repeatable SDK workflows with inputs,
outputs, providers, context formats, gates, and review policy. This GUI plan
describes the human-facing workbench that could make those recipes easier to
inspect, configure, run, and review.

The GUI should not become a second workflow engine. The SDK recipe contract and
CLI/API runner should remain the source of truth. The web app should sit on top
of that layer and expose the same recipes, validation results, dry-run plans,
run manifests, generated artifacts, and review gates in a browser.

## Core Idea

SDK workflow recipes are useful only if teams can understand and operate them.
YAML and CLI commands are a good developer contract, but many business,
governance, data office, and portfolio stakeholders need a browser surface for
repeatable work:

- choose a known workflow;
- inspect what it will read, write, and call;
- confirm the provider and execution policy;
- run a dry-run before changing files;
- monitor each step;
- review warnings, evidence gaps, and generated outputs;
- approve or reject gates before publishing.

The GUI should therefore be a recipe operations console. It should make the
planned ODPR workflow layer visible without hiding the underlying contract.
Users should always be able to see which recipe file, provider, command, input,
output, and validation result is behind each screen.

## Product Positioning

The web app should be framed as an SDK workflow workbench, not a generic admin
dashboard.

It should focus on Open Data Products work:

- data product fragment drafting;
- catalog and graph build workflows;
- portfolio build, refresh, sync, render, localize, and explain workflows;
- compact context choices such as GCF and TOON;
- local, hosted, and hybrid LLM execution;
- validation gates and human review.

The first version should avoid user management, billing, generic project
management, multi-tenant SaaS features, and drag-and-drop orchestration. Those
features would distract from the important risk: proving that recipes are
safe, repeatable, inspectable, and reviewable.

## User Roles

The GUI should support four practical roles without creating a heavy permission
system in the first version.

### Developer

Developers need to open a project, validate recipe files, dry-run changes,
inspect the exact SDK command plan, and debug failed steps. They should be able
to copy equivalent CLI commands from the browser.

### Data Product Owner

Product owners need to see which products, catalogs, graphs, localized pages,
and reports a recipe will update. They need clear warnings when generated
content is draft-only or requires review.

### Governance Reviewer

Reviewers need to inspect validation status, evidence gaps, policy warnings,
provider choices, generated outputs, and approval gates. Their main action is
not editing YAML. It is approving, rejecting, or asking for changes.

### AI Agent Operator

Agent operators need the same recipe metadata that agents need: allowed steps,
write scope, provider policy, review requirements, dry-run output, and run
manifests. The GUI should make agent execution inspectable rather than opaque.

## Primary Workflows

### 1. Recipe Library

The landing screen should show available recipes from the current project and
bundled starter recipes.

Each recipe row should show:

- recipe name and type;
- short description;
- execution mode: local, hosted, hybrid, deterministic, or mixed;
- provider references;
- expected inputs and outputs;
- gate count and review requirement;
- last run status when available.

The user should be able to open a recipe detail page before running anything.

### 2. Recipe Detail

The recipe detail page should show the contract in human terms:

- metadata and version;
- source recipe path;
- inputs and whether they exist;
- outputs and whether they would be created or changed;
- steps in execution order;
- provider and model policy;
- context format policy;
- run policy such as timeout, retries, chunk size, and write scope;
- gates and review requirements;
- equivalent CLI commands.

This page should include a raw YAML view. The GUI should make YAML easier to
read, not make it disappear.

### 3. Validate And Dry-Run

Before a run, the GUI should call the same validation and dry-run behavior as
the recipe CLI:

```bash
open-data-products recipe validate release-portfolio-review.yaml
open-data-products recipe run release-portfolio-review.yaml --dry-run --json
```

The dry-run view should show:

- resolved provider precedence;
- resolved step list;
- inputs and outputs;
- files that may be written;
- commands that would run;
- safety warnings;
- missing config or credentials;
- validation errors;
- review gates.

No state-changing run should be available until validation passes. If a recipe
has warnings but remains runnable, the GUI should make those warnings explicit.

### 4. Run Monitor

The run monitor should show one recipe execution as a step timeline.

Each step should show:

- status: pending, running, passed, warned, failed, skipped, or review-needed;
- start and end time;
- provider and model when a model is used;
- deterministic or LLM-backed classification;
- logs or structured messages;
- validation results;
- generated artifact links;
- evidence gaps and review notes.

The first implementation can poll a local run record. It does not need a
distributed job queue. The important design point is that every visible status
comes from a run manifest, not from browser-only state.

### 5. Artifact Review

After a run, the GUI should make generated artifacts reviewable:

- ODPS product YAML;
- ODPC catalog YAML and fragments;
- ODPG graph YAML and rendered graph view;
- portfolio `index.html` and localized pages;
- JSON reports;
- compact context sidecars such as TOON and GCF when produced.

The review view should separate generated drafts from accepted artifacts. It
should show validation warnings, review notes, and evidence gaps next to the
artifact they affect.

### 6. Gate Approval

Recipes can require human review before publishing or continuing. The GUI
should support a simple gate flow:

- show the gate reason;
- show required evidence or outputs;
- allow approve, reject, or request changes;
- write the decision into the run manifest or a companion review record;
- never modify canonical ODPS, ODPC, ODPG, or ODPV artifacts only because a
  browser control was clicked.

The first version can keep approvals local and file-based. A later version can
add stronger identity and audit integrations.

## Screen Map

The first GUI should stay small:

```text
Recipe Library
  -> Recipe Detail
       -> Validate / Dry-Run
       -> Run Monitor
            -> Artifact Review
            -> Gate Approval

Settings
  -> Provider Profiles
  -> Project Paths
  -> Runtime Checks
```

Settings should be operational, not decorative. The user needs to know whether
local providers are reachable, whether hosted provider environment variables
are set, whether configured input paths exist, and whether the SDK can write to
the selected output paths.

## Data Flow

The GUI should use a thin local service over the SDK rather than reimplementing
recipe logic in frontend code.

```text
Browser UI
  calls local web service

Local web service
  loads recipe files
  calls SDK recipe validation
  calls SDK dry-run
  starts recipe runs
  reads run manifests
  serves artifact previews

SDK recipe layer
  resolves providers and config
  executes deterministic and LLM-backed steps
  writes outputs and reports
  writes run manifests
```

The local service can start as a developer-only process. The SDK currently has
no web framework dependency, so the first implementation should evaluate the
smallest acceptable dependency surface instead of adding a large application
stack by default.

## Run Manifest Contract

The GUI depends on a stable run manifest. A browser cannot reliably explain a
workflow unless each execution produces structured evidence.

A run manifest should include at least:

- recipe id, recipe version, and recipe file path;
- SDK version;
- run id and timestamps;
- resolved provider and model per step;
- provider mode: local, hosted, hybrid, or deterministic;
- source input hashes;
- context format choices;
- planned writes;
- actual writes;
- validation results;
- warnings;
- review notes;
- evidence gaps;
- gate decisions;
- final status.

The GUI should read this manifest after dry-runs and real runs. That keeps CLI,
agent, CI, and browser behavior aligned.

## Safety Model

The GUI should inherit the SDK safety boundary:

- recipe validation and dry-run before state-changing execution;
- explicit write scope in the recipe or resolved run policy;
- provider config validation before model calls;
- human review gates for production or publishing workflows;
- no hidden remote schema loading at validate time;
- no destructive operations without an explicit recipe policy;
- equivalent CLI command visibility for every run.

The GUI should not add state-changing MCP tools. MCP can remain read-only for
discovery, validation, and manifest inspection until the recipe runner has a
strong enough execution contract.

## Implementation Phases

### Phase 0: Contract First

Build or finalize the recipe contract, validation, dry-run, and run manifest
before building a full GUI. The browser can only be reliable if those backend
surfaces exist.

Deliverables:

- recipe schema draft;
- `recipe validate`;
- `recipe explain`;
- `recipe run --dry-run --json`;
- run manifest shape;
- example recipes for fragment generation and portfolio review.

### Phase 1: Read-Only Workbench

Create a local web app that can list recipes, show details, validate them,
show dry-run plans, and preview existing artifacts. It should not execute
state-changing runs yet.

Deliverables:

- recipe library screen;
- recipe detail screen;
- validation and dry-run screen;
- provider/runtime checks;
- artifact preview from existing files;
- equivalent CLI commands.

### Phase 2: Controlled Local Runs

Allow users to run recipes from the GUI after validation passes. Keep execution
local and file-based. Use the run manifest as the only source of run status.

Deliverables:

- run monitor;
- step status timeline;
- structured warnings and failures;
- generated artifact links;
- run history loaded from manifest files.

### Phase 3: Review Gates

Add human review support for recipes that require approval before publishing or
promotion.

Deliverables:

- review-needed state;
- artifact review screen;
- approve, reject, and request-changes actions;
- local review records or run-manifest gate decisions;
- visible audit trail.

### Phase 4: Team And Deployment Options

Only after local runs and review gates are stable, consider broader deployment
models.

Possible later work:

- hosted internal service;
- authentication and identity;
- shared run history;
- CI integration views;
- repository pull request links;
- policy packs for organization-specific gates.

## Technical Direction

The first implementation should prefer a conservative architecture:

- keep SDK recipe validation, dry-run, execution, and manifests in Python;
- expose a small local HTTP service for browser use;
- keep the frontend as a focused operational UI;
- avoid duplicating command construction logic in JavaScript;
- treat the recipe file and run manifest as the API contract between CLI,
  agents, CI, and GUI.

If a web framework is needed, choose it deliberately when implementation begins.
The current SDK has no web framework dependency, so this planning document does
not prescribe FastAPI, Flask, Django, React, or another stack yet.

## Non-Goals

The first GUI should not:

- replace the CLI;
- replace recipe YAML;
- become a generic workflow builder;
- store secrets;
- add a database requirement;
- require a hosted service;
- introduce multi-tenant access control;
- bypass validation and dry-run;
- treat LLM output as accepted product truth;
- edit canonical standards artifacts without explicit user action.

## Open Questions

- Should the first GUI live inside this SDK package, or in a sibling web-app
  repository that depends on the SDK?
- Should the local service be installed as an optional extra such as
  `open-data-products[web]`?
- Should recipe run history live under the project workspace, under a hidden
  `.open-data-products/` folder, or beside each recipe?
- Which two starter recipes should become the first GUI demos:
  `dev-fragment-draft`, `release-portfolio-review`, or another pair?
- Should approvals write into the run manifest, a separate review file, or both?

## Recommended First Cut

The first useful GUI should be a local, read-only workbench:

1. list recipe files;
2. show recipe details;
3. validate recipes;
4. run dry-runs;
5. preview existing artifacts and warnings;
6. show equivalent CLI commands.

This avoids the biggest risk: adding a browser that can mutate files before
the recipe runner, policy model, and run manifest are stable. Once the dry-run
and manifest contract is proven, controlled local execution and review gates
can be added without changing the product direction.
