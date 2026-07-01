# Development Notes

This folder contains user-facing guides and contributor-facing development
notes. Contributor notes explain the SDK internals that are easy to misuse when
adding features, fixing validation behavior, or extending agent surfaces.

Use these pages when changing complex SDK behavior:

- [SDK architecture overview](sdk-architecture.md): high-level package map,
  boundaries, data flow, agent surfaces, and where new contributors should add
  code. See also the [visual HTML overview](sdk-architecture.html).
- [Generation development](generation.md): prompt pipelines,
  provider handling, ODPS product generation, normalization, validation, and
  repair.
- [ODPS validation development](odps-validation.md): ODPS loading,
  codecs, raw v4.1 checks, model validation, and schema-vs-SDK compatibility.
- [Data Contracts development](data-contracts.md): contract loading,
  optional adapter validation, ODPS contract references, static alignment, and
  product-level reports.
- [Agent surface development](agent-surface.md): cross-spec
  loading, detection, validation, explanation, reference discovery, and summary
  behavior.
- [ODPC catalog development](odpc-catalog.md): fragment collection,
  catalog building, validation, HTML rendering, and object guidance search.
- [ODPG graph development](odpg-graph.md): graph construction,
  validation, traversal, analysis, context extraction, and graph explorer
  generation.
- [Portfolio development](portfolio.md): portfolio source lanes, document
  intake, prompt budget gates, workspace orchestration, renderer, localization,
  validation, and tests.
- [Testing strategy](testing-strategy.md): baseline checks, focused test
  selection, portfolio intake ZIP regressions, and fixture rules for
  contributors.
- [SDK input documents plan](sdk-input-documents-plan.md): implemented
  portfolio document formats, optional Outlook support, warning-only source
  classes, and future intake adapters.
- [MCP development](mcp.md): MCP tool registry, safe-class policy,
  stdio server behavior, ARWS manifest generation, and tests.
- [SDK activity logging plan](sdk-activity-logging-plan.md): fixed-format
  command activity events, classification, rotation, redaction, and CLI
  integration planning.

Keep these pages focused on implementation rules and contributor workflows.
User setup, beginner commands, and runnable examples belong in the user-facing
guides such as [commands.md](../user/commands.md),
[generation.md](../user/generation.md), and
[data-contracts.md](../user/data-contracts.md).

## Refactor Compatibility Posture

Keep `open-data-products` as the primary CLI contract. The legacy
`open-data-products-odpg-generate` console script remains a compatibility entry
point for graph explorer generation; prefer the unified
`open-data-products odpg-generate` subcommand in new docs and examples.

Public imports continue to flow through `open_data_products.__init__`, while
internal modules should import from concrete namespaces such as
`open_data_products.agent`, `open_data_products.generation`, or
`open_data_products.contracts`. Do not remove compatibility wrappers or legacy
entry points during maintainability refactors unless a separate deprecation
plan, documentation update, and compatibility test are added first.
