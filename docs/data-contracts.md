# Data Contract Workflows

Data Contract capabilities are intentionally split between the ODP SDK and
`datacontract-cli`:

- The ODP SDK owns product context, ODPS reference resolution, static schema extraction, alignment checks, CLI orchestration, MCP tools, and compact agent-ready reports.
- `datacontract-cli` remains the optional execution engine for external contract linting and export.
- Live data tests are not run by default and are not exposed through MCP.

Install the optional adapter when you need external contract linting or export:

```bash
pip install "open-data-products[contracts]"
```

## Commands

```bash
open-data-products product check-contract examples/product.yaml examples/contract.yaml --json
open-data-products product resolve-contracts examples/product.yaml --json
open-data-products product contract-report examples/product.yaml examples/contract.yaml --json
open-data-products product align-contract examples/product.yaml examples/contract.yaml --json
open-data-products product contract-schema examples/contract.yaml --json
open-data-products product export-contract examples/contract.yaml --format jsonschema --json
open-data-products product audit examples/product.yaml --json
```

## Supported Contract References

Native ODPS `/product/contract` references can point to local files:

```yaml
product:
  contract:
    type: DCS
    $ref: ./contracts/orders.contract.yaml
```

They can also point to remote contract URLs:

```yaml
product:
  contract:
    type: ODCS
    contractURL: https://example.com/contracts/orders.yaml
```

Inline contract specs are used for static summaries and alignment:

```yaml
product:
  contract:
    type: DCS
    spec:
      name: Orders
      models:
        orders:
          fields:
            order_id:
              type: string
              required: true
```

Practical extension-style references such as `extensions.dataContract.href` are
also recognized when resolving product contracts.
