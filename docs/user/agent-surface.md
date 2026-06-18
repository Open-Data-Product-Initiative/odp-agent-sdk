# Agent Surface

The SDK ships a local stdio MCP (Model Context Protocol) server. MCP-capable
hosts such as Claude Code, Codex CLI, Cursor, and Gemini CLI can be configured
to launch the server and call its tools over MCP, instead of invoking SDK CLI
commands manually:

```bash
open-data-products serve
```

## Codex And Claude Code

Project-level MCP setup is included for Codex and Claude Code so the SDK can be
used as an MCP tool surface directly from the repository.

Codex uses `.codex/config.toml`:

```toml
[mcp_servers.open_data_products]
command = "open-data-products"
args = ["serve"]
enabled = true
startup_timeout_sec = 10
tool_timeout_sec = 60
```

Claude Code uses `.mcp.json`:

```json
{
  "mcpServers": {
    "open_data_products": {
      "command": "open-data-products",
      "args": ["serve"]
    }
  }
}
```

Both configs are intentionally portable: they use `open-data-products serve`,
contain no local absolute paths, and assume `open-data-products` is available
on `PATH`. Install the package in the active environment first with
`pip install -e .` or install the published package before expecting an agent
host to launch the server.

## MCP Tools

The MCP server exposes safe tools for validation, explanation, references,
resource discovery, summaries, ODPC object search, ODPV vocabulary work, ODPG
graph reasoning, OKF context bundle metadata, and product-level Data Contract
context.

Current tool names include:

- `validate_document`
- `explain_document`
- `resolve_references`
- `list_resources`
- `get_resource`
- `load_summary`
- `validate_okf_bundle`
- `list_okf_concepts`
- `catalog_artifacts`
- `search_terms`
- `resolve_vocabulary_term`
- `explain_vocabulary_term`
- `check_vocabulary_relationship`
- `vocabulary_term_context`
- `search_objects`
- `search_graph_objects`
- `summarize_graph`
- `traverse_graph`
- `analyze_graph`
- `agent_context`
- `resolve_product_contracts`
- `validate_product_contracts`
- `check_product_contract_alignment`
- `generate_product_contract_report`
- `summarize_product_contract_risks`
- `validate_data_contract`
- `summarize_data_contract`
- `extract_data_contract_schema`

## ARWS Manifest

The SDK also emits an
[ARWS](https://agenticpatterns.veso.ai/arws) agent manifest:

```bash
open-data-products manifest --json
```

The manifest is a full SDK capability map. It keeps the stable MCP-compatible
`tools` array, then adds discovery metadata for agent hosts:

- `interfaces`: CLI, stdio MCP, and manifest commands
- `standards`: ODPS, ODPC, ODPG, and ODPV coverage
- `capabilities`: validation, generation, local/hosted LLM runtime, fragment,
  portfolio, catalog/graph, compact-context sidecar, vocabulary,
  OKF context-bundle, product-contract, and resource surfaces
- `workflows`: common command recipes mapped to related MCP tools, including
  generation config setup, local/hosted provider selection, fragment
  generation, ODPC catalog assembly, ODPG graph assembly, TOON/GCF sidecar
  generation, OKF validation/import/export, graph inspection/conversion,
  vocabulary exploration,
  product-contract checks, and the full portfolio lifecycle from build through
  refresh, sync, localize, render, and explain
- `resources`: logical IDs for bundled schemas, vocabularies, prompts, and
  retrieval indexes
- `safety`: read-only MCP policy and CLI state-changing boundaries

## Skills

Three [agent skills](https://agenticpatterns.veso.ai/skills) under `skills/`
wrap common workflows for hosts that auto-load `SKILL.md` bundles:

- `odp-validate`
- `odp-author`
- `odp-explore-graph`
