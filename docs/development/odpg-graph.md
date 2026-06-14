# ODPG Graph Development Notes

This page explains ODPG graph helpers and graph generation internals for
contributors.

## Main Code Paths

ODPG behavior lives in `open_data_products/odpg/graph.py`.

Important helpers:

- `load_graph()`
- `validate_graph()`
- `build_graph()`
- `collect_odpc_graph_nodes()`
- `render_edge_prompt()`
- `parse_generated_edges()`
- `summarize_graph()`
- `traverse_graph()`
- `analyze_graph()`
- `agent_context()`
- `render_graph_toon()`
- `generate_graph_explorer()`

CLI wrappers live in `open_data_products/odpg/cli.py` and the unified CLI.

## Graph Shape

The canonical graph document uses:

```yaml
schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: "1.0"
kind: Graph
graph:
  metadata: ...
  nodes: ...
  edges: ...
```

Some helpers accept legacy flat graph examples through `graph_payload()`, but
new examples and generated files should use the canonical `graph` wrapper.

## Validation

`validate_graph()` checks:

- required root fields;
- `kind: Graph`;
- metadata fields;
- node ids, node types, and `$ref`;
- edge `from`, `to`, `type`, and `confidence`;
- edge endpoints that must match known node ids;
- confidence values of `high`, `medium`, or `low`.

Unknown node types and non-core edge types can be warnings rather than errors
when the graph is still structurally usable.

## Building Graphs From ODPC

`build_graph()` builds nodes from ODPC fragments and uses an injected model
client to infer edges.

Flow:

1. Collect ODPC objects from a folder.
2. Create ODPG nodes with `id`, `type`, and `$ref`.
3. Render an edge-inference prompt.
4. Parse generated edge YAML.
5. Validate the final graph.

The model client is required. Do not hide live LLM calls inside this helper.

`build_graph(..., context_graph=...)` can include an existing graph as prior
edge-inference context. The helper still builds the new graph from ODPC
fragments, but the prompt prefers a sibling `.gcf`, then `.toon`, then YAML
text for the context graph.

## Generated Edge Parsing

`parse_generated_edges()` strips Markdown fences, loads YAML, and accepts only
an `edges` list. It rejects:

- unknown source or target node ids;
- missing edge type;
- missing or invalid confidence;
- non-object edge items.

Duplicate `(from, to, type)` edges are deduplicated.

## Traversal And Analysis

`traverse_graph()` performs bounded graph traversal from a start node. Keep
depth limits enforced because graph payloads can grow quickly.

`analyze_graph()` returns governance and structure findings for agent triage.
`agent_context()` extracts nearby graph context around a focus node for agent
workflows.

The unified CLI can also attach compact sidecar text to the JSON context packet
with `odpg-agent-context --context-format auto`. That option selects sibling
`.gcf`, `.toon`, or `.yaml` files for agent prompt input while still loading and
validating the canonical graph YAML.

## Graph Explorer

`generate_graph_explorer()` renders a standalone HTML explorer from graph YAML.
The explorer is a generated artifact, not an MCP-safe read-only operation.

## TOON Rendering

`render_graph_toon()` creates an optional LLM-context view of a graph. It keeps
YAML as the source of truth and renders `nodes` and `edges` as TOON tables. Use
`write_graph_toon()` or `odpg-build --toon` when a workflow needs a compact
prompt artifact.

See [`toon-development.md`](toon.md) for the shared renderer rules.

## GCF Rendering

`render_graph_gcf()` creates an experimental GCF sidecar for graph context. It
keeps YAML as the source of truth, declares nodes once, assigns deterministic
local IDs, and renders edges as compact local-ID references. Use
`write_graph_gcf()` or `odpg-build --gcf` when an agent workflow sends graph
context repeatedly or when edge identifiers dominate the prompt payload.

See [`gcf-development.md`](gcf.md) for the local measurement notes
and scope boundary.

## Tests

Use these files when changing ODPG behavior:

- `tests/test_odpg.py`
- `tests/test_functional_cli.py`
- `tests/test_generation_prompts.py` for generated graph repair and reference
  behavior.
- `tests/test_examples.py` for bundled example graph/catalog consistency.
