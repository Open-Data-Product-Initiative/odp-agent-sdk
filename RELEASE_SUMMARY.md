# Release Summary: 0.2.1

Release 0.2.1 expands LLM-assisted generation from isolated ODPC fragments into
full ODPS product drafts and connected portfolio workspaces built from source
material such as business objectives, use cases, market signals, transcripts,
emails, and briefs.

## Highlights

- `open-data-products generate --kind odps-product` can now turn each file in an
  input folder into a full ODPS YAML product draft.
- `--profile minimal` remains the default evidence-first behavior, while
  `--profile complete-draft` can draft required commercial and governance
  sections such as `SLA`, `dataQuality`, and `pricingPlans`.
- `--include-components` gives advanced control over optional root-level ODPS
  sections, including access, license, payment gateway, SLA, data quality, and
  pricing content.
- `--max-source-chars` chunks long transcripts and other large source files,
  extracts facts per chunk, and merges those facts before YAML generation.
- ODPS product generation now uses purpose-specific prompts for fact extraction,
  chunk merging, minimal YAML generation, component drafting, assembly, and
  validation repair.
- Generated ODPS YAML is normalized toward the bundled schema before output,
  including schema-facing `SLA.declarative`, `dataQuality.declarative`, named
  `$ref` links, pricing plan shape, and access field casing.
- The generation result includes review notes, drafted component names, evidence
  gaps, validation status, and repair warnings in `--json` output.
- ODPS document validation now supports schema-shaped YAML mappings directly,
  including declarative SLA and data quality sections.
- New `open-data-products portfolio` commands can build, refresh, sync, render,
  explain, and localize a portfolio workspace that connects ODPC catalog
  objects, linked ODPS product specs, and ODPG graph relationships.
- `portfolio build` accepts separate source lanes for objectives, use cases,
  signals, and products, creates all required workspace folders, writes a final
  JSON report, and preserves a user-supplied portfolio title across reruns.
- Portfolio refresh defaults to processing changed and new source documents,
  while `--all-sources` forces full reprocessing and `portfolio sync` rebuilds
  from edited YAML artifacts without calling an LLM.
- Portfolio HTML now renders one browser-openable `index.html` with tabs for
  overview, artifact types, products, graph, and about content. Product cards
  open detailed modal views with pricing plans, linked access, SLA, data quality,
  payment, licensing, and raw artifact references.
- The Graph tab embeds the generated ODPG graph explorer in the same page, and
  successful builds or refreshes create version snapshots that can be opened
  from the portfolio page.
- Portfolio validation defaults to warning mode so schema-invalid ODPS drafts do
  not block users from reviewing generated browser output; `--strict-validation`
  is available when automation should fail on schema errors.
- `portfolio localize` translates human-facing HTML strings into static
  localized pages such as `index.fi.html`, `index.sv.html`, `index.ar.html`, and
  `index.vi.html` without changing canonical YAML artifacts. Localized pages
  include language switching, batched LLM translation, stale translation pruning,
  and deterministic RTL support for languages such as Arabic.
- New development documentation explains generation internals, ODPS validation,
  data contracts, ODPC catalog building, ODPG graph building, MCP tools, and the
  cross-spec agent surface.

## Verification

- `pytest -q`
- `python3 -c "import open_data_products; print(open_data_products.__version__)"`
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
- `test ! -e docs/superpowers`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m build`
- `python3 -m twine check dist/*`
