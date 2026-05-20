"""Command line entry points for ODPG SDK helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from open_data_products.results import ValidationResult

from .graph import (
    agent_context,
    analyze_graph,
    generate_graph_explorer,
    load_graph,
    render_graph_object_records,
    search_graph_objects,
    summarize_graph,
    traverse_graph,
    validate_graph,
)


def search_main(argv: Optional[List[str]] = None) -> int:
    """Search ODPG graph object records from the command line."""
    parser = argparse.ArgumentParser(
        description="Search ODPG graph object records.",
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Keyword query, for example: governance traversal",
    )
    parser.add_argument(
        "--id",
        dest="object_id",
        help="Return one object by id, for example: DataProduct",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON array output")
    args = parser.parse_args(argv)

    records = search_graph_objects(args.query, object_id=args.object_id)
    if args.json:
        print(json.dumps(records, indent=2))
    else:
        sys.stdout.write(render_graph_object_records(records))
    return 0 if records else 1


def validate_main(argv: Optional[List[str]] = None) -> int:
    """Validate an ODPG graph from the command line."""
    parser = argparse.ArgumentParser(description="Validate an ODPG graph YAML file.")
    parser.add_argument(
        "graph",
        nargs="?",
        help="Path to an ODPG YAML graph file. Defaults to bundled graph.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON object output")
    args = parser.parse_args(argv)

    try:
        graph = load_graph(args.graph) if args.graph else load_graph()
    except FileNotFoundError as exc:
        print(f"File not found: {exc.filename}", file=sys.stderr)
        return 1
    except (yaml.YAMLError, ValueError) as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        return 1

    result = validate_graph(graph)
    if not result.valid:
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
            return 1
        path = args.graph or "(bundled ODPG graph)"
        print(f"{path}: invalid ODPG graph", file=sys.stderr)
        for error in result.errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"{args.graph or '(bundled ODPG graph)'}: valid ODPG graph")
    return 0


def _load_valid_graph(graph_path: str) -> Tuple[Dict[str, Any], ValidationResult]:
    graph = load_graph(graph_path)
    result = validate_graph(graph)
    return graph, result


def summary_main(argv: Optional[List[str]] = None) -> int:
    """Summarize an ODPG graph from the command line."""
    parser = argparse.ArgumentParser(
        description="Summarize ODPG graph metadata, nodes, edges, relationship types, and confidence values.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("graph", help="Path to an ODPG YAML graph file")
    args = parser.parse_args(argv)

    try:
        graph = load_graph(args.graph)
    except (FileNotFoundError, yaml.YAMLError, ValueError) as exc:
        print(f"Could not summarize graph: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summarize_graph(graph), indent=2))
    return 0


def traverse_main(argv: Optional[List[str]] = None) -> int:
    """Discover ODPG relationship paths from the command line."""
    parser = argparse.ArgumentParser(
        description="Discover relationship paths from an ODPG node.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("graph", help="Path to an ODPG YAML graph file")
    parser.add_argument("--start", required=True, help="Starting node id")
    parser.add_argument("--depth", type=int, default=2, help="Maximum traversal depth")
    parser.add_argument("--relationship", help="Optional relationship type filter")
    parser.add_argument(
        "--reverse", action="store_true", help="Traverse incoming relationships"
    )
    args = parser.parse_args(argv)

    try:
        graph, result = _load_valid_graph(args.graph)
    except (FileNotFoundError, yaml.YAMLError, ValueError) as exc:
        print(f"Could not traverse graph: {exc}", file=sys.stderr)
        return 1
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


def analyze_main(argv: Optional[List[str]] = None) -> int:
    """Run ODPG strategic and governance checks from the command line."""
    parser = argparse.ArgumentParser(
        description="Run ODPG strategic and governance analysis checks.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("graph", help="Path to an ODPG YAML graph file")
    args = parser.parse_args(argv)

    try:
        graph, result = _load_valid_graph(args.graph)
    except (FileNotFoundError, yaml.YAMLError, ValueError) as exc:
        print(f"Could not analyze graph: {exc}", file=sys.stderr)
        return 1
    if not result.valid:
        print(json.dumps(result.to_dict(), indent=2))
        return 1
    print(
        json.dumps(
            {"warnings": result.warnings, "analysis": analyze_graph(graph)}, indent=2
        )
    )
    return 0


def agent_context_main(argv: Optional[List[str]] = None) -> int:
    """Extract trusted ODPG context around a focus node from the command line."""
    parser = argparse.ArgumentParser(
        description="Extract trusted ODPG graph context around a focus node for AI-agent use.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("graph", help="Path to an ODPG YAML graph file")
    parser.add_argument("--node", required=True, help="Focus node id")
    parser.add_argument("--depth", type=int, default=2, help="Context traversal depth")
    args = parser.parse_args(argv)

    try:
        graph, result = _load_valid_graph(args.graph)
    except (FileNotFoundError, yaml.YAMLError, ValueError) as exc:
        print(f"Could not extract graph context: {exc}", file=sys.stderr)
        return 1
    if not result.valid:
        print(json.dumps(result.to_dict(), indent=2))
        return 1
    payload = agent_context(graph, args.node, args.depth)
    payload["warnings"] = result.warnings
    print(json.dumps(payload, indent=2))
    return 0


def generate_main(argv: Optional[List[str]] = None) -> int:
    """Generate an ODPG graph explorer from the command line."""
    parser = argparse.ArgumentParser(
        description="Generate graph-explorer.html from an ODPG graph YAML file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="graph_yaml",
        type=Path,
        help="Path to graph YAML file. Defaults to bundled graph.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("graph-explorer.html"),
        metavar="PATH",
        help="Output HTML file path",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON object output")
    args = parser.parse_args(argv)

    try:
        output = generate_graph_explorer(args.graph_yaml, args.output)
    except (FileNotFoundError, yaml.YAMLError, ValueError) as exc:
        print(f"Could not generate graph explorer: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "spec": "odpg",
                    "kind": "Graph",
                    "output": str(output),
                    "generated": True,
                },
                indent=2,
            )
        )
    else:
        print(f"Graph Explorer generated successfully: {output}")
    return 0
