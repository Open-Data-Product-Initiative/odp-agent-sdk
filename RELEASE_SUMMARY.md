# Release Summary

Added user-owned prompt template control for LLM generation.

## Highlights

- Users can now copy bundled generation prompts into their own project:

  ```bash
  open-data-products config generation --copy-prompts-to prompts/
  ```

- Copied prompt templates are editable Markdown files, so users can tune the
  instructions used for ODPS, ODPC, and ODPG artifact generation.
- Generation can now use a project-owned prompt folder:

  ```bash
  open-data-products generate \
    --config my-generation.config.yaml \
    --prompts prompts/ \
    --input source_docs/ \
    --output generated/ \
    --json
  ```

- Prompt folder selection is also available through the generation config with
  the `prompts` key.

## Public API Additions

- `copy_generation_prompts(destination)`
- `list_generation_prompts(prompt_dir=...)`
- `load_generation_prompt(name, prompt_dir=...)`
- `render_generation_prompt(prompt_name, source_dir, prompt_dir=...)`

## Docs Updated

- `README.md`
- `docs/API.md`
- `docs/generation.md`
- `llms.txt`
