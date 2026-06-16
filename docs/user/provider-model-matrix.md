# Provider And Model Matrix

Provider catalogs change over time. The tables below show bundled defaults and
practical example model IDs for the SDK's generation config. Use `--model` to
override the default model for one run, and check the selected provider's
current model catalog before relying on an ID in production.

For full generation setup, prompts, source document layout, and output
behavior, see [LLM generation](generation.md).

## Hosted Providers

Hosted provider columns use API-backed inference outside your machine.

| Model or family | OpenAI `openai` | OpenRouter `openrouter` | Groq `groq` | Together AI `together` |
|-----------------|-----------------|--------------------------|-------------|--------------------------|
| GPT 4.1 mini | `gpt-4.1-mini` | `openai/gpt-4.1-mini` | - | - |
| GPT OSS 120B | - | provider catalog | `openai/gpt-oss-120b` | provider catalog |
| Llama 3.3 70B | - | provider catalog | provider catalog | `meta-llama/Llama-3.3-70B-Instruct-Turbo` |
| DeepSeek | - | provider catalog | provider catalog | provider catalog |
| Other provider models | - | use provider model ID | use provider model ID | use provider model ID |

| Model or family | Cerebras `cerebras` | SambaNova `sambanova` | Mistral `mistral` |
|-----------------|----------------------|------------------------|--------------------|
| GPT OSS 120B | `gpt-oss-120b` | `gpt-oss-120b` | - |
| Llama 3.3 70B | provider catalog | `Meta-Llama-3.3-70B-Instruct` | - |
| DeepSeek | provider catalog | `DeepSeek-V3.1` | - |
| Mistral Large | - | - | `mistral-large-latest` |
| Other provider models | use provider model ID | use provider model ID | use provider model ID |

| Model or family | Gemini `gemini` | xAI `xai` | Anthropic `claude` |
|-----------------|-----------------|-----------|--------------------|
| Gemini Flash | `gemini-3.5-flash` | - | - |
| Grok | - | `grok-4.3` | - |
| Claude Sonnet | - | - | `claude-sonnet-4-5` |
| Other provider models | use Gemini model ID | use xAI model ID | use Anthropic model ID |

## Local Providers

Local provider columns use a runtime or model server you run.

| Model or family | Ollama presets | LM Studio presets | vLLM/local chat |
|-----------------|----------------|-------------------|-----------------|
| Qwen 2.5 | `qwen2.5`, `qwen2.5:7b`, `qwen2.5:14b` | load manually | serve manually |
| Qwen 3 | `qwen3:8b`, `qwen3:14b`, `qwen3:32b` | load manually | serve manually |
| Gemma | `gemma3n:e4b` | `google/gemma-4-e4b`, `google/gemma-4-12b` | serve manually |
| Llama | `llama3.1:8b` | load manually | serve manually |
| DeepSeek | `deepseek-r1:14b` | load manually | serve manually |
| Any local model | model installed in Ollama | model loaded in LM Studio | model served by chat API |

| Model or family | NVIDIA NIM | Embedded llama.cpp |
|-----------------|------------|--------------------|
| Qwen | NIM catalog if available | GGUF path |
| Gemma | NIM catalog if available | GGUF path |
| Llama | `meta/llama-3.1-8b-instruct` example | GGUF path |
| DeepSeek | NIM catalog if available | GGUF path |
| Any local model | model returned by `/v1/models` | local `.gguf` file |
