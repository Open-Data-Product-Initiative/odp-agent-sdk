# ODPR Recipe Examples

These examples show the main recipe workflow shapes:

- `ci-validate-catalog.yaml`: deterministic validation that can execute.
- `portfolio-sync-render.yaml`: deterministic portfolio sync, render, and
  explain flow that writes only under `workspace/`.
- `odpg-build.yaml`: LLM-backed ODPG graph build from ODPC fragments with
  provider readiness, explicit LLM permission, and review approval.
- `portfolio-build.yaml`: LLM-backed portfolio build from source lane notes
  with provider readiness, explicit LLM permission, and review approval.
- `portfolio-refresh.yaml`: LLM-backed portfolio refresh from source lane notes
  with provider readiness, explicit LLM permission, and review approval.
- `release-portfolio-localize.yaml`: LLM-backed release localization that is
  guarded by provider readiness, explicit LLM permission, and review approval.

Run from the repository root:

```bash
open-data-products recipe validate examples/recipes/workflows/ci-validate-catalog.yaml --json
open-data-products recipe run examples/recipes/workflows/ci-validate-catalog.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --dry-run \
  --json
open-data-products recipe run examples/recipes/workflows/ci-validate-catalog.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --execute \
  --json
```

The example config sets `workflows/ci-validate-catalog.yaml` as
`recipes.defaultRecipe`, so the dry-run can also be started without a recipe
path:

```bash
open-data-products recipe run \
  --config examples/recipes/config/recipes.config.yaml \
  --dry-run \
  --json
```

For the LLM-backed release example, inspect the dry-run first:

```bash
open-data-products recipe run examples/recipes/workflows/release-portfolio-localize.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --dry-run \
  --json
```

For the LLM-backed graph and portfolio examples, inspect the dry-run first:

```bash
open-data-products recipe run examples/recipes/workflows/odpg-build.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --dry-run \
  --json
open-data-products recipe run examples/recipes/workflows/portfolio-build.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --dry-run \
  --json
open-data-products recipe run examples/recipes/workflows/portfolio-refresh.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --dry-run \
  --json
```

Execute any workflow only after reviewing the dry-run plan:

```bash
open-data-products recipe run examples/recipes/workflows/odpg-build.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --execute \
  --allow-llm \
  --approve-review \
  --json
open-data-products recipe run examples/recipes/workflows/portfolio-build.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --execute \
  --allow-llm \
  --approve-review \
  --json
open-data-products recipe run examples/recipes/workflows/portfolio-refresh.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --execute \
  --allow-llm \
  --approve-review \
  --json
```

The dry-run reports provider readiness from
`examples/recipes/config/generation.config.yaml`. If `ANTHROPIC_API_KEY` is not set,
the provider readiness is `missing-env`. Execute mode blocks LLM-backed steps
until the selected provider is ready and both guard flags are present.
