# AGENTS.md

Instruction file for AI coding agents (Claude Code, Codex, Cursor, Gemini)
working in this repository. Authoritative project conventions; precedence over
generic defaults.

## Project

Python SDK + MCP surface for the OpenDataProducts.org standards family
(ODPS, ODPC, ODPG, ODPV). Single package: `open_data_products`.

## Stack

- Python ≥ 3.8 (tested through 3.12; CI runs on 3.14)
- Runtime deps: `PyYAML`, `certifi`, `jsonschema`, `pycountry`, `phonenumbers`
- Dev deps: `pytest`, `pytest-cov`, `black`, `flake8`, `mypy`, `build`, `twine`
- No web framework, no DB, no async runtime.

## Style

- 4-space indent. Black with `line-length = 88`. No `any` in type hints.
- Public API surface lives in `open_data_products/__init__.py` — list new
  exports there explicitly; do not rely on barrel re-exports.
- Per-spec helpers live under `open_data_products/<spec>/`. Cross-spec
  facades live at the package root (`agent.py`, `cli.py`, `summary.py`,
  `pricing.py`, `mcp/`).
- Internal-only modules use a leading `_` prefix; do not export them.
- Docstrings: one-line summary, optional short body. No paragraph essays.

## Structure

```
open_data_products/
  __init__.py          # public API surface
  agent.py             # cross-spec load/detect/validate/explain/refs
  cli.py               # `open-data-products` console script
  summary.py           # load_summary — artifact references (no body)
  pricing.py           # ODPS PricingPlans → HTTP 402 envelope
  resources.py         # bundled resource registry
  results.py           # ValidationResult, Reference, Resource dataclasses
  mcp/
    tools.py           # MCP tool registry (data + handlers)
    manifest.py        # ARWS agent manifest
    server.py          # stdio JSON-RPC 2.0 MCP server
  odps/                # spec-specific package
  odpc/  odpg/  odpv/
skills/                # SKILL.md bundles for agent hosts
tests/
```

New code goes in the smallest existing module that fits its spec namespace.
Do not introduce parallel `validation.py` / `validators.py` style splits;
that confusion already exists and should be merged, not extended.

## Testing

- `pytest -q` from repo root. Target: 100% green.
- New behaviour requires a test in `tests/test_<area>.py`.
- Conformance to agenticpatterns.veso.ai prescriptions is enforced by
  `tests/test_agentic_patterns.py`. Treat that file as the spec — when
  changing the agent surface, update the test first, watch it fail, then
  implement.
- Use `tmp_path` fixtures, not real filesystem state.

## Git

- Branch: `feat/<short-description>`, `fix/<short-description>`, etc.
- Commit messages: imperative, one logical change per commit.
- One PR per concern. Don't bundle a refactor with a feature.
- Never `--amend` after pushing. Never `git push --force` to `main`.

## Security

- No hardcoded secrets in source or fixtures. The SDK has no credential
  surface today; if you add one, read from env vars and document it here.
- The MCP server is `safe`-class only today (read-only). When you add a
  `state-changing` or `destructive` tool, set the `class` field in
  `mcp/tools.py` accordingly and update `tests/test_agentic_patterns.py`.
- Bundled JSON Schemas are loaded with `jsonschema`'s default checker.
  Do not load arbitrary remote schemas at validate time.

## Pre-Commit Checklist

Before marking work complete, run all four:

1. `pytest -q` — all tests pass
2. `python -c "import open_data_products"` — package imports cleanly
3. `python -m open_data_products.cli manifest --json | python -m json.tool`
   — manifest renders and parses
4. No new files in `docs/superpowers/` (that path is reserved for legacy
   AI-planning artifacts already deleted; do not recreate)

## Anti-patterns to avoid

- Returning full document bodies from MCP handlers — use `load_summary`
  for references; only load full docs when validation/explanation needs them
- Adding console_script entry points beyond `open-data-products` — the
  unified subcommand CLI is the contract
- Importing from `open_data_products.odps.codecs` in user-facing code —
  that module is internal glue between models and YAML/JSON
- Storing absolute filesystem paths in tool responses — return logical IDs
  and let the resource registry resolve them
