# Lecture 23: Validate, List, And Dry-Run Recipes

The first habit with recipes is inspection before execution. Validation checks
the recipe shape. Listing shows what workflows are available. Dry-run explains
what would happen without writing artifacts.

## Before You Run This

Run from the repository root:

```bash
pwd
```

The examples use:

```text
examples/recipes/config/recipes.config.yaml
```

## 1. Validate A Recipe

Validate the catalog validation recipe:

```bash
open-data-products recipe validate \
  examples/recipes/workflows/ci-validate-catalog.yaml \
  --json
```

Validation confirms the file is an ODPR `Recipe`, checks it against the bundled
schema, and reports step classification.

## 2. List Available Recipes

List recipes discovered through the runner config:

```bash
open-data-products recipe list \
  --config examples/recipes/config/recipes.config.yaml \
  --json
```

The result is a metadata catalog. It does not execute any recipe.

## 3. Dry-Run A Recipe

Dry-run the graph build recipe:

```bash
open-data-products recipe run \
  examples/recipes/workflows/odpg-build.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --dry-run \
  --json
```

Look for these fields:

- `canRun`
- `blockingReasons`
- `providers`
- `steps[].inputs`
- `steps[].plannedWrites`
- `steps[].review`

## 4. Agent Reading Pattern

An AI agent should read dry-run JSON before execution:

```bash
open-data-products recipe run \
  examples/recipes/workflows/portfolio-build.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --dry-run \
  --json
```

The agent should verify that inputs exist, writes are allowed, provider
readiness is acceptable, and review requirements are understood.

## What You Learned

- `recipe validate` checks the recipe file.
- `recipe list` builds a recipe catalog from config.
- `recipe run --dry-run --json` is the safe planning surface.
- Dry-run JSON is the main contract for AI agents and CI.

## Next Lesson

Continue to [Lecture 24: Recipe Config And Execution Policy](../24-recipe-config-and-execution-policy/).
