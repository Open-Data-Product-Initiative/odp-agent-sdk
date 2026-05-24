"""Bundled resource registry for the Open Data Products SDK."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from .results import Resource

_PACKAGE_ROOT = Path(__file__).resolve().parent

ResourceDefinition = Tuple[str, str, str, str, str]


def _resource(definition: ResourceDefinition) -> Resource:
    resource_id, spec, resource_type, relative_path, description = definition
    return Resource(
        id=resource_id,
        spec=spec,
        type=resource_type,
        path=str(_PACKAGE_ROOT / relative_path),
        description=description,
    )


_RESOURCE_DEFINITIONS: Tuple[ResourceDefinition, ...] = (
    (
        "odps.schema.json",
        "odps",
        "schema",
        "odps/data/schema/odps.json",
        "Bundled ODPS v4.1 data product schema in JSON format.",
    ),
    (
        "odpc.schema.yaml",
        "odpc",
        "schema",
        "odpc/data/schema/odpc.yaml",
        "Bundled ODPC catalog schema in YAML format.",
    ),
    (
        "odpc.schema.json",
        "odpc",
        "schema",
        "odpc/data/schema/odpc.json",
        "Bundled ODPC catalog schema in JSON format.",
    ),
    (
        "odpc.objects",
        "odpc",
        "jsonl",
        "odpc/data/catalog/objects.jsonl",
        "Bundled ODPC object guidance records.",
    ),
    (
        "odpg.schema.yaml",
        "odpg",
        "schema",
        "odpg/data/schema/odpg.yaml",
        "Bundled ODPG graph schema in YAML format.",
    ),
    (
        "odpg.schema.json",
        "odpg",
        "schema",
        "odpg/data/schema/odpg.json",
        "Bundled ODPG graph schema in JSON format.",
    ),
    (
        "odpg.graph",
        "odpg",
        "example",
        "odpg/data/graph/graph.yaml",
        "Bundled ODPG example graph used by graph explorer helpers.",
    ),
    (
        "odpg.objects",
        "odpg",
        "jsonl",
        "odpg/data/graph/objects.jsonl",
        "Bundled ODPG graph object guidance records.",
    ),
    (
        "odpv.vocabulary",
        "odpv",
        "vocabulary",
        "odpv/data/vocab/odpv.yaml",
        "Bundled canonical ODPV vocabulary YAML.",
    ),
    (
        "odpv.terms",
        "odpv",
        "jsonl",
        "odpv/data/vocab/terms.jsonl",
        "Bundled ODPV term records for retrieval and search.",
    ),
    (
        "generation.prompt.system",
        "generation",
        "prompt",
        "generation/data/prompts/system.md",
        "System prompt for local LLM generation of ODP standards artifacts.",
    ),
    (
        "generation.prompt.odps_data_product_fragment",
        "generation",
        "prompt",
        "generation/data/prompts/odps_data_product_fragment.md",
        "Prompt for generating ODPS data product fragments from source docs.",
    ),
    (
        "generation.prompt.odpc_use_case_fragment",
        "generation",
        "prompt",
        "generation/data/prompts/odpc_use_case_fragment.md",
        "Prompt for generating ODPC use case fragments from source docs.",
    ),
    (
        "generation.prompt.odpc_objective_fragment",
        "generation",
        "prompt",
        "generation/data/prompts/odpc_objective_fragment.md",
        "Prompt for generating ODPC objective fragments from source docs.",
    ),
    (
        "generation.prompt.odpc_signal_fragment",
        "generation",
        "prompt",
        "generation/data/prompts/odpc_signal_fragment.md",
        "Prompt for generating ODPC signal fragments from source docs.",
    ),
    (
        "generation.prompt.odpg_graph_yaml",
        "generation",
        "prompt",
        "generation/data/prompts/odpg_graph_yaml.md",
        "Prompt for generating ODPG graph YAML from generated fragments.",
    ),
)

_RESOURCES = [_resource(definition) for definition in _RESOURCE_DEFINITIONS]


def list_resources() -> List[Resource]:
    """List bundled SDK resources for tools and AI agents."""
    return list(_RESOURCES)


def get_resource(resource_id: str) -> Resource:
    """Return a bundled SDK resource by id."""
    for resource in _RESOURCES:
        if resource.id == resource_id:
            return resource
    raise KeyError(f"Unknown Open Data Products resource: {resource_id}")
