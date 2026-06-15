# Release Summary: 0.2.4

## Richer agent manifest

The `open-data-products manifest --json` output now describes the SDK as a full
capability map instead of only a thin MCP tool list. The existing `tools` array
stays stable for ARWS/MCP compatibility, while the manifest now also exposes:

- `interfaces` for the CLI, stdio MCP server, and manifest command
- `standards` for ODPS, ODPC, ODPG, and ODPV coverage
- `capabilities` for validation, generation, local and hosted LLM runtimes,
  fragment workflows, portfolio workspaces, catalog/graph builds, compact
  TOON/GCF context sidecars, vocabulary context, product contracts, and bundled
  resources
- `workflows` with practical command recipes mapped to related MCP tools,
  including generation config setup, local/hosted provider selection, fragment
  generation, ODPC catalog assembly, ODPG graph assembly, TOON/GCF sidecar
  generation, graph inspection/conversion, vocabulary exploration,
  product-contract checks, and the full portfolio lifecycle: build, refresh,
  sync, localize, render, and explain
- `resources` as logical bundled resource IDs without package filesystem paths
- `safety` metadata that separates safe read-only MCP tools from CLI workflows
  that may write artifacts or call configured LLM providers

This makes the manifest useful as an agent-facing SDK discovery surface: agents
can now understand what the package can accomplish, which standards are covered,
which workflows exist, and which interface to use before choosing individual
tools.

## SDK architecture documentation

The development docs now include an SDK architecture overview in Markdown and a
visual HTML companion:

- `docs/development/sdk-architecture.md`
- `docs/development/sdk-architecture.html`

The new architecture guide gives contributors a high-level map of the package,
including spec namespaces, cross-spec facades, workflow modules, CLI/MCP/manifest
surfaces, bundled resources, compact-context helpers, and where new behavior
should be added.

Verification:

- `pytest -q`
- `python3 -c "import open_data_products"`
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
- `test ! -e docs/superpowers`
