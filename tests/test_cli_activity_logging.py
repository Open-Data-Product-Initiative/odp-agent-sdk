"""Tests for CLI activity logging behavior."""

from pathlib import Path

import pytest

from open_data_products.cli import main
from open_data_products.generation.models import GeneratedArtifact

REPO_ROOT = Path(__file__).resolve().parents[1]
ODPS_PRODUCT = (
    REPO_ROOT / "examples" / "apps" / "pricing_402_builder" / "priced_product.yaml"
)


def _log_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def test_cli_writes_workspace_activity_log_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("OPEN_DATA_PRODUCTS_ACTIVITY_LOG", raising=False)
    monkeypatch.chdir(tmp_path)

    assert main(["validate", str(ODPS_PRODUCT), "--json"]) == 0

    log_path = tmp_path / ".open-data-products" / "activity.log"
    lines = _log_lines(log_path)
    assert len(lines) == 1
    assert " [SUCCESS] " in lines[0]
    assert "source=cli command=validate exit_code=0" in lines[0]
    assert '"document":"' in lines[0]
    assert capsys.readouterr().err == ""


def test_cli_activity_logging_can_be_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPEN_DATA_PRODUCTS_ACTIVITY_LOG", "0")
    monkeypatch.chdir(tmp_path)

    assert main(["validate", str(ODPS_PRODUCT), "--json"]) == 0

    assert not (tmp_path / ".open-data-products").exists()


def test_cli_explicit_activity_log_path_bypasses_workspace_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explicit_log = tmp_path / "logs" / "sdk.log"
    child = tmp_path / "workspace" / "child"
    child.mkdir(parents=True)
    (tmp_path / "workspace" / "generation.config.yaml").write_text(
        "providers: {}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPEN_DATA_PRODUCTS_ACTIVITY_LOG", raising=False)
    monkeypatch.setenv("OPEN_DATA_PRODUCTS_ACTIVITY_LOG_PATH", str(explicit_log))
    monkeypatch.chdir(child)

    assert main(["validate", str(ODPS_PRODUCT), "--json"]) == 0

    assert explicit_log.is_file()
    assert not (tmp_path / "workspace" / ".open-data-products").exists()


def test_cli_from_subdirectory_writes_parent_workspace_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    child = workspace / "inputs" / "objectives"
    child.mkdir(parents=True)
    (workspace / "recipes.config.yaml").write_text("recipes: {}\n", encoding="utf-8")
    monkeypatch.delenv("OPEN_DATA_PRODUCTS_ACTIVITY_LOG", raising=False)
    monkeypatch.chdir(child)

    assert main(["validate", str(ODPS_PRODUCT), "--json"]) == 0

    assert (workspace / ".open-data-products" / "activity.log").is_file()
    assert not (child / ".open-data-products").exists()


def test_cli_parse_failure_is_logged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("OPEN_DATA_PRODUCTS_ACTIVITY_LOG", raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(["validate"])

    assert exc_info.value.code == 2
    lines = _log_lines(tmp_path / ".open-data-products" / "activity.log")
    assert len(lines) == 1
    assert " [FAILED] " in lines[0]
    assert "command=validate exit_code=2" in lines[0]
    assert "the following arguments are required: document" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["--help"], ["--version"]])
def test_cli_help_and_version_are_not_logged(
    argv: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPEN_DATA_PRODUCTS_ACTIVITY_LOG", raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 0
    assert not (tmp_path / ".open-data-products").exists()


def test_generate_logs_llm_invocation_with_provider_and_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.md"
    output = tmp_path / "generated"
    source.write_text("Customer renewal signal notes.\n", encoding="utf-8")

    def fake_client(prompt: str, model: str) -> str:
        return "unused"

    def fake_generate(*args: object, **kwargs: object) -> list[GeneratedArtifact]:
        return [
            GeneratedArtifact(
                name="signal",
                prompt_name="odpc_signal_fragment.md",
                output_path=output / "signal.yaml",
                valid_yaml=True,
            )
        ]

    import open_data_products.generation as generation

    monkeypatch.setattr(
        generation, "create_generation_client", lambda settings: fake_client
    )
    monkeypatch.setattr(generation, "generate_local_artifacts_for_kind", fake_generate)
    monkeypatch.delenv("OPEN_DATA_PRODUCTS_ACTIVITY_LOG", raising=False)
    monkeypatch.chdir(tmp_path)

    assert (
        main(
            [
                "generate",
                "--input",
                str(source),
                "--kind",
                "signal",
                "--output",
                str(output),
                "--provider",
                "openai",
                "--model",
                "gpt-4.1-mini",
                "--json",
            ]
        )
        == 0
    )

    lines = _log_lines(tmp_path / ".open-data-products" / "activity.log")
    assert len(lines) == 2
    assert " [INFO] source=cli command=llm.invoke exit_code=0" in lines[0]
    assert 'message="LLM provider invoked"' in lines[0]
    assert '"parent_command":"generate"' in lines[0]
    assert '"provider":"openai"' in lines[0]
    assert '"provider_type":"openai"' in lines[0]
    assert '"model":"gpt-4.1-mini"' in lines[0]
    assert " [SUCCESS] source=cli command=generate exit_code=0" in lines[1]
