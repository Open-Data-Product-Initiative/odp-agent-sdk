# Open Data Products Python SDK 0.5.0 Release Notes

## ODPC v1.1 AI products are ready to validate

Version 0.5.0 adds offline validation for the official ODPC v1.1 AI Product
profile and its catalog representation. The package bundles the canonical
schemas, so validation does not fetch remote schemas at runtime.

## What changes for users

- `validate_ai_product` validates a standalone `AIProduct` profile, including
  its purpose, structured ownership, governance, and evaluation requirements.
- `validate_ai_product_bundle` checks that a standalone profile, an ODPC v1.1
  catalog entry, and an ODPG `AIProduct` node have consistent identities and
  profile references.
- The unified Python agent API and `open-data-products validate` command
  automatically detect an ODPC v1.1 `AIProduct` from its canonical schema URI
  and report `odpc`, `AIProduct`, and version `1.1`.

## Compatibility

Existing ODPC v1.0 catalog validation remains unchanged. An AI product is a
separate ODPC v1.1 profile; no existing data-product profile or agent node is
reinterpreted.

## Release confidence

The test suite covers standalone profile validation, missing governance paths,
agent API and CLI detection, catalog validation, bundle identity mismatches, and
top-level public API exposure. The distribution build includes the v1.1 profile
and catalog schemas.
