# Data Contracts Development Notes

This page explains how Data Contract support is organized inside the SDK.
User-facing examples live in [data-contracts.md](data-contracts.md).

## Main Code Paths

Data Contract support lives under `open_data_products/contracts/`:

- `loader.py`: load, summarize, and extract schema information from contract
  YAML or JSON.
- `datacontract_cli_adapter.py`: optional integration with `datacontract-cli`.
- `product.py`: resolve ODPS product contract references and produce product
  contract reports.
- `alignment.py`: static ODPS-to-contract alignment checks.
- `models.py`: result dataclasses.
- `errors.py`: contract-specific exceptions.

The package root re-exports the public helpers through
`open_data_products/__init__.py`.

## Contract Loading And Summaries

Contract loading accepts local YAML/JSON paths and in-memory dictionaries.
Summaries intentionally return metadata, model counts, field counts, and
schema-like packets rather than full unbounded bodies.

`extract_contract_schema()` normalizes models and fields so alignment checks do
not need to understand every raw Data Contract dialect detail.

## Optional CLI Adapter

`validate_contract()` delegates to `datacontract-cli` only when that optional
tool is available. The SDK must remain usable without it.

Adapter rules:

- Missing optional tooling should return a structured validation result, not
  crash the SDK.
- Do not hardcode credentials or external service assumptions.
- Keep live data-source testing outside the default SDK path.

## ODPS Product References

`resolve_product_contracts()` walks an ODPS product mapping and looks for
contract-like objects. It recognizes conventional reference keys such as
`href`, `url`, `path`, `ref`, `$ref`, `contractURL`, and inline `spec`.

References are deduplicated by `(href, pointer)`.

Inline contract specs are supported for static SDK checks, but the optional
`datacontract-cli` adapter is not run against inline mappings.

## Product Contract Reports

`generate_product_contract_report()` orchestrates:

1. ODPS product validation through `validate_document()`.
2. Contract reference discovery.
3. Contract validation for each reference.
4. Contract summaries when local or inline content can be read.
5. Static product-contract alignment checks.
6. Findings and a compact report summary.

If no contract reference is found, the report includes a warning finding rather
than failing with an exception.

## Static Alignment

`check_product_contract_alignment()` is intentionally static. It compares
available ODPS metadata to contract schema models and fields. It does not run
live source tests.

Current checks include:

- product name compatibility;
- ODPS schema field presence compared with contract fields;
- required contract fields missing from ODPS metadata;
- ODPS fields missing from the contract.

`run_contract_tests=True` currently records a warning that live tests are not
implemented. Do not silently add network or database behavior to this path.

## Tests

Use these files when changing contract behavior:

- `tests/test_contracts.py` for unit-level contract loading, validation, and
  alignment behavior.
- `tests/test_functional_agent_api.py` for end-to-end public API workflows.
- `tests/test_agent_api.py` when changes affect shared validation or reference
  discovery.

Keep test fixtures local and deterministic. Do not require `datacontract-cli`
or external services in normal test runs.

