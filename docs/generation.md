# Local Generation

The SDK can use a local LLM through Ollama to turn plain source documents into
standards-ready ODPC fragments and ODPG graph YAML. This workflow stops before
catalog publishing: it produces source-backed fragment files and a graph file
that can be validated, inspected, and used by the existing ODPC/ODPG helpers.

## Requirements

Local generation requires Ollama running locally and Qwen 2.5 available:

```bash
ollama pull qwen2.5
ollama list
```

The default model is `qwen2.5`. Later provider-specific configuration can add
online LLM backends, but the current SDK generation path is local-only.

## Folder Layout

Generation assets live together under `open_data_products/generation/`:

```text
open_data_products/generation/
  data/prompts/        # editable prompt templates
  source_docs/         # plain Markdown/text input files
  fragments/           # generated ODPC fragments, ODPG graph, HTML explorer
```

The `source_docs/` folder is generic. Replace the bundled sample files with
source documents for any domain. The generator reads `.md` and `.txt` files.

Filenames are included in prompts as source boundaries, for example:

```text
--- Source file: turnaround-delay-signal.txt ---
```

The SDK does not route files by filename. In holistic generation, every source
file is passed to each artifact prompt. In single-artifact generation, `--kind`
selects the prompt. Descriptive filenames still help the model infer intent, so
prefer names like `*-product.md`, `*-signal.txt`, `*-use-case.md`, and
`*-objective.txt`.

## Generate One Artifact

Use `--kind` when one source file should produce one selected artifact type:

```bash
open-data-products generate \
  --input open_data_products/generation/source_docs/turnaround-delay-signal.txt \
  --kind signal \
  --output open_data_products/generation/fragments/ \
  --model qwen2.5 \
  --json
```

Supported `--kind` values are:

- `product`
- `use-case`
- `objective`
- `signal`
- `graph`

Single-artifact generation writes one YAML artifact to the output folder. For
fragment kinds, the final filename comes from the generated object id, not from
the source filename.

## Generate The Full Set

Run without `--kind` to generate all supported artifacts from a source folder.
The default input is `open_data_products/generation/source_docs/` and the
default output is `open_data_products/generation/fragments/`, so this works:

```bash
open-data-products generate --json
```

You can also set the folders explicitly:

```bash
open-data-products generate \
  --input open_data_products/generation/source_docs/ \
  --output open_data_products/generation/fragments/ \
  --model qwen2.5 \
  --json
```

The output folder contains separate ODPC fragment files:

- `productReference:` files such as `product_reference_<id>.yaml`
- `useCase:` files such as `use_case_<id>.yaml`
- `businessObjective:` files such as `business_objective_<id>.yaml`
- `signal:` files such as `signal_<id>.yaml`

It also contains `odpg_graph.yaml`, which connects the generated fragment ids.

## Validate And Build From Generated Fragments

Validate the graph:

```bash
open-data-products validate open_data_products/generation/fragments/odpg_graph.yaml --json
```

Build an ODPC catalog from generated fragments:

```bash
open-data-products odpc-build open_data_products/generation/fragments/ \
  --output catalog.yaml \
  --json
```

Build YAML and standalone HTML together:

```bash
open-data-products odpc-build open_data_products/generation/fragments/ \
  --output catalog.yaml \
  --html catalog.html \
  --json
```

Generate an ODPG graph explorer HTML page:

```bash
open-data-products odpg-generate open_data_products/generation/fragments/odpg_graph.yaml \
  --output open_data_products/generation/fragments/graph_explorer.html \
  --json
```

## Prompts

Prompt templates are plain Markdown files under
`open_data_products/generation/data/prompts/`:

- `system.md`
- `odps_data_product_fragment.md`
- `odpc_use_case_fragment.md`
- `odpc_objective_fragment.md`
- `odpc_signal_fragment.md`
- `odpg_graph_yaml.md`

Use Python helpers to inspect or render prompts:

```python
from open_data_products import (
    list_generation_prompts,
    load_generation_prompt,
    render_generation_prompt,
)

print(list_generation_prompts())
print(load_generation_prompt("odpc_signal_fragment.md"))
print(render_generation_prompt(
    "odpc_signal_fragment.md",
    "open_data_products/generation/source_docs",
))
```

The same prompt files are also listed through bundled resources:

```bash
open-data-products resources --id generation.prompt.system --json
open-data-products resources --json
```
