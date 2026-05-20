"""MCP tool registry — pure data + handlers.

Each entry follows the MCP tool definition shape mandated at
agenticpatterns.veso.ai/tool-protocols::

    {
      "name": "<identifier>",
      "description": "<one-line purpose>",
      "inputSchema": {"type": "object", "properties": {...}, "required": [...]},
      "handler": callable(dict) -> {"content": [{"type": "text", "text": "..."}]},
      "class": "safe" | "state-changing" | "destructive",   # ARWS taxonomy
    }

Handlers return the MCP content envelope so they can be piped through
``server.py`` without further wrapping. They never raise on user-input errors;
they encode failures into the text payload so the agent can recover.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .. import (
    explain_document,
    get_resource,
    list_resources,
    load_document,
    load_summary,
    resolve_references,
    validate_document,
)
from ..odpc import search_objects as _search_objects, load_object_records
from ..odpg import (
    agent_context as _agent_context,
    analyze_graph as _analyze_graph,
    load_graph as _load_graph,
    search_graph_objects as _search_graph_objects,
    summarize_graph as _summarize_graph,
    traverse_graph as _traverse_graph,
    validate_graph as _validate_graph,
)
from ..odpv import search_vocabulary, load_vocabulary

Handler = Callable[[Dict[str, Any]], Dict[str, Any]]


def _envelope(text: str) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _json_envelope(payload: Any) -> Dict[str, Any]:
    return _envelope(json.dumps(payload, indent=2, default=str))


def _int_arg(args: Dict[str, Any], name: str, default: int) -> int:
    value = args.get(name, default)
    return default if value is None else int(value)


def _object_schema(
    properties: Dict[str, Any],
    required: Optional[List[str]] = None,
) -> Dict[str, Any]:
    schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


# --- handlers ---------------------------------------------------------------
# No try/except here — the MCP server's handle() owns the error boundary.


def _h_validate(args: Dict[str, Any]) -> Dict[str, Any]:
    result = validate_document(args["path"])
    return _json_envelope(result.to_dict())


def _h_explain(args: Dict[str, Any]) -> Dict[str, Any]:
    document = load_document(args["path"])
    return _envelope(explain_document(document, path=Path(args["path"])))


def _h_resolve_refs(args: Dict[str, Any]) -> Dict[str, Any]:
    refs = resolve_references(args["path"])
    limit = _int_arg(args, "limit", 100)
    payload = [ref.to_dict() for ref in refs[:limit]]
    return _json_envelope(
        {"count": len(refs), "returned": len(payload), "refs": payload}
    )


def _h_list_resources(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope([r.to_dict() for r in list_resources()])


def _h_get_resource(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(get_resource(args["id"]).to_dict())


def _h_load_summary(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(load_summary(args["path"]))


def _h_search_terms(args: Dict[str, Any]) -> Dict[str, Any]:
    vocab = load_vocabulary()
    results = search_vocabulary(
        args["query"],
        limit=_int_arg(args, "limit", 10),
        data=vocab,
    )
    return _json_envelope(results)


def _h_search_objects(args: Dict[str, Any]) -> Dict[str, Any]:
    records = load_object_records()
    results = _search_objects(
        args["query"],
        records=records,
        limit=_int_arg(args, "limit", 10),
    )
    return _json_envelope(results)


def _h_search_graph_objects(args: Dict[str, Any]) -> Dict[str, Any]:
    results = _search_graph_objects(
        args["query"],
        limit=_int_arg(args, "limit", 10),
    )
    return _json_envelope(results)


def _h_summarize_graph(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(_summarize_graph(_load_graph(args["path"])))


def _h_traverse_graph(args: Dict[str, Any]) -> Dict[str, Any]:
    graph = _load_graph(args["path"])
    result = _validate_graph(graph)
    if not result.valid:
        return _json_envelope(result.to_dict())
    paths = _traverse_graph(
        graph,
        args["start"],
        _int_arg(args, "depth", 2),
        relationship=args.get("relationship"),
        reverse=bool(args.get("reverse", False)),
    )
    return _json_envelope({"start": args["start"], "paths": paths})


def _h_analyze_graph(args: Dict[str, Any]) -> Dict[str, Any]:
    graph = _load_graph(args["path"])
    result = _validate_graph(graph)
    if not result.valid:
        return _json_envelope(result.to_dict())
    return _json_envelope(
        {"warnings": result.warnings, "analysis": _analyze_graph(graph)}
    )


def _h_agent_context(args: Dict[str, Any]) -> Dict[str, Any]:
    graph = _load_graph(args["path"])
    result = _validate_graph(graph)
    if not result.valid:
        return _json_envelope(result.to_dict())
    payload = _agent_context(graph, args["node"], _int_arg(args, "depth", 2))
    payload["warnings"] = result.warnings
    return _json_envelope(payload)


# --- registry ---------------------------------------------------------------

_PATH_PROP = {
    "type": "string",
    "description": "Filesystem path to an ODPS, ODPC, ODPG, or ODPV document (YAML or JSON).",
}
_QUERY_PROP = {"type": "string", "description": "Free-text search query."}
_NODE_PROP = {"type": "string", "description": "ODPG node id."}
_DEPTH_PROP = {
    "type": "integer",
    "description": "Maximum graph traversal depth.",
    "minimum": 1,
    "maximum": 20,
    "default": 2,
}
_LIMIT_PROP = {
    "type": "integer",
    "description": "Maximum number of results to return.",
    "minimum": 1,
    "maximum": 200,
    "default": 10,
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "validate_document",
        "description": "Detect the ODP spec, validate the document, and return errors/warnings.",
        "class": "safe",
        "inputSchema": _object_schema({"path": _PATH_PROP}, ["path"]),
        "handler": _h_validate,
    },
    {
        "name": "explain_document",
        "description": "Return a compact, line-oriented human+agent summary of any ODP document.",
        "class": "safe",
        "inputSchema": _object_schema({"path": _PATH_PROP}, ["path"]),
        "handler": _h_explain,
    },
    {
        "name": "resolve_references",
        "description": "List $ref/ref pointers in a document for cross-spec traversal.",
        "class": "safe",
        "inputSchema": _object_schema(
            {"path": _PATH_PROP, "limit": _LIMIT_PROP}, ["path"]
        ),
        "handler": _h_resolve_refs,
    },
    {
        "name": "list_resources",
        "description": "Enumerate bundled SDK resources (schemas, vocabularies, JSONL indexes).",
        "class": "safe",
        "inputSchema": _object_schema({}),
        "handler": _h_list_resources,
    },
    {
        "name": "get_resource",
        "description": "Fetch metadata for one bundled SDK resource by id.",
        "class": "safe",
        "inputSchema": _object_schema(
            {
                "id": {
                    "type": "string",
                    "description": "Resource id from list_resources (e.g. odpv.terms).",
                }
            },
            ["id"],
        ),
        "handler": _h_get_resource,
    },
    {
        "name": "load_summary",
        "description": "Return lightweight metadata (size, hash, spec) for a document; never the body.",
        "class": "safe",
        "inputSchema": _object_schema({"path": _PATH_PROP}, ["path"]),
        "handler": _h_load_summary,
    },
    {
        "name": "search_terms",
        "description": "Search the bundled ODPV vocabulary terms by keyword.",
        "class": "safe",
        "inputSchema": _object_schema(
            {"query": _QUERY_PROP, "limit": _LIMIT_PROP}, ["query"]
        ),
        "handler": _h_search_terms,
    },
    {
        "name": "search_objects",
        "description": "Search the bundled ODPC catalog object guidance records by keyword.",
        "class": "safe",
        "inputSchema": _object_schema(
            {"query": _QUERY_PROP, "limit": _LIMIT_PROP}, ["query"]
        ),
        "handler": _h_search_objects,
    },
    {
        "name": "search_graph_objects",
        "description": "Search bundled ODPG graph guidance records by keyword.",
        "class": "safe",
        "inputSchema": _object_schema(
            {"query": _QUERY_PROP, "limit": _LIMIT_PROP}, ["query"]
        ),
        "handler": _h_search_graph_objects,
    },
    {
        "name": "summarize_graph",
        "description": "Summarize ODPG graph metadata, nodes, edges, types, and confidence values.",
        "class": "safe",
        "inputSchema": _object_schema({"path": _PATH_PROP}, ["path"]),
        "handler": _h_summarize_graph,
    },
    {
        "name": "traverse_graph",
        "description": "Discover ODPG relationship paths from a focus node.",
        "class": "safe",
        "inputSchema": _object_schema(
            {
                "path": _PATH_PROP,
                "start": _NODE_PROP,
                "depth": _DEPTH_PROP,
                "relationship": {
                    "type": "string",
                    "description": "Optional relationship type filter.",
                },
                "reverse": {
                    "type": "boolean",
                    "description": "Traverse incoming relationships.",
                    "default": False,
                },
            },
            ["path", "start"],
        ),
        "handler": _h_traverse_graph,
    },
    {
        "name": "analyze_graph",
        "description": "Run ODPG strategic and governance analysis checks.",
        "class": "safe",
        "inputSchema": _object_schema({"path": _PATH_PROP}, ["path"]),
        "handler": _h_analyze_graph,
    },
    {
        "name": "agent_context",
        "description": "Extract trusted ODPG context around a focus node.",
        "class": "safe",
        "inputSchema": _object_schema(
            {
                "path": _PATH_PROP,
                "node": _NODE_PROP,
                "depth": _DEPTH_PROP,
            },
            ["path", "node"],
        ),
        "handler": _h_agent_context,
    },
]


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None
