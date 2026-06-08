"""LLM generation prompt and provider helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import ssl
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
from urllib import error, request

import certifi
import yaml

_PROMPT_DIR = Path(__file__).resolve().parent / "data" / "prompts"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OPENAI_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_CHAT_URL = "http://localhost:1234/v1"
DEFAULT_ANTHROPIC_URL = "https://api.anthropic.com/v1"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MAX_TOKENS = 8192
DEFAULT_GENERATION_MODEL = "qwen2.5"
DEFAULT_OLLAMA_GENERATE_TIMEOUT = 300
DEFAULT_OPENAI_GENERATE_TIMEOUT = 300
DEFAULT_OPENAI_USER_AGENT = "open-data-products-python/0.2"
DEFAULT_GENERATION_CONFIG = Path(__file__).resolve().parent / "generation.config.yaml"
ODPS_SLA_DIMENSIONS = {
    "latency",
    "uptime",
    "responseTime",
    "errorRate",
    "endOfSupport",
    "endOfLife",
    "updateFrequency",
    "timeToDetect",
    "timeToNotify",
    "timeToRepair",
    "emailResponseTime",
}
ODPS_SLA_DIMENSION_ALIASES = {
    "availability": "uptime",
    "available": "uptime",
    "freshness": "updateFrequency",
    "datafreshness": "updateFrequency",
    "data-freshness": "updateFrequency",
    "refresh": "updateFrequency",
    "refreshtimeliness": "updateFrequency",
    "refresh-timeliness": "updateFrequency",
    "refreshfrequency": "updateFrequency",
    "refresh-frequency": "updateFrequency",
}
ODPS_SLA_UNITS = {
    "percent",
    "milliseconds",
    "seconds",
    "minutes",
    "days",
    "weeks",
    "months",
    "years",
    "never",
    "date",
    "null",
}
ODPS_DATA_QUALITY_DIMENSIONS = {
    "accuracy",
    "completeness",
    "conformity",
    "consistency",
    "coverage",
    "timeliness",
    "validity",
    "uniqueness",
}
ODPS_DATA_QUALITY_DIMENSION_ALIASES = {
    "freshness": "timeliness",
    "datafreshness": "timeliness",
    "data-freshness": "timeliness",
}
ODPS_DATA_QUALITY_UNITS = {"percentage", "number"}
ODPS_PRODUCT_TYPES = {
    "raw data",
    "derived data",
    "dataset",
    "reports",
    "analytic view",
    "3D visualisation",
    "algorithm",
    "decision support",
    "automated decision-making",
    "data-enhanced product",
    "data-driven service",
    "data-enabled performance",
    "bi-directional",
}
ODPS_PRODUCT_TYPE_ALIASES = {
    "api": "data-driven service",
    "service": "data-driven service",
    "data-service": "data-driven service",
    "ml-model": "algorithm",
    "model": "algorithm",
    "dashboard": "reports",
    "report": "reports",
}
ODPS_GENERATION_PROFILES = ("minimal", "complete-draft")
ODPS_COMPLETE_DRAFT_COMPONENTS = ("SLA", "dataQuality", "pricingPlans")
ODPS_PRODUCT_COMPONENTS = (
    "contract",
    "SLA",
    "dataQuality",
    "pricingPlans",
    "license",
    "dataAccess",
    "dataHolder",
    "paymentGateways",
    "productStrategy",
)
ODPS_PRODUCT_COMPONENT_ALIASES = {
    "contract": "contract",
    "sla": "SLA",
    "SLA": "SLA",
    "dq": "dataQuality",
    "DQ": "dataQuality",
    "dataquality": "dataQuality",
    "dataQuality": "dataQuality",
    "pricing": "pricingPlans",
    "pricingplans": "pricingPlans",
    "pricingPlans": "pricingPlans",
    "license": "license",
    "dataaccess": "dataAccess",
    "dataAccess": "dataAccess",
    "dataholder": "dataHolder",
    "dataHolder": "dataHolder",
    "paymentgateways": "paymentGateways",
    "paymentGateways": "paymentGateways",
    "productstrategy": "productStrategy",
    "productStrategy": "productStrategy",
}
BUILT_IN_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "ollama": {
        "type": "ollama",
        "model": DEFAULT_GENERATION_MODEL,
        "baseUrl": DEFAULT_OLLAMA_URL,
    },
    "openai": {
        "type": "openai",
        "model": "gpt-4.1-mini",
        "baseUrl": DEFAULT_OPENAI_URL,
        "apiKeyEnv": "OPENAI_API_KEY",
    },
    "openrouter": {
        "type": "openai",
        "model": "openai/gpt-4.1-mini",
        "baseUrl": "https://openrouter.ai/api/v1",
        "apiKeyEnv": "OPENROUTER_API_KEY",
    },
    "groq": {
        "type": "openai",
        "model": "openai/gpt-oss-120b",
        "baseUrl": "https://api.groq.com/openai/v1",
        "apiKeyEnv": "GROQ_API_KEY",
    },
    "lmstudio": {
        "type": "openai-chat",
        "model": "local-model",
        "baseUrl": "http://localhost:1234/v1",
    },
    "vllm": {
        "type": "openai-chat",
        "model": "local-model",
        "baseUrl": "http://localhost:8000/v1",
    },
    "claude": {
        "type": "anthropic",
        "model": "claude-sonnet-4-5",
        "baseUrl": DEFAULT_ANTHROPIC_URL,
        "apiKeyEnv": "ANTHROPIC_API_KEY",
        "version": DEFAULT_ANTHROPIC_VERSION,
        "maxTokens": DEFAULT_ANTHROPIC_MAX_TOKENS,
    },
    "anthropic": {
        "type": "anthropic",
        "model": "claude-sonnet-4-5",
        "baseUrl": DEFAULT_ANTHROPIC_URL,
        "apiKeyEnv": "ANTHROPIC_API_KEY",
        "version": DEFAULT_ANTHROPIC_VERSION,
        "maxTokens": DEFAULT_ANTHROPIC_MAX_TOKENS,
    },
}

ModelClient = Callable[[str, str], str]


@dataclass(frozen=True)
class GenerationTask:
    """Prompt and output mapping for one local generation artifact."""

    name: str
    prompt_name: str
    output_name: str
    expected_root: str
    fragment_root: Optional[str] = None
    filename_prefix: Optional[str] = None
    graph_node_type: Optional[str] = None


@dataclass(frozen=True)
class GenerationSettings:
    """Resolved LLM generation provider and path settings."""

    provider: str
    model: str
    input_path: str
    output_path: str
    provider_type: str = "ollama"
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    api_version: Optional[str] = None
    max_tokens: Optional[int] = None
    prompt_path: Optional[str] = None


@dataclass(frozen=True)
class GeneratedArtifact:
    """Generated YAML artifact metadata."""

    name: str
    prompt_name: str
    output_path: Path
    valid_yaml: bool
    errors: List[str] = field(default_factory=list)
    review_notes: List[str] = field(default_factory=list)
    drafted_components: List[str] = field(default_factory=list)
    evidence_gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-ready artifact summary."""
        return {
            "name": self.name,
            "prompt": self.prompt_name,
            "output": str(self.output_path),
            "valid_yaml": self.valid_yaml,
            "errors": list(self.errors),
            "review_notes": list(self.review_notes),
            "drafted_components": list(self.drafted_components),
            "evidence_gaps": list(self.evidence_gaps),
        }


GENERATION_TASKS: Sequence[GenerationTask] = (
    GenerationTask(
        name="odpc_product_references",
        prompt_name="odps_data_product_fragment.md",
        output_name="odpc_product_references.yaml",
        expected_root="productReferences",
        fragment_root="productReference",
        filename_prefix="product_reference",
        graph_node_type="DataProduct",
    ),
    GenerationTask(
        name="odps_products",
        prompt_name="odps_product_minimal_yaml.md",
        output_name="odps_product.yaml",
        expected_root="product",
        filename_prefix="odps_product",
        graph_node_type="DataProduct",
    ),
    GenerationTask(
        name="odpc_use_cases",
        prompt_name="odpc_use_case_fragment.md",
        output_name="odpc_use_cases.yaml",
        expected_root="useCases",
        fragment_root="useCase",
        filename_prefix="use_case",
        graph_node_type="UseCase",
    ),
    GenerationTask(
        name="odpc_objectives",
        prompt_name="odpc_objective_fragment.md",
        output_name="odpc_objectives.yaml",
        expected_root="businessObjectives",
        fragment_root="businessObjective",
        filename_prefix="business_objective",
        graph_node_type="BusinessObjective",
    ),
    GenerationTask(
        name="odpc_signals",
        prompt_name="odpc_signal_fragment.md",
        output_name="odpc_signals.yaml",
        expected_root="signals",
        fragment_root="signal",
        filename_prefix="signal",
        graph_node_type="Signal",
    ),
    GenerationTask(
        name="odpg_graph",
        prompt_name="odpg_graph_yaml.md",
        output_name="odpg_graph.yaml",
        expected_root="graph",
    ),
)

HOLISTIC_GENERATION_TASKS: Sequence[GenerationTask] = tuple(
    task for task in GENERATION_TASKS if task.name != "odps_products"
)

GENERATION_TASK_ALIASES = {
    "product-reference": "odpc_product_references",
    "product-references": "odpc_product_references",
    "odpc-product-reference": "odpc_product_references",
    "odpc-product-references": "odpc_product_references",
    "odps-product": "odps_products",
    "odps-products": "odps_products",
    "use-case": "odpc_use_cases",
    "usecase": "odpc_use_cases",
    "use-cases": "odpc_use_cases",
    "objective": "odpc_objectives",
    "objectives": "odpc_objectives",
    "business-objective": "odpc_objectives",
    "signal": "odpc_signals",
    "signals": "odpc_signals",
    "graph": "odpg_graph",
    "odpg": "odpg_graph",
}


def list_generation_prompts(prompt_dir: Optional[PathLike] = None) -> List[str]:
    """List bundled local generation prompt filenames."""
    root = Path(prompt_dir) if prompt_dir else _PROMPT_DIR
    return sorted(path.name for path in root.glob("*.md"))


def load_generation_prompt(name: str, prompt_dir: Optional[PathLike] = None) -> str:
    """Load a bundled local generation prompt by filename."""
    if "/" in name or "\\" in name:
        raise KeyError(f"Unknown generation prompt: {name}")

    prompt_path = (Path(prompt_dir) if prompt_dir else _PROMPT_DIR) / name
    if not prompt_path.is_file():
        raise KeyError(f"Unknown generation prompt: {name}")
    return prompt_path.read_text(encoding="utf-8")


def copy_generation_prompts(
    destination: PathLike,
    *,
    overwrite: bool = False,
) -> List[Path]:
    """Copy bundled generation prompts to a user-editable folder."""
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for prompt_path in sorted(_PROMPT_DIR.glob("*.md")):
        output = target / prompt_path.name
        if output.exists() and not overwrite:
            raise FileExistsError(f"Prompt file already exists: {output}")
        shutil.copyfile(prompt_path, output)
        copied.append(output)
    return copied


PathLike = Union[str, Path]


def load_source_documents(source_dir: PathLike) -> str:
    """Load Markdown and text source documents as one prompt context."""
    paths = _source_document_paths(source_dir)

    if not paths:
        raise ValueError(f"No Markdown or text source documents found at {source_dir}")

    sections = []
    for path in paths:
        sections.append(
            "\n".join(
                [
                    f"--- Source file: {path.name} ---",
                    path.read_text(encoding="utf-8").strip(),
                ]
            )
        )
    return "\n\n".join(sections)


def _source_document_paths(source: PathLike) -> List[Path]:
    root = Path(source)
    if root.is_file():
        return [root]
    if root.is_dir():
        return sorted(
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in {".md", ".txt"}
        )
    raise FileNotFoundError(f"Source document path not found: {root}")


def render_generation_prompt(
    prompt_name: str,
    source_dir: PathLike,
    prompt_dir: Optional[PathLike] = None,
) -> str:
    """Render a generation prompt with source documents inlined."""
    return load_generation_prompt(prompt_name, prompt_dir=prompt_dir).replace(
        "{source_documents}",
        load_source_documents(source_dir),
    )


def ollama_generate(
    prompt: str,
    model: str = DEFAULT_GENERATION_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
) -> str:
    """Generate text with a local Ollama model."""
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
    ).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=DEFAULT_OLLAMA_GENERATE_TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8"))
    generated = data.get("response")
    if not isinstance(generated, str):
        raise RuntimeError("Ollama response did not contain generated text.")
    return generated


def list_ollama_models(base_url: str = DEFAULT_OLLAMA_URL) -> List[str]:
    """List models available from the local Ollama server."""
    req = request.Request(
        f"{base_url.rstrip('/')}/api/tags",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, error.URLError) as exc:
        raise RuntimeError(
            "Ollama is required for local generation but is not reachable at "
            f"{base_url}. Start Ollama before running generation."
        ) from exc

    models = data.get("models", [])
    if not isinstance(models, list):
        return []

    names = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if isinstance(name, str):
            names.append(name)
    return names


def ensure_ollama_model(
    model: str = DEFAULT_GENERATION_MODEL,
    base_url: str = DEFAULT_OLLAMA_URL,
) -> None:
    """Require the configured local Ollama model before generation."""
    available = list_ollama_models(base_url)
    matches = {model, f"{model}:latest"}
    if not any(name in matches or name.startswith(f"{model}:") for name in available):
        raise RuntimeError(
            f"Required Ollama model {model} is not available. "
            f"Run `ollama pull {model}` before local generation."
        )


def openai_generate(
    prompt: str,
    model: str,
    api_key_env: str = "OPENAI_API_KEY",
    base_url: str = DEFAULT_OPENAI_URL,
) -> str:
    """Generate text with the OpenAI Responses API."""
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"OpenAI generation requires environment variable {api_key_env}. "
            "Set it before running generation."
        )
    _require_ascii_api_key(api_key, api_key_env, "OpenAI-compatible")

    payload = json.dumps({"model": model, "input": prompt}).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/responses",
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": DEFAULT_OPENAI_USER_AGENT,
        },
        method="POST",
    )
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with request.urlopen(
            req, timeout=DEFAULT_OPENAI_GENERATE_TIMEOUT, context=context
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = _http_error_detail(exc)
        message = f"OpenAI generation request failed with HTTP {exc.code}."
        if detail:
            message = f"{message} {detail}"
        raise RuntimeError(message) from exc
    except (OSError, error.URLError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"OpenAI generation request failed: {reason}") from exc

    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text

    output = data.get("output")
    if isinstance(output, list):
        parts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                text = content_item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "\n".join(parts)

    raise RuntimeError("OpenAI response did not contain generated text.")


def openai_chat_generate(
    prompt: str,
    model: str,
    api_key_env: Optional[str] = None,
    base_url: str = DEFAULT_OPENAI_CHAT_URL,
) -> str:
    """Generate text with an OpenAI-compatible chat completions API."""
    api_key = os.environ.get(api_key_env) if api_key_env else None
    if api_key_env and not api_key:
        raise RuntimeError(
            f"OpenAI-compatible chat generation requires environment variable "
            f"{api_key_env}. Set it before running generation."
        )
    if api_key and api_key_env:
        _require_ascii_api_key(api_key, api_key_env, "OpenAI-compatible chat")

    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
    ).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": DEFAULT_OPENAI_USER_AGENT,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=DEFAULT_OPENAI_GENERATE_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = _http_error_detail(exc)
        message = f"OpenAI-compatible chat request failed with HTTP {exc.code}."
        if detail:
            message = f"{message} {detail}"
        raise RuntimeError(message) from exc
    except (OSError, error.URLError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"OpenAI-compatible chat request failed: {reason}") from exc

    choices = data.get("choices")
    if isinstance(choices, list):
        parts = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                parts.append(message["content"])
            elif isinstance(choice.get("text"), str):
                parts.append(choice["text"])
        if parts:
            return "\n".join(parts)

    raise RuntimeError(
        "OpenAI-compatible chat response did not contain generated text."
    )


def anthropic_generate(
    prompt: str,
    model: str,
    api_key_env: str = "ANTHROPIC_API_KEY",
    base_url: str = DEFAULT_ANTHROPIC_URL,
    version: str = DEFAULT_ANTHROPIC_VERSION,
    max_tokens: int = DEFAULT_ANTHROPIC_MAX_TOKENS,
) -> str:
    """Generate text with the Anthropic Messages API."""
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"Anthropic generation requires environment variable {api_key_env}. "
            "Set it before running generation."
        )
    _require_ascii_api_key(api_key, api_key_env, "Anthropic")

    payload = json.dumps(
        {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/messages",
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": version,
            "User-Agent": DEFAULT_OPENAI_USER_AGENT,
        },
        method="POST",
    )
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with request.urlopen(
            req, timeout=DEFAULT_OPENAI_GENERATE_TIMEOUT, context=context
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = _http_error_detail(exc)
        message = f"Anthropic generation request failed with HTTP {exc.code}."
        if detail:
            message = f"{message} {detail}"
        raise RuntimeError(message) from exc
    except (OSError, error.URLError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"Anthropic generation request failed: {reason}") from exc

    content = data.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        if parts:
            return "\n".join(parts)

    raise RuntimeError("Anthropic response did not contain generated text.")


def _require_ascii_api_key(api_key: str, api_key_env: str, provider: str) -> None:
    try:
        api_key.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError(
            f"{provider} generation requires {api_key_env} to contain only ASCII "
            "characters. Re-export the API key using plain quotes."
        ) from exc


def _http_error_detail(exc: error.HTTPError) -> str:
    """Return a short, non-secret provider error detail when available."""
    try:
        raw = exc.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:500]
    error_value = parsed.get("error") if isinstance(parsed, dict) else None
    if isinstance(error_value, dict):
        message = error_value.get("message")
        if isinstance(message, str):
            return message[:500]
    if isinstance(error_value, str):
        return error_value[:500]
    return raw[:500]


def load_generation_config(path: PathLike) -> Dict[str, Any]:
    """Load a generation config YAML file."""
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Generation config not found: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Generation config must be a YAML mapping.")
    return data


def get_config_path(domain: str = "generation") -> Path:
    """Return the bundled config template path for a settings domain."""
    if domain != "generation":
        raise KeyError(f"Unknown config domain: {domain}")
    return DEFAULT_GENERATION_CONFIG


def get_config(
    domain: str = "generation",
    config_path: Optional[PathLike] = None,
) -> Dict[str, Any]:
    """Return a safe, user-facing config summary."""
    if domain != "generation":
        raise KeyError(f"Unknown config domain: {domain}")

    source_path = Path(config_path) if config_path else DEFAULT_GENERATION_CONFIG
    config = load_generation_config(source_path)
    settings = resolve_generation_settings(source_path)
    providers = config.get("providers")
    providers = providers if isinstance(providers, dict) else {}
    return {
        "domain": "generation",
        "template_path": str(DEFAULT_GENERATION_CONFIG),
        "config_path": str(source_path),
        "editable": config_path is not None,
        "copy_hint": (
            "Copy this template to your project, edit provider/model settings, "
            "then pass it with `open-data-products generate --config <path>`."
        ),
        "selected_provider": settings.provider,
        "resolved": _generation_settings_dict(settings),
        "providers": _provider_summaries(providers),
        "prompts": settings.prompt_path,
    }


def print_config(
    domain: str = "generation",
    config_path: Optional[PathLike] = None,
) -> str:
    """Return the raw YAML config template or user config content."""
    if domain != "generation":
        raise KeyError(f"Unknown config domain: {domain}")
    source_path = Path(config_path) if config_path else DEFAULT_GENERATION_CONFIG
    if not source_path.is_file():
        raise FileNotFoundError(f"Generation config not found: {source_path}")
    return source_path.read_text(encoding="utf-8")


def validate_config(
    domain: str = "generation",
    config_path: Optional[PathLike] = None,
) -> Dict[str, Any]:
    """Validate a user-editable config file without contacting providers."""
    if domain != "generation":
        raise KeyError(f"Unknown config domain: {domain}")

    source_path = Path(config_path) if config_path else DEFAULT_GENERATION_CONFIG
    errors: List[str] = []
    warnings: List[str] = []
    try:
        config = load_generation_config(source_path)
    except (FileNotFoundError, ValueError) as exc:
        return {
            "domain": "generation",
            "config_path": str(source_path),
            "valid": False,
            "errors": [str(exc)],
            "warnings": [],
            "resolved": None,
        }

    allowed_top = {
        "provider",
        "model",
        "input",
        "output",
        "prompts",
        "baseUrl",
        "providers",
        "version",
        "maxTokens",
    }
    for key in config:
        if key not in allowed_top:
            errors.append(f"Unknown top-level generation config key: {key}")

    providers = config.get("providers")
    if providers is not None and not isinstance(providers, dict):
        errors.append("providers must be a mapping")
        providers = {}
    providers = providers if isinstance(providers, dict) else {}

    provider_name = config.get("provider")
    if provider_name is not None and not isinstance(provider_name, str):
        errors.append("provider must be a string")
        provider_name = None
    if provider_name is None:
        errors.append("provider is required in generation config files")
    selected_provider = provider_name or ""
    built_in_providers = {"ollama", "openai", "anthropic"}
    if (
        selected_provider
        and selected_provider not in providers
        and selected_provider not in built_in_providers
    ):
        errors.append(f"providers.{selected_provider} is missing")

    _validate_optional_string(config, "model", "model", errors)
    _validate_optional_string(config, "input", "input", errors)
    _validate_optional_string(config, "output", "output", errors)
    _validate_optional_string(config, "prompts", "prompts", errors)
    _validate_optional_string(config, "baseUrl", "baseUrl", errors)
    _validate_optional_string(config, "version", "version", errors)
    _validate_optional_positive_int(config, "maxTokens", "maxTokens", errors)
    _validate_generation_paths(config, source_path, errors, warnings)
    _find_secret_values(config, "", errors)

    if not _has_configured_model(config, providers, selected_provider):
        errors.append("model is required at top level or on the selected provider")

    for name, value in providers.items():
        provider_path = f"providers.{name}"
        if not isinstance(name, str):
            errors.append("provider names must be strings")
            continue
        if not isinstance(value, dict):
            errors.append(f"{provider_path} must be a mapping")
            continue
        _validate_provider_config(provider_path, value, errors, warnings)

    resolved = None
    if not errors:
        try:
            resolved = _generation_settings_dict(
                resolve_generation_settings(source_path)
            )
        except ValueError as exc:
            errors.append(str(exc))

    return {
        "domain": "generation",
        "config_path": str(source_path),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "resolved": resolved,
    }


def copy_config_template(
    domain: str,
    destination: PathLike,
    *,
    overwrite: bool = False,
) -> Path:
    """Copy a bundled config template to a user-editable file."""
    source = get_config_path(domain)
    destination_text = str(destination)
    target = Path(destination)
    if target.is_dir() or destination_text.endswith(("/", "\\")):
        target = target / source.name
    if target.exists() and not overwrite:
        raise FileExistsError(f"Config file already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def _validate_provider_config(
    path: str,
    provider: Dict[str, Any],
    errors: List[str],
    warnings: List[str],
) -> None:
    allowed_provider = {"type", "model", "baseUrl", "apiKeyEnv", "version", "maxTokens"}
    allowed_types = {"anthropic", "ollama", "openai", "openai-chat"}
    for key in provider:
        if key not in allowed_provider:
            errors.append(f"Unknown generation config key: {path}.{key}")

    provider_type = provider.get("type")
    if provider_type is not None and provider_type not in allowed_types:
        errors.append(f"{path}.type must be one of anthropic, ollama, openai")
    elif provider_type is None:
        warnings.append(f"{path}.type is not set; provider name will be used")

    _validate_optional_string(provider, "model", f"{path}.model", errors)
    _validate_optional_string(provider, "baseUrl", f"{path}.baseUrl", errors)
    _validate_optional_string(provider, "version", f"{path}.version", errors)
    _validate_optional_positive_int(provider, "maxTokens", f"{path}.maxTokens", errors)
    api_key_env = provider.get("apiKeyEnv")
    if api_key_env is not None and (
        not isinstance(api_key_env, str) or _looks_like_secret(api_key_env)
    ):
        errors.append(f"{path}.apiKeyEnv must be an environment variable name")


def _has_configured_model(
    config: Dict[str, Any],
    providers: Dict[str, Any],
    selected_provider: str,
) -> bool:
    if isinstance(config.get("model"), str) and config["model"].strip():
        return True
    provider = providers.get(selected_provider)
    return (
        isinstance(provider, dict)
        and isinstance(provider.get("model"), str)
        and bool(provider["model"].strip())
    )


def _validate_generation_paths(
    config: Dict[str, Any],
    config_path: Path,
    errors: List[str],
    warnings: List[str],
) -> None:
    input_path = config.get("input")
    if isinstance(input_path, str):
        candidate = Path(input_path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if not candidate.exists():
            errors.append(f"input path does not exist: {input_path}")

    output_path = config.get("output")
    if isinstance(output_path, str):
        candidate = Path(output_path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if not candidate.parent.exists():
            warnings.append(
                f"output parent does not exist yet and will be created: {output_path}"
            )

    prompt_path = config.get("prompts")
    if isinstance(prompt_path, str):
        candidate = Path(prompt_path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if not candidate.is_dir():
            errors.append(f"prompt folder does not exist: {prompt_path}")


def _validate_optional_string(
    data: Dict[str, Any],
    key: str,
    path: str,
    errors: List[str],
) -> None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        errors.append(f"{path} must be a string")


def _validate_optional_positive_int(
    data: Dict[str, Any],
    key: str,
    path: str,
    errors: List[str],
) -> None:
    value = data.get(key)
    if value is None:
        return
    if not isinstance(value, int) or value <= 0:
        errors.append(f"{path} must be a positive integer")


def _find_secret_values(value: Any, path: str, errors: List[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            _find_secret_values(item, child_path, errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _find_secret_values(item, f"{path}[{index}]", errors)
    elif isinstance(value, str) and _looks_like_secret(value):
        errors.append(f"{path} appears to contain a secret value")


def _looks_like_secret(value: str) -> bool:
    lowered = value.lower()
    return (
        value.startswith(("sk-", "sk_", "xoxb-", "ghp_"))
        or "api_key=" in lowered
        or "bearer " in lowered
    )


def _generation_settings_dict(settings: GenerationSettings) -> Dict[str, Any]:
    return {
        "provider": settings.provider,
        "provider_type": settings.provider_type,
        "model": settings.model,
        "input_path": settings.input_path,
        "output_path": settings.output_path,
        "base_url": settings.base_url,
        "api_key_env": settings.api_key_env,
        "api_version": settings.api_version,
        "max_tokens": settings.max_tokens,
        "prompt_path": settings.prompt_path,
    }


def _provider_summaries(providers: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    summaries = {}
    for name, value in providers.items():
        provider = value if isinstance(value, dict) else {}
        summaries[str(name)] = {
            "type": provider.get("type"),
            "model": provider.get("model"),
            "base_url": provider.get("baseUrl"),
            "api_key_env": provider.get("apiKeyEnv"),
            "api_version": provider.get("version"),
            "max_tokens": provider.get("maxTokens"),
        }
    return summaries


def resolve_generation_settings(
    config_path: Optional[PathLike] = None,
    input_path: Optional[PathLike] = None,
    output_path: Optional[PathLike] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    ollama_url: Optional[str] = None,
    prompt_dir: Optional[PathLike] = None,
) -> GenerationSettings:
    """Resolve generation settings from config plus CLI-style overrides."""
    config: Dict[str, Any] = load_generation_config(config_path) if config_path else {}
    providers = config.get("providers")
    providers = providers if isinstance(providers, dict) else {}

    provider_name = str(provider or config.get("provider") or "ollama")
    provider_config = providers.get(provider_name)
    if not isinstance(provider_config, dict):
        provider_config = BUILT_IN_PROVIDERS.get(provider_name, {})
    provider_type = str(provider_config.get("type") or provider_name)

    resolved_model = str(
        model
        or provider_config.get("model")
        or config.get("model")
        or DEFAULT_GENERATION_MODEL
    )
    resolved_input = str(input_path or config.get("input") or "")
    resolved_output = str(output_path or config.get("output") or "")
    resolved_prompts = prompt_dir or config.get("prompts")
    resolved_prompt_path = str(resolved_prompts) if resolved_prompts else None
    api_version = None
    max_tokens = None

    if provider_type == "ollama":
        base_url = str(
            ollama_url
            or provider_config.get("baseUrl")
            or config.get("baseUrl")
            or DEFAULT_OLLAMA_URL
        )
        api_key_env = None
    elif provider_type == "openai":
        base_url = str(
            provider_config.get("baseUrl")
            or config.get("baseUrl")
            or DEFAULT_OPENAI_URL
        )
        api_key_env = str(provider_config.get("apiKeyEnv") or "OPENAI_API_KEY")
        api_version = None
        max_tokens = None
    elif provider_type == "openai-chat":
        base_url = str(
            provider_config.get("baseUrl")
            or config.get("baseUrl")
            or DEFAULT_OPENAI_CHAT_URL
        )
        api_key_value = provider_config.get("apiKeyEnv") or config.get("apiKeyEnv")
        api_key_env = str(api_key_value) if api_key_value else None
        api_version = None
        max_tokens = None
    elif provider_type == "anthropic":
        base_url = str(
            provider_config.get("baseUrl")
            or config.get("baseUrl")
            or DEFAULT_ANTHROPIC_URL
        )
        api_key_env = str(provider_config.get("apiKeyEnv") or "ANTHROPIC_API_KEY")
        api_version = str(
            provider_config.get("version")
            or config.get("version")
            or DEFAULT_ANTHROPIC_VERSION
        )
        max_tokens = int(
            provider_config.get("maxTokens")
            or config.get("maxTokens")
            or DEFAULT_ANTHROPIC_MAX_TOKENS
        )
    else:
        raise ValueError(f"Unsupported generation provider type: {provider_type}")

    return GenerationSettings(
        provider=provider_name,
        model=resolved_model,
        input_path=resolved_input,
        output_path=resolved_output,
        provider_type=provider_type,
        base_url=base_url,
        api_key_env=api_key_env,
        api_version=api_version,
        max_tokens=max_tokens,
        prompt_path=resolved_prompt_path,
    )


def create_generation_client(settings: GenerationSettings) -> ModelClient:
    """Create a model client for resolved generation settings."""
    if settings.provider_type == "ollama":
        base_url = settings.base_url or DEFAULT_OLLAMA_URL
        ensure_ollama_model(settings.model, base_url)
        return lambda prompt, model_name: ollama_generate(prompt, model_name, base_url)

    if settings.provider_type == "openai":
        api_key_env = settings.api_key_env or "OPENAI_API_KEY"
        base_url = settings.base_url or DEFAULT_OPENAI_URL
        return lambda prompt, model_name: openai_generate(
            prompt, model_name, api_key_env=api_key_env, base_url=base_url
        )

    if settings.provider_type == "openai-chat":
        base_url = settings.base_url or DEFAULT_OPENAI_CHAT_URL
        return lambda prompt, model_name: openai_chat_generate(
            prompt,
            model_name,
            api_key_env=settings.api_key_env,
            base_url=base_url,
        )

    if settings.provider_type == "anthropic":
        api_key_env = settings.api_key_env or "ANTHROPIC_API_KEY"
        base_url = settings.base_url or DEFAULT_ANTHROPIC_URL
        version = settings.api_version or DEFAULT_ANTHROPIC_VERSION
        max_tokens = settings.max_tokens or DEFAULT_ANTHROPIC_MAX_TOKENS
        return lambda prompt, model_name: anthropic_generate(
            prompt,
            model_name,
            api_key_env=api_key_env,
            base_url=base_url,
            version=version,
            max_tokens=max_tokens,
        )

    raise ValueError(f"Unsupported generation provider type: {settings.provider_type}")


def generate_local_artifacts(
    source_dir: PathLike,
    output_dir: PathLike,
    model: str = DEFAULT_GENERATION_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    client: Optional[ModelClient] = None,
    prompt_dir: Optional[PathLike] = None,
) -> List[GeneratedArtifact]:
    """Generate legacy ODPC fragments and graph YAML from source documents."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if client is None:
        ensure_ollama_model(model, ollama_url)
    model_client = client or (
        lambda prompt, model_name: ollama_generate(prompt, model_name, ollama_url)
    )

    artifacts: List[GeneratedArtifact] = []
    for task in HOLISTIC_GENERATION_TASKS:
        prompt_context = (
            _generated_artifact_context(artifacts)
            if task.name == "odpg_graph" and artifacts
            else None
        )
        expected_graph_nodes = (
            _generated_graph_nodes(artifacts)
            if task.name == "odpg_graph" and artifacts
            else None
        )
        artifacts.extend(
            _run_generation_task(
                task,
                source_dir,
                destination,
                model,
                model_client,
                prompt_context=prompt_context,
                expected_graph_nodes=expected_graph_nodes,
                prompt_dir=prompt_dir,
            )
        )
    return artifacts


def generate_local_artifact(
    artifact_kind: str,
    source: PathLike,
    output_dir: PathLike,
    model: str = DEFAULT_GENERATION_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    client: Optional[ModelClient] = None,
    prompt_dir: Optional[PathLike] = None,
    profile: str = "minimal",
    include_components: Optional[Sequence[str]] = None,
    max_source_chars: Optional[int] = None,
) -> GeneratedArtifact:
    """Generate one selected YAML artifact from source documents."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if client is None:
        ensure_ollama_model(model, ollama_url)
    model_client = client or (
        lambda prompt, model_name: ollama_generate(prompt, model_name, ollama_url)
    )
    task = _generation_task_for(artifact_kind)
    if task.name == "odps_products":
        artifacts = _generate_odps_product_artifacts(
            source,
            destination,
            model,
            model_client,
            prompt_dir=prompt_dir,
            profile=profile,
            include_components=include_components,
            max_source_chars=max_source_chars,
        )
        if not artifacts:
            raise RuntimeError(f"No artifacts generated for kind: {artifact_kind}")
        return artifacts[0]
    artifacts = _run_generation_task(
        task,
        source,
        destination,
        model,
        model_client,
        prompt_dir=prompt_dir,
    )
    if not artifacts:
        raise RuntimeError(f"No artifacts generated for kind: {artifact_kind}")
    return artifacts[0]


def generate_local_artifacts_for_kind(
    artifact_kind: str,
    source: PathLike,
    output_dir: PathLike,
    model: str = DEFAULT_GENERATION_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    client: Optional[ModelClient] = None,
    prompt_dir: Optional[PathLike] = None,
    profile: str = "minimal",
    include_components: Optional[Sequence[str]] = None,
    max_source_chars: Optional[int] = None,
) -> List[GeneratedArtifact]:
    """Generate selected YAML artifacts by processing each source document."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if client is None:
        ensure_ollama_model(model, ollama_url)
    model_client = client or (
        lambda prompt, model_name: ollama_generate(prompt, model_name, ollama_url)
    )
    task = _generation_task_for(artifact_kind)
    if task.name == "odps_products":
        return _generate_odps_product_artifacts(
            source,
            destination,
            model,
            model_client,
            prompt_dir=prompt_dir,
            profile=profile,
            include_components=include_components,
            max_source_chars=max_source_chars,
        )
    artifacts: List[GeneratedArtifact] = []
    for source_path in _source_document_paths(source):
        artifacts.extend(
            _run_generation_task(
                task,
                source_path,
                destination,
                model,
                model_client,
                prompt_dir=prompt_dir,
            )
        )
    if not artifacts:
        raise RuntimeError(f"No artifacts generated for kind: {artifact_kind}")
    return artifacts


def _generate_odps_product_artifacts(
    source: PathLike,
    destination: Path,
    model: str,
    model_client: ModelClient,
    prompt_dir: Optional[PathLike] = None,
    profile: str = "minimal",
    include_components: Optional[Sequence[str]] = None,
    max_source_chars: Optional[int] = None,
) -> List[GeneratedArtifact]:
    if profile not in ODPS_GENERATION_PROFILES:
        raise ValueError(
            "Unknown ODPS generation profile: "
            f"{profile}. Expected one of: {', '.join(ODPS_GENERATION_PROFILES)}"
        )
    requested_components = _resolve_odps_components(profile, include_components)
    artifacts = [
        _generate_one_odps_product(
            source_path,
            destination,
            model,
            model_client,
            prompt_dir=prompt_dir,
            requested_components=requested_components,
            max_source_chars=max_source_chars,
        )
        for source_path in _source_document_paths(source)
    ]
    if not artifacts:
        raise RuntimeError("No artifacts generated for kind: odps-product")
    return artifacts


def _resolve_odps_components(
    profile: str,
    include_components: Optional[Sequence[str]],
) -> List[str]:
    components: List[str] = []
    if profile == "complete-draft":
        components.extend(ODPS_COMPLETE_DRAFT_COMPONENTS)
    for component in include_components or []:
        normalized = _normalize_odps_component(component)
        if normalized not in components:
            components.append(normalized)
    return components


def _normalize_odps_component(component: str) -> str:
    key = component.strip()
    normalized = ODPS_PRODUCT_COMPONENT_ALIASES.get(key)
    if not normalized:
        compact = re.sub(r"[^A-Za-z]", "", key)
        normalized = ODPS_PRODUCT_COMPONENT_ALIASES.get(compact)
    if normalized:
        return normalized
    raise ValueError(
        f"Unknown ODPS product component: {component}. Expected one of: "
        + ", ".join(ODPS_PRODUCT_COMPONENTS)
    )


def _generate_one_odps_product(
    source: Path,
    destination: Path,
    model: str,
    model_client: ModelClient,
    prompt_dir: Optional[PathLike],
    requested_components: Sequence[str],
    max_source_chars: Optional[int],
) -> GeneratedArtifact:
    task = _generation_task_for("odps-product")
    source_documents = load_source_documents(source)
    facts_yaml = _generate_odps_product_facts(
        source_documents,
        model,
        model_client,
        prompt_dir=prompt_dir,
        max_source_chars=max_source_chars,
    )
    facts = _load_mapping_or_empty(facts_yaml)
    evidence_gaps = _string_list(facts.get("evidenceGaps"))

    minimal_prompt = _render_odps_prompt(
        "odps_product_minimal_yaml.md",
        prompt_dir=prompt_dir,
        source_documents=source_documents,
        product_facts=facts_yaml,
    )
    final_prompt_name = "odps_product_minimal_yaml.md"
    final_yaml = _normalize_generated_output(
        task,
        _extract_yaml_document(
            task,
            _strip_markdown_fence(model_client(minimal_prompt, model)).strip(),
        ),
    )

    review_notes: List[str] = []
    drafted_components: List[str] = []
    if requested_components:
        component_prompt = _render_odps_prompt(
            "odps_product_component_draft.md",
            prompt_dir=prompt_dir,
            source_documents=source_documents,
            product_facts=facts_yaml,
            minimal_odps=final_yaml,
            requested_components="\n".join(
                f"- {name}" for name in requested_components
            ),
        )
        component_yaml = _extract_yaml_mapping(model_client(component_prompt, model))
        component_document = _load_mapping_or_empty(component_yaml)
        review_notes.extend(_string_list(component_document.get("reviewNotes")))
        evidence_gaps.extend(_string_list(component_document.get("evidenceGaps")))
        drafted_components.extend(
            _string_list(component_document.get("draftedComponents"))
            or list(requested_components)
        )
        assemble_prompt = _render_odps_prompt(
            "odps_product_assemble_yaml.md",
            prompt_dir=prompt_dir,
            source_documents=source_documents,
            product_facts=facts_yaml,
            minimal_odps=final_yaml,
            component_draft=component_yaml,
        )
        final_prompt_name = "odps_product_assemble_yaml.md"
        final_yaml = _normalize_generated_output(
            task,
            _extract_yaml_document(
                task,
                _strip_markdown_fence(model_client(assemble_prompt, model)).strip(),
            ),
        )

    errors = _artifact_errors(task, final_yaml)
    if errors:
        repair_prompt = _render_odps_prompt(
            "odps_product_repair_yaml.md",
            prompt_dir=prompt_dir,
            generated_odps=final_yaml,
            validation_errors="\n".join(f"- {error}" for error in errors),
        )
        repaired_yaml = _normalize_generated_output(
            task,
            _extract_yaml_document(
                task,
                _strip_markdown_fence(model_client(repair_prompt, model)).strip(),
            ),
        )
        repaired_errors = _artifact_errors(task, repaired_yaml)
        if not repaired_errors:
            final_prompt_name = "odps_product_repair_yaml.md"
            final_yaml = repaired_yaml
            errors = []

    return _write_odps_product_artifact(
        task,
        final_yaml,
        destination,
        valid_yaml=not errors,
        errors=errors,
        prompt_name=final_prompt_name,
        review_notes=_dedupe_strings(review_notes),
        drafted_components=_dedupe_components(drafted_components),
        evidence_gaps=_dedupe_strings(evidence_gaps),
    )


def _generate_odps_product_facts(
    source_documents: str,
    model: str,
    model_client: ModelClient,
    prompt_dir: Optional[PathLike],
    max_source_chars: Optional[int],
) -> str:
    if max_source_chars is not None and max_source_chars <= 0:
        raise ValueError("max_source_chars must be a positive integer.")
    if not max_source_chars or len(source_documents) <= max_source_chars:
        facts_prompt = _render_odps_prompt(
            "odps_product_facts.md",
            prompt_dir=prompt_dir,
            source_documents=source_documents,
        )
        return _extract_yaml_mapping(model_client(facts_prompt, model))

    chunk_facts = []
    chunks = _chunk_text(source_documents, max_source_chars)
    for index, chunk in enumerate(chunks, start=1):
        chunk_context = (
            f"--- Source chunk {index} of {len(chunks)} ---\n" f"{chunk.strip()}"
        )
        facts_prompt = _render_odps_prompt(
            "odps_product_facts.md",
            prompt_dir=prompt_dir,
            source_documents=chunk_context,
        )
        chunk_facts.append(_extract_yaml_mapping(model_client(facts_prompt, model)))

    merge_prompt = _render_odps_prompt(
        "odps_product_merge_facts.md",
        prompt_dir=prompt_dir,
        source_documents=_chunk_summary_context(chunks),
        fact_chunks="\n\n".join(
            f"--- Fact chunk {index} ---\n{facts.strip()}"
            for index, facts in enumerate(chunk_facts, start=1)
        ),
    )
    return _extract_yaml_mapping(model_client(merge_prompt, model))


def _chunk_text(text: str, max_chars: int) -> List[str]:
    paragraphs = text.split("\n\n")
    chunks: List[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else current + "\n\n" + paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            chunks.extend(_hard_wrap_text(paragraph, max_chars))
    if current:
        chunks.append(current)
    return chunks


def _hard_wrap_text(text: str, max_chars: int) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            split_at = text.rfind(" ", start, end)
            if split_at > start:
                end = split_at
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
        while start < len(text) and text[start].isspace():
            start += 1
    return chunks


def _chunk_summary_context(chunks: Sequence[str]) -> str:
    return "\n\n".join(
        f"--- Source chunk {index} of {len(chunks)} ---\n{chunk[:1000].strip()}"
        for index, chunk in enumerate(chunks, start=1)
    )


def _render_odps_prompt(
    prompt_name: str,
    prompt_dir: Optional[PathLike] = None,
    **values: str,
) -> str:
    prompt = load_generation_prompt(prompt_name, prompt_dir=prompt_dir)
    for key, value in values.items():
        prompt = prompt.replace("{" + key + "}", value)
    return prompt


def _extract_yaml_mapping(text: str) -> str:
    stripped = _strip_markdown_fence(text).strip()
    if _loads_as_mapping(stripped):
        return stripped
    lines = stripped.splitlines()
    for index, line in enumerate(lines):
        if line[: len(line) - len(line.lstrip())]:
            continue
        candidate = "\n".join(lines[index:]).strip()
        if _loads_as_mapping(candidate):
            return candidate
    return stripped


def _load_mapping_or_empty(text: str) -> Dict[str, Any]:
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return {}
    return document if isinstance(document, dict) else {}


def _string_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str):
        return [value]
    return []


def _dedupe_strings(values: Sequence[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _dedupe_components(values: Sequence[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        component = _normalize_odps_component(value)
        if component not in result:
            result.append(component)
    return result


def _write_odps_product_artifact(
    task: GenerationTask,
    yaml_output: str,
    destination: Path,
    valid_yaml: bool,
    errors: Sequence[str],
    prompt_name: str,
    review_notes: Sequence[str],
    drafted_components: Sequence[str],
    evidence_gaps: Sequence[str],
) -> GeneratedArtifact:
    try:
        document = yaml.safe_load(yaml_output)
    except yaml.YAMLError:
        document = None
    product = document.get("product") if isinstance(document, dict) else None
    product_id = product.get("productID") if isinstance(product, dict) else None
    if product_id is None and isinstance(product, dict):
        details = product.get("details")
        if isinstance(details, dict):
            english = details.get("en")
            if isinstance(english, dict):
                product_id = english.get("productID")
    product_id = str(product_id or "product")
    output_path = destination / _fragment_file_name("odps_product", product_id)
    if isinstance(document, dict):
        output_path.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    else:
        output_path.write_text(yaml_output, encoding="utf-8")
    return GeneratedArtifact(
        name=f"odpsProduct:{product_id}",
        prompt_name=prompt_name or task.prompt_name,
        output_path=output_path,
        valid_yaml=valid_yaml,
        errors=list(errors),
        review_notes=list(review_notes),
        drafted_components=list(drafted_components),
        evidence_gaps=list(evidence_gaps),
    )


def _generation_task_for(artifact_kind: str) -> GenerationTask:
    task_name = GENERATION_TASK_ALIASES.get(artifact_kind)
    for task in GENERATION_TASKS:
        if artifact_kind == task.name or task_name == task.name:
            return task
    raise KeyError(f"Unknown generation artifact kind: {artifact_kind}")


def _run_generation_task(
    task: GenerationTask,
    source: PathLike,
    destination: Path,
    model: str,
    model_client: ModelClient,
    prompt_context: Optional[str] = None,
    expected_graph_nodes: Optional[Sequence[dict]] = None,
    prompt_dir: Optional[PathLike] = None,
) -> List[GeneratedArtifact]:
    prompt = (
        _render_generation_prompt_context(
            task.prompt_name, prompt_context, prompt_dir=prompt_dir
        )
        if prompt_context is not None
        else render_generation_prompt(task.prompt_name, source, prompt_dir=prompt_dir)
    )
    raw_output = model_client(prompt, model)
    yaml_output = (
        _normalize_generated_output(
            task,
            _extract_yaml_document(task, _strip_markdown_fence(raw_output).strip()),
            expected_graph_nodes=expected_graph_nodes,
        )
        + "\n"
    )
    expected_graph_node_ids = (
        [str(node["id"]) for node in expected_graph_nodes]
        if expected_graph_nodes
        else None
    )
    errors = _artifact_errors(task, yaml_output, expected_graph_node_ids)
    if errors:
        output_path = destination / task.output_name
        output_path.write_text(yaml_output, encoding="utf-8")
        return [
            GeneratedArtifact(
                name=task.name,
                prompt_name=task.prompt_name,
                output_path=output_path,
                valid_yaml=False,
                errors=errors,
            )
        ]

    return _write_generated_artifacts(task, yaml_output, destination)


def _write_generated_artifacts(
    task: GenerationTask,
    yaml_output: str,
    destination: Path,
) -> List[GeneratedArtifact]:
    if task.expected_root == "graph":
        output_path = destination / task.output_name
        output_path.write_text(yaml_output, encoding="utf-8")
        return [
            GeneratedArtifact(
                name=task.name,
                prompt_name=task.prompt_name,
                output_path=output_path,
                valid_yaml=True,
            )
        ]
    if task.name == "odps_products":
        document = yaml.safe_load(yaml_output)
        if not isinstance(document, dict):
            return []
        product = document.get("product")
        product_id = product.get("productID") if isinstance(product, dict) else None
        product_id = str(product_id or "product")
        output_path = destination / _fragment_file_name("odps_product", product_id)
        output_path.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return [
            GeneratedArtifact(
                name=f"odpsProduct:{product_id}",
                prompt_name=task.prompt_name,
                output_path=output_path,
                valid_yaml=True,
            )
        ]

    document = yaml.safe_load(yaml_output)
    if not isinstance(document, dict):
        return []
    items = document.get(task.expected_root)
    if (
        not isinstance(items, list)
        or not task.fragment_root
        or not task.filename_prefix
    ):
        return []

    artifacts = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or f"{task.filename_prefix}-{index + 1}")
        output_path = destination / _fragment_file_name(task.filename_prefix, item_id)
        output_path.write_text(
            yaml.safe_dump(
                {task.fragment_root: item},
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        artifacts.append(
            GeneratedArtifact(
                name=f"{task.fragment_root}:{item_id}",
                prompt_name=task.prompt_name,
                output_path=output_path,
                valid_yaml=True,
            )
        )
    return artifacts


def _fragment_file_name(prefix: str, item_id: str) -> str:
    return f"{prefix}_{_slugify_identifier(item_id)}.yaml"


def _render_generation_prompt_context(
    prompt_name: str,
    context: str,
    prompt_dir: Optional[PathLike] = None,
) -> str:
    return load_generation_prompt(prompt_name, prompt_dir=prompt_dir).replace(
        "{source_documents}", context
    )


def _generated_artifact_context(artifacts: Sequence[GeneratedArtifact]) -> str:
    sections = []
    for artifact in artifacts:
        sections.append(
            "\n".join(
                [
                    f"--- Source file: {artifact.output_path.name} ---",
                    artifact.output_path.read_text(encoding="utf-8").strip(),
                ]
            )
        )
    return "\n\n".join(sections)


def _generated_graph_nodes(artifacts: Sequence[GeneratedArtifact]) -> List[dict]:
    root_types = {
        "productReference": "DataProduct",
        "useCase": "UseCase",
        "businessObjective": "BusinessObjective",
        "signal": "Signal",
    }
    nodes = []
    for artifact in artifacts:
        try:
            document = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(document, dict):
            continue
        for root_key, value in document.items():
            if not isinstance(value, dict):
                continue
            node_type = root_types.get(root_key)
            if node_type is None:
                continue
            if isinstance(value.get("id"), str):
                nodes.append(
                    {
                        "id": value["id"],
                        "type": node_type,
                        "$ref": artifact.output_path.name,
                    }
                )
    return nodes


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return stripped


def _extract_yaml_document(task: GenerationTask, text: str) -> str:
    """Extract a YAML document when a model prepends prose or reasoning."""
    if _loads_as_mapping(text):
        return text

    if task.name == "odps_products":
        roots = ["schema", "product"]
    else:
        roots = ["graph"] if task.expected_root == "graph" else [task.expected_root]
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if line[: len(line) - len(stripped)]:
            continue
        if any(stripped.startswith(f"{root}:") for root in roots):
            candidate = "\n".join(lines[index:]).strip()
            if _loads_as_mapping(candidate):
                return candidate
    return text


def _loads_as_mapping(text: str) -> bool:
    try:
        return isinstance(yaml.safe_load(text), dict)
    except yaml.YAMLError:
        return False


def _normalize_generated_output(
    task: GenerationTask,
    text: str,
    expected_graph_nodes: Optional[Sequence[dict]] = None,
) -> str:
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return text
    if not isinstance(document, dict):
        return text

    if task.name == "odps_products":
        _normalize_odps_product_document(document)
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True).strip()
    if task.name == "odpc_signals":
        _normalize_signal_fragments(document)
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True).strip()
    if task.name == "odpc_objectives":
        _normalize_objective_fragments(document)
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True).strip()
    if task.name == "odpg_graph" and expected_graph_nodes:
        _normalize_graph_nodes(document, expected_graph_nodes)
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True).strip()
    return text


def _normalize_odps_product_document(document: dict) -> None:
    product = document.get("product")
    if not isinstance(product, dict):
        return
    _normalize_odps_v41_details(product)
    _normalize_odps_sla(product.get("SLA"))
    _normalize_odps_data_quality(product.get("dataQuality"))
    _normalize_odps_pricing_plans(product.get("pricingPlans"))
    _normalize_odps_data_access(product)
    _normalize_odps_license(product.get("license"))


def _normalize_odps_v41_details(product: Dict[str, Any]) -> None:
    details = product.get("details")
    if isinstance(details, dict) and details:
        return
    flat_detail_keys = (
        "name",
        "productID",
        "visibility",
        "status",
        "type",
        "valueProposition",
        "description",
        "categories",
        "tags",
        "brand",
        "keywords",
        "themes",
        "geography",
        "language",
        "homepage",
        "logoURL",
        "created",
        "updated",
        "productSeries",
        "standards",
        "useCases",
    )
    detail_block = {
        key: product.pop(key)
        for key in flat_detail_keys
        if key in product and product.get(key) is not None
    }
    if detail_block:
        product_type = detail_block.get("type")
        normalized_type = _normalize_odps_product_type(product_type)
        if normalized_type:
            detail_block["type"] = normalized_type
        product["details"] = {"en": detail_block}


def _normalize_odps_product_type(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped in ODPS_PRODUCT_TYPES:
        return stripped
    compact = re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-")
    return ODPS_PRODUCT_TYPE_ALIASES.get(compact)


def _normalize_odps_sla(sla: object) -> None:
    if not isinstance(sla, dict):
        return
    profiles = _component_profiles(sla)
    definitions: Dict[str, Dict[str, Any]] = {}
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        dimensions = [
            dimension
            for dimension in (
                _normalize_odps_dimension(
                    dimension,
                    allowed_dimensions=ODPS_SLA_DIMENSIONS,
                    dimension_aliases=ODPS_SLA_DIMENSION_ALIASES,
                    allowed_units=ODPS_SLA_UNITS,
                    keep_description=False,
                    stringify_objective=True,
                )
                for dimension in profile.get("dimensions", [])
                if isinstance(dimension, dict)
            )
            if dimension
        ]
        definition: Dict[str, Any] = {
            "name": {"en": _component_definition_title(name, "SLA")}
        }
        if dimensions:
            definition["dimensions"] = dimensions
        support = {}
        for source_key, target_key in (
            ("supportPhone", "phoneNumber"),
            ("support_phone", "phoneNumber"),
            ("supportEmail", "email"),
            ("support_email", "email"),
            ("serviceHours", "emailServiceHours"),
            ("service_hours", "emailServiceHours"),
            ("documentationURL", "documentationURL"),
            ("documentation_url", "documentationURL"),
        ):
            value = profile.get(source_key)
            if isinstance(value, str) and value.strip():
                support[target_key] = value.strip()
        if support:
            definition["support"] = support
        if len(definition) > 1:
            definitions[_component_profile_key(name, definitions)] = definition
    sla.clear()
    if definitions:
        sla["declarative"] = definitions


def _normalize_odps_license(license_data: object) -> None:
    if not isinstance(license_data, dict):
        return
    scope = license_data.get("scope")
    if isinstance(scope, dict):
        _truncate_odps_strings(scope, {"definition": 512, "restrictions": 255})
    termination = license_data.get("termination")
    if isinstance(termination, dict):
        _truncate_odps_strings(
            termination,
            {
                "terminationConditions": 512,
                "continuityConditions": 512,
            },
        )
    governance = license_data.get("governance")
    if isinstance(governance, dict):
        _truncate_odps_strings(
            governance,
            {
                "ownership": 512,
                "audit": 512,
                "warranties": 512,
                "damages": 512,
                "confidentiality": 512,
                "applicableLaws": 512,
                "forceMajeure": 512,
            },
        )


def _truncate_odps_strings(mapping: Dict[str, Any], limits: Dict[str, int]) -> None:
    for key, limit in limits.items():
        value = mapping.get(key)
        if isinstance(value, str) and len(value) > limit:
            mapping[key] = _truncate_odps_text(value, limit)


def _truncate_odps_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3].rstrip() + "..."


def _normalize_odps_data_quality(data_quality: object) -> None:
    if not isinstance(data_quality, dict):
        return
    profiles = _component_profiles(data_quality)
    definitions: Dict[str, Dict[str, Any]] = {}
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        dimensions = [
            dimension
            for dimension in (
                _normalize_odps_dimension(
                    dimension,
                    allowed_dimensions=ODPS_DATA_QUALITY_DIMENSIONS,
                    dimension_aliases=ODPS_DATA_QUALITY_DIMENSION_ALIASES,
                    allowed_units=ODPS_DATA_QUALITY_UNITS,
                    keep_description=True,
                    stringify_objective=False,
                )
                for dimension in profile.get("dimensions", [])
                if isinstance(dimension, dict)
            )
            if dimension
        ]
        definition: Dict[str, Any] = {
            "name": {"en": _component_definition_title(name, "Data Quality")}
        }
        if dimensions:
            definition["dimensions"] = dimensions
        quality_checks = profile.get("qualityChecks") or profile.get("quality_checks")
        if isinstance(quality_checks, dict):
            definition["spec"] = quality_checks
        if len(definition) > 1:
            definitions[_component_profile_key(name, definitions)] = definition
    data_quality.clear()
    if definitions:
        data_quality["declarative"] = definitions


def _component_definition_title(name: str, suffix: str) -> str:
    if name == "default":
        return f"Default {suffix}"
    words = re.sub(r"[^A-Za-z0-9]+", " ", str(name)).strip()
    return f"{words.title()} {suffix}" if words else suffix


def _component_profile_key(name: str, existing: Dict[str, Any]) -> str:
    key = re.sub(r"[^A-Za-z0-9]+", "-", str(name).strip().lower()).strip("-")
    key = key or "default"
    if key.startswith("default"):
        key = "default"
    if "premium" in key:
        key = "premium"
    candidate = key
    suffix = 2
    while candidate in existing:
        candidate = f"{key}-{suffix}"
        suffix += 1
    return candidate


def _component_profiles(component: Dict[str, Any]) -> Dict[str, Any]:
    profiles = component.get("profiles")
    if isinstance(profiles, dict):
        return profiles
    dimensions = component.get("dimensions")
    if isinstance(dimensions, list):
        return {"default": {"dimensions": dimensions}}
    declarative = component.get("declarative")
    if isinstance(declarative, dict):
        return declarative
    if isinstance(declarative, list):
        return {"default": {"dimensions": declarative}}
    return {}


def _normalize_odps_dimension(
    dimension: Dict[str, Any],
    *,
    allowed_dimensions: set,
    dimension_aliases: Dict[str, str],
    allowed_units: set,
    keep_description: bool,
    stringify_objective: bool,
) -> Dict[str, Any]:
    raw_name = dimension.get("name") or dimension.get("dimension")
    name = _normalize_odps_dimension_name(
        raw_name,
        allowed_dimensions=allowed_dimensions,
        dimension_aliases=dimension_aliases,
    )
    if not name:
        return {}
    normalized: Dict[str, Any] = {"dimension": name}
    if "objective" in dimension:
        objective = dimension["objective"]
        if _is_hour_unit(dimension.get("unit")) and "minutes" in allowed_units:
            objective = _hours_to_minutes(objective)
        normalized["objective"] = str(objective) if stringify_objective else objective
    unit = _normalize_odps_unit(dimension.get("unit"), allowed_units)
    if not unit and _is_hour_unit(dimension.get("unit")) and "minutes" in allowed_units:
        unit = "minutes"
    if unit:
        normalized["unit"] = unit
    display_title = dimension.get("displayTitle") or dimension.get("display_title")
    if display_title is not None:
        normalized["displayTitle"] = display_title
    description = dimension.get("description")
    if keep_description and isinstance(description, str) and description.strip():
        normalized["description"] = description.strip()
    return normalized


def _normalize_odps_dimension_name(
    value: object,
    *,
    allowed_dimensions: set,
    dimension_aliases: Dict[str, str],
) -> Optional[str]:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped in allowed_dimensions:
        return stripped
    compact = re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-")
    return dimension_aliases.get(compact) or dimension_aliases.get(
        compact.replace("-", "")
    )


def _normalize_odps_unit(value: object, allowed_units: set) -> Optional[str]:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped if stripped in allowed_units else None


def _is_hour_unit(value: object) -> bool:
    return isinstance(value, str) and value.strip().casefold() in {"hour", "hours"}


def _hours_to_minutes(value: object) -> object:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    minutes = number * 60
    return int(minutes) if minutes.is_integer() else minutes


def _normalize_odps_pricing_plans(pricing_plans: object) -> None:
    if not isinstance(pricing_plans, dict):
        return
    plans = pricing_plans.pop("plans", None)
    if isinstance(plans, list):
        declarative = pricing_plans.setdefault("declarative", {})
        if isinstance(declarative, dict):
            existing = declarative.get("en")
            normalized_plans = [
                _normalize_odps_pricing_plan(plan)
                for plan in plans
                if isinstance(plan, dict)
            ]
            if isinstance(existing, list):
                declarative["en"] = existing + normalized_plans
            else:
                declarative["en"] = normalized_plans
    declarative = pricing_plans.get("declarative")
    if isinstance(declarative, dict):
        for language, plans in list(declarative.items()):
            if isinstance(plans, list):
                declarative[language] = [
                    _normalize_odps_pricing_plan(plan)
                    for plan in plans
                    if isinstance(plan, dict)
                ]
    executable = pricing_plans.get("executable")
    if isinstance(executable, list):
        pricing_plans["executable"] = [
            _normalize_odps_pricing_plan(plan)
            for plan in executable
            if isinstance(plan, dict)
        ]


def _normalize_odps_pricing_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    if "name" in plan:
        normalized["name"] = plan["name"]
    currency = plan.get("priceCurrency") or plan.get("currency")
    if currency is not None:
        normalized["priceCurrency"] = currency
    if "price" in plan:
        normalized["price"] = str(plan["price"])
    billing_duration = _normalize_pricing_billing_duration(
        plan.get("billingDuration") or plan.get("billingCycle")
    )
    if billing_duration:
        normalized["billingDuration"] = billing_duration
    unit = _normalize_pricing_unit(plan.get("unit"))
    if unit:
        normalized["unit"] = unit

    notes = _pricing_plan_notes(plan)
    if notes:
        normalized["notes"] = notes
    for key in ("paymentGateway", "dataQuality", "SLA", "access"):
        reference = _normalize_pricing_component_reference(plan.get(key))
        if reference:
            normalized[key] = reference
    for key in (
        "minPrice",
        "maxPrice",
        "validFrom",
        "validTo",
        "qualityProfileReference",
        "slaProfileReference",
        "accessProfileReference",
    ):
        if key in plan:
            normalized[key] = plan[key]
    return normalized


def _normalize_pricing_component_reference(value: object) -> Optional[Dict[str, str]]:
    if not isinstance(value, dict):
        return None
    ref = value.get("$ref")
    if not isinstance(ref, str) or not ref.strip():
        return None
    normalized_ref = ref.strip()
    terminal = normalized_ref.rstrip("/").rsplit("/", 1)[-1]
    if not terminal or terminal.isdigit():
        return None
    return {"$ref": normalized_ref}


def _normalize_pricing_billing_duration(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("_", "-")
    allowed = {"instant", "day", "week", "month", "year"}
    return normalized if normalized in allowed else None


def _normalize_pricing_unit(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    aliases = {
        "one-time-payment": "One-time-payment",
        "pay-per-use": "Pay-per-use",
        "request": "On-request",
        "on-request": "On-request",
        "onrequest": "On-request",
        "recurring": "Recurring",
        "revenue-sharing": "Revenue-sharing",
        "data-volume": "Data-volume",
        "pay-what-you-want": "Pay-what-you-want",
        "freemium": "Freemium",
        "open-data": "Open-data",
        "value-based": "Value-based",
        "trial": "Trial",
    }
    return aliases.get(normalized)


def _pricing_plan_notes(plan: Dict[str, Any]) -> str:
    notes = []
    for key in ("notes", "description", "additionalPricingDetails"):
        value = plan.get(key)
        if isinstance(value, str) and value.strip():
            notes.append(value.strip())
    conditions = plan.get("conditions")
    if isinstance(conditions, list):
        for condition in conditions:
            if isinstance(condition, dict):
                text_parts = [
                    str(condition.get(key)).strip()
                    for key in ("condition", "description")
                    if condition.get(key)
                ]
                if text_parts:
                    notes.append("; ".join(text_parts))
            elif isinstance(condition, str) and condition.strip():
                notes.append(condition.strip())
    return " ".join(_dedupe_strings(notes))


def _normalize_odps_data_access(product: Dict[str, Any]) -> None:
    data_access = product.get("dataAccess")
    if isinstance(data_access, dict):
        items = {}
        for key, value in list(data_access.items()):
            if key == "$ref":
                continue
            if isinstance(value, dict):
                normalized = _normalize_odps_data_access_item(value)
                items[_data_access_component_key(key, normalized, items)] = normalized
        if items:
            product["dataAccess"] = items
    elif isinstance(data_access, list):
        items = {}
        for item in data_access:
            if not isinstance(item, dict):
                continue
            normalized = _normalize_odps_data_access_item(item)
            items[_data_access_component_key("", normalized, items)] = normalized
        if items:
            product["dataAccess"] = items


def _data_access_component_key(
    key: str, item: Dict[str, Any], existing: Dict[str, Any]
) -> str:
    raw = str(item.get("outputPortType") or key or item.get("name") or "API")
    if raw.lower() == "api":
        candidate = "API"
    else:
        candidate = re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-") or "API"
    suffix = 2
    base = candidate
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _normalize_odps_data_access_item(item: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(item)
    output_port_type = normalized.pop("outputPorttype", None)
    if output_port_type is not None and "outputPortType" not in normalized:
        normalized["outputPortType"] = output_port_type
    return normalized


def _normalize_objective_fragments(document: dict) -> None:
    for objective in document.get("businessObjectives", []):
        if not isinstance(objective, dict):
            continue
        objective.pop("linkedUseCases", None)
        objective.pop("dataProducts", None)


def _normalize_graph_nodes(
    document: dict, expected_graph_nodes: Sequence[dict]
) -> None:
    graph = document.get("graph")
    if not isinstance(graph, dict):
        return
    nodes = graph.setdefault("nodes", [])
    if not isinstance(nodes, list):
        return
    expected_by_id = {expected["id"]: expected for expected in expected_graph_nodes}
    existing = {
        node.get("id")
        for node in nodes
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        expected = expected_by_id.get(node_id)
        if expected:
            node["type"] = expected["type"]
            node["$ref"] = expected["$ref"]
    for expected in expected_graph_nodes:
        if expected["id"] not in existing:
            nodes.append(dict(expected))
            existing.add(expected["id"])


def _normalize_signal_fragments(document: dict) -> None:
    for signal in document.get("signals", []):
        if not isinstance(signal, dict):
            continue
        name = signal.get("name")
        english_name = name.get("en") if isinstance(name, dict) else None
        if isinstance(english_name, str):
            signal["id"] = _slugify_identifier(english_name)

        for signal_field in ("strength", "confidence"):
            if signal_field in signal:
                signal[signal_field] = _normalize_signal_enum(signal.get(signal_field))

        impact = signal.get("impact")
        if isinstance(impact, dict):
            for impact_field in ("valuePotential", "urgency"):
                if impact_field in impact:
                    impact[impact_field] = _normalize_signal_enum(
                        impact.get(impact_field)
                    )


def _normalize_signal_enum(value: object) -> object:
    if isinstance(value, str) and value.lower() == "moderate":
        return "medium"
    return value


def _artifact_errors(
    task: GenerationTask,
    text: str,
    expected_graph_node_ids: Optional[Sequence[str]] = None,
) -> List[str]:
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [str(exc)]
    if not isinstance(document, dict):
        return ["Generated YAML must be a mapping at the document root."]
    if task.expected_root not in document:
        return [
            "Generated YAML must contain expected root key "
            f"`{task.expected_root}` for {task.name}."
        ]
    if task.name == "odps_products":
        from open_data_products.agent import validate_document

        try:
            result = validate_document(document)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            return [str(exc)]
        if not result.valid:
            return _filter_odps_generation_validation_errors(result.errors)
        return []
    if task.expected_root != "graph" and not isinstance(
        document.get(task.expected_root), list
    ):
        return [f"`{task.expected_root}` must be a list."]
    if task.expected_root == "graph" and document.get("kind") != "Graph":
        return ["ODPG graph output must include `kind: Graph`."]
    if task.expected_root == "graph":
        from open_data_products.odpg import validate_graph

        graph_result = validate_graph(document)
        if not graph_result.valid:
            return graph_result.errors
        coverage_errors = _graph_coverage_errors(document, expected_graph_node_ids)
        if coverage_errors:
            return coverage_errors
    if task.expected_root != "graph":
        from open_data_products.odpc import validate_catalog

        catalog_result = validate_catalog(
            {
                "schema": "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml",
                "version": "1.0",
                "kind": "Catalog",
                "catalog": {
                    "metadata": {
                        "id": "CAT-GENERATED-CHECK",
                        "name": {"en": "Generated Check"},
                        "description": {"en": "Generated fragment validation."},
                    },
                    task.expected_root: document[task.expected_root],
                },
            }
        )
        if not catalog_result.valid:
            return catalog_result.errors
        quality_errors = _fragment_quality_errors(task, document)
        if quality_errors:
            return quality_errors
    return []


def _filter_odps_generation_validation_errors(errors: Sequence[str]) -> List[str]:
    return list(errors)


def _graph_coverage_errors(
    document: dict,
    expected_graph_node_ids: Optional[Sequence[str]],
) -> List[str]:
    if not expected_graph_node_ids:
        return []
    graph = document.get("graph")
    if not isinstance(graph, dict):
        return []
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return []
    actual_ids = {
        node.get("id")
        for node in nodes
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    missing = sorted(set(expected_graph_node_ids) - actual_ids)
    if not missing:
        return []
    return ["ODPG graph is missing generated fragment node ids: " + ", ".join(missing)]


def _fragment_quality_errors(task: GenerationTask, document: dict) -> List[str]:
    if task.name != "odpc_signals":
        return []

    errors = []
    for index, signal in enumerate(document.get("signals", [])):
        if not isinstance(signal, dict):
            continue
        signal_id = str(signal.get("id") or "")
        name = signal.get("name")
        english_name = name.get("en") if isinstance(name, dict) else None
        if not isinstance(english_name, str):
            continue
        expected_id = _slugify_identifier(english_name)
        if signal_id != expected_id:
            errors.append(
                f"signals.{index}.id `{signal_id}` does not match signal name "
                f"slug `{expected_id}`."
            )
    return errors


def _slugify_identifier(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-+", "-", slug)


__all__ = [
    "DEFAULT_ANTHROPIC_MAX_TOKENS",
    "DEFAULT_ANTHROPIC_URL",
    "DEFAULT_ANTHROPIC_VERSION",
    "DEFAULT_GENERATION_CONFIG",
    "DEFAULT_GENERATION_MODEL",
    "DEFAULT_OPENAI_GENERATE_TIMEOUT",
    "DEFAULT_OPENAI_CHAT_URL",
    "DEFAULT_OPENAI_USER_AGENT",
    "DEFAULT_OPENAI_URL",
    "DEFAULT_OLLAMA_GENERATE_TIMEOUT",
    "DEFAULT_OLLAMA_URL",
    "GENERATION_TASKS",
    "GENERATION_TASK_ALIASES",
    "GeneratedArtifact",
    "GenerationSettings",
    "GenerationTask",
    "anthropic_generate",
    "copy_config_template",
    "copy_generation_prompts",
    "create_generation_client",
    "ensure_ollama_model",
    "generate_local_artifact",
    "generate_local_artifacts_for_kind",
    "generate_local_artifacts",
    "get_config",
    "get_config_path",
    "list_generation_prompts",
    "list_ollama_models",
    "load_generation_config",
    "load_generation_prompt",
    "load_source_documents",
    "ollama_generate",
    "openai_chat_generate",
    "openai_generate",
    "print_config",
    "render_generation_prompt",
    "resolve_generation_settings",
    "validate_config",
]
