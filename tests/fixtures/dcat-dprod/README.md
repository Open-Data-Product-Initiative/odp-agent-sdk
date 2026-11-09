# DCAT and DPROD functional fixtures

`valid-catalog.ttl` is a self-contained DCAT catalog fixture with one explicit
dataset and distribution. `valid-product.ttl` is a self-contained, synthetic
DPROD 1.0 Beta 2 compatibility fixture with one explicit DataProduct, its
ports, datasets, service, owner, and policy. These are SDK-owned acceptance
fixtures, not claims of OMG example conformance.

`invalid-owner.ttl` deliberately violates the owner-node SHACL constraint.
`unsafe-remote-context.jsonld` deliberately contains a remote JSON-LD context;
the SDK must reject it without fetching it.
