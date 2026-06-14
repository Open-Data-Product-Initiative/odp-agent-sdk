"""Product command parser and handlers for the unified CLI."""

from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING

from .agent import validate_document

if TYPE_CHECKING:
    from .contracts import ProductContractReport


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


def add_product_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register product workflow commands."""
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


def handle_product_command(args: argparse.Namespace) -> int:
    """Run the selected product command."""
    if args.product_command == "check-contract":
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

    if args.product_command == "resolve-contracts":
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

    if args.product_command == "contract-report":
        from .contracts import generate_product_contract_report

        report = generate_product_contract_report(args.product, args.contract)
        _print_product_contract_report(report, args.json)
        return 0 if report.passed else 1

    if args.product_command == "align-contract":
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

    if args.product_command == "contract-schema":
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

    if args.product_command == "export-contract":
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

    if args.product_command == "audit":
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
