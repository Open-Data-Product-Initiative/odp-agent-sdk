# Development Notes

This folder contains user-facing guides and contributor-facing development
notes. Contributor notes explain the SDK internals that are easy to misuse when
adding features, fixing validation behavior, or extending agent surfaces.

Use these pages when changing complex SDK behavior:

- [Generation development](generation-development.md): prompt pipelines,
  provider handling, ODPS product generation, normalization, validation, and
  repair.
- [ODPS validation development](odps-validation-development.md): ODPS loading,
  codecs, raw v4.1 checks, model validation, and schema-vs-SDK compatibility.
- [Data Contracts development](data-contracts-development.md): contract loading,
  optional adapter validation, ODPS contract references, static alignment, and
  product-level reports.
- [Agent surface development](agent-surface-development.md): cross-spec
  loading, detection, validation, explanation, reference discovery, and summary
  behavior.
- [ODPC catalog development](odpc-catalog-development.md): fragment collection,
  catalog building, validation, HTML rendering, and object guidance search.
- [ODPG graph development](odpg-graph-development.md): graph construction,
  validation, traversal, analysis, context extraction, and graph explorer
  generation.
- [MCP development](mcp-development.md): MCP tool registry, safe-class policy,
  stdio server behavior, ARWS manifest generation, and tests.

Keep these pages focused on implementation rules and contributor workflows.
User setup, beginner commands, and runnable examples belong in the user-facing
guides such as [commands.md](commands.md), [generation.md](generation.md), and
[data-contracts.md](data-contracts.md).

