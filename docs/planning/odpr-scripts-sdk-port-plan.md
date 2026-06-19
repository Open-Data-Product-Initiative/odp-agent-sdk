# ODPR Scripts To SDK Port Plan

Source reviewed:
https://github.com/Open-Data-Product-Initiative/odpr-v1.0/tree/main/scripts

This note maps ODPR spec-repo scripts to SDK responsibilities now that the SDK
has an `open_data_products.odpr` namespace.

## Current SDK Baseline

The SDK now has:

- `open_data_products.odpr`
- recipe loading
- recipe structural validation
- ODPR document validation for `Recipe`, `Provider`, and `RecipeCatalog`
- bundled ODPR YAML and JSON schemas
- Draft 2020-12 JSON Schema validation for ODPR documents
- embedded-secret scanning for ODPR documents
- recipe runner config validation
- recipe catalog-style listing from configured folders
- metadata-only `RecipeCatalog` generation
- dry-run planning with structured `resolved.parameters`
- CLI commands under `open-data-products recipe ...`

The SDK does not yet have:

- bundled ODPR `recipes.jsonl` search records

## Script Mapping

| ODPR script | What it does in the spec repo | SDK decision | SDK target |
| --- | --- | --- | --- |
| `validate_recipe.py` | Validates `Recipe`, `Provider`, or `RecipeCatalog` documents against the ODPR JSON Schema and rejects embedded secrets. | Brought. The SDK bundles the ODPR schema, runs Draft 2020-12 validation, and applies secret/runtime hardening. | `open_data_products.odpr.validation` and `open-data-products recipe validate`. |
| `build_recipe_catalog.py` | Builds metadata-only `RecipeCatalog` YAML from canonical recipe examples. | Brought and generalized for project recipe folders. | `build_recipe_catalog()`, `write_recipe_catalog()`, and `open-data-products recipe catalog --config recipes.config.yaml --output catalog.yaml`. |
| `search_recipes.py` | Searches ODPR `recipes.jsonl` concept records by query or id. | Bring after bundled ODPR resources exist. | Add `open-data-products recipe search ...` or expose through `resources`/MCP search if the records are bundled. |
| `odpr_paths.py` | Centralizes spec-repo source paths. | Do not port as-is. | Replace with package resource helpers under `open_data_products.odpr.resources` if ODPR schema/examples are bundled. |
| `generate_recipe_artifacts.py` | Generates derived `odpr.json` from canonical `odpr.yaml`. | Do not bring as runtime feature. | Keep this in the ODPR spec repo. SDK should consume released/generated schema artifacts, not generate spec artifacts for users. |
| `check_agent_artifacts.py` | CI consistency check for schema, examples, `recipes.jsonl`, catalog, and `llms.txt`. | Do not bring as CLI feature. Port selected assertions into SDK tests after bundling ODPR artifacts. | Add tests only, not a public SDK command. |
| `requirements-agent.txt` | Lists script dependencies: `PyYAML` and `jsonschema`. | Already covered. | No SDK change needed. |

## Bring First

### 1. Schema-Backed ODPR Validation

Add SDK support for validating ODPR documents using bundled schema artifacts.

Status: implemented. The SDK validates ODPR root kinds, required fields,
command-specific step parameter schemas, metadata-only catalog constraints, and
embedded secrets through the bundled ODPR schema plus SDK hardening checks.

Target behavior:

```bash
open-data-products recipe validate recipes/release-portfolio-review.yaml --json
```

Should check:

- document is valid YAML or JSON;
- root `kind` is one of `Recipe`, `Provider`, or `RecipeCatalog`;
- document validates against bundled ODPR JSON Schema when available;
- `RecipeRunPlan`, `RecipeRunManifest`, and `RecipeInspection` are rejected as
  ODPR v1 roots;
- embedded secret-like field names and values are rejected.

Implementation direction:

- Add `open_data_products/odpr/validation.py`.
- Move structural recipe validation from `recipes.py` into ODPR validation
  helpers or call shared helpers from there.
- Keep `recipes.py` focused on workflow planning and runner config.
- Add tests for `Provider` and `RecipeCatalog`, not only `Recipe`.

### 2. Secret Scanning

Port the useful parts of `validate_recipe.py`:

- secret-like key detection;
- secret-like value detection;
- allow `credentialsRef`, `endpointRef`, and similar reference fields;
- reject raw keys such as `apiKey`, `password`, `authorization`, `bearer`, and
  obvious token patterns.

This belongs in SDK validation because users will author provider profiles in
projects, not only in the ODPR spec repo.

Status: implemented in `open_data_products.odpr.validation`.

### 3. RecipeCatalog Builder

The SDK already returns catalog-style JSON from `recipe list`. It should also be
able to write a standard ODPR `RecipeCatalog`.

Target behavior:

```bash
open-data-products recipe catalog \
  --config recipes.config.yaml \
  --output recipes/catalog.yaml
```

The generated catalog should:

- be `kind: RecipeCatalog`;
- include only metadata;
- include recipe paths, ids, versions, types, names, tags, execution mode,
  provider ref, context format, review requirement, and command list;
- not include steps, run ids, logs, planned writes, provider readiness, or
  runtime status.

Status: implemented for configured project recipe paths.

## Bring Later

### 4. Recipe Search

Bring `search_recipes.py` only after the SDK bundles ODPR recipe guidance
records.

Possible shape:

```bash
open-data-products recipe search localization --json
open-data-products recipe search --id RecipeCatalog --json
```

This should search concept records, not project recipe files. Project recipe
file discovery remains `recipe list`.

### 5. ODPR Resource Bundling

If ODPR becomes a full SDK namespace, bundle:

- ODPR YAML schema;
- generated ODPR JSON schema;
- canonical recipe examples;
- provider examples;
- recipe catalog example;
- recipe guidance JSONL records.

Then expose them through existing SDK resource discovery:

```bash
open-data-products resources --id odpr.schema --json
open-data-products resources --id odpr.recipes --json
```

## Leave In ODPR Spec Repo

Do not make these user-facing SDK commands:

- `generate_recipe_artifacts.py`
- `check_agent_artifacts.py`

Those are spec maintenance and CI scripts. The SDK should consume released
schema/resources and expose validation, discovery, planning, and search
capabilities.

## Recommended SDK Implementation Sequence

1. Keep `recipe validate` validating `Recipe`, `Provider`, and
   `RecipeCatalog`.
2. Add ODPR resources to `resources` and agent manifest metadata.
3. Add recipe guidance search only after `recipes.jsonl` is bundled.

## Non-Goals

- Do not port spec artifact generation as SDK runtime behavior.
- Do not expose `RecipeRunPlan`, `RecipeRunManifest`, or `RecipeInspection` as
  ODPR v1 document kinds.
- Do not add state-changing recipe execution until validation, catalog
  generation, and write-scope planning are solid.
