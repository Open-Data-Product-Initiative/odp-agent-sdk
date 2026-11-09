"""CLI parser and execution helpers for DCAT and DPROD interoperability."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .cli_core import print_error_payload
from .dcat import discover_dcat_catalog, render_dcat_catalog_html
from .dprod import discover_dprod_catalog, validate_dprod


def add_interop_subparsers(
    subparsers: argparse._SubParsersAction,
    portfolio_subparsers: argparse._SubParsersAction,
) -> None:
    """Register DCAT and DPROD commands on their established CLI paths."""
    dprod_validate_parser = subparsers.add_parser(
        "dprod-validate", help="Validate RDF against pinned DPROD 1.0 Beta 2 shapes"
    )
    dprod_validate_parser.add_argument("source", help="DPROD RDF source")
    dprod_validate_parser.add_argument("--json", action="store_true", help="Emit JSON")

    portfolio_dcat_parser = portfolio_subparsers.add_parser(
        "discover-dcat",
        help="Analyze a local or bounded remote DCAT catalog",
    )
    portfolio_dcat_parser.add_argument(
        "source", help="RDF file, directory, file URI, or public HTTP(S) catalog"
    )
    portfolio_dcat_parser.add_argument(
        "--output", "-o", help="Optional self-contained HTML report path"
    )
    portfolio_dcat_parser.add_argument("--json", action="store_true", help="Emit JSON")

    portfolio_dprod_parser = portfolio_subparsers.add_parser(
        "discover-dprod", help="Analyze explicit DPROD 1.0 Beta 2 products"
    )
    portfolio_dprod_parser.add_argument(
        "source", help="RDF file, directory, file URI, or public HTTP(S) source"
    )
    portfolio_dprod_parser.add_argument("--json", action="store_true", help="Emit JSON")


def handle_interop_command(args: argparse.Namespace) -> Optional[int]:
    """Run a DCAT or DPROD command, or return None for other commands."""
    if args.command == "dprod-validate":
        validation_result = validate_dprod(args.source)
        if args.json:
            print(json.dumps(validation_result.to_dict(), indent=2))
        else:
            print("DPROD Beta 2 SHACL conforms: {}".format(validation_result.conforms))
            for violation in validation_result.violations:
                print("- {}: {}".format(violation.property_path, violation.message))
        return 0 if validation_result.conforms else 1

    if args.command != "portfolio":
        return None
    if args.portfolio_command == "discover-dprod":
        try:
            dprod_result = discover_dprod_catalog(args.source)
        except (FileNotFoundError, ValueError) as exc:
            print_error_payload(exc, as_json=args.json, spec="dprod")
            return 1
        if args.json:
            print(json.dumps(dprod_result.to_dict(), indent=2))
        else:
            print("DPROD products: {}".format(len(dprod_result.products)))
            print("SHACL conforms: {}".format(dprod_result.validation.conforms))
        return 0

    if args.portfolio_command == "discover-dcat":
        try:
            dcat_result = discover_dcat_catalog(args.source)
            payload = dcat_result.to_dict()
            if args.output:
                destination = Path(args.output)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(
                    render_dcat_catalog_html(dcat_result), encoding="utf-8"
                )
                payload["html"] = str(destination)
        except (FileNotFoundError, ValueError) as exc:
            print_error_payload(exc, as_json=args.json, spec="dcat")
            return 1
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("DCAT resources: {}".format(len(dcat_result.resources)))
            print("Relationships: {}".format(len(dcat_result.relationships)))
            print("Findings: {}".format(len(dcat_result.findings)))
            if args.output:
                print("HTML: {}".format(args.output))
        return 0

    return None
