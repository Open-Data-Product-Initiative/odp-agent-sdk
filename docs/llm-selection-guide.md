# LLM Selection Guide

This guide is an opinionated starting point for choosing models in SDK
workflows. The goal is not to rank every model. It is to help a developer pick
a good enough local or hosted model for the task in front of them.

The SDK should use deterministic commands whenever possible. Use an LLM when
the work involves interpretation, drafting, inference, localization, or release
review.

## Recommended Defaults

| Situation | Recommended provider | Why |
|-----------|----------------------|-----|
| Fast local development | `ollama-gemma3n` | Small, fast, and useful for first-pass structured generation. |
| Local GGUF inference without a server | `llamacpp-embedded` | Useful when a project wants direct llama.cpp access through `llama-cpp-python` instead of Ollama, LM Studio, vLLM, or a llama.cpp server. |
| Balanced local work on Apple Silicon with 32 GB memory | `lmstudio-gemma4-12b` | Stronger local model for drafting, graph inference, and portfolio review while still realistic on a developer laptop. |
| Structured YAML generation | `ollama-qwen3` or `ollama-qwen3-14b` | Practical local choice when schema shape and predictable output matter. |
| Small draft generation | `ollama-llama`, `ollama-mistral`, or `ollama-phi` | Easy local options for short drafts, summaries, and experiments. |
| Production-quality generation or release review | `claude` or `openai` | Better default when quality, consistency, and review confidence matter more than local-only execution. |
| CI validation, catalog building, sidecar creation, rendering, and summaries | No LLM | These are deterministic SDK tasks and should stay model-free. |

## SDK Task Matrix

| SDK purpose | Use an LLM? | Local default | Stronger local option | Hosted or production option | Notes |
|-------------|-------------|---------------|-----------------------|-----------------------------|-------|
| Validate ODPS, ODPC, ODPG, or ODPV YAML | No | None | None | None | Use `open-data-products validate`. |
| Explain or summarize existing artifacts | Usually no | None | None | None | Use `explain`, `summary`, `refs`, and resource commands before reaching for a model. |
| Generate ODPC fragments from source notes | Yes | `ollama-gemma3n` | `ollama-qwen3`, `lmstudio-gemma4-12b` | `claude`, `openai` | Good local-first workflow for drafting catalog content. |
| Generate ODPS product drafts | Yes | `ollama-qwen3` | `lmstudio-gemma4-12b`, `ollama-qwen3-14b` | `claude`, `openai` | Always validate generated YAML before using it downstream. |
| Generate ODPG graph YAML | Yes | `ollama-qwen3` | `lmstudio-gemma4-12b`, `ollama-qwen3-14b` | `claude`, `openai` | Graphs benefit from stronger reasoning once the source set grows. |
| Build ODPC catalogs from fragments | No | None | None | None | Use `odpc-build`; use an LLM only to draft missing fragments. |
| Build TOON or GCF sidecars | No | None | None | None | Use `--toon` and `--gcf`; sidecar creation is deterministic. |
| Infer ODPG graph edges during build | Yes | `ollama-qwen3` | `lmstudio-gemma4-12b`, `ollama-qwen3-14b` | `claude`, `openai` | Compact GCF context is useful when passing prior graph context. |
| Refresh portfolio workspaces | Sometimes | `ollama-qwen3` | `lmstudio-gemma4-12b` | `claude`, `openai` | Use local models for development and hosted models for release-quality refreshes. |
| Sync, render, or explain portfolio output | No | None | None | None | These should remain deterministic after source content exists. |
| Localize portfolio output | Yes | `lmstudio-gemma4-12b` | `ollama-qwen3-14b` | `claude`, `openai` | Hosted models are usually the better production default for multilingual polish. |
| Run ODPR workflow recipes | Depends | Recipe-selected provider | Recipe-selected provider | Recipe-selected provider | Recipe steps should decide whether each action is deterministic, local LLM, or hosted LLM. |
| CI/CD quality gates | Prefer no | None | None | `claude` or `openai` only when generation is required | Keep CI deterministic by default: validate, build, diff, and render before asking a model to generate. |
| Release review | Yes | `lmstudio-gemma4-12b` | `ollama-qwen3-14b` | `claude`, `openai` | Use hosted models when release risk is higher than provider cost. |

## Machine Tiers

Embedded llama.cpp support is optional. Install it with
`pip install "open-data-products[llama-cpp]"`, then configure a `llama-cpp`
provider with `modelPath`, `contextWindow`, and `gpuLayers`. Use
`openai-chat` instead when llama.cpp is running as a separate local server.

| Machine | Practical local choices | Avoid by default |
|---------|-------------------------|------------------|
| 8-16 GB memory | `ollama-gemma3n`, smaller Qwen, Phi, Mistral, Llama 8B class models | Long portfolio localization, large graph reasoning, 27B-32B models. |
| Apple Silicon with 32 GB memory | `lmstudio-gemma4-12b`, `ollama-qwen3-14b`, `ollama-qwen3`, `ollama-gemma3n` | Large 32B models for latency-sensitive workflows. |
| 64 GB or workstation class | Qwen/Llama 27B-32B Q4 models, larger local review models | Assuming local output is production-ready without validation and human review. |
| Hosted CI runner | Deterministic SDK commands, hosted provider only for generation steps | Pulling large local models during CI unless the runner is designed for it. |

## Development To Production Pattern

Use local models while developing recipes, prompts, and source material:

```bash
open-data-products generate \
  --config my-generation.config.yaml \
  --provider ollama-gemma3n \
  --input source_docs/signals/ \
  --kind signal \
  --output generated/ \
  --json
```

Move to a stronger local or hosted provider when the same workflow becomes
release-facing:

```bash
open-data-products generate \
  --config my-generation.config.yaml \
  --provider claude \
  --input source_docs/signals/ \
  --kind signal \
  --output generated/ \
  --json
```

This is also the intended shape for future ODPR recipes: the recipe should
describe the workflow, while the selected provider profile decides whether a
step runs locally, online, or with a mix of both.

## Operating Rules

- Validate generated YAML every time before publishing, building catalogs, or
  running portfolio workflows.
- Prefer GCF or TOON sidecars as prompt context when they exist; they reduce
  repeated YAML context without changing the canonical source artifact.
- Keep local providers as the default for prompt development, privacy-sensitive
  source documents, and fast iteration.
- Use hosted providers for release review, production localization, difficult
  graph reasoning, and workflows where consistency matters more than cost.
- Do not make CI depend on an LLM unless generation is the thing being tested.
  Validation, rendering, catalog building, graph building, and sidecar creation
  should be the default CI gates.
