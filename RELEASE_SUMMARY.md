# Release Summary: 0.3.0

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
  (`generate`, `odpg.build`, `portfolio.build`, `portfolio.localize`,
  `portfolio.refresh`). Executed steps now include `writeCheck`, and
  localization runs include objective QA coverage counters.
- Added the recipe workflow user guide plus starter examples for CI validation,
  deterministic portfolio sync/render/explain, guarded ODPG graph builds,
  guarded portfolio build and refresh from source lanes, and guarded release
  localization. Dry-run plans now expose list-valued source lane inputs so
  agents can verify portfolio prerequisites before execution.
- Replaced the old course wrap-up guide with a seven-part ODPR recipe guide
  sequence covering recipe purpose, validation, dry-runs, config, execution
  policy, deterministic runs, LLM-backed runs, portfolio workflows, and
  agent/CI usage.

## Intentionally Left Out

- Recipes are not a full workflow scheduler: there is no background execution,
  retry engine, queue, cron support, or distributed state store.
- Recipes do not yet wrap every SDK CLI command. The first supported step set
  focuses on validation, explanation, generation, ODPG builds/renders, and
  portfolio workflows.
- Recipe steps remain inline in v1 examples. Reusable step fragments, shared
  step libraries, and fragment versioning are deferred.
- LLM-backed outputs are still drafts. The runner records review approval and
  write checks, but it does not replace human acceptance of generated YAML,
  graphs, localized pages, or portfolio content.
- CI examples intentionally favor deterministic recipes. Hosted LLM execution
  in CI remains an explicit project policy decision, not the default path.
