# Release Summary: 0.2.0

Release 0.2.0 expands LLM-assisted generation from ODPC fragments into full
ODPS product drafts built from source material such as transcripts, emails, and
briefs.

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
