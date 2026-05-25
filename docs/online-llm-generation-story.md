# Online LLM Generation Capability

The Open Data Products Python SDK now supports configurable LLM-backed
generation for ODPC fragments and ODPG graph YAML. Until now, the generation
workflow was centered on a local-first setup: source documents were processed
with Ollama and Qwen 2.5 running on the developer's machine. That local path
remains the default, but the SDK now has a provider configuration layer that
also enables online LLM backends.

The important shift is that generation is no longer hardwired to one model
runtime. Users can keep the default local Ollama setup, or they can choose an
external provider from a YAML config file. The config defines the provider name,
provider type, model, endpoint, input folder, output folder, and the environment
variable that contains the API key. Secrets are never stored in the config
itself.

Example:

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
```

The `type: openai` profile means the provider is called through an
OpenAI-compatible Responses API shape: Bearer token authentication, JSON request
body, and `baseUrl + /responses`. This makes the same SDK generation client
usable with OpenAI itself and compatible providers such as Groq and OpenRouter.
Providers with different authentication or request formats, such as Azure
OpenAI, Anthropic, Gemini, Mistral, Cohere, or Bedrock, are intentionally not
forced into this profile. They can be added later as dedicated provider clients.

The CLI now supports provider-driven generation:

```bash
open-data-products generate \
  --config generation.config.yaml \
  --provider openai \
  --model gpt-4.1-mini \
  --input source_docs/ \
  --output fragments/ \
  --json
```

A Groq smoke test can be run with:

```bash
export GROQ_API_KEY="..."
open-data-products generate \
  --config open_data_products/generation/generation.config.example.yaml \
  --provider groq \
  --input open_data_products/generation/source_docs/baggage-belt-congestion-signal.txt \
  --kind signal \
  --output /tmp/odp-groq-test \
  --json
```

This has been tested with OpenAI `gpt-4.1-mini` and Groq
`openai/gpt-oss-120b`, producing valid ODPC signal fragments from source
documents.

The generated output still follows the same standards-first design. The LLM
does not produce a loose summary or arbitrary text blob. It is guided by
editable prompt templates stored under
`open_data_products/generation/data/prompts/`. Those prompts instruct the model
to generate standards-ready YAML fragments, such as:

- ODPC `productReference` fragments
- ODPC `useCase` fragments
- ODPC `businessObjective` fragments
- ODPC `signal` fragments
- ODPG graph YAML connecting generated fragments

The output is then normalized and validated by the SDK. For example, if a model
wraps YAML in Markdown fences or adds a short reasoning preamble, the SDK now
defensively extracts the YAML document starting at the expected root such as
`signals:`. This improves reliability across different models, because some
online LLMs are more likely to explain their reasoning before producing the
requested artifact.

Security was an important part of the design. API keys are read only from
environment variables such as `OPENAI_API_KEY`, `GROQ_API_KEY`, or
`OPENROUTER_API_KEY`. The config stores only the environment variable name. The
SDK does not print API key values in JSON output or error messages. It also
validates that API key environment values contain only ASCII characters, which
catches copy-paste issues such as smart quotes before they reach the HTTP layer.

The OpenAI-compatible HTTPS client uses the `certifi` CA bundle for TLS
verification. This avoids local Python certificate-store problems without
disabling certificate validation.

The CLI error handling was also improved during testing. Instead of returning
vague failures such as "request failed" or only `HTTP 403`, the SDK now surfaces
short, non-secret provider error details where available. That makes it easier
to distinguish between missing credentials, blocked models, account
permissions, provider-side Cloudflare restrictions, and malformed output.

This addition keeps the SDK aligned with two important principles:

1. Local-first generation remains available by default with Ollama and Qwen 2.5.
2. Online LLM generation can be enabled through configuration without
   redesigning the workflow.

The same source document pipeline, prompt templates, output folders, fragment
validation, and graph generation flow work regardless of whether the model runs
locally or through an online provider. This means teams can prototype locally,
move to a managed LLM provider when needed, and later add organization-specific
providers without changing the high-level generation workflow.
