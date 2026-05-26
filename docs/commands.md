# Command Guide

This guide explains what the common `open-data-products` commands do. The
README keeps the command list compact; this page adds the intent behind each
workflow.

Most commands print human-readable output by default. Add `--json` when the
result is consumed by CI, scripts, MCP clients, or other agents.

## Cross-Spec Documents

```bash
open-data-products validate examples/product.yaml --json
```

Detects the document family, validates the file against the bundled schema and
SDK rules, and returns the validation result. For ODPS files, the SDK currently
supports the ODPS 4.x line.

```bash
open-data-products explain examples/odpc_catalog.yaml --json
```

Loads an ODPS, ODPC, ODPG, or ODPV document and returns a compact explanation
for humans and agents. Use this when you need a quick summary without reading
the whole YAML file.

```bash
open-data-products refs open_data_products/odpg/data/graph/graph.yaml --json
```

Lists `$ref` and `ref` pointers found in a document. This is useful when an
agent needs to discover linked artifacts without loading every target body.

```bash
open-data-products summary examples/product.yaml
```

Returns lightweight file metadata such as detected spec, size, and hash. This
is intentionally a reference summary, not the full document body.

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

These commands require local Ollama or configured provider credentials. See
[LLM generation](generation.md#llm-setup) for setup details.

```bash
open-data-products generate --json
```

Runs the default generation workflow. By default, it reads source documents from
`open_data_products/generation/source_docs/`, uses local Ollama with Qwen 2.5,
and writes generated fragments to `open_data_products/generation/fragments/`.

```bash
open-data-products generate --config open_data_products/generation/generation.config.yaml --json
```

Runs generation using a config file. The config can define provider, model,
input folder, output folder, base URL, and the environment variable name that
contains the API key.

```bash
open-data-products generate --config open_data_products/generation/generation.config.yaml --provider groq --json
open-data-products generate --config open_data_products/generation/generation.config.yaml --provider claude --json
```

Overrides the provider selected by the config. This lets you test the same
source documents with another configured backend without editing the file.

```bash
open-data-products generate --config open_data_products/generation/generation.config.yaml --kind signal --json
```

Generates one artifact type instead of the full set. Supported kinds include
`product`, `use-case`, `objective`, `signal`, and `graph`.

## Generated Fragment Artifacts

```bash
open-data-products validate open_data_products/generation/fragments/odpg_graph.yaml --json
```

Validates the generated ODPG graph YAML. Run this after LLM generation to catch
invalid graph structure before opening the graph explorer.

```bash
open-data-products odpg-generate open_data_products/generation/fragments/odpg_graph.yaml --output /tmp/odp-generation-graph.html --json
```

Builds a standalone HTML graph explorer from the generated ODPG graph file.
The `/tmp` output path keeps generated browser artifacts out of the repository.

## ODPC Catalog Helpers

```bash
open-data-products odpc-build examples/odpc_catalog_fragments/ --output /tmp/odp-catalog.yaml --json
```

Builds one ODPC catalog YAML file from fragment files in a folder.

```bash
open-data-products odpc-build examples/odpc_catalog_fragments/ --output /tmp/odp-catalog.yaml --html /tmp/odp-catalog.html --json
```

Builds the ODPC catalog YAML and a standalone HTML catalog page in one run.

```bash
open-data-products odpc-summary /tmp/odp-catalog.yaml --json
```

Summarizes catalog metadata and object counts from a built ODPC catalog.

```bash
open-data-products odpc-search "catalog data" --limit 3 --json
```

Searches the bundled ODPC object guidance index. Use this when you need help
choosing or explaining catalog object types.

## ODPV Vocabulary Helpers

```bash
open-data-products odpv-summary --json
```

Summarizes the bundled ODPV vocabulary, including sections and term counts.

```bash
open-data-products odpv-search "governance policy risk" --limit 3 --json
```

Searches vocabulary terms by keyword.

```bash
open-data-products odpv-resolve "reusable data asset" --json
```

Resolves free text or aliases to a canonical ODPV term.

```bash
open-data-products odpv-explain DataProduct --json
```

Returns the canonical vocabulary packet for one term.

```bash
open-data-products odpv-relationship DataProduct supports UseCase --json
```

Checks whether an ODPV relationship is valid for the given source and target
types.

```bash
open-data-products odpv-context DataProduct --json
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
open-data-products odpg-generate open_data_products/odpg/data/graph/graph.yaml --output /tmp/odp-graph-explorer.html --json
```

Generates a standalone HTML graph explorer for a bundled or user-supplied ODPG
graph.

```bash
open-data-products odpg-convert --input examples/graph.graphml --output /tmp/odp-converted-graph.yaml --json
```

Converts external graph formats to ODPG YAML. Supported inputs include JSON-LD,
GraphML, GraphSON, RDF/Turtle, OpenCypher, GQL, and Gremlin.

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
