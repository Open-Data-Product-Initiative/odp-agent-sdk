# Portfolio Workflow Phased Plan

This plan defines the SDK's portfolio workflow layer. The goal is to turn
multiple evidence streams into one maintained Open Data Products portfolio:
ODPC catalog objects, ODPS product specifications, an ODPG graph, and one
human-readable browser experience.

The low-level `generate` command remains useful for single artifacts. The new
portfolio workflow should orchestrate those capabilities and preserve identity,
links, state, and rendered views across reruns.

## Core Idea

Users often start from business objectives, use cases, market signals, product
discussions, emails, meeting notes, and transcripts. Product specifications are
only one part of the portfolio, and they are not always the first input.

The SDK should support this flow:

1. Create a portfolio from existing source folders with one command.
2. Generate connected ODPC, ODPS, and ODPG artifacts from the same evidence set.
3. Render one `index.html` with tabs for catalog views, artifact details, and
   graph exploration.
4. Maintain the portfolio later with targeted refresh, render, explain, and
   linking commands.

The build command must be non-interactive. It should not stop for human review,
approval, link confirmation, or artifact selection between start and finish.
Users should be able to run one command, wait for completion, and open the
generated `index.html` in a browser.

## Workspace Contract

The portfolio workflow should create and maintain a workspace at a path chosen
by the user. Examples use `portfolio/`, but the command must allow any output
directory such as `generated/portfolio/`, `/tmp/demo-portfolio/`, or a project
folder committed by the user.

```text
portfolio/
  index.html
  portfolio.yaml
  portfolio-state.yaml
  sources/
  odpc/
    catalog.yaml
    fragments/
      business_objective_*.yaml
      use_case_*.yaml
      signal_*.yaml
      product_reference_*.yaml
  odps/
    products/
      odps_product_*.yaml
  odpg/
    graph.yaml
```

`portfolio.yaml` is the human-readable source of truth for generated objects and
links. It records objectives, use cases, signals, product references, ODPS
product specs, evidence links, confidence, and unresolved gaps.

`portfolio-state.yaml` is the rerun state file. It records source file hashes,
stable generated IDs, artifact paths, and previous generation decisions.

## Filesystem Behavior

Portfolio commands must create all required folders before writing files. Users
should not have to pre-create the workspace, `odpc/`, `odpc/fragments/`,
`odps/`, `odps/products/`, `odpg/`, or any parent directory implied by
`--output`.

Any helper that writes YAML, HTML, state, or map files should call
`mkdir(parents=True, exist_ok=True)` on the target parent directory before
writing. Commands should fail only when an input path is missing or invalid, not
because an output folder was absent.

## HTML Experience

`<workspace>/index.html` should be one static browser-openable page. Catalog
and graph must not feel like separate products. They are views of the same
portfolio.

Required tabs:

- Overview
- Business Objectives
- Use Cases
- Products
- Signals
- Graph
- About

Each tab must include human-readable cards and detailed in-page views for its
artifacts. Users should be able to inspect business objectives, use cases,
signals, product references, and product specs without opening raw YAML first.

Artifact detail views should show:

- the artifact name, stable ID, status, priority, confidence, and type when
  present;
- description, source evidence, and evidence gaps;
- related objectives, use cases, signals, products, and graph nodes;
- generated links and raw YAML artifact paths;
- warnings or weak-link notes relevant to that artifact.

The Products tab has an extra two-layer model. Product cards come from ODPC
`ProductReference` objects. Product detail panels come from linked ODPS product
specs.

Product detail views should show:

- product name, `productID`, status, visibility, and type;
- description and source evidence;
- related objectives, use cases, and signals;
- access, license, payment, pricing, SLA, and data quality sections when present;
- data contract and schema references when present;
- a link to the raw ODPS YAML artifact.

The Graph tab should render the generated ODPG graph in the same page instead
of producing a separate graph explorer page.

`index.html` should include a version switcher when version snapshots exist.
The latest portfolio remains available at `<workspace>/index.html`, and the
switcher should let users open previous generated HTML snapshots without
leaving the browser experience. Each listed version should show its timestamp,
run type such as build or refresh, and a short change summary when available.

The About tab or section should explain how the portfolio was created. It
should state that the output was generated with the Open Data Products SDK and
is grounded in the OpenDataProducts.org standards family: ODPC for catalog
objects, ODPS for product specifications, ODPG for graph relationships, and
ODPV for shared vocabulary where vocabulary support is used. It should also
include the SDK version, generation timestamp, source lane counts, and links to
the generated raw artifacts.

## Command Shape

Initial build command:

```bash
open-data-products portfolio build \
  --use-cases inputs/use-cases/ \
  --signals inputs/signals/ \
  --products inputs/products/ \
  --config generation.config.yaml \
  --provider openai \
  --model gpt-4.1-mini \
  --output generated/portfolio/ \
  --json
```

`--output` names the workspace directory to create or update. The command
should also allow a single workspace argument once the workspace is initialized:

```bash
open-data-products portfolio build generated/portfolio/ --json
```

Maintenance commands operate on the chosen workspace path:

```bash
open-data-products portfolio render generated/portfolio/ --json
open-data-products portfolio explain generated/portfolio/ --json
open-data-products portfolio refresh generated/portfolio/ --json
```

Avoid overbuilding targeted maintenance commands before the workspace, state,
and renderer are stable.

When `--json` is set, the command should print one final JSON report after the
process is complete. It should not stream partial JSON objects during the run.
The report should include the workspace path, generated browser entry point,
source counts, artifact counts, created/updated/unchanged files, warnings,
unresolved links, weak links, validation results, and whether the command
completed successfully.

## LLM Orchestration

`portfolio build` and `portfolio refresh` require LLM generation when they need
to turn source documents into new or updated portfolio artifacts. They should
reuse the existing generation provider flow: `--config`, `--provider`,
`--model`, `--prompts`, and provider-specific settings such as `--ollama-url`
should behave consistently with `open-data-products generate`.

The LLM should be used for:

- extracting candidate objectives, use cases, signals, product concepts, and
  product facts from source lanes;
- creating an internal portfolio plan with proposed IDs and links;
- generating ODPC fragments;
- generating ODPS product specs;
- proposing ODPG relationships from the portfolio plan and generated artifacts;
- repairing generated YAML when validation fails.

Deterministic SDK code should be used for:

- source scanning and hashing;
- workspace and directory creation;
- stable ID reuse from `portfolio-state.yaml`;
- YAML parsing, normalization, and validation;
- writing ODPC, ODPS, and ODPG artifacts;
- rendering `index.html`;
- creating version snapshots;
- producing the final JSON report.

`portfolio render` and `portfolio explain` should not call an LLM. They should
operate only on existing workspace files.

If LLM settings are missing or invalid, `portfolio build` and `portfolio refresh`
should fail before writing partial generated artifacts. The final error should
tell the user which provider or config value is missing.

## Identity And Linking

The portfolio workflow must own identity generation. IDs should not be guessed
later by the catalog builder or graph renderer.

Stable IDs are needed for:

- `businessObjective.id`
- `useCase.id`
- `signal.id`
- `productReference.id`
- `productReference.productID`
- ODPS `product.details.en.productID`
- ODPG node IDs
- `$ref` paths between ODPC, ODPS, and ODPG artifacts

When a ProductReference and ODPS product spec are generated from the same
portfolio plan, the workflow should assign the same `productID` and write a
deterministic `productModel.$ref` from the ProductReference to the ODPS YAML.

If source material is ambiguous, the workflow should write a warning to
`portfolio.yaml` and `--json` output instead of silently inventing a confident
link.

## Rerun Behavior

The workflow must be rerunnable. Adding new source material should not break
existing IDs or links.

Minimum rerun behavior:

1. Scan configured source folders.
2. Hash source files and compare them with `portfolio-state.yaml`.
3. Preserve existing IDs for unchanged concepts.
4. Generate artifacts for new or affected concepts.
5. Rebuild `odpc/catalog.yaml`, `odpg/graph.yaml`, and `index.html`.
6. Report created, updated, unchanged, removed, unresolved, and weakly linked
   items in `--json`.

The first implementation can regenerate derived YAML and HTML from the current
portfolio map, but it must keep identity stable.

## Portfolio Versioning

Each successful `portfolio build` or `portfolio refresh` should create a version
snapshot. The latest files stay at the workspace root, while snapshots live
under `versions/`.

```text
<workspace>/
  index.html
  portfolio.yaml
  portfolio-state.yaml
  versions/
    2026-06-07T12-30-00Z/
      index.html
      portfolio.yaml
      report.json
```

Default snapshot behavior should keep the previous browser experience and run
metadata: `index.html`, `portfolio.yaml`, and `report.json`. Full raw artifact
snapshots can be added later if needed, but the HTML history should exist from
the first versioned implementation.

`index.html` should read version metadata generated by the workflow and expose
the available versions through the version switcher. The latest page should
link to each snapshot HTML file. Snapshot pages should link back to the latest
page and show which version they represent.

## Phases

### Phase 1: Portfolio Workspace And Static Renderer

Create the `portfolio` CLI namespace and a deterministic renderer that can build
`index.html` from existing ODPC, ODPS, and ODPG artifacts.

Deliverables:

- `open-data-products portfolio render <workspace>/ --json`
- `portfolio.yaml` loader and validator
- static `index.html` with tabs
- About tab or section with SDK version, generation timestamp, source counts,
  and ODPS standards family attribution
- version switcher when version snapshots exist
- product cards from ProductReference entries
- product detail views from linked ODPS specs
- artifact detail views for objectives, use cases, signals, product references,
  and linked ODPS product specs
- graph tab from ODPG YAML
- tests for deterministic HTML output and escaped values

This phase proves the human experience before adding more generation logic.

### Phase 2: Portfolio Build From Source Lanes

Add `portfolio build` to read multiple source lanes and create the first
connected portfolio workspace.

Deliverables:

- `open-data-products portfolio build --use-cases ... --signals ... --products ...`
- `--config`, `--provider`, `--model`, `--prompts`, and `--ollama-url` support
  matching the existing generation command
- source lane scanning for `.md`, `.txt`, `.yaml`, `.yml`, and `.json`
- internal portfolio plan generation before final artifacts, with no human
  approval gate
- ODPC fragments for objectives, use cases, signals, and product references
- ODPS product specs linked from ProductReference objects
- `portfolio.yaml`, `portfolio-state.yaml`, `odpc/catalog.yaml`,
  `odps/products/*.yaml`, `odpg/graph.yaml`, and `index.html`
- final JSON report with workspace path, browser entry point, artifact counts,
  source counts, validation results, created/updated files, unresolved links,
  weak links, and warnings

This phase makes the one-shot portfolio creation useful.

### Phase 3: Stable Reruns

Make `portfolio build <workspace>/` safe to run after new source material is
added.

Deliverables:

- source hash tracking in `portfolio-state.yaml`
- stable ID reuse for unchanged concepts
- warnings for deleted sources and unresolved links
- rebuild of derived catalog, graph, and HTML outputs
- version snapshot with `index.html`, `portfolio.yaml`, and `report.json`
- tests that rerunning with added material preserves old IDs

This phase turns the workflow from a demo generator into a maintainable
portfolio workspace.

### Phase 4: Targeted Maintenance

Add focused commands for day-to-day maintenance once the workspace model is
stable.

Deliverables:

- `portfolio explain <workspace>/`
- `portfolio refresh <workspace>/`
- optional `portfolio relink <workspace>/`
- optional `portfolio add-source <workspace>/ <path>`
- clear JSON output for agents and automation

This phase should stay conservative. Add only commands that solve repeated
maintenance needs observed in the first workflow.

### Phase 5: Public API And MCP Surface

Expose the workflow through Python and agent surfaces after CLI behavior is
stable.

Deliverables:

- explicit public exports in `open_data_products/__init__.py`
- Python helpers under a focused portfolio module
- safe read-only MCP tools for portfolio explanation, artifact summaries, and
  link inspection
- updates to `tests/test_agentic_patterns.py` if MCP tools are added

State-changing MCP tools should not be added until the project intentionally
expands beyond the current safe read-only MCP class.

## Testing Strategy

Use test-driven development for each phase.

Recommended test files:

- `tests/test_portfolio.py` for workspace, state, map, and renderer behavior
- `tests/test_functional_cli.py` for command behavior
- `tests/test_examples.py` for committed example workspace outputs if examples
  are added
- `tests/test_agentic_patterns.py` only if the MCP surface changes

Key regression tests:

- build and render commands create missing output parent directories;
- product cards render from ODPC ProductReference objects;
- objective, use case, signal, and product detail panels render in the same
  `index.html`;
- product detail panels use linked ODPS specs when available;
- graph tab renders from ODPG YAML in the same `index.html`;
- version switcher links latest and previous HTML snapshots;
- render and explain commands do not call an LLM;
- build fails early when required LLM provider settings are missing;
- rerun preserves IDs when unchanged source files are present;
- rerun reports warnings instead of silently guessing ambiguous links;
- generated HTML escapes source values.

## First Implementation Boundary

The first implementation should not try to solve every maintenance scenario.
The smallest valuable version is:

- one portfolio workspace;
- one `index.html`;
- artifact cards plus detail views for objectives, use cases, signals, and
  products;
- graph tab in the same HTML page;
- version snapshots with browser switching;
- generated ODPC, ODPS, and ODPG YAML underneath;
- stable IDs across reruns;
- clear JSON warnings.

This is enough to make the SDK feel like a portfolio operating tool rather than
only an isolated artifact generator.
