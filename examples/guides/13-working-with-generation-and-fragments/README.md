# Lecture 13: Working with Generation and Fragments

A fragment is a small, valid, standalone YAML document that describes one
portfolio object or one narrow object set. It is intended to be collected into a
larger ODPC catalog or used as node input for an ODPG graph.

Examples:

- `product_reference_<id>.yaml` contains one ODPC product reference
- `use_case_<id>.yaml` contains one ODPC use case
- `business_objective_<id>.yaml` contains one ODPC business objective
- `signal_<id>.yaml` contains one ODPC signal

Fragments are intermediate authoring units. They are not the final catalog, and
they are usually not full ODPS product specs. This lesson generates multiple
ODPC fragments from type-specific source folders.

## 1. Prepare folders

```bash
mkdir -p odps-sdk-guides/13-fragments/source_docs/products
mkdir -p odps-sdk-guides/13-fragments/source_docs/use-cases
mkdir -p odps-sdk-guides/13-fragments/source_docs/objectives
mkdir -p odps-sdk-guides/13-fragments/source_docs/signals
mkdir -p odps-sdk-guides/13-fragments/fragments
cd odps-sdk-guides/13-fragments
```

## 2. Add Markdown and text source files

```bash
cat > source_docs/products/airport-operations-product.md <<'MD'
# Airport Operations Performance Product

This data product combines flight schedule, gate assignment, turnaround status,
crew readiness, and departure delay information. It supports operational
decision making in the airport operations control center.
MD

cat > source_docs/use-cases/delay-risk-use-case.md <<'MD'
# Delay Risk Monitoring Use Case

Operations controllers need to identify flights at risk of delayed departure
at least 20 minutes before scheduled off-block time. The use case supports
prioritizing recovery actions for crews, gates, baggage, and cleaning.
MD

cat > source_docs/objectives/reduce-delay-objective.txt <<'TXT'
Business objective: reduce average departure delay minutes for short-haul
flights during morning and evening peak periods. The objective is measured by
delay minutes, number of recovered flights, and operational response time.
TXT

cat > source_docs/signals/turnaround-delay-signal.txt <<'TXT'
Signal: turnaround delay risk increases when inbound arrival is late, baggage
unloading has not started, cleaning crew is not assigned, or the gate has a
conflict with another aircraft movement.
TXT
```

## 3. Generate product fragments

```bash
open-data-products generate \
  --input source_docs/products/ \
  --kind product-reference \
  --output fragments/

open-data-products generate \
  --input source_docs/use-cases/ \
  --kind use-case \
  --output fragments/

open-data-products generate \
  --input source_docs/objectives/ \
  --kind objective \
  --output fragments/

open-data-products generate \
  --input source_docs/signals/ \
  --kind signal \
  --output fragments/
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

## 5. Build and validate a catalog

```bash
open-data-products odpc-build fragments/ \
  --output catalog.yaml

open-data-products validate catalog.yaml
```

## What You Learned

- Type-specific folder input keeps each selected prompt focused.
- Generated fragments are separate YAML files.
- The generated ODPC fragments can be collected into a catalog.
- Fragments make portfolio building easier because each object can be reviewed
  independently before catalog and graph assembly.

## Next Lesson

Continue to [Lecture 14: Working with ODPG graphs](../14-working-with-odpg-graphs/).
