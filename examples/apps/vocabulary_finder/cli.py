"""Search bundled ODPV vocabulary terms from the command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from open_data_products.odpv import search_vocabulary


def find_terms(query: str, limit: int) -> Dict[str, Any]:
    """Return ODPV vocabulary matches for a query."""
    matches = search_vocabulary(query, limit=limit)
    return {
        "query": query,
        "limit": limit,
        "count": len(matches),
        "matches": matches,
    }


def english(value: Any, fallback: str = "") -> str:
    """Return an English multilingual value when available."""
    if isinstance(value, dict):
        item = value.get("en", fallback)
        if isinstance(item, list):
            return "; ".join(str(part) for part in item)
        return str(item)
    if isinstance(value, list):
        return "; ".join(str(part) for part in value)
    return str(value) if value is not None else fallback


def render_text(report: Dict[str, Any]) -> str:
    """Render vocabulary matches for terminal reading."""
    lines = [
        "ODPV Vocabulary Finder",
        f"Query: {report['query']}",
        f"Matches: {report['count']}",
    ]

    if not report["matches"]:
        lines.append("")
        lines.append("No matching ODPV terms found.")
        return "\n".join(lines) + "\n"

    for match in report["matches"]:
        related_terms = ", ".join(match.get("relatedTerms", [])) or "(none)"
        matched_fields = ", ".join(match.get("matchedFields", [])) or "(none)"
        lines.extend(
            [
                "",
                match["id"],
                f"  Section: {match['section']}",
                f"  Score: {match['score']}",
                f"  URI: {match['uri']}",
                f"  Matched fields: {matched_fields}",
                f"  Definition: {english(match.get('definition'))}",
                f"  Related terms: {related_terms}",
            ]
        )

    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """Build the vocabulary finder command parser."""
    parser = argparse.ArgumentParser(
        prog="odp-vocabulary-finder",
        description="Search bundled ODPV vocabulary terms.",
    )
    parser.add_argument("query", help="Natural-language vocabulary search query")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of matches to return",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Run the ODPV vocabulary finder sample app."""
    parser = build_parser()
    args = parser.parse_args(argv)

    report = find_terms(args.query, args.limit)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report), end="")
    return 0 if report["matches"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
