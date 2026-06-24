"""Tests for local generation prompt assets and helpers."""

import io
import json
from pathlib import Path
import sys
import types
from urllib import error

import pytest
import yaml

from open_data_products.generation import (
    DEFAULT_GENERATION_CONFIG,
    GenerationSettings,
    anthropic_generate,
    copy_generation_prompts,
    copy_config_template,
    create_generation_client,
    ensure_ollama_model,
    generate_local_artifact,
    generate_local_artifacts_for_kind,
    generate_local_artifacts,
    get_config,
    get_config_path,
    load_generation_config,
    list_generation_prompts,
    load_generation_prompt,
    load_source_documents,
    llama_cpp_generate,
    list_ollama_models,
    openai_chat_generate,
    openai_generate,
    print_config,
    render_generation_prompt,
    resolve_generation_settings,
    validate_config,
)
from open_data_products import (
    anthropic_generate as anthropic_public_generate,
    copy_config_template as copy_public_config_template,
    create_generation_client as create_public_generation_client,
    ensure_ollama_model as ensure_public_ollama_model,
    generate_local_artifact as generate_public_local_artifact,
    generate_local_artifacts as generate_public_local_artifacts,
    get_config as get_public_config,
    get_config_path as get_public_config_path,
    list_generation_prompts as list_public_generation_prompts,
    load_generation_prompt as load_public_generation_prompt,
    llama_cpp_generate as llama_cpp_public_generate,
    openai_chat_generate as openai_public_chat_generate,
    print_config as print_public_config,
    render_generation_prompt as render_public_generation_prompt,
    resolve_generation_settings as resolve_public_generation_settings,
    validate_document,
    validate_config as validate_public_config,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATION_SOURCE_DOCS = REPO_ROOT / "open_data_products" / "generation" / "source_docs"


def test_generation_prompts_are_listed_and_loadable():
    """Test that editable local generation prompts are bundled."""
    prompt_names = list_generation_prompts()

    assert prompt_names == [
        "odpc_objective_fragment.md",
        "odpc_signal_fragment.md",
        "odpc_use_case_fragment.md",
        "odpg_edges_from_odpc_fragments.md",
        "odpg_graph_yaml.md",
        "odps_data_product_fragment.md",
        "odps_product_assemble_yaml.md",
        "odps_product_component_draft.md",
        "odps_product_facts.md",
        "odps_product_merge_facts.md",
        "odps_product_minimal_yaml.md",
        "odps_product_repair_yaml.md",
        "system.md",
    ]
    for name in prompt_names:
        prompt = load_generation_prompt(name)
        if name == "odpg_edges_from_odpc_fragments.md":
            assert "{nodes}" in prompt
            assert "{odpc_fragments}" in prompt
        elif name != "odps_product_repair_yaml.md":
            assert "{source_documents}" in prompt
        assert "valid YAML" in prompt
    assert "top-level `productReferences` list" in load_generation_prompt(
        "odps_data_product_fragment.md"
    )
    assert (
        "Do not start the YAML with `- productReferences:`"
        in load_generation_prompt("odps_data_product_fragment.md")
    )
    assert "Never create `productReferences` for use cases" in load_generation_prompt(
        "odps_data_product_fragment.md"
    )
    assert "Return evidence facts as valid YAML" in load_generation_prompt(
        "odps_product_facts.md"
    )
    assert "Merge ODPS product fact chunks" in load_generation_prompt(
        "odps_product_merge_facts.md"
    )
    assert "Return exactly one OpenDataProduct document" in load_generation_prompt(
        "odps_product_minimal_yaml.md"
    )
    assert "requested ODPS product components" in load_generation_prompt(
        "odps_product_component_draft.md"
    )
    assert (
        "Assemble one valid ODPS OpenDataProduct YAML document"
        in load_generation_prompt("odps_product_assemble_yaml.md")
    )
    assert "Repair one ODPS OpenDataProduct YAML document" in load_generation_prompt(
        "odps_product_repair_yaml.md"
    )
    assert "dataNeeds:" in load_generation_prompt("odpc_use_case_fragment.md")
    assert "summary:" in load_generation_prompt("odpc_use_case_fragment.md")
    assert "startDate:" in load_generation_prompt("odpc_objective_fragment.md")
    assert "Do not use `linkedUseCases`" in load_generation_prompt(
        "odpc_objective_fragment.md"
    )
    assert (
        "The `id` must describe the same signal as `name.en`"
        in load_generation_prompt("odpc_signal_fragment.md")
    )
    assert "Do not use `moderate`" in load_generation_prompt("odpc_signal_fragment.md")
    assert "`from`, `to`, `type`, and `confidence`" in load_generation_prompt(
        "odpg_graph_yaml.md"
    )
    assert "product_reference_<id>.yaml" in load_generation_prompt("odpg_graph_yaml.md")


def test_odps_generation_prompts_include_named_v41_component_example():
    """Test ODPS prompts show the named v4.1 component and pricing ref shape."""
    component_prompt = load_generation_prompt("odps_product_component_draft.md")
    assemble_prompt = load_generation_prompt("odps_product_assemble_yaml.md")
    prompts = "\n".join([component_prompt, assemble_prompt])

    assert "productStrategy:" in prompts
    assert "dataHolder:" in prompts
    assert "paymentGateways:" in prompts
    assert "license:" in prompts
    assert "scope:" in prompts
    assert "#/product/paymentGateways/default" in prompts
    assert "#/product/dataQuality/declarative/default" in prompts
    assert "#/product/SLA/declarative/default" in prompts
    assert "#/product/dataAccess/API" in prompts
    assert "scopeOfUse" not in prompts
    assert "#/product/SLA/declarative/0" not in prompts
    assert "#/product/dataQuality/declarative/0" not in prompts


def test_generation_config_summary_exposes_template_and_resolved_settings():
    """Test that users can discover the editable generation config template."""
    summary = get_config("generation")

    assert summary["domain"] == "generation"
    assert summary["template_path"] == DEFAULT_GENERATION_CONFIG.as_posix()
    assert summary["editable"] is False
    assert summary["copy_hint"].startswith("Copy this template")
    assert summary["selected_provider"] == "ollama"
    assert summary["resolved"]["model"] == "qwen2.5"
    assert "claude" in summary["providers"]
    assert summary["providers"]["claude"]["api_key_env"] == "ANTHROPIC_API_KEY"
    assert "sk-" not in json.dumps(summary)
    assert get_public_config is get_config
    assert get_public_config_path is get_config_path
    assert print_public_config is print_config
    assert validate_public_config is validate_config


def test_validate_generation_config_accepts_bundled_template():
    """Test that the bundled generation config passes explicit validation."""
    report = validate_config("generation", DEFAULT_GENERATION_CONFIG)

    assert report["valid"] is True
    assert report["errors"] == []
    assert report["resolved"]["provider"] == "ollama"
    assert report["resolved"]["model"] == "qwen2.5"


def test_validate_generation_config_reports_user_mistakes(tmp_path):
    """Test that edited config files fail before generation runs."""
    config = tmp_path / "bad-generation.config.yaml"
    config.write_text(
        """
provider: groq
base_url: https://typo.example/v1
providers:
  groq:
    type: openai
    model: openai/gpt-oss-120b
    apiKeyEnv: sk-secret-value
  claude:
    type: anthropic
    model: claude-test
    maxTokens: many
""",
        encoding="utf-8",
    )

    report = validate_config("generation", config)

    assert report["valid"] is False
    assert "Unknown top-level generation config key: base_url" in report["errors"]
    assert (
        "providers.groq.apiKeyEnv must be an environment variable name"
        in report["errors"]
    )
    assert "providers.claude.maxTokens must be a positive integer" in report["errors"]


def test_validate_generation_config_rejects_implicit_defaults_and_missing_input(
    tmp_path,
):
    """Test that commented-out provider/model settings are not silently accepted."""
    config = tmp_path / "weak-generation.config.yaml"
    config.write_text(
        """
# provider: claude
# model: claude-sonnet-4-5
input: missing/source_docs/
output: generation/fragments/
""",
        encoding="utf-8",
    )

    report = validate_config("generation", config)

    assert report["valid"] is False
    assert "provider is required in generation config files" in report["errors"]
    assert (
        "model is required at top level or on the selected provider" in report["errors"]
    )
    assert "input path does not exist: missing/source_docs/" in report["errors"]


def test_validate_generation_config_rejects_missing_custom_provider_profile(tmp_path):
    """Test that provider names like groq require a provider profile."""
    config = tmp_path / "missing-provider.config.yaml"
    config.write_text(
        """
provider: groq
model: openai/gpt-oss-120b
input: .
output: generation/fragments/
""",
        encoding="utf-8",
    )

    report = validate_config("generation", config)

    assert report["valid"] is False
    assert "providers.groq is missing" in report["errors"]


def test_copy_config_template_writes_user_editable_file(tmp_path):
    """Test that PyPI users can copy the bundled config before editing."""
    output = tmp_path / "generation.config.yaml"

    result = copy_config_template("generation", output)

    assert result == output
    assert output.read_text(encoding="utf-8") == DEFAULT_GENERATION_CONFIG.read_text(
        encoding="utf-8"
    )
    assert copy_public_config_template is copy_config_template


def test_copy_config_template_accepts_folder_destination(tmp_path):
    """Test that a folder destination receives the bundled config filename."""
    output_dir = tmp_path / "configs" / "llm"

    result = copy_config_template("generation", f"{output_dir}/")

    assert result == output_dir / "generation.config.yaml"
    assert result.read_text(encoding="utf-8") == DEFAULT_GENERATION_CONFIG.read_text(
        encoding="utf-8"
    )
    assert (
        "every edge `from` and `to` value appears in `graph.nodes`"
        in load_generation_prompt("odpg_graph_yaml.md")
    )
    assert "Do not use YAML document separators" in load_generation_prompt(
        "odpc_signal_fragment.md"
    )


def test_copy_generation_prompts_and_load_custom_prompt(tmp_path):
    """Test that users can copy and override bundled prompt templates."""
    prompt_dir = tmp_path / "prompts"

    copied = copy_generation_prompts(prompt_dir)

    assert prompt_dir / "odpc_signal_fragment.md" in copied
    custom = prompt_dir / "odpc_signal_fragment.md"
    custom.write_text("CUSTOM PROMPT\n{source_documents}\n", encoding="utf-8")
    prompt = render_generation_prompt(
        "odpc_signal_fragment.md",
        GENERATION_SOURCE_DOCS,
        prompt_dir=prompt_dir,
    )

    assert prompt.startswith("CUSTOM PROMPT")
    assert "--- Source file:" in prompt


def test_generation_prompt_rejects_unknown_name():
    """Test that prompt lookup fails clearly for unknown prompt names."""
    try:
        load_generation_prompt("missing.md")
    except KeyError as exc:
        assert "Unknown generation prompt" in str(exc)
    else:
        raise AssertionError("unknown prompt name did not raise KeyError")


def test_generation_prompt_helpers_are_public_api():
    """Test that prompt helpers are available from the package root."""
    from open_data_products.generation import models, prompts

    assert "system.md" in list_public_generation_prompts()
    assert load_public_generation_prompt("system.md").startswith(
        "# Local ODP Generation System Prompt"
    )
    assert GenerationSettings is models.GenerationSettings
    assert list_generation_prompts is prompts.list_generation_prompts
    assert load_generation_prompt is prompts.load_generation_prompt
    assert load_source_documents is prompts.load_source_documents
    assert ensure_public_ollama_model is ensure_ollama_model
    assert generate_public_local_artifact is generate_local_artifact
    assert generate_public_local_artifacts is generate_local_artifacts
    assert anthropic_public_generate is anthropic_generate
    assert llama_cpp_public_generate is llama_cpp_generate
    assert openai_public_chat_generate is openai_chat_generate
    assert create_public_generation_client is create_generation_client
    assert render_public_generation_prompt is render_generation_prompt
    assert resolve_public_generation_settings is resolve_generation_settings


def test_render_generation_prompt_inlines_source_documents():
    """Test that generation prompts are rendered with source document text."""
    prompt = render_generation_prompt("odpc_signal_fragment.md", GENERATION_SOURCE_DOCS)

    assert "{source_documents}" not in prompt
    assert "Source file: turnaround-delay-signal.txt" in prompt
    assert "Turnaround Delay Spike Signal" in prompt


def test_render_generation_prompt_accepts_one_source_file():
    """Test that one source file can drive single-artifact generation."""
    source_file = GENERATION_SOURCE_DOCS / "turnaround-delay-signal.txt"

    prompt = render_generation_prompt("odpc_signal_fragment.md", source_file)

    assert "Source file: turnaround-delay-signal.txt" in prompt
    assert "Turnaround Delay Spike Signal" in prompt
    assert "Passenger Flow and Queue Data Product" not in prompt


def test_load_source_documents_prefers_compact_yaml_context_sidecars(tmp_path):
    """Test YAML source context uses compact sidecars when available."""
    graph = tmp_path / "graph.yaml"
    graph.write_text("yaml graph body", encoding="utf-8")
    graph.with_suffix(".toon").write_text("toon graph body", encoding="utf-8")
    graph.with_suffix(".gcf").write_text("gcf graph body", encoding="utf-8")

    context = load_source_documents(graph)

    assert "--- Source file: graph.yaml (context: graph.gcf) ---" in context
    assert "gcf graph body" in context
    assert "toon graph body" not in context
    assert "yaml graph body" not in context


def test_load_source_documents_includes_yaml_sidecars_from_source_folders(tmp_path):
    """Test source folders include YAML artifacts only through compact sidecars."""
    note = tmp_path / "brief.md"
    note.write_text("Business objective: reduce churn", encoding="utf-8")
    graph = tmp_path / "graph.yaml"
    graph.write_text("yaml graph body", encoding="utf-8")
    graph.with_suffix(".gcf").write_text("gcf graph body", encoding="utf-8")
    config = tmp_path / "generation.config.yaml"
    config.write_text("provider: ollama", encoding="utf-8")

    context = load_source_documents(tmp_path)

    assert "Source file: brief.md" in context
    assert "Business objective: reduce churn" in context
    assert "Source file: graph.yaml (context: graph.gcf)" in context
    assert "gcf graph body" in context
    assert "provider: ollama" not in context


def test_list_ollama_models_reads_local_tags(monkeypatch):
    """Test that Ollama model discovery reads /api/tags."""

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"models":[{"name":"qwen2.5:latest"},{"model":"llama3.2"}]}'

    def fake_urlopen(req, timeout):
        assert req.full_url == "http://localhost:11434/api/tags"
        assert timeout == 10
        return FakeResponse()

    monkeypatch.setattr("open_data_products.generation.request.urlopen", fake_urlopen)

    assert list_ollama_models() == ["qwen2.5:latest", "llama3.2"]


def test_ensure_ollama_model_accepts_qwen_latest(monkeypatch):
    """Test that qwen2.5 is accepted when Ollama has qwen2.5:latest."""
    monkeypatch.setattr(
        "open_data_products.generation.list_ollama_models",
        lambda base_url="http://localhost:11434": ["qwen2.5:latest"],
    )

    ensure_ollama_model("qwen2.5")


def test_ensure_ollama_model_rejects_missing_qwen(monkeypatch):
    """Test that missing qwen2.5 fails before generation."""
    monkeypatch.setattr(
        "open_data_products.generation.list_ollama_models",
        lambda base_url="http://localhost:11434": ["llama3.2:latest"],
    )

    try:
        ensure_ollama_model("qwen2.5")
    except RuntimeError as exc:
        assert "Required Ollama model qwen2.5 is not available" in str(exc)
    else:
        raise AssertionError("missing qwen2.5 did not raise RuntimeError")


def test_load_generation_config_and_resolve_openai_settings(tmp_path):
    """Test provider config resolves paths, model, and secret env references."""
    config = tmp_path / "generation.config.yaml"
    config.write_text(
        """
provider: openai
input: source_docs
output: fragments
providers:
  openai:
    type: openai
    model: gpt-test
    baseUrl: https://api.openai.example/v1
    apiKeyEnv: TEST_OPENAI_API_KEY
""",
        encoding="utf-8",
    )

    raw = load_generation_config(config)
    settings = resolve_generation_settings(config)

    assert raw["provider"] == "openai"
    assert settings.provider == "openai"
    assert settings.provider_type == "openai"
    assert settings.model == "gpt-test"
    assert settings.input_path == "source_docs"
    assert settings.output_path == "fragments"
    assert settings.base_url == "https://api.openai.example/v1"
    assert settings.api_key_env == "TEST_OPENAI_API_KEY"


def test_resolve_generation_settings_allows_overrides(tmp_path):
    """Test CLI-style overrides take precedence over config values."""
    config = tmp_path / "generation.config.yaml"
    config.write_text(
        """
provider: openai
input: configured-input
output: configured-output
providers:
  openai:
    type: openai
    model: configured-model
    apiKeyEnv: TEST_OPENAI_API_KEY
""",
        encoding="utf-8",
    )

    settings = resolve_generation_settings(
        config,
        input_path="override-input",
        output_path="override-output",
        provider="ollama",
        model="override-model",
        ollama_url="http://ollama.example",
    )

    assert settings.provider == "ollama"
    assert settings.provider_type == "ollama"
    assert settings.model == "override-model"
    assert settings.input_path == "override-input"
    assert settings.output_path == "override-output"
    assert settings.base_url == "http://ollama.example"
    assert settings.api_key_env is None


def test_bundled_generation_config_includes_common_compatible_providers():
    """Test bundled config resolves common OpenAI-compatible provider profiles."""
    config = load_generation_config(DEFAULT_GENERATION_CONFIG)

    assert "openrouter" in config["providers"]
    assert "groq" in config["providers"]
    assert "together" in config["providers"]
    assert "cerebras" in config["providers"]
    assert "sambanova" in config["providers"]
    assert "mistral" in config["providers"]
    assert "gemini" in config["providers"]
    assert "xai" in config["providers"]
    assert "zai" in config["providers"]
    assert "claude" in config["providers"]
    assert "lmstudio" in config["providers"]
    assert "vllm" in config["providers"]
    assert "nvidia-nim" in config["providers"]
    assert "llamacpp-embedded" in config["providers"]

    openrouter = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="openrouter",
    )
    groq = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="groq",
    )

    assert openrouter.provider_type == "openai"
    assert openrouter.base_url == "https://openrouter.ai/api/v1"
    assert openrouter.api_key_env == "OPENROUTER_API_KEY"
    assert groq.provider_type == "openai"
    assert groq.base_url == "https://api.groq.com/openai/v1"
    assert groq.api_key_env == "GROQ_API_KEY"
    together = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="together",
    )
    assert together.provider_type == "openai-chat"
    assert together.base_url == "https://api.together.ai/v1"
    assert together.model == "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    assert together.api_key_env == "TOGETHER_API_KEY"
    cerebras = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="cerebras",
    )
    assert cerebras.provider_type == "openai-chat"
    assert cerebras.base_url == "https://api.cerebras.ai/v1"
    assert cerebras.model == "gpt-oss-120b"
    assert cerebras.api_key_env == "CEREBRAS_API_KEY"
    sambanova = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="sambanova",
    )
    assert sambanova.provider_type == "openai-chat"
    assert sambanova.base_url == "https://api.sambanova.ai/v1"
    assert sambanova.model == "Meta-Llama-3.3-70B-Instruct"
    assert sambanova.api_key_env == "SAMBANOVA_API_KEY"
    mistral = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="mistral",
    )
    assert mistral.provider_type == "openai-chat"
    assert mistral.base_url == "https://api.mistral.ai/v1"
    assert mistral.model == "mistral-large-latest"
    assert mistral.api_key_env == "MISTRAL_API_KEY"
    gemini = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="gemini",
    )
    assert gemini.provider_type == "openai-chat"
    assert gemini.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert gemini.model == "gemini-3.5-flash"
    assert gemini.api_key_env == "GEMINI_API_KEY"
    xai = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="xai",
    )
    assert xai.provider_type == "openai-chat"
    assert xai.base_url == "https://api.x.ai/v1"
    assert xai.model == "grok-4.3"
    assert xai.api_key_env == "XAI_API_KEY"
    zai = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="zai",
    )
    assert zai.provider_type == "openai-chat"
    assert zai.base_url == "https://api.z.ai/api/paas/v4"
    assert zai.model == "glm-5.2"
    assert zai.api_key_env == "ZAI_API_KEY"
    lmstudio = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="lmstudio",
    )
    assert lmstudio.provider_type == "openai-chat"
    assert lmstudio.base_url == "http://localhost:1234/v1"
    assert lmstudio.model == "local-model"
    assert lmstudio.api_key_env is None
    nvidia_nim = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="nvidia-nim",
    )
    assert nvidia_nim.provider_type == "openai-chat"
    assert nvidia_nim.base_url == "http://localhost:8000/v1"
    assert nvidia_nim.model == "local-model"
    assert nvidia_nim.api_key_env is None
    claude = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="claude",
    )
    assert claude.provider_type == "anthropic"
    assert claude.base_url == "https://api.anthropic.com/v1"
    assert claude.api_key_env == "ANTHROPIC_API_KEY"
    llamacpp = resolve_generation_settings(
        DEFAULT_GENERATION_CONFIG,
        provider="llamacpp-embedded",
    )
    assert llamacpp.provider_type == "llama-cpp"
    assert llamacpp.model == "local-gguf"
    assert llamacpp.model_path == "models/qwen2.5-7b-instruct-q4_k_m.gguf"
    assert llamacpp.context_window == 8192
    assert llamacpp.gpu_layers == -1


def test_llamacpp_embedded_provider_resolves_without_config_file():
    """Test built-in llama.cpp profile works with --provider only."""
    settings = resolve_generation_settings(provider="llamacpp-embedded")

    assert settings.provider == "llamacpp-embedded"
    assert settings.provider_type == "llama-cpp"
    assert settings.model == "local-gguf"
    assert settings.model_path == "models/qwen2.5-7b-instruct-q4_k_m.gguf"
    assert settings.context_window == 8192
    assert settings.gpu_layers == -1


def test_bundled_generation_config_includes_local_model_presets():
    """Test bundled config exposes local model presets for common runtimes."""
    expected = {
        "ollama-gemma3n": ("ollama", "gemma3n:e4b", "http://localhost:11434"),
        "ollama-qwen25": ("ollama", "qwen2.5:7b", "http://localhost:11434"),
        "ollama-qwen25-14b": ("ollama", "qwen2.5:14b", "http://localhost:11434"),
        "ollama-qwen3": ("ollama", "qwen3:8b", "http://localhost:11434"),
        "ollama-qwen3-14b": ("ollama", "qwen3:14b", "http://localhost:11434"),
        "ollama-llama": ("ollama", "llama3.1:8b", "http://localhost:11434"),
        "ollama-mistral": ("ollama", "mistral:7b", "http://localhost:11434"),
        "ollama-phi": ("ollama", "phi4-mini", "http://localhost:11434"),
        "ollama-deepseek14b": (
            "ollama",
            "deepseek-r1:14b",
            "http://localhost:11434",
        ),
        "ollama-large-q4": ("ollama", "qwen3:32b", "http://localhost:11434"),
        "lmstudio-gemma4-e4b": (
            "openai-chat",
            "google/gemma-4-e4b",
            "http://localhost:1234/v1",
        ),
        "lmstudio-gemma4-12b": (
            "openai-chat",
            "google/gemma-4-12b",
            "http://localhost:1234/v1",
        ),
    }
    config = load_generation_config(DEFAULT_GENERATION_CONFIG)

    for provider, (provider_type, model, base_url) in expected.items():
        assert provider in config["providers"]
        settings = resolve_generation_settings(
            DEFAULT_GENERATION_CONFIG,
            provider=provider,
        )
        assert settings.provider_type == provider_type
        assert settings.model == model
        assert settings.base_url == base_url
        assert settings.api_key_env is None


def test_resolve_generation_settings_supports_claude_without_config():
    """Test CLI provider override works for Claude without a config file."""
    settings = resolve_generation_settings(
        provider="claude",
        model="claude-sonnet-4-5",
        input_path="source_docs",
        output_path="fragments",
    )

    assert settings.provider == "claude"
    assert settings.provider_type == "anthropic"
    assert settings.model == "claude-sonnet-4-5"
    assert settings.input_path == "source_docs"
    assert settings.output_path == "fragments"
    assert settings.base_url == "https://api.anthropic.com/v1"
    assert settings.api_key_env == "ANTHROPIC_API_KEY"
    assert settings.api_version == "2023-06-01"
    assert settings.max_tokens == 8192


@pytest.mark.parametrize(
    ("provider", "provider_type", "model", "base_url", "api_key_env"),
    [
        (
            "openrouter",
            "openai",
            "openai/gpt-4.1-mini",
            "https://openrouter.ai/api/v1",
            "OPENROUTER_API_KEY",
        ),
        (
            "groq",
            "openai",
            "openai/gpt-oss-120b",
            "https://api.groq.com/openai/v1",
            "GROQ_API_KEY",
        ),
        (
            "together",
            "openai-chat",
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "https://api.together.ai/v1",
            "TOGETHER_API_KEY",
        ),
        (
            "cerebras",
            "openai-chat",
            "gpt-oss-120b",
            "https://api.cerebras.ai/v1",
            "CEREBRAS_API_KEY",
        ),
        (
            "sambanova",
            "openai-chat",
            "Meta-Llama-3.3-70B-Instruct",
            "https://api.sambanova.ai/v1",
            "SAMBANOVA_API_KEY",
        ),
        (
            "mistral",
            "openai-chat",
            "mistral-large-latest",
            "https://api.mistral.ai/v1",
            "MISTRAL_API_KEY",
        ),
        (
            "gemini",
            "openai-chat",
            "gemini-3.5-flash",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "GEMINI_API_KEY",
        ),
        (
            "xai",
            "openai-chat",
            "grok-4.3",
            "https://api.x.ai/v1",
            "XAI_API_KEY",
        ),
        (
            "zai",
            "openai-chat",
            "glm-5.2",
            "https://api.z.ai/api/paas/v4",
            "ZAI_API_KEY",
        ),
        (
            "lmstudio",
            "openai-chat",
            "local-model",
            "http://localhost:1234/v1",
            None,
        ),
        (
            "vllm",
            "openai-chat",
            "local-model",
            "http://localhost:8000/v1",
            None,
        ),
        (
            "nvidia-nim",
            "openai-chat",
            "local-model",
            "http://localhost:8000/v1",
            None,
        ),
    ],
)
def test_resolve_generation_settings_supports_bundled_provider_names_without_config(
    provider,
    provider_type,
    model,
    base_url,
    api_key_env,
):
    """Test bundled provider names work as CLI overrides without config."""
    settings = resolve_generation_settings(
        provider=provider,
        input_path="source_docs",
        output_path="fragments",
    )

    assert settings.provider == provider
    assert settings.provider_type == provider_type
    assert settings.model == model
    assert settings.input_path == "source_docs"
    assert settings.output_path == "fragments"
    assert settings.base_url == base_url
    assert settings.api_key_env == api_key_env


def test_resolve_generation_settings_reads_anthropic_provider(tmp_path):
    """Test Anthropic provider config resolves Claude-specific fields."""
    config = tmp_path / "generation.config.yaml"
    config.write_text(
        """
provider: claude
input: source_docs
output: fragments
providers:
  claude:
    type: anthropic
    model: claude-test
    baseUrl: https://api.anthropic.example/v1
    apiKeyEnv: TEST_ANTHROPIC_API_KEY
    version: "2023-06-01"
    maxTokens: 4096
""",
        encoding="utf-8",
    )

    settings = resolve_generation_settings(config)

    assert settings.provider == "claude"
    assert settings.provider_type == "anthropic"
    assert settings.model == "claude-test"
    assert settings.base_url == "https://api.anthropic.example/v1"
    assert settings.api_key_env == "TEST_ANTHROPIC_API_KEY"
    assert settings.api_version == "2023-06-01"
    assert settings.max_tokens == 4096


def test_resolve_generation_settings_reads_openai_chat_provider(tmp_path):
    """Test local chat providers keep arbitrary model names."""
    config = tmp_path / "generation.config.yaml"
    config.write_text(
        """
provider: lmstudio
model: fallback-model
input: .
output: fragments
providers:
  lmstudio:
    type: openai-chat
    model: any-local-model-loaded-in-the-server
    baseUrl: http://localhost:1234/v1
""",
        encoding="utf-8",
    )

    settings = resolve_generation_settings(config)
    report = validate_config("generation", config)

    assert settings.provider == "lmstudio"
    assert settings.provider_type == "openai-chat"
    assert settings.model == "any-local-model-loaded-in-the-server"
    assert settings.base_url == "http://localhost:1234/v1"
    assert settings.api_key_env is None
    assert report["valid"] is True


def test_resolve_generation_settings_reads_llama_cpp_provider(tmp_path):
    """Test embedded llama.cpp provider config resolves local model settings."""
    config = tmp_path / "generation.config.yaml"
    config.write_text(
        """
provider: llamacpp-embedded
input: .
output: fragments
providers:
  llamacpp-embedded:
    type: llama-cpp
    model: local-gguf
    modelPath: models/qwen2.5-7b-instruct-q4_k_m.gguf
    contextWindow: 8192
    gpuLayers: -1
""",
        encoding="utf-8",
    )

    settings = resolve_generation_settings(config)
    report = validate_config("generation", config)

    assert settings.provider == "llamacpp-embedded"
    assert settings.provider_type == "llama-cpp"
    assert settings.model == "local-gguf"
    assert settings.model_path == "models/qwen2.5-7b-instruct-q4_k_m.gguf"
    assert settings.context_window == 8192
    assert settings.gpu_layers == -1
    assert settings.base_url is None
    assert settings.api_key_env is None
    assert report["valid"] is True


def test_validate_config_requires_llama_cpp_model_path(tmp_path):
    """Test embedded llama.cpp config requires an explicit GGUF model path."""
    config = tmp_path / "generation.config.yaml"
    config.write_text(
        """
provider: llamacpp-embedded
input: source_docs
output: fragments
providers:
  llamacpp-embedded:
    type: llama-cpp
    model: local-gguf
""",
        encoding="utf-8",
    )

    report = validate_config("generation", config)

    assert report["valid"] is False
    assert (
        "providers.llamacpp-embedded.modelPath is required for llama-cpp"
        in report["errors"]
    )


def test_llama_cpp_generate_reports_optional_install(monkeypatch):
    """Test missing optional llama.cpp support explains how to install it."""
    monkeypatch.setitem(sys.modules, "llama_cpp", None)

    try:
        llama_cpp_generate("prompt", model_path="models/test.gguf")
    except RuntimeError as exc:
        message = str(exc)
        assert 'pip install "open-data-products[llama-cpp]"' in message
        assert "models/test.gguf" not in message
    else:
        raise AssertionError("missing llama_cpp module did not raise RuntimeError")


def test_llama_cpp_generate_reads_completion_text(monkeypatch):
    """Test embedded llama.cpp generation calls the optional package lazily."""
    observed = {}

    class FakeLlama:
        def __init__(self, model_path, n_ctx, n_gpu_layers):
            observed["init"] = {
                "model_path": model_path,
                "n_ctx": n_ctx,
                "n_gpu_layers": n_gpu_layers,
            }

        def __call__(self, prompt, max_tokens, temperature):
            observed["call"] = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            return {"choices": [{"text": "generated yaml"}]}

    fake_module = types.SimpleNamespace(Llama=FakeLlama)
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    assert (
        llama_cpp_generate(
            "prompt",
            model_path="models/test.gguf",
            context_window=4096,
            gpu_layers=-1,
            max_tokens=512,
            temperature=0.1,
        )
        == "generated yaml"
    )
    assert observed == {
        "init": {
            "model_path": "models/test.gguf",
            "n_ctx": 4096,
            "n_gpu_layers": -1,
        },
        "call": {"prompt": "prompt", "max_tokens": 512, "temperature": 0.1},
    }


def test_create_generation_client_uses_llama_cpp(monkeypatch):
    """Test provider factory creates an embedded llama.cpp model client."""
    observed = {}

    def fake_llama_cpp_generate(
        prompt,
        model_path,
        context_window=8192,
        gpu_layers=0,
        max_tokens=2048,
        temperature=0.2,
    ):
        observed.update(
            {
                "prompt": prompt,
                "model_path": model_path,
                "context_window": context_window,
                "gpu_layers": gpu_layers,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        return "generated"

    monkeypatch.setattr(
        "open_data_products.generation.llama_cpp_generate",
        fake_llama_cpp_generate,
    )
    settings = GenerationSettings(
        provider="llamacpp-embedded",
        provider_type="llama-cpp",
        model="local-gguf",
        input_path="source_docs",
        output_path="fragments",
        model_path="models/test.gguf",
        context_window=4096,
        gpu_layers=-1,
    )

    client = create_generation_client(settings)

    assert client("prompt", "ignored-model") == "generated"
    assert observed == {
        "prompt": "prompt",
        "model_path": "models/test.gguf",
        "context_window": 4096,
        "gpu_layers": -1,
        "max_tokens": 2048,
        "temperature": 0.2,
    }


def test_openai_generate_requires_env(monkeypatch):
    """Test OpenAI generation fails before HTTP without the API key env var."""
    monkeypatch.delenv("TEST_OPENAI_API_KEY", raising=False)

    try:
        openai_generate("prompt", "gpt-test", api_key_env="TEST_OPENAI_API_KEY")
    except RuntimeError as exc:
        assert "TEST_OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("missing OpenAI API key did not raise RuntimeError")


def test_openai_generate_rejects_non_ascii_api_key(monkeypatch):
    """Test copied smart quotes in API key env vars fail with a useful message."""
    monkeypatch.setenv("TEST_OPENAI_API_KEY", "sk-test\u2018")

    try:
        openai_generate("prompt", "gpt-test", api_key_env="TEST_OPENAI_API_KEY")
    except RuntimeError as exc:
        message = str(exc)
        assert "TEST_OPENAI_API_KEY" in message
        assert "plain quotes" in message
        assert "sk-test" not in message
    else:
        raise AssertionError("non-ASCII API key did not raise RuntimeError")


def test_openai_generate_reads_responses_output_text(monkeypatch):
    """Test OpenAI Responses API output_text parsing and secret header use."""

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"output_text":"generated yaml"}'

    def fake_urlopen(req, timeout, context=None):
        body = req.data.decode("utf-8")
        assert req.full_url == "https://api.openai.example/v1/responses"
        assert req.headers["Authorization"] == "Bearer sk-test"
        assert req.headers["Accept"] == "application/json"
        assert req.headers["User-agent"] == "open-data-products-python/0.2"
        assert '"model": "gpt-test"' in body
        assert '"input": "prompt"' in body
        assert timeout == 300
        assert context is not None
        return FakeResponse()

    monkeypatch.setenv("TEST_OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("open_data_products.generation.request.urlopen", fake_urlopen)

    assert (
        openai_generate(
            "prompt",
            "gpt-test",
            api_key_env="TEST_OPENAI_API_KEY",
            base_url="https://api.openai.example/v1",
        )
        == "generated yaml"
    )


def test_openai_chat_generate_reads_chat_completion(monkeypatch):
    """Test local OpenAI-compatible chat servers use chat completions."""

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"generated yaml"}}]}'

    def fake_urlopen(req, timeout, context=None):
        body = req.data.decode("utf-8")
        assert req.full_url == "http://localhost:1234/v1/chat/completions"
        assert req.headers["Accept"] == "application/json"
        assert "Authorization" not in req.headers
        assert '"model": "arbitrary-local-model"' in body
        assert '"content": "prompt"' in body
        assert timeout == 300
        assert context is None
        return FakeResponse()

    monkeypatch.setattr("open_data_products.generation.request.urlopen", fake_urlopen)

    assert (
        openai_chat_generate(
            "prompt",
            "arbitrary-local-model",
            base_url="http://localhost:1234/v1",
        )
        == "generated yaml"
    )


def test_openai_generate_reports_transport_reason(monkeypatch):
    """Test OpenAI transport failures include a non-secret diagnostic reason."""

    def fake_urlopen(req, timeout, context=None):
        assert context is not None
        raise OSError("network unavailable")

    monkeypatch.setenv("TEST_OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("open_data_products.generation.request.urlopen", fake_urlopen)

    try:
        openai_generate("prompt", "gpt-test", api_key_env="TEST_OPENAI_API_KEY")
    except RuntimeError as exc:
        message = str(exc)
        assert "OpenAI generation request failed: network unavailable" == message
        assert "sk-test" not in message
    else:
        raise AssertionError("transport failure did not raise RuntimeError")


def test_openai_generate_reports_http_error_message(monkeypatch):
    """Test provider HTTP errors include useful non-secret response details."""

    def fake_urlopen(req, timeout, context=None):
        assert context is not None
        raise error.HTTPError(
            req.full_url,
            403,
            "Forbidden",
            {},
            io.BytesIO(
                b'{"error":{"message":"The model is blocked at the organization level."}}'
            ),
        )

    monkeypatch.setenv("TEST_OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("open_data_products.generation.request.urlopen", fake_urlopen)

    try:
        openai_generate("prompt", "gpt-test", api_key_env="TEST_OPENAI_API_KEY")
    except RuntimeError as exc:
        message = str(exc)
        assert "HTTP 403" in message
        assert "blocked at the organization level" in message
        assert "sk-test" not in message
    else:
        raise AssertionError("HTTP error did not raise RuntimeError")


def test_anthropic_generate_requires_env(monkeypatch):
    """Test Anthropic generation fails before HTTP without the API key env var."""
    monkeypatch.delenv("TEST_ANTHROPIC_API_KEY", raising=False)

    try:
        anthropic_generate(
            "prompt",
            "claude-test",
            api_key_env="TEST_ANTHROPIC_API_KEY",
        )
    except RuntimeError as exc:
        assert "TEST_ANTHROPIC_API_KEY" in str(exc)
    else:
        raise AssertionError("missing Anthropic API key did not raise RuntimeError")


def test_anthropic_generate_reads_message_text(monkeypatch):
    """Test Anthropic Messages API request shape and text response parsing."""

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"content":[{"type":"text","text":"signals:\\n- id: test"}]}'

    def fake_urlopen(req, timeout, context=None):
        body = json.loads(req.data.decode("utf-8"))
        assert req.full_url == "https://api.anthropic.example/v1/messages"
        assert req.headers["X-api-key"] == "sk-ant-test"
        assert req.headers["Anthropic-version"] == "2023-06-01"
        assert req.headers["Accept"] == "application/json"
        assert req.headers["User-agent"] == "open-data-products-python/0.2"
        assert body == {
            "model": "claude-test",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": "prompt"}],
        }
        assert timeout == 300
        assert context is not None
        return FakeResponse()

    monkeypatch.setenv("TEST_ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("open_data_products.generation.request.urlopen", fake_urlopen)

    assert (
        anthropic_generate(
            "prompt",
            "claude-test",
            api_key_env="TEST_ANTHROPIC_API_KEY",
            base_url="https://api.anthropic.example/v1",
            version="2023-06-01",
            max_tokens=2048,
        )
        == "signals:\n- id: test"
    )


def test_create_generation_client_uses_anthropic(monkeypatch):
    """Test provider factory creates an Anthropic model client."""
    observed = {}

    def fake_anthropic_generate(
        prompt,
        model,
        api_key_env="ANTHROPIC_API_KEY",
        base_url="https://api.anthropic.com/v1",
        version="2023-06-01",
        max_tokens=4096,
    ):
        observed.update(
            {
                "prompt": prompt,
                "model": model,
                "api_key_env": api_key_env,
                "base_url": base_url,
                "version": version,
                "max_tokens": max_tokens,
            }
        )
        return "generated"

    monkeypatch.setattr(
        "open_data_products.generation.anthropic_generate",
        fake_anthropic_generate,
    )
    settings = GenerationSettings(
        provider="claude",
        provider_type="anthropic",
        model="claude-test",
        input_path="source_docs",
        output_path="fragments",
        base_url="https://api.anthropic.example/v1",
        api_key_env="TEST_ANTHROPIC_API_KEY",
        api_version="2023-06-01",
        max_tokens=2048,
    )

    client = create_generation_client(settings)

    assert client("prompt", "claude-test") == "generated"
    assert observed == {
        "prompt": "prompt",
        "model": "claude-test",
        "api_key_env": "TEST_ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.example/v1",
        "version": "2023-06-01",
        "max_tokens": 2048,
    }


def test_create_generation_client_checks_ollama(monkeypatch):
    """Test provider client creation keeps Ollama model validation."""
    observed = {}

    def fake_ensure(model, base_url):
        observed["model"] = model
        observed["base_url"] = base_url

    monkeypatch.setattr(
        "open_data_products.generation.ensure_ollama_model", fake_ensure
    )
    monkeypatch.setattr(
        "open_data_products.generation.ollama_generate",
        lambda prompt, model, base_url: f"{model}@{base_url}:{prompt}",
    )

    settings = resolve_generation_settings(
        input_path="source_docs",
        output_path="fragments",
        model="qwen2.5",
        ollama_url="http://ollama.example",
    )
    client = create_generation_client(settings)

    assert observed == {"model": "qwen2.5", "base_url": "http://ollama.example"}
    assert client("prompt", "qwen2.5") == "qwen2.5@http://ollama.example:prompt"


def test_generate_local_artifacts_writes_yaml_outputs(tmp_path):
    """Test local generation with a fake model client."""
    prompts_seen = []
    output_dir = tmp_path / "deep" / "fragments"

    def fake_client(prompt: str, model: str) -> str:
        prompts_seen.append((prompt, model))
        if prompt.startswith("# Generate ODPG Graph YAML"):
            return """```yaml
schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: '1.0'
kind: Graph
graph:
  metadata:
    id: GRAPH-AIRPORTS-001
    name:
      en: Airports and Flights Graph
    description:
      en: Airports and flights graph.
  nodes:
    - id: test-signal
      type: StrategicOpportunity
      $ref: odpc_signals.yaml#/signals/0
  edges: []
```"""
        if prompt.startswith("# Generate ODPS"):
            return """productReferences:
- id: test-product
  productID: test-product
  productVersion: "1.0.0"
  name:
    en: Test Product
  description:
    en: Test product.
  productModel:
    standard: ODPS
    version: "4.1"
    format: yaml
    $ref: products/test-product.yaml
"""
        if prompt.startswith("# Generate ODPC Use Case"):
            return "useCases: []\n"
        if prompt.startswith("# Generate ODPC Business Objective"):
            return "businessObjectives: []\n"
        return """signals:
- id: test-signal
  name:
    en: Test Signal
  description:
    en: Test signal.
  type: operational
  source:
    origin: internal
    method: test
  observedAt: "2026-05-20T00:00:00Z"
"""

    artifacts = generate_local_artifacts(
        GENERATION_SOURCE_DOCS,
        output_dir,
        model="qwen2.5",
        client=fake_client,
    )

    assert [artifact.name for artifact in artifacts] == [
        "productReference:test-product",
        "signal:test-signal",
        "odpg_graph",
    ]
    assert all(artifact.valid_yaml for artifact in artifacts)
    assert all(model == "qwen2.5" for _, model in prompts_seen)
    assert "{source_documents}" not in prompts_seen[0][0]
    graph_prompt = prompts_seen[-1][0]
    assert "Source file: product_reference_test-product.yaml" in graph_prompt
    assert "Source file: signal_test-signal.yaml" in graph_prompt
    graph = yaml.safe_load((output_dir / "odpg_graph.yaml").read_text(encoding="utf-8"))
    assert graph["graph"]["nodes"] == [
        {
            "id": "test-signal",
            "type": "Signal",
            "$ref": "signal_test-signal.yaml",
        },
        {
            "id": "test-product",
            "type": "DataProduct",
            "$ref": "product_reference_test-product.yaml",
        },
    ]
    assert yaml.safe_load(
        (output_dir / "product_reference_test-product.yaml").read_text(encoding="utf-8")
    ) == {
        "productReference": {
            "id": "test-product",
            "productID": "test-product",
            "productVersion": "1.0.0",
            "name": {"en": "Test Product"},
            "description": {"en": "Test product."},
            "productModel": {
                "standard": "ODPS",
                "version": "4.1",
                "format": "yaml",
                "$ref": "products/test-product.yaml",
            },
        }
    }
    assert yaml.safe_load(
        (output_dir / "signal_test-signal.yaml").read_text(encoding="utf-8")
    ) == {
        "signal": {
            "id": "test-signal",
            "name": {"en": "Test Signal"},
            "description": {"en": "Test signal."},
            "type": "operational",
            "source": {"origin": "internal", "method": "test"},
            "observedAt": "2026-05-20T00:00:00Z",
        }
    }
    assert (output_dir / "odpg_graph.yaml").is_file()


def test_generate_local_artifact_writes_one_selected_yaml_output(tmp_path):
    """Test generating only one selected artifact kind."""
    prompts_seen = []
    output_dir = tmp_path / "deep" / "fragments"

    def fake_client(prompt: str, model: str) -> str:
        prompts_seen.append((prompt, model))
        return """signals:
- id: turnaround-delay-spike-signal
  name:
    en: Turnaround Delay Spike Signal
  description:
    en: Turnaround delay increased at Terminal 2.
  type: operational
  source:
    origin: internal
    method: ground operations event log
  observedAt: "2026-05-20T00:00:00Z"
"""

    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "turnaround-delay-signal.txt",
        output_dir,
        client=fake_client,
    )

    assert artifact.name == "signal:turnaround-delay-spike-signal"
    assert (
        artifact.output_path == output_dir / "signal_turnaround-delay-spike-signal.yaml"
    )
    assert artifact.valid_yaml is True
    assert "Turnaround Delay Spike Signal" in prompts_seen[0][0]
    assert "Passenger Connection Protection" not in prompts_seen[0][0]
    assert yaml.safe_load(artifact.output_path.read_text(encoding="utf-8")) == {
        "signal": {
            "id": "turnaround-delay-spike-signal",
            "name": {"en": "Turnaround Delay Spike Signal"},
            "description": {"en": "Turnaround delay increased at Terminal 2."},
            "type": "operational",
            "source": {
                "origin": "internal",
                "method": "ground operations event log",
            },
            "observedAt": "2026-05-20T00:00:00Z",
        }
    }


def test_generate_local_artifacts_for_kind_processes_each_product_reference_source_file(
    tmp_path,
):
    """Test product-reference generation processes each source document."""
    source_dir = tmp_path / "source_docs"
    source_dir.mkdir()
    source_dir.joinpath("airport-operations-product.md").write_text(
        "# Airport Operations Product\n\n"
        "A data product for flight schedule, gate assignment, and turnaround status.",
        encoding="utf-8",
    )
    source_dir.joinpath("passenger-flow-product.md").write_text(
        "# Passenger Flow Product\n\n"
        "A data product for queue wait time, passenger volume, and gate allocation.",
        encoding="utf-8",
    )
    prompts = []

    def fake_client(prompt: str, model: str) -> str:
        prompts.append(prompt)
        if "airport-operations-product.md" in prompt:
            return """productReferences:
- id: airport-operations-performance
  productID: airport-operations-performance
  productVersion: "1.0.0"
  name:
    en: Airport Operations Performance Product
  description:
    en: Airport operations data product.
  productModel:
    standard: ODPS
    version: "4.1"
    format: yaml
    $ref: products/airport-operations-performance.yaml
"""
        return """productReferences:
- id: passenger-flow
  productID: passenger-flow
  productVersion: "1.0.0"
  name:
    en: Passenger Flow Product
  description:
    en: Passenger flow data product.
  productModel:
    standard: ODPS
    version: "4.1"
    format: yaml
    $ref: products/passenger-flow.yaml
"""

    artifacts = generate_local_artifacts_for_kind(
        "product-reference",
        source_dir,
        tmp_path / "fragments",
        client=fake_client,
    )

    assert [artifact.name for artifact in artifacts] == [
        "productReference:airport-operations-performance",
        "productReference:passenger-flow",
    ]
    assert len(prompts) == 2
    assert "airport-operations-product.md" in prompts[0]
    assert "passenger-flow-product.md" not in prompts[0]
    assert "passenger-flow-product.md" in prompts[1]
    assert "airport-operations-product.md" not in prompts[1]
    assert (
        tmp_path / "fragments" / "product_reference_airport-operations-performance.yaml"
    ).is_file()
    assert (tmp_path / "fragments" / "product_reference_passenger-flow.yaml").is_file()


def test_generate_local_artifacts_for_kind_rejects_product_alias(tmp_path):
    """Test ambiguous product kind is not accepted."""
    try:
        generate_local_artifacts_for_kind(
            "product",
            GENERATION_SOURCE_DOCS / "turnaround-delay-signal.txt",
            tmp_path,
            client=lambda prompt, model: "",
        )
    except KeyError as exc:
        assert "Unknown generation artifact kind: product" in str(exc)
    else:
        raise AssertionError("product alias should not be accepted")


def test_generate_local_artifacts_for_kind_writes_full_odps_product(tmp_path):
    """Test ODPS product generation writes a full OpenDataProduct document."""
    source = tmp_path / "airport-operations-product.md"
    source.write_text(
        "# Airport Operations Performance\n\n"
        "A public production dataset for airport operations performance.",
        encoding="utf-8",
    )

    prompts = []

    def fake_client(prompt, model):
        prompts.append(prompt)
        if prompt.startswith("# Extract ODPS Product Facts"):
            return """product:
  productID: airport-operations-performance
  name: Airport Operations Performance
evidenceGaps: []
"""
        return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: airport-operations-performance
  name: Airport Operations Performance
  visibility: public
  status: production
  type: dataset
"""

    artifact = generate_local_artifacts_for_kind(
        "odps-product",
        source,
        tmp_path / "fragments",
        client=fake_client,
    )[0]

    assert [prompt.splitlines()[0] for prompt in prompts] == [
        "# Extract ODPS Product Facts",
        "# Generate Minimal ODPS Product YAML",
    ]
    assert artifact.name == "odpsProduct:airport-operations-performance"
    assert artifact.prompt_name == "odps_product_minimal_yaml.md"
    assert artifact.review_notes == []
    assert artifact.drafted_components == []
    assert artifact.evidence_gaps == []
    assert artifact.output_path == (
        tmp_path / "fragments" / "odps_product_airport-operations-performance.yaml"
    )
    assert artifact.valid_yaml is True
    document = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))
    assert validate_document(document).valid is True
    assert document == {
        "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": "airport-operations-performance",
                    "name": "Airport Operations Performance",
                    "visibility": "public",
                    "status": "production",
                    "type": "dataset",
                }
            },
        },
    }


def test_generate_odps_product_complete_draft_uses_component_pipeline(tmp_path):
    """Test complete-draft ODPS generation drafts components in separate calls."""
    source = tmp_path / "customer-analytics-email.txt"
    source.write_text(
        "Email thread: we need a customer analytics dataset for retention teams.",
        encoding="utf-8",
    )
    prompts = []

    def fake_client(prompt, model):
        prompts.append(prompt)
        if prompt.startswith("# Extract ODPS Product Facts"):
            return """product:
  productID: customer-analytics
  name: Customer Analytics
evidenceGaps:
  - No pricing terms were provided.
"""
        if prompt.startswith("# Generate Minimal ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: customer-analytics
  name: Customer Analytics
  visibility: public
  status: draft
  type: dataset
"""
        if prompt.startswith("# Draft ODPS Product Components"):
            assert "SLA" in prompt
            assert "dataQuality" in prompt
            assert "pricingPlans" in prompt
            return """components:
  SLA:
    profiles:
      default:
        dimensions:
          - name: availability
            objective: 99.5
            unit: percent
  dataQuality:
    profiles:
      default:
        dimensions:
          - name: freshness
            objective: 24
            unit: hours
  pricingPlans:
    declarative:
      en:
        - name: Review Needed Starter
          priceCurrency: USD
          price: 0
          billingDuration: month
          unit: recurring
draftedComponents:
  - SLA
  - dataQuality
  - pricingPlans
reviewNotes:
  - pricingPlans drafted because no pricing terms were provided.
evidenceGaps:
  - No pricing terms were provided.
"""
        if prompt.startswith("# Assemble ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: customer-analytics
  name: Customer Analytics
  visibility: public
  status: draft
  type: dataset
  SLA:
    profiles:
      default:
        dimensions:
          - name: availability
            objective: 99.5
            unit: percent
  dataQuality:
    profiles:
      default:
        dimensions:
          - name: freshness
            objective: 24
            unit: hours
  pricingPlans:
    declarative:
      en:
        - name: Review Needed Starter
          priceCurrency: USD
          price: 0
          billingDuration: month
          unit: recurring
"""
        raise AssertionError(f"unexpected prompt: {prompt[:80]}")

    artifact = generate_local_artifacts_for_kind(
        "odps-product",
        source,
        tmp_path / "products",
        client=fake_client,
        profile="complete-draft",
    )[0]

    assert [prompt.splitlines()[0] for prompt in prompts] == [
        "# Extract ODPS Product Facts",
        "# Generate Minimal ODPS Product YAML",
        "# Draft ODPS Product Components",
        "# Assemble ODPS Product YAML",
    ]
    assert artifact.name == "odpsProduct:customer-analytics"
    assert artifact.valid_yaml is True
    assert artifact.drafted_components == ["SLA", "dataQuality", "pricingPlans"]
    assert artifact.review_notes == [
        "pricingPlans drafted because no pricing terms were provided."
    ]
    assert artifact.evidence_gaps == ["No pricing terms were provided."]
    document = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))
    assert {"SLA", "dataQuality", "pricingPlans"} <= set(document["product"])


def test_generate_odps_product_include_components_controls_component_prompt(tmp_path):
    """Test explicit component selection controls the component draft prompt."""
    source = tmp_path / "access-notes.md"
    source.write_text("Meeting notes for a partner API data product.", encoding="utf-8")
    component_prompts = []

    def fake_client(prompt, model):
        if prompt.startswith("# Extract ODPS Product Facts"):
            return "product:\n  productID: partner-api\n  name: Partner API\n"
        if prompt.startswith("# Generate Minimal ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: partner-api
  name: Partner API
  visibility: public
  status: draft
  type: API
"""
        if prompt.startswith("# Draft ODPS Product Components"):
            component_prompts.append(prompt)
            requested = prompt.split("Requested ODPS product components:", 1)[1]
            requested = requested.split("Minimal ODPS document:", 1)[0]
            assert "dataAccess" in requested
            assert "license" in requested
            assert "pricingPlans" not in requested
            return """components:
  dataAccess:
    default:
      outputPorttype: API
      format: JSON
      authenticationMethod: API key
  license:
    scopeOfUse: internal
draftedComponents:
  - dataAccess
  - license
reviewNotes:
  - dataAccess drafted from API context.
"""
        if prompt.startswith("# Assemble ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: partner-api
  name: Partner API
  visibility: public
  status: draft
  type: API
  dataAccess:
    default:
      outputPorttype: API
      format: JSON
      authenticationMethod: API key
  license:
    scopeOfUse: internal
"""
        raise AssertionError(f"unexpected prompt: {prompt[:80]}")

    artifact = generate_local_artifacts_for_kind(
        "odps-product",
        source,
        tmp_path / "products",
        client=fake_client,
        include_components=["dataAccess", "license"],
    )[0]

    assert len(component_prompts) == 1
    assert artifact.drafted_components == ["dataAccess", "license"]
    assert artifact.review_notes == ["dataAccess drafted from API context."]


def test_generate_odps_product_repairs_scalar_optional_component(tmp_path):
    """Test invalid scalar ODPS components trigger repair instead of crashing."""
    source = tmp_path / "license-notes.md"
    source.write_text(
        "Partner API product with a partner-use license.", encoding="utf-8"
    )
    prompt_headers = []

    def fake_client(prompt, model):
        prompt_headers.append(prompt.splitlines()[0])
        if prompt.startswith("# Extract ODPS Product Facts"):
            return "product:\n  productID: partner-api\n  name: Partner API\n"
        if prompt.startswith("# Generate Minimal ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: partner-api
  name: Partner API
  visibility: public
  status: draft
  type: API
"""
        if prompt.startswith("# Draft ODPS Product Components"):
            return """components:
  license: internal partner use only
draftedComponents:
  - license
reviewNotes:
  - License drafted from partner-use context.
"""
        if prompt.startswith("# Assemble ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: partner-api
  name: Partner API
  visibility: public
  status: draft
  type: API
  license: internal partner use only
"""
        if prompt.startswith("# Repair ODPS Product YAML"):
            assert "/product/license" in prompt
            assert "is not of type 'object'" in prompt
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: partner-api
  name: Partner API
  visibility: public
  status: draft
  type: API
  license:
    scopeOfUse: internal partner use only
    permanent: true
    exclusive: false
"""
        raise AssertionError(f"unexpected prompt: {prompt[:80]}")

    artifact = generate_local_artifacts_for_kind(
        "odps-product",
        source,
        tmp_path / "products",
        client=fake_client,
        include_components=["license"],
    )[0]

    assert "# Repair ODPS Product YAML" in prompt_headers
    assert artifact.valid_yaml is True
    assert artifact.errors == []
    document = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))
    assert document["product"]["license"]["scopeOfUse"] == "internal partner use only"


def test_generate_odps_product_normalizes_common_hosted_llm_schema_drift(tmp_path):
    """Test common hosted LLM ODPS schema drift is normalized before validation."""
    source = tmp_path / "customer-retention.md"
    source.write_text(
        "Customer retention analytics for internal lifecycle teams.",
        encoding="utf-8",
    )

    def fake_client(prompt, model):
        if prompt.startswith("# Extract ODPS Product Facts"):
            return """product:
  productID: customer-retention-analytics
  name: Customer Retention Analytics
"""
        if prompt.startswith("# Generate Minimal ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      productID: customer-retention-analytics
      name: Customer Retention Analytics
      visibility: internal
      status: draft
      type: dataset
      useCases:
        - Identify customers at renewal risk
        - Prioritize customer-success interventions
  dataAccess:
    API:
      outputPorttype: API
      format: warehouse-table
      authenticationMethod: API key
    API-2:
      outputPorttype: API
      format: semantic-model
      authenticationMethod: API key
"""
        raise AssertionError(f"unexpected prompt: {prompt[:80]}")

    artifact = generate_local_artifacts_for_kind(
        "odps-product",
        source,
        tmp_path / "products",
        client=fake_client,
    )[0]

    assert artifact.valid_yaml is True
    assert artifact.errors == []
    document = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))
    assert validate_document(document).valid is True
    english = document["product"]["details"]["en"]
    assert english["visibility"] == "organisation"
    assert english["useCases"] == [
        {
            "useCase": {
                "useCaseTitle": "Identify customers at renewal risk",
            },
        },
        {
            "useCase": {
                "useCaseTitle": "Prioritize customer-success interventions",
            },
        },
    ]
    assert "format" not in document["product"]["dataAccess"]["API"]
    assert "format" not in document["product"]["dataAccess"]["API-2"]


def test_generate_odps_product_truncates_overlong_license_restrictions(tmp_path):
    """Test generated license text is shortened to ODPS schema limits."""
    source = tmp_path / "license-notes.md"
    source.write_text(
        "Customer health product with internal restrictions.", encoding="utf-8"
    )
    long_restrictions = (
        "No external redistribution or resale; contact-level activation view "
        "restricted to approved marketing users with consent awareness controls; "
        "user-level product behavior aggregated to account level unless clear "
        "approved use case requires contact-level detail."
    )

    def fake_client(prompt, model):
        if prompt.startswith("# Extract ODPS Product Facts"):
            return "product:\n  productID: customer-health\n  name: Customer Health\n"
        if prompt.startswith("# Generate Minimal ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: customer-health
  name: Customer Health
  visibility: public
  status: draft
  type: dataset
"""
        if prompt.startswith("# Draft ODPS Product Components"):
            return f"""components:
  license:
    scope:
      definition: Internal use for customer retention workflows.
      restrictions: {long_restrictions}
draftedComponents:
  - license
reviewNotes:
  - License drafted from transcript context.
"""
        if prompt.startswith("# Assemble ODPS Product YAML"):
            return f"""schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: customer-health
  name: Customer Health
  visibility: public
  status: draft
  type: dataset
  license:
    scope:
      definition: Internal use for customer retention workflows.
      restrictions: {long_restrictions}
"""
        raise AssertionError(f"unexpected prompt: {prompt[:80]}")

    artifact = generate_local_artifacts_for_kind(
        "odps-product",
        source,
        tmp_path / "products",
        client=fake_client,
        include_components=["license"],
    )[0]

    assert artifact.valid_yaml is True
    assert artifact.errors == []
    document = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))
    restrictions = document["product"]["license"]["scope"]["restrictions"]
    assert len(restrictions) <= 255
    assert restrictions != long_restrictions


def test_generate_odps_product_drops_unsupported_pricing_plan_fields(tmp_path):
    """Test generated pricing plans keep only supported conservative ODPS fields."""
    source = tmp_path / "pricing-notes.md"
    source.write_text(
        "Partner API product with pricing pending approval.", encoding="utf-8"
    )

    def fake_client(prompt, model):
        if prompt.startswith("# Extract ODPS Product Facts"):
            return "product:\n  productID: partner-api\n  name: Partner API\n"
        if prompt.startswith("# Generate Minimal ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: partner-api
  name: Partner API
  visibility: public
  status: draft
  type: API
"""
        if prompt.startswith("# Draft ODPS Product Components"):
            return """components:
  pricingPlans:
    plans:
      - planID: partner-agreement-pending
        name: Partner Agreement Pricing
        description: Pricing model under partner agreements
        currency: USD
        billingCycle: Not specified
        price: 0
        unit: request
        paymentGateway:
          $ref: '#/product/paymentGateways/default'
        dataQuality:
          $ref: '#/product/dataQuality/default'
        SLA:
          $ref: '#/product/SLA/0'
        access:
          $ref: '#/product/dataAccess/API'
        conditions:
          - condition: Pricing terms pending approval
            description: Final pricing model is not approved
draftedComponents:
  - pricingPlans
reviewNotes:
  - Pricing terms pending approval.
"""
        if prompt.startswith("# Assemble ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: partner-api
  name: Partner API
  visibility: public
  status: draft
  type: API
  pricingPlans:
    plans:
      - planID: partner-agreement-pending
        name: Partner Agreement Pricing
        description: Pricing model under partner agreements
        currency: USD
        billingCycle: Not specified
        price: 0
        unit: request
        paymentGateway:
          $ref: '#/product/paymentGateways/default'
        dataQuality:
          $ref: '#/product/dataQuality/default'
        SLA:
          $ref: '#/product/SLA/0'
        access:
          $ref: '#/product/dataAccess/API'
        conditions:
          - condition: Pricing terms pending approval
            description: Final pricing model is not approved
"""
        raise AssertionError(f"unexpected prompt: {prompt[:80]}")

    artifact = generate_local_artifacts_for_kind(
        "odps-product",
        source,
        tmp_path / "products",
        client=fake_client,
        include_components=["pricingPlans"],
    )[0]

    assert artifact.valid_yaml is True
    document = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))
    plan = document["product"]["pricingPlans"]["declarative"]["en"][0]
    assert plan == {
        "name": "Partner Agreement Pricing",
        "priceCurrency": "USD",
        "price": "0",
        "unit": "On-request",
        "notes": (
            "Pricing model under partner agreements Pricing terms pending "
            "approval; Final pricing model is not approved"
        ),
        "paymentGateway": {"$ref": "#/product/paymentGateways/default"},
        "dataQuality": {"$ref": "#/product/dataQuality/default"},
        "access": {"$ref": "#/product/dataAccess/API"},
    }
    assert "SLA" not in plan


def test_generate_odps_product_normalizes_data_quality_component_shape(tmp_path):
    """Test generated data quality drafts keep only supported ODPS fields."""
    source = tmp_path / "inventory-notes.md"
    source.write_text("Inventory product with freshness concerns.", encoding="utf-8")

    def fake_client(prompt, model):
        if prompt.startswith("# Extract ODPS Product Facts"):
            return "product:\n  productID: inventory\n  name: Inventory\n"
        if prompt.startswith("# Generate Minimal ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: inventory
  name: Inventory
  visibility: public
  status: draft
  type: dataset
"""
        if prompt.startswith("# Draft ODPS Product Components"):
            return """components:
  dataQuality:
    dimensions:
      - name: freshness
        description: Inventory data should be refreshed every five minutes
        validationRules:
          - rule: Stale inventory snapshots trigger checks
            severity: high
      - name: completeness
        description: All required fields must be present
        objective: 95
        unit: percentage
    monitoring:
      description: Quality checks monitor freshness and completeness
draftedComponents:
  - dataQuality
reviewNotes:
  - Quality targets need review.
"""
        if prompt.startswith("# Assemble ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: inventory
  name: Inventory
  visibility: public
  status: draft
  type: dataset
  dataQuality:
    dimensions:
      - name: freshness
        description: Inventory data should be refreshed every five minutes
        validationRules:
          - rule: Stale inventory snapshots trigger checks
            severity: high
      - name: completeness
        description: All required fields must be present
        objective: 95
        unit: percentage
    monitoring:
      description: Quality checks monitor freshness and completeness
"""
        raise AssertionError(f"unexpected prompt: {prompt[:80]}")

    artifact = generate_local_artifacts_for_kind(
        "odps-product",
        source,
        tmp_path / "products",
        client=fake_client,
        include_components=["dataQuality"],
    )[0]

    assert artifact.valid_yaml is True
    document = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))
    assert document["product"]["dataQuality"] == {
        "declarative": {
            "default": {
                "name": {"en": "Default Data Quality"},
                "dimensions": [
                    {
                        "dimension": "timeliness",
                        "description": (
                            "Inventory data should be refreshed every five minutes"
                        ),
                    },
                    {
                        "dimension": "completeness",
                        "objective": 95,
                        "unit": "percentage",
                        "description": "All required fields must be present",
                    },
                ],
            }
        }
    }


def test_generate_odps_product_normalizes_sla_component_shape(tmp_path):
    """Test generated SLA drafts keep only supported ODPS dimensions and fields."""
    source = tmp_path / "checkout-notes.md"
    source.write_text(
        "Checkout product with latency and freshness needs.", encoding="utf-8"
    )

    def fake_client(prompt, model):
        if prompt.startswith("# Extract ODPS Product Facts"):
            return "product:\n  productID: checkout\n  name: Checkout\n"
        if prompt.startswith("# Generate Minimal ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: checkout
  name: Checkout
  visibility: public
  status: draft
  type: API
"""
        if prompt.startswith("# Draft ODPS Product Components"):
            return """components:
  SLA:
    profiles:
      default:
        dimensions:
          - name: availability
            objective: 99.5
            unit: percent
            scope: Marketplace trading hours
            description: High availability target
          - name: latency
            objective: 500
            unit: milliseconds
            description: Response time target
          - name: dataFreshness
            objective: 5
            unit: minutes
            description: Target refresh interval
          - name: refreshTimeliness
            objective: 2
            unit: hours
            description: Maximum refresh delay
        support:
          description: Support hours not specified
draftedComponents:
  - SLA
reviewNotes:
  - Support hours need review.
"""
        if prompt.startswith("# Assemble ODPS Product YAML"):
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: checkout
  name: Checkout
  visibility: public
  status: draft
  type: API
  SLA:
    profiles:
      default:
        dimensions:
          - name: availability
            objective: 99.5
            unit: percent
            scope: Marketplace trading hours
            description: High availability target
          - name: latency
            objective: 500
            unit: milliseconds
            description: Response time target
          - name: dataFreshness
            objective: 5
            unit: minutes
            description: Target refresh interval
          - name: refreshTimeliness
            objective: 2
            unit: hours
            description: Maximum refresh delay
        support:
          description: Support hours not specified
"""
        raise AssertionError(f"unexpected prompt: {prompt[:80]}")

    artifact = generate_local_artifacts_for_kind(
        "odps-product",
        source,
        tmp_path / "products",
        client=fake_client,
        include_components=["SLA"],
    )[0]

    assert artifact.valid_yaml is True
    document = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))
    assert document["product"]["SLA"] == {
        "declarative": {
            "default": {
                "name": {"en": "Default SLA"},
                "dimensions": [
                    {"dimension": "uptime", "objective": "99.5", "unit": "percent"},
                    {
                        "dimension": "latency",
                        "objective": "500",
                        "unit": "milliseconds",
                    },
                    {
                        "dimension": "updateFrequency",
                        "objective": "5",
                        "unit": "minutes",
                    },
                    {
                        "dimension": "updateFrequency",
                        "objective": "120",
                        "unit": "minutes",
                    },
                ],
            }
        }
    }


def test_generate_odps_product_chunks_long_sources_before_minimal_yaml(tmp_path):
    """Test long ODPS sources are chunked before merged facts drive YAML."""
    source = tmp_path / "long-transcript.txt"
    source.write_text(
        "Customer analytics product discussion. " * 20,
        encoding="utf-8",
    )
    prompt_headers = []

    def fake_client(prompt, model):
        prompt_headers.append(prompt.splitlines()[0])
        if prompt.startswith("# Extract ODPS Product Facts"):
            source_chunk = prompt.split("```text", 1)[1]
            assert len(source_chunk) < 420
            return """product:
  productID: customer-analytics
  name: Customer Analytics
chunkEvidence:
  - retention data product
"""
        if prompt.startswith("# Merge ODPS Product Facts"):
            assert "retention data product" in prompt
            return """product:
  productID: customer-analytics
  name: Customer Analytics
evidenceGaps:
  - Pricing is not discussed.
"""
        if prompt.startswith("# Generate Minimal ODPS Product YAML"):
            assert "Pricing is not discussed." in prompt
            return """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: customer-analytics
  name: Customer Analytics
  visibility: public
  status: draft
  type: dataset
"""
        raise AssertionError(f"unexpected prompt: {prompt[:80]}")

    artifact = generate_local_artifacts_for_kind(
        "odps-product",
        source,
        tmp_path / "products",
        client=fake_client,
        max_source_chars=180,
    )[0]

    assert prompt_headers.count("# Extract ODPS Product Facts") > 1
    assert "# Merge ODPS Product Facts" in prompt_headers
    assert prompt_headers[-1] == "# Generate Minimal ODPS Product YAML"
    assert artifact.evidence_gaps == ["Pricing is not discussed."]
    assert artifact.valid_yaml is True


def test_generate_odps_product_rejects_unknown_include_component(tmp_path):
    """Test unknown ODPS component names fail before LLM calls."""
    source = tmp_path / "product.md"
    source.write_text("A product.", encoding="utf-8")

    with pytest.raises(ValueError) as exc:
        generate_local_artifacts_for_kind(
            "odps-product",
            source,
            tmp_path / "products",
            client=lambda prompt, model: "",
            include_components=["unknown"],
        )

    assert "Unknown ODPS product component: unknown" in str(exc.value)


def test_generate_local_artifact_extracts_yaml_after_model_prose(tmp_path):
    """Test models that prepend reasoning can still yield valid fragments."""
    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "turnaround-delay-signal.txt",
        tmp_path,
        client=lambda prompt, model: """We must include fields: id, name, description, type, source, and observedAt.

signals:
- id: turnaround-delay-spike-signal
  name:
    en: Turnaround Delay Spike Signal
  description:
    en: Turnaround delay increased at Terminal 2.
  type: operational
  source:
    origin: internal
    method: ground operations event log
  observedAt: "2026-05-20T00:00:00Z"
""",
    )

    assert artifact.valid_yaml is True
    assert (
        artifact.output_path == tmp_path / "signal_turnaround-delay-spike-signal.yaml"
    )


def test_generate_local_artifact_rejects_wrong_fragment_shape(tmp_path):
    """Test that generic YAML is not accepted as a useful fragment."""
    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "turnaround-delay-signal.txt",
        tmp_path,
        client=lambda prompt, model: "items: []",
    )

    assert artifact.valid_yaml is False
    assert "expected root key `signals`" in artifact.errors[0]


def test_generate_local_artifact_rejects_schema_invalid_fragment(tmp_path):
    """Test that ODPC-shaped roots still need schema-valid contents."""
    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "turnaround-delay-signal.txt",
        tmp_path,
        client=lambda prompt, model: """signals:
- id: SIG-001
  name.en: Broken
  description.en: Broken
  type: operational
  source:
    origin: free text is not valid here
    method: test
  observedAt: "2026-05-20T00:00:00Z"
""",
    )

    assert artifact.valid_yaml is False
    assert artifact.errors


def test_generate_local_artifact_normalizes_signal_id_name_mismatch(tmp_path):
    """Test that repairable signal ids are normalized from the signal name."""
    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "security-queue-surge-signal.txt",
        tmp_path,
        client=lambda prompt, model: """signals:
- id: passenger-connection-protection-signal
  name:
    en: Security Queue Surge Signal
  description:
    en: Security queues exceeded the target threshold.
  type: operational
  source:
    origin: internal
    method: passenger flow queue measurements
  observedAt: "2026-05-21T07:10:00Z"
""",
    )

    assert artifact.valid_yaml is True
    assert yaml.safe_load(artifact.output_path.read_text(encoding="utf-8")) == {
        "signal": {
            "id": "security-queue-surge-signal",
            "name": {"en": "Security Queue Surge Signal"},
            "description": {"en": "Security queues exceeded the target threshold."},
            "type": "operational",
            "source": {
                "origin": "internal",
                "method": "passenger flow queue measurements",
            },
            "observedAt": "2026-05-21T07:10:00Z",
        }
    }


def test_generate_local_artifact_normalizes_signal_enum_aliases(tmp_path):
    """Test that common signal enum aliases are normalized before validation."""
    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "inbound-connection-risk-signal.txt",
        tmp_path,
        client=lambda prompt, model: """signals:
- id: inbound-connection-risk-signal
  name:
    en: Inbound Connection Risk Signal
  description:
    en: Connections are at risk.
  type: operational
  source:
    origin: internal
    method: connection reliability estimates
  observedAt: "2026-05-22T00:00:00Z"
  impact:
    valuePotential: moderate
    urgency: moderate
""",
    )

    assert artifact.valid_yaml is True
    signal = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))["signal"]
    assert signal["impact"]["valuePotential"] == "medium"
    assert signal["impact"]["urgency"] == "medium"


def test_generate_local_artifact_removes_objective_relationship_fields(tmp_path):
    """Test that objective graph relationship fields are removed from fragments."""
    artifact = generate_local_artifact(
        "objective",
        GENERATION_SOURCE_DOCS / "airport-business-objective.txt",
        tmp_path,
        client=lambda prompt, model: """businessObjectives:
- id: reduce-departure-delay-minutes
  name:
    en: Reduce Departure Delay Minutes
  description:
    en: Reduce delay minutes.
  linkedUseCases:
    - flight-delay-risk-monitoring
  dataProducts:
    - airport-operations-performance
""",
    )

    assert artifact.valid_yaml is True
    objective = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))[
        "businessObjective"
    ]
    assert "linkedUseCases" not in objective
    assert "dataProducts" not in objective


def test_generate_local_artifact_rejects_schema_invalid_graph(tmp_path):
    """Test that graph-shaped YAML still needs ODPG graph fields."""
    artifact = generate_local_artifact(
        "graph",
        GENERATION_SOURCE_DOCS,
        tmp_path,
        client=lambda prompt, model: """schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: "1.0"
kind: Graph
graph:
  nodes:
    - id: airport-operations-performance
      label: DataProduct
  edges:
    - source: flight-delay-risk-monitoring
      target: airport-operations-performance
      label: depends_on
""",
    )

    assert artifact.valid_yaml is False
    assert any("graph.metadata" in error for error in artifact.errors)


def test_generate_local_artifacts_repairs_graph_missing_generated_nodes(tmp_path):
    """Test that holistic graph output adds nodes for generated fragment ids."""

    def fake_client(prompt: str, model: str) -> str:
        if prompt.startswith("# Generate ODPG Graph YAML"):
            return """schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: "1.0"
kind: Graph
graph:
  metadata:
    id: airports-graph
    name:
      en: Airports Graph
    description:
      en: Incomplete graph.
  nodes: []
  edges: []
"""
        if prompt.startswith("# Generate ODPS"):
            return """productReferences:
- id: airport-operations-performance
  productID: airport-operations-performance
  productVersion: "1.0.0"
  name:
    en: Airport Operations Performance Data Product
  description:
    en: Airport operations data.
  productModel:
    standard: ODPS
    version: "4.1"
    format: yaml
    $ref: products/airport-operations-performance.yaml
"""
        if prompt.startswith("# Generate ODPC Use Case"):
            return "useCases: []\n"
        if prompt.startswith("# Generate ODPC Business Objective"):
            return "businessObjectives: []\n"
        return "signals: []\n"

    artifacts = generate_local_artifacts(
        GENERATION_SOURCE_DOCS, tmp_path, client=fake_client
    )

    graph_artifact = artifacts[-1]
    assert graph_artifact.name == "odpg_graph"
    assert graph_artifact.valid_yaml is True
    graph = yaml.safe_load(graph_artifact.output_path.read_text(encoding="utf-8"))
    assert graph["graph"]["nodes"] == [
        {
            "id": "airport-operations-performance",
            "type": "DataProduct",
            "$ref": "product_reference_airport-operations-performance.yaml",
        }
    ]


def test_generate_local_artifacts_repairs_graph_refs_to_fragment_files(tmp_path):
    """Test that graph nodes use generated fragment file references."""

    def fake_client(prompt: str, model: str) -> str:
        if prompt.startswith("# Generate ODPG Graph YAML"):
            return """schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: "1.0"
kind: Graph
graph:
  metadata:
    id: airports-graph
    name:
      en: Airports Graph
    description:
      en: Graph with stale aggregate refs.
  nodes:
    - id: test-signal
      type: StrategicOpportunity
      $ref: odpc_signals.yaml#/signals/0
  edges: []
"""
        if prompt.startswith("# Generate ODPS"):
            return "productReferences: []\n"
        if prompt.startswith("# Generate ODPC Use Case"):
            return "useCases: []\n"
        if prompt.startswith("# Generate ODPC Business Objective"):
            return "businessObjectives: []\n"
        return """signals:
- id: test-signal
  name:
    en: Test Signal
  description:
    en: Test signal.
  type: operational
  source:
    origin: internal
    method: test
  observedAt: "2026-05-20T00:00:00Z"
"""

    artifacts = generate_local_artifacts(
        GENERATION_SOURCE_DOCS, tmp_path, client=fake_client
    )

    graph = yaml.safe_load(artifacts[-1].output_path.read_text(encoding="utf-8"))
    assert graph["graph"]["nodes"] == [
        {
            "id": "test-signal",
            "type": "Signal",
            "$ref": "signal_test-signal.yaml",
        }
    ]


def test_generate_local_artifact_rejects_unknown_kind(tmp_path):
    """Test that unsupported artifact kinds fail clearly."""
    try:
        generate_local_artifact(
            "catalog",
            GENERATION_SOURCE_DOCS,
            tmp_path,
            client=lambda prompt, model: "items: []",
        )
    except KeyError as exc:
        assert "Unknown generation artifact kind" in str(exc)
    else:
        raise AssertionError("unknown artifact kind did not raise KeyError")
