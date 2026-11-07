# Contract Portfolio Discovery Design

## Purpose

Discover technical evidence in a collection of ODCS contracts before a human
defines or approves data product boundaries. The capability produces a
traceable contract inventory, explainable technical relationships, and
review-only product candidates. It does not create approved data products,
assert business demand, or replace product-management decisions.

## Scope

The first release accepts a local directory of YAML and JSON contracts. It
recursively inventories readable files, detects supported ODCS documents,
normalizes their available technical metadata, and records unreadable,
unsupported, invalid, and duplicate inputs without aborting the scan.

It exposes the same capability through the Python API, the `portfolio`
command group, MCP, the agent manifest, documentation, and automated tests.
It writes these review artifacts:

- `contract-inventory.json` — one normalized record per discovered file,
  including logical source identity, source reference, detection result,
  validation result, extracted metadata, and findings.
- `product-candidates.json` — deterministic candidate groups, relationship
  evidence, rule rationale, confidence classification, unresolved questions,
  and optional AI proposals.
- `discovery-report.html` — a static human-readable rendering of the two JSON
  artifacts, including evidence links and missing-business-information
  sections.
- `odpc/` and `odpg/` review fragments only when the available evidence can
  represent a valid object or confirmed technical dependency. These are never
  published as a portfolio or treated as approved products.

Optional AI analysis receives the normalized deterministic inventory rather
than raw arbitrary files. Its suggestions are tagged `proposed`, include
supporting contract references and a rationale, and never become confirmed
facts or generated products automatically.

## Source model

Discovery operates on a `ContractSource` abstraction. Source records have a
stable logical ID, a type, and a source reference. The first implementation
ships `directory`; it maps each file to a logical ID and a portable source
reference. Future API sources use the same normalized inventory and output
models rather than a separate portfolio engine.

The user-selectable source can be either a directory argument or a named
source from `generation.config.yaml`. The initial runtime rejects `type: api`
with a structured `source_not_implemented` finding. It must not make network
calls or infer an endpoint from a directory source.

API-ready source configuration belongs under `portfolio.contractSources` in
`generation.config.yaml`:

```yaml
portfolio:
  contractSources:
    contracts-api:
      type: api
      endpoint: https://contracts.example.org/api/contracts
      credentialsRef: env:ODP_CONTRACTS_API_TOKEN
      authentication:
        type: bearer
      documentsSelector: items
      pagination:
        type: cursor
        nextSelector: nextCursor
```

This config contains endpoint and response-shape metadata but no credential
values. `credentialsRef` is valid only as `env:NAME`, where `NAME` is an
environment-variable name. The SDK reads the process environment when an API
adapter exists; it does not load `.env` files, serialize secret values, include
them in URLs, or log them. Raw credential, authorization, token, and API-key
fields remain invalid configuration.

## Deterministic analysis

Every candidate and relationship records its evidence class:

- `explicit` for a dependency or reference declared in a source contract;
- `inferred` for deterministic overlap or similarity rules; and
- `proposed` for optional AI suggestions.

Exact duplicates use canonical hashes over normalized documents. Near-duplicate
and schema-overlap findings compare normalized model and field signatures.
Technical grouping rules may consider exact duplicates, shared data objects,
overlapping field signatures, explicit dependencies, common owner/domain, and
metadata completeness. Each rule records the matching inputs and score so a
reader can reproduce the result. Technical similarity alone cannot create a
confirmed data product boundary.

External contract validation remains optional because the existing
`datacontract-cli` adapter is optional. Structural parsing, ODCS detection, and
metadata extraction always run. Per-contract validation is recorded as
`passed`, `failed`, or `unavailable`; unavailable validation does not convert a
contract into an invalid one and does not stop the scan.

## Public interfaces

The Python facade exports a discovery request/result API from
`open_data_products.__init__`. The command is:

```text
open-data-products portfolio discover-contracts CONTRACTS_DIR --output DIR
```

It supports `--source NAME` for a future configured source, `--portfolio PATH`
to compare candidates with an existing ODPC portfolio, `--ai` plus the existing
generation provider options, `--strict-validation`, and `--json`. Directory
input and `--source` are mutually exclusive. The deterministic mode does not
require provider configuration.

The MCP tool is `discover_contract_portfolio`. It is `state-changing` because
it writes artifacts and requires `approved: true`. It returns only logical
source and artifact IDs, counts, statuses, and findings; it never returns
absolute paths, source documents, provider credentials, or raw contract bodies.
The MCP manifest and conformance tests classify it consistently.

## Error and security behavior

Discovery is best effort per contract and fail-safe per source configuration.
Unreadable, malformed, unsupported, and invalid documents produce normalized
findings while other records continue. An unknown named source, malformed
source configuration, an invalid `credentialsRef`, or an unimplemented API
source returns a clear structured error or source finding without attempting a
request.

Source references are logical IDs or credential-free URIs. The implementation
reuses the existing URL credential checks and activity-log redaction. Generated
HTML escapes values before rendering and contains no full contract documents
unless a future explicit export mode is separately designed.

## Verification

Tests use `tmp_path` fixtures and cover mixed YAML/JSON repositories,
multiple ODCS versions, duplicates, overlap, declared dependencies, incomplete
metadata, unreadable files, unsupported documents, validation unavailable,
strict-validation exit status, output determinism, AI proposal labelling,
portfolio comparison, and HTML escaping. Functional CLI, MCP, manifest, public
export, and configuration validation tests cover the full surface. The complete
suite and the repository pre-commit checks remain the release gate.
