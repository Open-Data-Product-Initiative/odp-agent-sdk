"""Recipe workflow loading, validation, and execution planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

import yaml

from .validation import load_odpr_data, validate_odpr_document

PathLike = Union[str, Path]
DEFAULT_RECIPE_CONFIG = Path(__file__).resolve().parent / "recipes.config.yaml"
DEFAULT_STARTER_CATALOG = (
    Path(__file__).resolve().parent / "data" / "starters" / "catalog.yaml"
)
ODPR_SCHEMA_URI = "https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml"
DEFAULT_RECIPE_CATALOG_VERSION = "1.0.0"
STARTER_GROUP_ID = "starters"


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
        "template_path": DEFAULT_RECIPE_CONFIG.as_posix(),
        "config_path": source_path.as_posix(),
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
    else:
        recipe = {}

    can_run = not blocking
    providers = _provider_readiness(steps, config, config_path, root)
    payload: Dict[str, object] = {
        "mode": mode,
        "dryRun": {
            "writes": False,
            "providerCalls": False,
        },
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
        "execution": _plan_execution_policy(recipe, config),
        "context": _plan_context_policy(recipe),
        "review": _plan_review_policy(recipe, steps),
        "gates": _plan_gates(recipe),
        "plannedReads": _plan_reads(steps),
        "plannedWrites": _plan_writes(steps),
        "requiredEnv": _plan_required_env(providers),
        "providers": providers,
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
    group: Optional[str] = None,
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
            if group:
                summary["groupRef"] = group
            recipes.append(summary)
    catalog: Dict[str, object] = {
        "version": DEFAULT_RECIPE_CATALOG_VERSION,
        "recipes": recipes,
    }
    if group:
        catalog["groups"] = [
            {
                "id": group,
                "name": _localized_text(group),
            }
        ]
    return {
        "mode": "list",
        "kind": "RecipeCatalog",
        "recipeCatalog": catalog,
        "warnings": warnings,
    }


def build_recipe_catalog(
    *,
    config_path: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
    catalog_id: str = "RCP-CATALOG-001",
    name: Optional[Mapping[str, object]] = None,
    description: Optional[Mapping[str, object]] = None,
    group: Optional[str] = None,
    group_name: Optional[Mapping[str, object]] = None,
    group_description: Optional[Mapping[str, object]] = None,
) -> Dict[str, object]:
    """Build a metadata-only ODPR RecipeCatalog from configured recipe files."""
    listing = list_recipes(
        config_path=config_path,
        project_root=project_root,
        group=group,
    )
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
    recipe_catalog: Dict[str, object] = {
        "metadata": metadata,
        "version": DEFAULT_RECIPE_CATALOG_VERSION,
        "recipes": recipes,
    }
    if group:
        group_entry: Dict[str, object] = {
            "id": group,
            "name": group_name or _localized_text(group),
        }
        if group_description is not None:
            group_entry["description"] = group_description
        recipe_catalog["groups"] = [group_entry]
    return {
        "schema": ODPR_SCHEMA_URI,
        "version": "1.0",
        "kind": "RecipeCatalog",
        "recipeCatalog": recipe_catalog,
    }


def write_recipe_catalog(
    output: PathLike,
    *,
    config_path: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
    group: Optional[str] = None,
) -> Path:
    """Write a metadata-only ODPR RecipeCatalog YAML file."""
    output_path = Path(output)
    catalog = build_recipe_catalog(
        config_path=config_path,
        project_root=project_root,
        group=group,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_dump_yaml(catalog), encoding="utf-8")
    return output_path


def load_recipe_catalog(catalog_path: Optional[PathLike] = None) -> Dict[str, object]:
    """Load an ODPR RecipeCatalog document."""
    path = Path(catalog_path) if catalog_path is not None else DEFAULT_STARTER_CATALOG
    data = dict(load_odpr_data(path))
    if data.get("kind") != "RecipeCatalog":
        raise ValueError(f"ODPR document is not a RecipeCatalog: {path}")
    return data


def list_starter_recipes(
    *,
    catalog_path: Optional[PathLike] = None,
) -> Dict[str, object]:
    """Return packaged starter recipes from the ODPR RecipeCatalog."""
    path = Path(catalog_path) if catalog_path is not None else DEFAULT_STARTER_CATALOG
    data = load_recipe_catalog(path)
    catalog = _mapping(data.get("recipeCatalog"))
    recipes = [
        dict(entry)
        for entry in _catalog_entries(catalog)
        if entry.get("groupRef") == STARTER_GROUP_ID
    ]
    recipe_catalog: Dict[str, object] = {
        "metadata": dict(_mapping(catalog.get("metadata"))),
        "version": catalog.get("version", DEFAULT_RECIPE_CATALOG_VERSION),
        "recipes": recipes,
    }
    groups = catalog.get("groups")
    if isinstance(groups, list):
        recipe_catalog["groups"] = [
            dict(group)
            for group in groups
            if isinstance(group, dict) and group.get("id") == STARTER_GROUP_ID
        ]
    return {
        "mode": "list",
        "source": "starters",
        "kind": "RecipeCatalog",
        "catalog": _relative_path(path, path.parent),
        "recipeCatalog": recipe_catalog,
        "warnings": [],
    }


def check_starter_catalog(
    *,
    catalog_path: Optional[PathLike] = None,
) -> Dict[str, object]:
    """Validate the packaged starter catalog and referenced recipes."""
    path = Path(catalog_path) if catalog_path is not None else DEFAULT_STARTER_CATALOG
    report = validate_odpr_document(path)
    root = path.parent
    errors = list(report.get("errors", []))
    warnings = list(report.get("warnings", []))
    checked_recipes: List[Dict[str, object]] = []
    try:
        data = load_recipe_catalog(path)
    except (FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
        data = {}
    catalog = _mapping(data.get("recipeCatalog"))
    for entry in _catalog_entries(catalog):
        entry_path = _string(entry.get("path"))
        entry_id = _string(entry.get("id")) or entry_path
        if not entry_path:
            continue
        recipe_path = root / entry_path
        recipe_result: Dict[str, object] = {
            "id": entry_id,
            "path": entry_path,
            "exists": recipe_path.is_file(),
            "valid": False,
        }
        if not recipe_path.is_file():
            errors.append(f"starter recipe not found: {entry_path}")
            checked_recipes.append(recipe_result)
            continue
        recipe_report = validate_recipe(recipe_path)
        recipe_result["valid"] = bool(recipe_report.get("valid"))
        recipe_result["errors"] = recipe_report.get("errors", [])
        if not recipe_report.get("valid"):
            errors.append(f"starter recipe is invalid: {entry_path}")
        workspace = recipe_path.parent
        for required_name in ("README.md", "AGENTS.md"):
            required_path = workspace / required_name
            if not required_path.is_file():
                errors.append(f"starter {entry_path} is missing {required_name}")
        checked_recipes.append(recipe_result)
    return {
        "mode": "starter-catalog-check",
        "valid": not errors,
        "catalog": _relative_path(path, root),
        "errors": errors,
        "warnings": warnings,
        "recipes": checked_recipes,
    }


def resolve_starter_recipe(
    identifier: str,
    *,
    catalog_path: Optional[PathLike] = None,
) -> Dict[str, object]:
    """Resolve a starter catalog entry by id, name, or folder name."""
    needle = _normalize_lookup(identifier)
    listing = list_starter_recipes(catalog_path=catalog_path)
    catalog = _mapping(listing.get("recipeCatalog"))
    matches = [
        entry
        for entry in _catalog_entries(catalog)
        if needle in _starter_entry_lookup_keys(entry)
    ]
    if not matches:
        raise ValueError(f"Starter recipe not found: {identifier}")
    if len(matches) > 1:
        raise ValueError(f"Starter recipe lookup is ambiguous: {identifier}")
    return dict(matches[0])


def init_starter_recipe(
    identifier: str,
    *,
    output: Optional[PathLike] = None,
    force: bool = False,
    parameterized: bool = False,
    catalog_path: Optional[PathLike] = None,
) -> Dict[str, object]:
    """Create a recipe workspace from a packaged starter."""
    catalog = (
        Path(catalog_path) if catalog_path is not None else DEFAULT_STARTER_CATALOG
    )
    entry = resolve_starter_recipe(identifier, catalog_path=catalog)
    entry_path = _string(entry.get("path"))
    if not entry_path:
        raise ValueError(f"Starter recipe has no path: {identifier}")
    if _is_unsafe_relative_path(entry_path):
        raise ValueError(f"Starter recipe path must be catalog-relative: {entry_path}")

    source_recipe = catalog.parent / entry_path
    source_dir = source_recipe.parent
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Starter recipe workspace not found: {source_dir}")

    target = Path(output) if output is not None else Path("recipes") / source_dir.name
    _validate_user_recipe_workspace_target(target)
    if target.exists() and not force:
        raise FileExistsError(f"Recipe workspace already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target, dirs_exist_ok=force)
    inputs_dir = target / "inputs"
    outputs_dir = target / "outputs"
    inputs_dir.mkdir(exist_ok=True)
    outputs_dir.mkdir(exist_ok=True)

    recipe_path = target / "recipe.yaml"
    if not recipe_path.is_file():
        raise FileNotFoundError(f"Initialized workspace missing recipe.yaml: {target}")

    created: Dict[str, str] = {
        "inputs": inputs_dir.as_posix(),
        "outputs": outputs_dir.as_posix(),
    }
    if parameterized:
        values_path = target / "recipe.values.yaml"
        schema_path = target / "values.schema.yaml"
        if values_path.exists() and not force:
            raise FileExistsError(f"Recipe values file already exists: {values_path}")
        if schema_path.exists() and not force:
            raise FileExistsError(f"Values schema file already exists: {schema_path}")
        values_path.write_text(
            _dump_yaml(_starter_values(entry, recipe_path)),
            encoding="utf-8",
        )
        schema_path.write_text(
            _dump_yaml(_starter_values_schema(entry)),
            encoding="utf-8",
        )
        _append_parameterized_notes(target)
        created["values"] = values_path.as_posix()
        created["valuesSchema"] = schema_path.as_posix()

    target_text = target.as_posix()
    recipe_text = recipe_path.as_posix()
    return {
        "mode": "init",
        "source": "starters",
        "catalog": _relative_path(catalog, catalog.parent),
        "starter": entry,
        "workspace": target_text,
        "recipe": recipe_text,
        "created": created,
        "force": force,
        "parameterized": parameterized,
        "nextCommands": [
            f"cd {target_text}",
            "open-data-products recipe plan",
            "open-data-products recipe run --allow-llm --approve-review",
        ],
    }


def _validate_user_recipe_workspace_target(target: Path) -> None:
    """Refuse starter init targets inside SDK-owned source folders."""
    resolved = target.resolve()
    package_root = Path(__file__).resolve().parents[1]
    repo_root = package_root.parent
    reserved = [package_root]
    for name in ("docs", "examples", "tests"):
        candidate = repo_root / name
        if candidate.exists():
            reserved.append(candidate)

    for root in reserved:
        if _is_relative_to(resolved, root.resolve()):
            raise ValueError(
                "Recipe workspaces should live in a user project folder. "
                "Run `open-data-products recipe init <starter>` from your "
                "project root, or pass `--output ./recipes/<starter>`."
            )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def explain_recipe(
    identifier: PathLike,
    *,
    catalog_path: Optional[PathLike] = None,
) -> Dict[str, object]:
    """Explain a local recipe file or packaged starter recipe."""
    value = Path(identifier)
    source = "local"
    catalog: Optional[Path] = None
    starter: Optional[Dict[str, object]] = None
    if value.is_file():
        recipe_path = value
    else:
        catalog = (
            Path(catalog_path)
            if catalog_path is not None
            else DEFAULT_STARTER_CATALOG
        )
        starter = resolve_starter_recipe(str(identifier), catalog_path=catalog)
        entry_path = _string(starter.get("path"))
        if not entry_path:
            raise ValueError(f"Starter recipe has no path: {identifier}")
        if _is_unsafe_relative_path(entry_path):
            raise ValueError(
                f"Starter recipe path must be catalog-relative: {entry_path}"
            )
        recipe_path = catalog.parent / entry_path
        source = "starters"

    validation = validate_recipe(recipe_path)
    recipe_doc = load_recipe(recipe_path) if validation.get("valid") else None
    data = recipe_doc.data if recipe_doc is not None else load_odpr_data(recipe_path)
    recipe = _mapping(data.get("recipe"))
    metadata = _mapping(recipe.get("metadata"))
    execution = _mapping(recipe.get("execution"))
    context = _mapping(recipe.get("context"))
    review = _mapping(recipe.get("review"))
    gates = recipe.get("gates")
    steps = _steps(recipe.get("steps"))

    recipe_summary = _recipe_summary(recipe_path, metadata, recipe)
    recipe_summary["path"] = recipe_path.as_posix()
    payload: Dict[str, object] = {
        "mode": "explain",
        "source": source,
        "valid": bool(validation.get("valid")),
        "errors": validation.get("errors", []),
        "warnings": validation.get("warnings", []),
        "recipe": recipe_summary,
        "execution": {
            "mode": execution.get("mode"),
            "providerRef": execution.get("providerRef"),
        },
        "context": {
            "format": context.get("format"),
        },
        "review": {
            "required": review.get("required", False),
        },
        "steps": [_explain_step(step) for step in steps],
        "gates": gates if isinstance(gates, list) else [],
        "safetyNotes": [
            "Explanation does not execute recipe steps.",
            "Explanation does not call providers.",
            "Run a dry-run before guarded execution.",
        ],
        "nextCommands": [
            f"open-data-products recipe run {recipe_path.as_posix()} --dry-run",
            (
                f"open-data-products recipe run {recipe_path.as_posix()} "
                "--execute --approve-review"
            ),
        ],
    }
    if catalog is not None and starter is not None:
        payload["catalog"] = _relative_path(catalog, catalog.parent)
        payload["starter"] = starter
    return payload


def _explain_step(step: Mapping[str, object]) -> Dict[str, object]:
    summary = _step_summary(step)
    with_values = _mapping(step.get("with"))
    if with_values:
        summary["with"] = dict(with_values)
    provider_ref = _string(step.get("providerRef"))
    if provider_ref:
        summary["providerRef"] = provider_ref
    model = _string(step.get("model"))
    if model:
        summary["model"] = model
    return summary


def _starter_values(
    entry: Mapping[str, object],
    recipe_path: Path,
) -> Dict[str, object]:
    recipe_doc = load_recipe(recipe_path)
    recipe = _mapping(recipe_doc.data.get("recipe"))
    execution = _mapping(recipe.get("execution"))
    context = _mapping(recipe.get("context"))
    first_step = _mapping(recipe_doc.steps[0]) if recipe_doc.steps else {}
    with_values = _mapping(first_step.get("with"))
    return {
        "starter": {
            "id": entry.get("id"),
            "path": entry.get("path"),
        },
        "execution": {
            "providerRef": first_step.get("providerRef")
            or execution.get("providerRef"),
            "model": first_step.get("model"),
        },
        "context": {
            "format": context.get("format") or entry.get("contextFormat"),
        },
        "paths": _starter_path_values(with_values),
    }


def _starter_path_values(values: Mapping[str, object]) -> Dict[str, object]:
    paths: Dict[str, object] = {}
    for key in (
        "input",
        "output",
        "workspace",
        "objectives",
        "useCases",
        "signals",
        "products",
        "graph",
    ):
        value = values.get(key)
        if isinstance(value, (str, list)):
            paths[key] = value
    return paths


def _starter_values_schema(entry: Mapping[str, object]) -> Dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"{_localized_name(entry)} values",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "starter": {"type": "object"},
            "execution": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "providerRef": {"type": ["string", "null"]},
                    "model": {"type": ["string", "null"]},
                },
            },
            "context": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "format": {"type": ["string", "null"]},
                },
            },
            "paths": {
                "type": "object",
                "additionalProperties": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ]
                },
            },
        },
    }


def _append_parameterized_notes(target: Path) -> None:
    readme = target / "README.md"
    agents = target / "AGENTS.md"
    readme_note = (
        "\n## Parameterized Mode\n\n"
        "`recipe.values.yaml` and `values.schema.yaml` are advanced reuse "
        "files for teams that want to separate project-specific settings from "
        "the workflow contract. The current recipe runner still executes "
        "`recipe.yaml`; update it deliberately when applying values.\n"
    )
    agents_note = (
        "\n## Parameterized Mode\n\n"
        "Treat `recipe.values.yaml` as editable project settings and "
        "`values.schema.yaml` as the expected shape. Do not store secrets in "
        "either file, and do not write runtime results back into ODPR files.\n"
    )
    if readme.is_file():
        readme.write_text(
            readme.read_text(encoding="utf-8") + readme_note,
            encoding="utf-8",
        )
    if agents.is_file():
        agents.write_text(
            agents.read_text(encoding="utf-8") + agents_note,
            encoding="utf-8",
        )


def _localized_name(entry: Mapping[str, object]) -> str:
    name = _mapping(entry.get("name"))
    english = name.get("en")
    return english if isinstance(english, str) else str(entry.get("id", "Recipe"))


def _catalog_entry(entry: Mapping[str, object]) -> Dict[str, object]:
    allowed = (
        "path",
        "id",
        "version",
        "type",
        "name",
        "groupRef",
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


def _catalog_entries(catalog: Mapping[str, object]) -> List[Mapping[str, object]]:
    entries = catalog.get("recipes")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _starter_entry_lookup_keys(entry: Mapping[str, object]) -> Set[str]:
    keys = set()
    for value in (entry.get("id"), entry.get("path")):
        if isinstance(value, str):
            keys.add(_normalize_lookup(value))
            keys.add(_normalize_lookup(Path(value).parent.name))
    name = _mapping(entry.get("name"))
    english_name = name.get("en")
    if isinstance(english_name, str):
        keys.add(_normalize_lookup(english_name))
    return {key for key in keys if key}


def _normalize_lookup(value: str) -> str:
    return "".join(char.lower() for char in value if char.isalnum())


def _localized_text(value: str) -> Dict[str, str]:
    return {"en": value.replace("-", " ").replace("_", " ").title()}


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
        "portfolio.build": ("objectives", "useCases", "signals", "products"),
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
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    inputs.append({"path": item, "exists": (root / item).exists()})
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
        if command == "portfolio.build":
            _append_string(paths, values.get("workspace"))
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
    elif command in {"portfolio.refresh", "portfolio.sync"}:
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
    if default_recipe:
        root = _project_root(None, config_path, project_root, config)
        return root / default_recipe, {
            "source": "config-default",
            "path": default_recipe,
            "defaultRecipe": default_recipe,
        }
    cwd_recipe = Path("recipe.yaml")
    if cwd_recipe.is_file():
        return cwd_recipe, {
            "source": "cwd-default",
            "path": cwd_recipe.as_posix(),
            "defaultRecipe": None,
        }
    if not default_recipe:
        raise ValueError(
            "recipe path is required unless recipes.defaultRecipe is set in "
            "recipes.config.yaml or recipe.yaml exists in the current directory"
        )


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
                "requiredEnv": [],
                "missingEnv": [],
                "source": None,
            }
            continue
        api_key_env = _string(provider_config.get("apiKeyEnv"))
        required_env = [api_key_env] if api_key_env else []
        missing_env = []
        if api_key_env and not os.environ.get(api_key_env):
            missing_env.append(api_key_env)
        providers[provider] = {
            "ref": provider,
            "model": parameters.get("model") or provider_config.get("model"),
            "type": provider_config.get("type"),
            "readiness": "missing-env" if missing_env else "ready",
            "requiredEnv": required_env,
            "missingEnv": missing_env,
            "source": source,
        }
    return list(providers.values())


def _plan_execution_policy(
    recipe: Mapping[str, object],
    config: Mapping[str, object],
) -> Dict[str, object]:
    execution = _mapping(recipe.get("execution"))
    return {
        "mode": execution.get("mode"),
        "providerRef": execution.get("providerRef") or _default_provider(config),
    }


def _plan_context_policy(recipe: Mapping[str, object]) -> Dict[str, object]:
    context = _mapping(recipe.get("context"))
    return {
        "format": context.get("format"),
    }


def _plan_review_policy(
    recipe: Mapping[str, object],
    steps: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    review = _mapping(recipe.get("review"))
    statuses = [
        _mapping(step.get("review")).get("status")
        for step in steps
        if isinstance(step, dict)
    ]
    return {
        "required": review.get("required", False),
        "requiresApproval": "review-needed" in statuses,
    }


def _plan_gates(recipe: Mapping[str, object]) -> List[object]:
    gates = recipe.get("gates")
    return list(gates) if isinstance(gates, list) else []


def _plan_reads(steps: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    reads: List[Dict[str, object]] = []
    for step in steps:
        step_id = _string(step.get("id")) or ""
        for item in step.get("inputs", []):
            if isinstance(item, dict):
                read = dict(item)
                read["step"] = step_id
                reads.append(read)
    return reads


def _plan_writes(steps: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    writes: List[Dict[str, object]] = []
    for step in steps:
        step_id = _string(step.get("id")) or ""
        for item in step.get("plannedWrites", []):
            if isinstance(item, dict):
                write = dict(item)
                write["step"] = step_id
                writes.append(write)
    return writes


def _plan_required_env(providers: Sequence[Mapping[str, object]]) -> List[str]:
    env_names = set()
    for provider in providers:
        required = provider.get("requiredEnv")
        if isinstance(required, list):
            env_names.update(item for item in required if isinstance(item, str))
        missing = provider.get("missingEnv")
        if isinstance(missing, list):
            env_names.update(item for item in missing if isinstance(item, str))
    return sorted(env_names)


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
        if command == "generate":
            from ..generation import create_generation_client
            from ..generation import generate_local_artifacts_for_kind
            from ..generation import resolve_generation_settings

            source = _required_path(parameters, "input", root)
            output = _required_path(parameters, "output", root)
            kind = _required_string(parameters, "kind")
            profile = _string(parameters.get("profile")) or "minimal"
            include_components = _string_sequence(parameters.get("includeComponents"))
            max_source_chars = _optional_int(parameters.get("maxSourceChars"))
            prompt_dir = _optional_path(parameters, "prompts", root)
            settings = resolve_generation_settings(
                config_path=generation_config,
                input_path=source,
                output_path=output,
                provider=_string(parameters.get("providerRef")),
                model=_string(parameters.get("model")),
                prompt_dir=prompt_dir,
            )
            client = create_generation_client(settings)
            artifacts = generate_local_artifacts_for_kind(
                kind,
                source,
                output,
                model=settings.model,
                client=client,
                prompt_dir=settings.prompt_path,
                profile=profile,
                include_components=include_components,
                max_source_chars=max_source_chars,
            )
            artifact_paths = [
                _relative_path(artifact.output_path, root) for artifact in artifacts
            ]
            return _step_result(
                step,
                "passed",
                started_at,
                artifacts=artifact_paths,
                summary={
                    "kind": "Generate",
                    "artifactKind": kind,
                    "artifactCount": len(artifacts),
                    "artifacts": [
                        {
                            "name": artifact.name,
                            "promptName": artifact.prompt_name,
                            "path": _relative_path(artifact.output_path, root),
                            "validYaml": artifact.valid_yaml,
                        }
                        for artifact in artifacts
                    ],
                },
            )
        if command == "odpg.build":
            from ..generation import create_generation_client
            from ..generation import resolve_generation_settings
            from ..odpg import build_graph
            from ..odpg import summarize_graph
            from ..odpg import validate_graph
            from ..odpg import write_graph
            from ..odpg import write_graph_gcf
            from ..odpg import write_graph_toon

            source = _required_path(parameters, "input", root)
            output = _required_path(parameters, "output", root)
            toon_output = _optional_path(parameters, "toon", root)
            gcf_output = _optional_path(parameters, "gcf", root)
            prompt_dir = _optional_path(parameters, "prompts", root)
            context_graph = _optional_path(parameters, "contextGraph", root)
            settings = resolve_generation_settings(
                config_path=generation_config,
                input_path=source,
                output_path=output,
                provider=_string(parameters.get("providerRef")),
                model=_string(parameters.get("model")),
                ollama_url=_string(parameters.get("ollamaUrl")),
                prompt_dir=prompt_dir,
            )
            client = create_generation_client(settings)
            document = build_graph(
                source,
                recursive=parameters.get("recursive") is not False,
                output_path=output,
                graph_id=_string(parameters.get("id")),
                name=_string(parameters.get("name")),
                description=_string(parameters.get("description")),
                client=client,
                model=settings.model,
                prompt_dir=settings.prompt_path,
                context_graph=context_graph,
            )
            validation = (
                validate_graph(document)
                if parameters.get("validate") is not False
                else None
            )
            write_graph(output, document)
            artifact_paths = [_relative_path(output, root)]
            if toon_output is not None:
                write_graph_toon(toon_output, document)
                artifact_paths.append(_relative_path(toon_output, root))
            if gcf_output is not None:
                write_graph_gcf(gcf_output, document)
                artifact_paths.append(_relative_path(gcf_output, root))
            summary = summarize_graph(document)
            return _step_result(
                step,
                "passed",
                started_at,
                artifacts=sorted(artifact_paths),
                summary={
                    "kind": "Graph",
                    "valid": validation.valid if validation is not None else None,
                    "nodeCount": summary.get("nodeCount"),
                    "edgeCount": summary.get("edgeCount"),
                    "path": _relative_path(output, root),
                    "toon": (
                        _relative_path(toon_output, root)
                        if toon_output is not None
                        else None
                    ),
                    "gcf": (
                        _relative_path(gcf_output, root)
                        if gcf_output is not None
                        else None
                    ),
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
        if command == "portfolio.build":
            from ..generation import create_generation_client
            from ..generation import resolve_generation_settings
            from ..portfolio import build_portfolio

            workspace = _portfolio_workspace_path(parameters, root)
            prompt_dir = _optional_path(parameters, "prompts", root)
            settings = resolve_generation_settings(
                config_path=generation_config,
                provider=_string(parameters.get("providerRef")),
                model=_string(parameters.get("model")),
                ollama_url=_string(parameters.get("ollamaUrl")),
                prompt_dir=prompt_dir,
            )
            client = create_generation_client(settings)
            result = build_portfolio(
                workspace,
                objectives=_optional_lane_path(parameters, "objectives", root),
                use_cases=_optional_lane_path(parameters, "useCases", root),
                signals=_optional_lane_path(parameters, "signals", root),
                products=_optional_lane_path(parameters, "products", root),
                title=_string(parameters.get("title")),
                client=client,
                model=settings.model,
            )
            return _portfolio_step_result(step, started_at, root, result)
        if command == "portfolio.refresh":
            from ..generation import create_generation_client
            from ..generation import resolve_generation_settings
            from ..portfolio import refresh_portfolio

            workspace = _required_path(parameters, "workspace", root)
            prompt_dir = _optional_path(parameters, "prompts", root)
            settings = resolve_generation_settings(
                config_path=generation_config,
                provider=_string(parameters.get("providerRef")),
                model=_string(parameters.get("model")),
                ollama_url=_string(parameters.get("ollamaUrl")),
                prompt_dir=prompt_dir,
            )
            client = create_generation_client(settings)
            result = refresh_portfolio(
                workspace,
                objectives=_optional_lane_path(parameters, "objectives", root),
                use_cases=_optional_lane_path(parameters, "useCases", root),
                signals=_optional_lane_path(parameters, "signals", root),
                products=_optional_lane_path(parameters, "products", root),
                title=_string(parameters.get("title")),
                client=client,
                model=settings.model,
                all_sources=parameters.get("allSources") is True,
            )
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
    except (FileNotFoundError, KeyError, RuntimeError, ValueError, OSError) as exc:
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
    planned_dirs = [path.rstrip("/") for path in planned if path.endswith("/")]
    planned_files = [path for path in planned if not path.endswith("/")]
    planned_set = set(planned)
    artifact_set = set(artifact_paths)
    matched_artifacts = {
        path
        for path in artifact_paths
        if path in planned_files
        or any(
            path == directory or path.startswith(f"{directory}/")
            for directory in planned_dirs
        )
    }
    missing_files = set(planned_files) - artifact_set
    missing_dirs = {
        f"{directory}/"
        for directory in planned_dirs
        if not any(
            path == directory or path.startswith(f"{directory}/")
            for path in artifact_paths
        )
    }
    missing = sorted(missing_files | missing_dirs)
    extra = sorted(artifact_set - matched_artifacts)
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
        "matched": sorted(matched_artifacts),
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


def _portfolio_workspace_path(parameters: Mapping[str, object], root: Path) -> Path:
    output = parameters.get("output")
    if isinstance(output, str) and output:
        return root / output
    return _required_path(parameters, "workspace", root)


def _optional_lane_path(
    parameters: Mapping[str, object],
    key: str,
    root: Path,
) -> Optional[Path]:
    value = parameters.get(key)
    if isinstance(value, str) and value:
        return root / value
    if isinstance(value, list):
        paths = [item for item in value if isinstance(item, str) and item]
        if not paths:
            return None
        if len(paths) > 1:
            raise ValueError(f"Recipe parameter {key} supports one path.")
        return root / paths[0]
    return None


def _required_string(parameters: Mapping[str, object], key: str) -> str:
    value = parameters.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required string parameter: {key}")
    return value.strip()


def _optional_int(value: object) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def _string_sequence(value: object) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return None


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
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


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
