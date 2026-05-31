# Release Summary: 0.1.7

Release 0.1.7 fixes selected-kind LLM generation for directory inputs.

## Highlights

- `open-data-products generate --kind product --input <source_docs/>` now
  processes each `.md` and `.txt` source document separately with the selected
  product prompt.
- Multiple product source documents can now produce multiple
  `product_reference_*.yaml` fragments in one command.
- Holistic generation with `--kind all` keeps its existing behavior: it passes
  the full source folder context through the product, use case, objective,
  signal, and graph generation tasks.
- The public Python API now exposes `generate_local_artifacts_for_kind()` for
  selected-kind multi-source generation.
- Bundled source document guidance now explains the distinction between
  holistic generation and selected-kind generation.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_generation_prompts.py tests/test_functional_cli.py -q`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_publish_workflow.py tests/test_namespace_layout.py -q`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m build`
