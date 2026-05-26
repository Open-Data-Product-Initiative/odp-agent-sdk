#!/usr/bin/env python3
"""Generate SDK capability drift reports for upstream ODP spec tooling."""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT / "docs/capability-drift"
DEFAULT_REPORT_NAME = "sdk-capability-drift.md"
RUN_TIMESTAMP_RE = re.compile(
    r"^(?:- )?Last drift detection run: `([^`]+)`$", re.MULTILINE
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class Capability:
    """One upstream script capability and its expected SDK exposure."""

    spec: str
    upstream_source: str
    capability: str
    api_symbol: Optional[str] = None
    cli_marker: Optional[str] = None
    mcp_tool: Optional[str] = None
    notes: str = ""


@dataclass(frozen=True)
class CapabilityRow:
    """Evaluated SDK exposure for one upstream capability."""

    spec: str
    upstream_source: str
    capability: str
    api_status: str
    cli_status: str
    mcp_status: str
    status: str
    notes: str


DEFAULT_CAPABILITIES: Sequence[Capability] = (
    Capability(
        spec="ODPG",
        upstream_source="odpg-v1.0/source/scripts/odpg_validate.py",
        capability="Validate ODPG graph documents",
        api_symbol="open_data_products.odpg:validate_graph",
        cli_marker="validate",
        mcp_tool="validate_document",
    ),
    Capability(
        spec="ODPG",
        upstream_source="odpg-v1.0/source/scripts/odpg_summary.py",
        capability="Summarize ODPG graph metadata, nodes, edges, and confidence values",
        api_symbol="open_data_products.odpg:summarize_graph",
        cli_marker="odpg-summary",
        mcp_tool="summarize_graph",
    ),
    Capability(
        spec="ODPG",
        upstream_source="odpg-v1.0/source/scripts/odpg_traverse.py",
        capability="Traverse ODPG relationship paths from a focus node",
        api_symbol="open_data_products.odpg:traverse_graph",
        cli_marker="odpg-traverse",
        mcp_tool="traverse_graph",
    ),
    Capability(
        spec="ODPG",
        upstream_source="odpg-v1.0/source/scripts/odpg_analyze.py",
        capability="Run ODPG strategic and governance analysis checks",
        api_symbol="open_data_products.odpg:analyze_graph",
        cli_marker="odpg-analyze",
        mcp_tool="analyze_graph",
    ),
    Capability(
        spec="ODPG",
        upstream_source="odpg-v1.0/source/scripts/odpg_agent_context.py",
        capability="Extract trusted ODPG graph context around a focus node",
        api_symbol="open_data_products.odpg:agent_context",
        cli_marker="odpg-agent-context",
        mcp_tool="agent_context",
    ),
    Capability(
        spec="ODPG",
        upstream_source="odpg-v1.0/source/scripts/generate_graph_explorer.py",
        capability="Generate a standalone ODPG graph explorer",
        api_symbol="open_data_products.odpg:generate_graph_explorer",
        cli_marker="odpg-generate",
        notes="MCP remains read-only; graph explorer generation is not exposed as an MCP tool.",
    ),
    Capability(
        spec="ODPG",
        upstream_source="odpg-v1.0/source/scripts/odpg_convert.py",
        capability="Convert external graph formats into ODPG YAML",
        api_symbol="open_data_products.odpg:convert_graph",
        cli_marker="odpg-convert",
        notes="Conversion writes generated YAML and is intentionally not exposed through the safe MCP surface.",
    ),
    Capability(
        spec="ODPV",
        upstream_source="odpv-v1.0/scripts/search_vocab.py",
        capability="Search ODPV vocabulary terms",
        api_symbol="open_data_products.odpv:search_vocabulary",
        cli_marker="search_main",
        mcp_tool="search_terms",
    ),
    Capability(
        spec="ODPV",
        upstream_source="odpv-v1.0/scripts/validate_vocab.py",
        capability="Validate bundled ODPV vocabulary data",
        api_symbol="open_data_products.odpv:validate_vocabulary",
        cli_marker="validate_main",
        notes="Useful SDK capability; not currently a dedicated MCP tool.",
    ),
    Capability(
        spec="ODPV",
        upstream_source="odpv-v1.0/scripts/generate_vocab_artifacts.py",
        capability="Generate derived ODPV vocabulary artifacts",
        api_symbol="open_data_products.odpv:write_artifacts",
        cli_marker="generate_main",
        notes="Artifact generation writes files and is intentionally not exposed through the safe MCP surface.",
    ),
    Capability(
        spec="ODPV",
        upstream_source="odpv-v1.0/scripts/agent_vocab_helper.py",
        capability="Resolve, explain, and package agent-ready vocabulary term context",
        api_symbol="open_data_products.odpv:agent_vocabulary_context",
        cli_marker="odpv-context",
        mcp_tool="vocabulary_term_context",
        notes="Ported as ODPV resolve/explain/relationship/context API, CLI, and safe MCP term-context tools.",
    ),
    Capability(
        spec="ODPV",
        upstream_source="odpv-v1.0/scripts/check_cross_spec_drift.py",
        capability="Track terminology drift across ODPS, ODPC, ODPG, and ODPV",
        notes="Upstream maintenance report; review whether SDK should link to reports rather than duplicate terms drift.",
    ),
    Capability(
        spec="ODPC",
        upstream_source="odpc-v1.0/scripts/search_objects.py",
        capability="Search ODPC catalog object guidance records",
        api_symbol="open_data_products.odpc:search_objects",
        cli_marker="search_main",
        mcp_tool="search_objects",
    ),
    Capability(
        spec="ODPC",
        upstream_source="odpc-v1.0/scripts/validate_catalog.py",
        capability="Validate ODPC catalog documents",
        api_symbol="open_data_products.odpc:validate_catalog",
        cli_marker="validate_main",
        mcp_tool="validate_document",
    ),
    Capability(
        spec="ODPC",
        upstream_source="odpc-v1.0/scripts/explain_catalog.py",
        capability="Explain ODPC catalogs for humans and AI agents",
        api_symbol="open_data_products.odpc:explain_catalog",
        cli_marker="explain_main",
        mcp_tool="explain_document",
    ),
    Capability(
        spec="ODPC",
        upstream_source="odpc-v1.0/scripts/generate_catalog_artifacts.py",
        capability="Generate derived ODPC catalog schema artifacts",
        api_symbol="open_data_products.odpc:write_catalog_artifacts",
        cli_marker="odpc-artifacts",
        mcp_tool="catalog_artifacts",
        notes="SDK can generate/check artifacts through API and CLI; MCP exposes read-only generated artifact metadata/content.",
    ),
    Capability(
        spec="ODPC",
        upstream_source="odpc-v1.0/scripts/build_catalog.py",
        capability="Build one ODPC catalog from ODPC fragments and ODPS product files",
        api_symbol="open_data_products.odpc:build_catalog",
        cli_marker="odpc-build",
        notes="Catalog building writes through the CLI/API workflow; MCP does not return full generated catalog bodies.",
    ),
    Capability(
        spec="ODPC",
        upstream_source="odpc-v1.0/scripts/check_agent_artifacts.py",
        capability="Check ODPC schema, examples, JSONL, and llms.txt agent artifacts",
        notes="Upstream docs consistency check; likely outside the SDK runtime surface.",
    ),
)


def current_run_timestamp() -> str:
    """Return the current UTC report timestamp."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def dated_report_path(run_timestamp: str) -> Path:
    """Return the dated report path for a run timestamp."""
    return DEFAULT_REPORT_DIR / f"{run_timestamp[:10]}-{DEFAULT_REPORT_NAME}"


def existing_run_timestamp(report_path: Path) -> Optional[str]:
    """Read the run timestamp from an existing report."""
    if not report_path.exists():
        return None
    match = RUN_TIMESTAMP_RE.search(report_path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def has_api_symbol(symbol: Optional[str]) -> bool:
    """Return true when a module attribute exists."""
    if not symbol:
        return False
    module_name, _, attribute_name = symbol.partition(":")
    if not module_name or not attribute_name:
        return False
    module = importlib.import_module(module_name)
    return hasattr(module, attribute_name)


def has_cli_marker(marker: Optional[str]) -> bool:
    """Return true when the configured CLI marker exists in SDK command files."""
    if not marker:
        return False
    search_files = (
        ROOT / "pyproject.toml",
        ROOT / "open_data_products" / "cli.py",
        ROOT / "open_data_products" / "odpc" / "cli.py",
        ROOT / "open_data_products" / "odpg" / "cli.py",
        ROOT / "open_data_products" / "odpv" / "cli.py",
    )
    return any(
        path.exists() and marker in path.read_text(encoding="utf-8")
        for path in search_files
    )


def mcp_tool_names() -> Set[str]:
    """Return registered MCP tool names."""
    from open_data_products.mcp.tools import TOOLS

    return {str(tool["name"]) for tool in TOOLS}


def has_mcp_tool(tool_name: Optional[str]) -> bool:
    """Return true when the MCP tool registry contains the tool."""
    return bool(tool_name and tool_name in mcp_tool_names())


def exposure_status(expected: Optional[str], present: bool) -> str:
    """Render one API/CLI/MCP exposure status."""
    if not expected:
        return "Not mapped"
    return "Covered" if present else "Gap"


def row_status(statuses: Iterable[str]) -> str:
    """Summarize exposure statuses for one capability."""
    values = list(statuses)
    if all(status == "Not mapped" for status in values):
        return "Review"
    if all(status in ("Covered", "Not mapped") for status in values):
        if any(status == "Not mapped" for status in values):
            return "Partial"
        return "Covered"
    return "Possible drift"


def evaluate_capabilities(
    capabilities: Sequence[Capability] = DEFAULT_CAPABILITIES,
) -> List[CapabilityRow]:
    """Evaluate upstream capabilities against SDK API, CLI, and MCP exposure."""
    rows = []
    for capability in capabilities:
        api_status = exposure_status(
            capability.api_symbol,
            has_api_symbol(capability.api_symbol),
        )
        cli_status = exposure_status(
            capability.cli_marker,
            has_cli_marker(capability.cli_marker),
        )
        mcp_status = exposure_status(
            capability.mcp_tool,
            has_mcp_tool(capability.mcp_tool),
        )
        statuses = (api_status, cli_status, mcp_status)
        rows.append(
            CapabilityRow(
                spec=capability.spec,
                upstream_source=capability.upstream_source,
                capability=capability.capability,
                api_status=api_status,
                cli_status=cli_status,
                mcp_status=mcp_status,
                status=row_status(statuses),
                notes=capability.notes,
            )
        )
    return rows


def markdown_escape(value: str) -> str:
    """Escape Markdown table separators."""
    return value.replace("|", "\\|")


def bold(value: str) -> str:
    """Bold a table cell."""
    return f"**{value}**" if value else value


def render_summary(rows: Sequence[CapabilityRow]) -> List[str]:
    """Render the unresolved drift summary section."""
    possible = [row for row in rows if row.status in ("Possible drift", "Review")]
    lines = ["## Possible Drift Summary", ""]
    if not possible:
        lines.append("No unresolved capability drift detected.")
        return lines
    lines.extend(
        [
            "| Spec | Source | Capability | Suggested action |",
            "|---|---|---|---|",
        ]
    )
    for row in possible:
        action = (
            "Review whether to add SDK/API/CLI/MCP exposure or mark as upstream-only."
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_escape(row.spec),
                    f"`{markdown_escape(row.upstream_source)}`",
                    markdown_escape(row.capability),
                    action,
                ]
            )
            + " |"
        )
    return lines


def render_spec_rows(spec: str, rows: Sequence[CapabilityRow]) -> List[str]:
    """Render the detailed table for one spec."""
    spec_rows = [row for row in rows if row.spec == spec]
    unresolved = [
        row for row in spec_rows if row.status in ("Possible drift", "Review")
    ]
    lines = [
        f"## {spec} Capability Coverage",
        "",
        f"- Checked capabilities: {len(spec_rows)}",
        f"- Unresolved capabilities: {len(unresolved)}",
        "",
    ]
    if unresolved:
        lines.append(
            "Unresolved capabilities need review before they can be treated as covered."
        )
    else:
        lines.append("No unresolved capability drift detected.")
    lines.extend(
        [
            "",
            "| Spec | Upstream source | Capability | API | CLI | MCP | Status | Notes |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in spec_rows:
        cells = [
            markdown_escape(row.spec),
            f"`{markdown_escape(row.upstream_source)}`",
            markdown_escape(row.capability),
            markdown_escape(row.api_status),
            markdown_escape(row.cli_status),
            markdown_escape(row.mcp_status),
            markdown_escape(row.status),
            markdown_escape(row.notes),
        ]
        if row.status in ("Possible drift", "Review"):
            cells = [bold(cell) for cell in cells]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def render_report(rows: Sequence[CapabilityRow], run_timestamp: str) -> str:
    """Render a Markdown capability drift report."""
    unresolved = [row for row in rows if row.status in ("Possible drift", "Review")]
    partial = [row for row in rows if row.status == "Partial"]
    specs = sorted({row.spec for row in rows})
    lines = [
        "# SDK Capability Drift Report",
        "",
        "This report compares upstream Open Data Product specification helper scripts against the SDK surfaces exposed for humans and AI agents.",
        "",
        f"Last drift detection run: `{run_timestamp}`",
        "",
        "- Upstream sources: ODPC, ODPG, and ODPV specification repositories",
        "- SDK surfaces: public Python API, unified/spec CLI helpers, and MCP tools",
        f"- Checked capabilities: {len(rows)}",
        f"- Partial capabilities: {len(partial)}",
        f"- Unresolved capabilities: {len(unresolved)}",
        "",
    ]
    if unresolved:
        lines.append(
            "Possible capability drift detected. Review rows marked `Review` or `Possible drift`."
        )
    else:
        lines.append("No unresolved capability drift detected.")
    lines.extend(["", *render_summary(rows)])
    for spec in specs:
        lines.extend(["", *render_spec_rows(spec, rows)])
    return "\n".join(lines) + "\n"


def check_report(report_path: Path, rows: Sequence[CapabilityRow]) -> int:
    """Validate an existing report without changing its timestamp."""
    run_timestamp = existing_run_timestamp(report_path)
    if not run_timestamp:
        print(
            f"Missing capability drift report timestamp: {report_path}", file=sys.stderr
        )
        return 1
    expected = render_report(rows, run_timestamp)
    if not report_path.exists():
        print(f"Missing capability drift report: {report_path}", file=sys.stderr)
        return 1
    current = report_path.read_text(encoding="utf-8")
    if current != expected:
        print(f"Capability drift report is out of sync: {report_path}", file=sys.stderr)
        return 1
    print("Capability drift report is in sync")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the capability drift report generator."""
    parser = argparse.ArgumentParser(
        description="Compare upstream ODP spec helper scripts against SDK exposure."
    )
    parser.add_argument("--report", type=Path, help="Markdown report path")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the existing report is out of sync",
    )
    args = parser.parse_args(argv)

    rows = evaluate_capabilities()
    run_timestamp = current_run_timestamp()
    report_path = args.report if args.report else dated_report_path(run_timestamp)
    if args.check:
        return check_report(report_path, rows)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(rows, run_timestamp), encoding="utf-8")
    unresolved = sum(1 for row in rows if row.status in ("Possible drift", "Review"))
    print(f"Wrote {report_path} capabilities={len(rows)} unresolved={unresolved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
