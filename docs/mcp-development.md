# MCP Development Notes

This page explains the MCP and ARWS surfaces for contributors.

## Main Code Paths

MCP support lives under `open_data_products/mcp/`:

- `tools.py`: pure tool registry and handlers.
- `server.py`: minimal stdio JSON-RPC 2.0 MCP server.
- `manifest.py`: ARWS-style agent manifest generation.

The unified CLI exposes the server through `open-data-products serve` and the
manifest through `open-data-products manifest`.

## Tool Registry

`TOOLS` is the source of truth for MCP tools. Each entry contains:

- `name`
- `description`
- `inputSchema`
- `handler`
- `class`

Tool classes follow the ARWS taxonomy:

- `safe`
- `state-changing`
- `destructive`

Today the MCP surface is safe/read-only. If a future tool changes state or can
destroy data, set the class correctly and update agentic-pattern tests.

## Handler Rules

Handlers return MCP content envelopes:

```python
{"content": [{"type": "text", "text": "..."}]}
```

Most handlers serialize structured payloads as formatted JSON text. Keep
outputs bounded and agent-readable. Do not return full document bodies from
summary or resource-discovery tools.

Handlers should use public SDK APIs where possible. This keeps MCP behavior
aligned with Python and CLI behavior.

## Server Boundary

`server.py` implements a small JSON-RPC loop over stdio:

- `initialize`
- `tools/list`
- `tools/call`
- `shutdown`
- `exit`

The server owns the error boundary for tool calls. If a handler raises, the
server returns an MCP error envelope instead of crashing the process.

Do not add third-party MCP runtime dependencies unless there is a strong reason.
The current server is intentionally small and portable.

## Manifest

`generate_agent_manifest()` renders public tool metadata without handlers. It
includes tool name, description, class, and input schema.

Keep the manifest and MCP tool list aligned by deriving both from `TOOLS`.

## Safe Surface Policy

The MCP surface should avoid:

- writing generated files;
- returning full document bodies for lightweight summary calls;
- running live external tests;
- requiring credentials;
- exposing destructive filesystem operations.

State-changing SDK features can still exist in Python or CLI. Exposing them to
MCP requires an explicit class decision and tests.

## Tests

Use these files when changing MCP or manifest behavior:

- `tests/test_mcp.py`
- `tests/test_agentic_patterns.py`
- `tests/test_functional_cli.py`
- `tests/test_functional_agent_api.py` when MCP handlers call public APIs whose
  result shape changes.

For new tools, add tests for registry metadata, handler output, manifest output,
and error behavior where relevant.

