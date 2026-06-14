# TOON Export Development Notes

This page explains how the SDK uses TOON for agent-facing context exports.

TOON means Token-Oriented Object Notation. It is a compact, line-oriented
encoding of JSON-shaped data for LLM prompts. In this SDK it is an optional
context format, not a canonical storage format and not a schema replacement.

## Scope

Use TOON where repeated object lists dominate the payload:

- ODPC catalog collections such as product references, use cases, business
  objectives, and signals;
- ODPG graph collections such as nodes and edges.

Do not optimize full ODPS product YAML around TOON first. ODPS product specs are
more nested and less uniform, so YAML and JSON remain the better source-of-truth
formats for validation, editing, and interchange.

## Code Paths

Shared low-level helpers live in `open_data_products/_toon.py`.

ODPC helpers live in `open_data_products/odpc/catalog.py`:

- `render_catalog_toon()`
- `write_catalog_toon()`

ODPG helpers live in `open_data_products/odpg/graph.py`:

- `render_graph_toon()`
- `write_graph_toon()`

The public package exports these helpers through `open_data_products.odpc`,
`open_data_products.odpg`, and the top-level `open_data_products` namespace.

## CLI Surface

TOON files are generated as optional sidecars from the existing build commands:

```bash
open-data-products odpc-build fragments/ \
  --output catalog.yaml \
  --toon catalog.toon

open-data-products odpg-build fragments/ \
  --output graph.yaml \
  --toon graph.toon
```

The YAML output remains required. The TOON file is a derived view for prompts,
reviews, and agent context packing.

## Encoding Rules

The internal renderer intentionally supports the subset the SDK needs:

- primitive object fields;
- uniform arrays of primitive object rows;
- deterministic two-space indentation;
- comma-delimited tabular rows;
- quoted keys and strings when required by TOON syntax;
- `null` for missing optional cells.

The renderer quotes URLs and `$ref` field names where needed. This is expected:
URLs contain `:`, and `$ref` is not a plain unquoted TOON key.

## Data Shape

ODPC TOON output flattens localized text fields to display text:

```toon
catalog:
  productReferences[1]{id,productID,productVersion,name,description,status,visibility}:
    PR-001,customer-product,1.0.0,Customer Product,Trusted analytics,production,internal
```

ODPG TOON output keeps nodes and edges as compact tables:

```toon
graph:
  nodes[2]{id,type,"$ref"}:
    customer-product,DataProduct,product_reference_customer-product.yaml
  edges[1]{from,to,type,confidence}:
    customer-retention,customer-product,dependsOn,high
```

## Testing

Use these tests when changing TOON behavior:

- `tests/test_odpc.py::test_render_and_write_catalog_toon`
- `tests/test_odpg.py::test_render_and_write_graph_toon`
- `tests/test_functional_cli.py::test_unified_cli_builds_odpc_catalog_from_fragments`
- `tests/test_functional_cli.py::test_unified_cli_builds_odpg_graph_from_odpc_fragments`

Run `pytest -q` before release work. The package import and manifest checks from
the repository checklist should also remain green because TOON helpers are part
of the public API surface.
