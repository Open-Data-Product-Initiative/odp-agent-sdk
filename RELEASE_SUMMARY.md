# Release Summary v0.1.2

Added user-owned LLM generation config management across API, CLI, MCP, and docs.

## Highlights

- Added `open-data-products config generation` for LLM config discovery and management.
- Users can copy the bundled config template into their own project:

  ```bash
  open-data-products config generation --copy-to my-generation.config.yaml
  open-data-products config generation --copy-to config/
  ```

- Folder targets create missing folders and write `generation.config.yaml` inside the target folder.
- Users can print the active YAML config:

  ```bash
  open-data-products config generation --config my-generation.config.yaml --print
  ```

- Users can validate config before generation:

  ```bash
  open-data-products config generation --config my-generation.config.yaml --check
  ```

- Config validation catches bad keys, unsupported provider types, invalid `maxTokens`, malformed field types, and secret-looking values.
- Generation docs now show real input/output workflows and explicit one-run provider/model overrides:

  ```bash
  open-data-products generate \
    --config my-generation.config.yaml \
    --provider groq \
    --model openai/gpt-oss-120b \
    --input source_docs/ \
    --output generated/ \
    --json
  ```

## Public API Additions

- `get_config()`
- `get_config_path()`
- `copy_config_template()`
- `print_config()`
- `validate_config()`

## Agent/MCP Additions

- `get_config`
- `validate_config`

## Docs Updated

- `README.md`
- `docs/API.md`
- `docs/generation.md`
- `llms.txt`

## CI/Release Workflow

- Fixed the PyPI publish workflow to upload the built `dist/*` artifact before publishing.
