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

if TYPE_CHECKING:
    from .contracts import ProductContractReport


def main(argv: Optional[List[str]] = None) -> int:
    """Run the top-level Open Data Products CLI."""
    parser = argparse.ArgumentParser(
        prog="open-data-products",
        description="Agent-oriented tools for the Open Data Products SDK.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

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

    subparsers.add_parser("manifest", help="Emit the ARWS agent manifest").add_argument(
        "--json", action="store_true", help="Emit JSON"
    )

    subparsers.add_parser("serve", help="Run the MCP server over stdio")

    product_parser = subparsers.add_parser(
        "product", help="Product-level orchestration workflows"
    )
    product_subparsers = product_parser.add_subparsers(
        dest="product_command", required=True
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
    resolve_contracts_parser.add_argument("product", help="Path to an ODPS product file")
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
