"""Tests for recipe workflow planning."""

from __future__ import annotations

from pathlib import Path
import yaml

from open_data_products.odpr import (
    load_recipe,
    plan_recipe_run,
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
