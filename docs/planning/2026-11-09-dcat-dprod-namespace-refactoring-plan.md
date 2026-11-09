# DCAT and DPROD Namespace Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove DPROD's dependency on DCAT private helpers and isolate DCAT/DPROD transport wiring without changing public Python, CLI, or MCP contracts.

**Architecture:** A private `_interop` package owns safe RDF input and neutral source-to-ODPS draft mechanics. DCAT and DPROD adapt their own models to that contract. The existing CLI/MCP entrypoints remain public aggregators while the interop command and handler implementations move into domain-focused modules.

**Tech Stack:** Python 3.8+, RDFLib, PySHACL, pytest, argparse, stdio JSON-RPC.

---

### Task 1: Establish private interoperability boundaries

**Files:**
- Create: `open_data_products/_interop/__init__.py`
- Create: `open_data_products/_interop/rdf.py`
- Create: `open_data_products/_interop/odps_draft.py`
- Modify: `open_data_products/dcat/catalog.py`
- Modify: `open_data_products/dprod/catalog.py`
- Modify: `open_data_products/dprod/validation.py`
- Test: `tests/test_namespace_layout.py`

- [x] **Step 1: Write failing import-boundary tests**

```python
def test_dprod_namespace_does_not_import_dcat_implementation() -> None:
    imports = _imports_for(REPO_ROOT / "open_data_products" / "dprod")
    assert "open_data_products.dcat.catalog" not in imports
```

- [x] **Step 2: Run the boundary test**

Run: `pytest -q tests/test_namespace_layout.py::test_dprod_namespace_does_not_import_dcat_implementation`
Expected: FAIL because DPROD imports `dcat.catalog` private helpers.

- [x] **Step 3: Move neutral mechanics**

Create private, typed `_interop.rdf` functions for bounded RDF loading, safe HTTP URLs, JSON-LD context rejection, and RDF parser selection. Create `_interop.odps_draft` dataclasses plus a draft builder that accepts only neutral resource and distribution data. DCAT and DPROD adapt their own facts to these internal contracts.

- [x] **Step 4: Run boundary and regression tests**

Run: `pytest -q tests/test_namespace_layout.py tests/test_dcat_catalog.py tests/test_dprod.py`
Expected: PASS with unchanged public results.

### Task 2: Isolate MCP interoperability handlers

**Files:**
- Create: `open_data_products/mcp/_response.py`
- Create: `open_data_products/mcp/interop.py`
- Modify: `open_data_products/mcp/tools.py`
- Test: `tests/test_functional_dcat_dprod.py`
- Test: `tests/test_namespace_layout.py`

- [x] **Step 1: Write failing structural tests**

```python
def test_mcp_tool_registry_imports_interop_handlers_from_domain_module() -> None:
    source = (REPO_ROOT / "open_data_products" / "mcp" / "tools.py").read_text()
    assert "from .interop import" in source
```

- [x] **Step 2: Run the structural test**

Run: `pytest -q tests/test_namespace_layout.py::test_mcp_tool_registry_imports_interop_handlers_from_domain_module`
Expected: FAIL because `tools.py` owns DCAT/DPROD handlers and response redaction.

- [x] **Step 3: Move only interop handlers and response helpers**

Move JSON envelope and local-path redaction helpers to `_response.py`. Move the six DCAT/DPROD MCP handlers to `interop.py`; retain all tool names, schemas, classifications, and response fields in `tools.py`.

- [x] **Step 4: Run functional MCP coverage**

Run: `pytest -q tests/test_functional_dcat_dprod.py tests/test_functional_mcp.py tests/test_agentic_patterns.py`
Expected: PASS with no local paths in responses.

### Task 3: Isolate CLI interoperability registration and execution

**Files:**
- Create: `open_data_products/cli_interop.py`
- Modify: `open_data_products/cli.py`
- Test: `tests/test_functional_dcat_dprod.py`
- Test: `tests/test_namespace_layout.py`

- [x] **Step 1: Write failing structural test**

```python
def test_cli_delegates_dcat_and_dprod_commands_to_interop_module() -> None:
    source = (REPO_ROOT / "open_data_products" / "cli.py").read_text()
    assert "from .cli_interop import" in source
```

- [x] **Step 2: Run the structural test**

Run: `pytest -q tests/test_namespace_layout.py::test_cli_delegates_dcat_and_dprod_commands_to_interop_module`
Expected: FAIL because the root CLI owns DCAT/DPROD parser and execution branches.

- [x] **Step 3: Move interop parser and execution functions**

Move `dprod-validate`, `portfolio discover-dcat`, and `portfolio discover-dprod` parser construction and execution into `cli_interop.py`. The root CLI supplies its existing activity finalizer and remains responsible for global parsing and telemetry.

- [x] **Step 4: Run CLI and package regression tests**

Run: `pytest -q tests/test_functional_dcat_dprod.py tests/test_dcat_catalog.py tests/test_dprod.py tests/test_functional_cli.py`
Expected: PASS with unchanged command names, exit codes, JSON payloads, and artifacts.

### Task 4: Verify refactoring boundaries and release gates

**Files:**
- Modify: `docs/reports/functional-test-report.md`
- Test: `tests/test_functional_report.py`

- [x] **Step 1: Update report evidence**

Document the private interoperability boundary and retained public API/CLI/MCP contracts without overstating external-standard conformance.

- [x] **Step 2: Run complete verification**

Run: `pytest -q && python3 -c "import open_data_products" && python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
Expected: zero test failures, clean import, and valid manifest JSON.

- [x] **Step 3: Inspect the scoped diff and commit**

Run: `git diff --check && git status --short`
Expected: only the refactoring, tests, and report files listed above.
