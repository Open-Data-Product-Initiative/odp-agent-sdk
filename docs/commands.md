# Command Guide

This guide explains what the common `open-data-products` commands do. The
README keeps the command list compact; this page adds the intent behind each
workflow.

Most commands print human-readable output by default. Add `--json` when the
result is consumed by CI, scripts, MCP clients, or other agents.

## Common Workflows

```bash
open-data-products validate product.yaml
open-data-products generate --input source_docs/ --kind product-reference --output generated/
open-data-products odpc-build fragments/ --output catalog.yaml --html catalog.html --toon catalog.toon --gcf catalog.gcf
open-data-products odpg-build fragments/ --output graph.yaml --toon graph.toon --gcf graph.gcf
open-data-products portfolio build --objectives inputs/objectives/ --use-cases inputs/use-cases/ --signals inputs/signals/ --products inputs/products/ --output portfolio/
```

Use the command-specific sections below when you need more control or
machine-readable output.

## Cross-Spec Documents

```bash
open-data-products validate examples/product.yaml
```

Detects the document family, validates the file against the bundled schema and
SDK rules, and returns the validation result. For ODPS files, the SDK currently
supports the ODPS 4.x line.

```bash
open-data-products explain examples/odpc_catalog.yaml
```

Loads an ODPS, ODPC, ODPG, or ODPV document and returns a compact explanation
for humans and agents. Use this when you need a quick summary without reading
the whole YAML file.

```bash
open-data-products refs open_data_products/odpg/data/graph/graph.yaml
```

Lists `$ref` and `ref` pointers found in a document. This is useful when an
agent needs to discover linked artifacts without loading every target body.

```bash
open-data-products summary examples/product.yaml
```

Returns lightweight file metadata such as detected spec, size, and hash. This
is intentionally a reference summary, not the full document body. When sibling
`.gcf` or `.toon` context sidecars exist, JSON output includes
`context_artifacts` metadata so agents can discover compact context files before
reading them.

## Bundled Resources

```bash
open-data-products resources --json
```

Lists bundled schemas, prompt templates, generated indexes, vocabulary records,
and object guidance resources shipped with the SDK.

```bash
open-data-products resources --id generation.prompt.system --json
open-data-products resources --id odpc.objects --json
open-data-products resources --id odpv.terms --json
open-data-products resources --id odpg.objects --json
```

Returns metadata for one bundled resource. These commands are helpful for
agents that need to discover what guidance or generated artifacts are available
before choosing a more specific command.

## LLM Generation

These commands require a configured local or hosted provider. The default is
local Ollama, while optional embedded llama.cpp support can run GGUF models
without a separate LLM server. See [LLM generation](generation.md#llm-setup)
for setup details.

```bash
open-data-products generate --kind signal
```

Runs signal generation with default paths. By default, it reads source documents from
`open_data_products/generation/source_docs/`, uses local Ollama with Qwen 2.5,
and writes generated fragments to `open_data_products/generation/fragments/`.
When source material includes a YAML catalog or graph with a sibling `.gcf` or
`.toon` sidecar, generation prompts inline the compact sidecar text instead of
the full YAML body. Source folders include YAML files only when those compact
sidecars exist.

```bash
open-data-products generate --config open_data_products/generation/generation.config.yaml --kind signal
```

Runs generation using a config file. The config can define provider, model,
input folder, output folder, base URL, and the environment variable name that
contains the API key.

```bash
open-data-products generate --config open_data_products/generation/generation.config.yaml --provider groq --kind signal
open-data-products generate --config open_data_products/generation/generation.config.yaml --provider claude --kind signal
```

Overrides the provider selected by the config. This lets you test the same
source documents with another configured backend without editing the file.

```bash
open-data-products generate --config open_data_products/generation/generation.config.yaml --kind signal
```

Generates the selected artifact type. Supported kinds include
`product-reference`, `odps-product`, `use-case`, `objective`, `signal`, and
`graph`.

## Generated Fragment Artifacts

```bash
open-data-products validate open_data_products/generation/fragments/odpg_graph.yaml
```

Validates the generated ODPG graph YAML. Run this after LLM generation to catch
invalid graph structure before opening the graph explorer.

```bash
open-data-products odpg-generate open_data_products/generation/fragments/odpg_graph.yaml --output /tmp/odp-generation-graph.html
```

Builds a standalone HTML graph explorer from the generated ODPG graph file.
The `/tmp` output path keeps generated browser artifacts out of the repository.

## ODPC Catalog Helpers

```bash
open-data-products odpc-build examples/odpc_catalog_fragments/ --output /tmp/odp-catalog.yaml
```

Builds one ODPC catalog YAML file from fragment files in a folder.

```bash
open-data-products odpc-build examples/odpc_catalog_fragments/ --output /tmp/odp-catalog.yaml --html /tmp/odp-catalog.html
```

Builds the ODPC catalog YAML and a standalone HTML catalog page in one run.

```bash
open-data-products odpc-build examples/odpc_catalog_fragments/ --output /tmp/odp-catalog.yaml --toon /tmp/odp-catalog.toon --gcf /tmp/odp-catalog.gcf
```

Builds the ODPC catalog YAML and optional compact sidecars for LLM prompt
context. TOON uses compact tables; GCF uses pipe-delimited rows. YAML remains
the source of truth.

```bash
open-data-products odpc-summary /tmp/odp-catalog.yaml
```

Summarizes catalog metadata and object counts from a built ODPC catalog.

```bash
open-data-products odpc-search "catalog data" --limit 3
```

Searches the bundled ODPC object guidance index. Use this when you need help
choosing or explaining catalog object types.

## ODPV Vocabulary Helpers

```bash
open-data-products odpv-summary
```

Summarizes the bundled ODPV vocabulary, including sections and term counts.

```bash
open-data-products odpv-search "governance policy risk" --limit 3
```

Searches vocabulary terms by keyword.

```bash
open-data-products odpv-resolve "reusable data asset"
```

Resolves free text or aliases to a canonical ODPV term.

```bash
open-data-products odpv-explain DataProduct
```

Returns the canonical vocabulary packet for one term.

```bash
open-data-products odpv-relationship DataProduct supports UseCase
```

Checks whether an ODPV relationship is valid for the given source and target
types.

```bash
open-data-products odpv-context DataProduct
```

Returns an agent-ready context packet for one vocabulary term.

## ODPG Graph Reasoning

```bash
open-data-products odpg-summary open_data_products/odpg/data/graph/graph.yaml
```

Summarizes graph metadata, node counts, edge counts, and relationship types.

```bash
open-data-products odpg-traverse open_data_products/odpg/data/graph/graph.yaml --start AGENT-AVIATION-001 --depth 2
```

Traverses relationship paths from a focus node up to the requested depth.

```bash
open-data-products odpg-analyze open_data_products/odpg/data/graph/graph.yaml
```

Runs graph analysis checks for strategic and governance signals.

```bash
open-data-products odpg-agent-context open_data_products/odpg/data/graph/graph.yaml --node AGENT-AVIATION-001 --depth 2
```

Extracts the graph neighborhood around one node in a compact format suitable
for agents.

```bash
open-data-products odpg-agent-context open_data_products/odpg/data/graph/graph.yaml \
  --node AGENT-AVIATION-001 \
  --context-format auto \
  --json
```

Adds a `contextArtifact` object to the JSON payload. `auto` prefers a sibling
`.gcf` file, then `.toon`, then the original YAML text. The graph YAML remains
the canonical file used for loading and validation.

```bash
open-data-products odpg-build examples/odpc_catalog_fragments/ --output /tmp/odp-graph.yaml --toon /tmp/odp-graph.toon --gcf /tmp/odp-graph.gcf
```

Builds the ODPG graph YAML and optional compact sidecars for LLM prompt
context. TOON keeps nodes and edges as tables. GCF uses local node IDs so graph
edges do not repeat full endpoint identifiers. YAML remains the source of truth.
Add `--context-graph previous-graph.yaml` when edge inference should see an
existing graph as prompt context; the command prefers `previous-graph.gcf`, then
`.toon`, then YAML text.

```bash
open-data-products odpg-generate open_data_products/odpg/data/graph/graph.yaml --output /tmp/odp-graph-explorer.html
```

Generates a standalone HTML graph explorer for a bundled or user-supplied ODPG
graph.

```bash
open-data-products odpg-convert --input examples/graph.graphml --output /tmp/odp-converted-graph.yaml
```

Converts external graph formats to ODPG YAML. Supported inputs include JSON-LD,
GraphML, GraphSON, RDF/Turtle, OpenCypher, GQL, and Gremlin.

## Portfolio Workspaces

Developer implementation notes for this workflow live in
[`portfolio-development.md`](portfolio-development.md).

```bash
open-data-products portfolio build \
  --objectives inputs/objectives/ \
  --use-cases inputs/use-cases/ \
  --signals inputs/signals/ \
  --products inputs/products/ \
  --title "Customer Intelligence Portfolio" \
  --output generated/portfolio/
```

Builds a portfolio workspace from source lanes. The command uses the configured
LLM provider to create an internal portfolio plan, writes ODPC fragments and
catalog YAML, linked ODPS product specs, ODPG graph YAML, and then renders the
static `index.html` browser experience. Missing output folders are created
before writing. Add `--json` when you want a structured report with source
counts, artifact counts, created/updated/unchanged files, warnings, link
findings, and the browser entry point.
The structured report also includes validation results for the ODPC catalog,
ODPG graph, and linked ODPS product specs. Portfolio commands default to
validation warning mode: they complete when generated ODPS drafts are valid
YAML but fail schema validation, while the JSON report keeps `valid: false` and
includes the exact schema errors.
The LLM prompt asks for one structured YAML portfolio plan with explicit
ProductReference-to-ODPS product linking rules, graph edge endpoint rules, and
warnings for weak evidence.
Use `--title` to set the human-controlled workspace title. The SDK persists
that title in `portfolio-state.yaml` and reuses it on reruns so the page title,
catalog name, and graph name do not drift with LLM output.
Use `--strict-validation` when a failing schema check should make the command
return a non-zero exit code, for example in CI.

After the first build, the workspace can be rerun without repeating the source
folder flags:

```bash
open-data-products portfolio build generated/portfolio/
```

The command reuses source lane paths saved in `portfolio-state.yaml`, compares
current source hashes with the previous run, preserves stable artifact IDs for
unchanged concepts, snapshots the previous `index.html`, and reports source
changes plus removed source files in the command output.

```bash
open-data-products portfolio sync generated/portfolio/
```

Synchronizes a portfolio from edited YAML artifacts without calling an LLM. Use
this when ODPC fragment YAML, ODPS product YAML, or graph YAML has been updated
directly and the portfolio should be refreshed from those files. The command
rebuilds `odpc/catalog.yaml` from `odpc/fragments/*.yaml`, keeps source lane
state, updates the identity registry, snapshots the previous `index.html`, and
renders a new browser view.
Use `--strict-validation` to make schema-invalid synced drafts return a
non-zero exit code.

```bash
open-data-products portfolio render generated/portfolio/
```

Renders one static `index.html` from an existing portfolio workspace. The page
combines ODPC catalog objects, linked ODPS product specs, ODPG graph data,
artifact detail views, version links, and About information into one
browser-openable file. Missing output parent directories are created before
writing.
Use `--strict-validation` to make schema-invalid rendered workspaces return a
non-zero exit code.

```bash
open-data-products portfolio localize generated/portfolio/ \
  --languages "fi,sv" \
  --provider claude \
  --model claude-sonnet-4-5
```

Localizes the browser experience without changing canonical ODPC, ODPS, or
ODPG YAML artifacts. The command translates human-facing HTML strings with the
configured LLM provider, writes `portfolio-i18n.yaml`, renders localized static
pages such as `index.fi.html` and `index.sv.html`, and updates `index.html`
with a language selector in the top bar. Language values use BCP 47 language
tags such as `fi`, `sv`, `en-GB`, or `pt-BR`.

```bash
open-data-products portfolio explain generated/portfolio/
```

Summarizes a portfolio workspace, including the browser entry point and counts
for objectives, use cases, signals, product references, ODPS product specs,
graph nodes, graph edges, and available versions.

```bash
open-data-products portfolio refresh generated/portfolio/
```

Refreshes an existing portfolio workspace using source lane paths saved in
`portfolio-state.yaml`. By default, refresh scans all saved source lanes but
sends only new or changed source files to the LLM. The generated delta is then
merged into the existing portfolio so unchanged artifacts are preserved.

Use `--all-sources` when the full evidence set should be reprocessed:

```bash
open-data-products portfolio refresh generated/portfolio/ --all-sources
```

Before writing the refreshed latest files, the command snapshots the previous
`index.html` and `portfolio.yaml` under `versions/<timestamp>/`, then writes a
`report.json` for the refresh run. The latest `index.html` includes a version
switcher so previous HTML snapshots can be opened from the browser. The final
JSON report includes `sourceCounts` for all current sources,
`processedSourceCounts` for the files sent to the LLM, and validation results
for the refreshed catalog, graph, and linked product specs.
Use `--strict-validation` when refresh should fail on schema-invalid drafts.

## Product-Level Data Contract Inspection

```bash
open-data-products product resolve-contracts examples/product.yaml --json
```

Finds Data Contract references in an ODPS product and resolves local reference
metadata.

```bash
open-data-products product contract-schema examples/contract.yaml --json
```

Extracts normalized model and field information from a local Data Contract
file. This command does not require the optional `datacontract-cli` adapter.

See [Data Contract workflows](data-contracts.md) for optional validation,
alignment, reports, and export commands that use `datacontract-cli`.
