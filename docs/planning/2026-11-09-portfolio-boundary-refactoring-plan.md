# Portfolio Boundary Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use inline execution with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Portfolio implementation responsibilities behind the stable `open_data_products.portfolio` public API without changing generated workspace artifacts, CLI/MCP contracts, or validation outcomes.

**Architecture:** `open_data_products/portfolio.py` remains the explicit public facade for the existing typed models and public workflow functions. New underscore-prefixed sibling modules own isolated implementation concerns and must only depend downwards: facade/workflow → prompting, workspace, normalization, and presentation. Existing `portfolio_sources`, `portfolio_budget`, and `portfolio_privacy` remain their current dedicated boundaries.

**Tech Stack:** Python 3.8+, PyYAML, pytest/pytest-cov, existing ODPS/ODPC/ODPG validators, package build and Twine checks.

---

## Scope and non-goals

- Preserve the current public imports from `open_data_products.portfolio` and `open_data_products.__init__`.
- Preserve CLI commands, MCP tool names, workspace layout, YAML/JSON output, and rendered HTML semantics.
- Do not add release features during mechanical extraction. Feature work begins only after the new boundaries are stable.
- Do not create `open_data_products/portfolio/`: it would conflict with the existing public module.
- Do not move the existing source/budget/privacy modules or mix this branch with DCAT/DPROD interoperability changes.

### Task 1: Add refactor characterization guards

**Files:**
- Create: `tests/test_portfolio_refactor_contracts.py`

- [x] **Step 1: Write a public-facade import contract test.**

```python
def test_portfolio_public_facade_keeps_supported_exports() -> None:
    assert inspect.isclass(PortfolioBuildRequest)
    assert inspect.isclass(PortfolioBuildResult)
    assert list(inspect.signature(build_portfolio).parameters) == [
        "workspace", "objectives", "use_cases", "signals", "products", "title",
        "client", "model", "run_kind", "process_all_sources", "context_format",
        "source_budget", "source_privacy",
    ]
    assert callable(refresh_portfolio)
    assert callable(sync_portfolio)
    assert callable(render_portfolio)
```

- [x] **Step 2: Add a workspace rendering contract test using a minimal linked workspace and the existing `tmp_path` fixture.**

```python
_write_render_workspace(workspace)
first = render_portfolio(workspace)
first_html = (workspace / "index.html").read_text(encoding="utf-8")
second = render_portfolio(workspace)

assert first["html"] == str(workspace / "index.html")
assert first_html == (workspace / "index.html").read_text(encoding="utf-8")
assert second["kind"] == "PortfolioRender"
```

- [x] **Step 3: Run the focused test file and confirm the tests pass against the current implementation.**

Run: `pytest -q tests/test_portfolio_refactor_contracts.py`

Expected: all characterization tests pass without production changes.

- [x] **Step 4: Commit the guardrails.**

```bash
git add docs/planning/2026-11-09-portfolio-boundary-refactoring-plan.md tests/test_portfolio_refactor_contracts.py
git commit -m "test: characterize portfolio refactor contracts"
```

### Task 2: Extract typed Portfolio models

**Files:**
- Create: `open_data_products/_portfolio_models.py`
- Modify: `open_data_products/portfolio.py`
- Modify: `tests/test_portfolio_refactor_contracts.py`

- [x] **Step 1: Write the failing facade-boundary test.**

```python
def test_portfolio_facade_reexports_models_from_private_module() -> None:
    source = Path("open_data_products/portfolio.py").read_text(encoding="utf-8")
    assert "from ._portfolio_models import" in source
    assert "class PortfolioBuildRequest" not in source
```

- [x] **Step 2: Run the test and confirm it fails before the move.**

Run: `pytest -q tests/test_portfolio_refactor_contracts.py::test_portfolio_facade_reexports_models_from_private_module`

Expected: FAIL because models still live in `portfolio.py`.

- [x] **Step 3: Move the source-lane, build-request, and build-result dataclasses plus client aliases to `_portfolio_models.py`; explicitly import them from the facade.**

```python
from ._portfolio_models import (
    PortfolioBuildClient,
    PortfolioBuildRequest,
    PortfolioBuildResult,
    PortfolioLocalizationClient,
    PortfolioSourceLanes,
)
```

- [x] **Step 4: Run the focused contracts and Portfolio regression suite.**

Run: `pytest -q tests/test_portfolio_refactor_contracts.py tests/test_portfolio.py tests/test_portfolio_odps_v42.py tests/test_portfolio_fragment_deduplication.py`

Expected: PASS.

- [x] **Step 5: Commit the models extraction.**

```bash
git add open_data_products/_portfolio_models.py open_data_products/portfolio.py tests/test_portfolio_refactor_contracts.py docs/planning/2026-11-09-portfolio-boundary-refactoring-plan.md
git commit -m "refactor: isolate portfolio models"
```

### Task 3: Extract presentation rendering without changing output

**Files:**
- Create: `open_data_products/_portfolio_html.py`
- Create: `open_data_products/_portfolio_assets.py`
- Modify: `open_data_products/portfolio.py`
- Modify: `tests/test_portfolio_refactor_contracts.py`

- [ ] **Step 1: Write a failing source-boundary test.**

```python
def test_portfolio_facade_delegates_html_rendering() -> None:
    source = Path("open_data_products/portfolio.py").read_text(encoding="utf-8")
    assert "from ._portfolio_html import render_portfolio_html" in source
    assert "def _portfolio_css" not in source
```

- [ ] **Step 2: Run the test and confirm it fails because the renderer remains in the facade.**

Run: `pytest -q tests/test_portfolio_refactor_contracts.py::test_portfolio_facade_delegates_html_rendering`

Expected: FAIL with the missing import or retained CSS helper.

- [ ] **Step 3: Move `render_portfolio_html` and all renderer-only helpers to `_portfolio_html.py`; move `_portfolio_css` and `_portfolio_js` to `_portfolio_assets.py`.**

```python
# open_data_products/portfolio.py
from ._portfolio_html import render_portfolio_html
```

Keep all generated markup byte-for-byte stable. Do not change labels, CSS, JavaScript, or rendering rules in this task.

- [ ] **Step 4: Run the focused contract and renderer tests.**

Run: `pytest -q tests/test_portfolio_refactor_contracts.py tests/test_portfolio.py -k 'render or localize or refactor_contracts'`

Expected: PASS.

- [ ] **Step 5: Commit the presentation extraction.**

```bash
git add open_data_products/portfolio.py open_data_products/_portfolio_html.py open_data_products/_portfolio_assets.py tests/test_portfolio_refactor_contracts.py
git commit -m "refactor: isolate portfolio presentation"
```

### Task 4: Extract ODPS output normalization

**Files:**
- Create: `open_data_products/_portfolio_normalization.py`
- Modify: `open_data_products/portfolio.py`
- Modify: `tests/test_portfolio_odps_v42.py`
- Modify: `tests/test_portfolio_refactor_contracts.py`

- [ ] **Step 1: Write a failing boundary test for a delegated normalizer.**

```python
def test_portfolio_facade_delegates_odps_normalization() -> None:
    source = Path("open_data_products/portfolio.py").read_text(encoding="utf-8")
    assert "from ._portfolio_normalization import normalize_odps_product" in source
```

- [ ] **Step 2: Run the boundary test and confirm it fails.**

Run: `pytest -q tests/test_portfolio_refactor_contracts.py::test_portfolio_facade_delegates_odps_normalization`

Expected: FAIL because the normalizer has not been extracted.

- [ ] **Step 3: Move only ODPS normalization helpers and constants to `_portfolio_normalization.py`; keep a private compatibility wrapper in the facade until direct private test imports are updated.**

```python
# open_data_products/portfolio.py
from ._portfolio_normalization import normalize_odps_product

def _normalize_odps_product(document: Dict[str, Any]) -> None:
    normalize_odps_product(document)
```

Preserve ODPS 4.1 and 4.2 output shapes and external `$ref` behavior.

- [ ] **Step 4: Run normalization, sync, and build tests.**

Run: `pytest -q tests/test_portfolio_odps_v42.py tests/test_portfolio.py -k 'normaliz or sync or build'`

Expected: PASS.

- [ ] **Step 5: Commit the normalization extraction.**

```bash
git add open_data_products/portfolio.py open_data_products/_portfolio_normalization.py tests/test_portfolio_odps_v42.py tests/test_portfolio_refactor_contracts.py
git commit -m "refactor: isolate portfolio ODPS normalization"
```

### Task 5: Extract workspace persistence and validation

**Files:**
- Create: `open_data_products/_portfolio_workspace.py`
- Modify: `open_data_products/portfolio.py`
- Modify: `tests/test_portfolio_refactor_contracts.py`

- [ ] **Step 1: Write failing tests for the facade boundary and file-layout preservation.**

```python
def test_portfolio_facade_delegates_workspace_loading() -> None:
    source = Path("open_data_products/portfolio.py").read_text(encoding="utf-8")
    assert "from ._portfolio_workspace import load_portfolio_workspace" in source

def test_refactor_preserves_workspace_artifact_paths(tmp_path: Path) -> None:
    result = sync_portfolio(tmp_path)
    assert result["html"].endswith("index.html")
```

- [ ] **Step 2: Run the tests and confirm the facade-boundary test fails.**

Run: `pytest -q tests/test_portfolio_refactor_contracts.py -k 'workspace'`

Expected: FAIL for the missing delegated import before production changes.

- [ ] **Step 3: Move workspace load, validation aggregation, artifact file helpers, version discovery, and i18n persistence to `_portfolio_workspace.py`.**

Keep public `load_portfolio_workspace` behavior available through the facade if callers require it. Keep filesystem paths internal to MCP responses through the existing adapter layer.

- [ ] **Step 4: Run focused workflow tests.**

Run: `pytest -q tests/test_portfolio.py -k 'sync or refresh or explain or localize'`

Expected: PASS.

- [ ] **Step 5: Commit the workspace extraction.**

```bash
git add open_data_products/portfolio.py open_data_products/_portfolio_workspace.py tests/test_portfolio_refactor_contracts.py
git commit -m "refactor: isolate portfolio workspace operations"
```

### Task 6: Reduce the facade to workflow orchestration

**Files:**
- Create: `open_data_products/_portfolio_workflow.py`
- Create: `open_data_products/_portfolio_prompting.py`
- Modify: `open_data_products/portfolio.py`
- Modify: `tests/test_portfolio_refactor_contracts.py`

- [ ] **Step 1: Write failing tests proving public facade functions retain their legacy call signatures and delegate to the workflow module.**

```python
def test_portfolio_facade_exports_workflow_functions() -> None:
    signature = inspect.signature(portfolio.build_portfolio)
    assert list(signature.parameters)[:1] == ["workspace"]
    assert callable(portfolio.refresh_portfolio)
```

- [ ] **Step 2: Run the new test, confirm the delegation assertion fails, then extract prompt parsing and orchestration.**

Run: `pytest -q tests/test_portfolio_refactor_contracts.py::test_portfolio_facade_exports_workflow_functions`

Expected: FAIL before adding the explicit facade delegation assertion; PASS after the extraction.

- [ ] **Step 3: Move prompt rendering/parsing to `_portfolio_prompting.py` and build/refresh orchestration internals to `_portfolio_workflow.py`; keep dataclasses and public wrappers in `portfolio.py`.**

```python
# open_data_products/portfolio.py
def build_portfolio(workspace: Union[str, Path], **kwargs: object) -> Dict[str, object]:
    return _build_portfolio(workspace, **kwargs)
```

Use explicit typed wrapper signatures rather than `**kwargs` in the final implementation.

- [ ] **Step 4: Run the full project verification.**

Run: `pytest -q && python3 -c "import open_data_products" && python3 -m open_data_products.cli manifest --json | python3 -m json.tool > /dev/null && python3 -m build --quiet && python3 -m twine check dist/*`

Expected: all commands succeed.

- [ ] **Step 5: Commit the completed Portfolio boundary refactor.**

```bash
git add open_data_products/portfolio.py open_data_products/_portfolio_workflow.py open_data_products/_portfolio_prompting.py tests/test_portfolio_refactor_contracts.py
git commit -m "refactor: reduce portfolio facade to public workflow API"
```

### Task 7: Add release features only after the refactor stabilizes

**Files:**
- To be selected from the approved 0.7.0 feature specification.

- [ ] **Step 1: Convert each approved feature into a separate implementation plan and failing public behavior test.**

Do not add a feature until its required input/output contract and owning module are identified.

- [ ] **Step 2: Implement one feature per commit and run its focused tests followed by the full suite.**

```bash
pytest -q tests/test_<feature>.py
pytest -q
```

- [ ] **Step 3: Perform release-candidate hardening after all approved features land.**

```bash
python3 -m build --quiet
python3 -m twine check dist/*
pytest -q
```

## Plan self-review

- Scope coverage: Tasks 1-5 protect and isolate every currently combined Portfolio responsibility; Task 6 deliberately defers unapproved features.
- No `docs/superpowers/` path is used because repository rules forbid it.
- The facade, public imports, CLI/MCP behavior, and artifact layout are explicit preservation constraints in every extraction task.
