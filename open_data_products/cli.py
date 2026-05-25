"""Top-level command line interface for agent-oriented SDK workflows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from .agent import (
    explain_document,
    load_document,
    resolve_references,
    validate_document,
)
from .resources import get_resource, list_resources
from .summary import load_summary

DEFAULT_GENERATION_INPUT = "open_data_products/generation/source_docs/"
DEFAULT_GENERATION_OUTPUT = "open_data_products/generation/fragments/"

if TYPE_CHECKING:
    from .contracts import ProductContractReport


TOP_LEVEL_HELP = """\
Core document commands:
  validate     Validate ODPS, ODPC, ODPG, or ODPV documents
  explain      Print an agent-readable document summary
  refs         List document references
  summary      Return lightweight file metadata

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

Discovery and agent commands:
  resources    List bundled schemas, vocabularies, and indexes
  manifest     Emit the MCP/agent manifest
  serve        Run the MCP server over stdio

Local generation commands:
  generate     Use local Ollama/Qwen prompts to create fragments and graph YAML

ODPG graph commands:
  odpg-summary         Summarize graph metadata and relationship counts
  odpg-traverse        Discover relationship paths from a focus node
  odpg-analyze         Run governance and strategic graph checks
  odpg-agent-context   Extract graph context around a node for agents
  odpg-generate        Generate a standalone graph explorer HTML file

Product/Data Contract commands:
  product resolve-contracts   Resolve Data Contract references
  product contract-report     Generate a product-contract report
  product audit               Run static product and contract checks
  product check-contract      Validate a product plus an external contract
  product align-contract      Check static ODPS/Data Contract alignment
  product contract-schema     Summarize a Data Contract schema
  product export-contract     Export through datacontract-cli

Examples:
  open-data-products validate product.yaml --json
  open-data-products explain catalog.yaml
  open-data-products odpc-build fragments/ --output catalog.yaml --json
  open-data-products odpc-build fragments/ --output catalog.yaml --html catalog.html --json
  open-data-products odpc-summary catalog.yaml --json
  open-data-products odpc-search "catalog data" --limit 3 --json
  open-data-products odpc-artifacts open_data_products/generation/fragments/ --check --json
  open-data-products odpv-summary --json
  open-data-products odpv-search "governance policy risk" --limit 3 --json
  open-data-products odpv-context DataProduct --json
  open-data-products resources --id odpc.objects --json
  open-data-products resources --id odpv.terms --json
  open-data-products resources --json
  open-data-products generate --json
  open-data-products generate --config generation.config.yaml --json
  open-data-products generate --input source_docs/ --output fragments/ --json
  open-data-products generate --input use-case.md --kind use-case --output fragments/ --json
  open-data-products odpg-agent-context graph.yaml --node DATA-PRODUCT-001
  open-data-products odpg-generate graph.yaml --output graph-explorer.html --json
  open-data-products product contract-report product.yaml contract.yaml --json
  open-data-products serve
"""

PRODUCT_HELP = """\
Data Contract workflow commands:
  resolve-contracts   Find Data Contract references in an ODPS product
  contract-report     Generate a static product-contract report
  audit               Run product checks, including referenced contracts
  check-contract      Validate a product and an external Data Contract
  align-contract      Check static ODPS-to-Data Contract alignment
  contract-schema     Extract models and fields from a Data Contract
  export-contract     Export a Data Contract through datacontract-cli

Examples:
  open-data-products product resolve-contracts product.yaml --json
  open-data-products product contract-report product.yaml contract.yaml --json
  open-data-products product audit product.yaml --contract contract.yaml --json
"""


def main(argv: Optional[List[str]] = None) -> int:
    """Run the top-level Open Data Products CLI."""
    parser = argparse.ArgumentParser(
        prog="open-data-products",
        description=(
            "Validate, inspect, and expose Open Data Product family artifacts."
        ),
        epilog=TOP_LEVEL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate fragments and graph YAML with a local LLM",
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
            "or claude."
        ),
    )
    generate_parser.add_argument(
        "--kind",
        choices=[
            "all",
            "product",
            "use-case",
            "objective",
            "signal",
            "graph",
        ],
        default="all",
        help="Artifact kind to generate. Defaults to all.",
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

    odpg_analyze_parser = subparsers.add_parser(
        "odpg-analyze", help="Run ODPG strategic and governance checks"
    )
    odpg_analyze_parser.add_argument("graph", help="Path to an ODPG graph file")

    odpg_context_parser = subparsers.add_parser(
        "odpg-agent-context", help="Extract ODPG context around a focus node"
    )
    odpg_context_parser.add_argument("graph", help="Path to an ODPG graph file")
    odpg_context_parser.add_argument("--node", required=True, help="Focus node id")
    odpg_context_parser.add_argument(
        "--depth", type=int, default=2, help="Context traversal depth"
    )

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

    subparsers.add_parser("manifest", help="Emit the ARWS agent manifest").add_argument(
        "--json", action="store_true", help="Emit JSON"
    )

    subparsers.add_parser("serve", help="Run the MCP server over stdio")

    product_parser = subparsers.add_parser(
        "product",
        help="Product-level orchestration workflows",
        epilog=PRODUCT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    product_subparsers = product_parser.add_subparsers(
        dest="product_command",
        metavar="PRODUCT_COMMAND",
        required=True,
    )
    check_contract_parser = product_subparsers.add_parser(
        "check-contract",
        help="Validate an ODPS product and an external Data Contract",
    )
    check_contract_parser.add_argument("product", help="Path to an ODPS product file")
    check_contract_parser.add_argument(
        "contract", help="Path or URL to a Data Contract file"
    )
    check_contract_parser.add_argument("--json", action="store_true", help="Emit JSON")
    resolve_contracts_parser = product_subparsers.add_parser(
        "resolve-contracts",
        help="Resolve Data Contract references from an ODPS product",
    )
    resolve_contracts_parser.add_argument(
        "product", help="Path to an ODPS product file"
    )
    resolve_contracts_parser.add_argument(
        "--json", action="store_true", help="Emit JSON"
    )
    contract_report_parser = product_subparsers.add_parser(
        "contract-report",
        help="Generate a static product-level Data Contract report",
    )
    contract_report_parser.add_argument("product", help="Path to an ODPS product file")
    contract_report_parser.add_argument(
        "contract",
        nargs="?",
        help="Optional explicit path or URL to a Data Contract file",
    )
    contract_report_parser.add_argument("--json", action="store_true", help="Emit JSON")
    align_contract_parser = product_subparsers.add_parser(
        "align-contract",
        help="Check static ODPS-to-Data Contract alignment",
    )
    align_contract_parser.add_argument("product", help="Path to an ODPS product file")
    align_contract_parser.add_argument(
        "contract", help="Path or URL to a Data Contract file"
    )
    align_contract_parser.add_argument(
        "--run-contract-tests",
        action="store_true",
        help="Reserved for future live Data Contract tests",
    )
    align_contract_parser.add_argument("--json", action="store_true", help="Emit JSON")
    contract_schema_parser = product_subparsers.add_parser(
        "contract-schema",
        help="Extract a normalized schema summary from a Data Contract",
    )
    contract_schema_parser.add_argument("contract", help="Path to a Data Contract file")
    contract_schema_parser.add_argument("--json", action="store_true", help="Emit JSON")
    contract_export_parser = product_subparsers.add_parser(
        "export-contract",
        help="Export a Data Contract through datacontract-cli",
    )
    contract_export_parser.add_argument(
        "contract", help="Path or URL to a Data Contract file"
    )
    contract_export_parser.add_argument(
        "--format",
        default="jsonschema",
        help="datacontract-cli export format",
    )
    contract_export_parser.add_argument("--json", action="store_true", help="Emit JSON")
    audit_parser = product_subparsers.add_parser(
        "audit",
        help="Run static product checks, including Data Contracts when referenced",
    )
    audit_parser.add_argument("product", help="Path to an ODPS product file")
    audit_parser.add_argument(
        "--contract",
        help="Optional explicit path or URL to a Data Contract file",
    )
    audit_parser.add_argument(
        "--run-contract-tests",
        action="store_true",
        help="Reserved for future live Data Contract tests",
    )
    audit_parser.add_argument("--json", action="store_true", help="Emit JSON")

    args = parser.parse_args(argv)

    try:
        if args.command == "validate":
            result = validate_document(args.document)
            if args.json:
                print(json.dumps(result.to_dict(), indent=2))
            elif result.valid:
                print(f"{args.document}: valid {result.spec} {result.kind}")
            else:
                print(f"{args.document}: invalid {result.spec} {result.kind}")
                for error in result.errors:
                    print(f"- {error}")
            return 0 if result.valid else 1

        if args.command == "explain":
            document = load_document(args.document)
            summary = explain_document(document, path=Path(args.document))
            if args.json:
                result = validate_document(document, path=args.document)
                print(
                    json.dumps(
                        {
                            "spec": result.spec,
                            "kind": result.kind,
                            "path": args.document,
                            "summary": summary,
                        },
                        indent=2,
                    )
                )
            else:
                print(summary, end="")
            return 0

        if args.command == "refs":
            refs = resolve_references(args.document)
            if args.json:
                print(json.dumps([ref.to_dict() for ref in refs], indent=2))
            else:
                for ref in refs:
                    print(f"{ref.pointer} -> {ref.ref}")
            return 0

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
            return 0

        if args.command == "summary":
            print(json.dumps(load_summary(args.document), indent=2))
            return 0

        if args.command == "generate":
            from . import generation

            if args.source_dir and args.input_dir:
                print(
                    "Provide the generation input as either positional source_dir "
                    "or --input, not both.",
                    file=sys.stderr,
                )
                return 2
            try:
                settings = generation.resolve_generation_settings(
                    config_path=args.config,
                    input_path=args.input_dir or args.source_dir,
                    output_path=args.output,
                    provider=args.provider,
                    model=args.model,
                    ollama_url=args.ollama_url,
                )
                generation_input = settings.input_path or DEFAULT_GENERATION_INPUT
                generation_output = settings.output_path or DEFAULT_GENERATION_OUTPUT
                model_client = generation.create_generation_client(settings)
            except (FileNotFoundError, RuntimeError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 1

            if args.kind == "all":
                artifacts = generation.generate_local_artifacts(
                    generation_input,
                    generation_output,
                    model=settings.model,
                    ollama_url=settings.base_url or generation.DEFAULT_OLLAMA_URL,
                    client=model_client,
                )
            else:
                artifacts = [
                    generation.generate_local_artifact(
                        args.kind,
                        generation_input,
                        generation_output,
                        model=settings.model,
                        ollama_url=settings.base_url or generation.DEFAULT_OLLAMA_URL,
                        client=model_client,
                    )
                ]
            valid_yaml = all(artifact.valid_yaml for artifact in artifacts)
            payload = {
                "spec": "generation",
                "kind": "LocalGeneration",
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
            return 0 if valid_yaml else 1

        if args.command == "odpc-summary":
            from .odpc import collect_ids, count_items, explain_catalog
            from .odpc import load_catalog, validate_catalog

            document = load_catalog(args.catalog)
            result = validate_catalog(document)
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
                "valid": result.valid,
                "errors": result.errors,
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
            return 0 if result.valid else 1

        if args.command == "odpc-build":
            from .odpc import (
                build_catalog,
                count_items,
                validate_catalog,
                write_catalog,
                write_catalog_html,
            )

            output = Path(args.output)
            html_output = Path(args.html) if args.html else None
            document = build_catalog(
                args.input_dir,
                recursive=not args.no_recursive,
                output_path=output,
                catalog_id=args.id,
                name=args.name,
                description=args.description,
            )
            result = validate_catalog(document) if not args.no_validate else None
            if result is not None and not result.valid:
                if args.json:
                    print(
                        json.dumps(
                            {
                                "spec": "odpc",
                                "kind": "Catalog",
                                "output": str(output),
                                "valid": False,
                                "errors": result.errors,
                            },
                            indent=2,
                        )
                    )
                else:
                    print("Generated catalog is invalid:", file=sys.stderr)
                    for error in result.errors:
                        print(f"- {error}", file=sys.stderr)
                return 1

            write_catalog(output, document)
            if html_output:
                write_catalog_html(html_output, document)
            catalog = document.get("catalog", {})
            payload = {
                "spec": "odpc",
                "kind": "Catalog",
                "output": str(output),
                "html": str(html_output) if html_output else None,
                "valid": True if result is not None else None,
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
            return 0

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
            return 0 if matches else 1

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
            return 1 if args.check and changed else 0

        if args.command == "odpv-summary":
            from .odpv import load_vocabulary, validate_vocabulary

            vocabulary = load_vocabulary(args.vocabulary) if args.vocabulary else None
            result = validate_vocabulary(vocabulary)
            payload = result.to_dict()
            if args.vocabulary:
                payload["path"] = args.vocabulary
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(
                    "ODPV Vocabulary: "
                    f"{result.term_count} terms, "
                    f"{result.relationship_count} relationships, "
                    f"{result.section_count} sections"
                )
                for error in result.errors:
                    print(f"- {error}")
            return 0 if result.valid else 1

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
            return 0 if matches else 1

        if args.command == "odpv-resolve":
            from .odpv import resolve_vocabulary_term

            payload = resolve_vocabulary_term(args.query)
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                match = payload.get("match")
                print(match["id"] if match else "No matching ODPV term found.")
            return 0 if payload.get("match") else 1

        if args.command == "odpv-explain":
            from .odpv import explain_vocabulary_term

            payload = explain_vocabulary_term(args.term)
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"{payload['id']}: {payload['definition'].get('en', '')}")
            return 0

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
            return 0 if payload["compatible"] else 1

        if args.command == "odpv-context":
            from .odpv import agent_vocabulary_context

            payload = agent_vocabulary_context(args.term)
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                term = payload["term"]
                print(f"{term['id']}: {term['definition'].get('en', '')}")
            return 0

        if args.command == "odpg-summary":
            from .odpg import load_graph, summarize_graph

            print(json.dumps(summarize_graph(load_graph(args.graph)), indent=2))
            return 0

        if args.command == "odpg-traverse":
            from .odpg import load_graph, traverse_graph, validate_graph

            graph = load_graph(args.graph)
            result = validate_graph(graph)
            if not result.valid:
                print(json.dumps(result.to_dict(), indent=2))
                return 1
            paths = traverse_graph(
                graph,
                args.start,
                args.depth,
                relationship=args.relationship,
                reverse=args.reverse,
            )
            print(json.dumps({"start": args.start, "paths": paths}, indent=2))
            return 0

        if args.command == "odpg-analyze":
            from .odpg import analyze_graph, load_graph, validate_graph

            graph = load_graph(args.graph)
            result = validate_graph(graph)
            if not result.valid:
                print(json.dumps(result.to_dict(), indent=2))
                return 1
            print(
                json.dumps(
                    {"warnings": result.warnings, "analysis": analyze_graph(graph)},
                    indent=2,
                )
            )
            return 0

        if args.command == "odpg-agent-context":
            from .odpg import agent_context, load_graph, validate_graph

            graph = load_graph(args.graph)
            result = validate_graph(graph)
            if not result.valid:
                print(json.dumps(result.to_dict(), indent=2))
                return 1
            payload = agent_context(graph, args.node, args.depth)
            payload["warnings"] = result.warnings
            print(json.dumps(payload, indent=2))
            return 0

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
            return 0

        if args.command == "manifest":
            from .mcp.manifest import generate_agent_manifest

            print(json.dumps(generate_agent_manifest(), indent=2))
            return 0

        if args.command == "serve":
            from .mcp.server import serve

            return serve()

        if args.command == "product" and args.product_command == "check-contract":
            from .contracts import validate_contract

            product_result = validate_document(args.product)
            contract_result = validate_contract(args.contract)
            passed = product_result.valid and contract_result.passed
            payload = {
                "passed": passed,
                "product": product_result.to_dict(),
                "contract": contract_result.to_dict(),
                "summary": _contract_check_summary(
                    product_result.valid,
                    contract_result.passed,
                ),
            }
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(payload["summary"])
                if not product_result.valid:
                    print("Product findings:")
                    for error in product_result.errors:
                        print(f"- {error}")
                if not contract_result.passed:
                    print("Contract findings:")
                    for finding in contract_result.findings:
                        print(f"- {finding.code}: {finding.message}")
            return 0 if passed else 1

        if args.command == "product" and args.product_command == "resolve-contracts":
            from .contracts import resolve_product_contracts

            references = resolve_product_contracts(args.product)
            if args.json:
                print(
                    json.dumps(
                        {"references": [ref.to_dict() for ref in references]},
                        indent=2,
                    )
                )
            else:
                if not references:
                    print("No Data Contract references found.")
                for reference in references:
                    print(f"{reference.pointer} -> {reference.href}")
            return 0

        if args.command == "product" and args.product_command == "contract-report":
            from .contracts import generate_product_contract_report

            report = generate_product_contract_report(args.product, args.contract)
            _print_product_contract_report(report, args.json)
            return 0 if report.passed else 1

        if args.command == "product" and args.product_command == "align-contract":
            from .contracts import check_product_contract_alignment

            alignment = check_product_contract_alignment(
                args.product,
                args.contract,
                run_contract_tests=args.run_contract_tests,
            )
            if args.json:
                print(json.dumps(alignment.to_dict(), indent=2))
            else:
                print(alignment.summary)
                for alignment_finding in alignment.findings:
                    print(f"- {alignment_finding.code}: {alignment_finding.message}")
            return 0 if alignment.passed else 1

        if args.command == "product" and args.product_command == "contract-schema":
            from .contracts import extract_contract_schema

            schema = extract_contract_schema(args.contract)
            if args.json:
                print(json.dumps(schema.to_dict(), indent=2))
            else:
                print(
                    f"{schema.path}: {schema.model_count} model(s), "
                    f"{schema.field_count} field(s)"
                )
                for model in schema.models:
                    print(f"- {model.name}: {len(model.fields)} field(s)")
            return 0 if not schema.findings else 1

        if args.command == "product" and args.product_command == "export-contract":
            from .contracts import export_contract

            export_result = export_contract(args.contract, args.format)
            if args.json:
                print(json.dumps(export_result.to_dict(), indent=2))
            elif export_result.exported:
                if isinstance(export_result.content, str):
                    print(export_result.content)
                else:
                    print(json.dumps(export_result.content, indent=2))
            else:
                for export_finding in export_result.findings:
                    print(f"- {export_finding.code}: {export_finding.message}")
            return 0 if export_result.exported else 1

        if args.command == "product" and args.product_command == "audit":
            from .contracts import generate_product_contract_report

            report = generate_product_contract_report(args.product, args.contract)
            payload = report.to_dict()
            payload["live_contract_tests_requested"] = args.run_contract_tests
            if args.run_contract_tests:
                findings = payload.get("findings")
                if isinstance(findings, list):
                    findings.append(
                        {
                            "code": "LIVE_TESTS_NOT_IMPLEMENTED",
                            "message": (
                                "Live Data Contract tests are not implemented in this "
                                "SDK command yet."
                            ),
                            "severity": "warning",
                            "path": None,
                            "source": "open-data-products",
                        }
                    )
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(payload["summary"])
                if args.run_contract_tests:
                    print("- LIVE_TESTS_NOT_IMPLEMENTED: live tests not run")
            return 0 if report.passed else 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


def _contract_check_summary(product_valid: bool, contract_valid: bool) -> str:
    product_state = "valid" if product_valid else "invalid"
    contract_state = "valid" if contract_valid else "invalid"
    return f"Product {product_state}; Data Contract {contract_state}."


def _print_product_contract_report(
    report: "ProductContractReport",
    as_json: bool,
) -> None:
    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
        return
    print(report.summary)
    for finding in report.findings:
        print(f"- {finding.code}: {finding.message}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
