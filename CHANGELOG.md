# Changelog

## Unreleased

## 0.8.0

- Set the minimum Python patch version to 3.8.1, matching the existing RDF
  dependencies; Python 3.8 remains supported.
- Add experimental named platform connection profiles and OpenMetadata read
  operations. ODPS export has been checked against one OpenMetadata 2.1.0 product.
- Add an opt-in workaround for OpenMetadata millisecond `updated` values that
  keeps the original export and records the loss of time precision.
- Add experimental reviewed OpenMetadata ODPS 4.1 creation for the 2.1.0 API,
  guarded by explicit review, a write-enabled profile, and local validation.
- Add reviewed OpenMetadata 2.1.0 data-product deletion with explicit notice
  that the platform deletes permanently and recursively.
- Add Keychain credential references and reviewed updates of product title and
  description, with retrieval of the platform-managed metadata revision.
- Add paginated OpenMetadata data-product search and live listing/search checks.
- Generate product drafts from Word documents and preserve source descriptions;
  add opt-in Markdown and Word generation-to-OpenMetadata live tests.
- Harden malformed configuration, Ollama responses and interrupted platform
  requests; ambiguous write outcomes remain explicit and are never retried.
- Protect generated product files from collisions, stage export files, report
  unverified create results, bound Word extraction and expose matching source
  evidence. Probe stale update revisions in the opt-in live test.
- Reject ambiguous create YAML, verify tested platform fields, report unverified
  deletions and provide read-only recovery candidates. Bound ODPS generation
  resources and flag instruction-like source text and critical-field changes.
- List OpenMetadata domains and verify the selected domain after product creation.
- Add reviewed OpenMetadata domain creation and revision-checked product domain changes.
- Review and attach ODCS 3.1 contracts to OpenMetadata products; support inline
  or linked contracts during reviewed ODPS 4.1 product creation.
- Preserve the complete ODCS source schema and version in product-linked
  contract metadata when OpenMetadata cannot apply the schema natively.
- Select ODPS 4.1 or 4.2 for generation without silently converting existing
  specifications; OpenMetadata creation requires a declared, matching 4.1 source.
- Add workspace connection selection and guided OpenMetadata CLI commands for
  listing, searching, retrieving, comparing, creating, updating and deleting.
  Retrieval, comparison, update and delete require product UUIDs.
- Add `config integrations --copy-to` to create a user-owned connection
  config from the packaged template; multiword domain FQNs are preserved.
- Support reviewed product updates from an ODPS YAML or JSON input, showing
  supported mappings and source fields that are not applied.
- Review folder batches together, exclude possible duplicates, recheck inputs,
  and report created, skipped, failed and uncertain outcomes without retries.
- Resolve and verify requested owners and catalog tags; default the owner for
  creation to the authenticated OpenMetadata account when none is specified.
- Compare source ODPS with native and exported platform metadata, preserving
  provenance, validation findings, timestamps and field-level differences.
- Return validated ODPC 1.0 catalogs from OpenMetadata CLI list and search and
  export catalogs as YAML or JSON. These CLI outputs replace the earlier native
  JSON result shape; the adapter's native listing and search APIs remain.
  ODPC `productVersion` uses the platform metadata revision and marks its origin.

## 0.7.0

- Add pinned offline DPROD 1.0 Beta 2 ingestion, SHACL validation, catalog
  intelligence, DPROD-to-ODPS drafting, and deterministic ODPS-to-DPROD Turtle
  and JSON-LD export.
- Reject the non-normative DPROD development namespace rather than mixing it
  with the OMG Beta 2 vocabulary.
- Add `pyshacl>=0.28.1,<0.29.0` for local normative SHACL evaluation.
- Preserve mapping classifications and loss records; DPROD and ODPS coverage
  is not asserted as equivalent.
- Extend the clean-wheel CI smoke test to load DPROD assets and cross-check an
  exported graph with SHA-512-verified Apache Jena SHACL.
