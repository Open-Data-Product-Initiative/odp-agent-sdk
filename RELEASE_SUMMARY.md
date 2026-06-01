# Release Summary: 0.1.8

Release 0.1.8 fixes selected-kind LLM generation for directory inputs and makes
product generation explicit.

## Highlights

- `open-data-products generate --kind=product-reference --input <source_docs/>`
  now processes each `.md` and `.txt` source document separately with the ODPC
  product reference prompt.
- `open-data-products generate --kind=odps-product --input <source_docs/>`
  generates full ODPS OpenDataProduct YAML documents.
- Folder input now runs one selected-kind generation attempt per source file, so
  a folder of product source documents can produce matching
  `product_reference_*.yaml` fragments or `odps_product_*.yaml` specs in the
  output folder.
- `open-data-products generate` now requires an explicit concrete `--kind`
  value; the old full-set generation mode and ambiguous `--kind=product` value
  have been removed from the CLI.
- The public Python API now exposes `generate_local_artifacts_for_kind()` for
  selected-kind multi-source generation.
- Bundled source document guidance now focuses on selected-kind generation and
  no longer describes full-set folder generation.

## Verification

- `pytest -q`
- `python3 -c "import open_data_products"`
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
- `test ! -e docs/superpowers`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m build`
- `python3 -m twine check dist/*`
