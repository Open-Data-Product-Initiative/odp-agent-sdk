# Portfolio Module Refactor Note

`open_data_products/portfolio.py` remains the public portfolio facade for build,
refresh, intake inspection, sync, localization, rendering, and explanation.
Portfolio document intake v1 is complete, and the first behavior-preserving
module split has been implemented.

## Current Split

- `portfolio.py`: public portfolio entry points, orchestration, artifact writes,
  state reconciliation, validation, localization, and HTML rendering.
- `portfolio_budget.py`: deterministic source chunking, prompt budget reports,
  word-count estimates, integer coercion, and prompt budget guard helpers.
- `portfolio_privacy.py`: source privacy application before prompt reduction,
  including the disabled-privacy warning payload.
- `source_documents/`: file type detection and format extraction.
- `portfolio_sources.py`: lane collection, source IDs, source hashes, extraction
  warnings, and source change calculations.

`portfolio.py` keeps compatibility aliases for the moved private helpers, such
as `_reduce_source_lanes_for_prompt`, so existing tests and internal imports
continue to resolve while the implementations live in the smaller modules.

## Implemented Guardrails

- Behavior was kept unchanged.
- Public imports from `open_data_products.portfolio` and `open_data_products`
  remain stable.
- Report fields were not renamed.
- Generated HTML, YAML, state files, and JSON reports were not intentionally
  changed.
- The ZIP-backed intake regressions and full portfolio workflow tests passed
  after the split.

## Remaining Candidates

- `portfolio_build.py`: build and refresh orchestration, if orchestration keeps
  growing.
- `portfolio_render.py`: HTML rendering helpers, if the rendering section remains
  difficult to navigate.
- `portfolio_state.py`: portfolio state, source change tracking adapters, and
  metadata artifact writes, if those responsibilities keep expanding.

Keep future extractions behavior-preserving and small enough that failures point
to movement mistakes rather than mixed behavior changes.

## Future Guardrails

- Move code without changing behavior first.
- Keep public imports stable from `open_data_products.portfolio` and
  `open_data_products.__init__`.
- Do not rename report fields during the refactor.
- Do not change generated HTML, YAML, state files, or JSON reports in the same
  patch unless a test forces it.
- Run full portfolio tests before and after each extraction step.

## Intake Coverage Baseline

The first split happened after document intake v1 covered:

- Word, PowerPoint, email, Outlook skip warnings, text PDF, CSV, and XLSX.
- Deterministic source reduction and prompt budget gates.
- Config-controlled privacy obfuscation.
- Warning-only handling for image inputs where OCR or vision extraction is not
  enabled.
