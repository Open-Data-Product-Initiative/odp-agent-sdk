# Release Summary: 0.1.5

Release 0.1.5 focuses on CLI output formatting and version reporting.

## Highlights

- `open-data-products explain <document> --json` now returns structured ODPS
  and ODPG JSON instead of embedding line-oriented explanations as JSON strings.
- ODPG explain JSON includes graph metadata, node and edge counts, node types,
  relationship types, and node references.
- ODPS explain JSON includes product metadata, component count, compliance
  level, production-readiness status, and data access state.
- `open-data-products summary <document>` now prints a compact human-readable
  metadata report by default.
- `open-data-products summary <document> --json` preserves the previous
  machine-readable summary payload.
- `open-data-products --version` and `open-data-products -V` report the
  installed SDK version.

## Verification

- `pytest -q`
- `python3 -c "import open_data_products"`
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
- `test ! -e docs/superpowers`
