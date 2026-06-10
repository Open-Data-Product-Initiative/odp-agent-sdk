# Lecture 14: Working with ODPG Graphs

ODPG graphs describe relationships between portfolio objects. Products, use
cases, business objectives, and signals become nodes. Relationships become
edges. This helps AI agents and portfolio reviewers understand how artifacts
connect.

The SDK can help you work with graphs in several ways:

- build an ODPG graph from ODPC fragments
- validate graph YAML
- summarize graph contents
- extract context around a focus node for agents
- render a standalone graph explorer HTML file
- convert external graph formats such as GraphML into ODPG YAML

This lesson focuses on two practical tasks: building a graph from fragments and
getting agent-ready context from the graph.

## 1. Create A Lesson Folder

```bash
mkdir -p odps-sdk-guides/14-odpg-graph/fragments
mkdir -p odps-sdk-guides/14-odpg-graph/output
```

## 2. Add Fragment Files

From the repository root, copy the sample fragment files from this lesson
folder:

```bash
cp examples/guides/14-working-with-odpg-graphs/fragments/*.yaml \
  odps-sdk-guides/14-odpg-graph/fragments/

cd odps-sdk-guides/14-odpg-graph
```

You can also use the fragments generated in Lecture 13.

The folder should contain files shaped like:

- `product_reference_*.yaml`
- `use_case_*.yaml`
- `business_objective_*.yaml`
- `signal_*.yaml`

## 3. Build The Graph

```bash
open-data-products odpg-build fragments/ \
  --output output/graph.yaml \
  --id customer-retention-graph \
  --name "Customer Retention Graph"
```

`odpg-build` turns the fragment objects into graph nodes and infers
relationships between them.

## 4. Validate And Render The Graph

```bash
open-data-products validate output/graph.yaml

open-data-products odpg-summary output/graph.yaml

open-data-products odpg-generate output/graph.yaml \
  --output output/graph-explorer.html
```

Open `output/graph-explorer.html` in a browser to inspect the graph visually.

## 5. Get Agent Context Around One Node

```bash
open-data-products odpg-agent-context output/graph.yaml \
  --node PR-CUSTOMER-HEALTH-SIGNALS \
  --depth 2
```

Agent context is useful when an AI agent or workflow needs the relationships
around one product, use case, objective, or signal without reading the whole
graph manually.

## What You Learned

- ODPG graphs make product, use case, objective, and signal relationships
  explicit.
- The SDK can build, validate, summarize, convert, render, and inspect graphs.
- `odpg-build` creates graph YAML from ODPC fragments.
- `odpg-generate` creates a standalone HTML graph explorer.
- `odpg-agent-context` extracts relationship context around one focus node.

## Next Lesson

Continue to [Lecture 15: Working with ODPC catalogs](../15-working-with-odpc-catalogs/).
