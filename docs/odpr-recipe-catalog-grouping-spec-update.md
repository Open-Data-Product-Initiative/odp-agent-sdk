# ODPR RecipeCatalog Grouping Spec Update

## Purpose

ODPR `RecipeCatalog` is the source-of-truth discovery format for recipes. The
current ODPR v1.0 catalog lists recipes in one flat `recipeCatalog.recipes`
array. That is enough for simple discovery, but SDKs, platforms, courses, and
agents need a spec-native way to organize recipes without inventing SDK-only
grouping models.

This note proposes adding optional catalog groups to ODPR.

## Problem

Recipe catalogs need to represent different recipe collections in one catalog,
for example:

- project recipes maintained in a workspace
- starter recipes used to initialize new workspaces
- complete example recipes used for learning
- organization-approved recipes
- release, CI, localization, or governance recipe collections

Using `tags` for this works only loosely. Tags are semantic search metadata, not
a stable catalog organization model. Using SDK-only fields such as `source`,
`sourceType`, or `initializable` would create a second discovery model outside
ODPR.

## Proposal

Add optional `recipeCatalog.groups[]` and optional
`recipeCatalog.recipes[].groupRef`.

Example:

```yaml
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: RecipeCatalog
recipeCatalog:
  metadata:
    id: RCP-CATALOG-001
    name:
      en: ODPR Example Recipe Catalog

  groups:
    - id: project
      name:
        en: Project Recipes
      description:
        en: Recipes maintained by this workspace.

    - id: starters
      name:
        en: Starter Recipes
      description:
        en: Recipes intended for initializing new workspaces.

    - id: examples
      name:
        en: Example Recipes
      description:
        en: Complete learning and demonstration recipes.

  recipes:
    - path: recipes/release-portfolio-review.yaml
      id: RCP-RELEASE-001
      groupRef: project
      version: "1.0.0"
      type: release
      name:
        en: Release Portfolio Review
      description:
        en: Refresh, localize, explain, and review a portfolio before release.
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
        - portfolio.explain
```

## Field Semantics

`recipeCatalog.groups`

Optional array of metadata-only group definitions for organizing catalog
entries.

`groups[].id`

Stable group identifier. Must be unique within the catalog.

`groups[].name`

Localized display name for humans and agents.

`groups[].description`

Optional localized description of the group purpose.

`recipes[].groupRef`

Optional reference to a declared `groups[].id`. If present, it assigns the
recipe entry to that group.

## Validation Rules

Recommended schema and semantic rules:

1. `recipeCatalog.groups` is optional.
2. Existing catalogs without groups remain valid.
3. `groups[].id` is required when a group is declared.
4. `groups[].id` values must be unique within one catalog.
5. `groups[].name` is required.
6. `groups[].description` is optional.
7. `recipes[].groupRef` is optional.
8. If `recipes[].groupRef` is present, it must match one declared
   `groups[].id`.
9. A recipe entry without `groupRef` is ungrouped.
10. Groups must not contain recipe step bodies, credentials, provider readiness
    results, runtime status, planned writes, run IDs, or logs.

## Why Not Tags

Tags should remain semantic and searchable:

```yaml
tags:
  - portfolio
  - release
  - governance
```

Groups describe catalog organization:

```yaml
groupRef: starters
```

This avoids overloading tags with UI or library structure and keeps grouping
stable enough for SDKs and agents.

## Why Not Type

`type` should continue to describe the recipe workflow kind, such as `release`,
`agent`, `ci`, or `localization`. A starter can still have a meaningful workflow
type. Grouping it as a starter is a catalog placement decision, not necessarily
the workflow type.

## SDK Implications

After the ODPR schema supports groups, SDK behavior can be:

```bash
open-data-products recipe list
open-data-products recipe list --group starters
open-data-products recipe init build-data-product-portfolio
```

Expected behavior:

- `recipe list` reads ODPR `RecipeCatalog`.
- Human output can group recipes by `recipeCatalog.groups`.
- JSON output should preserve the catalog-first structure.
- `recipe init` can resolve recipes from entries whose `groupRef` is
  `starters`, or from another group explicitly allowed for initialization.
- SDKs should not create a parallel source-of-truth grouping model.

## JSON Output Guidance

SDKs may wrap command results, but the catalog data should remain recognizably
ODPR:

```json
{
  "ok": true,
  "command": "recipe list",
  "catalog": {
    "kind": "RecipeCatalog",
    "metadata": {
      "id": "RCP-CATALOG-001",
      "name": {
        "en": "ODPR Example Recipe Catalog"
      }
    },
    "groups": [
      {
        "id": "starters",
        "name": {
          "en": "Starter Recipes"
        }
      }
    ],
    "recipes": [
      {
        "id": "RCP-SDK-PORTFOLIO-001",
        "groupRef": "starters",
        "path": "starters/build-data-product-portfolio/recipe.yaml",
        "version": "1.0.0",
        "type": "agent",
        "name": {
          "en": "Build Data Product Portfolio"
        }
      }
    ]
  }
}
```

## Backward Compatibility

This is backward compatible if both new fields are optional:

- old catalogs without `groups` remain valid
- old catalog entries without `groupRef` remain valid
- tools that do not understand grouping can still list all recipes
- tools that understand grouping can render grouped output

## Migration

Existing flat catalogs can be migrated incrementally:

1. Add `recipeCatalog.groups`.
2. Add `groupRef` to selected recipe entries.
3. Leave ungrouped recipes unchanged.
4. Update SDK/docs examples to use group-aware listing.

## Open Questions

1. Should a recipe entry support multiple groups, or only one `groupRef`?
2. Should ODPR define recommended group IDs such as `project`, `starters`, and
   `examples`, or leave all group IDs user-defined?
3. Should groups support optional ordering, such as `position`?
4. Should groups support nested groups, or should v1 keep grouping flat?
5. Should `recipe init` behavior be driven by group ID, a future ODPR field, or
   SDK policy?

## Recommendation

Add flat optional groups now:

- `recipeCatalog.groups[]`
- `groups[].id`
- `groups[].name`
- `groups[].description`
- `recipeCatalog.recipes[].groupRef`

Keep it simple, metadata-only, and backward compatible.
