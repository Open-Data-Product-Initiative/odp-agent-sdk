"""Top-level command line interface for agent-oriented SDK workflows."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from . import __version__
from ._activity import (
    ActivityContext,
    ActivityEvent,
    utc_timestamp,
    write_activity_event,
)
from .agent import (
    explain_document,
    load_document,
    resolve_references,
    validate_document,
)
from .cli_core import (
    print_error_payload as _print_error_payload,
    split_csv as _split_csv,
)
from .cli_product import add_product_subparser, handle_product_command
from .odpg.graph import (
    collect_relationship_types,
    graph_metadata,
    graph_payload,
    localized_text,
)
from .odps import OpenDataProduct
from .resources import get_resource, list_resources
from .summary import load_summary

DEFAULT_GENERATION_INPUT = "open_data_products/generation/source_docs/"
DEFAULT_GENERATION_OUTPUT = "open_data_products/generation/fragments/"

if TYPE_CHECKING:
    from .results import ValidationResult


TOP_LEVEL_HELP = """\
Common workflows:
  Validate one artifact:
    open-data-products validate product.yaml

  Generate ODPC fragments from source notes:
    open-data-products generate --input source_docs/ --kind product-reference --output generated/

  Generate a full ODPS product draft:
    open-data-products generate --input product.md --kind odps-product --output products/

  Build catalog and graph review artifacts:
    open-data-products odpc-build fragments/ --output catalog.yaml --html catalog.html --toon catalog.toon --gcf catalog.gcf
    open-data-products odpg-build fragments/ --output graph.yaml --toon graph.toon --gcf graph.gcf
    open-data-products odpg-generate graph.yaml --output graph-explorer.html

  Build a portfolio workspace:
    open-data-products portfolio build --objectives inputs/objectives/ --use-cases inputs/use-cases/ --signals inputs/signals/ --products inputs/products/ --output portfolio/

  Exchange OKF context bundles:
    open-data-products okf-validate knowledge-bundle/ --json
    open-data-products okf-import knowledge-bundle/ --output source_docs/
    open-data-products okf-export catalog.yaml --output okf-bundle/

  Use --json when scripting or handing command output to agents.

Core document commands:
  validate     Validate ODPS, ODPC, ODPG, or ODPV documents
  explain      Print an agent-readable document summary
  refs         List document references
  summary      Return lightweight file metadata

OKF context bundle commands:
  okf-validate         Validate an Open Knowledge Format bundle
  okf-summary          Summarize OKF concepts without returning bodies
  okf-import           Write OKF concepts as generation source documents
  okf-export           Export ODPC catalog or portfolio artifacts as OKF
  resources --id okf.spec        Return OKF adapter/spec reference metadata
  MCP validate_okf_bundle        Validate OKF bundles from agents
  MCP list_okf_concepts          List concept metadata without Markdown bodies

ODPC catalog commands:
  odpc-build           Build one ODPC catalog from YAML/JSON fragments
  odpc-summary         Summarize catalog metadata and item counts
  odpc-search          Search bundled catalog object guidance
  odpc-artifacts       Generate or check derived catalog schema artifacts
  resources --id odpc.objects   Return catalog object guidance records
  MCP search_objects            Search ODPC guidance from agents

ODPV vocabulary commands:
  odpv-summary         Summarize vocabulary sections and term counts
  odpv-search          Search bundled vocabulary terms
  odpv-resolve         Resolve text or aliases to a canonical term
  odpv-explain         Return one canonical term packet
  odpv-relationship    Check relationship domain/range compatibility
  odpv-context         Return an agent-ready term context packet
  resources --id odpv.terms     Return vocabulary term records
  MCP search_terms              Search ODPV terms from agents

ODPR recipe commands:
  recipe list           List workflow recipe metadata
  recipe validate       Validate an ODPR Recipe, Provider, or RecipeCatalog
  recipe catalog        Build a metadata-only RecipeCatalog
  recipe init           Create a workspace from a packaged starter recipe
  recipe explain        Explain a starter or local recipe without executing it
  recipe plan           Alias for recipe run --dry-run
  recipe dry-run        Alias for recipe run --dry-run
  resources --id odpr.schema.yaml          Return the bundled ODPR YAML schema
  resources --id odpr.recipe-config-template  Return the recipe runner config template
  resources --id odpr.recipes              Return bundled ODPR recipe guidance records

Discovery and agent commands:
  resources    List bundled schemas, vocabularies, and indexes
  config       Show or copy editable SDK config templates
  recipe       List, validate, and dry-run workflow recipes
  manifest     Emit the MCP/agent manifest
  serve        Run the MCP server over stdio

LLM generation commands:
  generate     Use configured LLM prompts to create selected YAML artifacts

ODPG graph commands:
  odpg-build           Build one ODPG graph from ODPC fragments with LLM-inferred edges
  odpg-summary         Summarize graph metadata and relationship counts
  odpg-traverse        Discover relationship paths from a focus node
  odpg-analyze         Run governance and strategic graph checks
  odpg-agent-context   Extract graph context around a node for agents
  odpg-generate        Generate a standalone graph explorer HTML file
  odpg-convert         Convert JSON-LD, GraphML, GraphSON, RDF, Cypher, GQL, or Gremlin to ODPG YAML

Product/Data Contract commands:
  product resolve-contracts   Resolve Data Contract references
  product contract-report     Generate a product-contract report
  product audit               Run static product and contract checks
  product check-contract      Validate a product plus an external contract
  product align-contract      Check static ODPS/Data Contract alignment
  product contract-schema     Summarize a Data Contract schema
  product export-contract     Export through datacontract-cli

Portfolio workflow commands:
  portfolio build     Build a portfolio workspace from source lanes
  portfolio refresh   Refresh a portfolio workspace from saved source lanes
  portfolio sync      Sync edited YAML artifacts without calling an LLM
  portfolio localize  Localize portfolio HTML without changing YAML artifacts
  portfolio render    Render one static portfolio index.html
  portfolio explain   Summarize a portfolio workspace

Examples:
  open-data-products validate product.yaml
  open-data-products explain catalog.yaml
  open-data-products odpc-build fragments/ --output catalog.yaml
  open-data-products odpc-build fragments/ --output catalog.yaml --html catalog.html
  open-data-products odpc-build fragments/ --output catalog.yaml --toon catalog.toon --gcf catalog.gcf
  open-data-products odpc-summary catalog.yaml
  open-data-products odpc-search "catalog data" --limit 3
  open-data-products odpc-artifacts open_data_products/generation/fragments/ --check
  open-data-products okf-validate knowledge-bundle/ --json
  open-data-products okf-summary knowledge-bundle/ --json
  open-data-products okf-import knowledge-bundle/ --output source_docs/
  open-data-products okf-export catalog.yaml --output okf-bundle/
  open-data-products resources --id okf.spec --json
  open-data-products odpv-summary
  open-data-products odpv-search "governance policy risk" --limit 3
  open-data-products odpv-context DataProduct
  open-data-products resources --id odpc.objects --json
  open-data-products resources --id odpv.terms --json
  open-data-products config generation --copy-to my-generation.config.yaml
  open-data-products config generation --copy-prompts-to prompts/
  open-data-products resources --id odpr.schema.yaml --json
  open-data-products resources --id odpr.recipe-config-template --json
  open-data-products recipe search localization --json
  open-data-products recipe search --id RecipeCatalog --json
  open-data-products recipe list --json
  open-data-products recipe init build-data-product-portfolio --json
  open-data-products recipe init build-data-product-portfolio --parameterized --json
  open-data-products recipe explain build-data-product-portfolio --json
  open-data-products recipe plan --json
  open-data-products recipe list --config recipes.config.yaml --json
  open-data-products recipe validate recipes/release-portfolio-review.yaml --json
  open-data-products recipe run --allow-llm --approve-review --json
  open-data-products resources --json
  open-data-products generate --input source_docs/ --kind product-reference --output generated/
  open-data-products generate --input product.md --kind odps-product --output generated/
  open-data-products generate --input transcripts/ --kind odps-product --profile complete-draft --include-components SLA,dataQuality,pricingPlans --output products/
  open-data-products generate --input use-case.md --kind use-case --output generated/
  open-data-products generate --config my-generation.config.yaml --provider groq --model openai/gpt-oss-120b --input source_docs/ --kind signal --output generated/
  open-data-products generate --config my-generation.config.yaml --prompts prompts/ --input source_docs/ --kind graph --output generated/
  open-data-products odpg-build fragments/ --output graph.yaml --toon graph.toon --gcf graph.gcf
  open-data-products odpg-agent-context graph.yaml --node DATA-PRODUCT-001
  open-data-products odpg-generate graph.yaml --output graph-explorer.html
  open-data-products odpg-convert --input graph.graphml --output graph.yaml
  open-data-products portfolio build --objectives inputs/objectives/ --use-cases inputs/use-cases/ --signals inputs/signals/ --products inputs/products/ --output generated/portfolio/
  open-data-products portfolio sync generated/portfolio/
  open-data-products portfolio localize generated/portfolio/ --languages "fi,sv" --provider claude --model claude-sonnet-4-5
  open-data-products portfolio render generated/portfolio/
  open-data-products product contract-report product.yaml contract.yaml --json
  open-data-products serve
"""


def _explain_json_payload(document: object, path: str) -> Dict[str, object]:
    """Return structured JSON payload for explain output."""
    result = validate_document(document, path=path)
    payload: Dict[str, object] = {
        "spec": result.spec,
        "kind": result.kind,
        "path": path,
    }
    if result.version is not None:
        payload["version"] = result.version

    if isinstance(document, OpenDataProduct):
        details = document.product_details
        payload.update(
            {
                "schema": document.schema,
                "version": str(document.version),
                "product": {
                    "id": details.product_id,
                    "name": details.name,
                    "status": details.status,
                    "visibility": details.visibility,
                    "type": details.type,
                },
                "components": document.component_count,
                "compliance_level": document.compliance_level,
                "production_ready": document.is_production_ready,
                "data_access": "configured" if document.data_access else None,
            }
        )
        if document.product_strategy:
            payload["strategy"] = {
                "objectives": len(document.product_strategy.objectives),
                "product_kpis": len(document.product_strategy.product_kpis),
            }
        return payload

    if result.spec == "odpg" and isinstance(document, dict):
        graph = graph_payload(document)
        metadata = graph_metadata(document)
        node_types = sorted(
            {
                str(node.get("type"))
                for node in graph.get("nodes", [])
                if isinstance(node, dict) and node.get("type")
            }
        )
        node_references = [
            str(node.get("$ref") or node.get("ref"))
            for node in graph.get("nodes", [])
            if isinstance(node, dict) and (node.get("$ref") or node.get("ref"))
        ]
        payload.update(
            {
                "schema": document.get("schema", ""),
                "graph": {
                    "id": metadata.get("id", ""),
                    "name": localized_text(metadata.get("name")),
                    "description": localized_text(metadata.get("description")),
                    "domain": localized_text(metadata.get("domain")),
                    "purpose": localized_text(metadata.get("purpose")),
                    "status": metadata.get("status", ""),
                    "visibility": metadata.get("visibility", ""),
                },
                "nodes": len(graph.get("nodes", [])),
                "edges": len(graph.get("edges", [])),
                "node_types": node_types,
                "relationship_types": collect_relationship_types(document),
                "node_references": node_references,
            }
        )
        return payload

    payload["summary"] = explain_document(document, path=Path(path))
    return payload


def _print_summary_report(summary: Dict[str, object]) -> None:
    """Print lightweight document metadata for humans."""
    lines = [
        f"File: {summary['path']}",
        f"Spec: {summary['spec']}",
        f"Kind: {summary['kind'] or '(unknown)'}",
        f"ID: {summary['id'] or '(not set)'}",
        f"Bytes: {summary['byte_size']}",
        f"Lines: {summary['line_count']}",
        f"SHA-256: {summary['sha256']}",
    ]
    print("\n".join(lines))


def _portfolio_validation_mode(args: argparse.Namespace) -> str:
    """Return portfolio schema validation handling mode for a CLI invocation."""
    return "strict" if getattr(args, "strict_validation", False) else "warn"


def _portfolio_exit_code(payload: Dict[str, object], args: argparse.Namespace) -> int:
    """Return portfolio command exit code for the selected validation mode."""
    if _portfolio_validation_mode(args) == "strict" and not payload.get("valid", False):
        return 1
    return 0


def _activity_command_id(args: argparse.Namespace) -> str:
    """Return the canonical command id for a parsed CLI namespace."""
    command = str(getattr(args, "command", "") or "cli")
    for nested in ("recipe_command", "portfolio_command", "product_command"):
        value = getattr(args, nested, None)
        if value:
            return f"{command}.{value}"
    return command


def _activity_command_id_from_argv(argv: List[str]) -> str:
    """Return a best-effort command id before argparse has a namespace."""
    for item in argv:
        if item in {"--help", "-h", "--version", "-V"}:
            return "cli"
        if not item.startswith("-"):
            return item
    return "cli"


def _activity_details_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    """Return safe default activity details from parsed CLI arguments."""
    details: Dict[str, Any] = {}
    for name in (
        "document",
        "bundle",
        "source",
        "output",
        "workspace",
        "input_dir",
        "source_dir",
        "kind",
        "provider",
        "model",
    ):
        value = getattr(args, name, None)
        if value is not None:
            details[name] = value
    if getattr(args, "json", False):
        details["json"] = True
    return details


def _activity_level(exit_code: int, context: ActivityContext) -> str:
    """Return the activity classification for a CLI exit code and context."""
    if exit_code != 0:
        return "FAILED"
    warnings = context.details.get("warnings")
    errors = context.details.get("errors")
    if context.warning or (isinstance(warnings, int) and warnings > 0):
        return "WARNING"
    if isinstance(errors, int) and errors > 0:
        return "WARNING"
    return "SUCCESS"


def _activity_message(command: str, level: str, context: ActivityContext) -> str:
    """Return a concise activity message."""
    if context.message:
        return context.message
    if level == "FAILED":
        return f"{command} failed"
    if level == "WARNING":
        return f"{command} completed with warnings"
    return f"{command} completed"


def _write_cli_activity(
    command: str,
    context: ActivityContext,
    exit_code: int,
    duration_ms: int,
) -> None:
    """Write one CLI activity event, warning but continuing on logging errors."""
    level = _activity_level(exit_code, context)
    try:
        write_activity_event(
            ActivityEvent(
                timestamp=utc_timestamp(),
                level=level,
                source="cli",
                command=command,
                exit_code=exit_code,
                duration_ms=duration_ms,
                message=_activity_message(command, level, context),
                details=context.details,
            )
        )
    except OSError as exc:
        print(f"Warning: could not write SDK activity log: {exc}", file=sys.stderr)


def _write_llm_invocation_activity(
    args: argparse.Namespace,
    settings: Any,
    *,
    phase: Optional[str] = None,
) -> None:
    """Write an activity line for a CLI LLM provider invocation."""
    details = {
        "parent_command": _activity_command_id(args),
        "provider": getattr(settings, "provider", None),
        "provider_type": getattr(settings, "provider_type", None),
        "model": getattr(settings, "model", None),
    }
    if phase:
        details["phase"] = phase
    kind = getattr(args, "kind", None)
    if kind:
        details["kind"] = kind
    try:
        write_activity_event(
            ActivityEvent(
                timestamp=utc_timestamp(),
                level="INFO",
                source="cli",
                command="llm.invoke",
                exit_code=0,
                duration_ms=0,
                message="LLM provider invoked",
                details=details,
            )
        )
    except OSError as exc:
        print(f"Warning: could not write SDK activity log: {exc}", file=sys.stderr)


def _finalize_activity(
    args: argparse.Namespace,
    context: ActivityContext,
    start_time: float,
    exit_code: int,
) -> int:
    """Write the terminal activity event for a parsed CLI command."""
    context.details = {**_activity_details_from_args(args), **context.details}
    duration_ms = int((time.monotonic() - start_time) * 1000)
    _write_cli_activity(_activity_command_id(args), context, exit_code, duration_ms)
    return exit_code


def _log_parse_failure(argv: List[str], exit_code: int, start_time: float) -> None:
    """Write an activity event for argparse failures."""
    if exit_code == 0:
        return
    duration_ms = int((time.monotonic() - start_time) * 1000)
    context = ActivityContext(
        details={"argument_count": len(argv)},
        message="CLI argument parsing failed",
    )
    _write_cli_activity(
        _activity_command_id_from_argv(argv),
        context,
        exit_code,
        duration_ms,
    )


def _print_odpg_summary(summary: Dict[str, object]) -> None:
    """Print an ODPG summary for humans."""
    print(f"ODPG Graph: {summary.get('name') or summary.get('id') or '(unnamed)'}")
    print(f"ID: {summary.get('id', '(missing)')}")
    print(f"Nodes: {summary.get('nodeCount', 0)}")
    print(f"Edges: {summary.get('edgeCount', 0)}")
    node_types = summary.get("nodeTypes")
    if isinstance(node_types, dict) and node_types:
        rendered = ", ".join(
            f"{key}={value}" for key, value in sorted(node_types.items())
        )
        print(f"Node types: {rendered}")
    edge_types = summary.get("edgeTypes")
    if isinstance(edge_types, dict) and edge_types:
        rendered = ", ".join(
            f"{key}={value}" for key, value in sorted(edge_types.items())
        )
        print(f"Edge types: {rendered}")


def _print_odpg_paths(start: str, paths: List[Dict[str, object]]) -> None:
    """Print ODPG traversal paths for humans."""
    print(f"Start: {start}")
    print(f"Paths: {len(paths)}")
    for path in paths:
        nodes = path.get("nodes") if isinstance(path, dict) else None
        relationships = path.get("relationships") if isinstance(path, dict) else None
        if isinstance(nodes, list) and nodes:
            print(f"- {' -> '.join(str(node) for node in nodes)}")
        elif isinstance(relationships, list) and relationships:
            print(f"- {len(relationships)} relationship(s)")


PORTFOLIO_HELP = """\
Portfolio workflow commands:
  build       Build a portfolio workspace from source lanes
  refresh     Refresh a portfolio workspace from saved source lanes
  sync        Sync edited YAML artifacts without calling an LLM
  localize    Localize portfolio HTML without changing YAML artifacts
  render      Render one static browser-viewable portfolio page
  explain     Summarize portfolio artifacts, counts, and browser entry point

Examples:
  open-data-products portfolio build --objectives inputs/objectives/ --use-cases inputs/use-cases/ --signals inputs/signals/ --products inputs/products/ --output generated/portfolio/
  open-data-products portfolio build --objectives inputs/objectives/ --products inputs/products/ --output generated/portfolio/ --strict-validation
  open-data-products portfolio refresh generated/portfolio/
  open-data-products portfolio refresh generated/portfolio/ --all-sources
  open-data-products portfolio sync generated/portfolio/
  open-data-products portfolio localize generated/portfolio/ --languages "fi,sv" --provider claude --model claude-sonnet-4-5
  open-data-products portfolio render generated/portfolio/
  open-data-products portfolio explain generated/portfolio/
"""


def main(argv: Optional[List[str]] = None) -> int:
    """Run the top-level Open Data Products CLI."""
    cli_argv = list(sys.argv[1:] if argv is None else argv)
    parse_start_time = time.monotonic()
    parser = argparse.ArgumentParser(
        prog="open-data-products",
        description=(
            "Validate, inspect, and expose Open Data Product family artifacts."
        ),
        epilog=TOP_LEVEL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        metavar="COMMAND",
        required=True,
    )

    validate_parser = subparsers.add_parser("validate", help="Validate a document")
    validate_parser.add_argument("document", help="Path to an ODPS, ODPC, or ODPG file")
    validate_parser.add_argument("--json", action="store_true", help="Emit JSON")

    explain_parser = subparsers.add_parser("explain", help="Explain a document")
    explain_parser.add_argument("document", help="Path to an ODPS, ODPC, or ODPG file")
    explain_parser.add_argument("--json", action="store_true", help="Emit JSON")

    refs_parser = subparsers.add_parser("refs", help="List document references")
    refs_parser.add_argument("document", help="Path to an ODPS, ODPC, or ODPG file")
    refs_parser.add_argument("--json", action="store_true", help="Emit JSON")

    resources_parser = subparsers.add_parser("resources", help="List SDK resources")
    resources_parser.add_argument("--json", action="store_true", help="Emit JSON")
    resources_parser.add_argument("--id", help="Return one resource by id")

    summary_parser = subparsers.add_parser(
        "summary", help="Lightweight artifact reference for a document"
    )
    summary_parser.add_argument("document", help="Path to an ODP document")
    summary_parser.add_argument("--json", action="store_true", help="Emit JSON")

    okf_validate_parser = subparsers.add_parser(
        "okf-validate", help="Validate an OKF bundle"
    )
    okf_validate_parser.add_argument("bundle", help="Path to an OKF bundle directory")
    okf_validate_parser.add_argument("--json", action="store_true", help="Emit JSON")

    okf_summary_parser = subparsers.add_parser(
        "okf-summary", help="Summarize an OKF bundle without concept bodies"
    )
    okf_summary_parser.add_argument("bundle", help="Path to an OKF bundle directory")
    okf_summary_parser.add_argument("--json", action="store_true", help="Emit JSON")

    okf_import_parser = subparsers.add_parser(
        "okf-import", help="Write OKF concepts as generation source documents"
    )
    okf_import_parser.add_argument("bundle", help="Path to an OKF bundle directory")
    okf_import_parser.add_argument(
        "--output",
        required=True,
        help="Directory for generated Markdown source documents.",
    )
    okf_import_parser.add_argument("--json", action="store_true", help="Emit JSON")

    okf_export_parser = subparsers.add_parser(
        "okf-export", help="Export ODPC catalog or portfolio artifacts as OKF"
    )
    okf_export_parser.add_argument(
        "source", help="ODPC catalog file or portfolio workspace directory"
    )
    okf_export_parser.add_argument(
        "--output", required=True, help="Directory for the OKF bundle."
    )
    okf_export_parser.add_argument("--json", action="store_true", help="Emit JSON")

    config_parser = subparsers.add_parser(
        "config", help="Show or copy SDK config templates"
    )
    config_parser.add_argument(
        "domain",
        nargs="?",
        choices=["generation", "recipes"],
        default="generation",
        help="Config domain to inspect. Defaults to generation.",
    )
    config_parser.add_argument(
        "--config",
        dest="config_path",
        help="Inspect a user-owned config file instead of the bundled template.",
    )
    config_parser.add_argument(
        "--copy-to",
        dest="copy_to",
        metavar="PATH",
        help="Copy the bundled config template to a user-editable file.",
    )
    config_parser.add_argument(
        "--copy",
        dest="copy_to",
        metavar="PATH",
        help=argparse.SUPPRESS,
    )
    config_parser.add_argument(
        "--copy-prompts-to",
        metavar="DIR",
        help="Copy bundled generation prompts to a user-editable folder.",
    )
    config_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow --copy-to to replace an existing file.",
    )
    config_parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the config file without contacting the LLM provider.",
    )
    config_parser.add_argument(
        "--print",
        action="store_true",
        help="Print the raw YAML config template or selected config file.",
    )
    config_parser.add_argument("--json", action="store_true", help="Emit JSON")

    recipe_parser = subparsers.add_parser(
        "recipe",
        help="List, validate, and dry-run workflow recipes",
    )
    recipe_subparsers = recipe_parser.add_subparsers(
        dest="recipe_command",
        metavar="RECIPE_COMMAND",
        required=True,
    )
    recipe_list_parser = recipe_subparsers.add_parser(
        "list",
        help="List packaged starters or recipe metadata from recipes.config.yaml",
    )
    recipe_list_parser.add_argument(
        "--config",
        help="Recipe runner config YAML. Defaults to recipes.config.yaml when present.",
    )
    recipe_list_parser.add_argument(
        "--group",
        help="Assign listed recipes to this RecipeCatalog group id.",
    )
    recipe_list_parser.add_argument(
        "--starters",
        action="store_true",
        help="List packaged starter recipes from the ODPR RecipeCatalog.",
    )
    recipe_list_parser.add_argument(
        "--catalog",
        help="Starter RecipeCatalog YAML path for --starters.",
    )
    recipe_list_parser.add_argument("--json", action="store_true", help="Emit JSON")
    recipe_validate_parser = recipe_subparsers.add_parser(
        "validate",
        help="Validate one ODPR Recipe, Provider, or RecipeCatalog",
    )
    recipe_validate_parser.add_argument(
        "recipe",
        nargs="?",
        help="ODPR YAML or JSON file. Uses recipes.defaultRecipe when omitted.",
    )
    recipe_validate_parser.add_argument(
        "--config",
        help="Optional recipe runner config YAML.",
    )
    recipe_validate_parser.add_argument("--json", action="store_true", help="Emit JSON")
    recipe_catalog_parser = recipe_subparsers.add_parser(
        "catalog",
        help="Build a metadata-only ODPR RecipeCatalog",
    )
    recipe_catalog_parser.add_argument(
        "--config",
        help="Recipe runner config YAML. Defaults to recipes.config.yaml when present.",
    )
    recipe_catalog_parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output RecipeCatalog YAML path.",
    )
    recipe_catalog_parser.add_argument(
        "--group",
        help="Assign catalog recipes to this RecipeCatalog group id.",
    )
    recipe_catalog_parser.add_argument("--json", action="store_true", help="Emit JSON")
    recipe_starter_check_parser = recipe_subparsers.add_parser(
        "starter-catalog-check",
        help="Validate the packaged starter RecipeCatalog and referenced recipes.",
    )
    recipe_starter_check_parser.add_argument(
        "--catalog",
        help="Starter RecipeCatalog YAML path. Defaults to the packaged catalog.",
    )
    recipe_starter_check_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON",
    )
    recipe_init_parser = recipe_subparsers.add_parser(
        "init",
        help="Create a workspace from a packaged starter recipe",
    )
    recipe_init_parser.add_argument(
        "starter",
        help="Starter recipe id, English name, or folder name.",
    )
    recipe_init_parser.add_argument(
        "--output",
        "-o",
        help="Output workspace directory. Defaults to recipes/<starter-folder>.",
    )
    recipe_init_parser.add_argument(
        "--force",
        action="store_true",
        help="Allow copying into an existing workspace directory.",
    )
    recipe_init_parser.add_argument(
        "--parameterized",
        action="store_true",
        help="Generate recipe.values.yaml and values.schema.yaml.",
    )
    recipe_init_parser.add_argument(
        "--catalog",
        help="Starter RecipeCatalog YAML path. Defaults to the packaged catalog.",
    )
    recipe_init_parser.add_argument("--json", action="store_true", help="Emit JSON")
    recipe_explain_parser = recipe_subparsers.add_parser(
        "explain",
        help="Explain a starter or local recipe without executing it",
    )
    recipe_explain_parser.add_argument(
        "recipe",
        help="Starter recipe id/name/folder or local recipe YAML path.",
    )
    recipe_explain_parser.add_argument(
        "--catalog",
        help="Starter RecipeCatalog YAML path. Defaults to the packaged catalog.",
    )
    recipe_explain_parser.add_argument("--json", action="store_true", help="Emit JSON")
    recipe_search_parser = recipe_subparsers.add_parser(
        "search",
        help="Search bundled ODPR recipe guidance",
    )
    recipe_search_parser.add_argument(
        "query",
        nargs="*",
        help="Keyword query for bundled ODPR recipe guidance.",
    )
    recipe_search_parser.add_argument(
        "--id",
        dest="guidance_id",
        help="Return one guidance record by id.",
    )
    recipe_search_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of search matches.",
    )
    recipe_search_parser.add_argument("--json", action="store_true", help="Emit JSON")
    recipe_run_parser = recipe_subparsers.add_parser(
        "run",
        help="Plan or execute one workflow recipe",
    )
    recipe_run_parser.add_argument(
        "recipe",
        nargs="?",
        help=(
            "Recipe YAML file. Uses ./recipe.yaml or recipes.defaultRecipe when "
            "omitted."
        ),
    )
    recipe_run_parser.add_argument(
        "--config",
        help="Optional recipe runner config YAML.",
    )
    recipe_run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit the resolved plan without writes or provider calls.",
    )
    recipe_run_parser.add_argument(
        "--execute",
        action="store_true",
        help="Run supported state-changing steps and write a run manifest.",
    )
    recipe_run_parser.add_argument(
        "--allow-llm",
        action="store_true",
        help="Permit LLM-backed recipe steps to call configured providers.",
    )
    recipe_run_parser.add_argument(
        "--approve-review",
        action="store_true",
        help="Permit steps marked review-needed to execute after approval.",
    )
    recipe_run_parser.add_argument(
        "--provider-ref",
        help="Provider reference override for compatible LLM-backed steps.",
    )
    recipe_run_parser.add_argument(
        "--model",
        help="Model override for compatible LLM-backed steps.",
    )
    recipe_run_parser.add_argument("--json", action="store_true", help="Emit JSON")
    for alias_name in ("plan", "dry-run"):
        recipe_plan_parser = recipe_subparsers.add_parser(
            alias_name,
            help="Alias for recipe run --dry-run",
        )
        recipe_plan_parser.add_argument(
            "recipe",
            nargs="?",
            help=(
                "Recipe YAML file. Uses ./recipe.yaml or recipes.defaultRecipe when "
                "omitted."
            ),
        )
        recipe_plan_parser.add_argument(
            "--config",
            help="Optional recipe runner config YAML.",
        )
        recipe_plan_parser.add_argument(
            "--provider-ref",
            help="Provider reference override for compatible LLM-backed steps.",
        )
        recipe_plan_parser.add_argument(
            "--model",
            help="Model override for compatible LLM-backed steps.",
        )
        recipe_plan_parser.add_argument("--json", action="store_true", help="Emit JSON")

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate selected YAML artifacts with configured LLMs",
        description="Generate selected YAML artifacts with configured LLMs.",
    )
    generate_parser.add_argument(
        "source_dir",
        nargs="?",
        help="Markdown/text source file or folder",
    )
    generate_parser.add_argument(
        "--input",
        "-i",
        dest="input_dir",
        help=(
            "Markdown/text source file or folder. Defaults to "
            f"{DEFAULT_GENERATION_INPUT}."
        ),
    )
    generate_parser.add_argument(
        "--config",
        help="Generation config YAML file with provider and path settings.",
    )
    generate_parser.add_argument(
        "--provider",
        help=(
            "LLM provider override. Defaults to config provider or ollama. "
            "Use a configured provider name such as openai, openrouter, groq, "
            "zai, sakana-fugu, or claude."
        ),
    )
    generate_parser.add_argument(
        "--kind",
        choices=[
            "product-reference",
            "odps-product",
            "use-case",
            "objective",
            "signal",
            "graph",
        ],
        required=True,
        help="Artifact kind to generate.",
    )
    generate_parser.add_argument(
        "--output",
        "-o",
        help=(
            "Output folder for generated YAML artifacts. Defaults to "
            f"{DEFAULT_GENERATION_OUTPUT}."
        ),
    )
    generate_parser.add_argument(
        "--model",
        help="Model override. Defaults to config model or qwen2.5.",
    )
    generate_parser.add_argument(
        "--prompts",
        help="Prompt template folder override. Defaults to config prompts or bundled prompts.",
    )
    generate_parser.add_argument(
        "--profile",
        choices=["minimal", "complete-draft"],
        default="minimal",
        help=(
            "ODPS product generation profile. minimal is evidence-only; "
            "complete-draft drafts SLA, dataQuality, and pricingPlans."
        ),
    )
    generate_parser.add_argument(
        "--include-components",
        help=(
            "Comma-separated ODPS product components to draft for --kind "
            "odps-product, such as SLA,dataQuality,pricingPlans,dataAccess."
        ),
    )
    generate_parser.add_argument(
        "--max-source-chars",
        type=int,
        help=(
            "Maximum source characters per ODPS product facts prompt before "
            "chunking and merging facts. Applies to --kind odps-product."
        ),
    )
    generate_parser.add_argument(
        "--ollama-url",
        help="Local Ollama base URL. Defaults to http://localhost:11434.",
    )
    generate_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpc_summary_parser = subparsers.add_parser(
        "odpc-summary", help="Summarize an ODPC catalog"
    )
    odpc_summary_parser.add_argument("catalog", help="Path to an ODPC catalog file")
    odpc_summary_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpc_build_parser = subparsers.add_parser(
        "odpc-build", help="Build an ODPC catalog from fragments"
    )
    odpc_build_parser.add_argument(
        "input_dir",
        help="Folder containing ODPC objects, ODPC catalogs, or ODPS product files",
    )
    odpc_build_parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output catalog YAML path",
    )
    odpc_build_parser.add_argument(
        "--html",
        help="Optional output path for a standalone browser-viewable HTML catalog",
    )
    odpc_build_parser.add_argument(
        "--toon",
        help="Optional output path for a TOON catalog context file",
    )
    odpc_build_parser.add_argument(
        "--gcf",
        help="Optional output path for a GCF catalog context file",
    )
    odpc_build_parser.add_argument(
        "--id", help="Catalog metadata id to use or override"
    )
    odpc_build_parser.add_argument(
        "--name", help="Catalog metadata name.en to use or override"
    )
    odpc_build_parser.add_argument(
        "--description",
        help="Catalog metadata description.en to use or override",
    )
    odpc_build_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only read files directly inside input_dir.",
    )
    odpc_build_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Write the catalog without validating it against the ODPC schema.",
    )
    odpc_build_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpc_search_parser = subparsers.add_parser(
        "odpc-search", help="Search ODPC catalog object guidance"
    )
    odpc_search_parser.add_argument(
        "query",
        nargs="?",
        help="Keyword query for bundled ODPC object guidance",
    )
    odpc_search_parser.add_argument("--id", help="Return one ODPC object by id")
    odpc_search_parser.add_argument(
        "--limit", type=int, default=5, help="Maximum number of matches"
    )
    odpc_search_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpc_artifacts_parser = subparsers.add_parser(
        "odpc-artifacts", help="Generate or check derived ODPC catalog artifacts"
    )
    odpc_artifacts_parser.add_argument(
        "output_dir",
        nargs="?",
        default=".",
        help="Directory for generated artifacts. Defaults to the current directory.",
    )
    odpc_artifacts_parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated artifacts under output_dir are not in sync.",
    )
    odpc_artifacts_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpv_summary_parser = subparsers.add_parser(
        "odpv-summary", help="Summarize an ODPV vocabulary"
    )
    odpv_summary_parser.add_argument(
        "vocabulary",
        nargs="?",
        help="Optional path to an ODPV vocabulary file; defaults to bundled ODPV",
    )
    odpv_summary_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpv_search_parser = subparsers.add_parser(
        "odpv-search", help="Search ODPV vocabulary terms"
    )
    odpv_search_parser.add_argument("query", help="Keyword query for ODPV terms")
    odpv_search_parser.add_argument(
        "--limit", type=int, default=5, help="Maximum number of matches"
    )
    odpv_search_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpv_resolve_parser = subparsers.add_parser(
        "odpv-resolve", help="Resolve text or aliases to a canonical ODPV term"
    )
    odpv_resolve_parser.add_argument("query", help="Term id, alias, or keyword query")
    odpv_resolve_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpv_explain_parser = subparsers.add_parser(
        "odpv-explain", help="Return one canonical ODPV term packet"
    )
    odpv_explain_parser.add_argument("term", help="ODPV term id")
    odpv_explain_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpv_relationship_parser = subparsers.add_parser(
        "odpv-relationship", help="Check ODPV relationship domain/range compatibility"
    )
    odpv_relationship_parser.add_argument("source", help="Source ODPV object type")
    odpv_relationship_parser.add_argument(
        "verb", help="Relationship id, alias, or text"
    )
    odpv_relationship_parser.add_argument("target", help="Target ODPV object type")
    odpv_relationship_parser.add_argument(
        "--json", action="store_true", help="Emit JSON"
    )

    odpv_context_parser = subparsers.add_parser(
        "odpv-context", help="Return an agent-ready ODPV term context packet"
    )
    odpv_context_parser.add_argument("term", help="ODPV term id")
    odpv_context_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpg_summary_parser = subparsers.add_parser(
        "odpg-summary", help="Summarize an ODPG graph"
    )
    odpg_summary_parser.add_argument("graph", help="Path to an ODPG graph file")
    odpg_summary_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpg_build_parser = subparsers.add_parser(
        "odpg-build", help="Build an ODPG graph from ODPC fragments"
    )
    odpg_build_parser.add_argument(
        "input_dir",
        help="Folder containing ODPC product reference, use case, objective, or signal fragments",
    )
    odpg_build_parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output graph YAML path",
    )
    odpg_build_parser.add_argument(
        "--toon",
        help="Optional output path for a TOON graph context file",
    )
    odpg_build_parser.add_argument(
        "--gcf",
        help="Optional output path for a GCF graph context file",
    )
    odpg_build_parser.add_argument(
        "--context-graph",
        help="Existing graph YAML to include as prior edge-inference context; prefers sibling .gcf/.toon",
    )
    odpg_build_parser.add_argument("--id", help="Graph metadata id to use or override")
    odpg_build_parser.add_argument(
        "--name", help="Graph metadata name.en to use or override"
    )
    odpg_build_parser.add_argument(
        "--description",
        help="Graph metadata description.en to use or override",
    )
    odpg_build_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only read files directly inside input_dir.",
    )
    odpg_build_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Write the graph without validating it against ODPG rules.",
    )
    odpg_build_parser.add_argument(
        "--config",
        help="Generation config path for the edge inference provider.",
    )
    odpg_build_parser.add_argument(
        "--provider",
        help=(
            "Provider override such as ollama, openai, openrouter, groq, zai, "
            "sakana-fugu, lmstudio, or claude."
        ),
    )
    odpg_build_parser.add_argument(
        "--model",
        help="Model override. Defaults to config model or qwen2.5.",
    )
    odpg_build_parser.add_argument(
        "--prompts",
        help="Prompt template folder override. Defaults to config prompts or bundled prompts.",
    )
    odpg_build_parser.add_argument(
        "--ollama-url",
        help="Local Ollama base URL. Defaults to http://localhost:11434.",
    )
    odpg_build_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpg_traverse_parser = subparsers.add_parser(
        "odpg-traverse", help="Discover ODPG relationship paths from a node"
    )
    odpg_traverse_parser.add_argument("graph", help="Path to an ODPG graph file")
    odpg_traverse_parser.add_argument("--start", required=True, help="Starting node id")
    odpg_traverse_parser.add_argument(
        "--depth", type=int, default=2, help="Maximum traversal depth"
    )
    odpg_traverse_parser.add_argument(
        "--relationship", help="Optional relationship type filter"
    )
    odpg_traverse_parser.add_argument(
        "--reverse", action="store_true", help="Traverse incoming relationships"
    )
    odpg_traverse_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpg_analyze_parser = subparsers.add_parser(
        "odpg-analyze", help="Run ODPG strategic and governance checks"
    )
    odpg_analyze_parser.add_argument("graph", help="Path to an ODPG graph file")
    odpg_analyze_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpg_context_parser = subparsers.add_parser(
        "odpg-agent-context", help="Extract ODPG context around a focus node"
    )
    odpg_context_parser.add_argument("graph", help="Path to an ODPG graph file")
    odpg_context_parser.add_argument("--node", required=True, help="Focus node id")
    odpg_context_parser.add_argument(
        "--depth", type=int, default=2, help="Context traversal depth"
    )
    odpg_context_parser.add_argument(
        "--context-format",
        choices=("auto", "gcf", "toon", "yaml"),
        help="Include compact context artifact content in JSON output",
    )
    odpg_context_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpg_generate_parser = subparsers.add_parser(
        "odpg-generate", help="Generate a standalone ODPG graph explorer"
    )
    odpg_generate_parser.add_argument(
        "graph",
        nargs="?",
        help="Path to an ODPG graph file. Defaults to the bundled graph.",
    )
    odpg_generate_parser.add_argument(
        "--output",
        type=Path,
        default=Path("graph-explorer.html"),
        help="Output HTML file path",
    )
    odpg_generate_parser.add_argument("--json", action="store_true", help="Emit JSON")

    odpg_convert_parser = subparsers.add_parser(
        "odpg-convert", help="Convert external graph formats to ODPG YAML"
    )
    odpg_convert_parser.add_argument(
        "-i", "--input", required=True, type=Path, help="Source graph file"
    )
    odpg_convert_parser.add_argument(
        "-o", "--output", type=Path, help="Output ODPG YAML file"
    )
    odpg_convert_parser.add_argument(
        "--format",
        help=(
            "Source graph format. Supports JSON-LD, GraphML, GraphSON, RDF/Turtle, "
            "OpenCypher, GQL, and Gremlin. Inferred from extension when omitted."
        ),
    )
    odpg_convert_parser.add_argument("--id", help="ODPG graph metadata id")
    odpg_convert_parser.add_argument("--name", help="ODPG graph metadata name")
    odpg_convert_parser.add_argument(
        "--description", help="ODPG graph metadata description"
    )
    odpg_convert_parser.add_argument(
        "--confidence",
        choices=["high", "medium", "low"],
        default="medium",
        help="Confidence value assigned to converted edges",
    )
    odpg_convert_parser.add_argument("--json", action="store_true", help="Emit JSON")

    subparsers.add_parser("manifest", help="Emit the ARWS agent manifest").add_argument(
        "--json", action="store_true", help="Emit JSON"
    )

    subparsers.add_parser("serve", help="Run the MCP server over stdio")

    portfolio_parser = subparsers.add_parser(
        "portfolio",
        help="Portfolio workspace workflows",
        epilog=PORTFOLIO_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    portfolio_subparsers = portfolio_parser.add_subparsers(
        dest="portfolio_command",
        metavar="PORTFOLIO_COMMAND",
        required=True,
    )
    portfolio_build_parser = portfolio_subparsers.add_parser(
        "build",
        help="Build a portfolio workspace from source lanes",
    )
    portfolio_build_parser.add_argument(
        "workspace",
        nargs="?",
        help="Existing portfolio workspace path for reruns.",
    )
    portfolio_build_parser.add_argument(
        "--objectives", help="Business objective source file or folder"
    )
    portfolio_build_parser.add_argument(
        "--use-cases", help="Use case source file or folder"
    )
    portfolio_build_parser.add_argument(
        "--signals", help="Signal source file or folder"
    )
    portfolio_build_parser.add_argument(
        "--products", help="Product source file or folder"
    )
    portfolio_build_parser.add_argument(
        "--output",
        "-o",
        help="Portfolio workspace directory to create or update.",
    )
    portfolio_build_parser.add_argument(
        "--title",
        help="Human-controlled portfolio workspace title. Overrides LLM metadata name.",
    )
    portfolio_build_parser.add_argument(
        "--config",
        help="Generation config YAML file with provider and path settings.",
    )
    portfolio_build_parser.add_argument("--provider", help="LLM provider override.")
    portfolio_build_parser.add_argument("--model", help="Model override.")
    portfolio_build_parser.add_argument(
        "--prompts",
        help="Reserved for portfolio prompt folder overrides.",
    )
    portfolio_build_parser.add_argument(
        "--ollama-url",
        help="Local Ollama base URL. Defaults to http://localhost:11434.",
    )
    portfolio_build_parser.add_argument(
        "--strict-validation",
        action="store_true",
        help=(
            "Return a non-zero exit code when generated artifacts fail schema "
            "validation. By default portfolio commands warn and still complete."
        ),
    )
    portfolio_build_parser.add_argument("--json", action="store_true", help="Emit JSON")
    portfolio_refresh_parser = portfolio_subparsers.add_parser(
        "refresh",
        help="Refresh a portfolio workspace from saved source lanes",
    )
    portfolio_refresh_parser.add_argument("workspace", help="Portfolio workspace path")
    portfolio_refresh_parser.add_argument(
        "--objectives", help="Optional business objective source override"
    )
    portfolio_refresh_parser.add_argument(
        "--use-cases", help="Optional use case source override"
    )
    portfolio_refresh_parser.add_argument(
        "--signals", help="Optional signal source override"
    )
    portfolio_refresh_parser.add_argument(
        "--products", help="Optional product source override"
    )
    portfolio_refresh_parser.add_argument(
        "--title",
        help="Human-controlled portfolio workspace title. Overrides saved title.",
    )
    portfolio_refresh_parser.add_argument(
        "--config",
        help="Generation config YAML file with provider and path settings.",
    )
    portfolio_refresh_parser.add_argument("--provider", help="LLM provider override.")
    portfolio_refresh_parser.add_argument("--model", help="Model override.")
    portfolio_refresh_parser.add_argument(
        "--all-sources",
        action="store_true",
        help="Process all saved source documents instead of only new or changed files.",
    )
    portfolio_refresh_parser.add_argument(
        "--prompts",
        help="Reserved for portfolio prompt folder overrides.",
    )
    portfolio_refresh_parser.add_argument(
        "--ollama-url",
        help="Local Ollama base URL. Defaults to http://localhost:11434.",
    )
    portfolio_refresh_parser.add_argument(
        "--strict-validation",
        action="store_true",
        help=(
            "Return a non-zero exit code when generated artifacts fail schema "
            "validation. By default portfolio commands warn and still complete."
        ),
    )
    portfolio_refresh_parser.add_argument(
        "--json", action="store_true", help="Emit JSON"
    )
    portfolio_sync_parser = portfolio_subparsers.add_parser(
        "sync",
        help="Sync edited YAML artifacts without calling an LLM",
    )
    portfolio_sync_parser.add_argument("workspace", help="Portfolio workspace path")
    portfolio_sync_parser.add_argument(
        "--strict-validation",
        action="store_true",
        help=(
            "Return a non-zero exit code when synced artifacts fail schema "
            "validation. By default portfolio commands warn and still complete."
        ),
    )
    portfolio_sync_parser.add_argument("--json", action="store_true", help="Emit JSON")
    portfolio_localize_parser = portfolio_subparsers.add_parser(
        "localize",
        help="Localize portfolio HTML pages without changing YAML artifacts",
    )
    portfolio_localize_parser.add_argument("workspace", help="Portfolio workspace path")
    portfolio_localize_parser.add_argument(
        "--languages",
        required=True,
        action="append",
        help='BCP 47 language tags to render, for example "fi,sv".',
    )
    portfolio_localize_parser.add_argument(
        "--default-language",
        default="en",
        help="Default portfolio language. Defaults to en.",
    )
    portfolio_localize_parser.add_argument(
        "--config",
        help="Generation config YAML file with provider and path settings.",
    )
    portfolio_localize_parser.add_argument("--provider", help="LLM provider override.")
    portfolio_localize_parser.add_argument("--model", help="Model override.")
    portfolio_localize_parser.add_argument(
        "--prompts",
        help="Reserved for portfolio prompt folder overrides.",
    )
    portfolio_localize_parser.add_argument(
        "--ollama-url",
        help="Local Ollama base URL. Defaults to http://localhost:11434.",
    )
    portfolio_localize_parser.add_argument(
        "--strict-validation",
        action="store_true",
        help=(
            "Return a non-zero exit code when localized artifacts fail schema "
            "validation. By default portfolio commands warn and still complete."
        ),
    )
    portfolio_localize_parser.add_argument(
        "--json", action="store_true", help="Emit JSON"
    )
    portfolio_render_parser = portfolio_subparsers.add_parser(
        "render",
        help="Render one static browser-viewable portfolio page",
    )
    portfolio_render_parser.add_argument("workspace", help="Portfolio workspace path")
    portfolio_render_parser.add_argument(
        "--output",
        "-o",
        help="Optional HTML output path. Defaults to <workspace>/index.html.",
    )
    portfolio_render_parser.add_argument(
        "--strict-validation",
        action="store_true",
        help=(
            "Return a non-zero exit code when rendered artifacts fail schema "
            "validation. By default portfolio commands warn and still complete."
        ),
    )
    portfolio_render_parser.add_argument(
        "--json", action="store_true", help="Emit JSON"
    )
    portfolio_explain_parser = portfolio_subparsers.add_parser(
        "explain",
        help="Summarize a portfolio workspace",
    )
    portfolio_explain_parser.add_argument("workspace", help="Portfolio workspace path")
    portfolio_explain_parser.add_argument(
        "--json", action="store_true", help="Emit JSON"
    )

    add_product_subparser(subparsers)

    try:
        args = parser.parse_args(cli_argv)
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
        _log_parse_failure(cli_argv, exit_code, parse_start_time)
        raise

    activity_context = ActivityContext()
    activity_start_time = time.monotonic()

    try:
        if args.command == "validate":
            document_result = validate_document(args.document)
            activity_context.add_details(
                document=args.document,
                spec=document_result.spec,
                valid=document_result.valid,
                errors=len(document_result.errors),
                warnings=len(document_result.warnings),
            )
            activity_context.warning = document_result.valid and bool(
                document_result.warnings
            )
            activity_context.message = (
                "Document validation passed"
                if document_result.valid
                else "Document validation failed"
            )
            if args.json:
                print(json.dumps(document_result.to_dict(), indent=2))
            else:
                _print_validation_report(args.document, document_result)
            return _finalize_activity(
                args,
                activity_context,
                activity_start_time,
                0 if document_result.valid else 1,
            )

        if args.command == "explain":
            document = load_document(args.document)
            if args.json:
                print(
                    json.dumps(
                        _explain_json_payload(document, args.document),
                        indent=2,
                    )
                )
            else:
                summary = explain_document(document, path=Path(args.document))
                print(summary, end="")
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "refs":
            refs = resolve_references(args.document)
            if args.json:
                print(json.dumps([ref.to_dict() for ref in refs], indent=2))
            else:
                for ref in refs:
                    print(f"{ref.pointer} -> {ref.ref}")
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "resources":
            resources = [get_resource(args.id)] if args.id else list_resources()
            if args.json:
                print(
                    json.dumps([resource.to_dict() for resource in resources], indent=2)
                )
            else:
                for resource in resources:
                    print(
                        f"{resource.id}\t{resource.spec}\t{resource.type}\t{resource.path}"
                    )
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "summary":
            summary = load_summary(args.document)
            if args.json:
                print(json.dumps(summary, indent=2))
            else:
                _print_summary_report(summary)
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "okf-validate":
            from .okf import validate_okf_bundle

            result = validate_okf_bundle(args.bundle)
            if args.json:
                print(json.dumps(result.to_dict(), indent=2))
            elif result.valid:
                print(f"{args.bundle}: valid OKF bundle")
                print(f"Concepts: {result.concept_count}")
                for warning in result.warnings:
                    print(f"Warning: {warning}", file=sys.stderr)
            else:
                print(f"{args.bundle}: invalid OKF bundle", file=sys.stderr)
                for error in result.errors:
                    print(f"- {error}", file=sys.stderr)
            return _finalize_activity(
                args, activity_context, activity_start_time, 0 if result.valid else 1
            )

        if args.command == "okf-summary":
            from .okf import summarize_okf_bundle

            summary = summarize_okf_bundle(args.bundle)
            if args.json:
                print(json.dumps(summary, indent=2))
            else:
                print(f"OKF Bundle: {args.bundle}")
                print(f"Valid: {summary['valid']}")
                print(f"Concepts: {summary['concept_count']}")
                for concept in summary["concepts"]:
                    if isinstance(concept, dict):
                        title = concept.get("title") or concept.get("id")
                        print(f"- {concept.get('id')}: {title}")
            return _finalize_activity(
                args,
                activity_context,
                activity_start_time,
                0 if summary["valid"] else 1,
            )

        if args.command == "okf-import":
            from .okf import import_okf_bundle

            try:
                written = import_okf_bundle(args.bundle, args.output)
            except (OSError, ValueError) as exc:
                print(f"OKF import error: {exc}", file=sys.stderr)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )
            payload = {
                "spec": "okf",
                "kind": "ImportedSourceDocuments",
                "output": args.output,
                "written": [str(path) for path in written],
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"OKF source documents written: {len(written)}")
                for path in written:
                    print(path)
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "okf-export":
            from .okf import export_okf_bundle

            try:
                written = export_okf_bundle(args.source, args.output)
            except (OSError, ValueError) as exc:
                print(f"OKF export error: {exc}", file=sys.stderr)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )
            payload = {
                "spec": "okf",
                "kind": "KnowledgeBundle",
                "output": args.output,
                "written": [str(path) for path in written],
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"OKF bundle written: {args.output}")
                print(f"Files: {len(written)}")
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "config":
            from .generation import (
                copy_config_template,
                copy_generation_prompts,
                get_config,
                print_config,
                validate_config,
            )
            from .odpr import (
                copy_recipe_config_template,
                get_recipe_config,
                get_recipe_config_path,
                print_recipe_config,
                validate_recipe_config,
            )

            try:
                if args.print:
                    if args.domain == "recipes":
                        print(print_recipe_config(args.config_path), end="")
                    else:
                        print(print_config(args.domain, args.config_path), end="")
                    return _finalize_activity(
                        args, activity_context, activity_start_time, 0
                    )
                if args.check:
                    if args.domain == "recipes":
                        payload = validate_recipe_config(
                            args.config_path or get_recipe_config_path()
                        )
                    else:
                        payload = validate_config(args.domain, args.config_path)
                else:
                    if args.domain == "recipes":
                        payload = get_recipe_config(args.config_path)
                    else:
                        payload = get_config(args.domain, args.config_path)
                if args.copy_to:
                    if args.domain == "recipes":
                        copied_to = copy_recipe_config_template(
                            args.copy_to,
                            overwrite=args.overwrite,
                        )
                    else:
                        copied_to = copy_config_template(
                            args.domain,
                            args.copy_to,
                            overwrite=args.overwrite,
                        )
                    payload["copied_to"] = str(copied_to)
                    payload["config_path"] = str(copied_to)
                    payload["editable"] = True
                if args.copy_prompts_to:
                    if args.domain == "recipes":
                        raise ValueError(
                            "--copy-prompts-to is only available for generation config"
                        )
                    copied_prompts = copy_generation_prompts(
                        args.copy_prompts_to,
                        overwrite=args.overwrite,
                    )
                    payload["prompt_dir"] = str(Path(args.copy_prompts_to))
                    payload["copied_prompts"] = [path.name for path in copied_prompts]
            except (FileExistsError, FileNotFoundError, KeyError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )

            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                if args.check:
                    print(f"Config domain: {payload['domain']}")
                    print(f"Active config: {payload['config_path']}")
                    print(f"Valid: {payload['valid']}")
                    for error in payload["errors"]:
                        print(f"Error: {error}")
                    for warning in payload["warnings"]:
                        print(f"Warning: {warning}")
                    return _finalize_activity(
                        args,
                        activity_context,
                        activity_start_time,
                        0 if payload["valid"] else 1,
                    )
                print(f"Config domain: {payload['domain']}")
                print(f"Bundled template: {payload['template_path']}")
                print(f"Active config: {payload['config_path']}")
                if "copied_to" in payload:
                    print(f"Copied editable config to: {payload['copied_to']}")
                if "copied_prompts" in payload:
                    print(f"Copied prompts to: {payload['prompt_dir']}")
                if args.domain == "recipes":
                    print(f"Recipe paths: {payload['recipes']['paths']}")
                    print(
                        "Default provider ref: "
                        f"{payload['providers']['defaultProviderRef']}"
                    )
                    print(f"Allow writes: {payload['execution']['allowWrites']}")
                    print(
                        "Edit a copied config and pass it with "
                        "`open-data-products recipe list --config <path>`."
                    )
                    return _finalize_activity(
                        args, activity_context, activity_start_time, 0
                    )
                resolved = payload["resolved"]
                print(f"Provider: {resolved['provider']}")
                print(f"Model: {resolved['model']}")
                print(f"Input: {resolved['input_path']}")
                print(f"Output: {resolved['output_path']}")
                print(
                    "Edit a copied config and pass it with "
                    "`open-data-products generate --config <path> --kind signal`."
                )
            if args.check:
                return _finalize_activity(
                    args,
                    activity_context,
                    activity_start_time,
                    0 if payload["valid"] else 1,
                )
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "recipe":
            from .odpr import (
                list_recipes,
                list_starter_recipes,
                plan_recipe_run,
                explain_recipe,
                init_starter_recipe,
                validate_odpr_document,
                validate_recipe,
                write_recipe_catalog,
                check_starter_catalog,
                get_recipe_guidance,
                search_recipe_guidance,
            )

            try:
                if args.recipe_command == "list":
                    default_config = Path("recipes.config.yaml")
                    list_starters = args.starters or (
                        args.config is None
                        and args.group is None
                        and not default_config.is_file()
                    )
                    if list_starters:
                        payload = list_starter_recipes(catalog_path=args.catalog)
                    else:
                        payload = list_recipes(
                            config_path=args.config,
                            group=args.group,
                        )
                    exit_code = 0
                elif args.recipe_command == "validate":
                    if args.recipe is None:
                        payload = validate_recipe(None, config_path=args.config)
                    else:
                        base_payload = validate_odpr_document(args.recipe)
                        if base_payload.get("kind") == "Recipe":
                            payload = validate_recipe(
                                args.recipe,
                                config_path=args.config,
                            )
                        else:
                            payload = base_payload
                    exit_code = 0 if payload["valid"] else 1
                elif args.recipe_command == "catalog":
                    output_path = write_recipe_catalog(
                        args.output,
                        config_path=args.config,
                        group=args.group,
                    )
                    payload = validate_odpr_document(output_path)
                    payload["output"] = str(output_path)
                    exit_code = 0 if payload["valid"] else 1
                elif args.recipe_command == "starter-catalog-check":
                    payload = check_starter_catalog(catalog_path=args.catalog)
                    exit_code = 0 if payload["valid"] else 1
                elif args.recipe_command == "init":
                    payload = init_starter_recipe(
                        args.starter,
                        output=args.output,
                        force=args.force,
                        parameterized=args.parameterized,
                        catalog_path=args.catalog,
                    )
                    exit_code = 0
                elif args.recipe_command == "explain":
                    payload = explain_recipe(
                        args.recipe,
                        catalog_path=args.catalog,
                    )
                    exit_code = 0 if payload["valid"] else 1
                elif args.recipe_command == "search":
                    if args.guidance_id:
                        payload = get_recipe_guidance(args.guidance_id)
                    else:
                        payload = search_recipe_guidance(
                            " ".join(args.query or []),
                            limit=args.limit,
                        )
                    exit_code = 0
                elif args.recipe_command == "run":
                    execute_requested = args.execute or (
                        not args.dry_run and (args.allow_llm or args.approve_review)
                    )
                    if execute_requested:
                        from .odpr import execute_recipe_run

                        payload = execute_recipe_run(
                            args.recipe,
                            config_path=args.config,
                            provider_ref=args.provider_ref,
                            model=args.model,
                            allow_llm=args.allow_llm,
                            approve_review=args.approve_review,
                        )
                        exit_code = int(payload["exitCode"])
                    else:
                        payload = plan_recipe_run(
                            args.recipe,
                            mode="dry-run",
                            config_path=args.config,
                            provider_ref=args.provider_ref,
                            model=args.model,
                        )
                        exit_code = 0 if payload["canRun"] else 1
                elif args.recipe_command in {"plan", "dry-run"}:
                    payload = plan_recipe_run(
                        args.recipe,
                        mode="dry-run",
                        config_path=args.config,
                        provider_ref=args.provider_ref,
                        model=args.model,
                    )
                    exit_code = 0 if payload["canRun"] else 1
                else:
                    raise ValueError(f"Unknown recipe command: {args.recipe_command}")
            except (FileExistsError, FileNotFoundError, ValueError) as exc:
                payload = {
                    "kind": "Error",
                    "mode": getattr(args, "recipe_command", "recipe"),
                    "valid": False,
                    "error": str(exc),
                }
                exit_code = 1

            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                if args.recipe_command == "list":
                    catalog = payload.get("recipeCatalog", {})
                    recipes = catalog.get("recipes", [])
                    print(f"Recipes: {len(recipes)}")
                    for recipe in recipes:
                        print(
                            f"- {recipe.get('id') or '(missing id)'} "
                            f"{recipe.get('path')}"
                        )
                elif args.recipe_command == "validate":
                    recipe = payload.get("recipe", {})
                    print(f"Recipe: {recipe.get('id') or args.recipe}")
                    print(f"Valid: {payload.get('valid')}")
                    for error in payload.get("errors", []):
                        print(f"Error: {error}")
                    for warning in payload.get("warnings", []):
                        print(f"Warning: {warning}")
                elif args.recipe_command == "catalog":
                    print(f"RecipeCatalog: {payload.get('output')}")
                    print(f"Valid: {payload.get('valid')}")
                    for error in payload.get("errors", []):
                        print(f"Error: {error}")
                elif args.recipe_command == "starter-catalog-check":
                    print(f"Starter RecipeCatalog: {payload.get('catalog')}")
                    print(f"Valid: {payload.get('valid')}")
                    for error in payload.get("errors", []):
                        print(f"Error: {error}")
                    for warning in payload.get("warnings", []):
                        print(f"Warning: {warning}")
                elif args.recipe_command == "init":
                    print(f"Recipe workspace: {payload.get('workspace')}")
                    print(f"Recipe: {payload.get('recipe')}")
                    print("Next commands:")
                    for command in payload.get("nextCommands", []):
                        print(f"- {command}")
                elif args.recipe_command == "explain":
                    recipe = payload.get("recipe", {})
                    print(f"Recipe: {recipe.get('id') or args.recipe}")
                    print(f"Valid: {payload.get('valid')}")
                    print(f"Source: {payload.get('source')}")
                    print(f"Steps: {len(payload.get('steps', []))}")
                    for step in payload.get("steps", []):
                        if isinstance(step, dict):
                            print(f"- {step.get('id')}: {step.get('command')}")
                    for note in payload.get("safetyNotes", []):
                        print(f"Note: {note}")
                elif args.recipe_command == "search":
                    records = payload if isinstance(payload, list) else [payload]
                    print(f"Guidance records: {len(records)}")
                    for record in records:
                        if isinstance(record, dict):
                            print(f"- {record.get('id')}: {record.get('definition')}")
                else:
                    print(f"Mode: {payload.get('mode')}")
                    print(f"Can run: {payload.get('canRun')}")
                    for reason in payload.get("blockingReasons", []):
                        if isinstance(reason, dict):
                            print(f"Blocking: {reason.get('message')}")
            return _finalize_activity(
                args, activity_context, activity_start_time, exit_code
            )

        if args.command == "generate":
            from .generation import (
                DEFAULT_OLLAMA_URL,
                create_generation_client,
                generate_local_artifacts_for_kind,
                resolve_generation_settings,
            )

            if args.source_dir and args.input_dir:
                print(
                    "Provide the generation input as either positional source_dir "
                    "or --input, not both.",
                    file=sys.stderr,
                )
                if args.source_dir.strip() == "":
                    print(
                        "Check for a trailing space after a line-continuation "
                        "backslash before the next option.",
                        file=sys.stderr,
                    )
                return _finalize_activity(
                    args, activity_context, activity_start_time, 2
                )
            try:
                settings = resolve_generation_settings(
                    config_path=args.config,
                    input_path=args.input_dir or args.source_dir,
                    output_path=args.output,
                    provider=args.provider,
                    model=args.model,
                    ollama_url=args.ollama_url,
                    prompt_dir=args.prompts,
                )
                generation_input = settings.input_path or DEFAULT_GENERATION_INPUT
                generation_output = settings.output_path or DEFAULT_GENERATION_OUTPUT
                model_client = create_generation_client(settings)
                _write_llm_invocation_activity(args, settings, phase=args.kind)
            except (FileNotFoundError, RuntimeError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )

            prompt_kwargs = (
                {"prompt_dir": settings.prompt_path} if settings.prompt_path else {}
            )
            include_components = _split_csv(args.include_components)
            odps_kwargs = (
                {
                    "profile": args.profile,
                    "include_components": include_components,
                    "max_source_chars": args.max_source_chars,
                }
                if args.kind == "odps-product"
                else {}
            )
            try:
                artifacts = generate_local_artifacts_for_kind(
                    args.kind,
                    generation_input,
                    generation_output,
                    model=settings.model,
                    ollama_url=settings.base_url or DEFAULT_OLLAMA_URL,
                    client=model_client,
                    **prompt_kwargs,
                    **odps_kwargs,
                )
            except (KeyError, RuntimeError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )
            valid_yaml = all(artifact.valid_yaml for artifact in artifacts)
            response_kind = (
                "LocalGeneration"
                if settings.provider_type == "ollama"
                else "Generation"
            )
            payload = {
                "spec": "generation",
                "kind": response_kind,
                "source": generation_input,
                "artifact_kind": args.kind,
                "output": generation_output,
                "provider": settings.provider,
                "provider_type": settings.provider_type,
                "model": settings.model,
                "valid_yaml": valid_yaml,
                "artifact_count": len(artifacts),
                "artifacts": [artifact.to_dict() for artifact in artifacts],
            }
            if args.kind == "odps-product":
                payload["profile"] = args.profile
                payload["include_components"] = include_components
                payload["max_source_chars"] = args.max_source_chars
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                state = "valid YAML" if valid_yaml else "invalid YAML"
                print(
                    f"Generated {len(artifacts)} artifact(s) in {generation_output} "
                    f"({state})"
                )
                for artifact in artifacts:
                    print(f"- {artifact.name}: {artifact.output_path}")
                    for error in artifact.errors:
                        print(f"  - {error}")
            return _finalize_activity(
                args, activity_context, activity_start_time, 0 if valid_yaml else 1
            )

        if args.command == "odpc-summary":
            from .odpc import collect_ids, count_items, explain_catalog
            from .odpc import load_catalog, validate_catalog

            document = load_catalog(args.catalog)
            catalog_result = validate_catalog(document)
            catalog = document.get("catalog", {})
            metadata = catalog.get("metadata", {}) if isinstance(catalog, dict) else {}
            name = metadata.get("name")
            catalog_name = (
                name.get("en", "(unnamed)") if isinstance(name, dict) else name
            )
            payload = {
                "spec": "odpc",
                "kind": "Catalog",
                "path": args.catalog,
                "valid": catalog_result.valid,
                "errors": catalog_result.errors,
                "catalogId": metadata.get("id", "(missing)"),
                "catalogName": catalog_name or "(unnamed)",
                "productReferenceCount": count_items(catalog, "productReferences"),
                "useCaseCount": count_items(catalog, "useCases"),
                "businessObjectiveCount": count_items(catalog, "businessObjectives"),
                "signalCount": count_items(catalog, "signals"),
                "productReferenceIds": collect_ids(
                    catalog.get("productReferences", [])
                ),
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(explain_catalog(document, path=Path(args.catalog)), end="")
            return _finalize_activity(
                args,
                activity_context,
                activity_start_time,
                0 if catalog_result.valid else 1,
            )

        if args.command == "odpc-build":
            from .odpc import (
                build_catalog,
                count_items,
                validate_catalog,
                write_catalog,
                write_catalog_gcf,
                write_catalog_html,
                write_catalog_toon,
            )

            output = Path(args.output)
            html_output = Path(args.html) if args.html else None
            toon_output = Path(args.toon) if args.toon else None
            gcf_output = Path(args.gcf) if args.gcf else None
            document = build_catalog(
                args.input_dir,
                recursive=not args.no_recursive,
                output_path=output,
                catalog_id=args.id,
                name=args.name,
                description=args.description,
            )
            build_result = validate_catalog(document) if not args.no_validate else None
            if build_result is not None and not build_result.valid:
                if args.json:
                    print(
                        json.dumps(
                            {
                                "spec": "odpc",
                                "kind": "Catalog",
                                "output": str(output),
                                "valid": False,
                                "errors": build_result.errors,
                            },
                            indent=2,
                        )
                    )
                else:
                    print("Generated catalog is invalid:", file=sys.stderr)
                    for error in build_result.errors:
                        print(f"- {error}", file=sys.stderr)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )

            write_catalog(output, document)
            if html_output:
                write_catalog_html(html_output, document)
            if toon_output:
                write_catalog_toon(toon_output, document)
            if gcf_output:
                write_catalog_gcf(gcf_output, document)
            catalog = document.get("catalog", {})
            payload = {
                "spec": "odpc",
                "kind": "Catalog",
                "output": str(output),
                "html": str(html_output) if html_output else None,
                "toon": str(toon_output) if toon_output else None,
                "gcf": str(gcf_output) if gcf_output else None,
                "valid": True if build_result is not None else None,
                "productReferenceCount": count_items(catalog, "productReferences"),
                "useCaseCount": count_items(catalog, "useCases"),
                "businessObjectiveCount": count_items(catalog, "businessObjectives"),
                "signalCount": count_items(catalog, "signals"),
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(
                    "Generated "
                    f"{output} "
                    f"(productReferences={payload['productReferenceCount']}, "
                    f"useCases={payload['useCaseCount']}, "
                    f"businessObjectives={payload['businessObjectiveCount']}, "
                    f"signals={payload['signalCount']})"
                )
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "odpc-search":
            from .odpc import render_object_records, search_objects

            matches = search_objects(
                args.query,
                object_id=args.id,
                limit=args.limit,
            )
            if args.json:
                print(
                    json.dumps(
                        {
                            "spec": "odpc",
                            "kind": "CatalogObjectGuidance",
                            "matches": matches,
                        },
                        indent=2,
                    )
                )
            else:
                print(render_object_records(matches), end="")
            return _finalize_activity(
                args, activity_context, activity_start_time, 0 if matches else 1
            )

        if args.command == "odpc-artifacts":
            from .odpc import build_catalog_artifacts, write_catalog_artifacts

            changed = write_catalog_artifacts(args.output_dir, check=args.check)
            payload = {
                "spec": "odpc",
                "kind": "CatalogArtifacts",
                "in_sync": not changed,
                "changed": [str(path) for path in changed],
                "artifact_count": len(build_catalog_artifacts()),
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            elif args.check and changed:
                for path in changed:
                    print(f"Out of sync: {path}")
            elif args.check:
                print("Catalog artifacts are in sync")
            else:
                print(f"Generated {payload['artifact_count']} catalog artifacts")
            return _finalize_activity(
                args,
                activity_context,
                activity_start_time,
                1 if args.check and changed else 0,
            )

        if args.command == "odpv-summary":
            from .odpv import load_vocabulary, validate_vocabulary

            vocabulary = load_vocabulary(args.vocabulary) if args.vocabulary else None
            vocabulary_result = validate_vocabulary(vocabulary)
            payload = vocabulary_result.to_dict()
            if args.vocabulary:
                payload["path"] = args.vocabulary
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(
                    "ODPV Vocabulary: "
                    f"{vocabulary_result.term_count} terms, "
                    f"{vocabulary_result.relationship_count} relationships, "
                    f"{vocabulary_result.section_count} sections"
                )
                for error in vocabulary_result.errors:
                    print(f"- {error}")
            return _finalize_activity(
                args,
                activity_context,
                activity_start_time,
                0 if vocabulary_result.valid else 1,
            )

        if args.command == "odpv-search":
            from .odpv import render_search_results, search_vocabulary

            matches = search_vocabulary(args.query, limit=args.limit)
            if args.json:
                print(
                    json.dumps(
                        {
                            "spec": "odpv",
                            "kind": "VocabularyTermSearch",
                            "matches": matches,
                        },
                        indent=2,
                    )
                )
            else:
                print(render_search_results(matches), end="")
            return _finalize_activity(
                args, activity_context, activity_start_time, 0 if matches else 1
            )

        if args.command == "odpv-resolve":
            from .odpv import resolve_vocabulary_term

            payload = resolve_vocabulary_term(args.query)
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                match = payload.get("match")
                print(match["id"] if match else "No matching ODPV term found.")
            return _finalize_activity(
                args,
                activity_context,
                activity_start_time,
                0 if payload.get("match") else 1,
            )

        if args.command == "odpv-explain":
            from .odpv import explain_vocabulary_term

            payload = explain_vocabulary_term(args.term)
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"{payload['id']}: {payload['definition'].get('en', '')}")
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "odpv-relationship":
            from .odpv import check_vocabulary_relationship

            payload = check_vocabulary_relationship(
                args.source,
                args.verb,
                args.target,
            )
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                state = "compatible" if payload["compatible"] else "not compatible"
                print(f"{args.source} {args.verb} {args.target}: {state}")
                for note in payload["notes"]:
                    print(f"- {note}")
            return _finalize_activity(
                args,
                activity_context,
                activity_start_time,
                0 if payload["compatible"] else 1,
            )

        if args.command == "odpv-context":
            from .odpv import agent_vocabulary_context

            payload = agent_vocabulary_context(args.term)
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                term = payload["term"]
                print(f"{term['id']}: {term['definition'].get('en', '')}")
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "odpg-summary":
            from .odpg import load_graph, summarize_graph

            summary = summarize_graph(load_graph(args.graph))
            if args.json:
                print(json.dumps(summary, indent=2))
            else:
                _print_odpg_summary(summary)
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "odpg-build":
            from .generation import (
                create_generation_client,
                resolve_generation_settings,
            )
            from .odpg import (
                build_graph,
                summarize_graph,
                validate_graph,
                write_graph,
                write_graph_gcf,
                write_graph_toon,
            )

            output = Path(args.output)
            toon_output = Path(args.toon) if args.toon else None
            gcf_output = Path(args.gcf) if args.gcf else None
            try:
                settings = resolve_generation_settings(
                    config_path=args.config,
                    input_path=args.input_dir,
                    output_path=str(output),
                    provider=args.provider,
                    model=args.model,
                    ollama_url=args.ollama_url,
                    prompt_dir=args.prompts,
                )
                model_client = create_generation_client(settings)
                _write_llm_invocation_activity(args, settings, phase="graph")
                document = build_graph(
                    args.input_dir,
                    recursive=not args.no_recursive,
                    output_path=output,
                    graph_id=args.id,
                    name=args.name,
                    description=args.description,
                    client=model_client,
                    model=settings.model,
                    prompt_dir=settings.prompt_path,
                    context_graph=args.context_graph,
                )
                build_result = (
                    validate_graph(document) if not args.no_validate else None
                )
            except (FileNotFoundError, KeyError, RuntimeError, ValueError) as exc:
                if args.json:
                    print(
                        json.dumps(
                            {
                                "spec": "odpg",
                                "kind": "Graph",
                                "output": str(output),
                                "valid": False,
                                "errors": [str(exc)],
                            },
                            indent=2,
                        )
                    )
                else:
                    print(f"Could not build ODPG graph: {exc}", file=sys.stderr)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )

            if build_result is not None and not build_result.valid:
                if args.json:
                    print(
                        json.dumps(
                            {
                                "spec": "odpg",
                                "kind": "Graph",
                                "output": str(output),
                                "valid": False,
                                "errors": build_result.errors,
                            },
                            indent=2,
                        )
                    )
                else:
                    print("Generated graph is invalid:", file=sys.stderr)
                    for error in build_result.errors:
                        print(f"- {error}", file=sys.stderr)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )

            write_graph(output, document)
            if toon_output:
                write_graph_toon(toon_output, document)
            if gcf_output:
                write_graph_gcf(gcf_output, document)
            summary = summarize_graph(document)
            payload = {
                "spec": "odpg",
                "kind": "Graph",
                "output": str(output),
                "toon": str(toon_output) if toon_output else None,
                "gcf": str(gcf_output) if gcf_output else None,
                "valid": True if build_result is not None else None,
                "nodeCount": summary["nodeCount"],
                "edgeCount": summary["edgeCount"],
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(
                    f"Generated {output} "
                    f"(nodes={payload['nodeCount']}, edges={payload['edgeCount']})"
                )
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "odpg-traverse":
            from .odpg import load_graph, traverse_graph, validate_graph

            graph = load_graph(args.graph)
            graph_result = validate_graph(graph)
            if not graph_result.valid:
                if args.json:
                    print(json.dumps(graph_result.to_dict(), indent=2))
                else:
                    _print_validation_report(args.graph, graph_result)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )
            paths = traverse_graph(
                graph,
                args.start,
                args.depth,
                relationship=args.relationship,
                reverse=args.reverse,
            )
            if args.json:
                print(json.dumps({"start": args.start, "paths": paths}, indent=2))
            else:
                _print_odpg_paths(args.start, paths)
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "odpg-analyze":
            from .odpg import analyze_graph, load_graph, validate_graph

            graph = load_graph(args.graph)
            graph_result = validate_graph(graph)
            if not graph_result.valid:
                if args.json:
                    print(json.dumps(graph_result.to_dict(), indent=2))
                else:
                    _print_validation_report(args.graph, graph_result)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )
            analysis = analyze_graph(graph)
            if args.json:
                print(
                    json.dumps(
                        {
                            "warnings": graph_result.warnings,
                            "analysis": analysis,
                        },
                        indent=2,
                    )
                )
            else:
                print("ODPG Analysis:")
                for warning in graph_result.warnings:
                    print(f"- Warning: {warning}")
                for item in analysis:
                    print(f"- {item}")
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "odpg-agent-context":
            from ._context_artifacts import select_context_artifact
            from .odpg import agent_context, load_graph, validate_graph

            graph = load_graph(args.graph)
            graph_result = validate_graph(graph)
            if not graph_result.valid:
                if args.json:
                    print(json.dumps(graph_result.to_dict(), indent=2))
                else:
                    _print_validation_report(args.graph, graph_result)
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )
            payload = agent_context(graph, args.node, args.depth)
            payload["warnings"] = graph_result.warnings
            if args.context_format:
                preferred = (
                    ("gcf", "toon", "yaml")
                    if args.context_format == "auto"
                    else (args.context_format,)
                )
                artifact = select_context_artifact(args.graph, preferred=preferred)
                payload["contextArtifact"] = {
                    "format": artifact.format,
                    "path": str(artifact.path),
                    "content": artifact.content,
                }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                focus = payload.get("focusNode")
                focus_id = (
                    focus.get("id", args.node) if isinstance(focus, dict) else args.node
                )
                print(f"Focus node: {focus_id}")
                print(f"Depth: {args.depth}")
                related = payload.get("relatedNodes", [])
                if isinstance(related, list):
                    print(f"Related nodes: {len(related)}")
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "odpg-generate":
            from .odpg import generate_graph_explorer

            output = generate_graph_explorer(args.graph, args.output)
            payload = {
                "spec": "odpg",
                "kind": "Graph",
                "output": str(output),
                "generated": True,
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"Graph Explorer generated successfully: {output}")
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "odpg-convert":
            from .odpg import convert_file, dump_graph_yaml

            document = convert_file(
                input_path=args.input,
                output_path=args.output,
                source_format=args.format,
                graph_id=args.id,
                name=args.name,
                description=args.description,
                confidence=args.confidence,
            )
            if args.output:
                payload = {
                    "spec": "odpg",
                    "kind": "Graph",
                    "output": str(args.output),
                    "nodes": len(document["graph"]["nodes"]),
                    "edges": len(document["graph"]["edges"]),
                    "converted": True,
                }
                if args.json:
                    print(json.dumps(payload, indent=2))
                else:
                    print(f"ODPG graph written successfully: {args.output}")
            else:
                print(dump_graph_yaml(document), end="")
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "manifest":
            from .mcp.manifest import generate_agent_manifest

            print(json.dumps(generate_agent_manifest(), indent=2))
            return _finalize_activity(args, activity_context, activity_start_time, 0)

        if args.command == "serve":
            from .mcp.server import serve

            return _finalize_activity(
                args, activity_context, activity_start_time, serve()
            )

        if args.command == "portfolio":
            from .portfolio import (
                build_portfolio,
                explain_portfolio,
                localize_portfolio,
                refresh_portfolio,
                render_portfolio,
                sync_portfolio,
            )

            try:
                if args.portfolio_command == "build":
                    from .generation import (
                        create_generation_client,
                        resolve_generation_settings,
                    )

                    workspace = args.output or args.workspace
                    if not workspace:
                        raise ValueError(
                            "Provide a portfolio workspace with --output or as an argument."
                        )
                    settings = resolve_generation_settings(
                        config_path=args.config,
                        provider=args.provider,
                        model=args.model,
                        ollama_url=args.ollama_url,
                        prompt_dir=args.prompts,
                    )
                    client = create_generation_client(settings)
                    _write_llm_invocation_activity(args, settings, phase="portfolio")
                    payload = build_portfolio(
                        workspace,
                        objectives=args.objectives,
                        use_cases=args.use_cases,
                        signals=args.signals,
                        products=args.products,
                        title=args.title,
                        client=client,
                        model=settings.model,
                    )
                elif args.portfolio_command == "refresh":
                    from .generation import (
                        create_generation_client,
                        resolve_generation_settings,
                    )

                    settings = resolve_generation_settings(
                        config_path=args.config,
                        provider=args.provider,
                        model=args.model,
                        ollama_url=args.ollama_url,
                        prompt_dir=args.prompts,
                    )
                    client = create_generation_client(settings)
                    _write_llm_invocation_activity(
                        args, settings, phase="portfolio.refresh"
                    )
                    payload = refresh_portfolio(
                        args.workspace,
                        objectives=args.objectives,
                        use_cases=args.use_cases,
                        signals=args.signals,
                        products=args.products,
                        title=args.title,
                        client=client,
                        model=settings.model,
                        all_sources=args.all_sources,
                    )
                elif args.portfolio_command == "sync":
                    payload = sync_portfolio(args.workspace)
                elif args.portfolio_command == "localize":
                    from .generation import (
                        create_generation_client,
                        resolve_generation_settings,
                    )

                    settings = resolve_generation_settings(
                        config_path=args.config,
                        provider=args.provider,
                        model=args.model,
                        ollama_url=args.ollama_url,
                        prompt_dir=args.prompts,
                    )
                    client = create_generation_client(settings)
                    _write_llm_invocation_activity(
                        args, settings, phase="portfolio.localize"
                    )
                    payload = localize_portfolio(
                        args.workspace,
                        languages=args.languages,
                        default_language=args.default_language,
                        client=client,
                        model=settings.model,
                    )
                elif args.portfolio_command == "render":
                    payload = render_portfolio(args.workspace, output_path=args.output)
                elif args.portfolio_command == "explain":
                    payload = explain_portfolio(args.workspace)
                else:
                    raise ValueError(
                        f"Unknown portfolio command: {args.portfolio_command}"
                    )
            except (FileNotFoundError, ValueError) as exc:
                _print_error_payload(
                    exc,
                    as_json=args.json,
                    spec="portfolio",
                )
                return _finalize_activity(
                    args, activity_context, activity_start_time, 1
                )

            payload["validationMode"] = _portfolio_validation_mode(args)
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"Workspace: {payload['workspace']}")
                print(f"HTML: {payload['html']}")
                print(f"Validation mode: {payload['validationMode']}")
                if "productReferenceCount" in payload:
                    print(f"Product references: {payload['productReferenceCount']}")
                if "created" in payload:
                    print(f"Created: {len(payload['created'])}")
                    print(f"Updated: {len(payload['updated'])}")
            return _finalize_activity(
                args,
                activity_context,
                activity_start_time,
                _portfolio_exit_code(payload, args),
            )

        if args.command == "product":
            return _finalize_activity(
                args,
                activity_context,
                activity_start_time,
                handle_product_command(args),
            )
    except Exception as exc:
        args_for_error = locals().get("args")
        as_json = bool(getattr(args_for_error, "json", False))
        _print_error_payload(exc, as_json=as_json)
        return _finalize_activity(args, activity_context, activity_start_time, 1)

    return _finalize_activity(args, activity_context, activity_start_time, 1)


def _print_validation_report(document: str, result: "ValidationResult") -> None:
    spec_label = result.spec.upper() if result.spec else "Document"
    print(f"✓ Loaded {spec_label} document: {document}")
    print(f"✓ Detected kind: {result.kind}")
    if result.version:
        print(f"✓ Detected version: {result.version}")
    if result.valid:
        print("✓ Schema validation passed")
        print(f"✓ {spec_label} validation passed")
        if result.warnings:
            print()
            for warning in result.warnings:
                print(f"! {warning}")
        if result.hints:
            print()
            for hint in result.hints:
                print(f"i {hint}")
        print()
        print("Validation successful!")
        return

    print("✗ Schema validation failed")
    print()
    print("Validation failed.")
    for error in result.errors:
        print(f"✗ {error}")
    for warning in result.warnings:
        print(f"! {warning}")
    for hint in result.hints:
        print(f"i {hint}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
