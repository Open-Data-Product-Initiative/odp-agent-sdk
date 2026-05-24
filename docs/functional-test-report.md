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
| Resolve product contracts | Covered | Covered | Covered |
| Validate Data Contracts | Covered missing optional adapter | Covered through check-contract/report/alignment | Covered |
| Summarize Data Contracts | Covered | Covered through contract-report | Covered |
| Extract contract schema | Covered | Covered | Covered |
| Product-contract alignment | Covered | Covered | Covered |
| Product contract report | Covered | Covered | Covered |
| Product contract risk summary | Not yet direct | Covered through audit findings | Covered |
| MCP initialize/list tools | Not applicable | Not applicable | Covered |

## Fixture Strategy

The functional layer uses real package and example artifacts where practical:

- ODPS: `apps/pricing_402_builder/priced_product.yaml`
- ODPC: a minimal temporary catalog fixture
- ODPG: `open_data_products/odpg/data/graph/graph.yaml`
- ODPV: `open_data_products/odpv/data/vocab/odpv.yaml`
- Data Contracts: temporary ODPS products with native inline
  `/product/contract/spec` plus temporary local Data Contract YAML files

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

## Current Intentional Gaps

The current functional layer is the first cross-surface pass. Useful follow-up
coverage would be:

- Direct CLI tests for `refs` and spec-specific search commands.
- Direct API tests for ODPC, ODPG, and ODPV namespace helpers.
- Subprocess-based console-script tests after packaging/install verification.
- Negative-path functional tests for invalid ODPS, ODPC, ODPG, and ODPV inputs.
- Functional tests with `datacontract-cli` installed for real external lint and
  export execution.
