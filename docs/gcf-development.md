# GCF Export Development Notes

This page explains how the SDK uses GCF for agent-facing context exports.

GCF support is experimental. YAML remains the source of truth. The GCF file is a
generated sidecar for prompt context, review automation, and agent workflows.

## Scope

Use GCF where repeated rows or graph edges dominate the payload:

- ODPC catalog collections are rendered as compact pipe-delimited rows.
- ODPG graph nodes are declared once with deterministic local IDs.
- ODPG graph edges use those local IDs instead of repeating full endpoint IDs.

Do not treat GCF as a replacement for ODPC or ODPG YAML. Do not use it as a schema
format. Validate, publish, and exchange the canonical YAML document.

ODPC catalogs can now emit both TOON and GCF. In the current fixtures, GCF is
very close to TOON for catalogs and slightly smaller on the larger portfolio
workspace catalog.

## Code Paths

Shared low-level helpers live in `open_data_products/_gcf.py`.

ODPC helpers live in `open_data_products/odpc/catalog.py`:

- `render_catalog_gcf()`
- `write_catalog_gcf()`

ODPG helpers live in `open_data_products/odpg/graph.py`:

- `render_graph_gcf()`
- `write_graph_gcf()`

The public package exports these helpers through `open_data_products.odpc`,
`open_data_products.odpg`, and the top-level `open_data_products` namespace.

## CLI Surface

GCF files are generated as optional sidecars from the existing build commands:

```bash
open-data-products odpc-build fragments/ \
  --output catalog.yaml \
  --gcf catalog.gcf

open-data-products odpg-build fragments/ \
  --output graph.yaml \
  --gcf graph.gcf
```

GCF can be generated in the same run as TOON:

```bash
open-data-products odpg-build fragments/ \
  --output graph.yaml \
  --toon graph.toon \
  --gcf graph.gcf
```

The YAML output remains required. The GCF file is a derived view for prompts,
reviews, and agent context packing.

When rebuilding a graph from fragments, `odpg-build` can also use an existing
graph as prior edge-inference context:

```bash
open-data-products odpg-build fragments/ \
  --output graph.yaml \
  --context-graph previous-graph.yaml \
  --gcf graph.gcf
```

The previous graph is not treated as canonical input. It is prompt context only,
and the edge prompt prefers `previous-graph.gcf`, then `previous-graph.toon`,
then `previous-graph.yaml`.

## Data Shape

ODPC GCF output renders repeated catalog collections as rows:

```text
GCF profile=generic tool=open-data-products kind=odpc-catalog
schema=https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml
version=1.0
kind=Catalog
id=CAT-001
name=Customer Catalog
description=Customer catalog for agent context.
## productReferences [1]{id,productID,productVersion,name,description,status,visibility}
PR-001|customer-product|1.0.0|Customer Product|Trusted analytics.|production|internal
```

ODPG GCF output declares nodes once and refers to them by local ID in the edge
section:

```text
GCF profile=generic tool=open-data-products kind=odpg-graph nodes=2 edges=1
schema=https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version=1.0
kind=Graph
id=GRAPH-001
name=Customer Graph
description=Customer graph for agent context.
## nodes [2]{id,type,ref}
@0 customer-product|DataProduct|product_reference_customer-product.yaml
@1 customer-retention|UseCase|use_case_customer-retention.yaml
## edges [1]
@0<@1 dependsOn high
```

The edge line reads as a compact relationship from local node `@1` to local
node `@0`, with the edge type and confidence appended.

## Local Measurements

The current fixture measurements cover both ODPC and ODPG sidecars:

| Measurement | YAML bytes | YAML tokens | TOON bytes | TOON tokens | TOON token reduction | GCF bytes | GCF tokens | GCF token reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ODPC tiny example fragments | 914 | 231 | 827 | 203 | 12.1% | 852 | 205 | 11.3% |
| ODPC guide catalog fragments | 1,716 | 419 | 1,300 | 297 | 29.1% | 1,307 | 297 | 29.1% |
| ODPC portfolio workspace catalog | 10,371 | 2,311 | 7,143 | 1,405 | 39.2% | 6,968 | 1,388 | 39.9% |
| ODPG guide graph with deterministic test edges | 998 | 316 | 793 | 250 | 20.9% | 680 | 212 | 32.9% |
| ODPG portfolio workspace graph | 2,925 | 970 | 2,226 | 739 | 23.8% | 1,701 | 561 | 42.2% |

For the ODPG graph rows specifically, GCF also improves on TOON:

| Measurement | YAML tokens | TOON tokens | GCF tokens | GCF vs YAML | GCF vs TOON |
| --- | ---: | ---: | ---: | ---: | ---: |
| ODPG guide graph with deterministic test edges | 316 | 250 | 212 | 32.9% fewer | 15.2% fewer |
| ODPG portfolio workspace graph | 970 | 739 | 561 | 42.2% fewer | 24.1% fewer |

These measurements use the `o200k_base` tokenizer through `tiktoken`.

Run the repository measurement script with:

```bash
python3 -m pip install '.[measurements]'
python3 scripts/measure_context_sidecars.py --encoding o200k_base
```

The `measurements` extra installs `tiktoken` on Python versions it supports.
Exact production savings should still be measured with the tokenizer used by the
target model.

## Agent Context Input

GCF remains a sidecar, not a canonical document format. Agent-facing workflows
can still use it as prompt input. For example, `odpg-agent-context` can attach a
selected context artifact to its JSON response:

```bash
open-data-products odpg-agent-context graph.yaml \
  --node AGENT-AVIATION-001 \
  --context-format auto \
  --json
```

`auto` selects `graph.gcf` first, then `graph.toon`, then `graph.yaml`. The
command still loads and validates `graph.yaml`; the selected sidecar is included
as compact text for downstream agents.

MCP clients can discover compact sidecars through the existing `load_summary`
tool. The summary still avoids returning document bodies, but now includes a
`context_artifacts` list when sibling `.gcf` or `.toon` files exist:

```json
{
  "path": "graph.yaml",
  "spec": "odpg",
  "kind": "Graph",
  "context_artifacts": [
    {
      "format": "gcf",
      "path": "graph.gcf",
      "byte_size": 1701,
      "line_count": 24,
      "sha256": "...",
      "preferred": true
    }
  ]
}
```

That gives agents a cheap discovery step: ask for a summary, choose the
preferred compact context artifact, and only read the sidecar when needed.

Generation prompts also use compact source context when it is available. If a
source YAML file such as `catalog.yaml` or `graph.yaml` has a sibling `.gcf` or
`.toon` file, `load_source_documents()` inlines the compact sidecar text into
the prompt while keeping the canonical YAML filename visible in the source
header. For source folders, YAML files are included only when they have one of
those compact sidecars, so unrelated config YAML is not pulled into generation
prompts.

## Testing

Use these tests when changing GCF behavior:

- `tests/test_context_artifacts.py`
- `tests/test_agentic_patterns.py::TestLoadSummary`
- `tests/test_functional_mcp.py::test_mcp_load_summary_exposes_context_sidecar_references`
- `tests/test_generation_prompts.py::test_load_source_documents_prefers_compact_yaml_context_sidecars`
- `tests/test_generation_prompts.py::test_load_source_documents_includes_yaml_sidecars_from_source_folders`
- `tests/test_odpc.py::test_render_and_write_catalog_gcf`
- `tests/test_odpg.py::test_render_and_write_graph_gcf`
- `tests/test_odpg.py::test_build_graph_uses_compact_prior_graph_context`
- `tests/test_functional_cli.py::test_unified_cli_builds_odpc_catalog_from_fragments`
- `tests/test_functional_cli.py::test_unified_cli_builds_odpg_graph_from_odpc_fragments`
- `tests/test_functional_cli.py::test_odpg_agent_context_can_include_compact_context_artifact`

Run `pytest -q` before release work. The package import and manifest checks from
the repository checklist should also remain green because GCF helpers are part
of the public API surface.
