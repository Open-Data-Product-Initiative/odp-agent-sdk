# Release Summary: ODPR Recipe Quick Starts

- Confirmed the SDK quick-start work reuses the existing vendored ODPR v1.0
  schema and the existing `open_data_products.odpr` package structure.
- Added grouped `RecipeCatalog` foundation support: `recipeCatalog.version`,
  `recipeCatalog.groups[]`, `recipeCatalog.recipes[].groupRef`, duplicate
  group and recipe id checks, unresolved `groupRef` checks, and grouped catalog
  output for project recipes.
- Added grouped project recipe catalog output through
  `open-data-products recipe list --group <id>`,
  `open-data-products recipe catalog --group <id>`, and the MCP
  `list_recipes` group argument.
- Added packaged ODPR starter recipe discovery backed by the bundled
  `RecipeCatalog` at `open_data_products/odpr/data/starters/catalog.yaml`.
- Added bundled starter catalog resource registration under
  `odpr.starter-catalog`.
- Added five starter recipe workspaces with `recipe.yaml`, `README.md`, and
  `AGENTS.md` files for portfolio build, source-to-fragments,
  fragments-to-ODPC catalog, fragments-to-ODPG graph, and agent context
  generation workflows.
- Added starter catalog resolution by catalog id, normalized English name, and
  folder name derived from catalog `path`.
- Added `open-data-products recipe list --starters` and
  `open-data-products recipe starter-catalog-check` for starter discovery and
  validation.
- Added `open-data-products recipe init <id-or-name>` to create a local starter
  workspace, with `--output`, `--force`, `--catalog`, and `--json` support.
- Added Python helpers for starter listing, catalog checking, starter
  resolution, and workspace initialization.
- Added MCP tools for starter recipe discovery, catalog checking, and starter
  initialization. Discovery and catalog checks are `safe`; workspace
  initialization is `state-changing`.
- Updated the ARWS manifest and development architecture docs to describe ODPR
  quick starts, `RecipeCatalog` discovery, and the MCP tool classification.
- Added tests for packaged starter catalog validation, referenced recipe
  validation, lookup by id/name/folder, CLI starter commands, MCP starter
  commands, overwrite protection, and manifest classification.

## Not Included Yet

- `recipe explain <id-or-path>` is not implemented yet.
- Parameterized starter mode is not implemented yet.
- Example workspaces separate from starters are not implemented yet.
- Dry-run planning and guarded execution were reused as existing recipe runner
  surfaces, not redesigned in this quick-start phase.
