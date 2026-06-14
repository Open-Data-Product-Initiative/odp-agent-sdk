"""Tests that keep the functional testing report aligned with the suite."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.functional

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "docs" / "reports" / "functional-test-report.md"


def test_functional_report_lists_public_functional_suites() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for expected in (
        "tests/test_functional_agent_api.py",
        "tests/test_functional_cli.py",
        "tests/test_functional_mcp.py",
        "Public Python API",
        "Unified CLI",
        "MCP JSON-RPC",
        "Data Contract orchestration",
        "resolve_product_contracts",
        "check_product_contract_alignment",
        "pytest -q -m functional",
    ):
        assert expected in content
