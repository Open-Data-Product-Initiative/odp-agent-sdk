# Release Summary: 0.2.5

- Added the hosted `zai` provider preset for the general Z.ai GLM
  OpenAI-compatible API, including config, manifest metadata, tests, a dedicated
  user guide, and complete provider-matrix coverage for bundled presets.
- Added the first ODPR recipe workflow surface with an `open_data_products.odpr`
  namespace, bundled ODPR schemas, Draft 2020-12 schema validation, embedded
  secret checks, metadata-only `RecipeCatalog` generation, recipe runner config,
  and agent-safe `recipe list`, `recipe validate`, `recipe catalog`, and
  `recipe run --dry-run` CLI planning commands. Deterministic/report recipe
  execution is now guarded behind `recipe run --execute`, with LLM-backed steps
  blocked explicitly, review-needed status visible in dry-run plans and run
  manifests, provider readiness resolved from generation config/env vars, and
  compact run manifests written under `.odp/runs/`.
  ODPR schemas, recipe guidance, and the recipe config template are also
  discoverable through the SDK resource registry, with `recipe search` for
  bundled ODPR guidance records. Added a dedicated ODPR recipe workflow user
  guide covering recipe files, `recipes.config.yaml`, `generation.config.yaml`,
  dry-run JSON, guarded execution, review policy, write policy, and manifests.
  Added starter recipe examples for CI validation, deterministic portfolio
  sync/render/explain, and LLM-backed release localization dry-runs.
  Recipe runner config now supports explicit `projectRoot`, allowing configs to
  live under `config/` while workflows and workspaces stay rooted at the
  project directory. `recipe validate`, `recipe run`, and the Python recipe
  helpers can now use `recipes.defaultRecipe` when the recipe path is omitted,
  while JSON responses expose `recipeSelection` so agents can distinguish
  command arguments from config defaults.
