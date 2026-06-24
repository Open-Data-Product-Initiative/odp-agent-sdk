# ODPR RecipeCatalog

An ODPR `RecipeCatalog` is the discovery layer for recipes. It is metadata-only
and points to full `Recipe` files instead of embedding executable step bodies.

The SDK uses the existing ODPR schema and the bundled starter catalog at:

```text
open_data_products/odpr/data/starters/catalog.yaml
```

## What Belongs in a Catalog

Catalog entries describe:

- recipe id
- version
- type
- localized name and description
- group reference
- tags
- execution mode
- provider reference
- context format
- review requirement
- command names
- path to the full `recipe.yaml`

Catalog entries should not store runtime inputs, generated outputs, approval
records, secrets, or provider responses.

## Starter Discovery

Use the CLI to list packaged starters:

```bash
open-data-products recipe list
open-data-products recipe list --starters --json
```

Bare `recipe list` shows packaged starters when the current directory has no
`recipes.config.yaml`. If a project config exists, `recipe list` keeps the
configured project recipe behavior. Use `--starters` to request packaged
starters explicitly.

Validate the packaged catalog and referenced recipes:

```bash
open-data-products recipe starter-catalog-check --json
```

## Project Catalogs

Project catalogs are still supported through recipe runner config:

```bash
open-data-products config recipes --copy-to recipes.config.yaml
open-data-products recipe list --config recipes.config.yaml --json
open-data-products recipe catalog --config recipes.config.yaml --output recipes/catalog.yaml --json
```

Use `--group <id>` when a generated project catalog should assign entries to a
specific `recipeCatalog.groups[]` group.

## Lookup

Starter init and explanation can resolve a starter by catalog id, English name,
or folder name:

```bash
open-data-products recipe explain build-data-product-portfolio
open-data-products recipe init RCP-SDK-PORTFOLIO-BUILD
```
