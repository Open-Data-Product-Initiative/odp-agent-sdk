# ODPR Simple V1 Runtime Boundary

This note records the simpler ODPR v1 decision: standardize authored recipes and
recipe discovery first. Do not turn dry-run plans, run manifests, provider
readiness checks, or inspection results into separate ODPR document kinds yet.

## Decision

ODPR v1 should define two recipe-facing document kinds:

- `Recipe` for one authored workflow contract.
- `RecipeCatalog` for discovering recipe files without loading or executing
  every recipe.

The primary authored recipe shape is:

```yaml
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-RELEASE-001
    name:
      en: Release Portfolio Review
  version: "1.0.0"
  type: release
  steps:
    - id: localize
      command: portfolio.localize
      with:
        workspace: generated/portfolio/
        languages:
          - fi
          - sv
```

The catalog shape should stay metadata-only:

```yaml
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: RecipeCatalog
recipeCatalog:
  metadata:
    id: RCP-CATALOG-001
    name:
      en: SDK Recipe Catalog
  recipes:
    - path: recipes/release-portfolio-review.yaml
      id: RCP-RELEASE-001
      version: "1.0.0"
      type: release
      name:
        en: Release Portfolio Review
      tags:
        - portfolio
        - release
```

Everything else is SDK runner output for now.

## Why Not More Kinds In V1

Separate runtime kinds such as `RecipeRunPlan`, `RecipeRunManifest`, or
`RecipeInspection` add schema surface before the basic recipe execution contract
has been proven. They also blur the boundary between a portable standard and one
SDK implementation's runtime telemetry.

The simpler v1 split is:

- ODPR owns the authored workflow recipe.
- ODPR owns recipe catalog metadata for discovery.
- The SDK owns validation, inspection, dry-run, execution, run manifests,
  provider readiness, logs, and recovery behavior.
- Agents consume SDK JSON response contracts, but those responses are not ODPR
  documents in v1.

The same `Recipe` file is used for validation, dry-run, execution, and resume.
Invocation mode is selected by the SDK command, not by mutating the recipe:

```bash
open-data-products recipe run recipes/release-portfolio-review.yaml --dry-run
open-data-products recipe run recipes/release-portfolio-review.yaml --execute
```

`recipe.execution.mode` means provider/runtime class such as `local`, `hosted`,
`hybrid`, or `none`. It does not mean `dry-run` or `execute`.

## SDK Agent Happy Path

The SDK should still expose stable JSON for agents. These responses are useful,
but they are SDK response structures, not ODPR document kinds.

The v1 agent path is:

```bash
open-data-products recipe list --config recipes.config.yaml --json
open-data-products recipe validate recipes/release-portfolio-review.yaml --json
open-data-products recipe run recipes/release-portfolio-review.yaml --dry-run --json
open-data-products recipe run recipes/release-portfolio-review.yaml --execute --json
```

### Recipe Catalog Response

```yaml
mode: list
kind: RecipeCatalog
recipeCatalog:
  recipes:
    - path: recipes/release-portfolio-review.yaml
      id: RCP-RELEASE-001
      version: "1.0.0"
      type: release
      name:
        en: Release Portfolio Review
      parseStatus: passed
      warnings: []
```

### Dry-Run Response

```yaml
mode: dry-run
recipe:
  path: recipes/release-portfolio-review.yaml
  id: RCP-RELEASE-001
  version: "1.0.0"
  type: release
canRun: false
blockingReasons: []
warnings: []
providers:
  - ref: claude
    model: claude-sonnet-4-5
    readiness: ready
    missingEnv: []
steps:
  - id: localize
    command: portfolio.localize
    classification: llm-backed
    resolved:
      action: portfolio.localize
      parameters:
        workspace: generated/portfolio/
        languages:
          - fi
          - sv
        providerRef: claude
        model: claude-sonnet-4-5
    inputs:
      - path: generated/portfolio/
        exists: true
    plannedWrites:
      - path: generated/portfolio/index.fi.html
        allowed: true
    review:
      status: review-needed
```

### Run Manifest

```yaml
mode: execute
runId: "20260619T120000Z-release-portfolio"
previousRunId: null
status: review-needed
exitCode: 2
startedAt: "2026-06-19T12:00:00Z"
completedAt: "2026-06-19T12:02:00Z"
recipe:
  path: recipes/release-portfolio-review.yaml
  id: RCP-RELEASE-001
  version: "1.0.0"
steps:
  - id: localize
    command: portfolio.localize
    status: passed
    artifacts:
      - path: generated/portfolio/index.fi.html
        kind: html
        hash: sha256:example
issues: []
```

## ODPR Fields To Include In V1

ODPR v1 should focus on fields needed to author portable recipes:

- recipe identity, version, type, names, and descriptions;
- recipe catalog metadata for discovery;
- inline steps with `id`, `command`, and `with`;
- recipe-level `execution.providerRef`;
- step-level `providerRef` and `model` for LLM-backed steps;
- `runPolicy` for timeout and basic failure policy;
- `inputs` and `outputs` declarations for human and agent inspection;
- report-only `gates` and `review` metadata;
- context preference such as `gcf`, `toon`, or `yaml`;
- v2 reservation for `uses`, rejected by v1 validators.

## SDK Response Fields To Stabilize

Even though these are not ODPR kinds, the SDK should keep them stable for
agents:

- `canRun`
- `blockingReasons`
- `warnings`
- `providers[].readiness`
- `providers[].missingEnv`
- `steps[].classification`
- `steps[].resolved.action`
- `steps[].resolved.parameters`
- `steps[].inputs`
- `steps[].plannedWrites`
- `steps[].review.status`
- `issues[].code`
- `issues[].blocking`
- `runId`
- `previousRunId`
- `status`
- `exitCode`

## Error Codes

The SDK should use stable machine-readable error codes:

- `schema_error`
- `unsupported_step`
- `unsupported_field`
- `missing_input`
- `missing_output`
- `missing_provider`
- `missing_model`
- `missing_env`
- `provider_unreachable`
- `optional_dependency_missing`
- `write_scope_violation`
- `review_needed`
- `validation_failed`
- `model_call_failed`
- `step_failed`
- `manifest_write_failed`

These can remain SDK codes in v1. If multiple implementations adopt them, ODPR
can standardize them later.

## Defer

Defer these until the recipe contract has real usage:

- `RecipeRunPlan` as an ODPR kind;
- `RecipeRunManifest` as an ODPR kind;
- `RecipeInspection` as an ODPR kind;
- recipe inspection as a separate command if list, validate, and dry-run are
  enough;
- reusable step template files;
- arbitrary recipe id registry lookup;
- persistent approval records;
- remote execution workers;
- scheduler semantics;
- generic conditional workflow language.
