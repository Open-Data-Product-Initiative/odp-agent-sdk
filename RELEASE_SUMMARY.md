# Open Data Products Python SDK 0.4.0 Release Notes

## Unreleased package contents

This is the next unreleased PyPI package. It combines the earlier ODPS 4.2
work with the new draft ODPV 1.1 interoperability capabilities below; neither
area is a separately published 0.5.0 release.

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

## What changes for users

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
final distribution-build check.
