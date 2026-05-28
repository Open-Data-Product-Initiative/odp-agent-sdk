# Release Summary

Updated local LLM flexibility and CLI help for generation workflows.

## Highlights

- Top-level `open-data-products --help` now shows current generation examples.
- Help examples now use project-owned config names, `generated/` output folders,
  provider/model overrides, and custom prompt folder usage.
- Removed stale `generation.config.yaml` examples from the top-level help text.
- Added `openai-chat` provider support for local OpenAI-compatible servers such
  as LM Studio, vLLM, llama.cpp server, and LocalAI.
- Local model names stay user-controlled strings; the SDK validates provider
  shape and paths without enforcing a fixed model catalog.
- Bundled generation config now includes editable local profiles for Ollama,
  LM Studio, and vLLM.

## Docs Updated

- CLI top-level help text
- `README.md`
- `docs/generation.md`
- `llms.txt`
