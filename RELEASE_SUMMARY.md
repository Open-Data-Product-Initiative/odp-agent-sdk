# Release Summary: 0.1.9

Release 0.1.9 adds an LLM-assisted ODPG graph builder for ODPC fragment
folders and tightens selected-kind generation guidance.

## Highlights

- `open-data-products odpg-build <fragments/> --output <graph.yaml>` now builds
  one ODPG graph from ODPC product reference, use case, objective, and signal
  fragments.
- The new graph builder converts ODPC fragments into ODPG nodes
  deterministically, then asks the configured LLM provider to infer only the
  graph edges.
- A dedicated `odpg_edges_from_odpc_fragments.md` prompt keeps edge inference
  separate from node creation, so generated edges must reference known node ids.
- The public Python API now exposes `build_graph()` and `write_graph()` for
  ODPG graph construction from ODPC fragments.
- New course guidance shows the full workflow: generate ODPC fragments, build an
  ODPC catalog, build an ODPG graph from the same fragments, and generate the
  graph explorer.
- Generation examples now prefer type-specific source folders such as
  `source_docs/products/`, `source_docs/use_cases/`,
  `source_docs/objectives/`, and `source_docs/signals/` so each explicit
  `--kind` prompt receives matching source material.
- README, command docs, `llms.txt`, and guide examples now consistently show
  `open-data-products generate` with the required concrete `--kind` value.

## Verification

- `pytest -q`
- `python3 -c "import open_data_products; print(open_data_products.__version__)"`
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
- `test ! -e docs/superpowers`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m build`
- `python3 -m twine check dist/*`
