"""Recipe workflow loading, validation, and dry-run planning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Dict, List, Mapping, Optional, Sequence, Union

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


def validate_recipe(path: PathLike) -> Dict[str, object]:
    """Validate one recipe without executing steps."""
    recipe_path = Path(path)
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

    allowed_top = {"version", "recipes", "providers", "execution", "outputs", "gui"}
    for key in config:
        if key not in allowed_top:
            errors.append(f"Unknown top-level recipes config key: {key}")

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
        elif not _generation_config_exists(config_path, generation_config):
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
    path: PathLike,
    *,
    mode: str = "dry-run",
    config_path: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
    provider_ref: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, object]:
    """Return an agent-facing recipe run plan without executing steps."""
    recipe_path = Path(path)
    root = _project_root(recipe_path, config_path, project_root)
    validation = validate_recipe(recipe_path)
    recipe_doc = load_recipe(recipe_path) if validation["valid"] else None
    config = _load_optional_recipe_config(config_path)
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
        "providers": _provider_readiness(steps),
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


def list_recipes(
    *,
    config_path: Optional[PathLike] = None,
    project_root: Optional[PathLike] = None,
) -> Dict[str, object]:
    """Return a RecipeCatalog-style listing for configured recipe paths."""
    root = _project_root(None, config_path, project_root)
    config = _load_optional_recipe_config(config_path)
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
        "review": {"status": "not-required"},
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
            for language in _language_list(languages):
                paths.append(f"{workspace.rstrip('/')}/index.{language}.html")
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


def _generation_config_exists(config_path: Path, generation_config: str) -> bool:
    if (config_path.parent / generation_config).is_file():
        return True
    if (
        config_path == DEFAULT_RECIPE_CONFIG
        and generation_config == "generation.config.yaml"
    ):
        return (config_path.parent.parent / "generation" / generation_config).is_file()
    return False


def _provider_readiness(
    steps: Sequence[Mapping[str, object]],
) -> List[Dict[str, object]]:
    providers: Dict[str, Dict[str, object]] = {}
    for step in steps:
        resolved = _mapping(step.get("resolved"))
        parameters = _mapping(resolved.get("parameters"))
        provider = _string(parameters.get("providerRef"))
        if not provider:
            continue
        providers[provider] = {
            "ref": provider,
            "model": parameters.get("model"),
            "readiness": "unchecked",
            "missingEnv": [],
        }
    return list(providers.values())


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
) -> Path:
    if project_root is not None:
        return Path(project_root)
    if config_path is not None:
        return Path(config_path).parent
    if recipe_path is not None:
        return recipe_path.parent
    return Path.cwd()
