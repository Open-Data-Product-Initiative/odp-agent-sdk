# ODPR Recipe Quick Start

ODPR recipes are repeatable SDK workflows. A recipe can validate artifacts,
build catalogs or graphs, generate portfolio content, render outputs, and make
review requirements visible before anything writes files or calls an LLM.

Use quick starts when you want a clear project folder instead of editing SDK
internals. Starter templates are packaged with the SDK, but initialized recipe
workspaces belong in your own project.

## Start a Recipe Workspace

From a project directory:

```bash
open-data-products recipe list
open-data-products recipe init build-data-product-portfolio
cd recipes/build-data-product-portfolio
open-data-products recipe explain recipe.yaml
open-data-products recipe plan
```

`recipe init` creates `./recipes/build-data-product-portfolio/` by default.
The workspace contains:

```text
README.md
AGENTS.md
recipe.yaml
inputs/
outputs/
```

Put your source files under `inputs/`, inspect `recipe.yaml`, then run the
plan. Planning is always read-only: it does not write workflow outputs and does
not call providers.

## Execute After Review

LLM-backed steps need explicit LLM permission. Review-needed steps need explicit
review approval.

```bash
open-data-products recipe run --allow-llm --approve-review
```

For deterministic recipes that do not call a provider, review approval is
enough when the recipe policy requires it:

```bash
open-data-products recipe run --approve-review
```

Add `--dry-run` when you want to force planning mode:

```bash
open-data-products recipe run --dry-run --json
```

## Starter Recipes

Packaged starters are discovered from the bundled ODPR `RecipeCatalog`:

```bash
open-data-products recipe list --json
open-data-products recipe starter-catalog-check --json
```

The catalog lives in the package as `catalog.yaml`. It is metadata-only: it
lists ids, names, descriptions, groups, tags, commands, and paths to full
recipe files. Runtime inputs, outputs, approvals, and generated content belong
in the initialized workspace, not in the catalog.

## Parameterized Mode

Parameterized init is advanced and optional:

```bash
open-data-products recipe init build-data-product-portfolio --parameterized
```

This adds `recipe.values.yaml` and `values.schema.yaml` beside `recipe.yaml`.
Those files document reusable settings for teams, but the current runner still
executes `recipe.yaml`. Apply values deliberately before execution; do not use
values files for secrets or runtime results.

## More Detail

- [Agent usage](agent-usage.md)
- [RecipeCatalog](catalog.md)
- [Examples](examples.md)
- [Full recipe workflow guide](../user/recipe-workflows.md)
