# ODPR Recipe Quick Starts and Agent Enablement Plan

## 1. Purpose

ODPR Recipes give the SDK a flexible workflow layer, but users should not need to write YAML recipes from scratch as the first step. This creates friction for course learners, developers, platform teams, and AI agents.

This plan defines a phased SDK implementation for ODPR Recipe Quick Starts. The goal is to let humans and AI agents start from intent, discover available recipes through the ODPR `RecipeCatalog`, initialize a working recipe workspace, inspect the plan, run a dry-run, and execute only with approval.

This plan is intended for Codex execution against the Open Data Products SDK repository.

---

## 2. Important Correction: Use Existing ODPR RecipeCatalog

ODPR v1.0 already defines `RecipeCatalog`.

Do not invent `recipe-index.yaml`.

Do not create a new SDK-only metadata model.

Do not create a new ODPR catalog schema.

Use the existing ODPR `RecipeCatalog` as the SDK recipe discovery model.

ODPR defines three root objects:

- `Recipe`
- `Provider`
- `RecipeCatalog`

The `RecipeCatalog` is the metadata-only discovery document. It lists available recipes and points to complete `Recipe` files. It must not embed full recipe step bodies, credentials, provider readiness results, runtime status, planned writes, run IDs, or logs.

SDK implication:

- Starter recipe discovery should come from `catalog.yaml`.
- Starter-scoped list output, such as `open-data-products recipe list --starters --json`, should return data derived from `RecipeCatalog`.
- `open-data-products recipe init <id-or-name>` should resolve the selected recipe through the catalog.
- `open-data-products recipe explain <id-or-path>` should load the catalog entry first, then load the referenced full recipe when needed.
- Catalog entries must be treated as discovery metadata only. The referenced recipe file remains the executable workflow contract.

Recommended packaged starter structure:

```text
open_data_products/
  odpr/
    data/
      starters/
        catalog.yaml

        build-data-product-portfolio/
          recipe.yaml
          README.md
          AGENTS.md
          inputs/
          outputs/

        source-to-product-fragments/
          recipe.yaml
          README.md
          AGENTS.md
          inputs/
          outputs/

        fragments-to-odpc-catalog/
          recipe.yaml
          README.md
          AGENTS.md
          inputs/
          outputs/

        fragments-to-odpg-graph/
          recipe.yaml
          README.md
          AGENTS.md
          inputs/
          outputs/

        generate-agent-context/
          recipe.yaml
          README.md
          AGENTS.md
          inputs/
          outputs/
```

The exact Python package path may differ. Codex must inspect the repository structure before adding files.

---

## 2.1 Resolved Implementation Decisions

The repository now already includes first-class ODPR support. The following
decisions are settled for this quick-start implementation:

1. The authoritative ODPR v1.0 schema sources are:
   - `https://opendataproducts.org/odpr-v1.0/schema/odpr.json`
   - `https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml`
2. The SDK already vendors the ODPR schema locally under `open_data_products/odpr/data/schema/`. Quick-start work should reuse that existing package structure instead of introducing a parallel schema location.
3. The SDK already has ODPR recipe validation, listing through `recipes.config.yaml`, grouped catalog generation, dry-run planning, guarded execution, and safe MCP recipe tools. Quick-start work should extend those surfaces rather than replace them.
4. The quick-start implementation should start with starter discovery, workspace initialization, and explanation. It should not redesign existing `recipe run --dry-run` or `recipe run --execute` behavior.
5. Starter `recipe.yaml` files should be authored as executable ODPR `Recipe` contracts compatible with the existing recipe runner.
6. Recipe quick-start support should be available through both the CLI and MCP/agent surface. Discovery and explanation MCP tools are `safe`. Workspace initialization creates files and must be classified as `state-changing`. Existing MCP dry-run planning remains `safe`; execution tools, if added to MCP later, must be classified as `state-changing` or stricter according to the ARWS tool taxonomy.

## 2.2 Completed Foundation: RecipeCatalog Grouping Support

The SDK foundation for grouped ODPR `RecipeCatalog` support is already in
place. Future quick-start phases should build on it instead of adding a
parallel grouping model.

Completed SDK support:

- vendored ODPR schemas under `open_data_products/odpr/data/schema/` include
  `recipeCatalog.version`, `recipeCatalog.groups[]`,
  `RecipeCatalogGroup`, and `recipeCatalog.recipes[].groupRef`
- `RecipeCatalog` validation requires `recipeCatalog.version`
- catalog validation rejects duplicate group ids
- catalog validation rejects duplicate recipe ids
- catalog validation rejects `groupRef` values that do not match a declared
  group
- `build_recipe_catalog()` and `write_recipe_catalog()` emit
  `recipeCatalog.version`
- `list_recipes()`, `build_recipe_catalog()`, and `write_recipe_catalog()`
  can assign emitted recipe entries to a group
- `open-data-products recipe list --group <id>` returns grouped
  `RecipeCatalog`-style JSON for configured project recipes
- `open-data-products recipe catalog --group <id>` writes grouped
  metadata-only catalogs for configured project recipes
- MCP `list_recipes` accepts an optional `group` argument
- recipe and catalog paths are emitted with portable forward slashes in
  SDK-facing recipe outputs

This foundation supports starter discovery, but it is not the starter discovery
feature itself. The next phases still need packaged starter resources,
starter-scoped list commands, catalog checks, init, and explain.

First-release user path:

```bash
open-data-products recipe list --starters
open-data-products recipe init build-data-product-portfolio
open-data-products recipe explain build-data-product-portfolio
```

First-release agent path:

```bash
open-data-products recipe list --starters --json
open-data-products recipe init build-data-product-portfolio --output build-data-product-portfolio --json
open-data-products recipe explain build-data-product-portfolio --json
```

Dry-run planning and guarded execution already exist as `recipe run --dry-run` and `recipe run --execute`. Quick starts should route initialized recipes into those existing lifecycle commands.

---

## 3. Findings from Common Automation Practices

### 3.1 Starter templates reduce blank-file friction

GitHub Actions, Cookiecutter-style project scaffolding, and other developer tools reduce first-use friction by starting users from working templates instead of empty files.

Implication for ODPR:

The SDK should provide built-in starter recipes that users initialize with one command.

```bash
open-data-products recipe init build-data-product-portfolio
```

### 3.2 Discovery metadata should be separate from executable workflow content

Automation systems usually separate discovery or registry metadata from executable workflow files. Users and tools first search, filter, and select a workflow. They load the executable file only after selecting it.

Implication for ODPR:

The SDK should use ODPR `RecipeCatalog` for discovery and full ODPR `Recipe` files for execution.

### 3.3 Examples and starters should stay separate

Templates are clean starting points. Examples show realistic usage with sample inputs, outputs, and variants.

Implication for ODPR:

The SDK should include both:

- starter recipes used by `recipe init`
- complete example workspaces under `examples/recipes/`

### 3.4 Values separation is useful, but not the default

Values files help reusable templates and team-approved workflows. They also add a concept.

Implication for ODPR:

Use one self-contained `recipe.yaml` by default. Support `recipe.values.yaml` later as advanced mode only.

Default:

```text
recipe.yaml
```

Advanced:

```text
recipe.yaml
recipe.values.yaml
values.schema.yaml
```

### 3.5 Agent instructions should follow known conventions

Use `AGENTS.md` for agent guidance. Do not invent `.agent-guide.md`.

Implication for ODPR:

Generated recipe workspaces should include:

```text
README.md
AGENTS.md
recipe.yaml
```

### 3.6 Plan and dry-run must be part of the core path

Users and agents need visibility before execution.

Implication for ODPR:

Quick starts should make inspection part of the default target flow. The existing SDK already exposes dry-run planning through `recipe run --dry-run` and guarded execution through `recipe run --execute`. Quick-start work should add catalog-backed starter discovery, workspace initialization, and starter explanation around those existing commands.

```bash
open-data-products recipe run recipe.yaml --dry-run
open-data-products recipe run recipe.yaml --execute --approve-review
```

For agents:

```bash
open-data-products recipe run recipe.yaml --dry-run --json
open-data-products recipe run recipe.yaml --execute --approve-review --json
```

---

## 4. Business Reasoning

### 4.1 Reduce adoption friction

ODPR Recipes become easier to adopt when users start from a known intent and receive a working folder.

Business value:

- faster SDK onboarding
- easier course exercises
- fewer support questions
- clearer demos
- faster path from interest to first result

### 4.2 Make ODPR easier to explain

The message becomes:

> Choose an intent. Initialize the recipe. Review the plan. Dry-run. Execute with approval.

This is easier than:

> Learn the ODPR schema and write a workflow YAML from scratch.

Business value:

- clearer positioning for ODPR
- stronger blog and course narrative
- easier adoption by ODPS community contributors

### 4.3 Turn the SDK into a workflow layer

The SDK already has commands for ODPS, ODPC, ODPG, generation, fragments, sidecars, and agent context. Recipes connect those commands into repeatable workflows.

Business value:

- the SDK becomes more than a collection of CLI commands
- recipes encode repeatable data product operating patterns
- platform teams can move toward approved workflow libraries

### 4.4 Enable AI agents safely

AI agents should not guess recipe fields or run workflows blindly. They need a catalog, explanation, plan, dry-run, and explicit approval gates.

Business value:

- safer agent execution
- better support for Codex, IDE agents, and local assistants
- stronger AI-agent-first story
- clear split between discovery metadata, agent instructions, and executable recipes

### 4.5 Align SDK behavior with ODPR

Using `RecipeCatalog` avoids SDK-specific discovery formats.

Business value:

- cleaner standards alignment
- easier future interoperability
- less custom documentation
- one discovery model for SDK, platforms, tools, and agents

---

## 5. Design Principles

1. Start from intent, not YAML.
2. Use ODPR `RecipeCatalog` for discovery.
3. Use full ODPR `Recipe` files for execution.
4. One self-contained `recipe.yaml` is the default.
5. `recipe.values.yaml` is advanced, not required.
6. `README.md` is for humans.
7. `AGENTS.md` is for AI agents.
8. Every starter recipe should be runnable after initialization when inputs and providers are available.
9. Every execution path should support plan, dry-run, and explicit approval.
10. Every agent-facing command should support `--json`.
11. Starter templates and examples must stay separate.
12. Do not duplicate recipe step bodies in the catalog.
13. Do not store secrets in recipes, providers, or catalogs.
14. Do not put runtime results, planned writes, logs, or run IDs in ODPR files.
15. Treat catalog entries as potentially stale until the referenced recipe file is loaded and validated.

---

## 6. Target User Journeys

### 6.1 Human beginner

```bash
open-data-products recipe list --starters
open-data-products recipe init build-data-product-portfolio
cd build-data-product-portfolio
open-data-products recipe run recipe.yaml --dry-run
open-data-products recipe run recipe.yaml --execute --approve-review
```

Expected result:

The user creates and runs a working recipe workspace without writing YAML from scratch.

### 6.2 Developer

```bash
open-data-products recipe init source-to-product-fragments --output my-fragment-workflow
cd my-fragment-workflow
open-data-products recipe run recipe.yaml --dry-run
open-data-products recipe run recipe.yaml --execute --approve-review
```

Expected result:

A developer receives a clean recipe workspace and adapts `recipe.yaml` as needed.

### 6.3 AI agent

```bash
open-data-products recipe list --starters --json
open-data-products recipe explain build-data-product-portfolio --json
open-data-products recipe init build-data-product-portfolio --output build-data-product-portfolio --json
open-data-products recipe run build-data-product-portfolio/recipe.yaml --dry-run --json
open-data-products recipe run build-data-product-portfolio/recipe.yaml --execute --approve-review --json
```

Expected result:

An agent discovers recipes through `RecipeCatalog`, understands safe usage, validates planned behavior, and executes only after explicit approval.

### 6.4 Advanced reusable template use

```bash
open-data-products recipe init build-data-product-portfolio --parameterized --output portfolio-template
```

Expected structure:

```text
portfolio-template/
  README.md
  AGENTS.md
  recipe.yaml
  recipe.values.yaml
  values.schema.yaml
  inputs/
  outputs/
```

Expected result:

Teams can separate approved workflow structure from project-specific values when reuse justifies the complexity.

---

## 7. ODPR RecipeCatalog Requirements for SDK Starters

The SDK starter recipe library must include a valid ODPR `RecipeCatalog`.

Recommended file:

```text
catalog.yaml
```

Recommended root shape:

```yaml
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: RecipeCatalog
recipeCatalog:
  metadata:
    id: RCP-CATALOG-SDK-STARTERS
    name:
      en: Open Data Products SDK Starter Recipes
    description:
      en: Built-in ODPR starter recipes for Open Data Products SDK workflows.
  recipes:
    - path: build-data-product-portfolio/recipe.yaml
      id: RCP-SDK-PORTFOLIO-001
      version: "1.0.0"
      type: agent
      name:
        en: Build Data Product Portfolio
      description:
        en: Create a portfolio workflow from source materials, fragments, catalog, graph, and agent context.
      tags:
        - portfolio
        - odpc
        - odpg
        - agent-context
      environment: development
      executionMode: hybrid
      providerRef: local-fast
      contextFormat: auto
      requiresReview: true
      commands:
        - portfolio.build
        - odpc.build
        - odpg.build
```

Notes for Codex:

- Match exact ODPR schema field names.
- Do not use custom fields unless namespaced with `x-`.
- Prefer ODPR-native fields over SDK-specific metadata.
- If the SDK needs extra metadata, add it with `x-sdk-*` fields only after confirming schema allows extensions.
- Keep catalog entries metadata-only.
- Keep full step definitions only in the referenced `recipe.yaml`.

---

## 8. Proposed Commands

### 8.1 Starter Discovery

Purpose:

List starter recipes from the packaged ODPR `RecipeCatalog` without changing the existing meaning of `recipe list` for configured project recipes.

Examples:

```bash
open-data-products recipe list --starters
open-data-products recipe list --starters --json
open-data-products recipe list --starters --catalog path/to/catalog.yaml
```

Alternative acceptable shape:

```bash
open-data-products recipe starters
open-data-products recipe starters --json
```

Default behavior:

- Existing `recipe list` behavior for configured project recipes must remain intact.
- Starter discovery should load packaged starter `catalog.yaml`.
- Validate it as `kind: RecipeCatalog`.
- Show catalog entries.
- Do not load every full recipe unless needed for validation or `--all-details`.
- Hide deprecated entries only if the catalog or future spec extension supports status. ODPR v1.0 does not define `status` in catalog entries.

Human output should include:

- id
- English name
- short description
- type
- environment
- execution mode
- context format
- review requirement
- command names

JSON output should be derived from the catalog:

```json
{
  "ok": true,
  "command": "recipe list",
  "catalog": {
    "id": "RCP-CATALOG-SDK-STARTERS",
    "name": "Open Data Products SDK Starter Recipes",
    "path": "catalog.yaml"
  },
  "recipes": [
    {
      "path": "build-data-product-portfolio/recipe.yaml",
      "id": "RCP-SDK-PORTFOLIO-001",
      "version": "1.0.0",
      "type": "agent",
      "name": {
        "en": "Build Data Product Portfolio"
      },
      "description": {
        "en": "Create a portfolio workflow from source materials, fragments, catalog, graph, and agent context."
      },
      "tags": ["portfolio", "odpc", "odpg", "agent-context"],
      "environment": "development",
      "executionMode": "hybrid",
      "providerRef": "local-fast",
      "contextFormat": "auto",
      "requiresReview": true,
      "commands": ["portfolio.build", "odpc.build", "odpg.build"]
    }
  ]
}
```

### 8.2 `recipe init <id-or-name>`

Purpose:

Create a working recipe workspace from a catalog entry.

Examples:

```bash
open-data-products recipe init build-data-product-portfolio
open-data-products recipe init RCP-SDK-PORTFOLIO-001
open-data-products recipe init build-data-product-portfolio --output my-workflow
open-data-products recipe init build-data-product-portfolio --parameterized
```

Resolution order:

1. Exact catalog recipe `id`
2. Exact normalized English recipe name
3. Exact folder name derived from catalog `path`
4. Optional future aliases if ODPR or SDK extension supports them

Default generated structure:

```text
build-data-product-portfolio/
  README.md
  AGENTS.md
  recipe.yaml
  inputs/
  outputs/
```

Behavior:

- Resolve selected starter through `catalog.yaml`.
- Copy the template folder that contains the referenced `recipe.yaml`.
- Fail if output directory exists, unless `--force` is provided.
- Never overwrite files by default.
- Create `inputs/` and `outputs/` when not present.
- Print next-step commands after successful initialization.
- Support `--json`.

Suggested options:

```text
--output PATH
--force
--parameterized
--minimal
--with-samples
--catalog PATH
--json
```

### 8.3 `recipe explain <id-or-path>`

Purpose:

Explain a starter recipe or local recipe file.

Examples:

```bash
open-data-products recipe explain build-data-product-portfolio
open-data-products recipe explain RCP-SDK-PORTFOLIO-001
open-data-products recipe explain recipe.yaml
open-data-products recipe explain build-data-product-portfolio --json
```

Behavior:

- If input matches a local file, load and validate it as `kind: Recipe`.
- If input is not a file, resolve it through `RecipeCatalog`.
- Load the referenced full `Recipe` file.
- Combine catalog discovery metadata with recipe execution details.
- Do not execute steps.
- Do not call providers.

Human output should include:

- purpose
- recipe id
- recipe version
- type
- environment
- execution mode
- provider reference
- context format
- commands
- inputs
- outputs
- gates
- review requirement
- safety notes
- next commands

JSON output should include catalog and recipe sections.

### 8.4 `recipe starter-catalog-check`

Purpose:

Validate the packaged or provided starter `RecipeCatalog` and its referenced recipe files. Use a dedicated name so this does not conflict with existing `recipe catalog`, which builds a metadata-only catalog from configured recipes.

Examples:

```bash
open-data-products recipe starter-catalog-check
open-data-products recipe starter-catalog-check --catalog path/to/catalog.yaml
open-data-products recipe starter-catalog-check --json
```

Checks:

- catalog exists
- catalog validates against ODPR schema
- root kind equals `RecipeCatalog`
- every `recipes[].path` is relative
- no path uses absolute paths
- no path uses `..` traversal
- every referenced recipe file exists
- every referenced recipe file validates as `kind: Recipe`
- catalog `id`, `version`, `type`, `name`, and `description` match or are consistent with the referenced recipe
- catalog does not contain forbidden runtime fields
- no duplicate catalog recipe ids
- no duplicate paths
- packaged starter folders contain `README.md` and `AGENTS.md`
- package build includes catalog and starter resources

### 8.5 Existing `recipe run <recipe.yaml> --dry-run`

Purpose:

Show the intended execution plan without executing workflow steps. This already exists in the SDK as `recipe run --dry-run`; quick-start work should reuse and improve that path rather than create a separate planning implementation.

Examples:

```bash
open-data-products recipe run recipe.yaml --dry-run
open-data-products recipe run recipe.yaml --dry-run --json
```

Plan output should include:

- resolved recipe id
- recipe version
- type
- environment
- execution mode
- provider reference
- context format
- steps in order
- command behind each step
- files and folders read
- files and folders written
- external providers needed
- required environment variables if known
- approval or review gates
- warnings

This command must not call LLMs, write outputs, or modify files.

Optional compatibility alias:

```bash
open-data-products recipe plan recipe.yaml --json
```

Only add this alias if it delegates to the existing `recipe run --dry-run` implementation.

### 8.6 Dry-Run Hardening

Purpose:

Validate runtime readiness and show what would happen through the existing dry-run planning path.

Examples:

```bash
open-data-products recipe run recipe.yaml --dry-run
open-data-products recipe run recipe.yaml --dry-run --json
```

Dry-run output should include:

- recipe schema validation result
- input existence checks
- output path checks
- missing environment variables
- provider readiness checks where possible without generation calls
- planned writes
- blocked operations
- next recommended command

This command must not write final outputs.

Optional compatibility alias:

```bash
open-data-products recipe dry-run recipe.yaml --json
```

Only add this alias if it delegates to the existing `recipe run --dry-run` implementation.

### 8.7 Existing `recipe run <recipe.yaml> --execute`

Purpose:

Execute a recipe.

Examples:

```bash
open-data-products recipe run recipe.yaml --execute
open-data-products recipe run recipe.yaml --execute --approve-review --json
```

Behavior:

- Use existing guarded execution behavior.
- Require `--approve-review` before executing steps marked review-needed.
- Require `--allow-llm` before LLM-backed steps can call providers.
- Validate recipe before execution.
- Print step progress.
- Write outputs only to declared or resolved output paths.
- Return non-zero exit code on failure.
- Use clear error messages.
- Never expose secrets in logs or JSON.

---

## 9. Starter Recipes for First Release

The first release should include 5 built-in starter recipes.

All starter recipes must appear in the packaged `catalog.yaml`.

Each starter should include:

```text
README.md
AGENTS.md
recipe.yaml
inputs/
outputs/
```

### 9.1 `build-data-product-portfolio`

Purpose:

Create a full portfolio build workflow.

Expected workflow:

1. read source materials or fragments
2. generate or collect product reference fragments
3. build ODPC catalog
4. build ODPG graph
5. generate agent context sidecars where relevant
6. validate outputs

Notes for Codex:

If the current SDK still has a hardcoded portfolio builder, this starter should wrap or mirror that behavior first. Do not remove the old command in Phase 1.

### 9.2 `source-to-product-fragments`

Purpose:

Generate product reference fragments from source materials.

Expected inputs:

```text
inputs/source-materials/
```

Expected outputs:

```text
outputs/fragments/
```

Notes:

This recipe may require LLM configuration depending on existing SDK generation behavior.

### 9.3 `fragments-to-odpc-catalog`

Purpose:

Build an ODPC catalog from existing product reference fragments.

Expected inputs:

```text
inputs/fragments/
```

Expected outputs:

```text
outputs/catalog/
```

### 9.4 `fragments-to-odpg-graph`

Purpose:

Build an ODPG graph from existing product reference fragments.

Expected inputs:

```text
inputs/fragments/
```

Expected outputs:

```text
outputs/graph/
```

### 9.5 `generate-agent-context`

Purpose:

Generate agent-facing context from an ODPG graph, using supported sidecar formats such as TOON and GCF where available.

Expected inputs:

```text
inputs/graph/
```

Expected outputs:

```text
outputs/agent-context/
```

---

## 10. Example Workspaces

Add examples separate from starters.

Suggested path:

```text
examples/recipes/
  basic-portfolio-build/
  source-documents-to-fragments/
  online-llm-fragment-generation/
  local-llm-fragment-generation/
  catalog-from-existing-fragments/
  graph-from-existing-fragments/
  graph-to-agent-context/
```

Each example should include:

```text
README.md
AGENTS.md
recipe.yaml
inputs/
outputs-example/
```

Rules:

- examples should be complete and realistic
- examples should not be used directly by `recipe init`
- examples can show variants and edge cases
- starters should remain clean and general
- example recipe files should validate against ODPR schema
- if examples need catalog discovery, add a separate example `catalog.yaml`

---

## 11. Generated README.md Requirements

Each starter workspace README should include:

1. What this recipe does
2. Who it is for
3. Folder structure
4. Inputs to add
5. Commands to run
6. Expected outputs
7. Safety notes
8. Troubleshooting

Minimum command section:

```bash
open-data-products recipe run recipe.yaml --dry-run
open-data-products recipe run recipe.yaml --execute --approve-review
```

---

## 12. Generated AGENTS.md Requirements

Each generated workspace should include `AGENTS.md`.

Minimum content:

```markdown
# Agent Instructions

## Purpose

This workspace contains an ODPR Recipe. Use it to plan, dry-run, and execute an SDK workflow safely.

## Editable Files

- Prefer editing `recipe.yaml` only when the user asks for workflow changes.
- Do not edit generated outputs unless the user asks.
- Do not add secrets to `recipe.yaml`, provider files, `README.md`, or `AGENTS.md`.

## Required Flow

1. Inspect `README.md` and `recipe.yaml`.
2. Run `open-data-products recipe run recipe.yaml --dry-run --json`.
3. Review blocking reasons, planned writes, provider readiness, and review status.
4. Execute only after explicit user approval.
5. Use `open-data-products recipe run recipe.yaml --execute --approve-review --json` when approved.

## Safety Rules

- Do not overwrite existing outputs without approval.
- Do not run LLM-backed steps unless the plan and dry-run show required providers and environment variables.
- Do not put dry-run responses, run manifests, provider readiness results, planned writes, run IDs, or logs into ODPR files.
- Report missing inputs, missing providers, and planned writes clearly.
```

---

## 13. JSON Output Contract

All agent-facing commands should return stable JSON when `--json` is passed.

General success shape:

```json
{
  "ok": true,
  "command": "recipe run --dry-run",
  "messages": [],
  "warnings": [],
  "data": {}
}
```

General error shape:

```json
{
  "ok": false,
  "command": "recipe run --dry-run",
  "messages": [],
  "warnings": [],
  "errors": [
    {
      "code": "missing_input",
      "message": "Expected input folder does not exist: inputs/source-materials"
    }
  ]
}
```

Guidance:

- avoid stack traces in normal JSON output
- include machine-readable error codes
- keep keys stable
- return non-zero exit code when `ok` is false
- include catalog metadata where the command resolves a recipe through `RecipeCatalog`
- include recipe metadata where the command loads a full `Recipe`

---

## 14. Repository Implementation Guidance for Codex

Codex should inspect the current SDK structure before editing.

Likely tasks:

1. Find the CLI entrypoint.
2. Inspect existing ODPR support in `open_data_products/odpr/`.
3. Inspect current ODPR validation, recipe loading, dry-run planning, execution, and guidance helpers.
4. Inspect existing recipe CLI command registration.
5. Inspect existing MCP recipe tools and ARWS classifications.
6. Inspect package data configuration for `open_data_products.odpr`.
7. Add packaged starter resources with `catalog.yaml` under the existing ODPR package structure.
8. Add or update command handlers for starter discovery, initialization, and explanation.
9. Add or update MCP handlers for starter discovery, initialization, and explanation with correct ARWS classifications.
10. Reuse existing parser, validator, dry-run planner, and guarded executor.
11. Add tests.
12. Add docs.

Do not assume exact module paths. Use the current repository structure.

Potential implementation modules if they match project style:

```text
open_data_products/
  odpr/
    data/
      starters/
        catalog.yaml
        build-data-product-portfolio/
        source-to-product-fragments/
        fragments-to-odpc-catalog/
        fragments-to-odpg-graph/
        generate-agent-context/
    starters.py
```

Use this only if it fits the repository style.

---

## 15. Phased Plan

## Phase 0: Repository Discovery

Goal:

Understand current SDK structure before implementation.

Codex tasks:

- inspect CLI framework and command registration
- inspect current ODPR recipe support
- inspect current ODPR schema validation
- inspect current handling of `Recipe`, `Provider`, and `RecipeCatalog` if present
- inspect current recipe parser, validator, executor, and dry-run logic
- inspect existing test patterns
- inspect package data configuration
- inspect documentation structure

Deliverable:

A short implementation note in the PR or commit message describing where changes will be made.

Acceptance checks:

- no behavior change required
- implementation path is clear

## Phase 0.5: Current ODPR Baseline

Goal:

Verify the ODPR support already present in the repository before adding starter quick starts.

Status:

Completed for the current SDK baseline. Keep this phase as a regression check
when resuming the work.

Codex tasks:

- confirm vendored ODPR v1.0 schemas exist under `open_data_products/odpr/data/schema/`
- confirm vendored ODPR schemas include RecipeCatalog grouping fields
- confirm package data includes ODPR schemas, recipe config, and recipe guidance resources
- confirm `recipe validate` validates `Recipe`, `Provider`, and `RecipeCatalog`
- confirm `recipe list` reads configured recipes through `recipes.config.yaml`
- confirm `recipe list --group <id>` and `recipe catalog --group <id>` preserve ODPR `RecipeCatalog` grouping structure
- confirm `recipe run --dry-run` returns an agent-facing plan without writes or provider calls
- confirm `recipe run --execute` remains guarded by review and LLM approval options
- confirm MCP tools `list_recipes`, `validate_recipe`, `plan_recipe_run`, and `search_recipe_guidance` remain safe
- confirm MCP `list_recipes` accepts optional `group`
- identify whether generic top-level `validate` should also detect ODPR documents, or whether ODPR validation intentionally stays under `recipe validate`

Acceptance checks:

```bash
open-data-products recipe validate path/to/recipe.yaml --json
open-data-products recipe validate path/to/catalog.yaml --json
open-data-products recipe run path/to/recipe.yaml --dry-run --json
open-data-products resources --json
```

Expected:

- ODPR documents validate through the existing recipe validation path
- `Recipe`, `Provider`, and grouped `RecipeCatalog` validation uses the existing vendored ODPR schema
- packaged schema resources work from an installed package, not only from a source checkout

## Phase 1: Packaged Starter Catalog Discovery

Goal:

Use a packaged grouped ODPR `RecipeCatalog` as the source of truth for starter
recipe discovery without breaking existing `recipe list` behavior for
configured project recipes.

Starting point:

The SDK already understands grouped `RecipeCatalog` documents and can generate
grouped project catalogs. Phase 1 should add packaged starter discovery on top
of that foundation.

Codex tasks:

- add packaged starter `catalog.yaml`
- include `recipeCatalog.version`
- define a starter group in `recipeCatalog.groups[]`
- assign starter entries with `groupRef: starters`
- validate `catalog.yaml` as `kind: RecipeCatalog`
- add parser helper for catalog loading if missing
- add catalog entry resolution by id, normalized English name, and folder name from `path`
- add starter discovery to `recipe list` through an explicit option such as `--starters`, or add a dedicated subcommand such as `recipe starters`
- add JSON output for starter discovery
- add `recipe catalog-check` only if it does not conflict with existing `recipe catalog`; otherwise add `recipe starter-catalog-check`
- add safe MCP handlers for listing starter recipes and checking the starter catalog
- ensure catalog and starter resources are included in package build
- add unit tests for catalog validation and discovery

Acceptance checks:

```bash
open-data-products recipe list --starters
open-data-products recipe list --starters --json
open-data-products recipe starter-catalog-check
open-data-products recipe starter-catalog-check --json
```

If implementation chooses `recipe starters` instead of `recipe list --starters`, update these commands consistently. Starter discovery commands and equivalent MCP handlers must work from an installed package, not only from a source checkout.

## Phase 2: Built-in Starter Recipe Resources

Goal:

Add the first starter recipe folders referenced by `catalog.yaml`.

Codex tasks:

- add 5 starter folders
- add a valid ODPR `Recipe` file to each folder
- make each starter recipe an executable workflow contract, even if SDK execution support is delivered in a later phase
- add `README.md`
- add `AGENTS.md`
- add empty or placeholder `inputs/` and `outputs/` folders as appropriate
- ensure each catalog entry points to the correct `recipe.yaml`
- run the starter catalog check command
- add tests that every catalog path resolves

Acceptance checks:

```bash
open-data-products recipe starter-catalog-check
```

Expected:

- catalog validates
- referenced recipe files exist
- referenced recipe files validate
- README.md and AGENTS.md exist for each starter

## Phase 3: Recipe Init Workspace Generation

Goal:

Let users create a working recipe workspace from a catalog entry.

Codex tasks:

- add `recipe init <id-or-name>`
- support `--output PATH`
- support `--force`
- support `--json`
- support `--catalog PATH`
- copy the starter folder that contains the referenced recipe
- fail safely when output exists without `--force`
- print next commands after success
- add a `state-changing` MCP handler for initializing a starter workspace
- update agent manifest and agentic pattern tests for the new `state-changing` recipe init tool
- add tests for output creation and overwrite protection

Acceptance checks:

```bash
open-data-products recipe init build-data-product-portfolio --output /tmp/portfolio-recipe
ls /tmp/portfolio-recipe
```

Expected files:

```text
README.md
AGENTS.md
recipe.yaml
inputs/
outputs/
```

## Phase 4: Recipe Explain

Goal:

Explain starter recipes and local recipe files for humans and agents.

Codex tasks:

- add or update `recipe explain <id-or-path>`
- support catalog id input
- support normalized English name input
- support local recipe path input
- support `--catalog PATH`
- support `--json`
- include catalog metadata when resolved through catalog
- include full recipe details after loading referenced recipe
- include inputs, outputs, execution mode, provider reference, context format, gates, review requirement, safety notes, and next commands
- add a safe MCP handler for explaining starter and local recipes
- add tests for starter explain and local recipe explain

Acceptance checks:

```bash
open-data-products recipe explain build-data-product-portfolio
open-data-products recipe explain build-data-product-portfolio --json
open-data-products recipe explain /tmp/portfolio-recipe/recipe.yaml --json
```

## Phase 5: Dry-Run Planning Hardening

Goal:

Ensure the existing `recipe run --dry-run` path gives a complete execution plan without running steps.

Codex tasks:

- improve `recipe run <recipe.yaml> --dry-run`
- support `--json`
- parse recipe and list steps
- show planned reads and writes where available in the recipe structure
- show required environment variables if known
- show provider requirements if known
- show gates and review requirement
- do not write files
- do not call providers
- add tests for no-write behavior

Acceptance checks:

```bash
open-data-products recipe run /tmp/portfolio-recipe/recipe.yaml --dry-run
open-data-products recipe run /tmp/portfolio-recipe/recipe.yaml --dry-run --json
```

## Phase 6: Optional Compatibility Aliases

Goal:

Decide whether to add user-friendly aliases around the existing runner.

Codex tasks:

- decide whether to add `recipe plan <recipe.yaml>` as an alias for `recipe run <recipe.yaml> --dry-run`
- decide whether to add `recipe dry-run <recipe.yaml>` as an alias for `recipe run <recipe.yaml> --dry-run`
- if aliases are added, delegate to existing `plan_recipe_run`
- keep JSON output shape identical to the existing dry-run path
- add tests proving aliases do not write final outputs

Acceptance checks:

```bash
open-data-products recipe run /tmp/portfolio-recipe/recipe.yaml --dry-run --json
```

If aliases are added:

```bash
open-data-products recipe plan /tmp/portfolio-recipe/recipe.yaml --json
open-data-products recipe dry-run /tmp/portfolio-recipe/recipe.yaml --json
```

## Phase 7: Guarded Execution Alignment

Goal:

Align starter recipes with the existing guarded execution model.

Codex tasks:

- confirm `recipe run <recipe.yaml> --execute` remains guarded
- require `--approve-review` for review-needed steps
- require `--allow-llm` for LLM-backed provider calls
- run validation before execution
- support `--json`
- print step progress
- return non-zero exit code on failure
- add tests for missing review approval, missing LLM approval, and approved deterministic execution path

Acceptance checks:

```bash
open-data-products recipe run /tmp/portfolio-recipe/recipe.yaml --execute
```

Expected:

Fails if review-needed or LLM-backed steps lack the required approval flags.

```bash
open-data-products recipe run /tmp/portfolio-recipe/recipe.yaml --execute --approve-review
```

Expected:

Runs deterministic approved steps or fails only because required inputs, write policy, or providers are missing.

## Phase 8: Example Workspaces

Goal:

Add realistic examples separate from starters.

Codex tasks:

- add examples under `examples/recipes/`
- include README.md, AGENTS.md, recipe.yaml, inputs/, outputs-example/
- keep sample inputs small
- avoid committing large generated artifacts
- add docs index linking examples
- optionally add an example `catalog.yaml` if useful for discovery demos

Initial examples:

```text
basic-portfolio-build
source-documents-to-fragments
online-llm-fragment-generation
local-llm-fragment-generation
catalog-from-existing-fragments
graph-from-existing-fragments
graph-to-agent-context
```

Acceptance checks:

- each example has a README
- each example has a recipe.yaml
- each example recipe validates against ODPR schema
- each example describes expected outputs
- examples are not confused with starter templates

## Phase 9: Optional Parameterized Recipe Mode

Goal:

Support advanced reuse without making it the default.

Codex tasks:

- add `recipe init <id-or-name> --parameterized`
- generate `recipe.values.yaml`
- generate `values.schema.yaml`
- update README and AGENTS.md to explain values usage
- support `recipe plan recipe.yaml --values recipe.values.yaml` if not already supported
- support `recipe dry-run recipe.yaml --values recipe.values.yaml` if not already supported
- add tests

Acceptance checks:

```bash
open-data-products recipe init build-data-product-portfolio --parameterized --output /tmp/portfolio-template
```

Expected files:

```text
README.md
AGENTS.md
recipe.yaml
recipe.values.yaml
values.schema.yaml
inputs/
outputs/
```

## Phase 10: Documentation and Release Notes

Goal:

Make the feature understandable and releasable.

Codex tasks:

- add docs page: `docs/recipes/quick-start.md`
- add docs page: `docs/recipes/agent-usage.md`
- add docs page: `docs/recipes/catalog.md`
- add docs page: `docs/recipes/examples.md`
- update main SDK README or command index
- add release note entry

Documentation should explain:

- why quick starts exist
- human path
- agent path
- ODPR `RecipeCatalog`
- starter recipes vs examples
- self-contained recipe vs parameterized recipe
- approval and dry-run model
- why runtime data must not be written back into ODPR files

Acceptance checks:

- docs include copy-pasteable commands
- docs mention `catalog.yaml`
- docs mention `AGENTS.md`
- docs mention that `recipe.values.yaml` is advanced, not default
- docs state that `RecipeCatalog` is metadata-only

---

## 16. Backward Compatibility

- Do not remove existing recipe commands.
- Do not remove the existing portfolio builder in the first implementation.
- If the portfolio builder is later implemented through ODPR internally, keep the old command as a compatibility shortcut.
- New commands should fail safely and avoid overwriting files by default.
- Existing ODPR `Recipe` and `Provider` validation behavior must keep working.
- `RecipeCatalog` support must use the existing ODPR schema, not a new SDK-private schema.

---

## 17. Testing Strategy

Minimum tests:

1. existing vendored ODPR schema resources load from package data
2. ODPR `Recipe`, `Provider`, and `RecipeCatalog` documents validate through `recipe validate`
3. packaged `catalog.yaml` validates as ODPR `RecipeCatalog`
4. every catalog entry path exists
5. every referenced recipe validates as ODPR `Recipe`
6. no catalog entry includes forbidden runtime fields
7. starter discovery human output
8. starter discovery JSON output
9. starter catalog check
10. starter catalog check JSON output
11. safe MCP recipe discovery handlers return stable content envelopes
12. `recipe init` creates expected files
13. `recipe init` refuses existing output without `--force`
14. MCP recipe init handler is classified as `state-changing`
15. `recipe explain` for catalog entry
16. `recipe explain` for local recipe path
17. safe MCP recipe explain handler works for catalog entries and local recipes
18. JSON output has stable agent-facing keys consistent with existing recipe reports
19. package build includes ODPR schemas, catalog, and starter resources
20. `recipe run --dry-run` does not write final outputs
21. optional `recipe plan` or `recipe dry-run` aliases, if added, do not write final outputs
22. `recipe run --execute` fails without required review or LLM approval flags

Suggested test command:

```bash
pytest
```

Use the repository's existing test command if different.

---

## 18. Non-Goals for First Release

Do not implement these in the first release unless the SDK already has most of the support:

- remote recipe registries
- organization recipe sources
- interactive wizard
- GUI recipe library
- recipe marketplace
- full recipe version locking
- new ODPR catalog model
- SDK-private recipe index schema
- parameterized values mode
- destructive MCP recipe tools
- MCP recipe execution tools

These can follow after the SDK quick start model proves useful.

---

## 19. Open Design Questions

1. Should starter recipe lookup support aliases through `x-sdk-aliases` until ODPR adds aliases?
2. Should the SDK support `recipes.jsonl` lookup later, or is `catalog.yaml` enough for SDK discovery?
3. Should `recipe explain` prefer catalog metadata, recipe metadata, or show both?
4. Should user-friendly `recipe plan` or `recipe dry-run` aliases be added, or should docs standardize on `recipe run --dry-run`?
5. Should the hardcoded portfolio builder become an internal ODPR recipe in a later release?
6. Should `recipe init` preserve the original catalog path or always copy the referenced recipe as `recipe.yaml`?
7. Should the MCP recipe init tool expose `--force`, or should it always refuse existing output paths even if the CLI supports `--force`?

Resolved:

- The ODPR schema is already vendored locally from the official ODPR v1.0 JSON and YAML schema URLs.
- The vendored ODPR schema includes grouped `RecipeCatalog` support:
  `recipeCatalog.version`, `recipeCatalog.groups[]`, and
  `recipeCatalog.recipes[].groupRef`.
- The SDK already validates grouped catalogs and rejects duplicate group ids,
  duplicate recipe ids, and unresolved `groupRef` values.
- The SDK already supports grouped project catalog output through
  `recipe list --group <id>`, `recipe catalog --group <id>`, and MCP
  `list_recipes(group=...)`.
- The quick-start implementation should add starter discovery, init, and explain on top of existing ODPR validation, dry-run planning, and guarded execution.
- Starter recipes should be executable ODPR contracts compatible with the current recipe runner.
- Recipe quick-start support should exist in both CLI and MCP surfaces. MCP discovery and explanation are safe; MCP init is state-changing because it creates a workspace.

---

## 20. Codex Execution Checklist

Use this checklist before opening a PR.

- [x] The SDK reuses the existing packaged official ODPR v1.0 schema.
- [x] The vendored ODPR schema supports grouped `RecipeCatalog` documents.
- [x] The SDK validates grouped catalog references.
- [x] Project recipe catalog output can assign entries to a group.
- [ ] The SDK uses `catalog.yaml` for starter discovery.
- [ ] The catalog root object is `kind: RecipeCatalog`.
- [ ] The catalog validates against ODPR v1.0 schema.
- [ ] Starter discovery JSON derives output from `RecipeCatalog`.
- [ ] `recipe init` resolves recipes through the catalog.
- [ ] MCP recipe init is classified as `state-changing`.
- [ ] `recipe explain` loads the full referenced recipe before explaining execution details.
- [ ] Catalog entries do not include step bodies or runtime data.
- [ ] Starter recipe files validate as `kind: Recipe`.
- [ ] Each starter has `README.md`.
- [ ] Each starter has `AGENTS.md`.
- [ ] JSON outputs are stable and safe for agents.
- [ ] No command overwrites files unless explicit force or approval is provided.
- [ ] Guarded execution keeps existing `--execute`, `--approve-review`, and `--allow-llm` safety behavior.
- [ ] Tests cover packaged resource loading.
- [ ] Docs explain the human and agent paths.
