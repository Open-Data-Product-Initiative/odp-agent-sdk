"""Canonical filesystem layout for a Portfolio workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PortfolioWorkspacePaths:
    """Resolve standard artifact locations beneath one workspace root."""

    root: Path

    @property
    def catalog(self) -> Path:
        """Return the ODPC catalog path."""
        return self.root / "odpc" / "catalog.yaml"

    @property
    def graph(self) -> Path:
        """Return the ODPG graph path."""
        return self.root / "odpg" / "graph.yaml"

    @property
    def portfolio(self) -> Path:
        """Return the portfolio metadata path."""
        return self.root / "portfolio.yaml"

    @property
    def executive_summary(self) -> Path:
        """Return the executive summary path."""
        return self.root / "executive-summary.yaml"
