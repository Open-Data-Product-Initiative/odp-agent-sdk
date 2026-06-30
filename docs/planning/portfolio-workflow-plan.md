# Portfolio Workflow Implementation Notes

This document is for SDK developers working on the portfolio workflow. It
describes the current implementation contract, code boundaries, file formats,
normalization rules, and regression tests that should be preserved when adding
features.

The portfolio workflow turns multiple source lanes into one maintained Open
Data Products workspace:

- ODPC catalog fragments and `odpc/catalog.yaml`;
- ODPS product specifications under `odps/products/`;
- an ODPG graph under `odpg/graph.yaml`;
- one static browser page at `index.html`;
- state, identity, source hashes, reports, and version snapshots.

The low-level `generate` command remains the single-artifact generator. The
portfolio workflow is the orchestration layer for full portfolio work.

## Draft Output Contract

Portfolio generation creates first-pass ODPC, ODPS, and ODPG artifacts from
messy source material such as text files, emails, briefs, meeting notes, and
transcripts. Generated ODPS product specifications are drafts. They should be
schema-shaped, linked, reviewable, and useful as a quick start, but they are
not automatically accepted product contracts.

The SDK should therefore be strict about structure and validation, while being
honest about uncertain content:

- generated YAML should use ODPS v4.1 component shapes whenever evidence exists;
- missing or weak evidence should appear in warnings, review notes, or evidence
  gaps instead of being hidden;
- commercial, access, license, SLA, and data quality content generated from
  sparse material should remain review-needed draft content;
- `index.html`, JSON reports, and docs should make clear that human review and
  acceptance are required before generated ODPS specs are production-ready.

## Code Ownership

Primary implementation files:

- `open_data_products/portfolio.py`: workspace orchestration, source scanning,
  LLM prompt rendering, plan parsing, normalization, identity reconciliation,
  artifact writing, sync, render, explain, graph embedding, version snapshots,
  and HTML/CSS rendering.
- `open_data_products/cli.py`: `open-data-products portfolio ...` command
  registration and provider/client wiring.
- `open_data_products/__init__.py`: public Python exports for
  `build_portfolio`, `refresh_portfolio`, `sync_portfolio`,
  `render_portfolio`, and `explain_portfolio`.
- `open_data_products/odpg/graph.py`: standalone graph explorer rendering used
  by the portfolio graph tab.
- `open_data_products/odps/codecs.py`, `open_data_products/odps/core.py`, and
  `open_data_products/odps/data/schema/odps.json`: ODPS v4.1 parser,
  serializer, and schema behavior that portfolio output must satisfy.

Primary test files:

- `tests/test_portfolio.py`: portfolio workspace, build, rerun, sync, render,
  graph, version, HTML escaping, and schema-normalization coverage.
- `tests/test_core.py`: ODPS parser behavior used by portfolio validation.
- `tests/test_generation_prompts.py`: single-artifact generation normalization
  that should stay consistent with portfolio normalization.

Do not add a second portfolio module unless the current file is intentionally
split by stable responsibilities. If it is split, keep public imports stable.

## Public API

Python entry points:

```python
from open_data_products import (
    build_portfolio,
    refresh_portfolio,
    sync_portfolio,
    render_portfolio,
    explain_portfolio,
)
```

Function contracts:

- `build_portfolio(workspace, ..., client, model, title=None)` requires a model
  client and writes source-derived artifacts.
- `refresh_portfolio(workspace, ..., client, model, title=None)` reuses saved
  source lane paths from `portfolio-state.yaml` unless lane paths are supplied.
  By default it sends only new or changed source files to the model.
  `all_sources=True` forces full source-lane processing.
- `sync_portfolio(workspace)` does not call an LLM. It refreshes generated
  outputs from edited YAML artifacts.
- `render_portfolio(workspace)` does not call an LLM. It renders `index.html`
  from existing workspace files.
- `explain_portfolio(workspace)` does not call an LLM. It returns counts,
  browser entry point, validation status, and version metadata.

Every public function returns a JSON-serializable dictionary. Paths may be
returned as strings in reports, but internal helpers may use `Path`.

## CLI Contract

The CLI namespace is:

```bash
open-data-products portfolio build ...
open-data-products portfolio refresh ...
open-data-products portfolio sync ...
open-data-products portfolio render ...
open-data-products portfolio explain ...
```

Build example:

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

Refresh example:

```bash
open-data-products portfolio refresh examples/portfolio/workspace/ --json
```

Force a full source reprocessing refresh:

```bash
open-data-products portfolio refresh examples/portfolio/workspace/ --all-sources --json
```

Sync edited YAML without LLM generation:

```bash
open-data-products portfolio sync examples/portfolio/workspace/ --json
```

Render existing files without LLM generation:

```bash
open-data-products portfolio render examples/portfolio/workspace/ --json
```

Portfolio commands default to validation warning mode. They still write valid
YAML drafts, render the HTML portfolio, and emit one final report when ODPS
schema validation fails. The report keeps `valid: false`, sets
`validationMode: warn`, and includes exact validation errors so humans can
review the drafts. Use `--strict-validation` on `build`, `refresh`, `sync`, or
`render` when schema failures should return a non-zero exit code.

All `--json` commands must emit one final JSON object, not a stream of partial
objects. Reports should include workspace path, browser entry point, artifact
counts, validation results, created/updated/unchanged paths, warnings, and
overall `valid`.

## Workspace Layout

The workflow owns all generated folders under the selected workspace path and
must create missing directories before writing.

```text
<workspace>/
  index.html
  portfolio.yaml
  portfolio-state.yaml
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

Do not assume `odpc/`, `odpc/fragments/`, `odps/products/`, `odpg/`, or
`versions/` already exist. Writers should call `mkdir(parents=True,
exist_ok=True)` through `_write_yaml`, `_write_json_report`, or equivalent
helpers.

## Source Lanes

`build` and `refresh` read these source lanes:

- `objectives`;
- `useCases`;
- `signals`;
- `products`.

Accepted source suffixes are defined by `PORTFOLIO_SOURCE_SUFFIXES`:

```text
.md, .txt, .yaml, .yml, .json, .eml, .docx, .pptx, .pdf, .csv, .xlsx, .msg, .png, .jpg, .jpeg
```

`.msg`, `.png`, `.jpg`, and `.jpeg` are accepted for detection and reporting.
Outlook `.msg` extraction is available through `open-data-products[email]`;
without the extra, or when parsing fails, `.msg` files are warning-only skipped
sources. Image files are warning-only because OCR and vision extraction are not
enabled.

Source lane collection lives in `open_data_products.portfolio_sources`.
Source hashes and source IDs remain deterministic.

If an input source path is missing, fail early. If an output path is missing,
create it.

## Build Flow

`build_portfolio` performs this sequence:

1. Load previous `portfolio-state.yaml` when present.
2. Snapshot existing workspace files before overwriting them.
3. Resolve source lane paths from explicit CLI arguments or saved state.
4. Collect source files and compare source hashes.
5. Select the source files to process. Build processes all sources. Refresh
   processes only new or changed sources unless `--all-sources` is set.
6. Render a portfolio build prompt for the selected sources.
7. Call the configured model client.
8. Parse the YAML portfolio plan.
9. For changed-only refresh, merge the returned delta plan into the current
   workspace plan.
10. Reconcile stable identities.
11. Normalize generated ODPC, ODPS, and ODPG shapes.
12. Apply the user-controlled workspace title.
13. Write `portfolio.yaml`, `portfolio-state.yaml`, ODPC fragments, ODPS
    product specs, ODPC catalog, ODPG graph, and `index.html`.
14. Validate catalog, graph, and ODPS products.
15. Return one JSON-serializable report.

The LLM may propose names, descriptions, facts, products, and links, but
deterministic SDK code owns workspace title, identity reconciliation, schema
normalization, validation, rendering, snapshots, and final reporting.

## Refresh Source Selection

Refresh defaults to changed-only source processing. The workflow still scans
all saved source lanes and updates hashes, but only files reported as
`created` or `updated` are included in the LLM prompt.

`refresh --all-sources` sets `all_sources=True` and sends every current source
file to the LLM.

Changed-only refresh must merge the model output into the existing workspace
plan. A delta plan may contain only one new use case, signal, product, or graph
edge. It must not delete unchanged existing artifacts just because they were
not included in the changed-source prompt.

Relevant helpers:

- `_changed_source_lanes`;
- `_plan_from_workspace`;
- `_merge_portfolio_plans`;
- `_merge_items_by_id`;
- `_merge_products`;
- `_merge_graph_edges`.

Reports include both:

- `sourceCounts`: all current source files by lane;
- `processedSourceCounts`: files actually sent to the model by lane.

`sync` is separate from refresh. It works from YAML artifacts only and must
never call an LLM.

## Title Ownership

The workspace title is user-controlled. `--title` sets it on build or refresh.
The workflow persists it in `portfolio-state.yaml` and reuses it on reruns.

LLM-generated portfolio metadata must not rename:

- the workspace;
- the rendered page;
- the catalog;
- the graph.

Title handling lives in `_resolve_workspace_title` and `_apply_workspace_title`.

## Identity And Linking

Stable IDs are managed by the workflow, not by the renderer.

Tracked identity classes include:

- business objective IDs;
- use case IDs;
- signal IDs;
- product reference IDs;
- product IDs;
- ODPS `product.details.en.productID`;
- graph node IDs and edge endpoints.

Identity reconciliation lives in `_reconcile_plan_identity`,
`_identity_registry`, `_registry_by_fingerprint`, `_artifact_fingerprint`, and
`_set_odps_product_id`.

Product references and ODPS product specs should share the same `productID`.
Product references must include a deterministic ODPS link:

```yaml
productModel:
  standard: ODPS
  version: "4.1"
  format: yaml
  $ref: ../odps/products/<product-id>.yaml
```

Do not silently invent high-confidence links. Ambiguous links should surface as
warnings in `portfolio.yaml` and JSON reports.

## Artifact Writing

`_write_portfolio_artifacts` writes the main generated files:

- `portfolio.yaml`;
- `portfolio-state.yaml`;
- ODPC fragments;
- ODPS product YAML;
- `odpc/catalog.yaml`;
- `odpg/graph.yaml`.

`_write_yaml` returns `(path, state)` where `state` is `created`, `updated`, or
`unchanged`. Reports should preserve these states so agents and CI can tell
what changed.

Catalog rebuilds use `_catalog_document` for generated plans and
`_catalog_from_fragments` for sync.

Graph rebuilds use `_graph_document`, `_graph_nodes`, `_graph_node`, and
`_graph_edge`.

## ODPS Normalization

Portfolio generation must produce ODPS v4.1 schema-shaped YAML, not just YAML
that the Python loader can tolerate.

Normalization starts in `_normalize_portfolio_plan` and delegates to
`_normalize_odps_product`.

Current ODPS normalization rules:

- detail status and visibility are mapped to allowed ODPS values;
- `product.details.en.productID` is kept aligned with the ODPC
  `ProductReference.productID`;
- legacy `pricing` is converted to `pricingPlans`;
- list-based pricing is converted to `pricingPlans.declarative.<language>`;
- `pricingPlanName` is mapped to `name`;
- pricing `license` text is mapped to `description`;
- missing pricing fields are made valid but visibly provisional:
  `priceCurrency: XXX`, `price: "0"`, `billingDuration: month`,
  `unit: On-request`;
- `dataAccess` is emitted as a named ODPS v4.1 access method mapping;
- `outputPorttype` is converted to `outputPortType`;
- loose `details.en.SLA` values are moved to `product.SLA.declarative`;
- loose generated `dataOps` is moved to `x-dataOps`.

The bundled ODPS parser must also accept canonical v4.1 shapes. In particular,
`OpenDataProduct.from_dict` and `parse_data_access` accept named `dataAccess`
method mappings and `outputPortType`.

When adding new generated component shapes, update both:

- portfolio normalization tests in `tests/test_portfolio.py`;
- ODPS parser or generation tests if the shape is shared by `generate`.

## Sync Flow

`sync_portfolio` is the maintenance path for users who edit YAML artifacts
directly.

Sync performs this sequence:

1. Snapshot the existing workspace.
2. Normalize ODPS product files in `odps/products/`.
3. Rebuild `odpc/catalog.yaml` from `odpc/fragments/*.yaml`.
4. Propagate linked ODPS product details back into matching ODPC product
   references.
5. Rewrite `portfolio-state.yaml` with current identity state.
6. Re-render `index.html`.
7. Return a JSON report.

Sync must not call an LLM. It must refresh product names and descriptions in:

- ODPS product YAML;
- ODPC product reference fragments;
- `odpc/catalog.yaml`;
- Products tab in `index.html`;
- embedded graph labels where graph nodes reference those products.

Product-reference propagation lives in `_sync_product_references_from_odps`,
`_merge_product_reference_details`, and `_odpc_product_visibility`.

ODPS file repair lives in `_normalize_product_spec_files`.

## Rendering

`render_portfolio` loads the workspace with `load_portfolio_workspace`,
validates artifacts, renders HTML with `render_portfolio_html`, and writes
`index.html`.

The static page is intentionally one browser-openable file. It contains:

- Overview;
- Business Objectives;
- Use Cases;
- Products;
- Signals;
- Graph;
- About;
- footer;
- version switcher when snapshots exist.

The Products tab renders ODPC product reference cards and linked ODPS product
detail panels. Product detail rendering lives in `_render_product_card`,
`_resolve_product`, and `_render_product_detail`.

The graph tab embeds the ODPG graph explorer generated by
`build_graph_explorer_html`. Portfolio-specific graph embedding lives in
`_render_graph`, `_portfolio_graph_explorer_html`, `_graph_for_explorer`, and
`_catalog_label_map`.

Graph labels should prefer human-readable catalog/product labels while keeping
stable graph node IDs unchanged.

All user/source-derived strings in HTML must be escaped with `_escape` or
`_escape_attr`.

## Version Snapshots

Build, refresh, and sync snapshot an existing workspace before writing new
outputs. Snapshot behavior lives in `_snapshot_existing_workspace`,
`_write_json_report`, `_refresh_portfolio_versions`, and `_portfolio_versions`.

Current snapshot contents:

- previous `index.html`;
- previous `portfolio.yaml`;
- `report.json` for the run that created the snapshot.

Latest output remains at `<workspace>/index.html`. Previous HTML snapshots live
under `versions/<timestamp>/index.html` and are exposed through the version
switcher in the Overview tab.

If full raw artifact snapshots are added later, keep the current browser
history behavior intact.

## Validation

Portfolio validation is collected by `_portfolio_validation_results` and
summarized by `_valid_portfolio`.

Validation inputs:

- `validate_catalog` for ODPC catalog mappings;
- `validate_graph` for ODPG graph mappings;
- `validate_document` for ODPS product paths.

ODPS products should pass both the bundled JSON Schema and SDK semantic
validators where possible. Do not make portfolio reports `valid: true` by
masking schema errors. The draft workflow may allow schema-invalid ODPS YAML to
be written in validation warning mode, but the report must keep `valid: false`
and preserve the exact errors.

The schema/parser boundary matters. When the schema changes, update:

- `open_data_products/odps/data/schema/odps.json`;
- `open_data_products/odps/core.py`;
- `open_data_products/odps/codecs.py`;
- portfolio and generation normalization tests.

## Error Handling

Build and refresh should fail before writing partial generated artifacts if LLM
settings are missing or invalid.

Render and sync should tolerate missing optional workspace files by using empty
catalog, graph, product, or version structures where appropriate.

Deleted sources are reported as warnings rather than silently ignored.

Unsupported generated enum values should be normalized to conservative defaults
and remain visible through generated YAML and JSON reports where possible.

## Reports

Portfolio reports should include:

- `spec`;
- `kind`;
- `workspace`;
- `html`;
- `snapshot`;
- source counts for build/refresh;
- processed source counts for build/refresh;
- artifact counts;
- validation results;
- created, updated, unchanged, and removed paths where applicable;
- source changes for build/refresh;
- warnings;
- unresolved links;
- weak links;
- overall `valid`.

Keep reports stable for automation. Additive fields are safer than renaming
existing fields.

## Examples

The committed example structure should stay grouped under `examples/portfolio/`:

```text
examples/portfolio/
  mockup/
    index.html
  sources/
    objectives/
    use-cases/
    signals/
    products/
  workspace/
    index.html
    odpc/
    odps/
    odpg/
```

Do not spread example portfolio sources, mockups, and generated workspaces
around the repository root.

`examples/portfolio/workspace/` is a generated demo workspace. It is useful for
manual browser checks, but regression safety should come from tests.

## Testing Checklist

Run focused tests after portfolio changes:

```bash
pytest -q tests/test_portfolio.py
```

Run parser tests after ODPS shape changes:

```bash
pytest -q tests/test_core.py
```

Run generation tests after shared normalization changes:

```bash
pytest -q tests/test_generation_prompts.py
```

Full pre-completion checks:

```bash
pytest -q
python3 -c "import open_data_products"
python3 -m open_data_products.cli manifest --json | python3 -m json.tool
git diff --check
find docs -path 'docs/superpowers' -o -path 'docs/superpowers/*'
```

Useful manual validation commands:

```bash
python3 -m open_data_products.cli portfolio sync examples/portfolio/workspace --json
python3 -m open_data_products.cli validate examples/portfolio/workspace/odps/products/customer-health-signals.yaml --json
```

For explicit ODPS JSON Schema checks, use `jsonschema.Draft202012Validator`
against `open_data_products/odps/data/schema/odps.json`.

## Extension Points

Prefer these extension points:

- add source lanes by extending source collection, prompt shape, state, and
  artifact mapping together;
- add ODPS component normalization in `_normalize_odps_product`;
- add detail rendering in `_render_product_detail`;
- add graph relationship types through `ODPG_EDGE_TYPES` and
  `ODPG_EDGE_TYPE_ALIASES`;
- add report fields without renaming current fields;
- add public helpers only after CLI and internal behavior are stable.

Avoid these changes unless intentionally scoped:

- introducing another CLI entry point outside `open-data-products`;
- making render or sync call an LLM;
- letting the LLM control workspace title;
- returning full document bodies from future MCP tools;
- accepting invalid ODPS output by suppressing schema errors;
- storing absolute filesystem paths inside generated YAML references.

## Developer Rule Of Thumb

The portfolio workflow should feel like this:

1. `build` creates a complete connected workspace from source lanes.
2. `refresh` reruns source-driven generation while preserving identity.
3. `sync` reflects curated YAML edits without starting over.
4. `render` turns existing artifacts into one browser page.
5. `explain` summarizes the workspace for humans, agents, and automation.

When in doubt, keep LLM work at the evidence-to-plan boundary and keep all
identity, linking, validation, filesystem writes, and rendering deterministic.
