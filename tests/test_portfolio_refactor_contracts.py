"""Behavior contracts that protect the Portfolio refactor."""

import inspect
from pathlib import Path

import pytest

from open_data_products.generation.models import PortfolioSourceBudget
from open_data_products import (
    PortfolioBuildRequest,
    PortfolioBuildResult,
    PortfolioPipeline,
    PortfolioSourceLanes,
    build_portfolio,
    explain_portfolio,
    localize_portfolio,
    refresh_portfolio,
    render_portfolio,
    sync_portfolio,
)
from open_data_products.portfolio import inspect_portfolio_intake


def _write_render_workspace(workspace: Path) -> None:
    """Write the smallest linked workspace required by the HTML renderer."""
    (workspace / "odpc").mkdir(parents=True)
    (workspace / "odpg").mkdir(parents=True)
    (workspace / "odps" / "products").mkdir(parents=True)
    (workspace / "portfolio.yaml").write_text(
        """
metadata:
  name: Refactor Contract Portfolio
""".lstrip(),
        encoding="utf-8",
    )
    (workspace / "odpc" / "catalog.yaml").write_text(
        """
schema: https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml
version: "1.0"
kind: Catalog
catalog:
  metadata:
    id: CATALOG-REFACTOR
    name:
      en: Refactor Contract Portfolio
    description:
      en: Stable workspace rendering contract.
  businessObjectives: []
  useCases: []
  signals: []
  productReferences: []
""".lstrip(),
        encoding="utf-8",
    )
    (workspace / "odpg" / "graph.yaml").write_text(
        """
schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: "1.0"
kind: Graph
graph:
  metadata:
    id: GRAPH-REFACTOR
    name:
      en: Refactor Contract Graph
  nodes: []
  edges: []
""".lstrip(),
        encoding="utf-8",
    )


def test_portfolio_public_facade_keeps_supported_exports() -> None:
    """Public callers retain the stable Portfolio entry points."""
    assert inspect.isclass(PortfolioBuildRequest)
    assert inspect.isclass(PortfolioBuildResult)
    assert inspect.isclass(PortfolioPipeline)
    assert inspect.isclass(PortfolioSourceLanes)
    assert list(inspect.signature(build_portfolio).parameters) == [
        "workspace",
        "objectives",
        "use_cases",
        "signals",
        "products",
        "title",
        "client",
        "model",
        "run_kind",
        "process_all_sources",
        "context_format",
        "source_budget",
        "source_privacy",
    ]
    for workflow in (
        explain_portfolio,
        localize_portfolio,
        refresh_portfolio,
        render_portfolio,
        sync_portfolio,
    ):
        assert callable(workflow)


def test_rendering_a_workspace_twice_keeps_artifacts_and_html_stable(
    tmp_path: Path,
) -> None:
    """Rendering remains deterministic while implementation moves internally."""
    workspace = tmp_path / "portfolio"
    _write_render_workspace(workspace)

    first = render_portfolio(workspace)
    first_html = (workspace / "index.html").read_text(encoding="utf-8")
    second = render_portfolio(workspace)
    second_html = (workspace / "index.html").read_text(encoding="utf-8")

    assert first["kind"] == "PortfolioRender"
    assert first["html"] == str(workspace / "index.html")
    assert second["kind"] == "PortfolioRender"
    assert first_html == second_html
    assert "Refactor Contract Portfolio" in first_html
    assert "Stable workspace rendering contract." in first_html
    assert 'class="topbar"' in first_html
    assert 'class="panels"' in first_html
    assert "document.addEventListener" in first_html


def test_portfolio_facade_reexports_models_from_private_module() -> None:
    """The public facade keeps model imports stable while moving their home."""
    source = Path("open_data_products/portfolio.py").read_text(encoding="utf-8")

    assert "from ._portfolio_models import" in source
    assert "class PortfolioBuildRequest" not in source


def test_portfolio_facade_delegates_static_presentation_assets() -> None:
    """Static CSS and JavaScript belong to the rendering boundary."""
    source = Path("open_data_products/_portfolio_html.py").read_text(encoding="utf-8")

    assert "from ._portfolio_assets import portfolio_css, portfolio_js" in source


def test_portfolio_facade_imports_shared_value_helpers() -> None:
    """Shared formatting helpers do not stay coupled to the facade."""
    source = Path("open_data_products/_portfolio_workflows.py").read_text(
        encoding="utf-8"
    )

    assert "from ._portfolio_values import" in source
    assert "def _text" not in source


def test_portfolio_facade_imports_shared_identity_helpers() -> None:
    """Normalization can reuse identities without importing the facade."""
    source = Path("open_data_products/_portfolio_plan.py").read_text(encoding="utf-8")

    assert "path_id as _path_id" in source
    assert "title_from_text as _title_from_text" in source


def test_portfolio_facade_imports_shared_change_counter() -> None:
    """Change summaries reuse a value helper outside workflow orchestration."""
    source = Path("open_data_products/_portfolio_html.py").read_text(encoding="utf-8")
    assert "change_list_count as _change_list_count" in source


def test_portfolio_prompt_functions_remain_available() -> None:
    """Prompt callers retain the established Portfolio entry points."""
    from open_data_products.portfolio import (
        render_portfolio_build_prompt,
        render_portfolio_executive_summary_prompt,
    )

    assert callable(render_portfolio_build_prompt)
    assert callable(render_portfolio_executive_summary_prompt)


def test_portfolio_facade_imports_prompt_yaml_helper() -> None:
    """Parser helpers use the private prompting boundary."""
    source = Path("open_data_products/portfolio.py").read_text(encoding="utf-8")
    assert "extract_yaml_text as _extract_yaml_text" in source


def test_workspace_loading_uses_private_layout_model() -> None:
    """Workspace loading receives one explicit layout boundary."""
    source = Path("open_data_products/_portfolio_rendering.py").read_text(
        encoding="utf-8"
    )
    assert "from ._portfolio_workspace_paths import PortfolioWorkspacePaths" in source


def test_portfolio_facade_imports_workspace_document_helpers() -> None:
    """Workspace document defaults do not stay coupled to the facade."""
    source = Path("open_data_products/_portfolio_workflows.py").read_text(
        encoding="utf-8"
    )
    assert "from ._portfolio_workspace import" in source


def test_portfolio_facade_imports_workspace_product_helpers() -> None:
    """Product discovery is provided by the workspace module."""
    source = Path("open_data_products/_portfolio_workflows.py").read_text(
        encoding="utf-8"
    )
    assert "load_product_specs as _load_product_specs" in source


def test_portfolio_facade_imports_workspace_version_helpers() -> None:
    """Version discovery is provided by the workspace module."""
    source = Path("open_data_products/_portfolio_workflows.py").read_text(
        encoding="utf-8"
    )
    assert "portfolio_versions as _portfolio_versions" in source


def test_portfolio_facade_delegates_read_only_intake() -> None:
    """Read-only intake has direct private-module dependencies."""
    source = Path("open_data_products/portfolio.py").read_text(encoding="utf-8")

    assert "from ._portfolio_intake import inspect_portfolio_intake" in source
    assert "def inspect_portfolio_intake" not in source


def test_portfolio_facade_delegates_rendering_and_workspace_loading() -> None:
    """Rendering concerns remain outside orchestration workflows."""
    source = Path("open_data_products/portfolio.py").read_text(encoding="utf-8")

    assert "from ._portfolio_rendering import" in source
    assert "def render_portfolio(" not in source
    assert "def load_portfolio_workspace(" not in source
    assert "def render_portfolio_html(" not in source


def test_portfolio_facade_delegates_generation_workflows() -> None:
    """Build, sync, and localization workflows leave the public facade."""
    source = Path("open_data_products/portfolio.py").read_text(encoding="utf-8")

    assert "from ._portfolio_workflows import" in source
    assert "class PortfolioPipeline" not in source
    assert "def build_portfolio(" not in source
    assert "def sync_portfolio(" not in source
    assert "def localize_portfolio(" not in source


def test_portfolio_workflows_delegate_plan_transformations() -> None:
    """Plan reconciliation and catalog conversion have no workflow dependency."""
    source = Path("open_data_products/_portfolio_workflows.py").read_text(
        encoding="utf-8"
    )

    assert "from ._portfolio_plan import" in source
    assert "def _reconcile_plan_identity(" not in source
    assert "def _catalog_from_fragments(" not in source


def test_portfolio_rendering_delegates_html_composition() -> None:
    """Workspace loading and HTML composition remain separate concerns."""
    source = Path("open_data_products/_portfolio_rendering.py").read_text(
        encoding="utf-8"
    )

    assert "from ._portfolio_html import" in source
    assert "def render_portfolio_html(" not in source


def test_portfolio_facade_delegates_odps_normalization() -> None:
    """Portfolio rendering relies on the private ODPS normalizer."""
    source = Path("open_data_products/_portfolio_html.py").read_text(encoding="utf-8")
    assert "from ._portfolio_normalization import" in source
    assert "normalize_odps_product as _normalize_odps_product" in source


def test_portfolio_public_workflow_signatures_remain_stable() -> None:
    """The facade preserves the complete workflow-call contract."""
    assert list(inspect.signature(explain_portfolio).parameters) == ["workspace"]
    assert list(inspect.signature(sync_portfolio).parameters) == ["workspace"]
    assert list(inspect.signature(render_portfolio).parameters) == [
        "workspace",
        "output_path",
    ]
    assert list(inspect.signature(refresh_portfolio).parameters) == [
        "workspace",
        "objectives",
        "use_cases",
        "signals",
        "products",
        "title",
        "client",
        "model",
        "all_sources",
        "context_format",
        "source_budget",
        "source_privacy",
    ]
    assert list(inspect.signature(localize_portfolio).parameters) == [
        "workspace",
        "languages",
        "client",
        "model",
        "default_language",
    ]


def test_explain_empty_workspace_is_read_only(tmp_path: Path) -> None:
    """Read-only explanation does not create implicit workspace artifacts."""
    workspace = tmp_path / "empty"
    workspace.mkdir()

    result = explain_portfolio(workspace)

    assert result["kind"] == "PortfolioExplain"
    assert result["businessObjectiveCount"] == 0
    assert result["productSpecCount"] == 0
    assert result["hasExecutiveSummary"] is False
    assert list(workspace.iterdir()) == []


def test_rendering_to_custom_path_does_not_create_default_html(tmp_path: Path) -> None:
    """An explicit render destination stays isolated from the workspace default."""
    workspace = tmp_path / "portfolio"
    output = tmp_path / "published" / "portfolio.html"
    _write_render_workspace(workspace)

    result = render_portfolio(workspace, output_path=output)

    assert result["html"] == str(output)
    assert output.is_file()
    assert not (workspace / "index.html").exists()


def test_custom_render_path_is_idempotent(tmp_path: Path) -> None:
    """A repeated custom render reports the HTML artifact as unchanged."""
    workspace = tmp_path / "portfolio"
    output = tmp_path / "published" / "portfolio.html"
    _write_render_workspace(workspace)

    render_portfolio(workspace, output_path=output)
    result = render_portfolio(workspace, output_path=output)

    assert str(output) in result["unchanged"]
    assert str(output) not in result["created"]
    assert str(output) not in result["updated"]


def test_sync_preserves_unrelated_workspace_files(tmp_path: Path) -> None:
    """Synchronizing managed artifacts leaves user-owned workspace files intact."""
    workspace = tmp_path / "portfolio"
    _write_render_workspace(workspace)
    notes = workspace / "review-notes.md"
    notes.write_text("Keep this reviewer note.", encoding="utf-8")

    sync_portfolio(workspace)

    assert notes.read_text(encoding="utf-8") == "Keep this reviewer note."


def test_intake_is_read_only_for_source_documents(tmp_path: Path) -> None:
    """Inspection neither changes source content nor creates generated artifacts."""
    objectives = tmp_path / "objectives"
    objectives.mkdir()
    source = objectives / "goal.md"
    source.write_text("Improve service reliability.", encoding="utf-8")

    result = inspect_portfolio_intake(objectives=objectives)

    assert result["llmCallCount"] == 0
    assert result["sourceCounts"]["objectives"] == 1
    assert source.read_text(encoding="utf-8") == "Improve service reliability."
    assert sorted(path.name for path in tmp_path.iterdir()) == ["objectives"]


def test_intake_rejects_zero_source_character_budget(tmp_path: Path) -> None:
    """Intake fails before reducing source text with an invalid source budget."""
    objectives = tmp_path / "objectives"
    objectives.mkdir()

    with pytest.raises(ValueError, match="max_source_chars"):
        inspect_portfolio_intake(
            objectives=objectives,
            source_budget=PortfolioSourceBudget(max_source_chars=0),
        )


def test_intake_rejects_zero_prompt_character_budget(tmp_path: Path) -> None:
    """Intake fails before prompting with an invalid prompt budget."""
    objectives = tmp_path / "objectives"
    objectives.mkdir()

    with pytest.raises(ValueError, match="max_prompt_chars"):
        inspect_portfolio_intake(
            objectives=objectives,
            source_budget=PortfolioSourceBudget(max_prompt_chars=0),
        )


def test_localize_rejects_default_language_without_calling_client(
    tmp_path: Path,
) -> None:
    """Localization refuses a no-op request before invoking an LLM client."""
    workspace = tmp_path / "portfolio"
    _write_render_workspace(workspace)
    calls = []

    def client(prompt: str, model: str) -> str:
        calls.append((prompt, model))
        return "translations: {}"

    with pytest.raises(ValueError, match="non-default language"):
        localize_portfolio(
            workspace,
            languages="en",
            client=client,
            model="test-model",
        )

    assert calls == []
    assert not (workspace / "portfolio-i18n.yaml").exists()


def test_localize_deduplicates_case_insensitive_language_tags(tmp_path: Path) -> None:
    """Duplicate language requests result in one localized artifact per language."""
    workspace = tmp_path / "portfolio"
    _write_render_workspace(workspace)
    calls = []

    def client(prompt: str, model: str) -> str:
        calls.append((prompt, model))
        return "translations: {}"

    result = localize_portfolio(
        workspace,
        languages="fi,FI,en",
        client=client,
        model="test-model",
    )

    assert result["languages"] == ["fi"]
    assert (workspace / "index.fi.html").is_file()
    assert calls
    assert all("Target language: fi" in prompt for prompt, _model in calls)


def test_localize_rejects_invalid_bcp47_tag_before_writing_files(
    tmp_path: Path,
) -> None:
    """Invalid localization language tags fail without creating i18n output."""
    workspace = tmp_path / "portfolio"
    _write_render_workspace(workspace)

    with pytest.raises(ValueError, match="Invalid BCP 47 language tag"):
        localize_portfolio(
            workspace,
            languages="not a language",
            client=lambda _prompt, _model: "translations: {}",
            model="test-model",
        )

    assert not (workspace / "portfolio-i18n.yaml").exists()
