# DPROD 1.0 Beta 2 Interoperability Implementation Plan

> **For agentic workers:** execute this plan task-by-task with tests before production code. The repository forbids the otherwise-default `docs/superpowers/` location.

**Goal:** Add offline, normative DPROD 1.0 Beta 2 ingestion, validation, conversion, export, and catalog intelligence to the existing SDK.

**Architecture:** A focused `open_data_products.dprod` package owns pinned normative assets, namespace detection, SHACL validation, and DPROD/ODPS mappings. It reuses the DCAT safe loader and ODPS schema-validation path rather than building another RDF or product-conversion stack. DCAT inventory gains only explicit DPROD facts; inferred dataset opportunities remain separate.

**Tech Stack:** Python 3.8+, RDFLib, pySHACL, bundled Turtle assets, JSON/YAML, pytest.

---

### Task 1: Pin the normative profile and safe validation boundary

**Files:**
- Create: `open_data_products/dprod/__init__.py`, `open_data_products/dprod/models.py`, `open_data_products/dprod/validation.py`
- Create: `open_data_products/dprod/data/dprod-ontology.ttl`, `open_data_products/dprod/data/dprod-shapes.ttl`, `open_data_products/dprod/data/registry.json`
- Modify: `pyproject.toml`, `requirements.txt`
- Test: `tests/test_dprod.py`

- [ ] Write a test that valid Beta 2 Turtle conforms, malformed RDF is distinct from SHACL failure, and the development namespace is rejected.
- [ ] Run `pytest tests/test_dprod.py -q`; expect import failure before the DPROD API exists.
- [ ] Bundle the downloaded OMG artifacts with SHA-256 provenance and implement `validate_dprod` using local shapes only, disabling imports and remote JSON-LD contexts.
- [ ] Re-run the focused tests; expect all validation-boundary cases to pass.

### Task 2: Build the DPROD inventory and DPROD-to-ODPS draft path

**Files:**
- Create: `open_data_products/dprod/catalog.py`, `open_data_products/dprod/mapping.py`
- Modify: `open_data_products/dcat/catalog.py`, `open_data_products/dcat/models.py`, `open_data_products/dcat/__init__.py`, `open_data_products/__init__.py`
- Test: `tests/test_dprod.py`, `tests/test_dcat_catalog.py`

- [ ] Write tests proving a DPROD product remains explicit, preserves ports/owners/datasets/services/policies, and produces a valid ODPS 4.2 draft with documented warnings.
- [ ] Run those tests; expect missing APIs.
- [ ] Implement deterministic DPROD ingestion/mapping, reuse the DCAT source loader, and extend the DCAT report model without reclassifying ordinary datasets as products.
- [ ] Re-run the focused tests; expect a schema-valid draft and an exact/conditional/partial/unsupported mapping report.

### Task 3: Add deterministic ODPS-to-DPROD export

**Files:**
- Modify: `open_data_products/dprod/mapping.py`, `open_data_products/dprod/models.py`
- Test: `tests/test_dprod.py`

- [ ] Write tests for reproducible Turtle and JSON-LD export, deterministic generated IRIs, SHACL validation, and explicit loss records for unsupported ODPS fields.
- [ ] Run the tests; expect failure because no exporter exists.
- [ ] Implement `export_odps_to_dprod` using the actual ODPS 4.2 document fields and validate its graph locally.
- [ ] Re-run the tests; expect exported artifacts to be byte-stable and SHACL-valid.

### Task 4: Connect API, CLI, MCP, and manifests

**Files:**
- Modify: `open_data_products/cli.py`, `open_data_products/cli_product.py`, `open_data_products/mcp/tools.py`, `open_data_products/mcp/manifest.py`, `tests/test_agentic_patterns.py`, `tests/test_functional_mcp.py`
- Test: `tests/test_dprod.py`, `tests/test_functional_mcp.py`, `tests/test_agentic_patterns.py`

- [ ] Write API/CLI/MCP tests for safe discovery/validation and state-changing write operations, including path redaction.
- [ ] Run them; expect unsupported command/tool names.
- [ ] Add `portfolio discover-dprod`, `product wrap-dprod`, `product export-dprod`, and equivalent MCP tools with correct safety classes.
- [ ] Re-run the tests; expect consistent structured output across interfaces.

### Task 5: Release documentation and regression evidence

**Files:**
- Create: `docs/user/dprod-interoperability.md`, `CHANGELOG.md`
- Modify: `README.md`, `llms.txt`, `docs/README.md`, `RELEASE_SUMMARY.md`
- Test: `tests/test_namespace_layout.py`

- [ ] Document Beta 2 status, normative namespace, accepted formats, offline validation, mapping/loss boundaries, and non-normative development repository status.
- [ ] Update the v0.7.0 release notes without claiming equivalence or publication.
- [ ] Run focused documentation/layout tests, then `pytest -q`, import, manifest JSON, build, and twine checks.
