# Agent Surface Development Notes

The agent surface is the stable cross-spec API used by Python callers, CLI
commands, MCP tools, and agent hosts. It lives mostly in
`open_data_products/agent.py`.

## Public Responsibilities

The agent surface provides:

- `load_document()`
- `detect_document()`
- `validate_document()`
- `explain_document()`
- `resolve_references()`
- `load_summary()`
- resource discovery through `resources.py`

These helpers are designed to work across ODPS, ODPC, ODPG, and ODPV without
callers needing to choose a spec-specific namespace first.

## Detection

`detect_document()` uses a small set of stable signals:

- ODPC: schema contains `odpc`, root `kind: Catalog`, or `catalog` key.
- ODPG: schema contains `odpg` or graph-like `kind`.
- ODPS: schema contains `odps` or root `product` key.
- ODPV: root `id: ODPV` or `sections` key.

Keep detection conservative. Ambiguous detection creates wrong validation and
bad agent behavior downstream.

## Loading

`load_document(path)` reads the raw mapping first, detects the spec, then
delegates to the spec loader:

- ODPS returns an `OpenDataProduct`.
- ODPC returns a catalog mapping.
- ODPG returns a graph mapping.
- ODPV returns a vocabulary mapping.

Do not make `load_document()` return full derived artifacts or remote content.
It should load the document the user provided.

## Validation

`validate_document()` returns a shared `ValidationResult`. It should not raise
for ordinary invalid user documents.

Spec-specific validation rules:

- ODPS runs raw v4.1 checks and SDK model validation.
- ODPC delegates to `validate_catalog()`.
- ODPG delegates to `validate_graph()`.
- ODPV delegates to `validate_vocabulary()`.

When changing validation shape, update both Python API tests and any CLI/MCP
expectations that serialize `ValidationResult.to_dict()`.

## Explanation

`explain_document()` returns compact human-and-agent text, not a full rendered
document. Keep explanations line-oriented and bounded.

Spec-specific explainers should summarize:

- identity and version;
- status and counts;
- important configured components;
- validation-relevant hints when useful.

## Reference Discovery

`resolve_references()` recursively walks mappings and lists `$ref` and `ref`
values with pointer paths, inferred source spec, inferred target spec, and
source path when available.

Do not resolve reference targets in this helper. It is a discovery surface, not
a loader.

## Summary

`load_summary()` intentionally returns lightweight metadata such as path, spec,
size, and hash. It must not include full document bodies. This keeps MCP and
agent workflows safe for large or sensitive documents.

## Tests

Use these files when changing the agent surface:

- `tests/test_agent_api.py`
- `tests/test_functional_agent_api.py`
- `tests/test_agentic_patterns.py` when MCP or agent protocol behavior is
  affected.
- `tests/test_core.py`, `tests/test_odpc.py`, `tests/test_odpg.py`, or
  `tests/test_odpv.py` for spec-specific behavior behind the shared surface.

