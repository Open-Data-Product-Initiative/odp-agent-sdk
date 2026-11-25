"""Product command parser and handlers for the unified CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from .agent import validate_document
from ._io import load_mapping

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
  wrap-contract       Generate an ODPS 4.2 draft from an ODCS contract
  wrap-dcat           Generate an ODPS 4.2 draft from a selected DCAT resource
  wrap-dprod          Generate an ODPS 4.2 draft from an explicit DPROD product
  export-dprod        Export an ODPS 4.2 definition as DPROD Turtle and JSON-LD

Examples:
  open-data-products product resolve-contracts product.yaml --json
  open-data-products product contract-report product.yaml contract.yaml --json
  open-data-products product audit product.yaml --contract contract.yaml --json
  open-data-products product wrap-contract --input contracts/orders.yaml --output products/orders.yaml
  open-data-products product wrap-dcat --input catalog.ttl --resource https://example.test/dataset/orders --output products/orders.yaml
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
    wrap_contract_parser = product_subparsers.add_parser(
        "wrap-contract",
        help="Generate an ODPS 4.2 draft from an ODCS contract",
    )
    wrap_contract_parser.add_argument(
        "contract",
        nargs="?",
        help="Deprecated positional ODCS contract path or URI; prefer --input",
    )
    wrap_contract_parser.add_argument(
        "--input",
        dest="input_contract",
        help="ODCS contract path or URI to wrap",
    )
    wrap_contract_parser.add_argument(
        "--output", "-o", required=True, help="Output ODPS YAML path"
    )
    wrap_contract_parser.add_argument(
        "--inline-contract",
        action="store_true",
        help="Embed the complete parsed ODCS document instead of contractURL",
    )
    wrap_contract_parser.add_argument(
        "--enrich",
        action="store_true",
        help="Enrich the draft with a business description and discovery tags",
    )
    wrap_contract_parser.add_argument(
        "--full-draft",
        action="store_true",
        help="Fill wider ODPS draft details; requires --enrich",
    )
    wrap_contract_parser.add_argument(
        "--contract-url", help="Override the generated ODPS contractURL"
    )
    wrap_contract_parser.add_argument("--product-name", help="Override product name")
    wrap_contract_parser.add_argument("--product-id", help="Override product ID")
    wrap_contract_parser.add_argument("--product-type", help="Override product type")
    wrap_contract_parser.add_argument(
        "--language", help="Set the ODPS content language"
    )
    wrap_contract_parser.add_argument(
        "--config", help="Generation config YAML used only with --enrich"
    )
    wrap_contract_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and validate without writing output",
    )
    wrap_contract_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacement of an existing output",
    )
    wrap_contract_parser.add_argument("--json", action="store_true", help="Emit JSON")
    wrap_dcat_parser = product_subparsers.add_parser(
        "wrap-dcat", help="Generate an ODPS 4.2 draft from a selected DCAT resource"
    )
    wrap_dcat_parser.add_argument(
        "--input",
        required=True,
        help="DCAT RDF file, directory, or public HTTP(S) catalog",
    )
    wrap_dcat_parser.add_argument(
        "--resource",
        required=True,
        action="append",
        help="DCAT Dataset, DatasetSeries, or DataService IRI; repeat for a batch",
    )
    wrap_dcat_parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output ODPS YAML path, or an output directory for several resources",
    )
    wrap_dcat_parser.add_argument(
        "--enrich",
        action="store_true",
        help="Add review-required AI business description and discovery tags",
    )
    wrap_dcat_parser.add_argument(
        "--full-draft",
        action="store_true",
        help="Include wider review-required AI business proposals; requires --enrich",
    )
    wrap_dcat_parser.add_argument(
        "--config", help="Generation config YAML used only with --enrich"
    )
    wrap_dcat_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacement of an existing output",
    )
    wrap_dcat_parser.add_argument("--json", action="store_true", help="Emit JSON")
    wrap_dprod_parser = product_subparsers.add_parser(
        "wrap-dprod", help="Generate an ODPS 4.2 draft from a DPROD DataProduct"
    )
    wrap_dprod_parser.add_argument("--input", required=True, help="DPROD RDF source")
    wrap_dprod_parser.add_argument(
        "--resource", required=True, help="DPROD DataProduct IRI"
    )
    wrap_dprod_parser.add_argument(
        "--output", "-o", required=True, help="Output ODPS YAML path"
    )
    wrap_dprod_parser.add_argument("--overwrite", action="store_true")
    wrap_dprod_parser.add_argument("--json", action="store_true", help="Emit JSON")
    export_dprod_parser = product_subparsers.add_parser(
        "export-dprod", help="Write deterministic DPROD Turtle and JSON-LD from ODPS"
    )
    export_dprod_parser.add_argument(
        "--input", required=True, help="ODPS 4.2 YAML or JSON"
    )
    export_dprod_parser.add_argument(
        "--output", "-o", required=True, help="Output basename"
    )
    export_dprod_parser.add_argument("--overwrite", action="store_true")
    export_dprod_parser.add_argument("--json", action="store_true", help="Emit JSON")


def handle_product_command(args: argparse.Namespace) -> int:
    """Run the selected product command."""
    if args.product_command == "wrap-dcat":
        from .dcat import wrap_dcat_resource, wrap_dcat_resources

        results = (
            wrap_dcat_resources(
                args.input,
                args.resource,
                args.output,
                overwrite=args.overwrite,
                use_ai=args.enrich,
                extend=args.full_draft,
                config=args.config,
            )
            if len(args.resource) > 1
            else [
                wrap_dcat_resource(
                    args.input,
                    args.resource[0],
                    args.output,
                    overwrite=args.overwrite,
                    use_ai=args.enrich,
                    extend=args.full_draft,
                    config=args.config,
                )
            ]
        )
        result = results[0]
        if args.json:
            print(
                json.dumps({"results": [item.to_dict() for item in results]}, indent=2)
            )
        else:
            for item in results:
                state = "valid" if item.validation.valid else "invalid"
                print(f"ODPS 4.2 DCAT draft {state}: {item.output}")
                for warning in item.warnings:
                    print(f"- {warning}")
                for error in item.validation.errors:
                    print(f"- ODPS_VALIDATION: {error}")
        return 0 if all(item.validation.valid for item in results) else 1

    if args.product_command == "wrap-dprod":
        from .dprod import wrap_dprod_resource

        result = wrap_dprod_resource(
            args.input, args.resource, args.output, overwrite=args.overwrite
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            state = "valid" if result.validation.valid else "invalid"
            print("ODPS 4.2 DPROD draft {}: {}".format(state, result.output))
            for warning in result.warnings:
                print("- " + warning)
        return 0 if result.validation.valid else 1

    if args.product_command == "export-dprod":
        from .dprod import write_dprod_export

        result = write_dprod_export(
            load_mapping(Path(args.input), root_name="ODPS document"),
            args.output,
            overwrite=args.overwrite,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("DPROD Turtle: " + str(result["turtle_output"]))
            print("DPROD JSON-LD: " + str(result["jsonld_output"]))
        return 0 if result["validation"]["conforms"] else 1

    if args.product_command == "wrap-contract":
        from .contracts import wrap_contract

        if args.input_contract and args.contract:
            raise ValueError(
                "Pass either --input or the positional contract argument, not both"
            )
        contract = args.input_contract or args.contract
        if not contract:
            raise ValueError("wrap-contract requires --input")

        result = wrap_contract(
            contract,
            args.output,
            inline_contract=args.inline_contract,
            use_ai=args.enrich,
            extend=args.full_draft,
            contract_url=args.contract_url,
            product_name=args.product_name,
            product_id=args.product_id,
            product_type=args.product_type,
            language=args.language,
            config=args.config,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            destination = args.output if not args.dry_run else "(dry run)"
            state = "valid" if result.validation.valid else "invalid"
            print(f"ODPS 4.2 draft {state}: {destination}")
            for warning in result.warnings:
                print(f"- {warning}")
            for error in result.errors:
                print(f"- {error}")
            for error in result.validation.errors:
                print(f"- ODPS_VALIDATION: {error}")
        return 0 if result.validation.valid else 1

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
