"""Behavior contracts that protect the Portfolio refactor."""

import inspect
from pathlib import Path

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
