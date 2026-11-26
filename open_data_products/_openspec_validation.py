"""Validate generated OpenSpec changes with the external OpenSpec CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import yaml

from ._guided_handoff import _workspace_file

_MAX_SOURCE_BYTES = 5 * 1024 * 1024
_MAX_FILES = 200
_INSTALLATION_GUIDANCE = "Install the OpenSpec CLI: https://github.com/Fission-AI/OpenSpec/blob/main/docs/installation.md"


def _change_directory(value):
    root = Path(value).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError(
            "Input must be a generated handover workspace or change directory"
        )
    root = root.resolve()
    if (root / "prepare.json").is_file():
        try:
            state = json.loads(
                _workspace_file(root, "prepare.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            raise ValueError("Cannot read prepared handover metadata") from None
        if (
            not isinstance(state, dict)
            or state.get("format") != "odps-guided-handoff"
            or state.get("version") != 1
        ):
            raise ValueError("Invalid prepared handover metadata")
        root = _workspace_file(root, state.get("change"), directory=True)
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", root.name):
        raise ValueError("OpenSpec change directory name must be kebab-case")
    return root


def _metadata(root):
    try:
        manifest = yaml.safe_load(
            _workspace_file(root, "supporting/manifest.yaml").read_text(
                encoding="utf-8"
            )
        )
        schema = yaml.safe_load(
            _workspace_file(root, ".openspec.yaml").read_text(encoding="utf-8")
        )
    except (OSError, ValueError, yaml.YAMLError):
        raise ValueError("Cannot read generated handover metadata") from None
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != "odps-assistant-handoff"
        or manifest.get("version") != 1
    ):
        raise ValueError("Input is not a recognized SDK handover")
    if (
        not isinstance(schema, dict)
        or schema.get("schema") != "spec-driven"
        or manifest.get("openspec_schema") != "spec-driven"
    ):
        raise ValueError(
            "Only the SDK default spec-driven schema can be validated in isolation"
        )
    mode = manifest.get("mode", "preparation-only")
    if mode not in ("preparation-only", "implementation-draft"):
        raise ValueError("Unsupported handover mode")
    return mode


def _stage_change(root, project):
    dest = project / "openspec" / "changes" / root.name
    dest.mkdir(parents=True)
    paths = []
    for filename in (".openspec.yaml", "proposal.md", "design.md", "tasks.md"):
        path = root / filename
        if path.is_symlink():
            raise ValueError("OpenSpec artifacts must not be symbolic links")
        if path.exists():
            if not path.is_file():
                raise ValueError("Invalid OpenSpec artifact")
            paths.append(path)
    specs = root / "specs"
    if specs.is_symlink():
        raise ValueError("OpenSpec artifacts must not be symbolic links")
    if specs.exists():
        if not specs.is_dir():
            raise ValueError("Invalid OpenSpec specifications directory")
        for path in specs.rglob("*"):
            if path.is_symlink():
                raise ValueError("OpenSpec artifacts must not be symbolic links")
            if path.is_file() and path.suffix == ".md":
                paths.append(path)
    if (
        len(paths) > _MAX_FILES
        or sum(path.stat().st_size for path in paths) > _MAX_SOURCE_BYTES
    ):
        raise ValueError("OpenSpec artifacts exceed validation size limits")
    for path in paths:
        target = dest / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return paths


def _run(cli, arguments, cwd):
    allowed = (
        "PATH",
        "HOME",
        "USERPROFILE",
        "SYSTEMROOT",
        "WINDIR",
        "PATHEXT",
        "TMPDIR",
        "TEMP",
        "TMP",
        "LANG",
        "LC_ALL",
        "NO_COLOR",
    )
    env = {name: os.environ[name] for name in allowed if name in os.environ}
    env["OPENSPEC_TELEMETRY"] = "0"
    try:
        return subprocess.run(
            [cli] + arguments,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def validate_openspec_handover(value):
    """Return explicit structural validation status without modifying the package."""
    root = _change_directory(value)
    mode = _metadata(root)
    result = {
        "status": "not_performed",
        "mode": mode,
        "cli_version": None,
        "cli_validation": "not_performed",
        "planning_complete": None,
        "issues": [],
        "scope": "isolated default spec-driven workflow; no business approval or implementation verification",
    }
    cli = shutil.which("openspec")
    if not cli:
        result["reason"] = "OpenSpec CLI not found; validation was not performed."
        result["installation_guidance"] = _INSTALLATION_GUIDANCE
        return result
    version = _run(cli, ["--version"], root)
    if version is None or version.returncode != 0 or not version.stdout.strip():
        result["reason"] = (
            "OpenSpec CLI version could not be determined; validation was not performed."
        )
        return result
    result["cli_version"] = version.stdout.strip()[:200]
    with tempfile.TemporaryDirectory(prefix="odp-openspec-validation-") as temp:
        project = Path(temp)
        paths = _stage_change(root, project)
        status = _run(cli, ["status", "--change", root.name, "--json"], project)
        result["cli_validation"] = "unknown"
        validation = _run(
            cli,
            [
                "validate",
                root.name,
                "--type",
                "change",
                "--strict",
                "--json",
                "--no-interactive",
            ],
            project,
        )
        if status is None or validation is None:
            result["reason"] = (
                "OpenSpec CLI failed to start or timed out; validation was not completed."
            )
            return result
        try:
            planning = json.loads(status.stdout)
            report = json.loads(validation.stdout)
            items = report["items"]
            if (
                not isinstance(planning, dict)
                or not isinstance(planning.get("isPlanningComplete"), bool)
                or not isinstance(items, list)
                or len(items) != 1
                or not isinstance(items[0], dict)
                or items[0].get("id") != root.name
                or not isinstance(items[0].get("valid"), bool)
                or not isinstance(items[0].get("issues"), list)
                or any(
                    not isinstance(issue, dict) for issue in items[0].get("issues", [])
                )
            ):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            result["reason"] = (
                "OpenSpec CLI returned an unexpected validation response."
            )
            return result
        if status.returncode != 0 or validation.returncode not in (0, 1):
            result["reason"] = "OpenSpec CLI could not complete validation."
            return result
        valid = items[0]["valid"] and validation.returncode == 0
        result["planning_complete"] = planning["isPlanningComplete"]
        result["cli_validation"] = "passed" if valid else "failed"
        result["issues"] = items[0]["issues"]
        names = {path.relative_to(root).as_posix() for path in paths}
        intentionally_incomplete = (
            mode == "preparation-only"
            and ".openspec.yaml" in names
            and "proposal.md" in names
            and "design.md" not in names
            and "tasks.md" not in names
            and not any(name.startswith("specs/") for name in names)
        )
        only_missing_deltas = (
            not valid
            and len(result["issues"]) == 1
            and "No deltas found" in str(result["issues"][0].get("message", ""))
        )
        if (
            intentionally_incomplete
            and not result["planning_complete"]
            and only_missing_deltas
        ):
            result["status"] = "incomplete"
            result["reason"] = (
                "Preparation-only package intentionally lacks specifications, design and tasks; strict OpenSpec validation did not pass."
            )
        elif valid and result["planning_complete"]:
            result["status"] = "passed"
        else:
            result["status"] = "failed"
            result["reason"] = (
                "OpenSpec validation failed or required planning artifacts are incomplete."
            )
    return result
