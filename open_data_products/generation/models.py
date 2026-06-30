"""Generation data models and task registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Union

PathLike = Union[str, Path]
ModelClient = Callable[[str, str], str]


@dataclass(frozen=True)
class PortfolioSourceBudget:
    """Portfolio document intake source reduction budget."""

    max_source_chars: int = 2000
    max_prompt_chars: int = 32000


@dataclass(frozen=True)
class PortfolioPrivacySettings:
    """Portfolio document intake privacy settings."""

    obfuscate_personal_data: bool = True


@dataclass(frozen=True)
class GenerationTask:
    """Prompt and output mapping for one local generation artifact."""

    name: str
    prompt_name: str
    output_name: str
    expected_root: str
    fragment_root: Optional[str] = None
    filename_prefix: Optional[str] = None
    graph_node_type: Optional[str] = None


@dataclass(frozen=True)
class GenerationSettings:
    """Resolved LLM generation provider and path settings."""

    provider: str
    model: str
    input_path: str
    output_path: str
    provider_type: str = "ollama"
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    api_version: Optional[str] = None
    max_tokens: Optional[int] = None
    model_path: Optional[str] = None
    context_window: Optional[int] = None
    gpu_layers: Optional[int] = None
    prompt_path: Optional[str] = None
    portfolio_source_budget: PortfolioSourceBudget = field(
        default_factory=PortfolioSourceBudget
    )
    portfolio_privacy: PortfolioPrivacySettings = field(
        default_factory=PortfolioPrivacySettings
    )


@dataclass(frozen=True)
class GeneratedArtifact:
    """Generated YAML artifact metadata."""

    name: str
    prompt_name: str
    output_path: Path
    valid_yaml: bool
    errors: List[str] = field(default_factory=list)
    review_notes: List[str] = field(default_factory=list)
    drafted_components: List[str] = field(default_factory=list)
    evidence_gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-ready artifact summary."""
        return {
            "name": self.name,
            "prompt": self.prompt_name,
            "output": str(self.output_path),
            "valid_yaml": self.valid_yaml,
            "errors": list(self.errors),
            "review_notes": list(self.review_notes),
            "drafted_components": list(self.drafted_components),
            "evidence_gaps": list(self.evidence_gaps),
        }


GENERATION_TASKS: Sequence[GenerationTask] = (
    GenerationTask(
        name="odpc_product_references",
        prompt_name="odps_data_product_fragment.md",
        output_name="odpc_product_references.yaml",
        expected_root="productReferences",
        fragment_root="productReference",
        filename_prefix="product_reference",
        graph_node_type="DataProduct",
    ),
    GenerationTask(
        name="odps_products",
        prompt_name="odps_product_minimal_yaml.md",
        output_name="odps_product.yaml",
        expected_root="product",
        filename_prefix="odps_product",
        graph_node_type="DataProduct",
    ),
    GenerationTask(
        name="odpc_use_cases",
        prompt_name="odpc_use_case_fragment.md",
        output_name="odpc_use_cases.yaml",
        expected_root="useCases",
        fragment_root="useCase",
        filename_prefix="use_case",
        graph_node_type="UseCase",
    ),
    GenerationTask(
        name="odpc_objectives",
        prompt_name="odpc_objective_fragment.md",
        output_name="odpc_objectives.yaml",
        expected_root="businessObjectives",
        fragment_root="businessObjective",
        filename_prefix="business_objective",
        graph_node_type="BusinessObjective",
    ),
    GenerationTask(
        name="odpc_signals",
        prompt_name="odpc_signal_fragment.md",
        output_name="odpc_signals.yaml",
        expected_root="signals",
        fragment_root="signal",
        filename_prefix="signal",
        graph_node_type="Signal",
    ),
    GenerationTask(
        name="odpg_graph",
        prompt_name="odpg_graph_yaml.md",
        output_name="odpg_graph.yaml",
        expected_root="graph",
    ),
)

HOLISTIC_GENERATION_TASKS: Sequence[GenerationTask] = tuple(
    task for task in GENERATION_TASKS if task.name != "odps_products"
)

GENERATION_TASK_ALIASES = {
    "product-reference": "odpc_product_references",
    "product-references": "odpc_product_references",
    "odpc-product-reference": "odpc_product_references",
    "odpc-product-references": "odpc_product_references",
    "odps-product": "odps_products",
    "odps-products": "odps_products",
    "use-case": "odpc_use_cases",
    "usecase": "odpc_use_cases",
    "use-cases": "odpc_use_cases",
    "objective": "odpc_objectives",
    "objectives": "odpc_objectives",
    "business-objective": "odpc_objectives",
    "signal": "odpc_signals",
    "signals": "odpc_signals",
    "graph": "odpg_graph",
    "odpg": "odpg_graph",
}
