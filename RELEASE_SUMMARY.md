# Release Summary: 0.2.5

Minor release for the OKF context bundle capability.

## OKF context bundle support

The SDK now supports Open Knowledge Format (OKF) as an external
Markdown/frontmatter context bundle format. OKF is not treated as a fifth Open
Data Products standard; ODPS, ODPC, ODPG, and ODPV remain the canonical
structured artifacts.

New OKF surfaces:

- Python helpers in `open_data_products.okf` for bundle validation, concept
  summaries, import, and export.
- CLI commands:
  - `open-data-products okf-validate <bundle-dir>`
  - `open-data-products okf-summary <bundle-dir>`
  - `open-data-products okf-import <bundle-dir> --output <source-docs-dir>`
  - `open-data-products okf-export <catalog-or-portfolio> --output <bundle-dir>`
- Safe MCP tools:
  - `validate_okf_bundle`
  - `list_okf_concepts`
- Agent manifest metadata for `okf-context-bundles`, including validate,
  import, and export workflows.
- Bundled resource metadata under `okf.spec`.

The import path writes OKF concepts as generation-ready Markdown source
documents. The export path writes ODPC catalog or portfolio artifacts as a
portable OKF bundle for human and agent review.
