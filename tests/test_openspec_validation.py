"""Offline tests for validation through the optional OpenSpec CLI."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from open_data_products import _openspec_validation as validator
from open_data_products.cli import main


def change(tmp_path, mode="implementation-draft"):
    root = tmp_path / "customer-view"
    (root / "supporting").mkdir(parents=True)
    (root / ".openspec.yaml").write_text("schema: spec-driven\n")
    (root / "proposal.md").write_text("# Proposal\n")
    (root / "supporting/manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "format": "odps-assistant-handoff",
                "version": 1,
                "openspec_schema": "spec-driven",
                "mode": mode,
            }
        )
    )
    if mode == "implementation-draft":
        (root / "design.md").write_text("# Design\n")
        (root / "tasks.md").write_text("# Tasks\n")
        (root / "specs/product").mkdir(parents=True)
        (root / "specs/product/spec.md").write_text("## ADDED Requirements\n")
    return root


def mock_cli(monkeypatch, *, valid, planning_complete, issues=None, version="2.2.0"):
    calls = []
    monkeypatch.setattr(validator.shutil, "which", lambda name: "/fake/openspec")

    def run(cli, arguments, cwd):
        calls.append(arguments)
        if arguments[0] == "--version":
            return SimpleNamespace(returncode=0, stdout=version)
        if arguments[0] == "status":
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"isPlanningComplete": planning_complete}),
            )
        return SimpleNamespace(
            returncode=0 if valid else 1,
            stdout=json.dumps(
                {
                    "items": [
                        {"id": "customer-view", "valid": valid, "issues": issues or []}
                    ]
                }
            ),
        )

    monkeypatch.setattr(validator, "_run", run)
    return calls


def test_missing_cli_reports_not_performed_and_guidance(tmp_path, monkeypatch, capsys):
    root = change(tmp_path)
    monkeypatch.setattr(validator.shutil, "which", lambda name: None)
    result = validator.validate_openspec_handover(root)
    assert result["status"] == "not_performed" and result["cli_version"] is None
    assert "installation.md" in result["installation_guidance"]
    assert main(["handover", "validate", "--input", str(root), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["cli_validation"] == "not_performed"


def test_success_reports_version_and_uses_strict_validation(tmp_path, monkeypatch):
    root = change(tmp_path)
    calls = mock_cli(monkeypatch, valid=True, planning_complete=True)
    result = validator.validate_openspec_handover(root)
    assert result["status"] == "passed" and result["cli_version"] == "2.2.0"
    assert result["cli_validation"] == "passed" and result["planning_complete"] is True
    assert calls[2] == [
        "validate",
        "customer-view",
        "--type",
        "change",
        "--strict",
        "--json",
        "--no-interactive",
    ]


def test_completed_draft_validation_failure_is_not_incomplete(tmp_path, monkeypatch):
    root = change(tmp_path)
    issues = [{"level": "ERROR", "message": "Invalid requirement"}]
    mock_cli(monkeypatch, valid=False, planning_complete=True, issues=issues)
    result = validator.validate_openspec_handover(root)
    assert result["status"] == "failed" and result["issues"] == issues
    assert main(["handover", "validate", "--input", str(root), "--json"]) == 1


def test_preparation_only_reports_incomplete_not_passed(tmp_path, monkeypatch):
    root = change(tmp_path, mode="preparation-only")
    mock_cli(
        monkeypatch,
        valid=False,
        planning_complete=False,
        issues=[
            {
                "level": "ERROR",
                "message": "Change must have at least one delta. No deltas found.",
            }
        ],
    )
    result = validator.validate_openspec_handover(root)
    assert result["status"] == "incomplete"
    assert result["cli_validation"] == "failed" and result["planning_complete"] is False
    assert main(["handover", "validate", "--input", str(root), "--json"]) == 2


def test_incomplete_does_not_hide_other_cli_failures(tmp_path, monkeypatch):
    root = change(tmp_path, mode="preparation-only")
    mock_cli(
        monkeypatch,
        valid=False,
        planning_complete=False,
        issues=[
            {"level": "ERROR", "message": "No deltas found"},
            {"level": "ERROR", "message": "Malformed metadata"},
        ],
    )
    assert validator.validate_openspec_handover(root)["status"] == "failed"


def test_cli_success_does_not_pass_incomplete_implementation(tmp_path, monkeypatch):
    root = change(tmp_path)
    mock_cli(monkeypatch, valid=True, planning_complete=False)
    result = validator.validate_openspec_handover(root)
    assert result["status"] == "failed" and result["cli_validation"] == "passed"


def test_rejects_symbolic_links_without_copying_outside_files(tmp_path, monkeypatch):
    root = change(tmp_path)
    (root / "design.md").unlink()
    (root / "design.md").symlink_to(tmp_path / "outside")
    mock_cli(monkeypatch, valid=True, planning_complete=True)
    with pytest.raises(ValueError, match="symbolic links"):
        validator.validate_openspec_handover(root)


def test_invalid_cli_output_is_not_a_pass(tmp_path, monkeypatch):
    root = change(tmp_path)
    monkeypatch.setattr(validator.shutil, "which", lambda name: "/fake/openspec")
    monkeypatch.setattr(
        validator,
        "_run",
        lambda cli, arguments, cwd: SimpleNamespace(
            returncode=0, stdout="2.2.0" if arguments[0] == "--version" else "invalid"
        ),
    )
    assert validator.validate_openspec_handover(root)["status"] == "not_performed"


def test_workspace_input_uses_recorded_change(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    root = change(workspace)
    (workspace / "prepare.json").write_text(
        json.dumps({"format": "odps-guided-handoff", "version": 1, "change": root.name})
    )
    mock_cli(monkeypatch, valid=True, planning_complete=True)
    assert validator.validate_openspec_handover(workspace)["status"] == "passed"


def test_cli_runs_with_telemetry_disabled_and_timeout(tmp_path, monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="2.2.0")

    monkeypatch.setenv("OPENSPEC_TEST_SECRET", "never-forward")
    monkeypatch.setattr(validator.subprocess, "run", run)
    result = validator._run("/fake/openspec", ["--version"], tmp_path)
    assert result.returncode == 0
    assert calls[0][0] == ["/fake/openspec", "--version"]
    assert calls[0][1]["env"]["OPENSPEC_TELEMETRY"] == "0"
    assert "OPENSPEC_TEST_SECRET" not in calls[0][1]["env"]
    assert calls[0][1]["timeout"] == 30


def test_validation_does_not_modify_generated_package(tmp_path, monkeypatch):
    root = change(tmp_path)
    before = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    mock_cli(monkeypatch, valid=True, planning_complete=True)
    assert validator.validate_openspec_handover(root)["status"] == "passed"
    after = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_implementation_with_missing_planning_files_is_not_a_pass(
    tmp_path, monkeypatch
):
    root = change(tmp_path)
    (root / "tasks.md").unlink()
    mock_cli(monkeypatch, valid=True, planning_complete=False)
    result = validator.validate_openspec_handover(root)
    assert result["status"] == "failed" and result["planning_complete"] is False
