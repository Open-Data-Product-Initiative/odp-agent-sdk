"""MCP handlers for DCAT and DPROD interoperability workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .._io import load_mapping
from ..dcat import discover_dcat_catalog, wrap_dcat_resource
from ..dprod import (
    discover_dprod_catalog,
    validate_dprod,
    wrap_dprod_resource,
    write_dprod_export,
)
from ._response import json_envelope, redact_local_paths


def discover_dcat_catalog_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze one supplied DCAT catalog without writing artifacts."""
    return json_envelope(
        redact_local_paths(discover_dcat_catalog(args["source"]).to_dict())
    )


def wrap_dcat_resource_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """Write one ODPS draft from an explicit DCAT resource selection."""
    result = wrap_dcat_resource(
        args["source"],
        args["resource"],
        args["output"],
        overwrite=bool(args.get("overwrite", False)),
        use_ai=bool(args.get("enrich", False)),
        extend=bool(args.get("full_draft", False)),
        config=args.get("config"),
    )
    payload = result.to_dict()
    payload["source"] = Path(args["source"]).name
    payload["output"] = Path(args["output"]).name
    return json_envelope(redact_local_paths(payload))


def discover_dprod_catalog_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze supplied DPROD RDF without writing artifacts."""
    return json_envelope(
        redact_local_paths(discover_dprod_catalog(args["source"]).to_dict())
    )


def validate_dprod_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """Validate supplied DPROD RDF without writing artifacts."""
    return json_envelope(validate_dprod(args["source"]).to_dict())


def wrap_dprod_resource_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """Write one ODPS draft from one explicit DPROD product."""
    result = wrap_dprod_resource(
        args["source"],
        args["resource"],
        args["output"],
        overwrite=bool(args.get("overwrite", False)),
    )
    payload = result.to_dict()
    payload["source"] = Path(args["source"]).name
    payload["output"] = Path(args["output"]).name
    return json_envelope(redact_local_paths(payload))


def export_dprod_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """Write deterministic DPROD serializations from an ODPS source mapping."""
    payload = write_dprod_export(
        load_mapping(Path(args["source"]), root_name="ODPS document"),
        args["output"],
        overwrite=bool(args.get("overwrite", False)),
    )
    payload["turtle_output"] = Path(str(payload["turtle_output"])).name
    payload["jsonld_output"] = Path(str(payload["jsonld_output"])).name
    return json_envelope(payload)
