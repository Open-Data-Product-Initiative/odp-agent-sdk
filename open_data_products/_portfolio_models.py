"""Internal typed models for Portfolio workflows."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Mapping, Optional, Tuple, Union

from . import __version__
from .generation.models import PortfolioPrivacySettings, PortfolioSourceBudget

PortfolioBuildClient = Callable[[str, str], str]
PortfolioLocalizationClient = Callable[[str, str], str]


@dataclass(frozen=True)
class PortfolioSourceLanes:
    """Source lane paths for portfolio generation."""

    objectives: Optional[Union[str, Path]] = None
    use_cases: Optional[Union[str, Path]] = None
    signals: Optional[Union[str, Path]] = None
    products: Optional[Union[str, Path]] = None

    @classmethod
    def from_mapping(
        cls, lanes: Mapping[str, Union[str, Path, None]]
    ) -> "PortfolioSourceLanes":
        """Create source lanes from canonical IDs or accepted aliases."""
        values: Dict[str, Optional[Union[str, Path]]] = {
            "objectives": None,
            "use_cases": None,
            "signals": None,
            "products": None,
        }
        aliases = {
            "objectives": "objectives",
            "objective": "objectives",
            "use_cases": "use_cases",
            "use-cases": "use_cases",
            "useCases": "use_cases",
            "usecases": "use_cases",
            "signals": "signals",
            "signal": "signals",
            "products": "products",
            "product": "products",
        }
        for key, value in lanes.items():
            canonical = aliases.get(str(key))
            if canonical is None:
                raise ValueError(f"Unsupported portfolio source lane: {key}")
            values[canonical] = value
        return cls(**values)

    def to_build_kwargs(self) -> Dict[str, Optional[Path]]:
        """Return paths using the existing build_portfolio keyword names."""
        return {
            "objectives": (
                Path(self.objectives) if self.objectives is not None else None
            ),
            "use_cases": Path(self.use_cases) if self.use_cases is not None else None,
            "signals": Path(self.signals) if self.signals is not None else None,
            "products": Path(self.products) if self.products is not None else None,
        }


@dataclass(frozen=True)
class PortfolioBuildRequest:
    """Application-grade portfolio build request."""

    workspace: Union[str, Path]
    source_lanes: Union[PortfolioSourceLanes, Mapping[str, Union[str, Path, None]]] = (
        field(default_factory=PortfolioSourceLanes)
    )
    title: Optional[str] = None
    description: Optional[str] = None
    languages: Tuple[str, ...] = ()
    client: Optional[PortfolioBuildClient] = None
    model: str = "qwen2.5"
    run_kind: str = "PortfolioBuild"
    process_all_sources: bool = True
    context_format: str = "markdown"
    source_budget: Optional[PortfolioSourceBudget] = None
    privacy: Optional[PortfolioPrivacySettings] = None
    progress: Optional[Callable[[Mapping[str, object]], None]] = None
    processing_mode: str = "lane-by-lane"

    def normalized_source_lanes(self) -> PortfolioSourceLanes:
        """Return source lanes as a typed lane model."""
        if isinstance(self.source_lanes, PortfolioSourceLanes):
            return self.source_lanes
        return PortfolioSourceLanes.from_mapping(self.source_lanes)


@dataclass(frozen=True)
class PortfolioBuildResult(MappingABC):
    """Typed portfolio build result with mapping compatibility."""

    valid: bool
    workspace: str
    artifacts: Dict[str, object]
    warnings: List[str]
    recoveries: List[Dict[str, object]]
    phases: List[str]
    source_budget: Dict[str, object]
    source_privacy: Dict[str, object]
    render: Dict[str, object]
    localization: Dict[str, object]
    sdk_version: str
    model: Optional[str]
    provider: Optional[str]
    _payload: Dict[str, object] = field(default_factory=dict, repr=False)

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, object],
        *,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> "PortfolioBuildResult":
        """Create a typed result from the legacy mapping payload."""
        data = dict(payload)
        artifacts = {
            "created": list(data.get("created", [])),
            "updated": list(data.get("updated", [])),
            "unchanged": list(data.get("unchanged", [])),
            "removed": list(data.get("removed", [])),
            "counts": dict(data.get("artifactCounts", {})),
        }
        render = {
            "html": data.get("html"),
            "validation_results": data.get("validationResults", {}),
        }
        return cls(
            valid=bool(data.get("valid")),
            workspace=str(data.get("workspace", "")),
            artifacts=artifacts,
            warnings=[str(item) for item in data.get("warnings", [])],
            recoveries=[],
            phases=[str(item) for item in data.get("llmPhases", [])],
            source_budget=dict(data.get("sourceBudget", {})),
            source_privacy=dict(data.get("sourcePrivacy", {})),
            render=render,
            localization={},
            sdk_version=__version__,
            model=model,
            provider=provider,
            _payload=data,
        )

    def __getitem__(self, key: str) -> object:
        return self._payload[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._payload)

    def __len__(self) -> int:
        return len(self._payload)

    def to_dict(self) -> Dict[str, object]:
        """Return the legacy JSON-ready mapping."""
        return dict(self._payload)
