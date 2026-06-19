"""Functional tests for the unified command line interface."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pytest
import yaml

from open_data_products import __version__
from open_data_products.cli import main

pytestmark = pytest.mark.functional

REPO_ROOT = Path(__file__).resolve().parents[1]
ODPS_PRODUCT = (
    REPO_ROOT / "examples" / "apps" / "pricing_402_builder" / "priced_product.yaml"
)
ODPG_GRAPH = REPO_ROOT / "open_data_products" / "odpg" / "data" / "graph" / "graph.yaml"
GENERATION_SOURCE_DOCS = REPO_ROOT / "open_data_products" / "generation" / "source_docs"
EXAMPLE_RECIPES = REPO_ROOT / "examples" / "recipes"


def _fake_localization_client(prompt: str, model: str) -> str:
    if "Target language: fi" in prompt:
        return """
language: fi
translations:
  Open Data Products Portfolio: Open Data Products Portfolio FI
  Generated workspace summary: Generated workspace summary FI
  Overview: Overview FI
  Products: Products FI
  Customer Product: Customer Product FI
  Full product details from product discussions.: Full product details from product discussions FI.
"""
    return """
language: sv
translations:
  Open Data Products Portfolio: Open Data Products Portfolio SV
  Generated workspace summary: Generated workspace summary SV
  Overview: Overview SV
  Products: Products SV
  Customer Product: Customer Product SV
  Full product details from product discussions.: Full product details from product discussions SV.
"""


def _json_output(capsys: pytest.CaptureFixture[str]) -> Dict[str, Any]:
    import json

    return json.loads(capsys.readouterr().out)


def test_unified_cli_help_uses_compact_command_metavar(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "usage: open-data-products [-h] [-V] COMMAND ..." in help_text
    assert "{validate,explain,refs" not in help_text
    assert "Common workflows:" in help_text
    assert "Validate one artifact:" in help_text
    assert "Generate ODPC fragments from source notes:" in help_text
    assert "Build catalog and graph review artifacts:" in help_text
    assert "Build a portfolio workspace:" in help_text
    assert "Exchange OKF context bundles:" in help_text
    assert "Use --json when scripting" in help_text
    assert "Core document commands:" in help_text
    assert "OKF context bundle commands:" in help_text
    assert "resources --id okf.spec" in help_text
    assert "MCP validate_okf_bundle" in help_text
    assert "MCP list_okf_concepts" in help_text
    assert "ODPC catalog commands:" in help_text
    assert "resources --id odpc.objects" in help_text
    assert "MCP search_objects" in help_text
    assert "ODPV vocabulary commands:" in help_text
    assert "resources --id odpv.terms" in help_text
    assert "MCP search_terms" in help_text
    assert "Discovery and agent commands:" in help_text
    assert "config       Show or copy editable SDK config templates" in help_text
    assert "ODPC catalog commands:" in help_text
    assert "odpc-summary" in help_text
    assert "odpc-search" in help_text
    assert "ODPV vocabulary commands:" in help_text
    assert "odpv-summary" in help_text
    assert "odpv-search" in help_text
    assert "ODPR recipe commands:" in help_text
    assert "resources --id odpr.schema.yaml" in help_text
    assert "ODPG graph commands:" in help_text
    assert "odpg-build" in help_text
    assert "odpg-generate" in help_text
    assert "odpg-convert" in help_text
    assert "Product/Data Contract commands:" in help_text
    assert "LLM generation commands:" in help_text
    assert "generate     Use configured LLM prompts" in help_text
    assert "Examples:" in help_text
    assert "open-data-products validate product.yaml" in help_text
    assert (
        "open-data-products product contract-report product.yaml contract.yaml --json"
        in help_text
    )
    assert "open-data-products resources --id odpc.objects --json" in help_text
    assert "open-data-products resources --id odpv.terms --json" in help_text
    assert "open-data-products resources --id odpr.schema.yaml --json" in help_text
    assert "open-data-products recipe search localization --json" in help_text
    assert "open-data-products okf-summary knowledge-bundle/ --json" in help_text
    assert "open-data-products resources --id okf.spec --json" in help_text
    assert (
        "open-data-products odpg-generate graph.yaml --output graph-explorer.html"
        in help_text
    )
    assert (
        "open-data-products odpg-convert --input graph.graphml --output graph.yaml"
        in help_text
    )
    assert (
        "open-data-products generate --input source_docs/ --kind product-reference --output generated/"
        in help_text
    )
    assert (
        "open-data-products generate --input product.md --kind odps-product --output generated/"
        in help_text
    )
    assert (
        "open-data-products config generation --copy-prompts-to prompts/" in help_text
    )
    assert (
        "open-data-products generate --config my-generation.config.yaml --prompts prompts/ --input source_docs/ --kind graph --output generated/"
        in help_text
    )
    assert "open-data-products odpg-build fragments/ --output graph.yaml" in help_text
    assert "generation.config.yaml --json" not in help_text
    assert "validate" in help_text
    assert "product" in help_text


def test_unified_cli_generate_help_is_provider_neutral(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["generate", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "Generate selected YAML artifacts with configured LLMs" in help_text
    assert "local LLM" not in help_text


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["validate", "--help"], "usage: open-data-products validate"),
        (["generate", "--help"], "usage: open-data-products generate"),
        (["odpc-build", "--help"], "usage: open-data-products odpc-build"),
        (["odpg-build", "--help"], "usage: open-data-products odpg-build"),
        (["portfolio", "--help"], "usage: open-data-products portfolio"),
        (["recipe", "--help"], "usage: open-data-products recipe"),
        (["product", "--help"], "usage: open-data-products product"),
        (["manifest", "--help"], "usage: open-data-products manifest"),
        (["serve", "--help"], "usage: open-data-products serve"),
    ],
)
def test_cli_command_family_help_smoke(
    argv: List[str],
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 0
    assert expected in capsys.readouterr().out


def test_unified_cli_json_errors_are_structured(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from open_data_products import cli_core

    assert cli_core.split_csv("fi, sv,,en") == ["fi", "sv", "en"]
    assert callable(cli_core.print_error_payload)

    assert main(["portfolio", "build", "--json"]) == 1
    payload = _json_output(capsys)
    assert payload["spec"] == "portfolio"
    assert payload["kind"] == "Error"
    assert payload["valid"] is False
    assert "Provide a portfolio workspace" in payload["error"]

    assert main(["resources", "--id", "missing.resource", "--json"]) == 1
    payload = _json_output(capsys)
    assert payload["spec"] == "cli"
    assert payload["kind"] == "Error"
    assert payload["valid"] is False
    assert "missing.resource" in payload["error"]


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_unified_cli_version_flag(
    flag: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([flag])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out == f"open-data-products {__version__}\n"


def test_product_cli_help_uses_compact_command_metavar_and_examples(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from open_data_products import cli_product

    assert callable(cli_product.add_product_subparser)
    assert callable(cli_product.handle_product_command)

    with pytest.raises(SystemExit) as exc_info:
        main(["product", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "usage: open-data-products product [-h] PRODUCT_COMMAND ..." in help_text
    assert "{check-contract,resolve-contracts" not in help_text
    assert "Data Contract workflow commands:" in help_text
    assert "Examples:" in help_text
    assert (
        "open-data-products product resolve-contracts product.yaml --json" in help_text
    )
    assert (
        "open-data-products product audit product.yaml --contract contract.yaml --json"
        in help_text
    )


def test_portfolio_cli_help_uses_human_first_examples(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["portfolio", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "usage: open-data-products portfolio [-h] PORTFOLIO_COMMAND ..." in help_text
    assert "Portfolio workflow commands:" in help_text
    assert (
        "open-data-products portfolio build --objectives inputs/objectives/ --use-cases inputs/use-cases/ --signals inputs/signals/ --products inputs/products/ --output generated/portfolio/"
        in help_text
    )
    assert "open-data-products portfolio refresh generated/portfolio/" in help_text
    assert "open-data-products portfolio sync generated/portfolio/" in help_text
    assert (
        'open-data-products portfolio localize generated/portfolio/ --languages "fi,sv" --provider claude --model claude-sonnet-4-5'
        in help_text
    )
    assert (
        "portfolio build --objectives inputs/objectives/ --use-cases inputs/use-cases/ --signals inputs/signals/ --products inputs/products/ --output generated/portfolio/ --json"
        not in help_text
    )


def test_recipe_cli_validates_and_dry_runs_recipe(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    workspace = tmp_path / "generated" / "portfolio"
    workspace.mkdir(parents=True)
    recipe_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-LOCALIZE-001
    name:
      en: Localize Portfolio
  version: "1.0.0"
  type: localization
  steps:
    - id: localize
      command: portfolio.localize
      providerRef: claude
      model: claude-sonnet-4-5
      with:
        workspace: generated/portfolio/
        languages:
          - fi
          - sv
""",
        encoding="utf-8",
    )

    assert main(["recipe", "validate", str(recipe_path), "--json"]) == 0
    validate_payload = _json_output(capsys)
    assert validate_payload["mode"] == "validate"
    assert validate_payload["valid"] is True
    assert validate_payload["recipe"]["id"] == "RCP-LOCALIZE-001"

    assert (
        main(
            [
                "recipe",
                "run",
                str(recipe_path),
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    plan = _json_output(capsys)
    assert plan["mode"] == "dry-run"
    assert plan["steps"][0]["resolved"]["parameters"]["languages"] == ["fi", "sv"]
    assert plan["steps"][0]["review"]["status"] == "review-needed"
    assert "resolvedCommand" not in plan["steps"][0]


def test_recipe_cli_execute_runs_deterministic_recipe(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        """
schema: https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml
version: "1.0"
kind: Catalog
catalog:
  metadata:
    id: CAT-001
    name:
      en: Customer Data Product Catalog
    description:
      en: Catalog for customer-facing data products.
  productReferences:
    - id: PRODUCT-001
      productID: PRODUCT-001
      productVersion: "1.0"
      name:
        en: Customer Product
      description:
        en: Customer product reference.
      productModel:
        standard: ODPS
        version: "4.0"
        format: yaml
        $ref: ./product.yaml
""",
        encoding="utf-8",
    )
    recipe_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-VALIDATE-001
    name:
      en: Validate Catalog
  version: "1.0.0"
  type: ci
  steps:
    - id: validate-catalog
      command: validate
      with:
        document: catalog.yaml
""",
        encoding="utf-8",
    )

    assert main(["recipe", "run", str(recipe_path), "--execute", "--json"]) == 0
    payload = _json_output(capsys)

    assert payload["mode"] == "execute"
    assert payload["status"] == "passed"
    assert payload["canRun"] is True
    assert payload["steps"][0]["status"] == "passed"
    assert payload["steps"][0]["summary"]["spec"] == "odpc"
    assert (tmp_path / payload["manifest"]["path"]).is_file()


def test_recipe_cli_execute_blocks_llm_backed_recipe(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    workspace = tmp_path / "generated" / "portfolio"
    workspace.mkdir(parents=True)
    recipe_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-LOCALIZE-001
    name:
      en: Localize Portfolio
  version: "1.0.0"
  type: localization
  steps:
    - id: localize
      command: portfolio.localize
      providerRef: claude
      model: claude-sonnet-4-5
      with:
        workspace: generated/portfolio/
        languages:
          - fi
""",
        encoding="utf-8",
    )

    assert main(["recipe", "run", str(recipe_path), "--execute", "--json"]) == 1
    payload = _json_output(capsys)

    assert payload["mode"] == "execute"
    assert payload["status"] == "blocked"
    assert payload["canRun"] is False
    assert payload["steps"][0]["status"] == "blocked"
    assert any(
        reason["code"] == "llm_execution_requires_allow_llm"
        for reason in payload["blockingReasons"]
    )
    assert any(
        reason["code"] == "review_approval_required"
        for reason in payload["blockingReasons"]
    )
    assert payload["executionPolicy"] == {
        "allowLlm": False,
        "reviewApproved": False,
    }
    assert (tmp_path / payload["manifest"]["path"]).is_file()


def test_recipe_cli_execute_requires_review_approval_after_allowing_llm(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    workspace = tmp_path / "generated" / "portfolio"
    workspace.mkdir(parents=True)
    recipe_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-LOCALIZE-001
    name:
      en: Localize Portfolio
  version: "1.0.0"
  type: localization
  steps:
    - id: localize
      command: portfolio.localize
      providerRef: claude
      model: claude-sonnet-4-5
      with:
        workspace: generated/portfolio/
        languages:
          - fi
""",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "recipe",
                "run",
                str(recipe_path),
                "--execute",
                "--allow-llm",
                "--provider-ref",
                "ollama",
                "--model",
                "test-model",
                "--json",
            ]
        )
        == 1
    )
    payload = _json_output(capsys)

    assert payload["status"] == "blocked"
    assert payload["executionPolicy"] == {"allowLlm": True, "reviewApproved": False}
    assert [reason["code"] for reason in payload["blockingReasons"]] == [
        "review_approval_required"
    ]


def test_recipe_cli_execute_localizes_portfolio_after_llm_and_review_approval(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products import generation

    recipe_path = tmp_path / "recipe.yaml"
    workspace = tmp_path / "generated" / "portfolio"
    shutil.copytree(EXAMPLE_RECIPES / "workspace", workspace)
    recipe_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-LOCALIZE-001
    name:
      en: Localize Portfolio
  version: "1.0.0"
  type: localization
  steps:
    - id: localize
      command: portfolio.localize
      providerRef: claude
      model: claude-sonnet-4-5
      with:
        workspace: generated/portfolio/
        languages:
          - fi
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: _fake_localization_client,
    )

    assert (
        main(
            [
                "recipe",
                "run",
                str(recipe_path),
                "--execute",
                "--allow-llm",
                "--approve-review",
                "--provider-ref",
                "ollama",
                "--model",
                "test-model",
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)

    assert payload["status"] == "passed"
    assert payload["canRun"] is True
    assert payload["blockingReasons"] == []
    assert payload["executionPolicy"] == {"allowLlm": True, "reviewApproved": True}
    assert payload["steps"][0]["review"]["decision"] == "approved-by-cli-flag"
    assert payload["steps"][0]["status"] == "passed"
    assert (workspace / "portfolio-i18n.yaml").is_file()
    assert (workspace / "index.fi.html").is_file()


def test_recipe_cli_execute_returns_failure_for_failed_deterministic_step(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    catalog_path = tmp_path / "catalog.yaml"
    recipe_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-VALIDATE-001
    name:
      en: Validate Catalog
  version: "1.0.0"
  type: ci
  steps:
    - id: validate-catalog
      command: validate
      with:
        document: catalog.yaml
""",
        encoding="utf-8",
    )
    catalog_path.write_text(
        """
schema: https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml
version: "1.0"
kind: Catalog
catalog: {}
""",
        encoding="utf-8",
    )

    assert main(["recipe", "run", str(recipe_path), "--execute", "--json"]) == 1
    payload = _json_output(capsys)

    assert payload["mode"] == "execute"
    assert payload["status"] == "failed"
    assert payload["canRun"] is True
    assert payload["steps"][0]["status"] == "failed"
    assert payload["steps"][0]["issues"]
    manifest_path = tmp_path / payload["manifest"]["path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["exitCode"] == 1
    assert manifest["steps"][0]["issues"]


def test_recipe_cli_execute_blocks_state_changing_step_outside_allow_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    config_path = tmp_path / "recipes.config.yaml"
    recipe_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-SYNC-001
    name:
      en: Sync Portfolio
  version: "1.0.0"
  type: ci
  steps:
    - id: sync
      command: portfolio.sync
      with:
        workspace: portfolio/
""",
        encoding="utf-8",
    )
    config_path.write_text(
        """
version: "1.0"
execution:
  manifestDir: .odp/runs/
  allowWrites:
    - generated/
""",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "recipe",
                "run",
                str(recipe_path),
                "--config",
                str(config_path),
                "--execute",
                "--json",
            ]
        )
        == 1
    )
    payload = _json_output(capsys)

    assert payload["status"] == "blocked"
    assert payload["steps"][0]["status"] == "blocked"
    assert any(
        "planned write outside allowWrites" in reason["message"]
        for reason in payload["blockingReasons"]
    )


def test_recipe_cli_dry_run_reports_provider_missing_env(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    config_path = tmp_path / "recipes.config.yaml"
    generation_path = tmp_path / "generation.config.yaml"
    workspace = tmp_path / "generated" / "portfolio"
    workspace.mkdir(parents=True)
    recipe_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-LOCALIZE-001
    name:
      en: Localize Portfolio
  version: "1.0.0"
  type: localization
  steps:
    - id: localize
      command: portfolio.localize
      providerRef: configured-openai
      with:
        workspace: generated/portfolio/
        languages:
          - fi
""",
        encoding="utf-8",
    )
    config_path.write_text(
        """
version: "1.0"
providers:
  generationConfig: generation.config.yaml
""",
        encoding="utf-8",
    )
    generation_path.write_text(
        """
provider: configured-openai
providers:
  configured-openai:
    type: openai
    model: gpt-test
    apiKeyEnv: TEST_ODPR_OPENAI_API_KEY
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("TEST_ODPR_OPENAI_API_KEY", raising=False)

    assert (
        main(
            [
                "recipe",
                "run",
                str(recipe_path),
                "--config",
                str(config_path),
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)

    assert payload["providers"] == [
        {
            "ref": "configured-openai",
            "model": "gpt-test",
            "type": "openai",
            "readiness": "missing-env",
            "missingEnv": ["TEST_ODPR_OPENAI_API_KEY"],
            "source": str(generation_path),
        }
    ]


def test_recipe_cli_uses_config_default_recipe_when_path_is_omitted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = REPO_ROOT / "examples" / "recipes" / "config" / "recipes.config.yaml"

    assert main(["recipe", "validate", "--config", str(config), "--json"]) == 0
    validate_payload = _json_output(capsys)
    assert validate_payload["recipe"]["id"] == "RCP-CI-VALIDATE-001"
    assert validate_payload["recipeSelection"] == {
        "source": "config-default",
        "path": "workflows/ci-validate-catalog.yaml",
        "defaultRecipe": "workflows/ci-validate-catalog.yaml",
    }

    assert main(["recipe", "run", "--config", str(config), "--dry-run", "--json"]) == 0
    run_payload = _json_output(capsys)
    assert run_payload["recipe"]["id"] == "RCP-CI-VALIDATE-001"
    assert run_payload["recipeSelection"]["source"] == "config-default"


def test_recipe_cli_explicit_recipe_argument_wins_over_config_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = REPO_ROOT / "examples" / "recipes" / "config" / "recipes.config.yaml"
    recipe = (
        REPO_ROOT
        / "examples"
        / "recipes"
        / "workflows"
        / "release-portfolio-localize.yaml"
    )

    assert (
        main(
            [
                "recipe",
                "run",
                str(recipe),
                "--config",
                str(config),
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)

    assert payload["recipe"]["id"] == "RCP-PORTFOLIO-LOCALIZE-001"
    assert payload["recipeSelection"] == {
        "source": "argument",
        "path": str(recipe),
        "defaultRecipe": "workflows/ci-validate-catalog.yaml",
    }


def test_recipe_cli_requires_path_without_config_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["recipe", "run", "--dry-run", "--json"]) == 1
    payload = _json_output(capsys)

    assert payload["mode"] == "run"
    assert (
        payload["error"]
        == "recipe path is required unless recipes.defaultRecipe is set in "
        "recipes.config.yaml"
    )


def test_config_recipes_check_reports_recipe_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "recipes.config.yaml"
    config_path.write_text(
        """
version: "1.0"
recipes:
  paths:
    - recipes/
providers:
  defaultProviderRef: claude
execution:
  manifestDir: .odp/runs/
  allowWrites:
    - generated/
""",
        encoding="utf-8",
    )

    assert (
        main(["config", "recipes", "--config", str(config_path), "--check", "--json"])
        == 0
    )
    payload = _json_output(capsys)
    assert payload["domain"] == "recipes"
    assert payload["valid"] is True
    assert payload["errors"] == []


def test_recipe_cli_list_uses_config_relative_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recipes_dir = tmp_path / "recipes"
    recipes_dir.mkdir()
    recipe_path = recipes_dir / "release.yaml"
    recipe_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-RELEASE-001
    name:
      en: Release
  version: "1.0.0"
  type: release
  steps:
    - id: explain
      command: portfolio.explain
      with:
        workspace: generated/portfolio/
""",
        encoding="utf-8",
    )
    config_path = tmp_path / "recipes.config.yaml"
    config_path.write_text(
        """
version: "1.0"
recipes:
  paths:
    - recipes/
""",
        encoding="utf-8",
    )

    assert main(["recipe", "list", "--config", str(config_path), "--json"]) == 0
    payload = _json_output(capsys)
    recipes = payload["recipeCatalog"]["recipes"]
    assert payload["mode"] == "list"
    assert recipes[0]["path"] == "recipes/release.yaml"
    assert recipes[0]["commands"] == ["portfolio.explain"]


def test_recipe_cli_catalog_writes_metadata_only_catalog(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recipes_dir = tmp_path / "recipes"
    recipes_dir.mkdir()
    (recipes_dir / "release.yaml").write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-RELEASE-001
    name:
      en: Release
  version: "1.0.0"
  type: release
  steps:
    - id: explain
      command: portfolio.explain
      with:
        workspace: generated/portfolio/
""",
        encoding="utf-8",
    )
    config_path = tmp_path / "recipes.config.yaml"
    config_path.write_text(
        """
version: "1.0"
recipes:
  paths:
    - recipes/
""",
        encoding="utf-8",
    )
    output = tmp_path / "recipes" / "catalog.yaml"

    assert (
        main(
            [
                "recipe",
                "catalog",
                "--config",
                str(config_path),
                "--output",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)
    catalog = yaml.safe_load(output.read_text(encoding="utf-8"))
    entry = catalog["recipeCatalog"]["recipes"][0]
    assert payload["kind"] == "RecipeCatalog"
    assert payload["output"] == str(output)
    assert entry["path"] == "recipes/release.yaml"
    assert "steps" not in entry
    assert "plannedWrites" not in entry


def test_recipe_cli_validate_accepts_provider_document(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider_path = tmp_path / "provider.yaml"
    provider_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Provider
provider:
  id: production-quality
  provider: openai
  credentialsRef: env:OPENAI_API_KEY
""",
        encoding="utf-8",
    )

    assert main(["recipe", "validate", str(provider_path), "--json"]) == 0
    payload = _json_output(capsys)
    assert payload["kind"] == "Provider"
    assert payload["valid"] is True


def test_recipe_cli_searches_bundled_guidance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["recipe", "search", "metadata", "discovery", "--json"]) == 0
    payload = _json_output(capsys)
    assert payload[0]["id"] == "RecipeCatalog"

    assert main(["recipe", "search", "--id", "Provider", "--json"]) == 0
    provider = _json_output(capsys)
    assert provider["id"] == "Provider"
    assert "provider profile" in provider["definition"]


def test_unified_cli_document_workflow(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(ODPS_PRODUCT), "--json"]) == 0
    validate_payload = _json_output(capsys)
    assert validate_payload["valid"] is True
    assert validate_payload["spec"] == "odps"
    assert validate_payload["version"] == "4.1"

    assert main(["explain", str(ODPS_PRODUCT), "--json"]) == 0
    explain_payload = _json_output(capsys)
    assert explain_payload["spec"] == "odps"
    assert explain_payload["kind"] == "OpenDataProduct"
    assert explain_payload["product"]["id"] == "agent-ready-product"
    assert explain_payload["product"]["name"] == "Agent Ready Product"
    assert explain_payload["product"]["status"] == "production"
    assert explain_payload["components"] == 1
    assert explain_payload["production_ready"] is False
    assert "summary" not in explain_payload

    assert main(["summary", str(ODPS_PRODUCT)]) == 0
    summary_output = capsys.readouterr().out
    assert summary_output.startswith(f"File: {ODPS_PRODUCT}\n")
    assert "Spec: odps\n" in summary_output
    assert "Kind: OpenDataProduct\n" in summary_output
    assert "SHA-256: " in summary_output
    assert not summary_output.lstrip().startswith("{")

    assert main(["summary", str(ODPS_PRODUCT), "--json"]) == 0
    summary_payload = _json_output(capsys)
    assert summary_payload["spec"] == "odps"
    assert "sha256" in summary_payload


def test_unified_cli_validate_human_output_is_step_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["validate", str(ODPS_PRODUCT)]) == 0

    output = capsys.readouterr().out

    assert f"✓ Loaded ODPS document: {ODPS_PRODUCT}" in output
    assert "✓ Detected kind: OpenDataProduct" in output
    assert "✓ Detected version: 4.1" in output
    assert "✓ Schema validation passed" in output
    assert "✓ ODPS validation passed" in output
    assert "Resources are valid" not in output
    assert "Relationships are valid" not in output
    assert "Validation successful!" in output


def test_unified_cli_resources_and_manifest(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["resources", "--json"]) == 0
    resources_payload = capsys.readouterr().out
    assert "odpv.terms" in resources_payload

    assert main(["manifest", "--json"]) == 0
    manifest_payload = _json_output(capsys)
    assert manifest_payload["name"] == "open-data-products"
    assert {tool["name"] for tool in manifest_payload["tools"]} >= {
        "validate_document",
        "search_terms",
        "agent_context",
    }


def test_unified_cli_config_reports_generation_template(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["config", "generation", "--json"]) == 0
    payload = _json_output(capsys)

    assert payload["domain"] == "generation"
    assert payload["template_path"].endswith(
        "open_data_products/generation/generation.config.yaml"
    )
    assert payload["resolved"]["provider"] == "ollama"
    assert payload["resolved"]["model"] == "qwen2.5"
    assert payload["editable"] is False
    assert "claude" in payload["providers"]


def test_unified_cli_config_prints_current_config(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    config = tmp_path / "my-generation.config.yaml"
    config.write_text(
        "provider: groq\nproviders:\n  groq:\n    type: openai\n",
        encoding="utf-8",
    )

    assert main(["config", "generation", "--config", str(config), "--print"]) == 0
    output = capsys.readouterr().out

    assert output.startswith("provider: groq")
    assert "type: openai" in output
    assert "Config domain:" not in output


def test_unified_cli_config_copies_generation_template(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output = tmp_path / "generation.config.yaml"

    assert main(["config", "generation", "--copy-to", str(output), "--json"]) == 0
    payload = _json_output(capsys)

    assert payload["domain"] == "generation"
    assert payload["copied_to"] == str(output)
    assert payload["config_path"] == str(output)
    assert output.read_text(encoding="utf-8").startswith("# Generation config")


def test_unified_cli_config_copies_generation_template_to_folder(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "configs" / "llm"
    expected = output_dir / "generation.config.yaml"

    assert main(["config", "generation", "--copy-to", f"{output_dir}/", "--json"]) == 0
    payload = _json_output(capsys)

    assert payload["copied_to"] == str(expected)
    assert payload["config_path"] == str(expected)
    assert expected.read_text(encoding="utf-8").startswith("# Generation config")


def test_unified_cli_config_copies_generation_prompts_to_folder(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "prompts"

    assert (
        main(
            [
                "config",
                "generation",
                "--copy-prompts-to",
                str(output_dir),
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)

    assert payload["prompt_dir"] == str(output_dir)
    assert "odpc_signal_fragment.md" in payload["copied_prompts"]
    assert (output_dir / "odpc_signal_fragment.md").is_file()


def test_unified_cli_config_check_reports_invalid_config(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    config = tmp_path / "bad-generation.config.yaml"
    config.write_text(
        """
provider: groq
providers:
  groq:
    type: spaceship
    model: gpt-test
""",
        encoding="utf-8",
    )

    assert (
        main(["config", "generation", "--config", str(config), "--check", "--json"])
        == 1
    )
    payload = _json_output(capsys)

    assert payload["valid"] is False
    assert (
        "providers.groq.type must be one of anthropic, llama-cpp, ollama, openai, openai-chat"
        in payload["errors"]
    )


def test_unified_cli_generation_uses_custom_prompt_dir(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products import generation

    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "odpc_signal_fragment.md").write_text(
        "CUSTOM\n{source_documents}\n", encoding="utf-8"
    )
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    output_dir = tmp_path / "generated"
    observed: Dict[str, object] = {}

    def fake_generate_local_artifacts_for_kind(
        artifact_kind: str,
        source_path: Union[str, Path],
        output_path: Union[str, Path],
        model: str = "qwen2.5",
        ollama_url: str = "http://localhost:11434",
        client: Optional[object] = None,
        prompt_dir: Optional[Union[str, Path]] = None,
    ) -> List[generation.GeneratedArtifact]:
        observed["prompt_dir"] = str(prompt_dir)
        output = Path(output_path) / "signal.yaml"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("signal: {}\n", encoding="utf-8")
        return [
            generation.GeneratedArtifact(
                name="odpc_signals",
                prompt_name="odpc_signal_fragment.md",
                output_path=output,
                valid_yaml=True,
            )
        ]

    monkeypatch.setattr(
        generation,
        "generate_local_artifacts_for_kind",
        fake_generate_local_artifacts_for_kind,
    )
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: (lambda prompt, model: ""),
    )

    assert (
        main(
            [
                "generate",
                "--input",
                str(source),
                "--kind",
                "signal",
                "--output",
                str(output_dir),
                "--prompts",
                str(prompt_dir),
                "--json",
            ]
        )
        == 0
    )
    _json_output(capsys)

    assert observed["prompt_dir"] == str(prompt_dir)


def test_unified_cli_local_generation_requires_kind(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "generate",
                "--input",
                str(GENERATION_SOURCE_DOCS),
                "--output",
                str(tmp_path),
                "--model",
                "qwen2.5",
                "--json",
            ]
        )

    assert exc_info.value.code == 2
    assert "the following arguments are required: --kind" in capsys.readouterr().err


def test_unified_cli_local_generation_rejects_all_kind(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "generate",
                "--input",
                str(GENERATION_SOURCE_DOCS),
                "--output",
                str(tmp_path),
                "--kind",
                "all",
            ]
        )

    assert exc_info.value.code == 2
    assert "invalid choice: 'all'" in capsys.readouterr().err


def test_unified_cli_local_generation(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products import generation

    def fake_generate_local_artifacts_for_kind(
        artifact_kind: str,
        source_dir: Union[str, Path],
        output_dir: Union[str, Path],
        model: str = "qwen2.5",
        ollama_url: str = "http://localhost:11434",
        client: Optional[object] = None,
    ) -> List[generation.GeneratedArtifact]:
        output = Path(output_dir) / "odpc_signals.yaml"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("signals: []\n", encoding="utf-8")
        return [
            generation.GeneratedArtifact(
                name="odpc_signals",
                prompt_name="odpc_signal_fragment.md",
                output_path=output,
                valid_yaml=True,
            )
        ]

    monkeypatch.setattr(
        generation,
        "generate_local_artifacts_for_kind",
        fake_generate_local_artifacts_for_kind,
    )
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: (lambda prompt, model: ""),
    )

    assert (
        main(
            [
                "generate",
                "--input",
                str(GENERATION_SOURCE_DOCS),
                "--output",
                str(tmp_path),
                "--model",
                "qwen2.5",
                "--kind",
                "signal",
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)

    assert payload["kind"] == "LocalGeneration"
    assert payload["source"] == str(GENERATION_SOURCE_DOCS)
    assert payload["artifact_kind"] == "signal"
    assert payload["output"] == str(tmp_path)
    assert payload["model"] == "qwen2.5"
    assert payload["valid_yaml"] is True
    assert payload["artifact_count"] == 1
    assert payload["artifacts"][0]["name"] == "odpc_signals"


def test_unified_cli_local_generation_can_select_one_kind(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products import generation

    def fake_generate_local_artifacts_for_kind(
        artifact_kind: str,
        source: Union[str, Path],
        output_dir: Union[str, Path],
        model: str = "qwen2.5",
        ollama_url: str = "http://localhost:11434",
        client: Optional[object] = None,
    ) -> List[generation.GeneratedArtifact]:
        output = Path(output_dir) / "odpc_use_cases.yaml"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("useCases: []\n", encoding="utf-8")
        return [
            generation.GeneratedArtifact(
                name="odpc_use_cases",
                prompt_name="odpc_use_case_fragment.md",
                output_path=output,
                valid_yaml=True,
            )
        ]

    monkeypatch.setattr(
        generation,
        "generate_local_artifacts_for_kind",
        fake_generate_local_artifacts_for_kind,
    )
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: (lambda prompt, model: ""),
    )

    assert (
        main(
            [
                "generate",
                str(GENERATION_SOURCE_DOCS / "flight-delay-use-case.md"),
                "--kind",
                "use-case",
                "--output",
                str(tmp_path),
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)

    assert payload["kind"] == "LocalGeneration"
    assert payload["artifact_kind"] == "use-case"
    assert payload["artifact_count"] == 1
    assert payload["artifacts"][0]["name"] == "odpc_use_cases"


def test_unified_cli_local_generation_uses_default_paths(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products import generation
    from open_data_products.cli import (
        DEFAULT_GENERATION_INPUT,
        DEFAULT_GENERATION_OUTPUT,
    )

    observed = {}

    def fake_generate_local_artifacts_for_kind(
        artifact_kind: str,
        source_dir: Union[str, Path],
        output_dir: Union[str, Path],
        model: str = "qwen2.5",
        ollama_url: str = "http://localhost:11434",
        client: Optional[object] = None,
    ) -> List[generation.GeneratedArtifact]:
        observed["source"] = source_dir
        observed["output"] = output_dir
        return [
            generation.GeneratedArtifact(
                name="odpg_graph",
                prompt_name="odpg_graph_yaml.md",
                output_path=Path(output_dir) / "odpg_graph.yaml",
                valid_yaml=True,
            )
        ]

    monkeypatch.setattr(
        generation,
        "generate_local_artifacts_for_kind",
        fake_generate_local_artifacts_for_kind,
    )
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: (lambda prompt, model: ""),
    )

    assert main(["generate", "--kind", "graph", "--json"]) == 0
    payload = _json_output(capsys)

    assert observed == {
        "source": DEFAULT_GENERATION_INPUT,
        "output": DEFAULT_GENERATION_OUTPUT,
    }
    assert payload["source"] == DEFAULT_GENERATION_INPUT
    assert payload["output"] == DEFAULT_GENERATION_OUTPUT


def test_unified_cli_local_generation_rejects_positional_and_input(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    assert (
        main(
            [
                "generate",
                str(GENERATION_SOURCE_DOCS),
                "--input",
                str(GENERATION_SOURCE_DOCS),
                "--output",
                str(tmp_path),
                "--kind",
                "signal",
            ]
        )
        == 2
    )

    assert "either positional source_dir or --input" in capsys.readouterr().err


def test_unified_cli_local_generation_hints_about_trailing_backslash_space(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    assert (
        main(
            [
                "generate",
                "--input",
                str(GENERATION_SOURCE_DOCS),
                "--output",
                str(tmp_path),
                "--kind",
                "signal",
                " ",
            ]
        )
        == 2
    )

    error = capsys.readouterr().err
    assert "either positional source_dir or --input" in error
    assert "trailing space after a line-continuation backslash" in error


def test_unified_cli_generation_accepts_model_override(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products import generation

    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: (lambda prompt, model: ""),
    )
    monkeypatch.setattr(
        generation,
        "generate_local_artifacts_for_kind",
        lambda artifact_kind, source_dir, output_dir, model="qwen2.5", ollama_url="http://localhost:11434", client=None: [
            generation.GeneratedArtifact(
                name="odpg_graph",
                prompt_name="odpg_graph_yaml.md",
                output_path=Path(output_dir) / "odpg_graph.yaml",
                valid_yaml=True,
            )
        ],
    )

    assert (
        main(
            [
                "generate",
                str(GENERATION_SOURCE_DOCS),
                "--output",
                str(tmp_path),
                "--model",
                "llama3.2",
                "--kind",
                "graph",
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)

    assert payload["model"] == "llama3.2"


def test_unified_cli_generation_uses_claude_without_config(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products import generation

    source = tmp_path / "signal-source.md"
    source.write_text(
        "Generate a signal about baggage belt congestion.",
        encoding="utf-8",
    )
    output_dir = tmp_path / "generated"
    observed: Dict[str, object] = {}

    def fake_anthropic_generate(
        prompt: str,
        model: str,
        api_key_env: str = "ANTHROPIC_API_KEY",
        base_url: str = "https://api.anthropic.com/v1",
        version: str = "2023-06-01",
        max_tokens: int = 8192,
    ) -> str:
        observed.update(
            {
                "prompt": prompt,
                "model": model,
                "api_key_env": api_key_env,
                "base_url": base_url,
                "version": version,
                "max_tokens": max_tokens,
            }
        )
        return """signals:
- id: baggage-belt-congestion-signal
  name:
    en: Baggage Belt Congestion Signal
  description:
    en: Baggage belt congestion exceeded the operating threshold.
  type: operational
  source:
    origin: internal
    method: baggage operations event stream
  observedAt: "2026-05-20T00:00:00Z"
"""

    monkeypatch.setattr(generation, "anthropic_generate", fake_anthropic_generate)

    assert (
        main(
            [
                "generate",
                "--provider",
                "claude",
                "--model",
                "claude-sonnet-4-5",
                "--input",
                str(source),
                "--kind",
                "signal",
                "--output",
                str(output_dir),
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)

    assert payload["kind"] == "Generation"
    assert payload["provider"] == "claude"
    assert payload["provider_type"] == "anthropic"
    assert payload["model"] == "claude-sonnet-4-5"
    assert payload["valid_yaml"] is True
    assert payload["artifact_count"] == 1
    assert payload["artifacts"][0]["name"] == "signal:baggage-belt-congestion-signal"
    assert (output_dir / "signal_baggage-belt-congestion-signal.yaml").is_file()
    assert observed["api_key_env"] == "ANTHROPIC_API_KEY"
    assert observed["base_url"] == "https://api.anthropic.com/v1"
    assert observed["version"] == "2023-06-01"
    assert observed["max_tokens"] == 8192


def test_unified_cli_odps_generation_passes_profile_and_components(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products import generation

    source = tmp_path / "meeting.txt"
    source.write_text(
        "Meeting transcript for a retention data product.",
        encoding="utf-8",
    )
    output_dir = tmp_path / "products"
    observed: Dict[str, object] = {}

    def fake_generate_local_artifacts_for_kind(
        artifact_kind: str,
        source_dir: Union[str, Path],
        output_dir: Union[str, Path],
        model: str = "qwen2.5",
        ollama_url: str = "http://localhost:11434",
        client: Optional[object] = None,
        profile: str = "minimal",
        include_components: Optional[List[str]] = None,
        max_source_chars: Optional[int] = None,
    ) -> List[generation.GeneratedArtifact]:
        observed.update(
            {
                "artifact_kind": artifact_kind,
                "source": source_dir,
                "output": output_dir,
                "profile": profile,
                "include_components": include_components,
                "max_source_chars": max_source_chars,
            }
        )
        output = Path(output_dir) / "odps_product_customer-retention.yaml"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            "product:\n  productID: customer-retention\n",
            encoding="utf-8",
        )
        return [
            generation.GeneratedArtifact(
                name="odpsProduct:customer-retention",
                prompt_name="odps_product_assemble_yaml.md",
                output_path=output,
                valid_yaml=True,
                review_notes=["pricingPlans drafted for review."],
                drafted_components=["pricingPlans", "dataAccess"],
                evidence_gaps=["Missing pricing details."],
            )
        ]

    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: (lambda prompt, model: ""),
    )
    monkeypatch.setattr(
        generation,
        "generate_local_artifacts_for_kind",
        fake_generate_local_artifacts_for_kind,
    )

    assert (
        main(
            [
                "generate",
                "--input",
                str(source),
                "--kind",
                "odps-product",
                "--profile",
                "complete-draft",
                "--include-components",
                "pricingPlans,dataAccess",
                "--max-source-chars",
                "12000",
                "--output",
                str(output_dir),
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)

    assert observed["profile"] == "complete-draft"
    assert observed["include_components"] == ["pricingPlans", "dataAccess"]
    assert observed["max_source_chars"] == 12000
    assert payload["profile"] == "complete-draft"
    assert payload["include_components"] == ["pricingPlans", "dataAccess"]
    assert payload["max_source_chars"] == 12000
    assert payload["artifacts"][0]["review_notes"] == [
        "pricingPlans drafted for review."
    ]
    assert payload["artifacts"][0]["drafted_components"] == [
        "pricingPlans",
        "dataAccess",
    ]
    assert payload["artifacts"][0]["evidence_gaps"] == ["Missing pricing details."]


def test_unified_cli_generation_uses_config_provider(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products import generation

    config = tmp_path / "generation.config.yaml"
    output_dir = tmp_path / "configured-output"
    config.write_text(
        f"""
provider: openai
input: {GENERATION_SOURCE_DOCS}
output: {output_dir}
providers:
  openai:
    type: openai
    model: gpt-test
    apiKeyEnv: TEST_OPENAI_API_KEY
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: (lambda prompt, model: ""),
    )
    monkeypatch.setattr(
        generation,
        "generate_local_artifacts_for_kind",
        lambda artifact_kind, source_dir, output_dir, model="qwen2.5", ollama_url="http://localhost:11434", client=None: [
            generation.GeneratedArtifact(
                name="odpg_graph",
                prompt_name="odpg_graph_yaml.md",
                output_path=Path(output_dir) / "odpg_graph.yaml",
                valid_yaml=True,
            )
        ],
    )

    assert main(["generate", "--config", str(config), "--kind", "graph", "--json"]) == 0
    payload = _json_output(capsys)

    assert payload["source"] == str(GENERATION_SOURCE_DOCS)
    assert payload["output"] == str(output_dir)
    assert payload["provider"] == "openai"
    assert payload["provider_type"] == "openai"
    assert payload["model"] == "gpt-test"


def test_unified_cli_odpc_commands(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
schema: https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml
version: '1.0'
kind: Catalog
catalog:
  metadata:
    id: CAT-001
    name:
      en: Customer Data Product Catalog
    description:
      en: Catalog for customer-facing data products.
  productReferences:
    - id: PRODUCT-001
      productID: PRODUCT-001
      productVersion: '1.0'
      name:
        en: Customer Product
      description:
        en: Customer product reference.
      productModel:
        standard: ODPS
        version: '4.0'
        format: yaml
        $ref: ./product.yaml
""",
        encoding="utf-8",
    )

    assert main(["odpc-summary", str(catalog), "--json"]) == 0
    summary_payload = _json_output(capsys)
    assert summary_payload["spec"] == "odpc"
    assert summary_payload["catalogId"] == "CAT-001"
    assert summary_payload["productReferenceCount"] == 1

    assert main(["odpc-search", "catalog data", "--limit", "1", "--json"]) == 0
    search_payload = _json_output(capsys)
    assert search_payload["spec"] == "odpc"
    assert len(search_payload["matches"]) == 1

    assert main(["odpc-artifacts", str(tmp_path), "--check", "--json"]) == 1
    artifact_check_payload = _json_output(capsys)
    assert artifact_check_payload["spec"] == "odpc"
    assert artifact_check_payload["in_sync"] is False
    assert artifact_check_payload["changed"] == ["odpc.json"]

    assert main(["odpc-artifacts", str(tmp_path), "--json"]) == 0
    artifact_payload = _json_output(capsys)
    assert artifact_payload["artifact_count"] == 1

    assert main(["odpc-artifacts", str(tmp_path), "--check", "--json"]) == 0
    assert _json_output(capsys)["in_sync"] is True


def test_unified_cli_builds_odpc_catalog_from_fragments(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    output = tmp_path / "catalog.yaml"
    html_output = tmp_path / "catalog.html"
    toon_output = tmp_path / "catalog.toon"
    gcf_output = tmp_path / "catalog.gcf"
    (fragments / "product.yaml").write_text(
        """
schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      name: Agent Ready Product
      productID: agent-ready-product
      visibility: public
""",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "odpc-build",
                str(fragments),
                "--output",
                str(output),
                "--html",
                str(html_output),
                "--toon",
                str(toon_output),
                "--gcf",
                str(gcf_output),
                "--id",
                "CAT-CLI",
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)
    assert payload["spec"] == "odpc"
    assert payload["kind"] == "Catalog"
    assert payload["output"] == str(output)
    assert payload["html"] == str(html_output)
    assert payload["toon"] == str(toon_output)
    assert payload["gcf"] == str(gcf_output)
    assert payload["productReferenceCount"] == 1

    assert output.read_text(encoding="utf-8").startswith(
        "schema: https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml\n"
    )
    html = html_output.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "Agent Ready Product" in html
    assert "productReferences[1]" in toon_output.read_text(encoding="utf-8")
    gcf = gcf_output.read_text(encoding="utf-8")
    assert "GCF profile=generic tool=open-data-products kind=odpc-catalog" in gcf
    assert "## productReferences [1]" in gcf


def test_unified_cli_builds_odpg_graph_from_odpc_fragments(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products import generation

    fragments = tmp_path / "fragments"
    fragments.mkdir()
    output = tmp_path / "graph.yaml"
    toon_output = tmp_path / "graph.toon"
    gcf_output = tmp_path / "graph.gcf"
    context_graph = tmp_path / "previous-graph.yaml"
    context_graph.write_text("full previous graph yaml", encoding="utf-8")
    context_graph.with_suffix(".gcf").write_text(
        "compact previous graph context", encoding="utf-8"
    )
    (fragments / "product.yaml").write_text(
        """
productReference:
  id: customer-analytics-product
  name:
    en: Customer Analytics Product
  description:
    en: Trusted customer analytics for retention decisions.
""",
        encoding="utf-8",
    )
    (fragments / "use-case.yaml").write_text(
        """
useCase:
  id: customer-retention
  name:
    en: Customer Retention
  description:
    en: Improve retention decisions with trusted customer analytics.
""",
        encoding="utf-8",
    )

    def fake_create_generation_client(settings):
        def fake_client(prompt: str, model: str) -> str:
            assert "customer-retention" in prompt
            assert "compact previous graph context" in prompt
            assert "full previous graph yaml" not in prompt
            return """
edges:
  - from: customer-retention
    to: customer-analytics-product
    type: dependsOn
    confidence: high
"""

        return fake_client

    monkeypatch.setattr(
        generation,
        "create_generation_client",
        fake_create_generation_client,
    )

    assert (
        main(
            [
                "odpg-build",
                str(fragments),
                "--output",
                str(output),
                "--toon",
                str(toon_output),
                "--gcf",
                str(gcf_output),
                "--context-graph",
                str(context_graph),
                "--id",
                "customer-graph",
                "--model",
                "test-model",
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)
    assert payload["spec"] == "odpg"
    assert payload["kind"] == "Graph"
    assert payload["output"] == str(output)
    assert payload["toon"] == str(toon_output)
    assert payload["gcf"] == str(gcf_output)
    assert payload["valid"] is True
    assert payload["nodeCount"] == 2
    assert payload["edgeCount"] == 1

    graph = __import__("yaml").safe_load(output.read_text(encoding="utf-8"))
    assert graph["graph"]["metadata"]["id"] == "customer-graph"
    assert graph["graph"]["edges"][0]["type"] == "dependsOn"
    assert "edges[1]{from,to,type,confidence}:" in toon_output.read_text(
        encoding="utf-8"
    )
    gcf = gcf_output.read_text(encoding="utf-8")
    assert "GCF profile=generic tool=open-data-products kind=odpg-graph" in gcf
    assert "## edges [1]" in gcf
    assert "@0<@1 dependsOn high" in gcf


def test_unified_cli_odpv_commands(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["odpv-summary", "--json"]) == 0
    summary_payload = _json_output(capsys)
    assert summary_payload["spec"] == "odpv"
    assert summary_payload["kind"] == "Vocabulary"
    assert summary_payload["term_count"] == 59

    assert (
        main(["odpv-search", "governance policy risk", "--limit", "2", "--json"]) == 0
    )
    search_payload = _json_output(capsys)
    assert search_payload["spec"] == "odpv"
    assert len(search_payload["matches"]) == 2

    assert (
        main(
            [
                "odpv-search",
                "nonsense term that should not match",
                "--json",
            ]
        )
        == 1
    )
    search_payload = _json_output(capsys)
    assert search_payload["matches"] == []

    assert main(["odpv-resolve", "reusable data asset", "--json"]) == 0
    resolve_payload = _json_output(capsys)
    assert resolve_payload["match"]["id"] == "DataProduct"
    assert resolve_payload["match"]["matchType"] == "alias"

    assert main(["odpv-explain", "DataProduct", "--json"]) == 0
    assert _json_output(capsys)["id"] == "DataProduct"

    assert (
        main(
            [
                "odpv-relationship",
                "DataProduct",
                "supports",
                "UseCase",
                "--json",
            ]
        )
        == 0
    )
    assert _json_output(capsys)["compatible"] is True

    assert main(["odpv-context", "DataProduct", "--json"]) == 0
    assert _json_output(capsys)["contextType"] == "odpv.term"


def test_unified_cli_odpg_reasoning_commands(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    assert main(["odpg-summary", str(ODPG_GRAPH), "--json"]) == 0
    assert _json_output(capsys)["nodeCount"] == 9

    assert (
        main(
            [
                "odpg-traverse",
                str(ODPG_GRAPH),
                "--start",
                "AGENT-AVIATION-001",
                "--json",
            ]
        )
        == 0
    )
    assert _json_output(capsys)["start"] == "AGENT-AVIATION-001"

    assert main(["odpg-analyze", str(ODPG_GRAPH), "--json"]) == 0
    assert "analysis" in _json_output(capsys)

    assert (
        main(
            [
                "odpg-agent-context",
                str(ODPG_GRAPH),
                "--node",
                "AGENT-AVIATION-001",
                "--json",
            ]
        )
        == 0
    )
    assert _json_output(capsys)["focusNode"]["id"] == "AGENT-AVIATION-001"

    output = tmp_path / "output" / "graph-explorer.html"
    assert (
        main(
            [
                "odpg-generate",
                str(ODPG_GRAPH),
                "--output",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)
    assert payload["spec"] == "odpg"
    assert payload["generated"] is True
    assert output.exists()


def test_odpg_agent_context_can_include_compact_context_artifact(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph.yaml"
    graph.write_text(ODPG_GRAPH.read_text(encoding="utf-8"), encoding="utf-8")
    graph.with_suffix(".gcf").write_text("compact graph context", encoding="utf-8")

    assert (
        main(
            [
                "odpg-agent-context",
                str(graph),
                "--node",
                "AGENT-AVIATION-001",
                "--context-format",
                "auto",
                "--json",
            ]
        )
        == 0
    )

    payload = _json_output(capsys)
    assert payload["focusNode"]["id"] == "AGENT-AVIATION-001"
    assert payload["contextArtifact"] == {
        "format": "gcf",
        "path": str(graph.with_suffix(".gcf")),
        "content": "compact graph context",
    }

    graph_source = tmp_path / "graph.graphson"
    graph_yaml = tmp_path / "converted-graph.yaml"
    graph_source.write_text(
        """
{
  "vertices": [
    {"id": "product-orders", "label": "DataProduct"},
    {"id": "case-retention", "label": "UseCase"}
  ],
  "edges": [
    {"outV": "case-retention", "inV": "product-orders", "label": "uses"}
  ]
}
""",
        encoding="utf-8",
    )
    assert (
        main(
            [
                "odpg-convert",
                "--input",
                str(graph_source),
                "--output",
                str(graph_yaml),
                "--json",
            ]
        )
        == 0
    )
    convert_payload = _json_output(capsys)
    assert convert_payload["spec"] == "odpg"
    assert convert_payload["converted"] is True
    assert graph_yaml.exists()


def test_unified_cli_odpg_reasoning_human_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["odpg-summary", str(ODPG_GRAPH)]) == 0
    output = capsys.readouterr().out
    assert "ODPG Graph:" in output
    assert "Nodes: 9" in output

    assert (
        main(["odpg-traverse", str(ODPG_GRAPH), "--start", "AGENT-AVIATION-001"]) == 0
    )
    output = capsys.readouterr().out
    assert "Start: AGENT-AVIATION-001" in output
    assert "Paths:" in output


def test_unified_cli_contract_workflow(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    product = tmp_path / "product.yaml"
    contract = tmp_path / "orders.contract.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: '4.0'
product:
  name: Orders
  productID: orders
  visibility: public
  status: production
  type: dataset
  datasets:
    orders:
      fields:
        order_id:
          type: string
  contract:
    type: DCS
    spec:
      name: Orders
      models:
        orders:
          fields:
            order_id:
              type: string
              required: true
""",
        encoding="utf-8",
    )
    contract.write_text(
        """
name: Orders
models:
  orders:
    fields:
      order_id:
        type: string
        required: true
""",
        encoding="utf-8",
    )

    assert main(["product", "resolve-contracts", str(product), "--json"]) == 0
    assert _json_output(capsys)["references"][0]["inline_spec"] is not None

    assert main(["product", "contract-schema", str(contract), "--json"]) == 0
    assert _json_output(capsys)["field_count"] == 1

    assert main(["product", "contract-report", str(product), "--json"]) == 0
    report_payload = _json_output(capsys)
    assert report_payload["summaries"][0]["name"] == "Orders"
    assert report_payload["summaries"][0]["field_count"] == 1
    assert report_payload["alignments"][0]["passed"] is True

    assert (
        main(["product", "check-contract", str(product), str(contract), "--json"]) == 1
    )
    check_payload = _json_output(capsys)
    assert check_payload["product"]["valid"] is True
    assert check_payload["contract"]["passed"] is False
    assert check_payload["summary"].startswith("Product valid; Data Contract invalid")

    assert (
        main(["product", "align-contract", str(product), str(contract), "--json"]) == 1
    )
    alignment_payload = _json_output(capsys)
    assert alignment_payload["contract_valid"] is False
    assert alignment_payload["summary"].startswith(
        "Product valid; Data Contract invalid"
    )

    assert (
        main(["product", "audit", str(product), "--contract", str(contract), "--json"])
        == 1
    )
    audit_payload = _json_output(capsys)
    assert audit_payload["contract_count"] == 1
    assert audit_payload["validations"][0]["passed"] is False
    assert audit_payload["findings"][0]["severity"] == "error"
    assert audit_payload["summary"].startswith(
        "Product valid; 1 Data Contract reference"
    )
