"""Tests for recipe workflow planning."""

from __future__ import annotations

import json
from pathlib import Path
import yaml

from open_data_products.odpr import (
    build_recipe_catalog,
    execute_recipe_run,
    get_recipe_guidance,
    load_odpr_schema,
    load_recipe,
    load_recipe_guidance,
    plan_recipe_run,
    search_recipe_guidance,
    validate_odpr_document,
    validate_recipe,
    validate_recipe_config,
)


def _write_recipe(path: Path) -> None:
    path.write_text(
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
  execution:
    providerRef: claude
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


def _write_validate_recipe(path: Path) -> None:
    path.write_text(
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


def _write_portfolio_sync_recipe(path: Path) -> None:
    path.write_text(
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


def _write_catalog(path: Path) -> None:
    path.write_text(
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


def _write_recipe_config(path: Path, generation_config: str) -> None:
    path.write_text(
        f"""
version: "1.0"
providers:
  generationConfig: {generation_config}
""",
        encoding="utf-8",
    )


def _write_generation_config(path: Path) -> None:
    path.write_text(
        """
provider: ollama
providers:
  configured-openai:
    type: openai
    model: gpt-test
    apiKeyEnv: TEST_ODPR_OPENAI_API_KEY
  configured-local:
    type: ollama
    model: qwen-test
    baseUrl: http://localhost:11434
""",
        encoding="utf-8",
    )


def test_validate_recipe_accepts_inline_steps(tmp_path: Path) -> None:
    """Test that a minimal ODPR recipe validates."""
    recipe_path = tmp_path / "recipe.yaml"
    _write_recipe(recipe_path)

    report = validate_recipe(recipe_path)

    assert report["valid"] is True
    assert report["errors"] == []
    assert report["recipe"]["id"] == "RCP-LOCALIZE-001"
    assert report["steps"][0]["classification"] == "llm-backed"
    assert report["schemaValidation"] == "draft-2020-12"


def test_odpr_schema_is_bundled() -> None:
    """Test the SDK bundles the released ODPR schema."""
    schema = load_odpr_schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["kind"]["enum"] == [
        "Recipe",
        "Provider",
        "RecipeCatalog",
    ]


def test_recipe_guidance_is_bundled_and_searchable() -> None:
    """Test bundled ODPR recipe guidance records are searchable."""
    records = load_recipe_guidance()

    assert {record["id"] for record in records} >= {
        "Recipe",
        "Provider",
        "RecipeCatalog",
    }
    assert get_recipe_guidance("RecipeCatalog")["id"] == "RecipeCatalog"
    matches = search_recipe_guidance("metadata discovery")
    assert matches
    assert matches[0]["id"] == "RecipeCatalog"


def test_validate_recipe_rejects_provider_on_deterministic_step(tmp_path: Path) -> None:
    """Test deterministic command validation catches provider fields."""
    recipe_path = tmp_path / "recipe.yaml"
    _write_recipe(recipe_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    data["recipe"]["steps"][0]["command"] = "portfolio.render"
    recipe_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    report = validate_recipe(recipe_path)

    assert report["valid"] is False
    assert (
        "steps[0].providerRef is only valid for LLM-backed commands" in report["errors"]
    )
    assert "steps[0].model is only valid for LLM-backed commands" in report["errors"]


def test_validate_recipe_runs_json_schema_for_step_parameters(tmp_path: Path) -> None:
    """Test schema validation catches command-specific with-field types."""
    recipe_path = tmp_path / "recipe.yaml"
    _write_recipe(recipe_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    data["recipe"]["steps"][0]["with"]["languages"] = "fi,sv"
    recipe_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    report = validate_recipe(recipe_path)

    assert report["valid"] is False
    assert any("languages" in error and "array" in error for error in report["errors"])


def test_plan_recipe_run_dry_run_returns_structured_parameters(
    tmp_path: Path,
) -> None:
    """Test dry-run planning exposes agent-friendly resolved parameters."""
    recipe_path = tmp_path / "recipe.yaml"
    workspace = tmp_path / "generated" / "portfolio"
    workspace.mkdir(parents=True)
    _write_recipe(recipe_path)

    plan = plan_recipe_run(recipe_path, mode="dry-run", project_root=tmp_path)

    assert plan["mode"] == "dry-run"
    assert plan["canRun"] is True
    assert plan["recipe"]["id"] == "RCP-LOCALIZE-001"
    step = plan["steps"][0]
    assert step["command"] == "portfolio.localize"
    assert step["classification"] == "llm-backed"
    assert step["resolved"] == {
        "action": "portfolio.localize",
        "parameters": {
            "workspace": "generated/portfolio/",
            "languages": ["fi", "sv"],
            "providerRef": "claude",
            "model": "claude-sonnet-4-5",
        },
    }
    assert step["inputs"] == [{"path": "generated/portfolio/", "exists": True}]
    assert {
        "path": "generated/portfolio/index.fi.html",
        "allowed": True,
    } in step["plannedWrites"]
    assert step["review"]["status"] == "review-needed"
    assert step["review"]["reasons"] == [
        {
            "code": "llm_backed_step",
            "message": "LLM-backed steps require review before execution.",
        }
    ]


def test_plan_recipe_run_marks_configured_recipe_type_review_needed(
    tmp_path: Path,
) -> None:
    """Test release-type recipes are review-needed when config requires it."""
    recipe_path = tmp_path / "recipe.yaml"
    config_path = tmp_path / "recipes.config.yaml"
    _write_validate_recipe(recipe_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    data["recipe"]["type"] = "release"
    recipe_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    config_path.write_text(
        """
version: "1.0"
execution:
  requireReviewFor:
    - release
""",
        encoding="utf-8",
    )

    plan = plan_recipe_run(
        recipe_path,
        config_path=config_path,
        project_root=tmp_path,
    )

    assert plan["steps"][0]["review"]["status"] == "review-needed"
    assert plan["steps"][0]["review"]["reasons"] == [
        {
            "code": "recipe_type_requires_review",
            "message": "Recipe type requires review: release",
        }
    ]


def test_plan_recipe_run_marks_deterministic_ci_review_not_required(
    tmp_path: Path,
) -> None:
    """Test deterministic CI recipes stay review-not-required by default."""
    recipe_path = tmp_path / "recipe.yaml"
    _write_validate_recipe(recipe_path)

    plan = plan_recipe_run(recipe_path, project_root=tmp_path)

    assert plan["steps"][0]["review"] == {"status": "not-required", "reasons": []}


def test_plan_recipe_run_reports_provider_ready_when_env_is_present(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Test provider readiness checks configured env vars without provider calls."""
    recipe_path = tmp_path / "recipe.yaml"
    config_path = tmp_path / "recipes.config.yaml"
    generation_path = tmp_path / "generation.config.yaml"
    _write_recipe(recipe_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    data["recipe"]["execution"]["providerRef"] = "configured-openai"
    data["recipe"]["steps"][0]["providerRef"] = "configured-openai"
    recipe_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    _write_recipe_config(config_path, "generation.config.yaml")
    _write_generation_config(generation_path)
    monkeypatch.setenv("TEST_ODPR_OPENAI_API_KEY", "present")

    plan = plan_recipe_run(
        recipe_path,
        config_path=config_path,
        project_root=tmp_path,
    )

    assert plan["providers"] == [
        {
            "ref": "configured-openai",
            "model": "claude-sonnet-4-5",
            "type": "openai",
            "readiness": "ready",
            "missingEnv": [],
            "source": str(generation_path),
        }
    ]


def test_plan_recipe_run_reports_missing_provider_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Test provider readiness reports missing environment variables."""
    recipe_path = tmp_path / "recipe.yaml"
    config_path = tmp_path / "recipes.config.yaml"
    generation_path = tmp_path / "generation.config.yaml"
    _write_recipe(recipe_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    data["recipe"]["execution"]["providerRef"] = "configured-openai"
    data["recipe"]["steps"][0]["providerRef"] = "configured-openai"
    recipe_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    _write_recipe_config(config_path, "generation.config.yaml")
    _write_generation_config(generation_path)
    monkeypatch.delenv("TEST_ODPR_OPENAI_API_KEY", raising=False)

    plan = plan_recipe_run(
        recipe_path,
        config_path=config_path,
        project_root=tmp_path,
    )

    assert plan["providers"][0]["readiness"] == "missing-env"
    assert plan["providers"][0]["missingEnv"] == ["TEST_ODPR_OPENAI_API_KEY"]


def test_plan_recipe_run_reports_unknown_provider(tmp_path: Path) -> None:
    """Test provider readiness reports recipe provider refs missing from config."""
    recipe_path = tmp_path / "recipe.yaml"
    config_path = tmp_path / "recipes.config.yaml"
    generation_path = tmp_path / "generation.config.yaml"
    _write_recipe(recipe_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    data["recipe"]["execution"]["providerRef"] = "not-configured"
    data["recipe"]["steps"][0]["providerRef"] = "not-configured"
    recipe_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    _write_recipe_config(config_path, "generation.config.yaml")
    _write_generation_config(generation_path)

    plan = plan_recipe_run(
        recipe_path,
        config_path=config_path,
        project_root=tmp_path,
    )

    assert plan["providers"] == [
        {
            "ref": "not-configured",
            "model": "claude-sonnet-4-5",
            "type": None,
            "readiness": "unknown-provider",
            "missingEnv": [],
            "source": None,
        }
    ]


def test_plan_recipe_run_reports_local_provider_ready(tmp_path: Path) -> None:
    """Test local providers do not require API-key environment variables."""
    recipe_path = tmp_path / "recipe.yaml"
    config_path = tmp_path / "recipes.config.yaml"
    generation_path = tmp_path / "generation.config.yaml"
    _write_recipe(recipe_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    data["recipe"]["execution"]["providerRef"] = "configured-local"
    data["recipe"]["steps"][0]["providerRef"] = "configured-local"
    recipe_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    _write_recipe_config(config_path, "generation.config.yaml")
    _write_generation_config(generation_path)

    plan = plan_recipe_run(
        recipe_path,
        config_path=config_path,
        project_root=tmp_path,
    )

    assert plan["providers"][0]["type"] == "ollama"
    assert plan["providers"][0]["readiness"] == "ready"
    assert plan["providers"][0]["missingEnv"] == []


def test_execute_recipe_run_runs_deterministic_validate_and_writes_manifest(
    tmp_path: Path,
) -> None:
    """Test execute mode runs deterministic steps and records an audit manifest."""
    recipe_path = tmp_path / "recipe.yaml"
    catalog_path = tmp_path / "catalog.yaml"
    _write_validate_recipe(recipe_path)
    _write_catalog(catalog_path)

    result = execute_recipe_run(recipe_path, project_root=tmp_path)

    assert result["mode"] == "execute"
    assert result["status"] == "passed"
    assert result["exitCode"] == 0
    assert result["canRun"] is True
    assert result["manifest"]["path"].startswith(".odp/runs/odpr-")
    assert result["steps"][0]["status"] == "passed"
    assert result["steps"][0]["summary"]["spec"] == "odpc"
    manifest_path = tmp_path / result["manifest"]["path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["runId"] == result["runId"]
    assert manifest["steps"][0]["id"] == "validate-catalog"
    assert manifest["steps"][0]["review"] == {"status": "not-required", "reasons": []}


def test_execute_recipe_run_blocks_llm_backed_steps(tmp_path: Path) -> None:
    """Test execute mode refuses LLM-backed steps until execution is supported."""
    recipe_path = tmp_path / "recipe.yaml"
    workspace = tmp_path / "generated" / "portfolio"
    workspace.mkdir(parents=True)
    _write_recipe(recipe_path)

    result = execute_recipe_run(recipe_path, project_root=tmp_path)

    assert result["status"] == "blocked"
    assert result["exitCode"] == 1
    assert result["canRun"] is False
    assert result["steps"][0]["status"] == "blocked"
    assert any(
        reason["code"] == "llm_execution_not_supported"
        for reason in result["blockingReasons"]
    )


def test_execute_recipe_run_blocks_portfolio_sync_outside_allow_writes(
    tmp_path: Path,
) -> None:
    """Test state-changing deterministic steps honor configured write roots."""
    recipe_path = tmp_path / "recipe.yaml"
    config_path = tmp_path / "recipes.config.yaml"
    _write_portfolio_sync_recipe(recipe_path)
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

    plan = plan_recipe_run(
        recipe_path,
        config_path=config_path,
        project_root=tmp_path,
    )
    result = execute_recipe_run(
        recipe_path,
        config_path=config_path,
        project_root=tmp_path,
    )

    assert plan["canRun"] is False
    assert plan["steps"][0]["plannedWrites"] == [
        {"path": "portfolio/", "allowed": False}
    ]
    assert result["status"] == "blocked"
    assert result["steps"][0]["status"] == "blocked"
    assert any(
        "planned write outside allowWrites" in reason["message"]
        for reason in result["blockingReasons"]
    )


def test_validate_recipe_config_checks_paths(tmp_path: Path) -> None:
    """Test recipes.config.yaml validation catches unsafe write roots."""
    recipes_dir = tmp_path / "recipes"
    recipes_dir.mkdir()
    config_path = tmp_path / "recipes.config.yaml"
    config_path.write_text(
        """
version: "1.0"
recipes:
  paths:
    - recipes/
providers:
  generationConfig: generation.config.yaml
  defaultProviderRef: claude
execution:
  manifestDir: .odp/runs/
  allowWrites:
    - generated/
    - ../outside
""",
        encoding="utf-8",
    )

    report = validate_recipe_config(config_path)

    assert report["valid"] is False
    assert "execution.allowWrites[1] must be project-relative" in report["errors"]
    assert (
        "providers.generationConfig does not exist: generation.config.yaml"
        in report["warnings"]
    )


def test_load_recipe_exposes_metadata(tmp_path: Path) -> None:
    """Test loader returns a typed metadata summary."""
    recipe_path = tmp_path / "recipe.yaml"
    _write_recipe(recipe_path)

    recipe = load_recipe(recipe_path)

    assert recipe.path == recipe_path
    assert recipe.id == "RCP-LOCALIZE-001"
    assert recipe.name == {"en": "Localize Portfolio"}
    assert recipe.commands == ["portfolio.localize"]


def test_validate_odpr_document_accepts_provider_profile(tmp_path: Path) -> None:
    """Test ODPR validation accepts provider documents."""
    provider_path = tmp_path / "provider.yaml"
    provider_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Provider
provider:
  id: production-quality
  provider: openai
  model: gpt-4.1
  credentialsRef: env:OPENAI_API_KEY
""",
        encoding="utf-8",
    )

    report = validate_odpr_document(provider_path)

    assert report["valid"] is True
    assert report["kind"] == "Provider"
    assert report["errors"] == []


def test_validate_odpr_document_rejects_embedded_provider_secret(
    tmp_path: Path,
) -> None:
    """Test raw provider secrets are rejected."""
    provider_path = tmp_path / "provider.yaml"
    provider_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Provider
provider:
  id: unsafe
  provider: openai
  apiKey: sk-test-secret-value
""",
        encoding="utf-8",
    )

    report = validate_odpr_document(provider_path)

    assert report["valid"] is False
    assert any("provider.apiKey" in error for error in report["errors"])
    assert any("secret-like value" in error for error in report["errors"])


def test_validate_odpr_document_rejects_runtime_root_kind(tmp_path: Path) -> None:
    """Test runtime artifacts are not accepted as ODPR v1 root kinds."""
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: RecipeRunPlan
plan:
  canRun: true
""",
        encoding="utf-8",
    )

    report = validate_odpr_document(plan_path)

    assert report["valid"] is False
    assert "RecipeRunPlan is not an ODPR v1 root kind" in report["errors"]


def test_validate_odpr_document_rejects_runtime_fields_in_catalog(
    tmp_path: Path,
) -> None:
    """Test RecipeCatalog stays metadata-only."""
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        """
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: RecipeCatalog
recipeCatalog:
  metadata:
    id: RCP-CATALOG-001
    name:
      en: Catalog
  recipes:
    - path: recipes/release.yaml
      id: RCP-RELEASE-001
      version: "1.0.0"
      type: release
      name:
        en: Release
      runId: 20260619T120000Z
      plannedWrites: []
""",
        encoding="utf-8",
    )

    report = validate_odpr_document(catalog_path)

    assert report["valid"] is False
    assert (
        "recipeCatalog.recipes[0].plannedWrites must not be included"
        in report["errors"]
    )
    assert "recipeCatalog.recipes[0].runId must not be included" in report["errors"]


def test_build_recipe_catalog_is_metadata_only(tmp_path: Path) -> None:
    """Test project recipes can be rendered as a standard RecipeCatalog."""
    recipes_dir = tmp_path / "recipes"
    recipes_dir.mkdir()
    recipe_path = recipes_dir / "release.yaml"
    _write_recipe(recipe_path)
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

    catalog = build_recipe_catalog(config_path=config_path)

    assert catalog["kind"] == "RecipeCatalog"
    entry = catalog["recipeCatalog"]["recipes"][0]
    assert entry["path"] == "recipes/release.yaml"
    assert entry["commands"] == ["portfolio.localize"]
    assert "steps" not in entry
    assert "plannedWrites" not in entry
    assert "parseStatus" not in entry
