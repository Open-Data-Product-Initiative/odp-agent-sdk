"""Tests for packaging publication workflows."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TESTPYPI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-testpypi.yml"
PYPI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-pypi.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
MANIFEST = REPO_ROOT / "MANIFEST.in"


def test_testpypi_workflow_uses_manual_trusted_publishing() -> None:
    content = TESTPYPI_WORKFLOW.read_text(encoding="utf-8")

    for expected in (
        "name: Publish to TestPyPI",
        "workflow_dispatch:",
        "id-token: write",
        "python -m build",
        "actions/upload-artifact@v4",
        "pypa/gh-action-pypi-publish@release/v1",
        "repository-url: https://test.pypi.org/legacy/",
    ):
        assert expected in content


def test_pypi_workflow_uses_release_trusted_publishing_with_version_guard() -> None:
    content = PYPI_WORKFLOW.read_text(encoding="utf-8")

    for expected in (
        "name: Publish to PyPI",
        "workflow_dispatch:",
        "release:",
        "types: [published]",
        "id-token: write",
        "python -m build",
        "actions/upload-artifact@v4",
        "pypa/gh-action-pypi-publish@release/v1",
        "Verify package version matches release",
        "EXPECTED_VERSION",
        "open_data_products.__version__",
    ):
        assert expected in content

    assert "repository-url: https://test.pypi.org/legacy/" not in content


def test_package_metadata_includes_mcp_package() -> None:
    content = PYPROJECT.read_text(encoding="utf-8")

    assert '"open_data_products.mcp",' in content


def test_source_distribution_prunes_repo_automation_files() -> None:
    content = MANIFEST.read_text(encoding="utf-8")

    for expected in (
        "prune .codex",
        "prune .github",
        "prune docs/capability-drift",
        "prune scripts",
        "prune tests",
    ):
        assert expected in content
