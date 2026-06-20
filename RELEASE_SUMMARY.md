# Release Summary: 0.2.5

- Added the hosted `zai` provider preset for the general Z.ai GLM
  OpenAI-compatible API, including config, manifest metadata, tests, a dedicated
  user guide, and complete provider-matrix coverage for bundled presets.
- Added ODPR recipe workflows as a first-class SDK surface:
  `open_data_products.odpr`, bundled ODPR schemas, Draft 2020-12 validation,
  secret checks, metadata-only `RecipeCatalog` generation, recipe guidance
  search, resource-registry discovery, Python helpers, MCP/ARWS dry-run
  discovery, and the `recipe list`, `recipe validate`, `recipe catalog`,
  `recipe search`, and `recipe run` CLI commands.
- Added guarded recipe execution with dry-run planning, explicit
  `--allow-llm` and `--approve-review` gates, provider readiness checks from
  generation config and environment variables, `executionPolicy` reporting,
  default recipe selection via `recipes.defaultRecipe`, config-root support via
  `projectRoot`, and compact run manifests under `.odp/runs/`.
- Added supported recipe execution for deterministic/report commands
  (`validate`, `explain`, `odpg.render`, `portfolio.sync`,
  `portfolio.render`, `portfolio.explain`) and LLM-backed commands
  (`generate`, `portfolio.build`, `portfolio.localize`,
  `portfolio.refresh`). Executed steps now include `writeCheck`, and
  localization runs include objective QA coverage counters.
- Added the recipe workflow user guide plus starter examples for CI validation,
  deterministic portfolio sync/render/explain, guarded portfolio build and
  refresh from source lanes, and guarded release localization. Dry-run plans now
  expose list-valued source lane inputs so agents can verify portfolio
  prerequisites before execution.
