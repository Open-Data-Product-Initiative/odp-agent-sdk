"""User-editable platform connection configuration template."""

from pathlib import Path
import shutil
from typing import Dict, Optional, Union

from .config import ConfigurationError, load_integration_config

TEMPLATE = Path(__file__).resolve().parent / "connections.yaml"
PathLike = Union[str, Path]


def get_integration_config(config_path: Optional[PathLike] = None) -> Dict[str, object]:
    """Return a sanitized connection-config summary without resolving tokens."""
    path = Path(config_path) if config_path is not None else TEMPLATE
    config = load_integration_config(path)
    return {
        "domain": "integrations",
        "template_path": str(TEMPLATE),
        "config_path": str(path),
        "editable": config_path is not None,
        "default_connection": config.default_connection,
        "connections": [
            {
                "name": profile.name,
                "platform": profile.platform,
                "read_only": profile.read_only,
            }
            for profile in config.connections.values()
        ],
        "copy_hint": "Copy the template, edit the local endpoint, and connect using that file.",
    }


def validate_integration_config(
    config_path: Optional[PathLike] = None,
) -> Dict[str, object]:
    """Validate a connection config locally without accessing credentials."""
    path = Path(config_path) if config_path is not None else TEMPLATE
    try:
        load_integration_config(path)
    except ConfigurationError as exc:
        return {
            "domain": "integrations",
            "config_path": str(path),
            "valid": False,
            "errors": [str(exc)],
            "warnings": [],
        }
    return {
        "domain": "integrations",
        "config_path": str(path),
        "valid": True,
        "errors": [],
        "warnings": [],
    }


def copy_integration_config_template(
    destination: PathLike, *, overwrite: bool = False
) -> Path:
    """Copy the bundled example to a user-owned config file."""
    target = Path(destination)
    if target.is_dir() or str(destination).endswith(("/", "\\")):
        target = target / TEMPLATE.name
    if target.exists() and not overwrite:
        raise FileExistsError("Config file already exists: " + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATE, target)
    return target
