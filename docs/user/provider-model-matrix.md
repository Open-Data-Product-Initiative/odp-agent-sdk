# Provider And Model Matrix

Provider catalogs change over time. The tables below show bundled provider
presets, bundled defaults, and practical example model IDs for the SDK's
generation config. Use `--model` to override the default model for one run, and
check the selected provider's current model catalog before relying on an ID in
production.

For full generation setup, prompts, source document layout, and output
behavior, see [LLM generation](generation.md).

For provider-specific setup guides, see [NVIDIA NIM generation](nvidia-nim.md),
[embedded llama.cpp](llama-cpp.md), and [Z.ai GLM generation](zai-glm.md).

## Hosted Provider Presets

These presets are available by provider name through `--provider <name>`.

| Provider preset | Type | Default model | Base URL | API key env |
|-----------------|------|---------------|----------|-------------|
| `openai` | `openai` | `gpt-4.1-mini` | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| `openrouter` | `openai` | `openai/gpt-4.1-mini` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| `groq` | `openai` | `openai/gpt-oss-120b` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `together` | `openai-chat` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | `https://api.together.ai/v1` | `TOGETHER_API_KEY` |
| `cerebras` | `openai-chat` | `gpt-oss-120b` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `sambanova` | `openai-chat` | `Meta-Llama-3.3-70B-Instruct` | `https://api.sambanova.ai/v1` | `SAMBANOVA_API_KEY` |
| `mistral` | `openai-chat` | `mistral-large-latest` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `gemini` | `openai-chat` | `gemini-3.5-flash` | `https://generativelanguage.googleapis.com/v1beta/openai` | `GEMINI_API_KEY` |
| `xai` | `openai-chat` | `grok-4.3` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `zai` | `openai-chat` | `glm-5.2` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `sakana-fugu` | `openai` | `fugu` | `https://api.sakana.ai/v1` | `SAKANA_API_KEY` |
| `claude` | `anthropic` | `claude-sonnet-4-5` | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` |
| `anthropic` | `anthropic` | `claude-sonnet-4-5` | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` |

## Hosted Model Lookup

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

| Model or family | Gemini `gemini` | xAI `xai` | Z.ai `zai` | Sakana Fugu `sakana-fugu` | Anthropic `claude` |
|-----------------|-----------------|-----------|-------------|-----------------------------|--------------------|
| Gemini Flash | `gemini-3.5-flash` | - | - | - | - |
| Grok | - | `grok-4.3` | - | - | - |
| GLM | - | - | `glm-5.2` | - | - |
| Fugu | - | - | - | `fugu` | - |
| Fugu Ultra | - | - | - | `fugu-ultra` | - |
| Claude Sonnet | - | - | - | - | `claude-sonnet-4-5` |
| Other provider models | use Gemini model ID | use xAI model ID | use GLM model ID | use Sakana model ID | use Anthropic model ID |

## Local Provider Presets

These presets are bundled in either the built-in provider map, the copied
generation config template, or both.

| Provider preset | Type | Default model | Base URL or model path |
|-----------------|------|---------------|------------------------|
| `ollama` | `ollama` | `qwen2.5` | `http://localhost:11434` |
| `ollama-gemma3n` | `ollama` | `gemma3n:e4b` | `http://localhost:11434` |
| `ollama-qwen25` | `ollama` | `qwen2.5:7b` | `http://localhost:11434` |
| `ollama-qwen25-14b` | `ollama` | `qwen2.5:14b` | `http://localhost:11434` |
| `ollama-qwen3` | `ollama` | `qwen3:8b` | `http://localhost:11434` |
| `ollama-qwen3-14b` | `ollama` | `qwen3:14b` | `http://localhost:11434` |
| `ollama-large-q4` | `ollama` | `qwen3:32b` | `http://localhost:11434` |
| `ollama-llama` | `ollama` | `llama3.1:8b` | `http://localhost:11434` |
| `ollama-mistral` | `ollama` | `mistral:7b` | `http://localhost:11434` |
| `ollama-phi` | `ollama` | `phi4-mini` | `http://localhost:11434` |
| `ollama-deepseek14b` | `ollama` | `deepseek-r1:14b` | `http://localhost:11434` |
| `lmstudio` | `openai-chat` | `local-model` | `http://localhost:1234/v1` |
| `lmstudio-gemma4-e4b` | `openai-chat` | `google/gemma-4-e4b` | `http://localhost:1234/v1` |
| `lmstudio-gemma4-12b` | `openai-chat` | `google/gemma-4-12b` | `http://localhost:1234/v1` |
| `vllm` | `openai-chat` | `local-model` | `http://localhost:8000/v1` |
| `nvidia-nim` | `openai-chat` | `local-model` | `http://localhost:8000/v1` |
| `llamacpp-embedded` | `llama-cpp` | `local-gguf` | `models/qwen2.5-7b-instruct-q4_k_m.gguf` |

## Local Model Lookup

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
