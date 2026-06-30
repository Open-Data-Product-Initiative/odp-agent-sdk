# Portfolio Module Refactor Note

`open_data_products/portfolio.py` has grown large enough that future portfolio
changes should avoid adding unrelated responsibilities to it. The refactor
should be handled as a separate cleanup task after portfolio document intake v1
is complete.

## Recommendation

Do not refactor `portfolio.py` in the middle of intake work. Finish the intake
formats first, then split the module by responsibility while keeping behavior
unchanged.

The reason is practical: intake changes should fail tests only because intake
behavior changed. If module movement and intake behavior are mixed, failures are
harder to diagnose and reviews become less clear.

## Proposed Split

- `portfolio_build.py`: build and refresh orchestration.
- `portfolio_budget.py`: source chunking, prompt budget reports, and prompt
  guard helpers.
- `portfolio_privacy.py`: source privacy application before reduction.
- `portfolio_render.py`: HTML rendering helpers if the current rendering section
  remains difficult to navigate.
- `portfolio_state.py`: portfolio state, source change tracking adapters, and
  metadata artifact writes if those responsibilities keep expanding.

Keep source loading and document extraction outside this split:

- `source_documents/`: file type detection and format extraction.
- `portfolio_sources.py`: lane collection, source IDs, source hashes, and source
  change calculations.

## Guardrails

- Move code without changing behavior first.
- Keep public imports stable from `open_data_products.portfolio` and
  `open_data_products.__init__`.
- Do not rename report fields during the refactor.
- Do not change generated HTML, YAML, state files, or JSON reports in the same
  patch unless a test forces it.
- Run full portfolio tests before and after each extraction step.

## Suggested Timing

Start this after document intake v1 covers:

- Word, PowerPoint, email, Outlook skip warnings, text PDF, CSV, and XLSX.
- Deterministic source reduction and prompt budget gates.
- Config-controlled privacy obfuscation.
- Warning-only handling for image inputs where OCR or vision extraction is not
  enabled.

At that point, `portfolio.py` can be refactored with lower risk because the
intake behavior will already be pinned by tests.
