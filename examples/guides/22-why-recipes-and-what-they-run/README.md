# Lecture 22: Why Recipes Matter And What They Run

Recipes turn SDK command sequences into named, reviewable workflows. Instead of
copying commands between terminals, notebooks, CI jobs, and agent prompts, a
project can store the workflow as an ODPR recipe file and run it the same way
each time.

## Before You Run This

Install the SDK and run the commands from the repository root if you are using
the cloned examples:

```bash
pip install open-data-products
```

The starter recipe files live under:

```text
examples/recipes/
```

## 1. What A Recipe Adds

Direct SDK commands are still useful:

```bash
open-data-products validate examples/recipes/workspace/odpc/catalog.yaml
open-data-products portfolio explain examples/recipes/workspace/
```

A recipe adds the workflow layer around commands:

- workflow metadata and purpose;
- ordered steps;
- provider and model choices for LLM-backed steps;
- declared inputs and planned writes;
- review policy;
- dry-run output for humans, CI, and AI agents;
- execution manifests under `.odp/runs/`.

## 2. Starter Recipe Files

Inspect the starter workflows:

```bash
find examples/recipes/workflows -maxdepth 1 -type f -name "*.yaml" | sort
```

You should see examples for validation, graph build, portfolio build, portfolio
refresh, portfolio sync/render/explain, and localization.

## 3. Recipe Files Versus Config Files

Recipes describe what should run. Config files describe how the runner behaves.

```text
examples/recipes/workflows/*.yaml       # workflow definitions
examples/recipes/config/recipes.config.yaml
examples/recipes/config/generation.config.yaml
```

Keep that split clear:

- the recipe owns the workflow steps;
- `recipes.config.yaml` owns runner policy;
- `generation.config.yaml` owns LLM provider settings.

## 4. Why This Matters

Recipes make portfolio and standards workflows easier to repeat, review, and
automate. They also make the workflow easier for an AI agent to inspect before
execution because the dry-run result exposes inputs, planned writes, provider
readiness, and review status as JSON.

## What You Learned

- Recipes are workflow contracts around existing SDK commands.
- Recipes do not replace direct CLI commands.
- Runner config and generation config are separate from the recipe file.
- The next step is to validate, list, and dry-run recipes before executing
  anything.

## Next Lesson

Continue to [Lecture 23: Validate, List, And Dry-Run Recipes](../23-validate-list-and-dry-run-recipes/).
