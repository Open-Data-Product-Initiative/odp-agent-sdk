"""Inspect any Open Data Products document from the command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from open_data_products import (
    explain_document,
    list_resources,
    load_document,
    resolve_references,
    validate_document,
)


def inspect_document(path: Path) -> Dict[str, Any]:
    """Return a validation, explanation, reference, and resource report."""
    document = load_document(path)
    validation = validate_document(document, path=path)
    references = resolve_references(document, path=path)
    resources = [
        {
            "id": resource.id,
            "spec": resource.spec,
            "type": resource.type,
            "description": resource.description,
        }
        for resource in list_resources()
    ]

    return {
        "document": {"path": str(path)},
        "validation": validation.to_dict(),
        "explanation": explain_document(document, path=path),
        "references": [reference.to_dict() for reference in references],
        "resources": resources,
    }


def render_text(report: Dict[str, Any]) -> str:
    """Render an inspector report for terminal reading."""
    validation = report["validation"]
    references = report["references"]
    resources = report["resources"]
    lines = [
        "ODP Document Inspector",
        f"Path: {report['document']['path']}",
        f"Spec: {validation['spec']}",
        f"Kind: {validation['kind']}",
        f"Valid: {'yes' if validation['valid'] else 'no'}",
        "",
        "Explanation:",
        report["explanation"].rstrip(),
        "",
        "References:",
    ]

    if references:
        for reference in references:
            lines.append(f"- {reference['pointer']} -> {reference['ref']}")
    else:
        lines.append("- none")

    lines.extend(["", "Bundled resources:"])
    for resource in resources:
        lines.append(f"- {resource['id']} ({resource['spec']}, {resource['type']})")

    errors = validation.get("errors") or []
    warnings = validation.get("warnings") or []
    if errors:
        lines.extend(["", "Errors:"])
        lines.extend(f"- {error}" for error in errors)
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)

    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """Build the inspector command parser."""
    parser = argparse.ArgumentParser(
        prog="odp-document-inspector",
        description="Inspect an ODPS, ODPC, ODPG, or ODPV YAML/JSON document.",
    )
    parser.add_argument("document", help="Path to the document to inspect")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Run the ODP document inspector sample app."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report = inspect_document(Path(args.document))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report), end="")
    return 0 if report["validation"]["valid"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
