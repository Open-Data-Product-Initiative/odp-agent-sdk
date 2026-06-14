# Release Summary: 0.2.3

## Embedded llama.cpp Support

This release adds optional embedded llama.cpp generation support for users who
want local GGUF inference without running Ollama, LM Studio, vLLM, or a
separate llama.cpp server.

Users can now install the optional runtime support with:

```bash
pip install "open-data-products[llama-cpp]"
```

The new `llama-cpp` provider type loads a local GGUF model file directly through
`llama-cpp-python`:

```yaml
providers:
  llamacpp-embedded:
    type: llama-cpp
    model: local-gguf
    modelPath: models/qwen2.5-7b-instruct-q4_k_m.gguf
    contextWindow: 8192
    gpuLayers: -1
```

## What Changed

- Added the `open-data-products[llama-cpp]` optional extra.
- Added the `llama-cpp` generation provider type for in-process GGUF inference.
- Kept the base SDK install lightweight by importing `llama_cpp` lazily only
  when embedded llama.cpp generation is selected.
- Added config validation for `modelPath`, `contextWindow`, and `gpuLayers`.
- Added a bundled `llamacpp-embedded` provider example in the generation config.
- Documented the difference between embedded llama.cpp mode and
  OpenAI-compatible llama.cpp server mode.
- Added a practical venv-first setup guide in `docs/llama-cpp.md`.

## Why It Matters

Before this release, local generation depended on a local server runtime such
as Ollama, LM Studio, vLLM, or llama.cpp server. Those paths still work.

This release adds a direct Python path for teams that want to keep generation
inside the SDK process, point at a project-owned GGUF file, and avoid managing
another local LLM service.

## Verification Focus

Release verification should confirm:

- the package imports cleanly;
- the manifest renders as valid JSON;
- the full test suite passes;
- the built wheel and source distribution pass `twine check`;
- a fresh virtual environment can install the built wheel with
  `[llama-cpp]` and import both `open_data_products` and `llama_cpp`.
