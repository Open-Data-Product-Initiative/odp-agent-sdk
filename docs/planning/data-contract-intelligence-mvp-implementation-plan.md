# Data Contract Intelligence MVP Implementation Plan

> **For agentic workers:** Use test-first implementation. This plan remains in `docs/planning/` because this repository reserves `docs/superpowers/`.

**Goal:** Turn ODCS repository discovery into evidence-led contract intelligence that remains useful when no product group is proposed.

**Architecture:** Extend the existing contracts discovery facade and result models; retain inventory and relationship records, add normalized intelligence findings and summary counts, and derive product candidates only from qualifying relationship rules. Render one self-contained light HTML report from the same result object. Existing Python, CLI, and MCP entry points continue to delegate to the facade unchanged.

**Tech Stack:** Python 3.8+, dataclasses, existing YAML/JSON loaders, argparse, self-contained HTML/CSS/JavaScript, pytest.

---

### Task 1: Add normalized intelligence findings

**Files:**
- Modify: `tests/test_contract_discovery.py`
- Modify: `open_data_products/contracts/models.py`
- Modify: `open_data_products/contracts/discovery.py`

- [ ] Write failing tests that assert metadata gaps reference their source contract, duplicate evidence is a reuse finding, and exact duplicates are not product candidates.
- [ ] Run `pytest -q tests/test_contract_discovery.py -k 'gap or duplicate'` and confirm failure.
- [ ] Add `IntelligenceFinding`, inventory lifecycle/purpose/tags metadata, deterministic gap extraction, and an intelligence summary. Limit product candidates to grouping rules, never reuse/duplicate findings.
- [ ] Run the focused tests and commit `feat: add contract intelligence findings`.

### Task 2: Write structured intelligence artifacts

**Files:**
- Modify: `tests/test_contract_discovery.py`
- Modify: `open_data_products/contracts/discovery.py`

- [ ] Write a failing test for `contract-intelligence.json`, including summary counts and source-linked findings with no raw document body.
- [ ] Run the focused test and confirm failure.
- [ ] Emit the JSON artifact and expose its logical artifact ID while preserving `contract-inventory.json` and `product-candidates.json`.
- [ ] Run the focused tests and commit `feat: write contract intelligence artifact`.

### Task 3: Replace the HTML report with a usable offline explorer

**Files:**
- Modify: `tests/test_contract_discovery.py`
- Modify: `open_data_products/contracts/discovery.py`

- [ ] Write failing tests for a light branded Overview, searchable Contract Intelligence Explorer, evidence anchors, and a zero-candidate Product Opportunities state.
- [ ] Run the focused test and confirm failure.
- [ ] Render self-contained CSS and JavaScript with the three requested sections. Use only escaped content and internal anchors; no CDN, framework, service, or raw contract body.
- [ ] Run the full suite, import check, manifest JSON check, and a 146-contract report generation check. Commit `feat: render data contract intelligence report`.
