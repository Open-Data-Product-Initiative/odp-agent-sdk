"""ARWS-style agent manifest generation.

Renders the SDK's MCP tool registry as the discovery payload an agent host
fetches from ``/.well-known/agent-manifest.json`` per
agenticpatterns.veso.ai/arws.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..resources import list_resources
from .tools import TOOLS


def generate_agent_manifest() -> Dict[str, Any]:
    """Return the ARWS manifest for this SDK."""
    return {
        "name": "open-data-products",
        "description": (
            "Validate, explain, traverse, and search Open Data Products documents "
            "(ODPS, ODPC, ODPG, ODPV)."
        ),
        "version": _package_version(),
        "auth": {"type": "none"},
        "interfaces": _interfaces(),
        "standards": _standards(),
        "capabilities": _capabilities(),
        "workflows": _workflows(),
        "resources": _resources(),
        "safety": _safety(),
        "tools": [_describe(tool) for tool in TOOLS],
    }


def _describe(tool: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": tool["name"],
        "description": tool["description"],
        "class": tool["class"],
        "inputSchema": tool["inputSchema"],
    }


def _interfaces() -> Dict[str, Dict[str, str]]:
    return {
        "cli": {
            "command": "open-data-products",
            "description": "Unified command line interface for SDK workflows.",
        },
        "mcp": {
            "command": "open-data-products serve",
            "description": "Safe stdio MCP server for agent hosts.",
            "transport": "stdio",
        },
        "manifest": {
            "command": "open-data-products manifest --json",
            "description": "Machine-readable capability and MCP tool manifest.",
        },
    }


def _standards() -> List[Dict[str, str]]:
    return [
        {
            "id": "odps",
            "name": "Open Data Product Specification",
            "description": "Data product metadata, ownership, access, SLA, and pricing.",
        },
        {
            "id": "odpc",
            "name": "Open Data Product Catalog",
            "description": "Catalog objects for objectives, use cases, signals, and products.",
        },
        {
            "id": "odpg",
            "name": "Open Data Product Graph",
            "description": "Relationship graph for product portfolio reasoning and traversal.",
        },
        {
            "id": "odpv",
            "name": "Open Data Product Vocabulary",
            "description": "Canonical vocabulary terms and relationship guidance.",
        },
    ]


def _capabilities() -> List[Dict[str, Any]]:
    return [
        {
            "id": "document-validation",
            "title": "Document validation and explanation",
            "standards": ["odps", "odpc", "odpg", "odpv"],
            "interfaces": ["python", "cli", "mcp"],
            "summary": (
                "Detect, validate, explain, summarize, and inspect references "
                "across standards-family YAML and JSON artifacts."
            ),
        },
        {
            "id": "artifact-generation",
            "title": "LLM-assisted artifact generation",
            "standards": ["odps", "odpc", "odpg"],
            "interfaces": ["cli", "python"],
            "summary": (
                "Generate ODPS products, ODPC fragments, and ODPG graphs with "
                "bundled prompts and configurable local or hosted providers."
            ),
        },
        {
            "id": "llm-runtime-support",
            "title": "Local and hosted LLM runtime support",
            "standards": ["odps", "odpc", "odpg"],
            "interfaces": ["cli", "python"],
            "local_providers": [
                "ollama",
                "lmstudio",
                "vllm",
                "nvidia-nim",
                "llamacpp-embedded",
            ],
            "hosted_providers": [
                "openai",
                "openrouter",
                "groq",
                "together",
                "cerebras",
                "sambanova",
                "mistral",
                "gemini",
                "xai",
                "zai",
                "claude",
            ],
            "provider_types": [
                "ollama",
                "openai",
                "openai-chat",
                "anthropic",
                "llama-cpp",
            ],
            "summary": (
                "Run generation, graph inference, portfolio refresh, and "
                "localization through local runtimes or hosted providers selected "
                "by config and CLI overrides."
            ),
        },
        {
            "id": "fragment-workflows",
            "title": "Fragment generation and assembly",
            "standards": ["odpc", "odpg", "odps"],
            "interfaces": ["cli", "python"],
            "fragment_kinds": [
                "product-reference",
                "use-case",
                "objective",
                "signal",
                "graph",
            ],
            "summary": (
                "Generate ODPC product, use case, objective, and signal "
                "fragments, then assemble them into ODPC catalogs, ODPG graphs, "
                "and compact TOON/GCF context artifacts."
            ),
        },
        {
            "id": "portfolio-workspaces",
            "title": "Portfolio workspace workflows",
            "standards": ["odpc", "odpg", "odps"],
            "interfaces": ["cli"],
            "lifecycle": [
                "build",
                "refresh",
                "sync",
                "localize",
                "render",
                "explain",
            ],
            "summary": (
                "Build, refresh, sync, render, localize, and explain static "
                "portfolio workspaces from source lanes and generated artifacts."
            ),
        },
        {
            "id": "catalog-and-graph-builds",
            "title": "Catalog and graph build pipelines",
            "standards": ["odpc", "odpg"],
            "interfaces": ["cli", "python"],
            "context_formats": ["toon", "gcf"],
            "summary": (
                "Build ODPC catalogs, compact context sidecars, ODPG graphs, "
                "graph analyses, and standalone graph explorer HTML."
            ),
        },
        {
            "id": "compact-context-sidecars",
            "title": "Compact context sidecars",
            "standards": ["odpc", "odpg"],
            "interfaces": ["cli"],
            "formats": ["toon", "gcf"],
            "sidecar_outputs": [
                "catalog.toon",
                "catalog.gcf",
                "graph.toon",
                "graph.gcf",
            ],
            "summary": (
                "Generate TOON and GCF sidecars for compact agent-readable "
                "catalog and graph context."
            ),
        },
        {
            "id": "okf-context-bundles",
            "title": "Open Knowledge Format context bundles",
            "standards": ["external-okf", "odpc", "odps", "odpg"],
            "interfaces": ["python", "cli", "mcp"],
            "lifecycle": ["validate", "summarize", "import", "export"],
            "summary": (
                "Validate OKF Markdown/frontmatter bundles, import concepts as "
                "generation source documents, and export ODPC catalog or "
                "portfolio artifacts as OKF context."
            ),
        },
        {
            "id": "vocabulary-context",
            "title": "Vocabulary search and context",
            "standards": ["odpv"],
            "interfaces": ["python", "cli", "mcp"],
            "summary": (
                "Search, resolve, explain, and check canonical ODPV terms and "
                "relationships for authoring and review."
            ),
        },
        {
            "id": "product-contracts",
            "title": "Product and Data Contract alignment",
            "standards": ["odps"],
            "interfaces": ["python", "cli", "mcp"],
            "lifecycle": [
                "resolve-contracts",
                "contract-report",
                "audit",
                "check-contract",
                "align-contract",
                "contract-schema",
                "export-contract",
            ],
            "summary": (
                "Resolve product contract references, validate contracts, inspect "
                "schemas, and report ODPS/Data Contract alignment risks."
            ),
        },
        {
            "id": "bundled-resources",
            "title": "Bundled schemas, prompts, and retrieval indexes",
            "standards": ["odps", "odpc", "odpg", "odpv"],
            "interfaces": ["python", "cli", "mcp"],
            "summary": (
                "Expose logical resource IDs for bundled schemas, vocabularies, "
                "object indexes, examples, and generation prompts."
            ),
        },
    ]


def _workflows() -> List[Dict[str, Any]]:
    return [
        {
            "id": "validate-artifact",
            "title": "Validate and explain one standards artifact",
            "commands": [
                "open-data-products validate product.yaml",
                "open-data-products explain product.yaml",
                "open-data-products summary product.yaml --json",
            ],
            "mcp_tools": ["validate_document", "explain_document", "load_summary"],
        },
        {
            "id": "configure-generation",
            "title": "Inspect and copy generation configuration",
            "provider_modes": ["local", "hosted"],
            "commands": [
                "open-data-products config generation --json",
                "open-data-products config generation --copy-to my-generation.config.yaml",
                "open-data-products config generation --copy-prompts-to prompts/",
                "open-data-products config generation --config my-generation.config.yaml --check --json",
            ],
            "mcp_tools": ["get_config", "validate_config"],
        },
        {
            "id": "discover-resources",
            "title": "Discover bundled schemas, prompts, and retrieval indexes",
            "commands": [
                "open-data-products resources --json",
                "open-data-products resources --id odpc.objects --json",
                "open-data-products resources --id odpv.terms --json",
                "open-data-products resources --id okf.spec --json",
            ],
            "mcp_tools": ["list_resources", "get_resource"],
        },
        {
            "id": "validate-okf-bundle",
            "title": "Validate and summarize an OKF context bundle",
            "commands": [
                "open-data-products okf-validate knowledge-bundle/ --json",
                "open-data-products okf-summary knowledge-bundle/ --json",
            ],
            "mcp_tools": ["validate_okf_bundle", "list_okf_concepts"],
        },
        {
            "id": "import-okf-bundle",
            "title": "Import OKF concepts as generation source documents",
            "commands": [
                "open-data-products okf-import knowledge-bundle/ --output source_docs/"
            ],
            "mcp_tools": ["validate_okf_bundle", "list_okf_concepts"],
        },
        {
            "id": "export-okf-bundle",
            "title": "Export ODPC catalog or portfolio artifacts as OKF",
            "commands": [
                "open-data-products okf-export catalog.yaml --output okf-bundle/",
                "open-data-products okf-export portfolio/ --output okf-bundle/",
            ],
            "mcp_tools": ["validate_document", "load_summary"],
        },
        {
            "id": "generate-odpc-fragments",
            "title": "Generate ODPC fragments from source material",
            "provider_modes": ["local", "hosted"],
            "commands": [
                "open-data-products generate --input source_docs/ --kind product-reference --output fragments/",
                "open-data-products generate --input use-case.md --kind use-case --output fragments/",
                "open-data-products generate --input objective.md --kind objective --output fragments/",
                "open-data-products generate --input signal.md --kind signal --output fragments/",
                "open-data-products generate --input fragments/ --kind graph --output fragments/",
            ],
            "mcp_tools": ["get_config", "validate_config", "search_objects"],
        },
        {
            "id": "generate-odps-product",
            "title": "Generate a full ODPS product draft",
            "provider_modes": ["local", "hosted"],
            "commands": [
                "open-data-products generate --input product.md --kind odps-product --output products/",
                "open-data-products generate --input transcripts/ --kind odps-product --profile complete-draft --include-components SLA,dataQuality,pricingPlans --output products/",
            ],
            "mcp_tools": ["get_config", "validate_config"],
        },
        {
            "id": "build-portfolio",
            "title": "Build a static portfolio workspace",
            "commands": [
                "open-data-products portfolio build --objectives inputs/objectives/ --use-cases inputs/use-cases/ --signals inputs/signals/ --products inputs/products/ --output portfolio/"
            ],
            "mcp_tools": ["search_objects", "search_graph_objects"],
        },
        {
            "id": "refresh-portfolio",
            "title": "Refresh a portfolio workspace from saved source lanes",
            "commands": [
                "open-data-products portfolio refresh portfolio/",
                "open-data-products portfolio refresh portfolio/ --all-sources",
            ],
            "mcp_tools": ["search_objects", "search_graph_objects"],
        },
        {
            "id": "sync-portfolio",
            "title": "Sync edited portfolio YAML without calling an LLM",
            "commands": ["open-data-products portfolio sync portfolio/"],
            "mcp_tools": ["validate_document", "load_summary"],
        },
        {
            "id": "localize-portfolio",
            "title": "Localize rendered portfolio HTML",
            "commands": [
                "open-data-products portfolio localize portfolio/ --languages fi,sv"
            ],
            "mcp_tools": [],
        },
        {
            "id": "render-portfolio",
            "title": "Render one static browser-viewable portfolio page",
            "commands": ["open-data-products portfolio render portfolio/"],
            "mcp_tools": ["load_summary"],
        },
        {
            "id": "explain-portfolio",
            "title": "Summarize portfolio artifacts and browser entry point",
            "commands": ["open-data-products portfolio explain portfolio/"],
            "mcp_tools": ["load_summary"],
        },
        {
            "id": "build-odpc-catalog",
            "title": "Build an ODPC catalog from fragments",
            "context_formats": ["toon", "gcf"],
            "sidecar_outputs": ["catalog.toon", "catalog.gcf"],
            "commands": [
                "open-data-products odpc-build fragments/ --output catalog.yaml --html catalog.html --toon catalog.toon --gcf catalog.gcf",
                "open-data-products odpc-summary catalog.yaml --json",
                "open-data-products odpc-artifacts open_data_products/generation/fragments/ --check",
            ],
            "mcp_tools": ["catalog_artifacts", "search_objects"],
        },
        {
            "id": "build-odpg-graph",
            "title": "Build an ODPG graph from ODPC fragments",
            "context_formats": ["toon", "gcf"],
            "provider_modes": ["local", "hosted"],
            "sidecar_outputs": ["graph.toon", "graph.gcf"],
            "commands": [
                "open-data-products odpg-build fragments/ --output graph.yaml --toon graph.toon --gcf graph.gcf",
                "open-data-products odpg-build fragments/ --context-graph graph.yaml --output graph-updated.yaml",
            ],
            "mcp_tools": ["search_graph_objects", "summarize_graph", "analyze_graph"],
        },
        {
            "id": "inspect-odpg-graph",
            "title": "Inspect, traverse, and analyze an ODPG graph",
            "commands": [
                "open-data-products odpg-summary graph.yaml --json",
                "open-data-products odpg-traverse graph.yaml --start DATA-PRODUCT-001 --depth 2 --json",
                "open-data-products odpg-analyze graph.yaml --json",
                "open-data-products odpg-agent-context graph.yaml --node DATA-PRODUCT-001 --json",
                "open-data-products odpg-generate graph.yaml --output graph-explorer.html",
            ],
            "mcp_tools": [
                "summarize_graph",
                "traverse_graph",
                "analyze_graph",
                "agent_context",
            ],
        },
        {
            "id": "convert-odpg-graph",
            "title": "Convert external graph formats to ODPG YAML",
            "commands": [
                "open-data-products odpg-convert --input graph.graphml --output graph.yaml",
                "open-data-products odpg-convert --input graph.ttl --format rdf --output graph.yaml",
            ],
            "mcp_tools": ["validate_document", "load_summary"],
        },
        {
            "id": "explore-vocabulary",
            "title": "Search and inspect ODPV vocabulary terms",
            "commands": [
                "open-data-products odpv-summary --json",
                'open-data-products odpv-search "governance policy risk" --limit 3 --json',
                'open-data-products odpv-resolve "reusable data asset" --json',
                "open-data-products odpv-explain DataProduct --json",
                "open-data-products odpv-relationship DataProduct supports UseCase --json",
                "open-data-products odpv-context DataProduct --json",
            ],
            "mcp_tools": [
                "search_terms",
                "resolve_vocabulary_term",
                "explain_vocabulary_term",
                "check_vocabulary_relationship",
                "vocabulary_term_context",
            ],
        },
        {
            "id": "inspect-product-contracts",
            "title": "Inspect product and Data Contract alignment",
            "commands": [
                "open-data-products product resolve-contracts product.yaml --json",
                "open-data-products product contract-report product.yaml contract.yaml --json",
                "open-data-products product audit product.yaml --contract contract.yaml --json",
                "open-data-products product check-contract product.yaml contract.yaml --json",
                "open-data-products product align-contract product.yaml contract.yaml --json",
                "open-data-products product contract-schema contract.yaml --json",
                "open-data-products product export-contract contract.yaml --format json --json",
            ],
            "mcp_tools": [
                "resolve_product_contracts",
                "validate_product_contracts",
                "check_product_contract_alignment",
                "generate_product_contract_report",
                "summarize_product_contract_risks",
                "validate_data_contract",
                "summarize_data_contract",
                "extract_data_contract_schema",
            ],
        },
    ]


def _resources() -> List[Dict[str, str]]:
    return [
        {
            "id": resource.id,
            "spec": resource.spec,
            "type": resource.type,
            "description": resource.description,
        }
        for resource in list_resources()
    ]


def _safety() -> Dict[str, Any]:
    return {
        "mcp_tool_class": "safe",
        "mcp_is_read_only": True,
        "mcp_note": (
            "MCP tools expose read-only inspection, validation, search, and "
            "summary behavior."
        ),
        "cli_note": (
            "Some CLI workflows are state-changing because they write generated "
            "artifacts, render HTML, or call configured LLM providers."
        ),
    }


def _package_version() -> str:
    from .. import __version__

    return __version__


__all__ = ["generate_agent_manifest"]
