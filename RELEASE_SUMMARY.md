# Release Summary: 0.3.1

## ODPR Recipe Workflows

- Added first-class ODPR recipe workflow support for repeatable SDK runs:
  `recipe list`, `recipe validate`, `recipe catalog`, `recipe search`,
  `recipe explain`, and guarded `recipe run` flows.
- Added dry-run planning for agents and CI, including resolved step
  parameters, planned writes, provider readiness, review status, gates,
  blocking reasons, and `recipeSelection` metadata when a config default is
  used.
- Added guarded execution with separate LLM and review approval gates, so
  LLM-backed steps require `--allow-llm` and review-needed steps require
  `--approve-review`.
- Added compact run manifests under the configured manifest directory so
  deterministic, blocked, and failed runs leave a machine-readable audit record
  for humans, CI, and agents.
- Added project-level `recipes.config.yaml` support for recipe search paths,
  default recipes, write policy, review policy, manifest location, and the
  pointer to `generation.config.yaml`.
- Added packaged starter recipe workspaces and init/list/explain flows so users
  can bootstrap local recipe projects instead of copying command sequences by
  hand.
- Added complete example workflows under `examples/recipes/`, including
  deterministic catalog validation, ODPC/ODPG build flows, portfolio build,
  portfolio refresh, portfolio sync/render, signal generation, and release
  localization.
- Added recipe docs covering quick start, agent usage, metadata-only
  `RecipeCatalog` discovery, examples, runner configuration, dry-run planning,
  guarded execution, provider readiness, and run manifests.

## Provider And Generation Updates

- Added the hosted `sakana-fugu` provider preset for Sakana Fugu's
  OpenAI-compatible Responses API, with default model `fugu` and documented
  `fugu-ultra` override examples.
- Tightened `--kind odps-product --profile minimal` so generated products keep
  only mandatory ODPS fields and strip hallucinated optional components unless
  they are requested through `complete-draft`.
- Tightened generation prompts to separate source-backed facts from defaults,
  skip unsupported optional ODPS component drafts, avoid invented signal
  timestamps, and constrain graph nodes to generated fragment context.
- Added compact contrast examples to the most drift-prone generation prompts so
  models see when to emit nulls, skip optional components, return empty signals,
  and avoid graph nodes without generated fragments.
- Added scoped rich examples for `--profile complete-draft` showing the default
  `SLA`, `dataQuality`, and `pricingPlans` component set without implying
  unrelated optional components.
- Added deterministic ODPS output pruning so unsupported root, product, and
  detail fields are removed before validation and writing.
