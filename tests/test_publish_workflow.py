"""Tests for packaging publication workflows."""

import re
from pathlib import Path
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTPYPI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-testpypi.yml"
PYPI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-pypi.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
MANIFEST = REPO_ROOT / "MANIFEST.in"
DOCS_DIR = REPO_ROOT / "docs"
DEVELOPMENT_DOC = DOCS_DIR / "development" / "README.md"


def test_testpypi_workflow_uses_manual_trusted_publishing() -> None:
    content = TESTPYPI_WORKFLOW.read_text(encoding="utf-8")

    for expected in (
        "name: Publish to TestPyPI",
        "workflow_dispatch:",
        "id-token: write",
        "python -m build --quiet",
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
        "python -m build --quiet",
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


def test_package_metadata_includes_portfolio_icon_assets() -> None:
    content = PYPROJECT.read_text(encoding="utf-8")

    assert '"data/portfolio/*.png"' in content


def test_console_scripts_preserve_unified_and_legacy_entry_points() -> None:
    metadata = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    assert metadata["project"]["scripts"] == {
        "open-data-products": "open_data_products.cli:main",
        "open-data-products-odpg-generate": (
            "open_data_products.odpg.cli:generate_main"
        ),
    }


def test_development_notes_document_refactor_compatibility_posture() -> None:
    content = DEVELOPMENT_DOC.read_text(encoding="utf-8")

    assert "Refactor Compatibility Posture" in content
    assert "open-data-products" in content
    assert "open-data-products-odpg-generate" in content
    assert "Do not remove compatibility wrappers" in content


def test_docs_are_grouped_with_readme_at_top() -> None:
    top_level_markdown = sorted(path.name for path in DOCS_DIR.glob("*.md"))

    assert top_level_markdown == ["README.md"]
    for dirname in ("user", "development", "planning", "reports"):
        assert (DOCS_DIR / dirname).is_dir()


def test_markdown_links_point_to_existing_repo_files() -> None:
    markdown_link = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    missing = []

    for path in [README := REPO_ROOT / "README.md", *DOCS_DIR.rglob("*.md")]:
        for match in markdown_link.finditer(path.read_text(encoding="utf-8")):
            target = match.group(1).split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            target_path = (path.parent / target).resolve()
            if not target_path.exists():
                missing.append(f"{path.relative_to(REPO_ROOT)} -> {target}")

    assert missing == []


def test_source_distribution_uses_positive_artifact_includes() -> None:
    content = MANIFEST.read_text(encoding="utf-8")

    for expected in (
        "include README.md",
        "include pyproject.toml",
        "include llms.txt",
        "recursive-include docs *.md",
        "recursive-include examples *.py *.json *.yaml *.html *.md *.graphml",
        "recursive-include images *.png",
        "recursive-include skills */SKILL.md",
        "recursive-exclude tests *",
    ):
        assert expected in content

    for excluded in ("prune .github", "prune scripts", "prune tests"):
        assert excluded not in content
