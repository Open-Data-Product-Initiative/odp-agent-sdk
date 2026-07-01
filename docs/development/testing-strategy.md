# Testing Strategy

This SDK uses deterministic local tests as the default confidence gate. Tests
should exercise public behavior through Python APIs, CLI commands, and MCP
handlers without requiring live providers, external services, or persistent
local filesystem state.

## Baseline Checks

Run these before marking work complete:

```powershell
python -m pytest -q
python -c "import open_data_products"
python -m open_data_products.cli manifest --json | python -m json.tool
Test-Path docs/superpowers
```

`docs/superpowers` should be absent. That path is reserved for deleted legacy
planning artifacts and must not be recreated.

Use `python -m pytest` on Windows when the `pytest.exe` launcher is blocked by
application control policy.

## Test Scope

Use the narrowest focused test first, then run the full suite:

- Core spec behavior: `tests/test_core.py`, `tests/test_odpc.py`,
  `tests/test_odpg.py`, `tests/test_odpv.py`, and `tests/test_validation.py`.
- Public agent surface: `tests/test_agent_api.py`,
  `tests/test_functional_agent_api.py`, and `tests/test_agentic_patterns.py`.
- CLI behavior: `tests/test_functional_cli.py`.
- MCP behavior: `tests/test_mcp.py`, `tests/test_functional_mcp.py`, and
  `tests/test_agentic_patterns.py`.
- Generation behavior: `tests/test_generation_prompts.py`.
- Portfolio behavior: `tests/test_portfolio.py`.
- Recipe workflow behavior: `tests/test_recipes.py`.

When a change crosses boundaries, run each affected area plus the full suite.
For example, portfolio command changes usually need `tests/test_portfolio.py`,
relevant `tests/test_functional_cli.py` cases, and portfolio-filtered recipe
tests.

## Portfolio Intake Regression Fixtures

Portfolio document intake has three ZIP-backed regression fixtures under
`tests/`:

- `intake-test-1.zip`: mixed file type detection, skipped Outlook/image inputs,
  text PDF extraction, renamed Office files, lane assignment, and warnings.
- `intake-test-2.zip`: long content, deterministic source reduction, prompt
  budget reports, privacy obfuscation, and many small source files.
- `intake-test-3.zip`: encoding edge cases, control characters, duplicate file
  names across lanes, nested files, corrupt Office containers, and skipped
  image-only or protected PDFs.

These fixtures are wired into `tests/test_portfolio.py` through:

- `test_portfolio_intake_zip_fixture_matches_embedded_expectations`
- `test_portfolio_long_content_zip_fixture_matches_embedded_expectations`
- `test_portfolio_edge_case_zip_fixture_matches_embedded_expectations`

Run the focused ZIP-backed regression set with:

```powershell
python -m pytest tests/test_portfolio.py -q `
  -k "intake_zip_fixture or long_content_zip_fixture or edge_case_zip_fixture"
```

Run the broader intake and source-helper sweep with:

```powershell
$filter = "portfolio_source_helpers or inspect_portfolio_intake or " + `
  "portfolio_intake or cli_intake or intake"
python -m pytest tests/test_portfolio.py tests/test_functional_cli.py -q `
  -k $filter
```

The portfolio intake command must remain inspection-only: fixture-backed intake
checks should report `llmCallCount` as `0`.

## Portfolio Workflow Regression

Portfolio changes should not stop at intake tests. The full portfolio workflow
suite covers build, refresh, sync, localize, render, explain, validation modes,
prompt budget gates, privacy obfuscation, malformed YAML repair, workspace
reruns, and generated HTML behavior.

Use:

```powershell
python -m pytest tests/test_portfolio.py -q
python -m pytest tests/test_recipes.py -q -k "portfolio"
```

Then run `python -m pytest -q`.

## Fixture Rules

- Use `tmp_path` fixtures for generated files and workspaces.
- Keep regression inputs local, deterministic, and small enough for normal test
  runs.
- Do not call live LLM providers, network APIs, databases, or external service
  CLIs in default tests.
- Prefer generated fixture files inside tests unless a realistic binary fixture
  is needed to pin parser behavior.
- When using ZIP fixtures, store expectations inside the fixture or assert
  stable behavior directly in tests.

## Adding Or Changing Behavior

Add or update tests with the behavior change. When fixing a bug, add the
smallest regression that fails before the fix and passes after it.

When changing public API, CLI JSON shape, MCP tool metadata, report fields, or
generated artifacts, update the tests that pin that contract. Do not rename
fields or change generated HTML/YAML/JSON in a refactor-only patch unless a test
already requires that change.
