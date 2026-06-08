# Portfolio Capability Development

This document is for SDK developers maintaining the portfolio workflow. It
describes the implemented capability, source boundaries, workspace contract,
LLM responsibilities, renderer behavior, localization, validation modes, and
tests that should stay green when the workflow changes.

The portfolio workflow is the SDK's full-workflow layer. It turns multiple
evidence streams into one maintained Open Data Products workspace:

- ODPC catalog fragments and `odpc/catalog.yaml`;
- linked ODPS product specifications under `odps/products/`;
- ODPG graph YAML under `odpg/graph.yaml`;
- one static browser experience at `index.html`;
- optional localized browser pages such as `index.fi.html` and `index.ar.html`;
- source hashes, stable IDs, reports, and version snapshots.

The lower-level `generate` command remains useful for one artifact at a time.
Portfolio commands orchestrate the standards family together and preserve
identity, links, state, and browser output across reruns.

## Code Boundaries

Primary implementation files:

- `open_data_products/portfolio.py`: source scanning, LLM prompt rendering,
  plan parsing and repair, ID reconciliation, ODPC/ODPS/ODPG artifact writing,
  sync, render, localize, explain, version snapshots, HTML/CSS/JS rendering,
  graph embedding, validation reporting, and portfolio state handling.
- `open_data_products/cli.py`: `open-data-products portfolio ...` command
  parsing, provider settings, strict-validation behavior, and JSON output.
- `open_data_products/__init__.py`: public exports for portfolio helpers.
- `open_data_products/odpg/graph.py`: standalone graph explorer renderer that
  the portfolio Graph tab embeds.
- `open_data_products/generation/__init__.py`: provider client construction and
  shared LLM settings used by portfolio build, refresh, and localize.

Primary tests:

- `tests/test_portfolio.py`: portfolio build, refresh, sync, render, localize,
  stable IDs, graph embedding, product modals, validation mode, source deltas,
  escaped HTML, RTL output, and stale i18n pruning.
- `tests/test_functional_cli.py`: CLI command behavior.
- `tests/test_generation_prompts.py`: prompt and schema-shape behavior shared
  with generation flows.

Keep new behavior in the smallest existing module that fits. If
`portfolio.py` is split later, preserve the public imports and CLI behavior.

## Public API

Public helpers are exported from `open_data_products`:

```python
from open_data_products import (
    build_portfolio,
    refresh_portfolio,
    sync_portfolio,
    render_portfolio,
    localize_portfolio,
    explain_portfolio,
)
```

All helpers return JSON-serializable dictionaries. Reports use string paths.
Internal helpers may use `Path`.

LLM-backed helpers:

- `build_portfolio(...)`
- `refresh_portfolio(...)` when new or changed source files need generation
- `localize_portfolio(...)`

Deterministic helpers:

- `sync_portfolio(...)`
- `render_portfolio(...)`
- `explain_portfolio(...)`

## CLI Surface

Portfolio commands live under one CLI namespace:

```bash
open-data-products portfolio build ...
open-data-products portfolio refresh ...
open-data-products portfolio sync ...
open-data-products portfolio render ...
open-data-products portfolio localize ...
open-data-products portfolio explain ...
```

Initial build:

```bash
open-data-products portfolio build \
  --objectives examples/portfolio/sources/objectives/ \
  --use-cases examples/portfolio/sources/use-cases/ \
  --signals examples/portfolio/sources/signals/ \
  --products examples/portfolio/sources/products/ \
  --title "Customer Intelligence Portfolio" \
  --output examples/portfolio/workspace/ \
  --provider claude \
  --model claude-sonnet-4-5 \
  --json
```

After the workspace is initialized:

```bash
open-data-products portfolio refresh examples/portfolio/workspace/ --json
open-data-products portfolio sync examples/portfolio/workspace/ --json
open-data-products portfolio render examples/portfolio/workspace/ --json
open-data-products portfolio explain examples/portfolio/workspace/ --json
```

Localization:

```bash
open-data-products portfolio localize examples/portfolio/workspace/ \
  --languages "fi,sv,ar,vi" \
  --provider claude \
  --model claude-sonnet-4-5 \
  --json
```

`--json` commands should emit one final JSON object. Do not stream partial JSON
reports.

## Workspace Contract

The workflow owns this generated workspace shape:

```text
<workspace>/
  index.html
  portfolio.yaml
  portfolio-state.yaml
  portfolio-i18n.yaml
  odpc/
    catalog.yaml
    fragments/
      business_objective_*.yaml
      use_case_*.yaml
      signal_*.yaml
      product_reference_*.yaml
  odps/
    products/
      *.yaml
  odpg/
    graph.yaml
  versions/
    <timestamp>/
      index.html
      portfolio.yaml
      report.json
```

`portfolio-i18n.yaml` exists only after localization.

Do not assume output folders exist. Any writer for YAML, HTML, JSON reports, or
state must create the target parent directory first.

Do not store absolute paths inside canonical artifacts. Reports may include the
paths used in the current run.

## Source Lanes

Build and refresh support four source lanes:

- `objectives`
- `useCases`
- `signals`
- `products`

Accepted source suffixes are defined by `PORTFOLIO_SOURCE_SUFFIXES`:

```text
.md, .txt, .yaml, .yml, .json
```

Source scanning and hashing are deterministic. If an input source folder is
missing, fail early. If an output folder is missing, create it.

## Build And Refresh Flow

`build_portfolio` performs this high-level sequence:

1. Load previous `portfolio-state.yaml` when present.
2. Resolve and scan source lane paths.
3. Compare source hashes.
4. Decide which sources should be processed.
5. Render one portfolio-plan prompt.
6. Parse the model's YAML plan, with one syntax repair attempt.
7. Reconcile generated IDs against the previous identity registry.
8. Merge delta output into the current workspace when processing only changed
   or new sources.
9. Normalize generated ODPC, ODPS, and ODPG shapes.
10. Snapshot the previous HTML and portfolio map when rerunning.
11. Write `portfolio.yaml`, `portfolio-state.yaml`, ODPC fragments, ODPS
    products, ODPC catalog YAML, and ODPG graph YAML.
12. Render `index.html`.
13. Return one JSON-serializable report.

`refresh_portfolio` delegates to `build_portfolio`. By default it sends only
new or changed source files to the model. `--all-sources` sets `all_sources`
and forces the full saved source lane set through the model.

## Sync Flow

`sync_portfolio` is YAML-only and must never call an LLM.

Use sync when a user edits files such as:

- `odpc/fragments/*.yaml`
- `odps/products/*.yaml`
- `odpg/graph.yaml`

Sync rebuilds `odpc/catalog.yaml`, updates state from existing artifacts,
snapshots the previous browser output, renders a fresh `index.html`, and
returns one report.

## Identity And Linking

The workflow owns identity. Do not let the renderer or graph builder invent
IDs later.

Stable IDs are needed for:

- business objectives;
- use cases;
- signals;
- product references;
- ODPS `productID` values;
- ODPG node and edge endpoints.

When a ProductReference and ODPS product spec represent the same planned
product, they must share the same `productID`. ProductReference should link to
the ODPS YAML through a deterministic `productModel.$ref`.

If evidence is ambiguous, write warnings and weak-link notes. Do not silently
invent confident links.

## ODPS Draft Normalization

Generated ODPS specs are drafts. The SDK should make them schema-shaped and
reviewable, not pretend they are accepted production contracts.

Normalization should protect common schema shapes:

- `SLA.declarative` is a named mapping such as `default` and `premium`.
- `dataQuality.declarative` is a named mapping such as `default` and `premium`.
- Pricing plans should use named `$ref` paths, for example
  `#/product/SLA/declarative/default` and `#/product/dataAccess/API`.
- Data access should be a named mapping keyed by access method.
- Known loose data quality dimensions should be normalized. For example,
  reconciliation evidence maps to `dimension: consistency` while retaining the
  reconciliation wording in display labels or descriptions.
- Unsupported extension content can live under `x-*` fields when it is not part
  of ODPS schema.

Validation errors should be included in reports and browser review context.

## Validation Modes

Portfolio commands default to validation warning mode. A command can complete,
write YAML, render HTML, and return `valid: false` when ODPS draft schema
validation fails.

Use `--strict-validation` when schema-invalid drafts should make the CLI return
a non-zero exit code, such as in CI.

YAML parse failures are different from schema validation failures. Invalid YAML
must still fail because the workspace cannot safely load or render it.

## HTML Renderer

`index.html` is a static, browser-openable page. It should not require a server.

Required top-level tabs:

- Overview
- Business Objectives
- Use Cases
- Products
- Signals
- Graph
- About

Products use a two-layer view:

- cards list ODPC ProductReference objects;
- each card opens a modal with linked ODPS product details.

Product modals should show pricing plans together with their referenced access,
SLA, data quality, and payment components. Do not list all SLA or data quality
profiles separately when pricing plans already reference them. Unreferenced
profiles may be shown as unlinked profiles.

The Graph tab embeds the ODPG graph explorer generated by
`build_graph_explorer_html`, with the standalone explorer header and footer
removed.

Generated HTML must escape user/model content. Localization must not rewrite or
escape `<style>` and `<script>` blocks as normal text.

## Version Snapshots

Successful build, refresh, and sync reruns snapshot previous browser output
under `versions/<timestamp>/`.

Snapshots currently preserve:

- `index.html`
- `portfolio.yaml`
- `report.json`

The latest workspace remains at the root. The latest `index.html` includes a
version switcher that links to historical snapshot HTML pages.

## Localization

`portfolio localize` translates human-facing HTML strings without changing
canonical ODPC, ODPS, or ODPG YAML artifacts.

Localization writes:

- `portfolio-i18n.yaml`
- `index.<language>.html` files for non-default languages
- an updated default `index.html` with a language selector

Language tags are BCP 47-style values such as `fi`, `sv`, `ar`, `vi`,
`en-GB`, or `pt-BR`.

Localization uses batched LLM calls so large pages do not require one huge YAML
response. Each batch can be repaired independently if the model returns
malformed YAML. Stale i18n keys are pruned from `portfolio-i18n.yaml` when they
no longer appear in the current HTML.

Right-to-left support is deterministic. The renderer sets `dir="rtl"` for
language primary subtags such as `ar`, `he`, `fa`, and `ur`; all other pages use
`dir="ltr"` unless the RTL set is expanded.

## Reports

Reports should include enough detail for automation and agents:

- `spec`
- `kind`
- `workspace`
- `html`
- `sourceCounts`
- `processedSourceCounts` when generation is source-limited
- `artifactCounts`
- `validationResults`
- `created`
- `updated`
- `unchanged`
- `removed`
- `sourceChanges`
- `warnings`
- `unresolvedLinks`
- `weakLinks`
- `validationMode`
- `valid`

Keep reports JSON-serializable.

## Testing Expectations

When changing portfolio behavior, add or update tests in `tests/test_portfolio.py`
first.

High-value regression areas:

- missing output directories are created;
- source deltas preserve existing IDs;
- refresh defaults to changed/new sources only;
- `--all-sources` forces full source processing;
- sync does not call an LLM;
- ProductReference cards link to ODPS product details;
- product modals render pricing-linked SLA, data quality, access, and payment;
- graph explorer content is embedded without standalone header/footer copy;
- localized pages preserve CSS and JavaScript;
- RTL languages render with `dir="rtl"`;
- stale localization keys are pruned;
- validation warning mode completes while strict mode fails.

Before marking work complete, run:

```bash
python3 -m pytest -q
python3 -c "import open_data_products"
python3 -m open_data_products.cli manifest --json | python3 -m json.tool
git diff --check
test ! -e docs/superpowers
```
