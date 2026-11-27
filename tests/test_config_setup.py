"""Offline tests for guided configuration and status."""

import json
import os

import pytest
import yaml

from open_data_products import _config_setup as setup
from open_data_products.cli import main


def _interactive(monkeypatch, answers, secrets):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    replies = iter(answers)
    private = iter(secrets)
    monkeypatch.setattr("builtins.input", lambda prompt: next(replies))
    monkeypatch.setattr(setup.getpass, "getpass", lambda prompt: next(private))


def test_full_setup_preserves_existing_values_and_hides_credentials(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").write_text(
        "input: old-input\n", encoding="utf-8"
    )
    (tmp_path / "connections.yaml").write_text(
        "version: 1\nconnections:\n  untouched:\n    platform: future\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("KEEP_THIS=old\n", encoding="utf-8")
    _interactive(
        monkeypatch,
        [
            "4",
            "openai",
            "model-example",
            "",
            "https://metadata.example.org",
            "",
            "https://jira.example.org",
            "TEST",
            "10001",
            "y",
        ],
        [
            "fake-llm-secret",
            "fake-metadata-secret",
            "person@example.invalid",
            "fake-jira-secret",
        ],
    )
    assert main(["config", "setup"]) == 0
    output = capsys.readouterr().out
    assert "fake-llm-secret" not in output
    assert "fake-metadata-secret" not in output
    assert "fake-jira-secret" not in output
    assert "person@example.invalid" not in output
    gen = yaml.safe_load((tmp_path / "generation.config.yaml").read_text())
    connections = yaml.safe_load((tmp_path / "connections.yaml").read_text())
    env = (tmp_path / ".env").read_text()
    assert gen["input"] == "old-input"
    assert connections["connections"]["untouched"]["platform"] == "future"
    assert connections["connections"]["jira"]["platform"] == "jira_cloud"
    assert "KEEP_THIS=old" in env
    assert (tmp_path / ".env").stat().st_mode & 0o777 == 0o600
    for key in (
        "OPENAI_API_KEY",
        "OPENMETADATA_TOKEN",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "JIRA_PROJECT",
        "JIRA_ISSUE_TYPE_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    assert main(["config", "status", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["generation"]["credential"] == "present"
    assert {x["name"]: x["status"] for x in status["connections"]} == {
        "untouched": "unsupported platform",
        "openmetadata": "configured",
        "jira": "configured",
    }
    assert "fake-llm-secret" not in json.dumps(status)
    assert "OPENAI_API_KEY" not in os.environ


def test_setup_decline_does_not_write(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch, ["1", "openai", "model-example", "n"], ["fake-secret"])
    assert main(["config", "setup"]) == 0
    assert not (tmp_path / "generation.config.yaml").exists()
    assert not (tmp_path / ".env").exists()
    assert "fake-secret" not in capsys.readouterr().out


def test_setup_selects_existing_custom_provider_and_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    existing = {
        "provider": "company",
        "providers": {
            "company": {
                "type": "openai-chat",
                "baseUrl": "https://llm.example.org/v1",
                "model": "old-model",
                "apiKeyEnv": "COMPANY_API_KEY",
            }
        },
    }
    (tmp_path / "generation.config.yaml").write_text(yaml.safe_dump(existing))
    _interactive(monkeypatch, ["1", "company", "new-model", "y"], [""])
    assert main(["config", "setup"]) == 0
    config = yaml.safe_load((tmp_path / "generation.config.yaml").read_text())
    assert config["providers"]["company"]["model"] == "new-model"
    assert config["providers"]["company"]["baseUrl"] == "https://llm.example.org/v1"
    assert config["providers"]["company"]["apiKeyEnv"] == "COMPANY_API_KEY"


def test_setup_adds_custom_hosted_provider_and_keeps_secret_out_of_yaml(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    _interactive(
        monkeypatch,
        [
            "1",
            "company",
            "openai-chat",
            "https://llm.example.org/v1",
            "COMPANY_API_KEY",
            "company-model",
            "y",
        ],
        ["fake-custom-secret"],
    )
    assert main(["config", "setup"]) == 0
    config_text = (tmp_path / "generation.config.yaml").read_text()
    config = yaml.safe_load(config_text)
    assert config["provider"] == "company"
    assert config["providers"]["company"] == {
        "type": "openai-chat",
        "baseUrl": "https://llm.example.org/v1",
        "apiKeyEnv": "COMPANY_API_KEY",
        "model": "company-model",
    }
    assert "fake-custom-secret" not in config_text
    assert "fake-custom-secret" not in capsys.readouterr().out
    assert "fake-custom-secret" in (tmp_path / ".env").read_text()


def test_setup_supports_custom_local_provider_without_api_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _interactive(
        monkeypatch,
        [
            "1",
            "local",
            "openai-chat",
            "http://localhost:1234/v1",
            "",
            "local-model",
            "y",
        ],
        [],
    )
    assert main(["config", "setup"]) == 0
    config = yaml.safe_load((tmp_path / "generation.config.yaml").read_text())
    assert "apiKeyEnv" not in config["providers"]["local"]
    assert not (tmp_path / ".env").exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.example.org/v1",
        "https://secret@example.org/v1",
        "https://example.org/v1?token=x",
    ],
)
def test_setup_rejects_unsafe_custom_provider_url(tmp_path, monkeypatch, url):
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch, ["1", "custom", "openai-chat", url], [])
    assert main(["config", "setup"]) == 1
    assert not (tmp_path / "generation.config.yaml").exists()


def test_setup_rejects_invalid_url_before_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch, ["2", "", "http://metadata.invalid", "n"], [])
    assert main(["config", "setup"]) == 1
    assert not (tmp_path / "connections.yaml").exists()


def test_setup_allows_http_only_after_explicit_transport_confirmation(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _interactive(
        monkeypatch,
        ["2", "", "http://metadata.example.org:8585", "y", "y"],
        ["fake-secret"],
    )
    assert main(["config", "setup"]) == 0
    config = yaml.safe_load((tmp_path / "connections.yaml").read_text())
    assert config["connections"]["openmetadata"]["http"]["allow_insecure_http"] is True


def test_status_prefers_process_environment_and_does_not_leak(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").write_text(
        "provider: openai\n", encoding="utf-8"
    )
    (tmp_path / ".env").write_text("OPENAI_API_KEY=file-value\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "process-value")
    assert main(["config", "status", "--json"]) == 0
    text = capsys.readouterr().out
    assert json.loads(text)["generation"]["credential"] == "present"
    assert "process-value" not in text and "file-value" not in text
    assert os.environ["OPENAI_API_KEY"] == "process-value"


def test_setup_does_not_overwrite_symlink(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").symlink_to(tmp_path / "target")
    _interactive(monkeypatch, ["1"], [])
    assert main(["config", "setup"]) == 1
    assert not (tmp_path / "target").exists()


def test_named_metadata_profiles_use_distinct_credential_variables(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _interactive(
        monkeypatch,
        ["2", "analytics", "https://metadata.example.org", "y"],
        ["fake-secret"],
    )
    assert main(["config", "setup"]) == 0
    config = yaml.safe_load((tmp_path / "connections.yaml").read_text())
    token = config["connections"]["analytics"]["auth"]["token"]
    assert token["name"] == "OPENMETADATA_ANALYTICS_TOKEN"
    assert "OPENMETADATA_ANALYTICS_TOKEN=" in (tmp_path / ".env").read_text()


def test_existing_keychain_and_read_only_settings_are_preserved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile = {
        "platform": "openmetadata",
        "base_url": "https://old.example.org",
        "read_only": True,
        "auth": {
            "type": "bearer_token",
            "token": {
                "source": "keychain",
                "service": "test-service",
                "account": "test-account",
            },
        },
        "http": {"timeout_seconds": 15},
    }
    (tmp_path / "connections.yaml").write_text(
        yaml.safe_dump({"version": 1, "connections": {"openmetadata": profile}})
    )
    _interactive(monkeypatch, ["2", "", "https://new.example.org", "y"], [])
    assert main(["config", "setup"]) == 0
    saved = yaml.safe_load((tmp_path / "connections.yaml").read_text())["connections"][
        "openmetadata"
    ]
    assert saved["auth"] == profile["auth"]
    assert saved["http"] == profile["http"]
    assert saved["read_only"] is True
    assert saved["base_url"] == "https://new.example.org"
    assert not (tmp_path / ".env").exists()


def test_review_stops_if_config_changed_before_save(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    replies = iter(["1", "openai", "model-example"])

    def answer(prompt):
        if prompt.startswith("Save"):
            (tmp_path / "generation.config.yaml").write_text("provider: other\n")
            return "y"
        return next(replies)

    monkeypatch.setattr("builtins.input", answer)
    monkeypatch.setattr(setup.getpass, "getpass", lambda prompt: "fake-secret")
    assert main(["config", "setup"]) == 1
    assert (tmp_path / "generation.config.yaml").read_text() == "provider: other\n"
    assert not (tmp_path / ".env").exists()
    assert "fake-secret" not in capsys.readouterr().out


def test_status_test_uses_read_only_connection_checks(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    config = {
        "version": 1,
        "default_connection": "om",
        "connections": {
            "om": {
                "platform": "openmetadata",
                "base_url": "https://metadata.example.org",
                "read_only": True,
                "auth": {
                    "type": "bearer_token",
                    "token": {"source": "env", "name": "OM_TOKEN"},
                },
            },
            "jira": {
                "platform": "jira_cloud",
                "base_url": "https://jira.example.org",
                "read_only": False,
                "auth": {
                    "type": "basic_env",
                    "email_env": "JIRA_EMAIL",
                    "token_env": "JIRA_TOKEN",
                },
            },
        },
    }
    (tmp_path / "connections.yaml").write_text(yaml.safe_dump(config))
    calls = []

    class Adapter:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def check_connection(self):
            calls.append("metadata read")

    class Jira:
        def __init__(self, _profile):
            pass

        def _request(self, method, path):
            calls.append((method, path))

    monkeypatch.setattr(setup, "open_integration", lambda _profile: Adapter())
    monkeypatch.setattr(setup, "JiraCloudAdapter", Jira)
    assert main(["config", "status", "--test", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert len(calls) == 2
    assert ("GET", "myself") in calls and "metadata read" in calls
    assert all(x["connectivity"] == "passed" for x in status["connections"])
    assert "LLM connectivity was not tested" in status["notes"][0]


def test_status_test_reports_failure_without_exposing_error(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "connections.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "connections": {
                    "jira": {
                        "platform": "jira_cloud",
                        "base_url": "https://jira.example.org",
                        "read_only": True,
                        "auth": {
                            "type": "basic_env",
                            "email_env": "JIRA_EMAIL",
                            "token_env": "JIRA_TOKEN",
                        },
                    }
                },
            }
        )
    )

    class Jira:
        def __init__(self, _profile):
            pass

        def _request(self, *_args):
            raise ValueError("HTTP 401 fake-secret-in-error")

    monkeypatch.setattr(setup, "JiraCloudAdapter", Jira)
    assert main(["config", "status", "--test", "--json"]) == 1
    text = capsys.readouterr().out
    assert "fake-secret-in-error" not in text
    assert "failed" in text
    assert "HTTP 401" in text


def test_llm_add_lists_and_selects_custom_provider(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").write_text(
        "provider: ollama\n", encoding="utf-8"
    )
    _interactive(
        monkeypatch,
        [
            "company",
            "openai-chat",
            "https://llm.example.org/v1",
            "COMPANY_API_KEY",
            "company-model",
            "y",
        ],
        ["fake-provider-secret"],
    )
    assert main(["config", "llm", "add"]) == 0
    output = capsys.readouterr().out
    assert "fake-provider-secret" not in output
    assert "active provider will not change" in output
    config = yaml.safe_load((tmp_path / "generation.config.yaml").read_text())
    assert config["provider"] == "ollama"
    assert config["providers"]["company"]["model"] == "company-model"
    assert main(["config", "llm", "list", "--json"]) == 0
    listed = {
        item["name"]: item for item in json.loads(capsys.readouterr().out)["providers"]
    }
    assert listed["company"]["configured"] and not listed["company"]["active"]
    assert listed["ollama"]["active"] and listed["ollama"]["built_in"]
    _interactive(monkeypatch, ["y"], [])
    assert main(["config", "llm", "use", "--name", "company"]) == 0
    assert (
        yaml.safe_load((tmp_path / "generation.config.yaml").read_text())["provider"]
        == "company"
    )


def test_llm_add_rejects_existing_provider_without_modifying_config(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    source = "provider: ollama\nproviders:\n  company:\n    type: openai-chat\n    model: original\n"
    (tmp_path / "generation.config.yaml").write_text(source)
    _interactive(monkeypatch, ["company"], [])
    assert main(["config", "llm", "add"]) == 1
    assert (tmp_path / "generation.config.yaml").read_text() == source


def test_llm_use_decline_and_unknown_leave_file_unchanged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = "provider: ollama\nproviders:\n  company:\n    type: openai-chat\n    model: original\n"
    (tmp_path / "generation.config.yaml").write_text(source)
    _interactive(monkeypatch, ["n"], [])
    assert main(["config", "llm", "use", "--name", "company"]) == 0
    assert (tmp_path / "generation.config.yaml").read_text() == source
    assert main(["config", "llm", "use", "--name", "missing"]) == 1
    assert (tmp_path / "generation.config.yaml").read_text() == source


def test_first_run_requires_llm_setup_but_not_offline_commands(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    assert main([]) == 0
    assert "open-data-products config setup" in capsys.readouterr().out
    assert main(["resources", "--json"]) == 0
    capsys.readouterr()
    assert main(["generate", "--kind", "signal"]) == 1
    assert "open-data-products config setup" in capsys.readouterr().err
    assert main(["handover", "prepare", "--input", "brief.md"]) == 1
    assert "open-data-products config setup" in capsys.readouterr().err


def test_generate_uses_project_setup_and_env(tmp_path, monkeypatch, capsys):
    from open_data_products import generation

    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").write_text(
        "provider: company\nproviders:\n  company:\n    type: openai-chat\n    model: company-model\n    apiKeyEnv: COMPANY_API_KEY\n"
    )
    (tmp_path / ".env").write_text("COMPANY_API_KEY=fake-secret\n")
    monkeypatch.delenv("COMPANY_API_KEY", raising=False)
    observed = {}

    def client(settings):
        observed["provider"] = settings.provider
        observed["model"] = settings.model
        observed["credential"] = os.environ.get("COMPANY_API_KEY")
        return lambda *_args: ""

    monkeypatch.setattr(generation, "create_generation_client", client)
    monkeypatch.setattr(
        generation, "generate_local_artifacts_for_kind", lambda *args, **kwargs: []
    )
    assert main(["generate", "--kind", "signal", "--json"]) == 0
    assert observed == {
        "provider": "company",
        "model": "company-model",
        "credential": "fake-secret",
    }
    assert "fake-secret" not in capsys.readouterr().out
    monkeypatch.delenv("COMPANY_API_KEY", raising=False)


def test_mixed_connection_configuration_lists_both_platforms(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    config = {
        "version": 1,
        "default_connection": "openmetadata",
        "connections": {
            "openmetadata": {
                "platform": "openmetadata",
                "base_url": "https://metadata.example.org",
                "read_only": False,
                "auth": {
                    "type": "bearer_token",
                    "token": {"source": "env", "name": "OM_TOKEN"},
                },
            },
            "jira": {
                "platform": "jira_cloud",
                "base_url": "https://jira.example.org",
                "read_only": False,
                "auth": {
                    "type": "basic_env",
                    "email_env": "JIRA_EMAIL",
                    "token_env": "JIRA_TOKEN",
                },
            },
        },
    }
    (tmp_path / "connections.yaml").write_text(yaml.safe_dump(config))
    assert main(["integrations", "list", "--config", "connections.yaml", "--json"]) == 0
    assert {item["platform"] for item in json.loads(capsys.readouterr().out)} == {
        "openmetadata",
        "jira_cloud",
    }
    from open_data_products.integrations._guided_cli import _select

    assert _select("connections.yaml", "openmetadata")[1].platform == "openmetadata"


def test_connection_commands_add_list_and_edit(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _interactive(
        monkeypatch,
        ["1", "catalog", "https://metadata.example.org", "", "y"],
        ["fake-connection-secret"],
    )
    assert main(["config", "connections", "add"]) == 0
    assert "fake-connection-secret" not in capsys.readouterr().out
    assert main(["config", "connections", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)["connections"]
    assert listed[0]["name"] == "catalog" and listed[0]["mode"] == "read-write"
    before = (tmp_path / ".env").read_text()
    _interactive(monkeypatch, ["https://new.example.org", "read-only", "y"], [""])
    assert main(["config", "connections", "edit", "--name", "catalog"]) == 0
    saved = yaml.safe_load((tmp_path / "connections.yaml").read_text())["connections"][
        "catalog"
    ]
    assert saved["base_url"] == "https://new.example.org"
    assert saved["read_only"] is True
    assert (tmp_path / ".env").read_text() == before


def test_connection_add_rejects_existing_name_and_lists_future_platform(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    original = {
        "version": 1,
        "connections": {
            "future": {"platform": "datahub", "base_url": "https://future.example.org"}
        },
    }
    (tmp_path / "connections.yaml").write_text(yaml.safe_dump(original))
    assert main(["config", "connections", "list", "--json"]) == 0
    entry = json.loads(capsys.readouterr().out)["connections"][0]
    assert entry["name"] == "future" and entry["supported"] is False
    _interactive(monkeypatch, ["1", "future"], [])
    assert main(["config", "connections", "add"]) == 1
    assert yaml.safe_load((tmp_path / "connections.yaml").read_text()) == original


def test_config_show_presents_one_redacted_view(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").write_text(
        "provider: company\nproviders:\n  company:\n    type: openai-chat\n    model: sample-model\n    baseUrl: https://user:password@llm.example.org/private?token=secret\n    apiKeyEnv: COMPANY_KEY\n"
    )
    config = {
        "version": 1,
        "default_connection": "jira",
        "connections": {
            "jira": {
                "platform": "jira_cloud",
                "base_url": "https://jira.example.org",
                "read_only": False,
                "auth": {
                    "type": "basic_env",
                    "email_env": "TEST_EMAIL",
                    "token_env": "TEST_TOKEN",
                },
            }
        },
    }
    (tmp_path / "connections.yaml").write_text(yaml.safe_dump(config))
    (tmp_path / ".env").write_text(
        "COMPANY_KEY=fake-llm-secret\nTEST_EMAIL=person@example.org\nTEST_TOKEN=fake-jira-secret\nJIRA_PROJECT=DEMO\nJIRA_ISSUE_TYPE_ID=10001\n"
    )
    for name in (
        "COMPANY_KEY",
        "TEST_EMAIL",
        "TEST_TOKEN",
        "JIRA_PROJECT",
        "JIRA_ISSUE_TYPE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    assert main(["config", "show"]) == 0
    text = capsys.readouterr().out
    for expected in (
        "company",
        "sample-model",
        "COMPANY_KEY",
        "TEST_EMAIL",
        "TEST_TOKEN",
        "https://llm.example.org",
        "jira",
        "https://jira.example.org",
        "DEMO",
        "10001",
    ):
        assert expected in text
    for secret in (
        "fake-llm-secret",
        "fake-jira-secret",
        "password",
        "token=secret",
        "/private",
        "person@example.org",
    ):
        assert secret not in text
    assert main(["config", "show", "--json"]) == 0
    view = json.loads(capsys.readouterr().out)
    assert view["connections"][0]["default"] is True


def test_credential_command_hides_value_and_preserves_other_settings(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("KEEP=unchanged\nTOKEN=old-value\n")
    _interactive(monkeypatch, ["y"], ["new secret # value"])
    assert main(["config", "credentials", "set", "--name", "TOKEN"]) == 0
    output = capsys.readouterr().out
    assert "new secret # value" not in output and "old-value" not in output
    env = (tmp_path / ".env").read_text()
    assert "KEEP=unchanged" in env and "old-value" not in env
    assert (tmp_path / ".env").stat().st_mode & 0o777 == 0o600
    monkeypatch.delenv("TOKEN", raising=False)
    monkeypatch.delenv("KEEP", raising=False)
    setup._load_env_file(".env")
    assert os.environ["TOKEN"] == "new secret # value"
    monkeypatch.delenv("TOKEN", raising=False)
    monkeypatch.delenv("KEEP", raising=False)


def test_credential_command_decline_leaves_existing_secret_untouched(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("TOKEN=old-value\n")
    _interactive(monkeypatch, ["n"], ["new-value"])
    assert main(["config", "credentials", "set", "--name", "TOKEN"]) == 0
    assert (tmp_path / ".env").read_text() == "TOKEN=old-value\n"
    assert "new-value" not in capsys.readouterr().out


def test_config_test_calls_model_without_printing_response_or_secrets(
    tmp_path, monkeypatch, capsys
):
    from open_data_products import generation

    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").write_text(
        "provider: company\nproviders:\n  company:\n    type: openai-chat\n    model: test-model\n    apiKeyEnv: TEST_API_KEY\n"
    )
    (tmp_path / ".env").write_text("TEST_API_KEY=fake-secret\n")
    monkeypatch.delenv("TEST_API_KEY", raising=False)
    requests = []

    def client(settings):
        assert os.environ["TEST_API_KEY"] == "fake-secret"
        return (
            lambda prompt, model: requests.append((prompt, model))
            or "model-response-not-for-display"
        )

    monkeypatch.setattr(generation, "create_generation_client", client)
    assert main(["config", "test", "--json"]) == 0
    text = capsys.readouterr().out
    assert "fake-secret" not in text and "model-response-not-for-display" not in text
    assert json.loads(text)["generation"]["connectivity"] == "passed"
    assert requests == [("Reply with OK.", "test-model")]
    assert "TEST_API_KEY" not in os.environ


def test_config_test_reports_missing_provider_and_failed_model_safely(
    tmp_path, monkeypatch, capsys
):
    from open_data_products import generation

    monkeypatch.chdir(tmp_path)
    assert main(["config", "test", "--json"]) == 1
    capsys.readouterr()
    (tmp_path / "generation.config.yaml").write_text("provider: ollama\n")
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: lambda *args: (_ for _ in ()).throw(
            ValueError("secret-in-provider-error")
        ),
    )
    assert main(["config", "test", "--json"]) == 1
    text = capsys.readouterr().out
    assert "secret-in-provider-error" not in text
    assert json.loads(text)["generation"]["connectivity"].startswith("failed")


def test_setup_shows_existing_state_and_specific_next_step(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").write_text(
        "provider: openai\nproviders:\n  openai:\n    type: openai\n    model: test-model\n    apiKeyEnv: TEST_SETUP_KEY\n"
    )
    monkeypatch.delenv("TEST_SETUP_KEY", raising=False)
    _interactive(monkeypatch, ["1", "openai", "", "n"], [""])
    assert main(["config", "setup"]) == 0
    output = capsys.readouterr().out
    assert "Current settings (local checks only)" in output
    assert "openai / test-model; credential missing" in output
    assert "OpenMetadata: not configured" in output
    assert "Jira: not configured" in output
    assert "No files changed" in output


def test_status_reports_actionable_missing_credentials_without_values(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").write_text(
        "provider: openai\nproviders:\n  openai:\n    type: openai\n    model: test-model\n    apiKeyEnv: TEST_SETUP_KEY\n"
    )
    monkeypatch.delenv("TEST_SETUP_KEY", raising=False)
    assert main(["config", "show", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {
        "scope": "LLM",
        "reason": "credential missing",
        "command": "open-data-products config credentials set --name TEST_SETUP_KEY",
    } in payload["next_steps"]


def test_generation_missing_credential_reports_specific_command(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").write_text(
        "provider: company\nproviders:\n  company:\n    type: openai-chat\n    model: example\n    apiKeyEnv: TEST_SETUP_KEY\n"
    )
    monkeypatch.delenv("TEST_SETUP_KEY", raising=False)
    assert main(["generate", "--kind", "signal"]) == 1
    assert (
        "open-data-products config credentials set --name TEST_SETUP_KEY"
        in capsys.readouterr().err
    )


def test_platform_missing_credentials_offer_specific_commands(monkeypatch):
    from open_data_products.integrations.config import (
        ConnectionProfile,
        ConfigurationError,
        IntegrationError,
    )
    from open_data_products.integrations.jira import JiraCloudAdapter, JiraConnection

    monkeypatch.delenv("TEST_OM_TOKEN", raising=False)
    metadata = ConnectionProfile(
        name="metadata",
        platform="openmetadata",
        base_url="https://metadata.example.org",
        token_env="TEST_OM_TOKEN",
    )
    with pytest.raises(
        ConfigurationError, match="config credentials set --name TEST_OM_TOKEN"
    ):
        metadata.token()
    monkeypatch.delenv("TEST_JIRA_EMAIL", raising=False)
    monkeypatch.delenv("TEST_JIRA_TOKEN", raising=False)
    jira = JiraCloudAdapter(
        JiraConnection(
            name="jira",
            base_url="https://jira.example.org",
            email_env="TEST_JIRA_EMAIL",
            token_env="TEST_JIRA_TOKEN",
        )
    )
    with pytest.raises(
        IntegrationError, match="config credentials set --name TEST_JIRA_EMAIL"
    ):
        jira._request("GET", "myself")


def test_test_reports_safe_action_for_auth_failure(tmp_path, monkeypatch, capsys):
    from open_data_products import generation

    monkeypatch.chdir(tmp_path)
    (tmp_path / "generation.config.yaml").write_text(
        "provider: openai\nproviders:\n  openai:\n    type: openai\n    model: test-model\n    apiKeyEnv: TEST_SETUP_KEY\n"
    )
    monkeypatch.setenv("TEST_SETUP_KEY", "fake-secret")
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: lambda *args: (_ for _ in ()).throw(
            ValueError("HTTP 401 fake-secret")
        ),
    )
    assert main(["config", "test", "--json"]) == 1
    text = capsys.readouterr().out
    assert "fake-secret" not in text
    assert {
        "scope": "LLM",
        "reason": "authentication failed (HTTP 401)",
        "command": "open-data-products config credentials set --name TEST_SETUP_KEY",
    } in json.loads(text)["next_steps"]
