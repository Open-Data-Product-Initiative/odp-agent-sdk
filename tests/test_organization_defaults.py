"""Organization settings and ODPS data holder defaults."""

import json
from pathlib import Path

import pytest
import yaml

from open_data_products._organization import (
    FIELDS,
    apply_organization,
    load_organization,
)
from open_data_products.generation import generate_local_artifacts_for_kind
from open_data_products.contracts import wrap_contract


def config():
    holder = {field: "Synthetic " + field for field in FIELDS}
    holder.update(
        email="contact@example.com",
        URL="https://example.test",
        logoURL="https://example.test/logo",
        ratingCount=3,
        addressCountry="FI",
    )
    return {"version": 1, "language": "en", "dataHolder": holder}


def save_config(tmp_path, value):
    directory = tmp_path / ".open-data-products"
    directory.mkdir(exist_ok=True)
    (directory / "organization.yaml").write_text(yaml.safe_dump(value))


@pytest.mark.parametrize("version", ["4.1", "4.2"])
def test_all_organization_fields_are_applied_and_existing_conflicts_preserved(version):
    document = {"version": version, "product": {}}
    assert apply_organization(document, config())
    actual = document["product"]["dataHolder"]
    assert (actual if version == "4.1" else actual["en"]) == config()["dataHolder"]
    conflicting = {"legalName": "Different organization"}
    document["product"]["dataHolder"] = (
        conflicting if version == "4.1" else {"en": conflicting}
    )
    assert "differs" in apply_organization(document, config())[0]
    assert conflicting == {"legalName": "Different organization"}


def test_matching_holder_fills_missing_fields_without_overwriting():
    document = {
        "version": "4.1",
        "product": {
            "dataHolder": {
                "legalName": "Synthetic legalName",
                "email": "existing@example.test",
            }
        },
    }
    notes = apply_organization(document, config())
    assert document["product"]["dataHolder"]["businessID"] == "Synthetic businessID"
    assert document["product"]["dataHolder"]["email"] == "existing@example.test"
    assert any("conflicts" in note and "email" in note for note in notes)


def test_generation_applies_settings_after_provider_calls(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_config(tmp_path, config())
    source = tmp_path / "brief.md"
    source.write_text("A product for synthetic customers.")
    prompts = []

    def client(prompt, model):
        prompts.append(prompt)
        if prompt.startswith("# Extract ODPS Product Facts"):
            return "product:\n  productID: test\n  name: Test\nevidenceGaps: []\n"
        return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: '4.1'
product:
  productID: test
  name: Test
  visibility: private
  status: draft
  type: dataset
"""

    artifact = generate_local_artifacts_for_kind(
        "odps-product", source, tmp_path / "out", client=client
    )[0]
    assert artifact.valid_yaml
    assert (
        yaml.safe_load(artifact.output_path.read_text())["product"]["dataHolder"]
        == config()["dataHolder"]
    )
    assert all("Synthetic legalName" not in prompt for prompt in prompts)
    assert any("Configured organization" in note for note in artifact.review_notes)


def test_offline_contract_wrapper_applies_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_config(tmp_path, config())
    contract = tmp_path / "contract.yaml"
    contract.write_text(
        "apiVersion: v3.1.0\nkind: DataContract\nid: TEST\nname: Test\nversion: 1.0.0\n"
    )
    result = wrap_contract(str(contract))
    assert result.validation.valid
    assert result.document["product"]["dataHolder"]["en"] == config()["dataHolder"]
    assert any("Configured organization" in warning for warning in result.warnings)


def test_organization_rejects_unknown_fields_and_symlink(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    invalid = config()
    invalid["dataHolder"]["invented"] = "bad"
    save_config(tmp_path, invalid)
    with pytest.raises(ValueError, match="unsupported"):
        load_organization()
    path = tmp_path / ".open-data-products" / "organization.yaml"
    path.unlink()
    path.symlink_to(tmp_path / "other")
    with pytest.raises(ValueError, match="symbolic"):
        load_organization()


def test_mcp_review_binds_organization(tmp_path, monkeypatch):
    from open_data_products.mcp._handover import _business_review

    monkeypatch.chdir(tmp_path)
    source = tmp_path / "brief.md"
    source.write_text("A product for synthetic customers.")
    save_config(tmp_path, config())
    args = {
        "business_document": str(source),
        "output": str(tmp_path / "out"),
        "provider": "openai",
        "model": "test",
    }
    first = _business_review(args)[-1]
    changed = config()
    changed["dataHolder"]["email"] = "different@example.test"
    save_config(tmp_path, changed)
    assert _business_review(args)[-1] != first


def test_interactive_organization_setup_and_status(tmp_path, monkeypatch, capsys):
    from open_data_products.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    answers = iter(
        [
            "",
            "Example Inc",
            "BUS-1",
            "",
            "person@example.com",
            "https://example.com",
            "",
            "",
            "n",
            "y",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert main(["config", "organization", "edit"]) == 0
    assert load_organization()["dataHolder"]["businessID"] == "BUS-1"
    assert main(["config", "show", "--json"]) == 0
    output = capsys.readouterr().out
    assert "Organization defaults saved" in output
    assert '"legalName": "Example Inc"' in output
    assert (
        tmp_path / ".open-data-products/organization.yaml"
    ).stat().st_mode & 0o777 == 0o600


def test_holder_without_optional_email_remains_valid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_config(
        tmp_path,
        {"version": 1, "language": "en", "dataHolder": {"legalName": "Example Inc"}},
    )
    contract = tmp_path / "contract.yaml"
    contract.write_text(
        "apiVersion: v3.1.0\nkind: DataContract\nid: TEST\nname: Test\nversion: 1.0.0\n"
    )
    assert wrap_contract(str(contract)).validation.valid


def test_dcat_and_dprod_wrappers_apply_organization(tmp_path, monkeypatch):
    from open_data_products.dcat import wrap_dcat_resource
    from open_data_products.dprod import wrap_dprod_resource

    fixture_root = Path(__file__).parent / "fixtures"
    monkeypatch.chdir(tmp_path)
    save_config(
        tmp_path,
        {
            "version": 1,
            "language": "en",
            "dataHolder": {"legalName": "Configured Organization"},
        },
    )
    dcat = wrap_dcat_resource(
        str(fixture_root / "dcat-dprod" / "valid-catalog.ttl"),
        "https://fixtures.example.test/datasets/air-quality",
    )
    dprod = wrap_dprod_resource(
        str(fixture_root / "dcat-dprod" / "valid-product.ttl"),
        "https://fixtures.example.test/products/air-quality",
    )
    for result in (dcat, dprod):
        assert (
            result.document["product"]["dataHolder"]["en"]["legalName"]
            == "Configured Organization"
        )
        assert result.validation.valid
        assert any("Configured organization" in item for item in result.warnings)
