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

## ODPS v4.2 profiles

ODPS v4.2 stores Contracts as named profiles under `product.contract`. An
inline collection always includes `default`; additional profile names are
publisher-defined. Data Access follows the same pattern under
`product.dataAccess`, and every inline access profile has `outputPortType`.

```yaml
schema: https://opendataproducts.org/v4.2/schema/odps.yaml
version: "4.2"
product:
  details:
    en:
      productID: orders
      name: Orders
      visibility: public
      status: draft
      type: dataset
  contract:
    default:
      id: ORDERS-001
      type: ODCS
  dataAccess:
    default:
      outputPortType: API
      contract:
        $ref: "#/product/contract/default"
```

The SDK preserves root profile-package and individual-profile references. It
does not fetch external references during ordinary validation.

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

## Wrap an ODCS contract as an ODPS 4.2 draft

`wrap-contract` creates a structurally valid ODPS 4.2 draft from an ODCS 3.0,
3.1, or 3.2 contract. It is deterministic by default: the source contract remains
the technical authority and the product is deliberately marked `draft` and
`private`. A valid draft is not evidence of approved ownership, business value,
service commitments, access rights, or production readiness.

```bash
open-data-products product wrap-contract --input contracts/orders.yaml \
  --output products/orders.yaml
```

Local relative and absolute paths are resolved without network access and are
recorded as schema-valid `file://` URIs in `product.contract.default.contractURL`.
Those references are portable only to systems with access to the same path; use
`--contract-url` to publish a portable reference when one becomes available.
The same command accepts percent-encoded file URIs and HTTP(S) URLs. Remote
loads use bounded requests; retrieval failures do not include credentials in
the diagnostic. For safe generated references, query parameters and fragments
are rejected; use a credential-free canonical URL. Use `--contract-url` when
the generated product should refer to the published location rather than the
loaded local copy:

```bash
open-data-products product wrap-contract --input ./contracts/orders.yaml \
  --contract-url https://example.org/contracts/orders.yaml \
  --output products/orders.yaml
```

The default profile is always named `default`, uses `type: ODCS`, and records
the ODCS specification version separately from the contract instance version.
`--inline-contract` instead preserves the complete parsed source document under
`product.contract.default.spec`; it does not translate ODCS-only structures.

```bash
open-data-products product wrap-contract --input contracts/orders.yaml \
  --inline-contract --output products/orders.yaml
```

When an ODCS server explicitly establishes a supported technical transport, the
wrapper creates one named Data Access profile bound to
`#/product/contract/default`. It otherwise omits Data Access rather than
inventing endpoints, authentication, or availability commitments.

Use `--json` to receive source and resolved location, mapped fields,
provisional defaults, missing business information, warnings, optional AI
proposals, and the final ODPS validation result. `--dry-run` validates without
writing; existing outputs require `--overwrite`.

`--enrich` is opt-in and uses the normal generation-provider configuration:

```bash
open-data-products product wrap-contract --input contracts/orders.yaml \
  --output products/orders.yaml --enrich --config generation.config.yaml --json
```

AI output is returned as proposed, review-required business-layer fields. When
the provider returns a `description`, the generated ODPS draft uses its
business-language restatement of `description.purpose`. When it returns
`suggestedTags`, the draft uses those concise discovery tags in
`product.details.en.tags`. The structured result retains both as `proposed`;
only the AI description emits a review warning. Value propositions, consumers,
use cases, and suggested categories remain report-only proposals unless
`--full-draft` is selected. AI never rewrites the ODCS source or asserts ownership,
terms, access rights, service commitments, demand, or production approval.

Add `--full-draft` with `--enrich` when the intended output is a fuller draft rather
than a minimal ODPS wrapper:

```bash
open-data-products product wrap-contract --input contracts/orders.yaml \
  --output products/orders.yaml --enrich --full-draft --config generation.config.yaml
```

Extended mode applies the generated value proposition, categories, use cases,
product series, brand slogan, version notes, issue URL, and recommended product
URLs to `product.details.en`. It also maps the source contract instance version
to `productVersion`. `--full-draft` requires `--enrich` and retains all generated values
in the structured proposal report.

### Python API

```python
from open_data_products.contracts import wrap_contract

result = wrap_contract(
    "contracts/orders.yaml",
    output="products/orders.yaml",
    inline_contract=False,
    use_ai=False,
)

assert result.validation.valid
print(result.to_dict())
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

## Discover contract portfolio candidates

Use deterministic discovery before deciding whether technical contracts should
become data products:

    open-data-products portfolio discover-contracts ./contracts \
      --output ./portfolio-discovery --json

The command recursively reads YAML and JSON files and writes:

- `contract-inventory.json` with normalized source references and contract
  metadata.
- `contract-intelligence.json` with evidence-linked similarities, reuse
  findings, actionable investigation guidance, and information gaps.
- `product-candidates.json` with review-only standalone product candidates,
  boundary proposals, rationalisation opportunities, and source references for
  contracts with no current opportunity signal.
- `discovery-report.html`, a self-contained offline Data Contract Intelligence
  report with an overview, searchable contract explorer, relationship evidence,
  and product opportunities.

The report separates three different portfolio decisions: a standalone product
candidate requires a declared name, domain, and purpose; a boundary proposal
requires repeatable shared-domain capability evidence; and a rationalisation
opportunity requires exact-duplicate evidence. Contracts that meet none of
these conservative rules remain visible as having no current opportunity
signal. Relationships are inferred unless source contracts declare them. Every
candidate remains proposed; technical similarity does not establish a business
objective, consumer demand, ownership, or approved product boundary.

The default CLI output mirrors the report details in the terminal: overview
counts, interface types and their contracts, priority findings, contract
inventory, all three opportunity types, and every contract with no current
opportunity signal. Add `--json` to receive the same data as structured output.

The intelligence artifact records source contracts, evidence, why each finding
matters, and a suggested human investigation. It normalizes safe technical
interface identifiers such as declared server types and resource names, but it
does not expose server locations or credentials.

Future API sources are configured under portfolio.contractSources in
generation.config.yaml. Credentials use credentialsRef with an env:NAME
reference only. API retrieval is not implemented yet, so configured API
sources return a clear status without making a network request.
