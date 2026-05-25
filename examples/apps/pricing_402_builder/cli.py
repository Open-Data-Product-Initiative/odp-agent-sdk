"""Build HTTP 402 payment envelopes from ODPS pricing plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from open_data_products import (
    detect_document,
    load_document,
    pricing_to_402,
    validate_document,
)
from open_data_products.odps import OpenDataProduct


def build_402_report(path: Path) -> Dict[str, Any]:
    """Return an HTTP 402 report for a priced ODPS product."""
    document = load_document(path)
    spec, kind = detect_document(document)
    if spec != "odps" or not isinstance(document, OpenDataProduct):
        raise ValueError("Pricing 402 envelopes can only be built from ODPS products")

    validation = validate_document(document, path=path)
    if not validation.valid:
        errors = "; ".join(validation.errors) or "validation failed"
        raise ValueError(f"Invalid ODPS product: {errors}")

    envelope = pricing_to_402(document)
    return {
        "document": {
            "path": str(path),
            "spec": spec,
            "kind": kind,
        },
        "product_id": document.product_details.product_id,
        "priced": envelope is not None,
        "envelope": envelope,
    }


def render_text(report: Dict[str, Any]) -> str:
    """Render a pricing envelope report for terminal reading."""
    lines = [
        "ODPS Pricing 402 Builder",
        f"Path: {report['document']['path']}",
        f"Product ID: {report['product_id']}",
        f"Priced: {'yes' if report['priced'] else 'no'}",
    ]

    envelope = report["envelope"]
    if envelope is None:
        lines.append("No pricing plan found.")
        return "\n".join(lines) + "\n"

    lines.append(f"Status: {envelope['status']}")
    lines.append("")
    lines.append("Headers:")
    for name, value in envelope["headers"].items():
        lines.append(f"{name}: {value}")

    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """Build the pricing 402 builder command parser."""
    parser = argparse.ArgumentParser(
        prog="odp-pricing-402-builder",
        description="Build an HTTP 402 payment envelope from an ODPS document.",
    )
    parser.add_argument("document", help="Path to the ODPS document")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Run the ODPS pricing 402 builder sample app."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report = build_402_report(Path(args.document))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report), end="")
    return 0 if report["priced"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
