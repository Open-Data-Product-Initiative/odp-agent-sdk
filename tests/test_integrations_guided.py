"""Short platform CLI workflows with isolated configuration and fake adapters."""

from dataclasses import dataclass
import json
from types import SimpleNamespace

import pytest
import yaml

from open_data_products.cli import main
from open_data_products.integrations import UnknownCreateOutcome
from open_data_products.integrations import _guided_cli as guided


@dataclass
class Page:
    products: list
    after: object = None
    provenance: object = None


@dataclass
class Provenance:
    source: str = "test"


class Review:
    def __init__(self, name, valid=True):
        self.product_id = name
        self.review_sha256 = "digest-" + name
        self.executable = valid

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "product_name": self.product_id,
            "validation": {
                "valid": self.executable,
                "errors": [] if self.executable else ["Invalid"],
            },
            "unsupported_fields": ["/product/contract"],
            "executable": self.executable,
        }


class FakeAdapter:
    def __init__(self, profile):
        self.profile = profile
        self.calls = []
        self.items = []
        self.duplicates = set()
        self.failures = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def check_connection(self):
        return {"status": "connected"}

    def list_products(self, **kwargs):
        return Page(self.items, provenance=Provenance())

    def list_products_odpc(self, **kwargs):
        return {
            "schema": "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml",
            "version": "1.0",
            "kind": "Catalog",
            "catalog": {
                "metadata": {
                    "id": "test",
                    "name": {"en": "Test"},
                    "description": {"en": "Test"},
                },
                "productReferences": [],
            },
        }

    def search_products(self, query):
        return Page(self.items, provenance=Provenance())

    def search_products_odpc(self, query, **kwargs):
        return self.list_products_odpc()

    def review_create(self, text, **kwargs):
        data = yaml.safe_load(text)
        return Review(data["name"], data.get("valid", True))

    def find_create_candidates(self, text, **kwargs):
        name = yaml.safe_load(text)["name"]
        return {
            "complete": True,
            "candidates": [{"id": "existing"}] if name in self.duplicates else [],
        }

    def create_product(self, text, **kwargs):
        name = yaml.safe_load(text)["name"]
        self.calls.append((name, kwargs))
        if name in self.failures:
            raise self.failures[name]
        assert kwargs["reviewed_sha256"] == "digest-" + name
        return SimpleNamespace(
            status="created", to_dict=lambda: {"status": "created", "product_id": name}
        )


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "connections.yaml"
    config.write_text(
        """version: 1\ndefault_connection: alpha\nconnections:\n  alpha:\n    platform: openmetadata\n    base_url: https://example.test\n    read_only: false\n    auth: {type: bearer_token, token: {source: env, name: TEST_TOKEN}}\n  beta:\n    platform: openmetadata\n    base_url: https://example.test\n    read_only: true\n    auth: {type: bearer_token, token: {source: env, name: TEST_TOKEN}}\n"""
    )
    adapters = []

    def factory(profile):
        adapter = FakeAdapter(profile)
        adapters.append(adapter)
        return adapter

    monkeypatch.setattr(guided, "open_integration", factory)
    return config, adapters


def test_connect_saves_default_and_explicit_override(setup, capsys):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["connection"] == "alpha"
    assert main(["products", "list", "--connection", "beta", "--json"]) == 0
    assert adapters[-1].profile.name == "beta"
    assert json.loads(capsys.readouterr().out)["catalog"]["productReferences"] == []
    assert main(["products", "list", "--json"]) == 0
    assert adapters[-1].profile.name == "alpha"


def test_explicit_openmetadata_command_creates_via_review(
    setup, monkeypatch, capsys, tmp_path
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    source = tmp_path / "product.yaml"
    source.write_text("name: one\n")
    assert main(["openmetadata", "create", str(source), "--domain", "Banking"]) == 0
    assert adapter.calls[0][0] == "one"
    assert "Platform: openmetadata" in capsys.readouterr().out


def test_guided_create_accepts_multiword_domain_fqn(
    setup, monkeypatch, capsys, tmp_path
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    source = tmp_path / "product.yaml"
    source.write_text("name: one\n")
    assert (
        main(
            [
                "openmetadata",
                "products",
                "create",
                str(source),
                "--domain",
                "Retail Banking Services",
            ]
        )
        == 0
    )
    assert adapter.calls[0][1]["domain"] == "Retail Banking Services"
    assert "Retail Banking Services" in capsys.readouterr().out


def test_explicit_openmetadata_rejects_other_platform(setup, monkeypatch, capsys):
    config, _ = setup
    monkeypatch.setattr(
        guided,
        "_select",
        lambda *args: (str(config), SimpleNamespace(platform="other")),
    )
    assert main(["openmetadata", "list", "--json"]) == 1
    assert "not an OpenMetadata" in json.loads(capsys.readouterr().out)["error"]


@pytest.mark.parametrize(
    "identifier_args",
    [
        ["Campaign Eligibility"],
        ["--id", "Campaign Eligibility"],
    ],
)
def test_get_rejects_names_without_platform_lookup(
    setup, monkeypatch, capsys, identifier_args
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    capsys.readouterr()
    adapter = FakeAdapter(adapters[0].profile)
    adapter.list_products = lambda **kwargs: pytest.fail("Name lookup is forbidden")
    adapter.get_product = lambda *args, **kwargs: pytest.fail(
        "Name retrieval is forbidden"
    )
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    assert main(["openmetadata", "products", "get"] + identifier_args + ["--json"]) == 1
    assert "UUID" in json.loads(capsys.readouterr().out)["error"]


@pytest.mark.parametrize(
    "identifier_args",
    [
        ["--id", "11111111-1111-4111-8111-111111111111"],
        ["11111111-1111-4111-8111-111111111111"],
    ],
)
def test_get_accepts_uuid_without_listing(setup, monkeypatch, capsys, identifier_args):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    capsys.readouterr()
    adapter = FakeAdapter(adapters[0].profile)
    adapter.list_products = lambda **kwargs: pytest.fail("UUID should not use listing")
    adapter.get_product = lambda ident, **kwargs: SimpleNamespace(
        data={"id": ident}, provenance=Provenance(), validation=None
    )
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    assert main(["openmetadata", "products", "get"] + identifier_args + ["--json"]) == 0
    assert (
        json.loads(capsys.readouterr().out)["data"]["id"]
        == "11111111-1111-4111-8111-111111111111"
    )


def test_folder_review_one_confirmation_and_outcomes(
    setup, monkeypatch, capsys, tmp_path
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    adapter.duplicates.add("duplicate")
    adapter.failures["uncertain"] = UnknownCreateOutcome("Outcome unknown")
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)
    prompts = []
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "y")
    folder = tmp_path / "products"
    folder.mkdir()
    for name, valid in [
        ("one", True),
        ("invalid", False),
        ("duplicate", True),
        ("uncertain", True),
    ]:
        (folder / (name + ".yaml")).write_text(
            yaml.safe_dump({"name": name, "valid": valid})
        )
    assert main(["products", "create", str(folder), "--domain", "Banking"]) == 1
    assert len(prompts) == 1
    assert [name for name, _ in adapter.calls] == ["one", "uncertain"]
    out = capsys.readouterr().out
    assert (
        "invalid" in out
        and "duplicate" in out
        and "uncertain" in out
        and "created" in out
    )


def test_changed_file_after_confirmation_is_not_created(
    setup, monkeypatch, capsys, tmp_path
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)
    source = tmp_path / "product.yaml"
    source.write_text("name: first\n")

    def confirm(prompt):
        source.write_text("name: changed\n")
        return "y"

    monkeypatch.setattr("builtins.input", confirm)
    assert main(["products", "create", str(source), "--domain", "Banking"]) == 1
    assert not adapter.calls and "Source changed" in capsys.readouterr().out


def test_noninteractive_creation_cannot_write(setup, monkeypatch, capsys, tmp_path):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    capsys.readouterr()
    monkeypatch.setattr(guided, "_interactive", lambda args: False)
    source = tmp_path / "product.yaml"
    source.write_text("name: one\n")
    assert (
        main(["products", "create", str(source), "--domain", "Banking", "--json"]) == 1
    )
    assert not adapters[-1].calls
    report = json.loads(capsys.readouterr().out)
    assert "interactive terminal" in report["message"]
    assert report["status"] == "review_only" and len(report["products"]) == 1


def test_folder_rejects_duplicate_source_identifiers_and_discovers_json(
    setup, monkeypatch, capsys, tmp_path
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: pytest.fail("No duplicate should be offered for creation"),
    )
    folder = tmp_path / "products"
    folder.mkdir()
    nested = folder / "nested"
    nested.mkdir()
    (folder / "a.yaml").write_text("name: repeated\n")
    (nested / "b.json").write_text('{"name":"repeated"}')
    assert main(["products", "create", str(folder), "--domain", "Banking"]) == 1
    assert not adapter.calls
    output = capsys.readouterr().out
    assert output.count("Multiple source files have the same product identifier") == 2


def test_confirmation_declined_never_writes(setup, monkeypatch, capsys, tmp_path):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    source = tmp_path / "one.yml"
    source.write_text("name: one\n")
    assert main(["products", "create", str(source), "--domain", "Banking"]) == 1
    assert not adapter.calls and "Not confirmed" in capsys.readouterr().out


def test_new_duplicate_after_review_is_skipped(setup, monkeypatch, capsys, tmp_path):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)

    def confirm(prompt):
        adapter.duplicates.add("one")
        return "y"

    monkeypatch.setattr("builtins.input", confirm)
    source = tmp_path / "one.yaml"
    source.write_text("name: one\n")
    assert main(["products", "create", str(source), "--domain", "Banking"]) == 1
    assert not adapter.calls and "before creation" in capsys.readouterr().out


def test_read_only_connection_is_not_executed(setup, monkeypatch, capsys, tmp_path):
    config, adapters = setup
    assert main(["connect", "beta", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    adapter.review_create = lambda *args, **kwargs: Review("one", valid=False)
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)
    source = tmp_path / "one.yaml"
    source.write_text("name: one\n")
    assert main(["products", "create", str(source), "--domain", "Banking"]) == 1
    assert not adapter.calls and "read-only" in capsys.readouterr().out


def test_explicit_config_uses_its_default(setup, capsys, tmp_path):
    config, adapters = setup
    assert main(["connect", "beta", "--config", str(config)]) == 0
    other = tmp_path / "other.yaml"
    other.write_text(config.read_text())
    assert main(["products", "list", "--config", str(other), "--json"]) == 0
    assert adapters[-1].profile.name == "alpha"
    guided.SETTINGS.write_text("not: valid\n")
    assert main(["products", "list", "--config", str(other), "--json"]) == 0
    assert adapters[-1].profile.name == "alpha"


def test_adapter_without_operation_reports_unsupported(setup, monkeypatch, capsys):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    capsys.readouterr()
    adapter = FakeAdapter(adapters[0].profile)
    adapter.search_products_odpc = None
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    assert main(["products", "search", "campaign", "--json"]) == 1
    assert "does not support" in json.loads(capsys.readouterr().out)["error"]


def test_review_digest_change_blocks_write(setup, monkeypatch, capsys, tmp_path):
    from open_data_products.integrations import IntegrationError

    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    adapter.failures["one"] = IntegrationError(
        "Product, changes or destination changed since review; review again"
    )
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    source = tmp_path / "one.yaml"
    source.write_text("name: one\n")
    assert main(["products", "create", str(source), "--domain", "Banking"]) == 1
    assert "review again" in capsys.readouterr().out


@pytest.mark.parametrize("action", ["update", "delete"])
def test_nested_mutations_reject_names_without_network(
    setup, monkeypatch, capsys, action
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    capsys.readouterr()
    adapter = FakeAdapter(adapters[0].profile)
    adapter.review_update = lambda *a, **kw: pytest.fail("Name triggered a lookup")
    adapter.update_product = lambda *a, **kw: pytest.fail("Name triggered a write")
    adapter.review_delete = lambda *a, **kw: pytest.fail("Name triggered a lookup")
    adapter.delete_product = lambda *a, **kw: pytest.fail("Name triggered a write")
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    command = [
        "openmetadata",
        "products",
        action,
        "--id",
        "Campaign Eligibility",
        "--json",
    ]
    if action == "update":
        command += ["--title", "new"]
    assert main(command) == 1
    assert "UUID" in json.loads(capsys.readouterr().out)["error"]


@pytest.mark.parametrize("action", ["update", "delete"])
def test_nested_mutations_review_and_confirm(setup, monkeypatch, capsys, action):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    calls = []
    review = SimpleNamespace(
        review_sha256="reviewed-digest",
        write_enabled=True,
        to_dict=lambda: {
            "review_sha256": "reviewed-digest",
            "permanent": action == "delete",
        },
    )
    adapter.review_update = lambda ident, **kwargs: review
    adapter.review_delete = lambda ident: review

    def update(ident, **kwargs):
        calls.append((ident, kwargs))
        return SimpleNamespace(
            comparison={"displayName": "matched"},
            to_dict=lambda: {"comparison": {"displayName": "matched"}},
        )

    def delete(ident, **kwargs):
        calls.append((ident, kwargs))
        return SimpleNamespace(
            verification="not_found_by_id",
            to_dict=lambda: {"verification": "not_found_by_id"},
        )

    adapter.update_product = update
    adapter.delete_product = delete
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)
    prompts = []
    monkeypatch.setattr(
        "builtins.input", lambda message: prompts.append(message) or "y"
    )
    ident = "11111111-1111-4111-8111-111111111111"
    command = ["openmetadata", "products", action, "--id", ident]
    if action == "update":
        command += ["--title", "new"]
    assert main(command) == 0
    assert len(prompts) == 1 and calls[0][0] == ident
    assert calls[0][1]["reviewed_sha256"] == "reviewed-digest"
    if action == "delete":
        assert "recursively" in prompts[0] and calls[0][1]["confirm_permanent"] is True


def test_noninteractive_deletion_requires_digest_and_confirmation(
    setup, monkeypatch, capsys
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    capsys.readouterr()
    adapter = FakeAdapter(adapters[0].profile)
    adapter.review_delete = lambda ident: SimpleNamespace(
        review_sha256="digest",
        write_enabled=True,
        to_dict=lambda: {"review_sha256": "digest"},
    )
    adapter.delete_product = lambda *args, **kwargs: pytest.fail("Unconfirmed delete")
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    ident = "11111111-1111-4111-8111-111111111111"
    command = [
        "openmetadata",
        "products",
        "delete",
        "--id",
        ident,
        "--execute",
        "--reviewed-sha256",
        "digest",
        "--json",
    ]
    assert main(command) == 1
    assert "confirm-permanent" in json.loads(capsys.readouterr().out)["error"]


def test_noninteractive_review_does_not_write(setup, monkeypatch, capsys):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    capsys.readouterr()
    adapter = FakeAdapter(adapters[0].profile)
    adapter.review_update = lambda *args, **kwargs: SimpleNamespace(
        review_sha256="digest",
        write_enabled=True,
        to_dict=lambda: {"review_sha256": "digest"},
    )
    adapter.update_product = lambda *args, **kwargs: pytest.fail(
        "Review performed write"
    )
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    ident = "11111111-1111-4111-8111-111111111111"
    assert (
        main(
            [
                "openmetadata",
                "products",
                "update",
                "--id",
                ident,
                "--title",
                "new",
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["review_sha256"] == "digest"


def test_nested_update_cancelled_without_write(setup, monkeypatch, capsys):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    adapter.review_update = lambda *args, **kwargs: SimpleNamespace(
        review_sha256="digest",
        write_enabled=True,
        to_dict=lambda: {"review_sha256": "digest", "proposed": {"displayName": "new"}},
    )
    adapter.update_product = lambda *args, **kwargs: pytest.fail(
        "Cancelled update was executed"
    )
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    ident = "11111111-1111-4111-8111-111111111111"
    assert (
        main(["openmetadata", "products", "update", "--id", ident, "--title", "new"])
        == 1
    )
    assert "Cancelled" in capsys.readouterr().out


def test_update_input_changed_after_confirmation_is_blocked(
    setup, monkeypatch, tmp_path, capsys
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    source = tmp_path / "product.yaml"
    source.write_text("original")
    adapter.review_update = lambda *args, **kwargs: SimpleNamespace(
        review_sha256="digest",
        write_enabled=True,
        to_dict=lambda: {"review_sha256": "digest"},
    )
    adapter.update_product = lambda *args, **kwargs: pytest.fail(
        "Changed input executed"
    )
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    monkeypatch.setattr(guided, "_interactive", lambda args: True)

    def confirm(prompt):
        source.write_text("changed")
        return "y"

    monkeypatch.setattr("builtins.input", confirm)
    ident = "11111111-1111-4111-8111-111111111111"
    assert (
        main(
            [
                "openmetadata",
                "products",
                "update",
                "--id",
                ident,
                "--input",
                str(source),
            ]
        )
        == 1
    )
    assert "changed after review" in capsys.readouterr().err


def test_nested_update_reports_changed_review(setup, monkeypatch, capsys):
    from open_data_products.integrations import IntegrationError

    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    adapter = FakeAdapter(adapters[0].profile)
    adapter.review_update = lambda *args, **kwargs: SimpleNamespace(
        review_sha256="digest",
        write_enabled=True,
        to_dict=lambda: {"review_sha256": "digest"},
    )

    def update(*args, **kwargs):
        raise IntegrationError(
            "Product, changes or destination changed since review; review again"
        )

    adapter.update_product = update
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    ident = "11111111-1111-4111-8111-111111111111"
    capsys.readouterr()
    assert (
        main(
            [
                "openmetadata",
                "products",
                "update",
                "--id",
                ident,
                "--title",
                "new",
                "--execute",
                "--reviewed-sha256",
                "old",
                "--json",
            ]
        )
        == 1
    )
    assert "review again" in json.loads(capsys.readouterr().out)["error"]


@pytest.mark.parametrize(
    "command",
    [
        ["openmetadata", "products", "compare", "Campaign Eligibility"],
        ["openmetadata", "compare", "--id", "Campaign Eligibility"],
        ["products", "compare", "Campaign Eligibility"],
    ],
)
def test_comparison_rejects_names_without_lookup(
    setup, monkeypatch, capsys, tmp_path, command
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    capsys.readouterr()
    adapter = FakeAdapter(adapters[0].profile)
    adapter.list_products = lambda **kwargs: pytest.fail(
        "Comparison performed a name lookup"
    )
    adapter.get_product = lambda *args, **kwargs: pytest.fail(
        "Comparison retrieved a name"
    )
    adapter.compare_product = lambda *args, **kwargs: pytest.fail(
        "Comparison accepted a name"
    )
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    source = tmp_path / "product.yaml"
    source.write_text("name: one\n")
    assert main(command + ["--source", str(source), "--json"]) == 1
    assert "UUID" in json.loads(capsys.readouterr().out)["error"]


@pytest.mark.parametrize(
    "identifier_args",
    [
        ["--id", "11111111-1111-4111-8111-111111111111"],
        ["11111111-1111-4111-8111-111111111111"],
    ],
)
def test_comparison_accepts_only_uuid_identifier(
    setup, monkeypatch, capsys, tmp_path, identifier_args
):
    config, adapters = setup
    assert main(["connect", "alpha", "--config", str(config)]) == 0
    capsys.readouterr()
    adapter = FakeAdapter(adapters[0].profile)
    adapter.list_products = lambda **kwargs: pytest.fail(
        "UUID should not use product listing"
    )
    adapter.get_product = lambda *args, **kwargs: pytest.fail(
        "Explicit domain should not need a lookup"
    )
    seen = []

    def compare(source, product_id, domain):
        seen.append((product_id, domain))
        return SimpleNamespace(
            source_validation=SimpleNamespace(valid=True),
            to_dict=lambda: {"product_id": product_id},
        )

    adapter.compare_product = compare
    monkeypatch.setattr(guided, "open_integration", lambda profile: adapter)
    source = tmp_path / "product.yaml"
    source.write_text("name: one\n")
    assert (
        main(
            ["openmetadata", "products", "compare"]
            + identifier_args
            + ["--source", str(source), "--domain", "Banking", "--json"]
        )
        == 0
    )
    assert seen == [("11111111-1111-4111-8111-111111111111", "Banking")]
    assert json.loads(capsys.readouterr().out)["product_id"] == seen[0][0]


@pytest.mark.parametrize("extension", ["yaml", "json"])
def test_export_odpc_catalog_without_overwrite(setup, tmp_path, capsys, extension):
    from open_data_products.odpc import validate_catalog

    config, _ = setup
    assert main(["connect", "alpha", "--config", str(config), "--json"]) == 0
    capsys.readouterr()
    output = tmp_path / ("catalog." + extension)
    command = ["openmetadata", "products", "export", "--output", str(output), "--json"]
    assert main(command) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "exported"
    catalog = yaml.safe_load(output.read_text())
    assert validate_catalog(catalog).valid
    original = output.read_bytes()
    assert main(command) == 1
    assert output.read_bytes() == original
    assert "error" in json.loads(capsys.readouterr().out)


def test_integration_config_copy_and_offline_validation(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENMETADATA_TOKEN", raising=False)
    target = tmp_path / "connections.yaml"
    assert main(["config", "integrations", "--copy-to", str(target), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["domain"] == "integrations" and report["copied_to"] == str(target)
    assert target.read_text() == guided_template_text()
    assert (
        main(["config", "integrations", "--config", str(target), "--check", "--json"])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["config", "integrations", "--copy-to", str(target)]) == 1
    assert target.read_text() == guided_template_text()


def guided_template_text():
    from open_data_products.integrations._template import TEMPLATE

    return TEMPLATE.read_text(encoding="utf-8")


def test_integration_template_matches_repository_example():
    from open_data_products.integrations._template import TEMPLATE
    from pathlib import Path

    example = (
        Path(__file__).resolve().parents[1]
        / "examples/integrations/connections.example.yaml"
    )
    assert TEMPLATE.read_text(encoding="utf-8") == example.read_text(encoding="utf-8")
