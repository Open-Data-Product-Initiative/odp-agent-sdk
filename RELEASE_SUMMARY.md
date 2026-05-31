# Release Summary: 0.1.4

Release 0.1.4 improves CLI output consistency and expands generation workflow
flexibility for local and OpenAI-compatible LLM providers.

## Highlights

- `open-data-products explain <document> --json` now returns structured ODPS
  JSON instead of embedding the line-oriented explanation as a JSON string.
- ODPS explain JSON includes product metadata, component count, compliance
  level, production-readiness status, and data access state.
- `open-data-products summary <document>` now prints a compact human-readable
  metadata report by default.
- `open-data-products summary <document> --json` preserves the previous
  machine-readable summary payload.
- `open-data-products --version` and `open-data-products -V` now report the
  installed SDK version.
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

- `RELEASE_SUMMARY.md`
- CLI top-level help text
- `README.md`
- `docs/generation.md`
- `llms.txt`

## Verification

- `pytest -q`
- `python3 -c "import open_data_products"`
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
- `test ! -e docs/superpowers`
