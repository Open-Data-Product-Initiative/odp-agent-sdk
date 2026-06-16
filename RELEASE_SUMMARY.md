# Release Summary: 0.2.4

## NVIDIA NIM generation provider

The generation workflow now includes a bundled `nvidia-nim` provider preset for
locally running NVIDIA NIM LLM containers. The preset uses the existing
OpenAI-compatible chat client with:

- `type: openai-chat`
- `baseUrl: http://localhost:8000/v1`
- `model: local-model` as a placeholder that users override with the model ID
  returned by the NIM `/v1/models` endpoint

This keeps NVIDIA NIM support aligned with the SDK's local-runtime model:
Docker, NGC authentication, image pulls, and model downloads are handled outside
the SDK, while `open-data-products generate --provider nvidia-nim --model ...`
routes prompts to the local NIM container through
`/v1/chat/completions`.

The docs now include `docs/user/nvidia-nim.md`, a dedicated setup guide that
covers NGC login, running the container, startup tuning through
`NIM_MODEL_PROFILE`, NIM environment variables, backend CLI arguments, and
`NIM_PASSTHROUGH_ARGS`, health checks, model discovery, project config usage,
and the boundary between local/container NIM and hosted NVIDIA APIs.

## Hosted OpenAI-compatible provider presets

The generation workflow now also includes bundled `together`, `cerebras`,
`sambanova`, `mistral`, `gemini`, and `xai` provider presets for hosted
OpenAI-compatible Chat Completions APIs. The Together preset uses:

- `type: openai-chat`
- `baseUrl: https://api.together.ai/v1`
- `apiKeyEnv: TOGETHER_API_KEY`
- `model: meta-llama/Llama-3.3-70B-Instruct-Turbo`

The Cerebras preset uses:

- `type: openai-chat`
- `baseUrl: https://api.cerebras.ai/v1`
- `apiKeyEnv: CEREBRAS_API_KEY`
- `model: gpt-oss-120b`

The SambaNova preset uses:

- `type: openai-chat`
- `baseUrl: https://api.sambanova.ai/v1`
- `apiKeyEnv: SAMBANOVA_API_KEY`
- `model: Meta-Llama-3.3-70B-Instruct`

The Mistral preset uses:

- `type: openai-chat`
- `baseUrl: https://api.mistral.ai/v1`
- `apiKeyEnv: MISTRAL_API_KEY`
- `model: mistral-large-latest`

The Gemini preset uses:

- `type: openai-chat`
- `baseUrl: https://generativelanguage.googleapis.com/v1beta/openai`
- `apiKeyEnv: GEMINI_API_KEY`
- `model: gemini-3.5-flash`

The xAI preset uses:

- `type: openai-chat`
- `baseUrl: https://api.x.ai/v1`
- `apiKeyEnv: XAI_API_KEY`
- `model: grok-4.3`

This gives users hosted open-model options alongside OpenAI, OpenRouter, Groq,
and Claude without adding another SDK client or dependency. Users can override
the model with any chat model exposed by their selected provider account:

```bash
export TOGETHER_API_KEY="..."

open-data-products generate \
  --provider together \
  --model meta-llama/Llama-3.3-70B-Instruct-Turbo \
  --input source_docs/products/ \
  --kind product-reference \
  --output generated/

export CEREBRAS_API_KEY="..."

open-data-products generate \
  --provider cerebras \
  --model gpt-oss-120b \
  --input source_docs/products/ \
  --kind product-reference \
  --output generated/

export SAMBANOVA_API_KEY="..."

open-data-products generate \
  --provider sambanova \
  --model Meta-Llama-3.3-70B-Instruct \
  --input source_docs/products/ \
  --kind product-reference \
  --output generated/

export MISTRAL_API_KEY="..."

open-data-products generate \
  --provider mistral \
  --model mistral-large-latest \
  --input source_docs/products/ \
  --kind product-reference \
  --output generated/

export GEMINI_API_KEY="..."

open-data-products generate \
  --provider gemini \
  --model gemini-3.5-flash \
  --input source_docs/products/ \
  --kind product-reference \
  --output generated/

export XAI_API_KEY="..."

open-data-products generate \
  --provider xai \
  --model grok-4.3 \
  --input source_docs/products/ \
  --kind product-reference \
  --output generated/
```
