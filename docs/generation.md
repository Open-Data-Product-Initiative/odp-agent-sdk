# LLM Generation

The SDK can use a configured LLM provider to turn plain source documents into
standards-ready ODPC fragments and ODPG graph YAML. The default provider is
local Ollama with Qwen 2.5, and OpenAI can be selected through the generation
config. This workflow stops before catalog publishing: it produces
source-backed fragment files and a graph file that can be validated, inspected,
and used by the existing ODPC/ODPG helpers.

## Requirements

Default local generation requires Ollama running locally and Qwen 2.5
available:

```bash
ollama pull qwen2.5
ollama list
```

The default provider is `ollama` and the default model is `qwen2.5`. External
providers can be selected with a generation config file. OpenAI generation
requires `OPENAI_API_KEY` in the environment; the SDK stores only the
environment variable name in config.

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

## Provider Configuration

Use a generation config file when you want to select a provider, model, input
folder, and output folder together. This is the normal path:

```bash
open-data-products generate \
  --config open_data_products/generation/generation.config.example.yaml \
  --json
```

To use another provider already defined in the config, override only the
provider:

```bash
open-data-products generate \
  --config generation.config.yaml \
  --provider groq \
  --json
```

CLI flags are for temporary overrides. Use them when testing a different model,
input, or output without editing the config:

```bash
open-data-products generate \
  --config generation.config.yaml \
  --provider openai \
  --model gpt-4.1-mini \
  --input source_docs/ \
  --output fragments/ \
  --json
```

Example config:

```yaml
provider: ollama
model: qwen2.5
input: open_data_products/generation/source_docs/
output: open_data_products/generation/fragments/

providers:
  ollama:
    type: ollama
    baseUrl: http://localhost:11434

  openai:
    type: openai
    model: gpt-4.1-mini
    baseUrl: https://api.openai.com/v1
    apiKeyEnv: OPENAI_API_KEY

  # OpenAI-compatible Responses API providers. Select one with
  # `--provider openrouter` or `--provider groq`, and choose a model supported
  # by that provider.
  openrouter:
    type: openai
    model: openai/gpt-4.1-mini
    baseUrl: https://openrouter.ai/api/v1
    apiKeyEnv: OPENROUTER_API_KEY

  groq:
    type: openai
    model: openai/gpt-oss-120b
    baseUrl: https://api.groq.com/openai/v1
    apiKeyEnv: GROQ_API_KEY

  # Anthropic Claude uses its own Messages API client.
  claude:
    type: anthropic
    model: claude-sonnet-4-5
    baseUrl: https://api.anthropic.com/v1
    apiKeyEnv: ANTHROPIC_API_KEY
    version: "2023-06-01"
    maxTokens: 4096

  # Providers with different auth or request formats should get a dedicated
  # SDK client before being enabled here, for example Azure OpenAI, Google
  # Gemini, Mistral, Cohere, and Bedrock.
```

The config file is safe to commit when it only references secret environment
variable names. Do not store API keys in YAML. Set the required provider key in
the environment before running generation:

```bash
export OPENAI_API_KEY="..."
open-data-products generate --config generation.config.yaml --json
```

The SDK never prints API key values in JSON output or error messages. If a
required secret env var is missing, generation fails before sending a request.
OpenAI HTTPS requests use the package `certifi` CA bundle, which avoids local
Python certificate-store issues without disabling TLS verification.

Provider entries with `type: openai` use the OpenAI Responses request shape,
Bearer token authentication, and `baseUrl + /responses`. That supports OpenAI
and providers that expose a compatible Responses API endpoint, such as
OpenRouter and Groq.

Provider entries with `type: anthropic` use the Anthropic Messages API request
shape, `x-api-key` authentication, `anthropic-version`, and
`baseUrl + /messages`. Use this profile for Claude models. Providers with
different auth headers or request formats should be added as dedicated clients
instead of forced into an existing profile.

Smoke tests have produced valid ODPC signal fragments with OpenAI
`gpt-4.1-mini` and Groq `openai/gpt-oss-120b`. Provider availability, model
permissions, and output quality still depend on the account, model, and source
documents used at runtime.

To smoke-test OpenAI with one small source file while overriding config paths:

```bash
export OPENAI_API_KEY="..."
open-data-products generate \
  --config generation.config.yaml \
  --provider openai \
  --model gpt-4.1-mini \
  --input open_data_products/generation/source_docs/baggage-belt-congestion-signal.txt \
  --kind signal \
  --output /tmp/odp-openai-test \
  --json
```

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
