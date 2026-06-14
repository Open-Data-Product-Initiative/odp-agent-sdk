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

from ..agent import (
    explain_document,
    load_document,
    resolve_references,
    validate_document,
)
from ..contracts import (
    check_product_contract_alignment,
    extract_contract_schema,
    generate_product_contract_report,
    resolve_product_contracts,
    summarize_contract,
    validate_contract,
)
from ..generation import get_config, validate_config
from ..odpc import (
    build_catalog_artifacts,
    load_object_records,
    search_objects as _search_objects,
)
from ..odpg import (
    agent_context as _agent_context,
    analyze_graph as _analyze_graph,
    load_graph as _load_graph,
    search_graph_objects as _search_graph_objects,
    summarize_graph as _summarize_graph,
    traverse_graph as _traverse_graph,
    validate_graph as _validate_graph,
)
from ..odpv import (
    agent_vocabulary_context as _agent_vocabulary_context,
    check_vocabulary_relationship as _check_vocabulary_relationship,
    explain_vocabulary_term as _explain_vocabulary_term,
    load_vocabulary,
    resolve_vocabulary_term as _resolve_vocabulary_term,
    search_vocabulary,
)
from ..resources import get_resource, list_resources
from ..summary import load_summary

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


def _h_get_config(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(get_config(args.get("domain", "generation")))


def _h_validate_config(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(
        validate_config(args.get("domain", "generation"), args.get("path"))
    )


def _h_load_summary(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(load_summary(args["path"]))


def _h_catalog_artifacts(args: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = build_catalog_artifacts()
    include_content = bool(args.get("include_content", False))
    payload: Dict[str, Any] = {
        "spec": "odpc",
        "kind": "CatalogArtifacts",
        "artifact_count": len(artifacts),
        "artifacts": [
            {
                "path": path,
                "byte_size": len(content.encode("utf-8")),
                **({"content": content} if include_content else {}),
            }
            for path, content in artifacts.items()
        ],
    }
    return _json_envelope(payload)


def _h_search_terms(args: Dict[str, Any]) -> Dict[str, Any]:
    vocab = load_vocabulary()
    results = search_vocabulary(
        args["query"],
        limit=_int_arg(args, "limit", 10),
        data=vocab,
    )
    return _json_envelope(results)


def _h_resolve_vocabulary_term(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(_resolve_vocabulary_term(args["query"]))


def _h_explain_vocabulary_term(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(_explain_vocabulary_term(args["term"]))


def _h_check_vocabulary_relationship(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(
        _check_vocabulary_relationship(
            args["source"],
            args["verb"],
            args["target"],
        )
    )


def _h_vocabulary_term_context(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(_agent_vocabulary_context(args["term"]))


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


def _h_resolve_product_contracts(args: Dict[str, Any]) -> Dict[str, Any]:
    refs = resolve_product_contracts(args["path"])
    return _json_envelope({"count": len(refs), "contracts": [r.to_dict() for r in refs]})


def _h_validate_product_contracts(args: Dict[str, Any]) -> Dict[str, Any]:
    report = generate_product_contract_report(args["path"], args.get("contract"))
    return _json_envelope(
        {
            "passed": report.passed,
            "product_valid": report.product_valid,
            "contract_count": report.contract_count,
            "contract_valid": report.contract_valid,
            "contract_tests_run": report.contract_tests_run,
            "validations": [result.to_dict() for result in report.validations],
            "findings": [finding.to_dict() for finding in report.findings],
            "summary": report.summary,
        }
    )


def _h_check_product_contract_alignment(args: Dict[str, Any]) -> Dict[str, Any]:
    result = check_product_contract_alignment(args["path"], args["contract"])
    return _json_envelope(result.to_dict())


def _h_generate_product_contract_report(args: Dict[str, Any]) -> Dict[str, Any]:
    report = generate_product_contract_report(args["path"], args.get("contract"))
    return _json_envelope(report.to_dict())


def _h_summarize_product_contract_risks(args: Dict[str, Any]) -> Dict[str, Any]:
    report = generate_product_contract_report(args["path"], args.get("contract"))
    product_findings = [finding.to_dict() for finding in report.findings]
    alignment_findings = [
        {
            "code": finding.code,
            "message": finding.message,
            "severity": finding.severity,
            "path": finding.odps_path or finding.contract_path,
            "source": "open-data-products",
        }
        for alignment in report.alignments
        for finding in alignment.findings
    ]
    findings = product_findings + alignment_findings
    counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}
    for finding in findings:
        severity = str(finding.get("severity", "info"))
        if severity in counts:
            counts[severity] += 1
    return _json_envelope(
        {
            "passed": report.passed,
            "risk_counts": counts,
            "findings": findings,
            "summary": report.summary,
        }
    )


def _h_validate_data_contract(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(validate_contract(args["contract"]).to_dict())


def _h_summarize_data_contract(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(summarize_contract(args["contract"]).to_dict())


def _h_extract_data_contract_schema(args: Dict[str, Any]) -> Dict[str, Any]:
    return _json_envelope(extract_contract_schema(args["contract"]).to_dict())


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
_CONTRACT_PROP = {
    "type": "string",
    "description": "Filesystem path or URL to a Data Contract file.",
}
_TERM_PROP = {"type": "string", "description": "ODPV term id."}

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
        "name": "get_config",
        "description": "Inspect safe SDK config template and resolved provider/model settings.",
        "class": "safe",
        "inputSchema": _object_schema(
            {
                "domain": {
                    "type": "string",
                    "description": "Config domain to inspect. Currently supports generation.",
                    "default": "generation",
                }
            }
        ),
        "handler": _h_get_config,
    },
    {
        "name": "validate_config",
        "description": "Validate safe SDK config files without contacting providers.",
        "class": "safe",
        "inputSchema": _object_schema(
            {
                "domain": {
                    "type": "string",
                    "description": "Config domain to validate. Currently supports generation.",
                    "default": "generation",
                },
                "path": {
                    "type": "string",
                    "description": "Optional user-owned config file path.",
                },
            }
        ),
        "handler": _h_validate_config,
    },
    {
        "name": "load_summary",
        "description": "Return lightweight metadata (size, hash, spec) for a document; never the body.",
        "class": "safe",
        "inputSchema": _object_schema({"path": _PATH_PROP}, ["path"]),
        "handler": _h_load_summary,
    },
    {
        "name": "catalog_artifacts",
        "description": "Return derived ODPC catalog schema artifact metadata and optional content.",
        "class": "safe",
        "inputSchema": _object_schema(
            {
                "include_content": {
                    "type": "boolean",
                    "description": "Include generated artifact content in the response.",
                    "default": False,
                }
            }
        ),
        "handler": _h_catalog_artifacts,
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
        "name": "resolve_vocabulary_term",
        "description": "Resolve text, aliases, or ids to a canonical ODPV term packet.",
        "class": "safe",
        "inputSchema": _object_schema({"query": _QUERY_PROP}, ["query"]),
        "handler": _h_resolve_vocabulary_term,
    },
    {
        "name": "explain_vocabulary_term",
        "description": "Return one canonical ODPV term packet by id.",
        "class": "safe",
        "inputSchema": _object_schema({"term": _TERM_PROP}, ["term"]),
        "handler": _h_explain_vocabulary_term,
    },
    {
        "name": "check_vocabulary_relationship",
        "description": "Check ODPV relationship domain/range compatibility.",
        "class": "safe",
        "inputSchema": _object_schema(
            {
                "source": {
                    "type": "string",
                    "description": "Source ODPV object type.",
                },
                "verb": {
                    "type": "string",
                    "description": "Relationship id, alias, or search text.",
                },
                "target": {
                    "type": "string",
                    "description": "Target ODPV object type.",
                },
            },
            ["source", "verb", "target"],
        ),
        "handler": _h_check_vocabulary_relationship,
    },
    {
        "name": "vocabulary_term_context",
        "description": "Return an agent-ready ODPV term context packet.",
        "class": "safe",
        "inputSchema": _object_schema({"term": _TERM_PROP}, ["term"]),
        "handler": _h_vocabulary_term_context,
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
    {
        "name": "resolve_product_contracts",
        "description": "Resolve native and extension Data Contract references from an ODPS product.",
        "class": "safe",
        "inputSchema": _object_schema({"path": _PATH_PROP}, ["path"]),
        "handler": _h_resolve_product_contracts,
    },
    {
        "name": "validate_product_contracts",
        "description": "Validate an ODPS product and its referenced or explicit Data Contract.",
        "class": "safe",
        "inputSchema": _object_schema(
            {"path": _PATH_PROP, "contract": _CONTRACT_PROP}, ["path"]
        ),
        "handler": _h_validate_product_contracts,
    },
    {
        "name": "check_product_contract_alignment",
        "description": "Check static ODPS-to-Data Contract alignment without live source tests.",
        "class": "safe",
        "inputSchema": _object_schema(
            {"path": _PATH_PROP, "contract": _CONTRACT_PROP}, ["path", "contract"]
        ),
        "handler": _h_check_product_contract_alignment,
    },
    {
        "name": "generate_product_contract_report",
        "description": "Generate a static product-level Data Contract report.",
        "class": "safe",
        "inputSchema": _object_schema(
            {"path": _PATH_PROP, "contract": _CONTRACT_PROP}, ["path"]
        ),
        "handler": _h_generate_product_contract_report,
    },
    {
        "name": "summarize_product_contract_risks",
        "description": "Summarize product-contract findings by severity for agent triage.",
        "class": "safe",
        "inputSchema": _object_schema(
            {"path": _PATH_PROP, "contract": _CONTRACT_PROP}, ["path"]
        ),
        "handler": _h_summarize_product_contract_risks,
    },
    {
        "name": "validate_data_contract",
        "description": "Validate one Data Contract through the optional datacontract-cli adapter.",
        "class": "safe",
        "inputSchema": _object_schema({"contract": _CONTRACT_PROP}, ["contract"]),
        "handler": _h_validate_data_contract,
    },
    {
        "name": "summarize_data_contract",
        "description": "Summarize a local Data Contract without returning the full body.",
        "class": "safe",
        "inputSchema": _object_schema({"contract": _CONTRACT_PROP}, ["contract"]),
        "handler": _h_summarize_data_contract,
    },
    {
        "name": "extract_data_contract_schema",
        "description": "Extract normalized schema models and fields from a local Data Contract.",
        "class": "safe",
        "inputSchema": _object_schema({"contract": _CONTRACT_PROP}, ["contract"]),
        "handler": _h_extract_data_contract_schema,
    },
]


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None
