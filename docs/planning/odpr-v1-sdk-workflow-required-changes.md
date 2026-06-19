# ODPR V1 Workflow Recipe Change Brief For Codex

Use this file as the implementation brief when updating the ODPR v1
specification repository. It is written for a coding agent working in the ODPR
repo, not as end-user documentation.

Source SDK planning file:
`odps-python/docs/planning/sdk-workflow-profiles-plan.md`

Source ODPR page reviewed:
https://opendataproducts.org/odpr-v1.0/

## Objective

Update ODPR v1 so it can support SDK workflow recipes without turning ODPR into
an SDK runtime format.

The standard should define:

- authored workflow recipes;
- provider profiles referenced by recipes;
- recipe catalog metadata for discovery;
- portable step command names and their parameter shapes;
- enough constraints for AI agents to validate and inspect recipes before
  asking an SDK to run them.

The SDK should still own:

- invocation mode such as `list`, `validate`, `dry-run`, `execute`, or
  `resume`;
- dry-run JSON response shape;
- provider readiness checks;
- write-scope checks;
- resolved SDK commands or argv arrays;
- run manifests and logs;
- GUI behavior;
- approval records;
- remote workers and schedulers.

## Core Boundary Decision

ODPR v1 should include these root kinds:

- `Recipe`
- `Provider`
- `RecipeCatalog`

ODPR v1 should not include these root kinds yet:

- `RecipeRunPlan`
- `RecipeRunManifest`
- `RecipeInspection`

Reason: `Recipe`, `Provider`, and `RecipeCatalog` are portable documents.
Run plans, manifests, inspections, provider readiness, and write-scope results
are runtime outputs of an SDK or platform.

## Implementation Order

1. Locate the ODPR canonical schema source, generated JSON schema, examples,
   JSONL recipe index, docs page source, and validation/generation scripts.
2. Add or tighten schema support for `Recipe`, `Provider`, and
   `RecipeCatalog`.
3. Add command-specific step parameter schemas for the v1 command catalog.
4. Update examples so every documented pattern has a complete YAML file.
5. Regenerate derived artifacts such as JSON schema, recipe JSONL, and rendered
   docs if the ODPR repo uses generators.
6. Run the repo's validation and drift-check scripts.
7. Keep all SDK runtime response formats out of ODPR schema files.

## Schema Changes

### Root Kind Enum

Expand the root `kind` enum to:

- `Recipe`
- `Provider`
- `RecipeCatalog`

Do not add `RecipeRunPlan`, `RecipeRunManifest`, or `RecipeInspection` to the
v1 schema.

### Recipe Root

Recipe files should keep this shape:

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
  execution:
    mode: hosted
    providerRef: production-quality
  steps:
    - id: localize
      command: portfolio.localize
      providerRef: production-quality
      model: claude-sonnet-4-5
      with:
        workspace: generated/portfolio/
        languages:
          - fi
          - sv
```

Required fields:

- `schema`
- `version`
- `kind`
- `recipe`
- `recipe.metadata.id`
- `recipe.metadata.name`
- `recipe.version`
- `recipe.type`
- `recipe.steps`

Rules:

- `recipe.steps` must contain at least one step.
- `recipe.metadata.name` should allow language maps.
- `recipe.version` should use semantic-version-like text.
- Recommended `recipe.type` values are `dev`, `ci`, `release`,
  `localization`, `hybrid`, and `agent`.
- Extension recipe types may be allowed, but the canonical docs should define
  the recommended values above.

### RecipeCatalog Root

Add a `RecipeCatalog` root object for discovery.

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
      description:
        en: Refresh, localize, render, explain, and review a portfolio.
      tags:
        - portfolio
        - release
      environment: production
      executionMode: hosted
      providerRef: production-quality
      contextFormat: gcf
      requiresReview: true
      commands:
        - portfolio.refresh
        - portfolio.localize
        - portfolio.render
        - portfolio.explain
```

Required fields:

- `schema`
- `version`
- `kind`
- `recipeCatalog`
- `recipeCatalog.metadata.id`
- `recipeCatalog.metadata.name`
- `recipeCatalog.recipes`

Required `recipeCatalog.recipes[]` fields:

- `path`
- `id`
- `version`
- `type`
- `name`

Optional `recipeCatalog.recipes[]` fields:

- `description`
- `tags`
- `environment`
- `executionMode`
- `providerRef`
- `contextFormat`
- `requiresReview`
- `commands`

Rules:

- `RecipeCatalog` is metadata-only.
- It must not include full recipe step bodies.
- It must not include credentials, resolved provider settings, runtime status,
  planned writes, run ids, or logs.
- Entries should point to complete `Recipe` files.
- Entries should be treated as stale until the referenced recipe is loaded and
  validated.
- If the repo has `recipes.jsonl`, keep it as a derived retrieval artifact or
  align it with `RecipeCatalog`.

### Execution Policy

Define `recipe.execution` as workflow intent:

```yaml
execution:
  mode: hosted
  providerRef: production-quality
```

Fields:

- `mode`: optional string. Recommended values: `local`, `hosted`, `hybrid`,
  and `none`.
- `providerRef`: optional string. Refers to `Provider.provider.id`.

Rules:

- `execution.providerRef` is the default provider profile for LLM-backed steps.
- Step-level `providerRef` overrides `execution.providerRef`.
- Step-level `model` overrides the provider model for that step.
- Deterministic commands must not use `providerRef` or `model`.
- Recipes must not contain provider credentials.
- `execution.mode` means provider/runtime class. It must not mean `dry-run`,
  `execute`, `validate`, or `resume`.
- The same `Recipe` document is used for validation, dry-run, execution, and
  resume. SDK command flags select the invocation mode.

### Step Object

Each step should support:

- `id`: required string, unique within the recipe.
- `command`: required string.
- `with`: optional object, command-specific parameters.
- `providerRef`: optional string, only valid for LLM-backed commands.
- `model`: optional string, only valid for LLM-backed commands.
- `optional`: optional boolean.
- `timeoutSeconds`: optional positive integer.

Rules:

- `with` contains command parameters only.
- `providerRef` and `model` stay beside `command`, not inside `with`.
- V1 keeps steps fully inline.
- Reserve `uses` for future reusable step fragments, but reject it as a normal
  v1 field unless it is inside an `x-` extension.

## V1 Command Catalog

Add these portable step command names to the spec docs and schema where
practical. Do not document SDK CLI flags as the ODPR contract.

### `generate`

Classification: `llm-backed`

Required `with`:

- `input`
- `kind`
- `output`

Allowed `with.kind` values:

- `product-reference`
- `odps-product`
- `use-case`
- `objective`
- `signal`
- `graph`

Optional `with`:

- `config`
- `prompts`
- `profile`
- `includeComponents`
- `maxSourceChars`
- `ollamaUrl`

### `odpc.build`

Classification: `deterministic`

Required `with`:

- `input`
- `output`

Optional `with`:

- `html`
- `toon`
- `gcf`
- `id`
- `name`
- `description`
- `recursive`
- `validate`

### `odpg.build`

Classification: `llm-backed`

Required `with`:

- `input`
- `output`

Optional `with`:

- `toon`
- `gcf`
- `contextGraph`
- `id`
- `name`
- `description`
- `recursive`
- `validate`
- `config`
- `prompts`
- `ollamaUrl`

### `odpg.render`

Classification: `deterministic`

Required `with`:

- `graph`
- `output`

### `portfolio.build`

Classification: `llm-backed`

Required `with`:

- at least one of `objectives`, `useCases`, `signals`, or `products`;
- either `output` or `workspace`.

Optional `with`:

- `title`
- `config`
- `prompts`
- `ollamaUrl`
- `strictValidation`

### `portfolio.refresh`

Classification: `llm-backed`

Required `with`:

- `workspace`

Optional `with`:

- `objectives`
- `useCases`
- `signals`
- `products`
- `title`
- `config`
- `allSources`
- `prompts`
- `ollamaUrl`
- `strictValidation`

### `portfolio.sync`

Classification: `deterministic`

Required `with`:

- `workspace`

Optional `with`:

- `strictValidation`

### `portfolio.localize`

Classification: `llm-backed`

Required `with`:

- `workspace`
- `languages`

Optional `with`:

- `defaultLanguage`
- `config`
- `prompts`
- `ollamaUrl`
- `strictValidation`

Rules:

- `languages` should be a YAML list of BCP 47 language tags.
- Implementations may accept comma-separated strings, but examples should use a
  list.
- This command must not mutate canonical ODPS, ODPC, or ODPG YAML artifacts.

### `portfolio.render`

Classification: `deterministic`

Required `with`:

- `workspace`

Optional `with`:

- `output`
- `strictValidation`

### `portfolio.explain`

Classification: `report`

Required `with`:

- `workspace`

### `validate`

Classification: `deterministic`

Required `with`:

- `document`

Rules:

- V1 validates one explicit document per step.
- Do not add glob semantics in v1. A future command can be named
  `validate.each`.

### `explain`

Classification: `report`

Required `with`:

- `document`

## Command Classification Vocabulary

Document these classifications:

- `deterministic`: no provider needed, repeatable from files and options.
- `llm-backed`: calls a configured provider and model.
- `review`: requires human or external approval.
- `report`: reads artifacts and produces summaries, diagnostics, or manifests.

The classification can be documented in the command catalog. It does not need
to be repeated in every recipe step.

## Inputs And Outputs

Define recipe-level `inputs` and `outputs` as inspectable workflow
declarations.

```yaml
inputs:
  - id: portfolio-workspace
    path: generated/portfolio/
outputs:
  - id: localized-fi
    path: generated/portfolio/index.fi.html
    kind: html
```

Fields:

- `id`: required string.
- `path`: required string.
- `kind`: optional string such as `yaml`, `html`, `toon`, `gcf`, `json`, or
  `directory`.
- `description`: optional language map or string.

Rules:

- Paths should be project-relative.
- Recipes should not use absolute paths.
- Recipes should not use `..` traversal.
- ODPR states the safety expectation; SDKs enforce write-scope policy.

## Gates, Review, And Run Policy

Keep gates declarative. Do not define approval storage in v1.

```yaml
gates:
  - id: localized-pages-reviewed
    type: review
    required: true
review:
  required: true
  reviewer: release-owner
runPolicy:
  timeoutSeconds: 1800
  stopOnFailure: true
```

Gate fields:

- `id`: required string.
- `type`: required string. Recommended values: `validation`, `quality`,
  `review`, and `publication`.
- `required`: optional boolean, default `false`.
- `description`: optional language map or string.

Review fields:

- `required`: optional boolean.
- `reviewer`: optional string.
- `instructions`: optional language map or string.

Run policy fields:

- `timeoutSeconds`: optional positive integer.
- `stopOnFailure`: optional boolean, default `true`.
- `maxRetries`: optional non-negative integer.

Rules:

- Required gates must be visible to runners and agents.
- ODPR v1 should not define approval records, approval commands, signatures, or
  workflow pauses.
- SDKs may record gate status in run manifests as implementation output.

## Provider Profiles

Keep `Provider` small and stable:

```yaml
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Provider
provider:
  id: production-quality
  provider: openai
  model: gpt-4.1
  providerClass: hosted
  endpointRef: platform:openai
  credentialsRef: env:OPENAI_API_KEY
  temperature: 0.2
  settings:
    maxOutputTokens: 4000
```

Required fields:

- `provider.id`
- `provider.provider`

Optional fields:

- `model`
- `providerClass`
- `endpointRef`
- `credentialsRef`
- `temperature`
- `settings`
- `description`
- `environment`

Rules:

- `providerClass` recommended values are `local`, `hosted`, `hybrid`, and
  `none`.
- Provider documents must not contain raw secrets.
- `settings` must not contain secret-like keys or values.

## Reserved Future Fields

Reserve these names for future workflow features:

- `uses`
- `template`
- `from`
- `when`
- `foreach`
- `matrix`
- `approval`
- `schedule`
- `worker`

V1 validators should reject these as standard fields unless they appear inside
`x-` extensions.

## Examples To Add Or Update

Add complete YAML examples for:

- minimal local generation recipe;
- CI generate-and-validate recipe;
- release portfolio review recipe;
- portfolio localization recipe;
- hybrid graph review recipe;
- recipe catalog;
- local provider profile;
- hosted provider profile;
- internal gateway provider profile.

Example rules:

- Use `kind: Recipe` for workflow files.
- Use `kind: Provider` for provider files.
- Use `kind: RecipeCatalog` for catalog files.
- Use YAML lists for list values, especially `languages`.
- Do not use comma-separated strings in canonical examples.
- Do not include SDK dry-run responses or run manifests as ODPR examples.

## Agent And SDK Boundary Text To Add To Docs

Add prose equivalent to:

> A Recipe is the portable workflow contract. The same Recipe document can be
> validated, dry-run, executed, or resumed by an SDK or platform. ODPR does not
> store invocation mode in the Recipe body. Invocation mode belongs to the
> executing tool, for example an SDK command using `--dry-run` or `--execute`.
> `recipe.execution.mode` describes runtime/provider class such as local,
> hosted, hybrid, or none.

Add prose equivalent to:

> A RecipeCatalog is a metadata-only discovery document. It lists available
> recipes and points to their full Recipe files. It does not contain full steps,
> credentials, runtime status, planned writes, run ids, logs, or provider
> readiness results.

## Acceptance Criteria

The ODPR change is complete when:

- `Recipe`, `Provider`, and `RecipeCatalog` validate against the schema.
- `RecipeRunPlan`, `RecipeRunManifest`, and `RecipeInspection` are not accepted
  as v1 root kinds.
- A recipe with no steps fails validation.
- A recipe with step-level `providerRef` on a deterministic command fails
  validation if the schema can express that rule.
- `portfolio.localize.with.languages` is shown as a YAML list in examples.
- `RecipeCatalog` examples include metadata only and do not embed step bodies.
- Provider examples do not contain raw secrets.
- Generated JSON schema, rendered docs, JSONL recipe indexes, and examples are
  regenerated if the ODPR repo has generators for them.
- The repo's schema validation, example validation, and artifact drift checks
  pass.

## Suggested Codex Prompt For The ODPR Repo

Use this prompt when starting the ODPR implementation work:

```text
Update ODPR v1 using the change brief in
docs/planning/odpr-v1-sdk-workflow-required-changes.md from the odps-python
repo. Implement the schema/docs/examples changes for Recipe, Provider, and
RecipeCatalog. Keep runtime outputs such as RecipeRunPlan, RecipeRunManifest,
RecipeInspection, dry-run responses, run manifests, provider readiness, and
write-scope checks out of ODPR v1. After editing, regenerate derived artifacts
and run the ODPR repo validation/drift checks.
```
