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
- Simplified the starter CLI flow: bare `recipe list` shows packaged starters
  when no local `recipes.config.yaml` is present, starter init now defaults to
  `./recipes/<starter-folder>/`, and initialized workspaces can be planned with
  `recipe plan` from the workspace directory.
- Added `open-data-products recipe explain <id-or-path>` to explain packaged
  starters or local recipe files without executing steps or calling providers.
- Hardened `recipe run --dry-run` planning with explicit no-write and
  no-provider-call guarantees, top-level planned reads and writes, gate and
  review summaries, execution/context policy summaries, required environment
  variable reporting, and corrected `portfolio.build` workspace write
  detection.
- Added `open-data-products recipe plan` and
  `open-data-products recipe dry-run` as compatibility aliases for
  `recipe run --dry-run`; both reuse the same dry-run payload and no-write
  behavior.
- Added current-directory recipe discovery for `recipe.yaml`, so `recipe plan`,
  `recipe dry-run`, `recipe validate`, and guarded execution can run from
  inside an initialized recipe workspace without repeating the recipe path.
- Aligned initialized starter recipes with the guarded execution model:
  LLM-backed starter steps stay blocked without `--allow-llm`, review-needed
  steps stay blocked without `--approve-review`, and approving review does not
  implicitly permit provider calls.
- Simplified guarded execution approval ergonomics: `recipe run --approve-review`
  or `recipe run --allow-llm --approve-review` executes the current recipe,
  while `--dry-run` still forces planning.
- Added workspace-style ODPR examples under `examples/recipes/workspaces/`,
  separate from packaged starters, covering portfolio build, source document
  fragment generation, hosted and local LLM generation, catalog assembly, graph
  build, and graph-to-agent-context rendering.
- Added advanced `recipe init --parameterized` support that generates
  `recipe.values.yaml` and `values.schema.yaml` alongside the initialized
  starter workspace while keeping the default init path self-contained.
- Added Python helpers for starter listing, catalog checking, starter
  resolution, workspace initialization, and recipe explanation.
- Added MCP tools for starter recipe discovery, catalog checking, and starter
  initialization plus recipe explanation. Discovery, catalog checks, and
  explanation are `safe`; workspace initialization is `state-changing`.
- Updated the ARWS manifest and development architecture docs to describe ODPR
  quick starts, `RecipeCatalog` discovery, and the MCP tool classification.
- Added Phase 10 user-facing recipe docs for quick starts, agent usage,
  `RecipeCatalog` behavior, and example workspaces, and linked them from the
  docs index, command guide, root README, and full recipe workflow guide.
- Added tests for packaged starter catalog validation, referenced recipe
  validation, lookup by id/name/folder, CLI starter commands, MCP starter
  commands, recipe explanation, overwrite protection, and manifest
  classification.

## Not Included Yet

- Guarded execution was reused as an existing recipe runner surface, with
  starter-specific regression coverage added rather than a new execution model.
