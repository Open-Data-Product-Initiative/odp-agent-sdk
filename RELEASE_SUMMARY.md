# Open Data Products Python SDK 0.6.4 Release Notes

## Unreleased package contents

This release supersedes 0.6.3 with the same Data Contract Intelligence
capabilities and restores normal PyPI provenance attestations.

## Release provenance

- 0.6.4 is the preferred release for the Data Contract Intelligence update.
- It is published through the normal trusted-publishing workflow with PyPI
  provenance attestations enabled.
- Version 0.6.3 remains available for compatibility with pinned installs, but
  has no PyPI provenance attestation because the external transparency log was
  unavailable during its publication.

## Data Contract Intelligence

- Discover and inventory ODCS contracts from local folders or configured API
  sources, with source references and declared metadata retained as evidence.
- Identify exact duplicates, schema overlap, shared technical resources, and
  shared domain/capability signals without treating inferred relationships as
  source facts.
- Report metadata gaps, interface coverage and types, and contracts that have
  no current opportunity signal.
- Classify review-only opportunities as standalone product candidates,
  boundary proposals, or rationalisation opportunities. No data product is
  created or approved automatically.
- Produce the same evidence-backed intelligence through the Python API, CLI,
  MCP response, structured JSON artifacts, and a self-contained offline HTML
  report.

## Explicit ODCS wrapper input

- Use `open-data-products product wrap-contract --input contract.yaml` in all
  documented wrapper workflows.
- The former positional contract input remains a compatibility alias, but it
  cannot be combined with `--input`.

## MCP product drafting

- `wrap_odcs_contract` is a state-changing MCP tool for writing a validated
  ODPS draft from an ODCS contract.
- It accepts the same enrichment and full-draft options as the CLI and redacts
  local filesystem paths from its response.

## ODCS-to-ODPS product drafting

- Wrap ODCS 3.0, 3.1, and 3.2 contracts as validated ODPS 4.2 drafts with
  `open-data-products product wrap-contract`.
- Use `--enrich` for a business-language description and discovery tags, or
  `--enrich --full-draft` for wider AI-generated ODPS product details.

## ODPS v4.2 support

The SDK supports ODPS v4.2 while retaining v4.1 parsing and validation. It
understands profile-based Contracts and Data Access, including required default
profiles, output-port types, profile references, and malformed URL checks.
New generation and portfolio workflows produce v4.2 artifacts. The CLI and MCP
surfaces detect v4.1 and v4.2 through schema URI or version value.

## Draft ODPV 1.1 interoperability support

This package also bundles ODPV 1.1 vocabulary and five interoperability profiles:
DCAT 3, ODCS 3, OpenLineage 1, PROV-O, and ODRL 2. ODPV 1.1 and every bundled
profile remain draft. Existing ODPV 1.0 behaviour remains the default.
The executable profile API is `open_data_products.profiles`; ODPV retains the
versioned vocabulary and source-profile assets.

## ODPC v1.1 AI products

- `validate_ai_product` validates a standalone `AIProduct` profile, including
  its purpose, structured ownership, governance, and evaluation requirements.
- `validate_ai_product_bundle` checks that a standalone profile, an ODPC v1.1
  catalog entry, and an ODPG `AIProduct` node have consistent identities and
  profile references.
- The unified Python agent API and `open-data-products validate` command
  automatically detect an ODPC v1.1 `AIProduct` from its canonical schema URI.

## Other user-facing capabilities

- Select ODPV 1.1 explicitly with `load_vocabulary_release("1.1.0")`; no
  existing call is upgraded silently.
- Use `open_data_products.profiles` for profile validation, mapping resolution,
  and bounded transformations; importing those operations from
  `open_data_products.odpv` is not supported.
- Validate an exact profile id and version, then resolve or explain mappings
  only with `allow_draft=True`. Every mapping result includes vocabulary and
  profile identity, lifecycle status, evidence, direction, and a SHA-256
  content digest.
- Use `odpv-profile-validate`, `odpv-profile-resolve`, and
  `odpv-profile-transform` from the unified CLI, or use the safe MCP profile
  tools for validation, resolution, explanation, and bounded transformation.
- DCAT 3, ODCS 3, OpenLineage 1, PROV-O, and ODRL 2 adapters execute only
  profile-permitted mappings. They preserve declared-versus-observed state and
  report missing bindings, missing policy rules, unsupported directions, and
  out-of-scope concepts as reviewable refusals or skips.
## Compatibility and release confidence

ODPV 1.0 remains the default vocabulary and retains its existing URI and helper
behaviour. The test suite validates every bundled profile against the supplied
Draft 2020-12 schema, checks all five pinned mapping counts, and exercises
adapter direction, prerequisite, and provenance boundaries. CI remains the
final distribution-build check. Existing ODPC v1.0 catalog validation remains
unchanged; an AI product is a separate ODPC v1.1 profile.
