# Open Data Products Python SDK 0.4.0 Release Notes

## ODPS v4.2 is ready to use

Version 0.4.0 adds full support for ODPS v4.2 while keeping existing ODPS v4.1
documents working. You can validate, inspect, generate, and package v4.2 data
products without downloading schemas at runtime.

The SDK now understands v4.2 profile-based Contracts and Data Access. A data
product can declare a default Contract profile, additional named profiles,
external profile packages, and explicit links from an access profile to its
Contract. Invalid profile structures, missing required defaults, missing output
port types, invalid references, and malformed URLs are reported during
validation.

## What changes for users

- New product generation and portfolio builds produce ODPS v4.2 artifacts.
  Generated Data Access uses the required `default` profile, and the linked
  Product Reference records ODPS version 4.2 as well.
- The Python SDK offers helpers for creating Contract and Data Access profiles.
  Use `OpenDataProduct(details, version="4.2")` when creating a v4.2 product
  directly in Python.
- The CLI and MCP interfaces automatically recognize v4.1 and v4.2 documents
  from their schema URI or `version` value. Their validation, explanation, and
  reference commands expose the matching version and v4.2 profile references.
- MCP can now build a portfolio workspace. This is a state-changing tool: the
  caller must send `approved: true` because the operation writes files and can
  call the configured LLM provider.

## Compatibility

ODPS v4.1 remains supported for parsing and validation, and the Python
`OpenDataProduct` constructor continues to default to v4.1 for compatibility.
Use `version="4.2"` for newly created v4.2 products. A v4.1 singleton Contract
is not silently reinterpreted as a v4.2 Contract profile.

## Release confidence

The test suite covers v4.1 and v4.2 schema routing, profile round trips, CLI
and MCP commands, portfolio generation and fallback artifacts, plus the MCP
portfolio-build approval gate. CI runs the full suite, builds and checks the
distribution, then validates a v4.2 fixture from an installed wheel.

The local environment cannot build a distribution because its Python build
backend is unavailable and it cannot download dependencies. The CI workflow is
the final distribution-build check.
