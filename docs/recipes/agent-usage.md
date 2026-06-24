# ODPR Recipe Agent Usage

Agents should treat recipes as local workflow contracts. The safe path is to
discover, explain, plan, and only then execute with explicit approval flags.

## Agent Flow

```bash
open-data-products recipe list --json
open-data-products recipe init build-data-product-portfolio --json
cd recipes/build-data-product-portfolio
open-data-products recipe explain recipe.yaml --json
open-data-products recipe plan --json
open-data-products recipe run --allow-llm --approve-review --json
```

Use JSON output for machine decisions. The dry-run plan includes `dryRun`,
`plannedReads`, `plannedWrites`, `providers`, `requiredEnv`, `review`, `gates`,
`canRun`, and `blockingReasons`.

## Workspace Rules

Agents may edit project-owned files in initialized recipe workspaces:

```text
inputs/
recipe.yaml
recipe.values.yaml
```

Agents should not edit packaged SDK starter folders. `recipe init` copies
starters into `./recipes/<starter-folder>/` so work happens in a clear project
location.

Agents must not write runtime outputs back into ODPR files. Generated catalogs,
graphs, portfolio artifacts, manifests, and rendered HTML belong in configured
output folders such as `outputs/` or `.odp/runs/`.

## AGENTS.md

Every initialized starter includes an `AGENTS.md`. Treat it as the local
operating note for that workspace. It should explain editable files, the
required plan-before-run flow, approval rules, and where outputs belong.

## MCP Classification

Safe MCP recipe tools can discover, validate, explain, and plan. Starter
initialization is `state-changing` because it creates files on disk. Recipe
execution stays on the guarded CLI/Python runner surface and requires explicit
approval flags for review-needed or LLM-backed steps.

## Provider Safety

Provider readiness comes from recipe and generation configuration. Missing
environment variables should block execution. Review approval never implies
provider-call permission; LLM-backed steps still require `--allow-llm`.
