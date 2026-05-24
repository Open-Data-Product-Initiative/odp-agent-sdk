"""Tests for the weekly SDK capability drift report."""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_capability_drift.py"


def load_script_module() -> ModuleType:
    """Load the capability drift script as an importable test module."""
    spec = importlib.util.spec_from_file_location("check_capability_drift", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_capability_drift"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_inventory_tracks_odpg_source_scripts() -> None:
    drift = load_script_module()

    sources = {capability.upstream_source for capability in drift.DEFAULT_CAPABILITIES}

    assert "odpg-v1.0/source/scripts/odpg_validate.py" in sources
    assert "odpg-v1.0/source/scripts/odpg_agent_context.py" in sources
    assert "odpg-v1.0/source/scripts/generate_graph_explorer.py" in sources


def test_report_renders_history_friendly_capability_statuses() -> None:
    drift = load_script_module()

    rows = drift.evaluate_capabilities(
        [
            drift.Capability(
                spec="ODPG",
                upstream_source="odpg-v1.0/source/scripts/odpg_validate.py",
                capability="Validate ODPG graph documents",
                api_symbol="open_data_products.odpg:validate_graph",
                cli_marker="odpg-analyze",
                mcp_tool="validate_document",
            ),
            drift.Capability(
                spec="ODPV",
                upstream_source="odpv-v1.0/scripts/agent_vocab_helper.py",
                capability="Resolve vocabulary text to canonical term context",
            ),
        ]
    )

    report = drift.render_report(rows, run_timestamp="2026-05-23T12:00:00Z")

    assert "# SDK Capability Drift Report" in report
    assert "Last drift detection run: `2026-05-23T12:00:00Z`" in report
    assert "| ODPG | `odpg-v1.0/source/scripts/odpg_validate.py` |" in report
    assert "| ODPV | `odpv-v1.0/scripts/agent_vocab_helper.py` |" in report
    assert "Covered" in report
    assert "Review" in report


def test_graph_explorer_capability_uses_unified_cli_marker() -> None:
    drift = load_script_module()

    marker_by_source = {
        capability.upstream_source: capability.cli_marker
        for capability in drift.DEFAULT_CAPABILITIES
    }

    assert (
        marker_by_source["odpg-v1.0/source/scripts/generate_graph_explorer.py"]
        == "odpg-generate"
    )


def test_targeted_capability_drifts_are_mapped_to_sdk_surfaces() -> None:
    drift = load_script_module()

    rows = drift.evaluate_capabilities()
    by_source = {row.upstream_source: row for row in rows}

    odpv = by_source["odpv-v1.0/scripts/agent_vocab_helper.py"]
    assert odpv.api_status == "Covered"
    assert odpv.cli_status == "Covered"
    assert odpv.mcp_status == "Covered"
    assert odpv.status == "Covered"

    odpc = by_source["odpc-v1.0/scripts/generate_catalog_artifacts.py"]
    assert odpc.api_status == "Covered"
    assert odpc.cli_status == "Covered"
    assert odpc.mcp_status == "Covered"
    assert odpc.status == "Covered"


def test_check_mode_reuses_existing_timestamp(tmp_path: Path) -> None:
    drift = load_script_module()
    report_path = tmp_path / "2026-05-23-sdk-capability-drift.md"
    rows = drift.evaluate_capabilities([])
    report_path.write_text(
        drift.render_report(rows, run_timestamp="2026-05-23T08:30:00Z"),
        encoding="utf-8",
    )

    assert drift.check_report(report_path, rows) == 0
