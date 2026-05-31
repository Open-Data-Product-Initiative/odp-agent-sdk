# LLM Generation

The SDK can use a configured LLM provider to turn plain source documents into
standards-ready ODPC fragments and ODPG graph YAML. The default provider is
local Ollama with Qwen 2.5, but the same generation workflow also supports
local OpenAI-compatible servers such as LM Studio, vLLM, llama.cpp server,
LocalAI, text-generation-webui, and other compatible local runtimes. Through
those servers, the SDK can run locally hosted models such as Llama, DeepSeek,
Qwen, Mistral, Mixtral, Phi, Gemma, Code Llama, StarCoder, Yi, Command R,
Falcon, Granite, Nemotron, Vicuna, WizardLM, and other models exposed by the
selected local runtime.

Online providers can also be selected through the generation config, including
OpenAI-compatible providers and Claude. This workflow stops before catalog
publishing: it produces source-backed fragment files and a graph file that can
be validated, inspected, and used by the existing ODPC/ODPG helpers.

## LLM Setup

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

For LM Studio and similar local servers, use a provider entry with
`type: openai-chat` and set the model to the name loaded in that server:

```bash
open-data-products generate \
  --config my-generation.config.yaml \
  --provider lmstudio \
  --model deepseek-r1-distill-qwen-7b \
  --input source_docs/ \
  --kind signal \
  --output generated/ \
  --json
```

## Folder Layout

Generation assets live together under `open_data_products/generation/`:

```text
open_data_products/generation/
  data/prompts/        # editable prompt templates
  source_docs/         # plain Markdown/text input files
  fragments/           # generated ODPC fragments, ODPG graph, HTML explorer
```

When installed from PyPI, bundled prompt templates are package data. Copy them
to a project-owned folder before editing:

```bash
open-data-products config generation --copy-prompts-to prompts/
```

The `source_docs/` folder is generic. Replace the bundled sample files with
source documents for any domain. The generator reads `.md` and `.txt` files.

Filenames are included in prompts as source boundaries, for example:

```text
--- Source file: turnaround-delay-signal.txt ---
```

The SDK does not route files by filename. The `--kind` option selects the
artifact prompt to run. Descriptive filenames still help the model infer intent,
so prefer names like `*-product.md`, `*-signal.txt`, `*-use-case.md`, and
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

## Generate From A Folder

Use an explicit `--kind` value when generating from a source folder:

```bash
open-data-products generate \
  --input open_data_products/generation/source_docs/ \
  --kind product \
  --output open_data_products/generation/fragments/ \
  --model qwen2.5 \
  --json
```

For selected-kind folder generation, each `.md` or `.txt` source document is
processed separately with the selected prompt. The output folder contains one
or more matching artifacts, depending on what the model can extract:

- `productReference:` files such as `product_reference_<id>.yaml`
- `useCase:` files such as `use_case_<id>.yaml`
- `businessObjective:` files such as `business_objective_<id>.yaml`
- `signal:` files such as `signal_<id>.yaml`

It also contains `odpg_graph.yaml`, which connects the generated fragment ids.

## Provider Configuration

Use a generation config file when you want to select a provider, model, input
folder, and output folder together. When installed from PyPI, treat the bundled
config as a template inside the package, not as the file to edit. Copy it to a
project-owned path first. The `my-generation.config.yaml` name is only an
example for your copied file. You can also pass a folder path, such as
`--copy-to config/`, and missing folders are created automatically:

```bash
open-data-products config generation --copy-to my-generation.config.yaml
open-data-products config generation --copy-prompts-to prompts/
```

Then inspect or edit `my-generation.config.yaml`, validate it, and pass it
explicitly:

```bash
open-data-products config generation --config my-generation.config.yaml --print
open-data-products config generation --config my-generation.config.yaml --check
open-data-products generate --config my-generation.config.yaml --prompts prompts/ --kind signal --json
```

The config check verifies required provider/model settings, catches common key
typos such as `base_url`, rejects secret-looking values, and confirms configured
input and prompt paths exist before generation runs.

To use another provider already defined in the config, override only the
provider:

```bash
open-data-products generate \
  --config my-generation.config.yaml \
  --prompts prompts/ \
  --provider groq \
  --kind signal \
  --json
```

CLI flags are for temporary overrides. Use them when testing a different model,
input, or output without editing the config:

```bash
open-data-products generate \
  --config my-generation.config.yaml \
  --prompts prompts/ \
  --provider openai \
  --model gpt-4.1-mini \
  --input source_docs/ \
  --kind signal \
  --output fragments/ \
  --json
```

Example config:

```yaml
provider: ollama
model: qwen2.5
input: open_data_products/generation/source_docs/
output: open_data_products/generation/fragments/
# Optional project-owned prompt template folder.
# prompts: prompts/

providers:
  ollama:
    type: ollama
    model: qwen2.5
    baseUrl: http://localhost:11434

  # Local OpenAI-compatible chat servers such as LM Studio, vLLM, llama.cpp
  # server, LocalAI, and text-generation-webui usually expose
  # /v1/chat/completions. Replace `model` with the model name loaded in that
  # server, such as Llama, DeepSeek, Qwen, Mistral, Mixtral, Phi, Gemma,
  # Code Llama, StarCoder, Yi, Command R, Falcon, Granite, Nemotron, Vicuna,
  # or WizardLM.
  lmstudio:
    type: openai-chat
    model: local-model
    baseUrl: http://localhost:1234/v1

  vllm:
    type: openai-chat
    model: local-model
    baseUrl: http://localhost:8000/v1

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
open-data-products generate --config my-generation.config.yaml --kind signal --json
```

The SDK never prints API key values in JSON output or error messages. If a
required secret env var is missing, generation fails before sending a request.
OpenAI HTTPS requests use the package `certifi` CA bundle, which avoids local
Python certificate-store issues without disabling TLS verification.

Provider entries with `type: openai` use the OpenAI Responses request shape,
Bearer token authentication, and `baseUrl + /responses`. That supports OpenAI
and providers that expose a compatible Responses API endpoint, such as
OpenRouter and Groq.

Provider entries with `type: openai-chat` use the Chat Completions request
shape, `baseUrl + /chat/completions`. Use this profile for local
OpenAI-compatible servers such as LM Studio, vLLM, llama.cpp server, and
LocalAI. They can also work with other local runtimes that expose compatible
chat completions endpoints, such as text-generation-webui. Model names are not
fixed by the SDK; set `model` to whatever the selected server exposes, or
override it for one run with `--model`. Common local model families include
Llama, DeepSeek, Qwen, Mistral, Mixtral, Phi, Gemma, Code Llama, StarCoder, Yi,
Command R, Falcon, Granite, Nemotron, Vicuna, and WizardLM.

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
  --config my-generation.config.yaml \
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
