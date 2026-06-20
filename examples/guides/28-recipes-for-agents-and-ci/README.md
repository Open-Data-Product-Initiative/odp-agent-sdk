# Lecture 28: Recipes For Agents And CI

Recipes are useful for people, but they are especially important for AI agents
and CI jobs. They expose workflow intent before execution and write manifests
after execution.

## 1. Agent-Safe Order Of Operations

An AI agent should follow this order:

1. Validate the recipe.
2. Dry-run the recipe with JSON output.
3. Check `canRun`, `blockingReasons`, provider readiness, inputs, planned
   writes, and review status.
4. Execute only when policy allows it.
5. Read the manifest instead of guessing from output folders.

## 2. CI Pattern

Use deterministic recipes for CI:

```bash
open-data-products recipe validate \
  examples/recipes/workflows/ci-validate-catalog.yaml \
  --json

open-data-products recipe run \
  examples/recipes/workflows/ci-validate-catalog.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --execute \
  --json
```

CI should usually avoid hosted LLM calls unless the project explicitly permits
them.

## 3. Agent Pattern

Use dry-run JSON as the agent contract:

```bash
open-data-products recipe run \
  examples/recipes/workflows/portfolio-build.yaml \
  --config examples/recipes/config/recipes.config.yaml \
  --dry-run \
  --json
```

The agent should not infer hidden behavior from prose. It should use the
structured fields in the dry-run response.

## 4. What You Can Do Now

You can now use the SDK to:

- validate and explain standards files;
- configure local and hosted LLM providers;
- generate ODPS drafts and ODPC fragments;
- build ODPG graphs;
- build, refresh, sync, localize, render, and explain portfolio workspaces;
- define repeatable ODPR recipe workflows;
- inspect run manifests for audit evidence.

## 5. References

- [SDK README](../../../README.md)
- [SDK API reference](../../../docs/user/API.md)
- [SDK command guide](../../../docs/user/commands.md)
- [ODPR recipe workflows](../../../docs/user/recipe-workflows.md)
- [Generation guide](../../../docs/user/generation.md)
- [Portfolio development notes](../../../docs/development/portfolio.md)
- [ODPS product specification](https://opendataproducts.org/v4.1/)
- [ODPC catalog specification](https://opendataproducts.org/odpc-v1.0/)
- [ODPG graph specification](https://opendataproducts.org/odpg-v1.0/)
- [ODPV vocabulary specification](https://opendataproducts.org/odpv-v1.0/)
- [ODPR recipe specification](https://opendataproducts.org/odpr-v1.0/)

## What You Learned

- Recipes make SDK workflows repeatable.
- Dry-run JSON is the safe planning surface.
- Execution manifests are the audit surface.
- Human review remains required for draft LLM-generated artifacts.
