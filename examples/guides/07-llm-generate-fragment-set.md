# Guide 7: Generate a Full Fragment Set from Source Documents

This guide uses local Ollama/Qwen 2.5 to generate multiple ODPC fragments and
one ODPG graph from a folder of source documents.

## 1. Prepare folders

```bash
mkdir -p odp-course/07-fragment-set/source_docs
mkdir -p odp-course/07-fragment-set/fragments
cd odp-course/07-fragment-set
```

## 2. Add Markdown and text source files

```bash
cat > source_docs/airport-operations-product.md <<'MD'
# Airport Operations Performance Product

This data product combines flight schedule, gate assignment, turnaround status,
crew readiness, and departure delay information. It supports operational
decision making in the airport operations control center.
MD

cat > source_docs/delay-risk-use-case.md <<'MD'
# Delay Risk Monitoring Use Case

Operations controllers need to identify flights at risk of delayed departure
at least 20 minutes before scheduled off-block time. The use case supports
prioritizing recovery actions for crews, gates, baggage, and cleaning.
MD

cat > source_docs/reduce-delay-objective.txt <<'TXT'
Business objective: reduce average departure delay minutes for short-haul
flights during morning and evening peak periods. The objective is measured by
delay minutes, number of recovered flights, and operational response time.
TXT

cat > source_docs/turnaround-delay-signal.txt <<'TXT'
Signal: turnaround delay risk increases when inbound arrival is late, baggage
unloading has not started, cleaning crew is not assigned, or the gate has a
conflict with another aircraft movement.
TXT
```

## 3. Generate the full set

```bash
open-data-products generate \
  --input source_docs/ \
  --output fragments/ \
  --json
```

## 4. Inspect generated artifacts

```bash
ls fragments/
```

Expected artifact types:

- `product_reference_*.yaml`
- `use_case_*.yaml`
- `business_objective_*.yaml`
- `signal_*.yaml`
- `odpg_graph.yaml`

## 5. Validate the graph

```bash
open-data-products validate fragments/odpg_graph.yaml --json
```

## What You Learned

- Folder input lets the model consider several source documents together.
- Generated fragments are separate YAML files.
- The generated `odpg_graph.yaml` links the generated fragment ids.
