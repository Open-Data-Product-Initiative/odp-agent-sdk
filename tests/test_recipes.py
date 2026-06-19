"""Tests for recipe workflow planning."""

from __future__ import annotations

from pathlib import Path
import yaml

from open_data_products.odpr import (
    build_recipe_catalog,
    load_odpr_schema,
    load_recipe,
    plan_recipe_run,
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
