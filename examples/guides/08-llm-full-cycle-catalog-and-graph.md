# Guide 8: Full Cycle from Source Docs to Catalog and Graph HTML

This guide shows the complete LLM-assisted flow:

1. Put `.md` and `.txt` source files into a source directory.
2. Generate ODPC fragments and ODPG graph YAML.
3. Build an ODPC catalog YAML file.
4. Build an ODPC catalog HTML page.
5. Generate an ODPG graph explorer HTML page.

## 1. Prepare folders

```bash
mkdir -p odp-course/08-full-cycle/source_docs
mkdir -p odp-course/08-full-cycle/fragments
mkdir -p odp-course/08-full-cycle/output
cd odp-course/08-full-cycle
```

## 2. Add source documents

Use a mix of Markdown and text files. Descriptive filenames help the model
understand the intended artifact type.

```bash
cat > source_docs/airport-operations-product.md <<'MD'
# Airport Operations Performance Product

The product provides a trusted operational view of flights, gates, turnaround
milestones, baggage status, cleaning readiness, and delay risk. Primary users
are airport operations controllers and airline station managers.
MD

cat > source_docs/passenger-flow-product.md <<'MD'
# Passenger Flow Queue Product

The product combines security wait time, passenger count, checkpoint capacity,
and boarding gate demand. It helps terminal operations prevent queue congestion
and missed connections.
MD

cat > source_docs/delay-risk-use-case.md <<'MD'
# Flight Delay Risk Monitoring

Operations teams need to detect flights likely to miss scheduled departure.
The use case supports early intervention for gate conflicts, turnaround tasks,
crew readiness, and baggage loading.
MD

cat > source_docs/connection-protection-use-case.md <<'MD'
# Passenger Connection Protection

The airport wants to identify inbound passengers at risk of missing outbound
connections. The use case supports gate coordination, passenger assistance,
and proactive disruption management.
MD

cat > source_docs/reduce-delay-objective.txt <<'TXT'
Objective: reduce average departure delay minutes and improve recovered flight
count during peak operating windows. Success is measured by delay minutes,
recovery actions completed, and passenger connection success rate.
TXT

cat > source_docs/turnaround-delay-signal.txt <<'TXT'
Signal: turnaround delay risk rises when inbound arrival is late, unloading has
not started, cleaning crew is missing, fueling is delayed, or a gate conflict
exists.
TXT

cat > source_docs/security-queue-signal.txt <<'TXT'
Signal: security queue surge risk rises when passenger volume exceeds planned
checkpoint capacity and estimated wait time crosses the operating threshold.
TXT
```

## 3. Generate fragments and graph YAML

This command uses the default local provider, Ollama with Qwen 2.5:

```bash
open-data-products generate \
  --input source_docs/ \
  --output fragments/ \
  --json
```

The `fragments/` folder should now contain separate ODPC fragments and
`odpg_graph.yaml`.

## 4. Validate the generated ODPG graph

```bash
open-data-products validate fragments/odpg_graph.yaml --json
```

Fix source text or rerun generation if validation fails.

## 5. Build the ODPC catalog YAML and HTML

```bash
open-data-products odpc-build fragments/ \
  --output output/catalog.yaml \
  --html output/catalog.html \
  --json
```

Open `output/catalog.html` in a browser to inspect the human-friendly catalog.

## 6. Generate the ODPG graph explorer

```bash
open-data-products odpg-generate fragments/odpg_graph.yaml \
  --output output/graph-explorer.html \
  --json
```

Open `output/graph-explorer.html` in a browser to explore the generated graph.

## 7. Optional checks

```bash
open-data-products odpc-summary output/catalog.yaml --json
open-data-products odpg-summary fragments/odpg_graph.yaml
```

## What You Learned

- Source documents can be plain `.md` and `.txt` files.
- Generation creates separate ODPC fragment files, not one large mixed file.
- The generated fragments can become an ODPC catalog.
- The generated ODPG graph can become an interactive HTML explorer.
