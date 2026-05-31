# Release Summary: 0.1.6

Release 0.1.6 fixes config-free generation provider overrides for online and
local OpenAI-compatible providers.

## Highlights

- `open-data-products generate --provider claude` now works without passing
  `--config`; it resolves to the Anthropic Messages API client.
- Config-free provider overrides now also work for `openrouter`, `groq`,
  `lmstudio`, and `vllm`, matching the bundled generation config defaults.
- Built-in provider defaults include provider type, model, base URL, and API
  key environment variable where needed.
- Generation now reaches the expected missing-key or local-connection checks
  instead of failing with `Unsupported generation provider type`.
- Added CLI-level regression coverage proving Claude generation wiring writes a
  valid signal artifact while mocking only the network call.

## Verification

- `pytest -q`
- `python3 -c "import open_data_products"`
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
- `test ! -e docs/superpowers`
