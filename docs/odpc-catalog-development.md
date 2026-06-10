# ODPC Catalog Development Notes

This page explains the ODPC catalog helpers for contributors.

## Main Code Paths

ODPC catalog behavior lives in `open_data_products/odpc/catalog.py`.

Important helpers:

- `load_catalog()`
- `iter_catalog_input_files()`
- `build_catalog()`
- `validate_catalog()`
- `explain_catalog()`
- `render_catalog_html()`
- `render_catalog_toon()`
- `build_catalog_artifacts()`
- `search_objects()`

CLI wrappers live in `open_data_products/odpc/cli.py` and the unified CLI in
`open_data_products/cli.py`.

## Input Files

Catalog building reads `.yaml`, `.yml`, and `.json` files. Recursive traversal
is enabled by default. When an output path is provided, that path is skipped so
regenerating a catalog into the source folder does not ingest itself.

The YAML loader disables timestamp coercion so date-like values remain strings.
This is important for generated and hand-authored ODPC fragments.

## Accepted Fragment Shapes

`collect_catalog_document()` accepts several shapes:

- a full `catalog` document;
- standalone `metadata` or `catalogMetadata`;
- single object roots such as `productReference`, `useCase`,
  `businessObjective`, or `signal`;
- collection roots such as `productReferences`, `useCases`,
  `businessObjectives`, or `signals`;
- ODPS product documents, which can be converted to ODPC product references.

When adding a new accepted shape, update both collection logic and validation
tests.

## Catalog Building

`build_catalog()` collects fragments into ODPC collections, chooses metadata,
and returns a full catalog document:

```yaml
schema: https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml
version: "1.0"
kind: Catalog
catalog:
  metadata: ...
```

Metadata priority is:

1. standalone metadata candidates;
2. embedded catalog metadata candidates;
3. generated default metadata.

CLI overrides can replace id, name, and description after metadata selection.

## ODPS Product References

`product_reference_from_product()` derives an ODPC `ProductReference` from an
ODPS product file. It prefers `product.details.en` but also handles older flat
detail fields.

The generated reference uses a relative `$ref` from the input folder to the
source product file.

## Validation

`validate_catalog()` checks root fields, catalog metadata, and object
collections. Keep errors specific enough for CLI users and agents to repair the
right fragment.

Generated fragments are often validated by wrapping them in a temporary
catalog. Avoid validation behavior that only works for one file layout.

## HTML Rendering

`render_catalog_html()` uses the bundled HTML template and section renderers.
HTML output should be deterministic and escaped. Do not embed unescaped source
values.

## TOON Rendering

`render_catalog_toon()` creates an optional LLM-context view of a catalog.
It keeps YAML as the source of truth and renders repeated ODPC collections as
TOON tables. Use `write_catalog_toon()` or `odpc-build --toon` when a workflow
needs a compact prompt artifact.

See [`toon-development.md`](toon-development.md) for the shared renderer rules.

## Object Guidance Search

ODPC object guidance records live in bundled JSONL resources. Search uses the
shared lightweight search helpers. Keep records compact and agent-readable.

## Tests

Use these files when changing ODPC catalog behavior:

- `tests/test_odpc.py`
- `tests/test_examples.py`
- `tests/test_functional_cli.py`
- `tests/test_generation_prompts.py` when generated fragments depend on ODPC
  validation.
