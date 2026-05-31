# Release Summary: 0.1.7

Release 0.1.7 fixes selected-kind LLM generation for directory inputs.

## Highlights

- `open-data-products generate --kind=product --input <source_docs/>` now
  processes each `.md` and `.txt` source document separately with the selected
  product prompt.
- Folder input now runs one selected-kind generation attempt per source file, so
  a folder of product source documents produces matching
  `product_reference_*.yaml` fragments in the output folder.
- `open-data-products generate` now requires an explicit concrete `--kind`
  value; the old full-set generation mode has been removed from the CLI.
- The public Python API now exposes `generate_local_artifacts_for_kind()` for
  selected-kind multi-source generation.
- Bundled source document guidance now focuses on selected-kind generation and
  no longer describes full-set folder generation.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_generation_prompts.py tests/test_functional_cli.py -q`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_publish_workflow.py tests/test_namespace_layout.py -q`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m build`
