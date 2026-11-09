# DPROD 1.0 Beta 2 interoperability

The SDK supports the OMG Data Products Ontology (DPROD) **1.0 Beta 2**, an
OMG in-process specification. It pins the normative 2026-06-01 ontology and
SHACL shapes locally, including their provenance and upstream SHA-256 values.
The bundled files are LF-normalized package copies; validation has no runtime
network dependency.

Only the normative Beta 2 namespace is supported:

```text
https://www.omg.org/spec/DPROD/
```

The development namespace `https://www.omg.org/spec/DPROD/dprod/` is rejected,
not silently converted. GitHub development examples and its experimental Data
Contracts profile are not normative Beta 2 functionality.

The OMG informative example archive (`ptc/26-05-33.zip`) is recorded in the
registry with its checksum, but is not an acceptance fixture: its JSON-LD
examples require a remote legacy context. Fetching that context would violate
the SDK's offline, non-crawling security boundary.

## Inspect and validate

```bash
open-data-products portfolio discover-dprod product.ttl --json
open-data-products dprod-validate product.ttl --json
```

Local files, `file://` URIs, supported RDF formats, and bounded public HTTP(S)
sources use the existing DCAT loader. Remote JSON-LD contexts, RDF imports,
credential-bearing URLs, crawling, and runtime ontology downloads are disabled.
Validation returns parsing errors separately from SHACL violations and semantic
conversion warnings. The normative shapes do not define mandatory cardinality,
so incomplete business context is reported as a conversion warning, not a new
SHACL rule.

## DPROD to ODPS

```bash
open-data-products product wrap-dprod --input product.ttl \
  --resource https://example.test/products/air --output air.yaml --json
```

The converter reuses the DCAT-to-ODPS 4.2 private-draft builder and validates
the resulting ODPS document. It maps labels, descriptions, domains, compatible
output-service endpoints, datasets, and distributions only where their
preconditions hold. A DPROD port is not automatically an ODPS data-access
profile. Purpose, owner, policy, input-port, lifecycle, security, and contract
information that lacks an ODPS-equivalent approved assertion remain in the
structured mapping report as conditional, partial, or unsupported information.

## ODPS to DPROD

```bash
open-data-products product export-dprod --input air.yaml --output air --json
```

This writes `air.ttl` and `air.jsonld`. When no identifier IRI is available,
the exporter uses `<base-iri>/<percent-encoded productID>`; the default is a
documented `urn:odps:dprod:/<productID>` rule. Exported graphs are checked with
the same pinned SHACL profile. They are not a semantic-equivalence claim:
unsupported and partially represented ODPS concepts appear in `losses`.

## Python and MCP

```python
from open_data_products import (
    discover_dprod_catalog, validate_dprod, wrap_dprod_resource,
    export_odps_to_dprod,
)

inventory = discover_dprod_catalog("product.ttl")
validation = validate_dprod("product.ttl")
draft = wrap_dprod_resource("product.ttl", inventory.products[0].id)
export = export_odps_to_dprod(draft.document)
```

MCP exposes safe `discover_dprod_catalog` and `validate_dprod` tools, and
state-changing `wrap_dprod_resource` and `export_dprod` tools because they
write artifacts. Local paths are redacted from MCP results.

## Release verification

CI installs the built wheel into a clean virtual environment and validates an
ODPS export using Apache Jena SHACL in addition to the SDK's pySHACL check.
Jena is downloaded from Apache with a pinned release and verified SHA-512; it
is a CI-only independent validator and is not an SDK runtime dependency.
