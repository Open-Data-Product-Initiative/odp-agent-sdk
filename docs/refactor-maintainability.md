# Maintainability Refactor Plan

Goal: improve maintainability, code clarity, architecture, and structure without
changing public behavior.

This plan is intentionally conservative. Each task keeps existing public
facades in place, runs focused tests immediately after the change, and ends with
the repository-level verification gate.

## Baseline

Captured on 2026-06-14 on branch `refactor-maintainability`.

- `pytest -q`: pass
- `python3 -c "import open_data_products; print(open_data_products.__version__)"`: `0.2.3`
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`: pass
- `test ! -e docs/superpowers`: pass

## Non-Negotiables

- Keep public imports and command names stable.
- Keep `open_data_products.cli:main` as the unified console script target.
- Keep MCP tool names, input schemas, and manifest shape stable unless a test is
  intentionally changed first.
- Do not combine behavior changes with file moves.
- Do not introduce new files under `docs/superpowers/`.
- Do not remove compatibility wrappers until a separate deprecation plan exists.
- Run the verification gate after every completed task.

## Verification Gate

Run these before claiming any task is complete:

```bash
pytest -q
python3 -c "import open_data_products; print(open_data_products.__version__)"
python3 -m open_data_products.cli manifest --json | python3 -m json.tool
test ! -e docs/superpowers
git diff --check
```

For release readiness or packaging-sensitive changes, add:

```bash
rm -rf dist build open_data_products.egg-info
PYTHONDONTWRITEBYTECODE=1 python3 -m build
python3 -m twine check dist/*
```

## Current Hotspots

- `open_data_products/portfolio.py` is the largest module and mixes workflow
  orchestration, prompt parsing, source tracking, normalization, persistence,
  validation aggregation, localization, HTML rendering, CSS, and JavaScript.
- `open_data_products/generation/__init__.py` mixes public exports, provider
  clients, config loading, prompt rendering, generation workflows, YAML
  extraction, ODPS normalization, and artifact validation.
- `open_data_products/cli.py` has one large parser-and-dispatch function.
- ODPS normalization rules are duplicated between portfolio and generation.
- Root package imports are broad; internal modules should prefer concrete
  namespace imports over importing through `open_data_products`.

## Task 1: Add Refactor Guard Tests

Purpose: freeze the behavior that must survive module moves.

Files:

- Modify: `tests/test_namespace_layout.py`
- Modify: `tests/test_functional_cli.py`
- Modify: `tests/test_functional_mcp.py`
- Modify: `tests/test_generation_prompts.py`
- Modify: `tests/test_portfolio.py`

Steps:

1. Add or tighten tests that assert the current public root exports needed by
   README examples still exist.
2. Add CLI smoke tests for command families before moving command handlers:
   `validate`, `generate`, `odpc-build`, `odpg-build`, `portfolio`, `product`,
   `manifest`, and `serve`.
3. Add MCP manifest invariants for tool count, tool names, tool classes, and
   JSON-serializable manifest output.
4. Add focused tests around representative portfolio and generation outputs
   that currently depend on normalization.
5. Run targeted tests:

```bash
pytest tests/test_namespace_layout.py tests/test_functional_cli.py tests/test_functional_mcp.py tests/test_generation_prompts.py tests/test_portfolio.py -q
```

6. Run the full verification gate.

Commit message:

```bash
git commit -m "test: add refactor safety guards"
```

## Task 2: Extract Shared ODPS Normalization Internals

Purpose: remove duplicated normalization rules before moving larger modules.

Files:

- Create: `open_data_products/odps/_normalization.py`
- Modify: `open_data_products/generation/__init__.py`
- Modify: `open_data_products/portfolio.py`
- Test: `tests/test_generation_prompts.py`
- Test: `tests/test_portfolio.py`

Approach:

- Move shared ODPS constants and pure helper functions into
  `open_data_products.odps._normalization`.
- Keep the module internal; do not export it from `open_data_products.odps`.
- Move only helpers with identical behavior or clearly equivalent intent.
- Leave portfolio-specific and generation-specific wrappers in place where their
  names reduce churn.

Target candidates:

- SLA dimension and unit normalization.
- Data quality dimension and unit normalization.
- Product type normalization where generation owns product drafting.
- Pricing plan normalization if both workflows currently use the same rules.
- Data access normalization if both workflows currently use the same rules.
- Markdown fence and YAML extraction helpers only if behavior is identical.

Targeted tests:

```bash
pytest tests/test_generation_prompts.py tests/test_portfolio.py tests/test_validation.py -q
```

Then run the full verification gate.

Commit message:

```bash
git commit -m "refactor: share ODPS normalization helpers"
```

## Task 3: Split Generation Behind the Existing Facade

Purpose: make `open_data_products.generation` easier to reason about while
preserving all existing imports.

Files:

- Create: `open_data_products/generation/models.py`
- Create: `open_data_products/generation/config.py`
- Create: `open_data_products/generation/prompts.py`
- Create: `open_data_products/generation/providers.py`
- Create: `open_data_products/generation/artifacts.py`
- Modify: `open_data_products/generation/__init__.py`
- Test: `tests/test_generation_prompts.py`
- Test: `tests/test_functional_cli.py`

Approach:

- Move dataclasses to `models.py`.
- Move config template loading, validation, and copy helpers to `config.py`.
- Move prompt listing, loading, rendering, and copy helpers to `prompts.py`.
- Move provider clients and provider client factory to `providers.py`.
- Move artifact workflow functions to `artifacts.py`.
- Keep `generation/__init__.py` as a facade that imports and exposes the same
  public names listed today.

Targeted tests:

```bash
pytest tests/test_generation_prompts.py tests/test_functional_cli.py -q
```

Then run the full verification gate.

Commit message:

```bash
git commit -m "refactor: split generation internals"
```

## Task 4: Split Portfolio Behind the Existing Facade

Purpose: reduce the highest-risk module without changing the public portfolio
API.

Files:

- Create: `open_data_products/portfolio_models.py`
- Create: `open_data_products/portfolio_sources.py`
- Create: `open_data_products/portfolio_workspace.py`
- Create: `open_data_products/portfolio_localization.py`
- Create: `open_data_products/portfolio_rendering.py`
- Create: `open_data_products/portfolio_validation.py`
- Modify: `open_data_products/portfolio.py`
- Test: `tests/test_portfolio.py`
- Test: `tests/test_functional_cli.py`

Approach:

- Keep `portfolio.py` as the public facade for:
  `build_portfolio`, `refresh_portfolio`, `sync_portfolio`,
  `localize_portfolio`, `render_portfolio`, and `explain_portfolio`.
- Move source lane collection, hashing, and change detection first.
- Move workspace loading, writing, version reports, and artifact counts second.
- Move localization prompt parsing and HTML translation third.
- Move HTML rendering last because it has broad snapshot-like behavior.
- Keep each move behavior-preserving and run targeted tests after each internal
  module extraction.

Targeted tests:

```bash
pytest tests/test_portfolio.py tests/test_functional_cli.py -q
```

Then run the full verification gate.

Commit message:

```bash
git commit -m "refactor: split portfolio internals"
```

## Task 5: Modularize CLI Handlers

Purpose: make CLI changes safer while preserving `open-data-products` behavior.

Files:

- Create: `open_data_products/cli_core.py`
- Create: `open_data_products/cli_generation.py`
- Create: `open_data_products/cli_odpc.py`
- Create: `open_data_products/cli_odpg.py`
- Create: `open_data_products/cli_odpv.py`
- Create: `open_data_products/cli_portfolio.py`
- Create: `open_data_products/cli_product.py`
- Modify: `open_data_products/cli.py`
- Test: `tests/test_functional_cli.py`
- Test: `tests/test_agentic_patterns.py`

Approach:

- First extract print helpers and command handlers without changing parser
  construction.
- Then extract parser registration by command family.
- Keep `TOP_LEVEL_HELP` and `main()` in `cli.py`.
- Keep `main(argv: Optional[List[str]] = None) -> int` stable.

Targeted tests:

```bash
pytest tests/test_functional_cli.py tests/test_agentic_patterns.py -q
```

Then run the full verification gate.

Commit message:

```bash
git commit -m "refactor: split CLI command handlers"
```

## Task 6: Reduce Internal Root-Package Coupling

Purpose: make imports clearer without changing public API.

Files:

- Modify: `open_data_products/mcp/tools.py`
- Modify: `open_data_products/summary.py`
- Modify: `open_data_products/portfolio*.py`
- Modify: `open_data_products/cli*.py`
- Modify: `open_data_products/__init__.py` only if needed to preserve exports.

Approach:

- Replace internal imports from `open_data_products` root with concrete module
  imports such as `open_data_products.agent`,
  `open_data_products.contracts`, or spec namespaces.
- Do not remove root exports.
- Do not introduce lazy imports unless import-time behavior becomes a measured
  problem.

Targeted tests:

```bash
pytest tests/test_namespace_layout.py tests/test_functional_mcp.py tests/test_functional_cli.py -q
```

Then run the full verification gate.

Commit message:

```bash
git commit -m "refactor: clarify internal imports"
```

## Task 7: Packaging and Compatibility Review

Purpose: decide what to do with compatibility surfaces without surprising users.

Files:

- Review: `pyproject.toml`
- Review: `README.md`
- Review: `docs/commands.md`
- Review: `docs/development.md`

Approach:

- Keep `open-data-products` as the primary contract.
- Do not remove `open-data-products-odpg-generate` in this refactor unless a
  separate deprecation note and compatibility test are added first.
- Update docs only where internal module paths are mentioned.

Verification:

```bash
pytest tests/test_functional_cli.py tests/test_agentic_patterns.py -q
rm -rf dist build open_data_products.egg-info
PYTHONDONTWRITEBYTECODE=1 python3 -m build
python3 -m twine check dist/*
```

Then run the full verification gate.

Commit message:

```bash
git commit -m "docs: document refactor compatibility posture"
```

## Rollback Strategy

- Each task should be one commit.
- If a task fails the full gate, fix within that task before continuing.
- If a split becomes too broad, stop and reduce scope to a smaller helper group.
- If public behavior changes accidentally, restore the public facade first and
  only then continue with internal cleanup.

## Completion Criteria

This refactor branch is complete only when:

- All public imports covered by tests still work.
- CLI examples used in README and command docs still work.
- MCP manifest renders and parses.
- `pytest -q` passes.
- `python3 -c "import open_data_products"` passes.
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
  passes.
- `test ! -e docs/superpowers` passes.
- `git diff --check` passes.
