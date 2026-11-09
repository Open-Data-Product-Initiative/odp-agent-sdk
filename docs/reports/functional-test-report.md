# Functional Test Report

This report describes the functional test layer for the Open Data Products
Python SDK. The goal is to test the SDK as agents and users consume it: through
public APIs, CLI commands, and the MCP JSON-RPC surface.

## How To Run

```bash
pytest -q -m functional
pytest -q
```

## Functional Suites

| Suite | Surface | What It Proves |
|-------|---------|----------------|
| `tests/test_functional_agent_api.py` | Public Python API | `load_document`, `detect_document`, `validate_document`, `explain_document`, `resolve_references`, `load_summary`, and `list_resources` work across ODPS, ODPC, ODPG, and ODPV fixtures. |
| `tests/test_functional_agent_api.py` | Data Contract orchestration | Contract APIs resolve native ODPS `/product/contract/spec`, validate optional-adapter missing paths, summarize and extract schemas, check alignment, and generate reports. |
| `tests/test_functional_cli.py` | Unified CLI | User-facing commands return successful exit codes and parseable JSON for document validation, explanation, summary, resources, manifest, ODPG reasoning workflows, and product-level Data Contract workflows. |
| `tests/test_functional_mcp.py` | MCP JSON-RPC | The MCP handler initializes, lists tools, calls every registered safe tool with representative inputs, including Data Contract tools, and reports unknown tools through JSON-RPC errors. |
| `tests/test_dcat_catalog.py` | DCAT catalogue regression suite | DCAT catalog discovery, multilingual facts, selected-resource wrapping, AI proposal boundaries, RDF syntax safety, duplicate-resource evidence, and bounded redirects run in the functional selection. |
| `tests/test_dprod.py` | DPROD interoperability regression suite | Pinned-profile validation, artifact integrity, namespace/context safety, inventory, wrapping, deterministic export, and public-surface identity boundaries run in the functional selection. |
| `tests/test_functional_dcat_dprod.py` | DCAT catalog intelligence and DPROD 1.0 Beta 2 interoperability | Versioned RDF fixtures exercise public API, CLI, and MCP discovery, wrapping, validation, and export workflows, including state-changing output selection and path redaction. |
| `tests/test_functional_report.py` | Documentation guard | This report mentions the functional suites, covered surfaces, and run command. |

## Coverage Matrix

| Capability | API | CLI | MCP |
|------------|-----|-----|-----|
| Load/detect documents | Covered | Indirect | Indirect |
| Validate documents | Covered | Covered | Covered |
| Explain documents | Covered | Covered | Covered |
| Resolve references | Covered | Not yet direct | Covered |
| Lightweight summaries | Covered | Covered | Covered |
| Resource registry | Covered | Covered | Covered |
| ODPC catalog build | Covered | Covered | Not mapped; MCP avoids full generated catalog bodies |
| ODPV search | Not yet direct | Not yet direct | Covered |
| ODPC object search | Not yet direct | Not yet direct | Covered |
| ODPG object search | Not yet direct | Not yet direct | Covered |
| ODPG summary | Covered through spec fixture | Covered | Covered |
| ODPG traversal | Not yet direct | Covered | Covered |
| ODPG analysis | Not yet direct | Covered | Covered |
| ODPG agent context | Not yet direct | Covered | Covered |
| ODPG external graph conversion | Covered | Covered | Not mapped; conversion writes generated YAML |
| Resolve product contracts | Covered | Covered | Covered |
| Validate Data Contracts | Covered missing optional adapter | Covered through check-contract/report/alignment | Covered |
| Summarize Data Contracts | Covered | Covered through contract-report | Covered |
| Extract contract schema | Covered | Covered | Covered |
| Product-contract alignment | Covered | Covered | Covered |
| Product contract report | Covered | Covered | Covered |
| Product contract risk summary | Not yet direct | Covered through audit findings | Covered |
| DCAT catalog discovery | Covered | Covered | Covered |
| DCAT selected-resource ODPS draft | Covered | Covered | Covered state-changing tool |
| DCAT HTML intelligence report | Not applicable | Covered | Not mapped; MCP intentionally returns metadata only |
| DPROD Beta 2 SHACL validation | Covered | Covered | Covered |
| DPROD explicit product inventory | Covered | Covered | Covered |
| DPROD selected-product ODPS draft | Covered | Covered | Covered state-changing tool |
| ODPS-to-DPROD Turtle and JSON-LD export | Covered | Covered | Covered state-changing tool |
| MCP initialize/list tools | Not applicable | Not applicable | Covered |

## Fixture Strategy

The functional layer uses real package and example artifacts where practical:

- ODPS: `examples/apps/pricing_402_builder/priced_product.yaml`
- ODPC: a minimal temporary catalog fixture
- ODPG: `open_data_products/odpg/data/graph/graph.yaml`
- ODPV: `open_data_products/odpv/data/vocab/odpv.yaml`
- Data Contracts: temporary ODPS products with native inline
  `/product/contract/spec` plus temporary local Data Contract YAML files
- DCAT: `tests/fixtures/dcat-dprod/valid-catalog.ttl`, a self-contained
  catalog with a single selected Dataset and Distribution
- DPROD: `tests/fixtures/dcat-dprod/valid-product.ttl`, a self-contained
  DPROD 1.0 Beta 2 compatibility fixture with product, datasets, services,
  owner, policy, and ports
- Negative DCAT/DPROD: `unsafe-remote-context.jsonld` and `invalid-owner.ttl`
  prove that remote JSON-LD contexts are rejected and SHACL-invalid product
  sources cannot be wrapped

The temporary ODPC fixture keeps the suite independent from a larger catalog
example while still exercising the public loader, detector, validator, explainer,
and summary behavior.

The temporary Data Contract fixtures avoid requiring `datacontract-cli` to be
installed. Missing optional-adapter behavior is asserted explicitly, while
static SDK-owned extraction, alignment, report, CLI, and MCP behavior is tested
end to end.

Contract API and MCP workflows covered include `resolve_product_contracts`,
`validate_contract`, `summarize_contract`, `extract_contract_schema`,
`check_product_contract_alignment`, and `generate_product_contract_report`.

## DCAT and DPROD Release Evidence

The DCAT/DPROD functional suite executes the public Python API, unified CLI,
and MCP JSON-RPC surfaces against the same versioned fixtures. It verifies
that state-changing MCP operations write only the requested output and redact
local paths from their response bodies.

The packaging CI additionally runs an `installed-wheel` smoke test outside the
checkout and runs an ODPS-to-DPROD export using the packaged profile assets. It then
cross-checks that export with Apache Jena SHACL after verifying the downloaded
Jena archive checksum. This is an independent-engine CI gate for outbound
DPROD RDF; it does not claim DCAT SHACL conformance because the SDK does not
bundle a pinned DCAT application-profile shape set.

## Current Intentional Gaps

The current functional layer is the first cross-surface pass. Useful follow-up
coverage would be:

- Direct CLI tests for `refs` and spec-specific search commands.
- Direct API tests for ODPC, ODPG, and ODPV namespace helpers.
- Subprocess-based console-script tests after packaging/install verification.
- Negative-path functional tests for invalid ODPS, ODPC, ODPG, and ODPV inputs.
- Functional tests with `datacontract-cli` installed for real external lint and
  export execution.
- A maintained external DPROD corpus with locally usable contexts. The OMG
  Beta 2 archive examples use remote context URLs that this SDK deliberately
  refuses to fetch, so the current DPROD corpus is synthetic and explicitly
  labelled as such.
- A pinned DCAT application-profile SHACL suite. Current DCAT validation is
  limited to safe RDF parsing, fact extraction, and validated ODPS drafts.
