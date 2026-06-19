"""Recipe workflow loading, validation, and execution planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

import yaml

from .validation import load_odpr_data, validate_odpr_document

PathLike = Union[str, Path]
DEFAULT_RECIPE_CONFIG = Path(__file__).resolve().parent / "recipes.config.yaml"
ODPR_SCHEMA_URI = "https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml"


LLM_BACKED_COMMANDS = {
    "generate",
    "odpg.build",
    "portfolio.build",
    "portfolio.refresh",
    "portfolio.localize",
}
DETERMINISTIC_COMMANDS = {
    "odpc.build",
    "odpg.render",
    "portfolio.sync",
    "portfolio.render",
    "validate",
}
REPORT_COMMANDS = {
    "portfolio.explain",
    "explain",
}
SUPPORTED_COMMANDS = LLM_BACKED_COMMANDS | DETERMINISTIC_COMMANDS | REPORT_COMMANDS

COMMAND_REQUIRED_WITH: Dict[str, Sequence[str]] = {
    "generate": ("input", "kind", "output"),
    "odpc.build": ("input", "output"),
    "odpg.build": ("input", "output"),
    "odpg.render": ("graph", "output"),
    "portfolio.build": (),
    "portfolio.refresh": ("workspace",),
    "portfolio.sync": ("workspace",),
    "portfolio.localize": ("workspace", "languages"),
    "portfolio.render": ("workspace",),
    "portfolio.explain": ("workspace",),
    "validate": ("document",),
    "explain": ("document",),
}


@dataclass(frozen=True)
class RecipeDocument:
    """Loaded ODPR recipe with metadata used by the runner."""

    path: Path
    data: Mapping[str, object]
    id: str
    version: str
    type: str
    name: object
    steps: Sequence[Mapping[str, object]]
    commands: Sequence[str]


def load_recipe(path: PathLike) -> RecipeDocument:
    """Load one recipe YAML file."""
    recipe_path = Path(path)
    data = _load_yaml_mapping(recipe_path, "Recipe")
    recipe = _mapping(data.get("recipe"))
    metadata = _mapping(recipe.get("metadata"))
    steps = _steps(recipe.get("steps"))
    commands = [
        str(step.get("command"))
        for step in steps
        if isinstance(step.get("command"), str)
    ]
    return RecipeDocument(
        path=recipe_path,
        data=data,
        id=str(metadata.get("id", "")),
        version=str(recipe.get("version", "")),
        type=str(recipe.get("type", "")),
        name=metadata.get("name", ""),
        steps=steps,
        commands=commands,
    )


def validate_recipe(
    path: Optional[PathLike] = None,
    *,
    config_path: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
) -> Dict[str, object]:
    """Validate one recipe without executing steps."""
    config = _load_optional_recipe_config(config_path)
    recipe_path, recipe_selection = _resolve_recipe_path(
        path,
        config_path,
        project_root,
        config,
    )
    base_report = validate_odpr_document(recipe_path)
    errors: List[str] = list(base_report["errors"])
    warnings: List[str] = list(base_report["warnings"])
    data: Mapping[str, object] = {}
    recipe: Mapping[str, object] = {}
    metadata: Mapping[str, object] = {}
    steps: Sequence[Mapping[str, object]] = []

    if base_report.get("kind") == "Recipe":
        try:
            data = load_odpr_data(recipe_path)
        except (FileNotFoundError, ValueError) as exc:
            errors.append(str(exc))
        recipe = _mapping(data.get("recipe"))
        metadata = _mapping(recipe.get("metadata"))
        steps = _steps(recipe.get("steps"))
        _validate_steps(steps, errors, warnings)
    elif base_report.get("kind") is not None:
        errors.append("kind must be Recipe")

    return {
        "mode": "validate",
        "recipeSelection": recipe_selection,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "schemaValidation": base_report.get("schemaValidation"),
        "recipe": _recipe_summary(recipe_path, metadata, recipe),
        "steps": [_step_summary(step) for step in steps],
    }


def validate_recipe_config(path: PathLike) -> Dict[str, object]:
    """Validate recipes.config.yaml without contacting providers."""
    config_path = Path(path)
    errors: List[str] = []
    warnings: List[str] = []
    try:
        config = _load_yaml_mapping(config_path, "Recipe config")
    except (FileNotFoundError, ValueError) as exc:
        return {
            "domain": "recipes",
            "config_path": str(config_path),
            "valid": False,
            "errors": [str(exc)],
            "warnings": [],
        }

    allowed_top = {
        "version",
        "projectRoot",
        "recipes",
        "providers",
        "execution",
        "outputs",
        "gui",
    }
    for key in config:
        if key not in allowed_top:
            errors.append(f"Unknown top-level recipes config key: {key}")
    project_root_value = config.get("projectRoot")
    if project_root_value is not None and not isinstance(project_root_value, str):
        errors.append("projectRoot must be a string")
    root = _project_root(None, config_path, None, config)

    recipes = _mapping(config.get("recipes"))
    paths = recipes.get("paths")
    if paths is not None and not isinstance(paths, list):
        errors.append("recipes.paths must be a list")
    elif isinstance(paths, list):
        for index, value in enumerate(paths):
            if not isinstance(value, str):
                errors.append(f"recipes.paths[{index}] must be a string")
                continue
            if _is_unsafe_relative_path(value):
                errors.append(f"recipes.paths[{index}] must be project-relative")

    providers = _mapping(config.get("providers"))
    generation_config = providers.get("generationConfig")
    if generation_config is not None:
        if not isinstance(generation_config, str):
            errors.append("providers.generationConfig must be a string")
        elif not _generation_config_exists(config_path, generation_config, root):
            warnings.append(
                f"providers.generationConfig does not exist: {generation_config}"
            )
    default_provider = providers.get("defaultProviderRef")
    if default_provider is not None and not isinstance(default_provider, str):
        errors.append("providers.defaultProviderRef must be a string")

    execution = _mapping(config.get("execution"))
    _validate_config_path(
        execution.get("manifestDir"),
        "execution.manifestDir",
        errors,
    )
    allow_writes = execution.get("allowWrites")
    if allow_writes is not None and not isinstance(allow_writes, list):
        errors.append("execution.allowWrites must be a list")
    elif isinstance(allow_writes, list):
        for index, value in enumerate(allow_writes):
            _validate_config_path(
                value,
                f"execution.allowWrites[{index}]",
                errors,
            )

    return {
        "domain": "recipes",
        "config_path": str(config_path),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def get_recipe_config_path() -> Path:
    """Return the bundled recipe runner config template path."""
    return DEFAULT_RECIPE_CONFIG


def get_recipe_config(config_path: Optional[PathLike] = None) -> Dict[str, object]:
    """Return a safe recipe runner config summary."""
    source_path = Path(config_path) if config_path else DEFAULT_RECIPE_CONFIG
    config = _load_yaml_mapping(source_path, "Recipe config")
    recipes = _mapping(config.get("recipes"))
    providers = _mapping(config.get("providers"))
    execution = _mapping(config.get("execution"))
    return {
        "domain": "recipes",
        "template_path": str(DEFAULT_RECIPE_CONFIG),
        "config_path": str(source_path),
        "projectRoot": config.get("projectRoot"),
        "editable": config_path is not None,
        "copy_hint": (
            "Copy this template to your project, edit recipe paths and write "
            "policy, then pass it with `open-data-products recipe --config <path>`."
        ),
        "recipes": {
            "paths": recipes.get("paths", []),
            "defaultRecipe": recipes.get("defaultRecipe"),
        },
        "providers": {
            "generationConfig": providers.get("generationConfig"),
            "defaultProviderRef": providers.get("defaultProviderRef"),
        },
        "execution": {
            "manifestDir": execution.get("manifestDir"),
            "allowWrites": execution.get("allowWrites", []),
            "requireReviewFor": execution.get("requireReviewFor", []),
            "stopOnWarning": execution.get("stopOnWarning", False),
        },
    }


def print_recipe_config(config_path: Optional[PathLike] = None) -> str:
    """Return raw recipe runner config YAML."""
    source_path = Path(config_path) if config_path else DEFAULT_RECIPE_CONFIG
    if not source_path.is_file():
        raise FileNotFoundError(f"Recipe config not found: {source_path}")
    return source_path.read_text(encoding="utf-8")


def copy_recipe_config_template(
    destination: PathLike,
    *,
    overwrite: bool = False,
) -> Path:
    """Copy the bundled recipe runner config template to a project file."""
    target = Path(destination)
    destination_text = str(destination)
    if target.is_dir() or destination_text.endswith(("/", "\\")):
        target = target / DEFAULT_RECIPE_CONFIG.name
    if target.exists() and not overwrite:
        raise FileExistsError(f"Config file already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DEFAULT_RECIPE_CONFIG, target)
    return target


def plan_recipe_run(
    path: Optional[PathLike] = None,
    *,
    mode: str = "dry-run",
    config_path: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
    provider_ref: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, object]:
    """Return an agent-facing recipe run plan without executing steps."""
    config = _load_optional_recipe_config(config_path)
    recipe_path, recipe_selection = _resolve_recipe_path(
        path,
        config_path,
        project_root,
        config,
    )
    validation = validate_recipe(recipe_path)
    recipe_doc = load_recipe(recipe_path) if validation["valid"] else None
    root = _project_root(recipe_path, config_path, project_root, config)
    allow_writes = _allow_write_roots(config)
    steps = []
    blocking = list(validation["errors"])
    warnings = list(validation["warnings"])

    if recipe_doc is not None:
        recipe = _mapping(recipe_doc.data.get("recipe"))
        execution = _mapping(recipe.get("execution"))
        for step in recipe_doc.steps:
            planned = _planned_step(
                step,
                recipe,
                root,
                allow_writes,
                execution,
                config,
                provider_ref,
                model,
            )
            steps.append(planned)
            for planned_write in planned["plannedWrites"]:
                if isinstance(planned_write, dict) and not planned_write["allowed"]:
                    blocking.append(
                        f"{planned['id']} planned write outside allowWrites: "
                        f"{planned_write['path']}"
                    )

    can_run = not blocking
    payload: Dict[str, object] = {
        "mode": mode,
        "recipeSelection": recipe_selection,
        "recipe": validation["recipe"],
        "canRun": can_run,
        "blockingReasons": [
            {"code": "validation_failed", "message": reason, "blocking": True}
            for reason in blocking
        ],
        "warnings": warnings,
        "config": {
            "recipeConfig": str(config_path) if config_path else None,
            "generationConfig": _generation_config(config),
        },
        "providers": _provider_readiness(steps, config, config_path, root),
        "steps": steps,
    }
    if mode == "execute":
        payload["status"] = "unsupported"
        payload["blockingReasons"].append(
            {
                "code": "unsupported_step",
                "message": "Recipe execution is not implemented yet; use --dry-run.",
                "blocking": True,
            }
        )
        payload["canRun"] = False
    return payload


def execute_recipe_run(
    path: Optional[PathLike] = None,
    *,
    config_path: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
    provider_ref: Optional[str] = None,
    model: Optional[str] = None,
    allow_llm: bool = False,
    approve_review: bool = False,
) -> Dict[str, object]:
    """Execute deterministic and report-only recipe steps with a run manifest."""
    config = _load_optional_recipe_config(config_path)
    recipe_path, recipe_selection = _resolve_recipe_path(
        path,
        config_path,
        project_root,
        config,
    )
    root = _project_root(recipe_path, config_path, project_root, config)
    run_id = _run_id()
    plan = plan_recipe_run(
        recipe_path,
        mode="dry-run",
        config_path=config_path,
        project_root=root,
        provider_ref=provider_ref,
        model=model,
    )
    plan["mode"] = "execute"
    blocking = list(plan["blockingReasons"])
    execution_policy = {
        "allowLlm": allow_llm,
        "reviewApproved": approve_review,
    }
    for issue in _execution_config_issues(config_path):
        blocking.append({"code": "config_invalid", "message": issue, "blocking": True})
    for step in plan["steps"]:
        if not isinstance(step, dict):
            continue
        if step.get("classification") == "llm-backed" and not allow_llm:
            blocking.append(
                {
                    "code": "llm_execution_requires_allow_llm",
                    "message": (
                        f"{step.get('id', '')} uses {step.get('command', '')}; "
                        "rerun with --allow-llm to permit provider calls."
                    ),
                    "blocking": True,
                }
            )
    if allow_llm:
        for provider in plan["providers"]:
            if not isinstance(provider, dict):
                continue
            if provider.get("readiness") != "ready":
                blocking.append(
                    {
                        "code": "provider_not_ready",
                        "message": (
                            f"Provider {provider.get('ref', '')} is "
                            f"{provider.get('readiness', 'not ready')}."
                        ),
                        "blocking": True,
                    }
                )
    for step in plan["steps"]:
        if not isinstance(step, dict):
            continue
        review = _mapping(step.get("review"))
        if review.get("status") == "review-needed" and not approve_review:
            blocking.append(
                {
                    "code": "review_approval_required",
                    "message": (
                        f"{step.get('id', '')} requires review approval; "
                        "rerun with --approve-review after approval."
                    ),
                    "blocking": True,
                }
            )

    started_at = _utc_now()
    step_results: List[Dict[str, object]] = []
    status = "blocked"
    exit_code = 1
    if not blocking:
        status = "passed"
        exit_code = 0
        for step in plan["steps"]:
            if not isinstance(step, dict):
                continue
            execution_step = _execution_step(step, approve_review)
            result = _execute_step(
                execution_step,
                root,
                _execution_generation_config(plan, root),
            )
            step_results.append(result)
            if result["status"] == "failed":
                status = "failed"
                exit_code = 1
                break
    else:
        step_results = [
            _blocked_step(_execution_step(step, approve_review))
            for step in plan["steps"]
            if isinstance(step, dict)
        ]

    completed_at = _utc_now()
    manifest_payload = {
        "runId": run_id,
        "mode": "execute",
        "status": status,
        "exitCode": exit_code,
        "startedAt": started_at,
        "completedAt": completed_at,
        "recipeSelection": recipe_selection,
        "executionPolicy": execution_policy,
        "recipe": plan["recipe"],
        "config": plan["config"],
        "blockingReasons": blocking,
        "warnings": plan["warnings"],
        "steps": step_results,
    }
    manifest_path = _write_run_manifest(root, config, run_id, manifest_payload)
    return {
        "mode": "execute",
        "recipeSelection": recipe_selection,
        "executionPolicy": execution_policy,
        "runId": run_id,
        "status": status,
        "exitCode": exit_code,
        "canRun": not blocking,
        "recipe": plan["recipe"],
        "blockingReasons": blocking,
        "warnings": plan["warnings"],
        "manifest": {"path": _relative_path(manifest_path, root)},
        "steps": step_results,
    }


def list_recipes(
    *,
    config_path: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
) -> Dict[str, object]:
    """Return a RecipeCatalog-style listing for configured recipe paths."""
    config = _load_optional_recipe_config(config_path)
    root = _project_root(None, config_path, project_root, config)
    search_paths = _recipe_search_paths(config) or [Path("recipes")]
    recipes: List[Dict[str, object]] = []
    warnings: List[str] = []
    for search_path in search_paths:
        base = root / search_path
        if not base.exists():
            warnings.append(f"recipe path does not exist: {search_path}")
            continue
        paths = [base] if base.is_file() else sorted(base.glob("*.yaml"))
        for recipe_path in paths:
            report = validate_recipe(recipe_path)
            summary = dict(report["recipe"])
            summary["path"] = _relative_path(recipe_path, root)
            summary["parseStatus"] = "passed" if report["valid"] else "failed"
            summary["warnings"] = report["warnings"]
            summary["commands"] = [
                step.get("command")
                for step in report["steps"]
                if isinstance(step, dict) and isinstance(step.get("command"), str)
            ]
            recipes.append(summary)
    return {
        "mode": "list",
        "kind": "RecipeCatalog",
        "recipeCatalog": {"recipes": recipes},
        "warnings": warnings,
    }


def build_recipe_catalog(
    *,
    config_path: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
    catalog_id: str = "RCP-CATALOG-001",
    name: Optional[Mapping[str, object]] = None,
    description: Optional[Mapping[str, object]] = None,
) -> Dict[str, object]:
    """Build a metadata-only ODPR RecipeCatalog from configured recipe files."""
    listing = list_recipes(config_path=config_path, project_root=project_root)
    listing_catalog = _mapping(listing.get("recipeCatalog"))
    entries = listing_catalog.get("recipes")
    recipes = [
        _catalog_entry(entry)
        for entry in entries
        if isinstance(entry, dict) and entry.get("parseStatus") == "passed"
    ]
    metadata: Dict[str, object] = {
        "id": catalog_id,
        "name": name or {"en": "ODPR Recipe Catalog"},
    }
    if description is not None:
        metadata["description"] = description
    return {
        "schema": ODPR_SCHEMA_URI,
        "version": "1.0",
        "kind": "RecipeCatalog",
        "recipeCatalog": {
            "metadata": metadata,
            "recipes": recipes,
        },
    }


def write_recipe_catalog(
    output: PathLike,
    *,
    config_path: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
) -> Path:
    """Write a metadata-only ODPR RecipeCatalog YAML file."""
    output_path = Path(output)
    catalog = build_recipe_catalog(config_path=config_path, project_root=project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_dump_yaml(catalog), encoding="utf-8")
    return output_path


def _catalog_entry(entry: Mapping[str, object]) -> Dict[str, object]:
    allowed = (
        "path",
        "id",
        "version",
        "type",
        "name",
        "description",
        "tags",
        "environment",
        "executionMode",
        "providerRef",
        "contextFormat",
        "requiresReview",
        "commands",
    )
    return {key: entry[key] for key in allowed if key in entry and entry[key] != []}


def _dump_yaml(data: Mapping[str, object]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=False)


def _planned_step(
    step: Mapping[str, object],
    recipe: Mapping[str, object],
    root: Path,
    allow_writes: Sequence[Path],
    execution: Mapping[str, object],
    config: Mapping[str, object],
    provider_ref: Optional[str],
    model: Optional[str],
) -> Dict[str, object]:
    command = str(step.get("command", ""))
    with_values = dict(_mapping(step.get("with")))
    resolved_parameters = dict(with_values)
    resolved_provider = (
        provider_ref
        or _string(step.get("providerRef"))
        or _string(execution.get("providerRef"))
        or _default_provider(config)
    )
    resolved_model = model or _string(step.get("model"))
    classification = _classify_command(command)
    if classification == "llm-backed":
        if resolved_provider:
            resolved_parameters["providerRef"] = resolved_provider
        if resolved_model:
            resolved_parameters["model"] = resolved_model
    return {
        "id": step.get("id", ""),
        "command": command,
        "classification": classification,
        "resolved": {
            "action": command,
            "parameters": resolved_parameters,
        },
        "inputs": _step_inputs(command, with_values, root),
        "plannedWrites": _planned_writes(command, with_values, root, allow_writes),
        "review": _review_status(classification, recipe, config),
    }


def _validate_steps(
    steps: Sequence[Mapping[str, object]],
    errors: List[str],
    warnings: List[str],
) -> None:
    seen_ids = set()
    for index, step in enumerate(steps):
        prefix = f"steps[{index}]"
        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id:
            errors.append(f"{prefix}.id is required")
        elif step_id in seen_ids:
            errors.append(f"{prefix}.id must be unique")
        seen_ids.add(step_id)
        command = step.get("command")
        if not isinstance(command, str) or not command:
            errors.append(f"{prefix}.command is required")
            continue
        if command not in SUPPORTED_COMMANDS:
            errors.append(f"{prefix}.command is unsupported: {command}")
            continue
        if command in DETERMINISTIC_COMMANDS:
            if "providerRef" in step:
                errors.append(
                    f"{prefix}.providerRef is only valid for LLM-backed commands"
                )
            if "model" in step:
                errors.append(f"{prefix}.model is only valid for LLM-backed commands")
        with_values = _mapping(step.get("with"))
        for required in COMMAND_REQUIRED_WITH[command]:
            if required not in with_values:
                errors.append(f"{prefix}.with.{required} is required")
        if command == "portfolio.build" and not _has_portfolio_source(with_values):
            errors.append(
                f"{prefix}.with must include one of objectives, useCases, "
                "signals, or products"
            )
        if command == "portfolio.build" and not (
            "output" in with_values or "workspace" in with_values
        ):
            errors.append(f"{prefix}.with must include output or workspace")
        if command == "portfolio.localize":
            languages = with_values.get("languages")
            if isinstance(languages, str):
                warnings.append(
                    f"{prefix}.with.languages should be a YAML list, not a string"
                )
            elif not _string_sequence(languages):
                errors.append(f"{prefix}.with.languages must be a list of strings")


def _step_summary(step: Mapping[str, object]) -> Dict[str, object]:
    command = step.get("command")
    return {
        "id": step.get("id", ""),
        "command": command,
        "classification": _classify_command(
            command if isinstance(command, str) else ""
        ),
    }


def _recipe_summary(
    path: Path,
    metadata: Mapping[str, object],
    recipe: Mapping[str, object],
) -> Dict[str, object]:
    summary: Dict[str, object] = {
        "path": str(path),
        "id": metadata.get("id", ""),
        "version": recipe.get("version", ""),
        "type": recipe.get("type", ""),
        "name": metadata.get("name", ""),
    }
    optional_fields = (
        ("description", metadata.get("description")),
        ("tags", metadata.get("tags")),
        ("environment", recipe.get("environment")),
        ("executionMode", _mapping(recipe.get("execution")).get("mode")),
        ("providerRef", _mapping(recipe.get("execution")).get("providerRef")),
        ("contextFormat", _mapping(recipe.get("context")).get("format")),
        ("requiresReview", _mapping(recipe.get("review")).get("required")),
    )
    for key, value in optional_fields:
        if value is not None and value != []:
            summary[key] = value
    return summary


def _step_inputs(
    command: str,
    values: Mapping[str, object],
    root: Path,
) -> List[Dict[str, object]]:
    input_keys = {
        "generate": ("input",),
        "odpc.build": ("input",),
        "odpg.build": ("input", "contextGraph"),
        "odpg.render": ("graph",),
        "portfolio.build": (
            "workspace",
            "objectives",
            "useCases",
            "signals",
            "products",
        ),
        "portfolio.refresh": (
            "workspace",
            "objectives",
            "useCases",
            "signals",
            "products",
        ),
        "portfolio.sync": ("workspace",),
        "portfolio.localize": ("workspace",),
        "portfolio.render": ("workspace",),
        "portfolio.explain": ("workspace",),
        "validate": ("document",),
        "explain": ("document",),
    }
    inputs = []
    for key in input_keys.get(command, ()):
        value = values.get(key)
        if isinstance(value, str):
            inputs.append({"path": value, "exists": (root / value).exists()})
    return inputs


def _planned_writes(
    command: str,
    values: Mapping[str, object],
    root: Path,
    allow_writes: Sequence[Path],
) -> List[Dict[str, object]]:
    paths: List[str] = []
    if command in {"generate", "portfolio.build"}:
        _append_string(paths, values.get("output"))
    elif command in {"odpc.build", "odpg.build", "odpg.render"}:
        for key in ("output", "html", "toon", "gcf"):
            _append_string(paths, values.get(key))
    elif command == "portfolio.localize":
        workspace = values.get("workspace")
        languages = values.get("languages")
        if isinstance(workspace, str):
            workspace_root = workspace.rstrip("/")
            paths.append(f"{workspace_root}/portfolio-i18n.yaml")
            paths.append(f"{workspace_root}/index.html")
            for language in _language_list(languages):
                paths.append(f"{workspace_root}/index.{language}.html")
    elif command == "portfolio.sync":
        _append_string(paths, values.get("workspace"))
    elif command == "portfolio.render":
        output = values.get("output")
        workspace = values.get("workspace")
        if isinstance(output, str):
            paths.append(output)
        elif isinstance(workspace, str):
            paths.append(f"{workspace.rstrip('/')}/index.html")
    return [
        {"path": path, "allowed": _write_allowed(path, root, allow_writes)}
        for path in paths
    ]


def _load_optional_recipe_config(
    config_path: Optional[PathLike],
) -> Mapping[str, object]:
    if config_path is None:
        return {}
    try:
        return _load_yaml_mapping(Path(config_path), "Recipe config")
    except (FileNotFoundError, ValueError):
        return {}


def _resolve_recipe_path(
    path: Optional[PathLike],
    config_path: Optional[PathLike],
    project_root: Optional[PathLike],
    config: Mapping[str, object],
) -> Tuple[Path, Dict[str, Optional[str]]]:
    default_recipe = _default_recipe(config)
    if path is not None:
        recipe_path = Path(path)
        return recipe_path, {
            "source": "argument",
            "path": str(path),
            "defaultRecipe": default_recipe,
        }
    if not default_recipe:
        raise ValueError(
            "recipe path is required unless recipes.defaultRecipe is set in "
            "recipes.config.yaml"
        )
    root = _project_root(None, config_path, project_root, config)
    return root / default_recipe, {
        "source": "config-default",
        "path": default_recipe,
        "defaultRecipe": default_recipe,
    }


def _default_recipe(config: Mapping[str, object]) -> Optional[str]:
    recipes = _mapping(config.get("recipes"))
    return _string(recipes.get("defaultRecipe"))


def _recipe_search_paths(config: Mapping[str, object]) -> Sequence[Path]:
    recipes = _mapping(config.get("recipes"))
    paths = recipes.get("paths")
    if not isinstance(paths, list):
        return []
    return [Path(value) for value in paths if isinstance(value, str)]


def _allow_write_roots(config: Mapping[str, object]) -> Sequence[Path]:
    execution = _mapping(config.get("execution"))
    allow_writes = execution.get("allowWrites")
    if not isinstance(allow_writes, list):
        return []
    return [Path(value) for value in allow_writes if isinstance(value, str)]


def _generation_config(config: Mapping[str, object]) -> Optional[str]:
    providers = _mapping(config.get("providers"))
    return _string(providers.get("generationConfig"))


def _default_provider(config: Mapping[str, object]) -> Optional[str]:
    providers = _mapping(config.get("providers"))
    return _string(providers.get("defaultProviderRef"))


def _generation_config_exists(
    config_path: Path,
    generation_config: str,
    root: Path,
) -> bool:
    source_path = Path(generation_config)
    if not source_path.is_absolute():
        source_path = root / source_path
    if source_path.is_file():
        return True
    if (
        config_path == DEFAULT_RECIPE_CONFIG
        and generation_config == "generation.config.yaml"
    ):
        return (config_path.parent.parent / "generation" / generation_config).is_file()
    return False


def _provider_readiness(
    steps: Sequence[Mapping[str, object]],
    config: Mapping[str, object],
    config_path: Optional[PathLike],
    root: Path,
) -> List[Dict[str, object]]:
    providers_config, providers_source = _generation_providers(
        config, config_path, root
    )
    providers: Dict[str, Dict[str, object]] = {}
    for step in steps:
        resolved = _mapping(step.get("resolved"))
        parameters = _mapping(resolved.get("parameters"))
        provider = _string(parameters.get("providerRef"))
        if not provider:
            continue
        provider_config = _mapping(providers_config.get(provider))
        source = str(providers_source) if provider_config else "built-in"
        if not provider_config:
            provider_config = _built_in_provider(provider)
        if not provider_config:
            providers[provider] = {
                "ref": provider,
                "model": parameters.get("model"),
                "type": None,
                "readiness": "unknown-provider",
                "missingEnv": [],
                "source": None,
            }
            continue
        api_key_env = _string(provider_config.get("apiKeyEnv"))
        missing_env = []
        if api_key_env and not os.environ.get(api_key_env):
            missing_env.append(api_key_env)
        providers[provider] = {
            "ref": provider,
            "model": parameters.get("model") or provider_config.get("model"),
            "type": provider_config.get("type"),
            "readiness": "missing-env" if missing_env else "ready",
            "missingEnv": missing_env,
            "source": source,
        }
    return list(providers.values())


def _generation_providers(
    config: Mapping[str, object],
    config_path: Optional[PathLike],
    root: Path,
) -> Tuple[Mapping[str, object], Optional[Path]]:
    generation_config = _generation_config(config)
    if not generation_config:
        return {}, None
    source_path = Path(generation_config)
    if not source_path.is_absolute():
        source_path = root / source_path
    try:
        from ..generation import load_generation_config

        generation = load_generation_config(source_path)
    except (FileNotFoundError, ValueError):
        return {}, source_path
    providers = generation.get("providers")
    return (_mapping(providers), source_path)


def _built_in_provider(provider: str) -> Mapping[str, object]:
    try:
        from ..generation import BUILT_IN_PROVIDERS
    except ImportError:
        return {}
    return _mapping(BUILT_IN_PROVIDERS.get(provider))


def _review_status(
    classification: str,
    recipe: Mapping[str, object],
    config: Mapping[str, object],
) -> Dict[str, object]:
    reasons = []
    review = _mapping(recipe.get("review"))
    if review.get("required") is True:
        reasons.append(
            {
                "code": "recipe_review_required",
                "message": "Recipe declares review.required: true.",
            }
        )
    recipe_type = _string(recipe.get("type"))
    require_review_for = _require_review_for(config)
    if recipe_type and recipe_type in require_review_for:
        reasons.append(
            {
                "code": "recipe_type_requires_review",
                "message": f"Recipe type requires review: {recipe_type}",
            }
        )
    if classification == "llm-backed":
        reasons.append(
            {
                "code": "llm_backed_step",
                "message": "LLM-backed steps require review before execution.",
            }
        )
    if reasons:
        return {"status": "review-needed", "reasons": reasons}
    return {"status": "not-required", "reasons": []}


def _require_review_for(config: Mapping[str, object]) -> Sequence[str]:
    execution = _mapping(config.get("execution"))
    value = execution.get("requireReviewFor")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _execution_config_issues(config_path: Optional[PathLike]) -> List[str]:
    if config_path is None:
        return []
    report = validate_recipe_config(config_path)
    return list(report["errors"])


def _execution_generation_config(
    plan: Mapping[str, object],
    root: Path,
) -> Optional[Path]:
    config = _mapping(plan.get("config"))
    generation_config = _string(config.get("generationConfig"))
    if not generation_config:
        return None
    path = Path(generation_config)
    if path.is_absolute():
        return path
    return root / path


def _execute_step(
    step: Mapping[str, object],
    root: Path,
    generation_config: Optional[Path] = None,
) -> Dict[str, object]:
    command = str(step.get("command", ""))
    parameters = _mapping(_mapping(step.get("resolved")).get("parameters"))
    started_at = _utc_now()
    try:
        if command == "validate":
            from ..agent import validate_document

            document = _required_path(parameters, "document", root)
            result = validate_document(document)
            payload = result.to_dict()
            return _step_result(
                step,
                "passed" if result.valid else "failed",
                started_at,
                issues=list(payload.get("errors", [])),
                summary={
                    "spec": payload.get("spec"),
                    "kind": payload.get("kind"),
                    "valid": payload.get("valid"),
                    "path": _relative_path(document, root),
                },
            )
        if command == "explain":
            from ..agent import explain_document

            document = _required_path(parameters, "document", root)
            explanation = explain_document(document)
            return _step_result(
                step,
                "passed",
                started_at,
                summary={
                    "path": _relative_path(document, root),
                    "format": "text",
                    "characterCount": len(explanation),
                },
            )
        if command == "odpg.render":
            from ..odpg import generate_graph_explorer

            graph = _required_path(parameters, "graph", root)
            output = _required_path(parameters, "output", root)
            output_path = generate_graph_explorer(graph, output)
            return _step_result(
                step,
                "passed",
                started_at,
                artifacts=[_relative_path(output_path, root)],
            )
        if command == "portfolio.sync":
            from ..portfolio import sync_portfolio

            workspace = _required_path(parameters, "workspace", root)
            result = sync_portfolio(workspace)
            return _portfolio_step_result(step, started_at, root, result)
        if command == "portfolio.render":
            from ..portfolio import render_portfolio

            workspace = _required_path(parameters, "workspace", root)
            output = _optional_path(parameters, "output", root)
            result = render_portfolio(workspace, output_path=output)
            return _portfolio_step_result(step, started_at, root, result)
        if command == "portfolio.localize":
            from ..generation import create_generation_client
            from ..generation import resolve_generation_settings
            from ..portfolio import localize_portfolio

            workspace = _required_path(parameters, "workspace", root)
            languages = _language_list(parameters.get("languages"))
            default_language = _string(parameters.get("defaultLanguage")) or "en"
            settings = resolve_generation_settings(
                config_path=generation_config,
                provider=_string(parameters.get("providerRef")),
                model=_string(parameters.get("model")),
            )
            client = create_generation_client(settings)
            result = localize_portfolio(
                workspace,
                languages=languages,
                default_language=default_language,
                client=client,
                model=settings.model,
            )
            return _portfolio_step_result(step, started_at, root, result)
        if command == "portfolio.explain":
            from ..portfolio import explain_portfolio

            workspace = _required_path(parameters, "workspace", root)
            result = explain_portfolio(workspace)
            return _step_result(
                step,
                "passed" if result.get("valid") is not False else "failed",
                started_at,
                issues=_portfolio_issues(result),
                summary={
                    "workspace": _relative_path(workspace, root),
                    "valid": result.get("valid"),
                    "productSpecCount": result.get("productSpecCount"),
                    "graphNodeCount": result.get("graphNodeCount"),
                    "graphEdgeCount": result.get("graphEdgeCount"),
                },
            )
    except (FileNotFoundError, ValueError, OSError) as exc:
        return _step_result(step, "failed", started_at, issues=[str(exc)])
    return _step_result(
        step,
        "failed",
        started_at,
        issues=[f"Execution is not implemented for command: {command}"],
    )


def _portfolio_step_result(
    step: Mapping[str, object],
    started_at: str,
    root: Path,
    result: Mapping[str, object],
) -> Dict[str, object]:
    artifacts = []
    for key in ("html", "snapshot"):
        value = result.get(key)
        if isinstance(value, str) and value:
            artifacts.append(_relative_path(Path(value), root))
    for key in ("created", "updated", "unchanged"):
        values = result.get(key)
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str):
                    artifacts.append(_relative_path(Path(value), root))
    return _step_result(
        step,
        "passed" if result.get("valid") is not False else "failed",
        started_at,
        artifacts=sorted(set(artifacts)),
        issues=_portfolio_issues(result),
        summary={
            "kind": result.get("kind"),
            "valid": result.get("valid"),
            "workspace": (
                _relative_path(Path(str(result.get("workspace", ""))), root)
                if result.get("workspace")
                else None
            ),
            "localizationQa": result.get("localizationQa"),
        },
    )


def _portfolio_issues(result: Mapping[str, object]) -> List[str]:
    issues: List[str] = []
    warnings = result.get("warnings")
    if isinstance(warnings, list):
        issues.extend(str(warning) for warning in warnings)
    validation_results = result.get("validationResults")
    if isinstance(validation_results, list):
        for item in validation_results:
            if isinstance(item, dict) and item.get("valid") is False:
                path = item.get("path", "portfolio artifact")
                errors = item.get("errors")
                if isinstance(errors, list):
                    issues.extend(f"{path}: {error}" for error in errors)
    return issues


def _blocked_step(step: Mapping[str, object]) -> Dict[str, object]:
    return {
        "id": step.get("id", ""),
        "command": step.get("command", ""),
        "classification": step.get("classification", ""),
        "status": "blocked",
        "review": step.get("review", {}),
        "artifacts": [],
        "issues": [],
    }


def _execution_step(
    step: Mapping[str, object],
    approve_review: bool,
) -> Dict[str, object]:
    execution_step = dict(step)
    review = _mapping(step.get("review"))
    if review.get("status") == "review-needed" and approve_review:
        review = dict(review)
        review["decision"] = "approved-by-cli-flag"
        execution_step["review"] = review
    return execution_step


def _step_result(
    step: Mapping[str, object],
    status: str,
    started_at: str,
    *,
    artifacts: Optional[Sequence[str]] = None,
    issues: Optional[Sequence[str]] = None,
    summary: Optional[Mapping[str, object]] = None,
) -> Dict[str, object]:
    artifact_paths = list(artifacts or [])
    write_check = _write_check(step, artifact_paths)
    result: Dict[str, object] = {
        "id": step.get("id", ""),
        "command": step.get("command", ""),
        "classification": step.get("classification", ""),
        "status": status,
        "review": step.get("review", {}),
        "startedAt": started_at,
        "completedAt": _utc_now(),
        "artifacts": artifact_paths,
        "issues": list(issues or []),
    }
    if summary is not None:
        result["summary"] = {
            key: value for key, value in summary.items() if value is not None
        }
    if write_check is not None:
        summary_value = result.setdefault("summary", {})
        if isinstance(summary_value, dict):
            summary_value["writeCheck"] = write_check
    return result


def _write_check(
    step: Mapping[str, object],
    artifacts: Sequence[str],
) -> Optional[Dict[str, object]]:
    planned = []
    planned_writes = step.get("plannedWrites")
    if isinstance(planned_writes, list):
        for item in planned_writes:
            if isinstance(item, dict) and item.get("allowed") is True:
                path = item.get("path")
                if isinstance(path, str) and path:
                    planned.append(path)
    artifact_paths = [path for path in artifacts if path]
    if not planned and not artifact_paths:
        return None
    planned_set = set(planned)
    artifact_set = set(artifact_paths)
    missing = sorted(planned_set - artifact_set)
    extra = sorted(artifact_set - planned_set)
    if missing and extra:
        status = "mismatch"
    elif missing:
        status = "missing"
    elif extra:
        status = "extra"
    else:
        status = "matched"
    return {
        "status": status,
        "planned": sorted(planned_set),
        "artifacts": sorted(artifact_set),
        "matched": sorted(planned_set & artifact_set),
        "missing": missing,
        "extra": extra,
    }


def _required_path(
    parameters: Mapping[str, object],
    key: str,
    root: Path,
) -> Path:
    value = parameters.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing required path parameter: {key}")
    return root / value


def _optional_path(
    parameters: Mapping[str, object],
    key: str,
    root: Path,
) -> Optional[Path]:
    value = parameters.get(key)
    if not isinstance(value, str) or not value:
        return None
    return root / value


def _write_run_manifest(
    root: Path,
    config: Mapping[str, object],
    run_id: str,
    payload: Mapping[str, object],
) -> Path:
    manifest_dir = _manifest_dir(config)
    output = root / manifest_dir / f"{run_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output


def _manifest_dir(config: Mapping[str, object]) -> Path:
    execution = _mapping(config.get("execution"))
    value = execution.get("manifestDir")
    if isinstance(value, str) and value:
        return Path(value)
    return Path(".odp") / "runs"


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("odpr-%Y%m%dT%H%M%SZ")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_yaml_mapping(path: Path, label: str) -> Mapping[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a YAML mapping.")
    return data


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _steps(value: object) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _classify_command(command: str) -> str:
    if command in LLM_BACKED_COMMANDS:
        return "llm-backed"
    if command in DETERMINISTIC_COMMANDS:
        return "deterministic"
    if command in REPORT_COMMANDS:
        return "report"
    return "unsupported"


def _string(value: object) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _string_sequence(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _language_list(value: object) -> Sequence[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if _string_sequence(value):
        return list(value)
    return []


def _append_string(paths: List[str], value: object) -> None:
    if isinstance(value, str):
        paths.append(value)


def _has_portfolio_source(values: Mapping[str, object]) -> bool:
    return any(
        key in values for key in ("objectives", "useCases", "signals", "products")
    )


def _validate_config_path(
    value: object,
    path: str,
    errors: List[str],
) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        errors.append(f"{path} must be a string")
        return
    if _is_unsafe_relative_path(value):
        errors.append(f"{path} must be project-relative")


def _is_unsafe_relative_path(value: str) -> bool:
    path = Path(value)
    return path.is_absolute() or ".." in path.parts


def _write_allowed(path: str, root: Path, allow_writes: Sequence[Path]) -> bool:
    if not allow_writes:
        return True
    target = (root / path).resolve()
    for allowed in allow_writes:
        allowed_root = (root / allowed).resolve()
        try:
            target.relative_to(allowed_root)
            return True
        except ValueError:
            continue
    return False


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _project_root(
    recipe_path: Optional[Path],
    config_path: Optional[PathLike],
    project_root: Optional[PathLike],
    config: Optional[Mapping[str, object]] = None,
) -> Path:
    if project_root is not None:
        return Path(project_root).resolve()
    if config is not None and config_path is not None:
        configured_root = _string(config.get("projectRoot"))
        if configured_root:
            root = Path(configured_root)
            if root.is_absolute():
                return root
            return (Path(config_path).parent / root).resolve()
    if config_path is not None:
        return Path(config_path).parent.resolve()
    if recipe_path is not None:
        return recipe_path.parent.resolve()
    return Path.cwd().resolve()
