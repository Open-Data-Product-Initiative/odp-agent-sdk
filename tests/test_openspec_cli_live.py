"""Opt-in OpenSpec CLI integration tests for freshly generated packages."""

import os
import json
import importlib.util
from pathlib import Path
import shutil

import pytest

from open_data_products._openspec_validation import validate_openspec_handover
from open_data_products.cli import main
from open_data_products.generation import resolve_generation_settings
from open_data_products.handoff import generate_handoff, preview_handoff
from open_data_products._handoff_implementation import (
    generate_implementation_handoff,
    preview_implementation_handoff,
)


def _fixture_module(name):
    path = Path(__file__).parent / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_initial = _fixture_module("test_handoff")
_implementation = _fixture_module("test_implementation_handoff")
inputs, model_reply = _initial.inputs, _initial.model_reply
reply, setup_inputs = _implementation.reply, _implementation.setup_inputs

pytestmark = pytest.mark.skipif(
    os.environ.get("ODPS_OPENSPEC_CLI_TEST") != "1",
    reason="Set ODPS_OPENSPEC_CLI_TEST=1 to test against the installed OpenSpec CLI",
)


def test_real_cli_validates_generated_package_modes(tmp_path, monkeypatch, capsys):
    assert shutil.which("openspec"), "The opt-in test requires OpenSpec CLI on PATH"
    settings = resolve_generation_settings()
    brief, product = inputs(tmp_path)
    preview = preview_handoff(brief, product, settings)
    monkeypatch.setattr(
        "open_data_products.handoff.create_generation_client",
        lambda _: lambda prompt, model: model_reply(),
    )
    preparation = generate_handoff(
        preview,
        tmp_path / "prep",
        "customer-view",
        settings,
        reviewed_sha256=preview.digest,
    )
    result = validate_openspec_handover(preparation)
    assert result["cli_version"] == "2.2.0"
    assert result["status"] == "incomplete"
    assert result["cli_validation"] == "failed"
    assert result["planning_complete"] is False
    assert main(["handover", "validate", "--input", str(preparation), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "incomplete"

    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    brief, product, context = setup_inputs(source_dir)
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, model: reply(),
    )
    implementation = generate_implementation_handoff(
        preview,
        tmp_path / "impl",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    result = validate_openspec_handover(implementation)
    assert result["cli_version"] == "2.2.0"
    assert result["status"] == "passed"
    assert result["cli_validation"] == "passed"
    assert result["planning_complete"] is True
    assert main(["handover", "validate", "--input", str(implementation), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "passed"
    (implementation / "specs/data-product-draft/spec.md").write_text(
        "# Invalid specification\n"
    )
    broken = validate_openspec_handover(implementation)
    assert broken["status"] == "failed"
    assert broken["cli_validation"] == "failed"
