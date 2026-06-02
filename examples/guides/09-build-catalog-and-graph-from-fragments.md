# Guide 9: Build Catalog and Graph from the Same Fragments

This guide shows how one ODPC fragment folder can produce both an ODPC catalog
and an ODPG graph.

## 1. Prepare folders

```bash
mkdir -p odp-course/09-fragments-to-catalog-and-graph/source_docs/products
mkdir -p odp-course/09-fragments-to-catalog-and-graph/source_docs/use_cases
mkdir -p odp-course/09-fragments-to-catalog-and-graph/source_docs/objectives
mkdir -p odp-course/09-fragments-to-catalog-and-graph/source_docs/signals
mkdir -p odp-course/09-fragments-to-catalog-and-graph/fragments
mkdir -p odp-course/09-fragments-to-catalog-and-graph/output
cd odp-course/09-fragments-to-catalog-and-graph
```

## 2. Add source documents

```bash
cat > source_docs/products/customer-analytics-product.md <<'MD'
# Customer Analytics Product

The product provides customer profile, purchase, support, and churn risk data
for retention teams.
MD

cat > source_docs/use_cases/customer-retention-use-case.md <<'MD'
# Customer Retention

Retention teams need trusted customer analytics to identify customers at risk
and choose the next best action.
MD

cat > source_docs/objectives/reduce-churn-objective.txt <<'TXT'
Objective: reduce preventable churn by improving retention decision quality and
intervention timing.
TXT

cat > source_docs/signals/churn-risk-signal.txt <<'TXT'
Signal: churn risk rises when product usage drops, support tickets increase,
and renewal activity slows.
TXT
```

## 3. Generate ODPC fragments

Generate each fragment type into the same output folder, but read each type
from its own source folder:

```bash
open-data-products generate \
  --input source_docs/products/ \
  --kind product-reference \
  --output fragments/ \
  --json

open-data-products generate \
  --input source_docs/use_cases/ \
  --kind use-case \
  --output fragments/ \
  --json

open-data-products generate \
  --input source_docs/objectives/ \
  --kind objective \
  --output fragments/ \
  --json

open-data-products generate \
  --input source_docs/signals/ \
  --kind signal \
  --output fragments/ \
  --json
```

## 4. Build the ODPC catalog

```bash
open-data-products odpc-build fragments/ \
  --output output/catalog.yaml \
  --html output/catalog.html \
  --json
```

The catalog command collects the ODPC fragments into one catalog document.

## 5. Build the ODPG graph from the same fragments

```bash
open-data-products odpg-build fragments/ \
  --output output/graph.yaml \
  --id customer-retention-graph \
  --name "Customer Retention Graph" \
  --json
```

The graph command converts the ODPC fragments into ODPG nodes and uses the
configured LLM provider to infer the edges between those nodes.

## 6. Validate and open the graph explorer

```bash
open-data-products validate output/graph.yaml --json

open-data-products odpg-generate output/graph.yaml \
  --output output/graph-explorer.html \
  --json
```

Open `output/graph-explorer.html` in a browser to inspect the relationships.

## What You Learned

- ODPC fragments can feed both catalog and graph workflows.
- `odpc-build` creates one catalog from the fragment folder.
- `odpg-build` creates ODPG nodes from the same fragments and asks the LLM only
  for graph edges.
- `odpg-generate` turns the graph YAML into a browser-viewable explorer.
