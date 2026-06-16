"""Conformance harness: SDK alignment with agenticpatterns.veso.ai prescriptions.

Each class targets one pattern from the catalog. These tests are the spec —
implementation is judged by their pass/fail status, not by code reading.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- Instruction Files ------------------------------------------------------
# https://agenticpatterns.veso.ai/instruction-files


class TestInstructionFiles:
    def test_agents_md_exists(self):
        assert (REPO_ROOT / "AGENTS.md").exists(), "Missing AGENTS.md at repo root"

    def test_agents_md_under_200_lines(self):
        lines = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 200, f"AGENTS.md is {len(lines)} lines; max 200"

    def test_agents_md_has_required_sections(self):
        content = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
        for section in (
            "stack",
            "style",
            "testing",
            "git",
            "security",
            "structure",
            "pre-commit",
        ):
            assert section in content, f"AGENTS.md missing section: {section}"


# --- Skills & Reusable Workflows --------------------------------------------
# https://agenticpatterns.veso.ai/skills

REQUIRED_SKILLS = ("odp-validate", "odp-author", "odp-explore-graph")


class TestSkills:
    @pytest.mark.parametrize("skill", REQUIRED_SKILLS)
    def test_skill_bundle_exists(self, skill):
        assert (REPO_ROOT / "skills" / skill / "SKILL.md").exists()

    @pytest.mark.parametrize("skill", REQUIRED_SKILLS)
    def test_skill_frontmatter_is_valid(self, skill):
        text = (REPO_ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{skill}: SKILL.md missing YAML frontmatter"
        _, fm, body = text.split("---\n", 2)
        meta = yaml.safe_load(fm)
        assert meta["name"] == skill, f"{skill}: name field must match directory"
        assert meta.get("description"), f"{skill}: description is required"
        assert body.strip(), f"{skill}: SKILL.md body is empty"


# --- Tool Protocols (MCP) ---------------------------------------------------
# https://agenticpatterns.veso.ai/tool-protocols

EXPECTED_TOOLS = {
    "validate_document",
    "explain_document",
    "resolve_references",
    "list_resources",
    "get_resource",
    "get_config",
    "validate_config",
    "load_summary",
    "catalog_artifacts",
    "search_terms",
    "resolve_vocabulary_term",
    "explain_vocabulary_term",
    "check_vocabulary_relationship",
    "vocabulary_term_context",
    "search_objects",
    "search_graph_objects",
    "summarize_graph",
    "traverse_graph",
    "analyze_graph",
    "agent_context",
    "resolve_product_contracts",
    "validate_product_contracts",
    "check_product_contract_alignment",
    "generate_product_contract_report",
    "summarize_product_contract_risks",
    "validate_data_contract",
    "summarize_data_contract",
    "extract_data_contract_schema",
}


class TestMCPToolDefinitions:
    def test_tools_module_importable(self):
        from open_data_products.mcp import tools  # noqa: F401

    def test_tool_count_meets_minimum(self):
        from open_data_products.mcp.tools import TOOLS

        assert len(TOOLS) >= len(EXPECTED_TOOLS)

    def test_each_tool_self_describes(self):
        from open_data_products.mcp.tools import TOOLS

        for tool in TOOLS:
            assert tool["name"], "tool missing name"
            assert tool["description"], f"{tool['name']}: missing description"
            schema = tool["inputSchema"]
            assert schema["type"] == "object", f"{tool['name']}: inputSchema not object"
            assert (
                "properties" in schema
            ), f"{tool['name']}: inputSchema missing properties"
            assert callable(tool["handler"]), f"{tool['name']}: handler not callable"

    def test_expected_tools_present(self):
        from open_data_products.mcp.tools import TOOLS

        names = {t["name"] for t in TOOLS}
        missing = EXPECTED_TOOLS - names
        assert not missing, f"Missing tools: {missing}"

    def test_handler_returns_mcp_content_envelope(self):
        from open_data_products.mcp.tools import TOOLS

        list_resources = next(t for t in TOOLS if t["name"] == "list_resources")
        result = list_resources["handler"]({})
        assert isinstance(result, dict)
        assert isinstance(result.get("content"), list)
        assert result["content"][0]["type"] == "text"
        assert isinstance(result["content"][0]["text"], str)

    def test_validate_document_tool_works_end_to_end(self, tmp_path):
        from open_data_products.mcp.tools import TOOLS

        path = tmp_path / "p.yaml"
        path.write_text(
            "schema: https://opendataproducts.org/v4.1/schema/odps.json\n"
            "version: '4.1'\n"
            "product:\n"
            "  details:\n"
            "    en:\n"
            "      name: X\n"
            "      productID: x\n"
            "      visibility: public\n"
            "      status: production\n"
            "      type: dataset\n",
            encoding="utf-8",
        )

        tool = next(t for t in TOOLS if t["name"] == "validate_document")
        result = tool["handler"]({"path": str(path)})
        payload = json.loads(result["content"][0]["text"])
        assert payload["valid"] is True
        assert payload["spec"] == "odps"

    @pytest.mark.parametrize(
        ("tool_name", "query"),
        [
            ("search_terms", "data product"),
            ("search_objects", "business objective"),
            ("search_graph_objects", "data product"),
        ],
    )
    def test_search_tools_work_end_to_end(self, tool_name, query):
        from open_data_products.mcp.tools import TOOLS

        tool = next(t for t in TOOLS if t["name"] == tool_name)
        result = tool["handler"]({"query": query, "limit": 1})
        payload = json.loads(result["content"][0]["text"])

        assert isinstance(payload, list)
        assert len(payload) == 1

    def test_search_tool_null_limit_uses_default(self):
        from open_data_products.mcp.tools import TOOLS

        tool = next(t for t in TOOLS if t["name"] == "search_objects")
        result = tool["handler"]({"query": "catalog data", "limit": None})
        payload = json.loads(result["content"][0]["text"])

        assert isinstance(payload, list)
        assert payload


class TestCodexProjectConfig:
    def test_codex_mcp_config_points_to_sdk_server(self):
        path = REPO_ROOT / ".codex" / "config.toml"

        config = tomllib.loads(path.read_text(encoding="utf-8"))
        server = config["mcp_servers"]["open_data_products"]

        assert server["command"] == "open-data-products"
        assert server["args"] == ["serve"]
        assert server["enabled"] is True
        assert server["startup_timeout_sec"] == 10
        assert server["tool_timeout_sec"] == 60
        assert "/" not in server["command"]


class TestClaudeCodeProjectConfig:
    def test_claude_code_mcp_config_points_to_sdk_server(self):
        path = REPO_ROOT / ".mcp.json"

        config = json.loads(path.read_text(encoding="utf-8"))
        server = config["mcpServers"]["open_data_products"]

        assert server["command"] == "open-data-products"
        assert server["args"] == ["serve"]
        assert "/" not in server["command"]


class TestLlmsText:
    def test_llms_txt_exists_and_routes_agents_to_sdk_surfaces(self):
        path = REPO_ROOT / "llms.txt"

        content = path.read_text(encoding="utf-8")

        for expected in (
            "open-data-products serve",
            "open-data-products manifest --json",
            ".codex/config.toml",
            ".mcp.json",
            "validate_document",
            "traverse_graph",
            "load_summary",
            "AGENTS.md",
        ):
            assert expected in content


# --- Agent-Readable Web (ARWS) ----------------------------------------------
# https://agenticpatterns.veso.ai/arws

VALID_TOOL_CLASSES = {"safe", "state-changing", "destructive"}


class TestAgentManifest:
    def test_manifest_function_exists(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        manifest = generate_agent_manifest()
        for required in (
            "name",
            "description",
            "interfaces",
            "standards",
            "capabilities",
            "workflows",
            "resources",
            "safety",
            "tools",
        ):
            assert required in manifest

    def test_manifest_tools_match_mcp_tools(self):
        from open_data_products.mcp.manifest import generate_agent_manifest
        from open_data_products.mcp.tools import TOOLS

        manifest_names = {t["name"] for t in generate_agent_manifest()["tools"]}
        sdk_names = {t["name"] for t in TOOLS}
        assert manifest_names == sdk_names

    def test_manifest_tools_carry_arws_classification(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        for tool in generate_agent_manifest()["tools"]:
            assert (
                tool["class"] in VALID_TOOL_CLASSES
            ), f"{tool['name']}: class must be one of {VALID_TOOL_CLASSES}"

    def test_manifest_includes_inputschema_per_tool(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        for tool in generate_agent_manifest()["tools"]:
            assert tool["inputSchema"]["type"] == "object"

    def test_manifest_describes_sdk_capabilities(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        manifest = generate_agent_manifest()
        capability_ids = {item["id"] for item in manifest["capabilities"]}

        assert capability_ids >= {
            "document-validation",
            "artifact-generation",
            "fragment-workflows",
            "llm-runtime-support",
            "portfolio-workspaces",
            "catalog-and-graph-builds",
            "compact-context-sidecars",
            "vocabulary-context",
            "product-contracts",
        }
        assert {item["id"] for item in manifest["standards"]} == {
            "odps",
            "odpc",
            "odpg",
            "odpv",
        }

    def test_manifest_describes_workflows_and_interfaces(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        manifest = generate_agent_manifest()
        workflow_ids = {item["id"] for item in manifest["workflows"]}

        assert workflow_ids >= {
            "validate-artifact",
            "configure-generation",
            "discover-resources",
            "generate-odpc-fragments",
            "generate-odps-product",
            "build-portfolio",
            "localize-portfolio",
            "build-odpc-catalog",
            "build-odpg-graph",
            "inspect-odpg-graph",
            "convert-odpg-graph",
            "explore-vocabulary",
            "inspect-product-contracts",
        }
        assert manifest["interfaces"]["cli"]["command"] == "open-data-products"
        assert manifest["interfaces"]["mcp"]["command"] == "open-data-products serve"
        assert manifest["interfaces"]["manifest"]["command"] == (
            "open-data-products manifest --json"
        )

    def test_manifest_describes_full_portfolio_lifecycle(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        manifest = generate_agent_manifest()
        portfolio = next(
            item
            for item in manifest["capabilities"]
            if item["id"] == "portfolio-workspaces"
        )
        workflow_ids = {item["id"] for item in manifest["workflows"]}

        assert portfolio["lifecycle"] == [
            "build",
            "refresh",
            "sync",
            "localize",
            "render",
            "explain",
        ]
        assert workflow_ids >= {
            "build-portfolio",
            "refresh-portfolio",
            "sync-portfolio",
            "localize-portfolio",
            "render-portfolio",
            "explain-portfolio",
        }

    def test_manifest_describes_fragment_generation_and_assembly(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        manifest = generate_agent_manifest()
        fragment_capability = next(
            item
            for item in manifest["capabilities"]
            if item["id"] == "fragment-workflows"
        )
        workflows = {item["id"]: item for item in manifest["workflows"]}

        assert fragment_capability["fragment_kinds"] == [
            "product-reference",
            "use-case",
            "objective",
            "signal",
            "graph",
        ]
        assert workflows["generate-odpc-fragments"]["commands"] == [
            "open-data-products generate --input source_docs/ --kind product-reference --output fragments/",
            "open-data-products generate --input use-case.md --kind use-case --output fragments/",
            "open-data-products generate --input objective.md --kind objective --output fragments/",
            "open-data-products generate --input signal.md --kind signal --output fragments/",
            "open-data-products generate --input fragments/ --kind graph --output fragments/",
        ]
        assert workflows["build-odpc-catalog"]["commands"][0].startswith(
            "open-data-products odpc-build fragments/"
        )
        assert workflows["build-odpg-graph"]["commands"][0].startswith(
            "open-data-products odpg-build fragments/"
        )

    def test_manifest_describes_toon_and_gcf_sidecars(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        manifest = generate_agent_manifest()
        compact_context = next(
            item
            for item in manifest["capabilities"]
            if item["id"] == "compact-context-sidecars"
        )
        workflows = {item["id"]: item for item in manifest["workflows"]}

        assert compact_context["formats"] == ["toon", "gcf"]
        assert compact_context["sidecar_outputs"] == [
            "catalog.toon",
            "catalog.gcf",
            "graph.toon",
            "graph.gcf",
        ]
        assert workflows["build-odpc-catalog"]["context_formats"] == ["toon", "gcf"]
        assert workflows["build-odpc-catalog"]["sidecar_outputs"] == [
            "catalog.toon",
            "catalog.gcf",
        ]
        assert workflows["build-odpg-graph"]["context_formats"] == ["toon", "gcf"]
        assert workflows["build-odpg-graph"]["sidecar_outputs"] == [
            "graph.toon",
            "graph.gcf",
        ]

    def test_manifest_describes_local_and_hosted_llm_runtime_support(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        manifest = generate_agent_manifest()
        llm_runtime = next(
            item
            for item in manifest["capabilities"]
            if item["id"] == "llm-runtime-support"
        )
        workflows = {item["id"]: item for item in manifest["workflows"]}

        assert llm_runtime["local_providers"] == [
            "ollama",
            "lmstudio",
            "vllm",
            "nvidia-nim",
            "llamacpp-embedded",
        ]
        assert llm_runtime["hosted_providers"] == [
            "openai",
            "openrouter",
            "groq",
            "together",
            "cerebras",
            "claude",
        ]
        assert llm_runtime["provider_types"] == [
            "ollama",
            "openai",
            "openai-chat",
            "anthropic",
            "llama-cpp",
        ]
        assert "configure-generation" in workflows
        assert "generate-odpc-fragments" in workflows
        assert "generate-odps-product" in workflows
        assert workflows["configure-generation"]["provider_modes"] == [
            "local",
            "hosted",
        ]

    def test_manifest_describes_product_contract_lifecycle(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        manifest = generate_agent_manifest()
        product_contracts = next(
            item
            for item in manifest["capabilities"]
            if item["id"] == "product-contracts"
        )

        assert product_contracts["lifecycle"] == [
            "resolve-contracts",
            "contract-report",
            "audit",
            "check-contract",
            "align-contract",
            "contract-schema",
            "export-contract",
        ]

    def test_manifest_workflow_tool_references_exist(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        manifest = generate_agent_manifest()
        tool_names = {tool["name"] for tool in manifest["tools"]}

        for workflow in manifest["workflows"]:
            missing = set(workflow["mcp_tools"]) - tool_names
            assert not missing, f"{workflow['id']} references unknown tools: {missing}"

    def test_manifest_resources_are_logical_not_filesystem_paths(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        resources = generate_agent_manifest()["resources"]

        assert {resource["id"] for resource in resources} >= {
            "odps.schema.json",
            "odpv.terms",
            "generation.prompt.system",
        }
        for resource in resources:
            assert set(resource) == {"id", "spec", "type", "description"}
            assert "/" not in resource["id"]

    def test_manifest_safety_distinguishes_mcp_and_cli_surfaces(self):
        from open_data_products.mcp.manifest import generate_agent_manifest

        safety = generate_agent_manifest()["safety"]

        assert safety["mcp_tool_class"] == "safe"
        assert safety["mcp_is_read_only"] is True
        assert "state-changing" in safety["cli_note"]


# --- ARWS: enum semantic verbosity ------------------------------------------


class TestEnumSemanticVerbosity:
    def test_product_status_descriptions(self):
        from open_data_products.odps.enums import ProductStatus

        for member in ProductStatus:
            assert member.description, f"{member.name}: missing description"
            assert len(member.description) > 10

    def test_product_visibility_descriptions(self):
        from open_data_products.odps.enums import ProductVisibility

        for member in ProductVisibility:
            assert member.description

    def test_describe_helper_emits_full_taxonomy(self):
        from open_data_products.odps.enums import ProductStatus

        rendered = ProductStatus.describe()
        for member in ProductStatus:
            assert member.value in rendered


# --- Context Management: artifact references --------------------------------
# https://agenticpatterns.veso.ai/context-management


class TestLoadSummary:
    def test_load_summary_returns_lightweight_metadata(self, tmp_path):
        from open_data_products import load_summary

        path = tmp_path / "p.yaml"
        path.write_text(
            "schema: https://opendataproducts.org/v4.1/schema/odps.yaml\n"
            "version: '4.1'\nproduct:\n  productID: x\n",
            encoding="utf-8",
        )
        summary = load_summary(path)
        for key in ("path", "byte_size", "line_count", "sha256", "spec"):
            assert key in summary, f"summary missing key: {key}"
        assert summary["byte_size"] > 0
        assert summary["spec"] in {"odps", "odpc", "odpg", "odpv", "unknown"}
        assert len(summary["sha256"]) == 64

    def test_load_summary_does_not_return_document_body(self, tmp_path):
        from open_data_products import load_summary

        path = tmp_path / "p.yaml"
        path.write_text("schema: odpg\nkind: Graph\n", encoding="utf-8")
        path.with_suffix(".gcf").write_text("gcf body", encoding="utf-8")
        summary = load_summary(path)
        assert "document" not in summary
        assert "body" not in summary
        assert "content" not in json.dumps(summary)

    def test_load_summary_counts_empty_file_as_zero_lines(self, tmp_path):
        from open_data_products import load_summary

        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")

        assert load_summary(path)["line_count"] == 0

    def test_load_summary_references_compact_context_sidecars(self, tmp_path):
        from open_data_products import load_summary

        path = tmp_path / "graph.yaml"
        path.write_text("schema: odpg\nkind: Graph\n", encoding="utf-8")
        gcf = path.with_suffix(".gcf")
        toon = path.with_suffix(".toon")
        gcf.write_text("gcf body", encoding="utf-8")
        toon.write_text("toon body\nline two", encoding="utf-8")

        summary = load_summary(path)

        assert summary["context_artifacts"] == [
            {
                "format": "gcf",
                "path": str(gcf),
                "byte_size": 8,
                "line_count": 1,
                "sha256": hashlib.sha256(b"gcf body").hexdigest(),
                "preferred": True,
            },
            {
                "format": "toon",
                "path": str(toon),
                "byte_size": 18,
                "line_count": 2,
                "sha256": hashlib.sha256(b"toon body\nline two").hexdigest(),
                "preferred": False,
            },
        ]


# --- Agent Payments (HTTP 402) ----------------------------------------------
# https://agenticpatterns.veso.ai/agent-payments


class TestPricing402:
    def test_helper_exists(self):
        from open_data_products.pricing import pricing_to_402

        assert callable(pricing_to_402)

    def test_emits_402_status_and_payment_headers(self):
        from open_data_products.odps import OpenDataProduct
        from open_data_products.odps.models import (
            PricingPlan,
            PricingPlans,
            ProductDetails,
        )
        from open_data_products.pricing import pricing_to_402

        product = OpenDataProduct(
            ProductDetails(
                name="Premium Feed",
                product_id="pp-1",
                visibility="public",
                status="production",
                type="dataset",
            )
        )
        product.pricing_plans = PricingPlans(
            plans=[
                PricingPlan(
                    name={"en": "Starter"},
                    price_currency="USD",
                    price=5.00,
                    billing_duration="month",
                )
            ]
        )
        response = pricing_to_402(product)
        assert response["status"] == 402
        headers = response["headers"]
        assert "X-Payment-Required" in headers
        body = json.loads(headers["X-Payment-Required"])
        assert body["price"] == 5.00
        assert body["currency"] == "USD"

    def test_returns_none_when_no_pricing(self):
        from open_data_products.odps import OpenDataProduct
        from open_data_products.odps.models import ProductDetails
        from open_data_products.pricing import pricing_to_402

        product = OpenDataProduct(
            ProductDetails(
                name="Free",
                product_id="free",
                visibility="public",
                status="production",
                type="dataset",
            )
        )
        assert pricing_to_402(product) is None


# --- CLI consolidation: manifest subcommand ---------------------------------


class TestCLIManifest:
    def test_manifest_subcommand(self, capsys):
        from open_data_products.cli import main

        rc = main(["manifest", "--json"])
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["name"]
        assert payload["tools"]
        assert rc == 0
