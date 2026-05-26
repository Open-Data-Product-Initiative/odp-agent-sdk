"""LLM generation prompt and provider helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import ssl
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
from urllib import error, request

import certifi
import yaml

_PROMPT_DIR = Path(__file__).resolve().parent / "data" / "prompts"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OPENAI_URL = "https://api.openai.com/v1"
DEFAULT_ANTHROPIC_URL = "https://api.anthropic.com/v1"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MAX_TOKENS = 4096
DEFAULT_GENERATION_MODEL = "qwen2.5"
DEFAULT_OLLAMA_GENERATE_TIMEOUT = 300
DEFAULT_OPENAI_GENERATE_TIMEOUT = 300
DEFAULT_OPENAI_USER_AGENT = "open-data-products-python/0.2"
DEFAULT_GENERATION_CONFIG = (
    Path(__file__).resolve().parent / "generation.config.yaml"
)

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


@dataclass(frozen=True)
class GeneratedArtifact:
    """Generated YAML artifact metadata."""

    name: str
    prompt_name: str
    output_path: Path
    valid_yaml: bool
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-ready artifact summary."""
        return {
            "name": self.name,
            "prompt": self.prompt_name,
            "output": str(self.output_path),
            "valid_yaml": self.valid_yaml,
            "errors": list(self.errors),
        }


GENERATION_TASKS: Sequence[GenerationTask] = (
    GenerationTask(
        name="odps_data_products",
        prompt_name="odps_data_product_fragment.md",
        output_name="odps_data_products.yaml",
        expected_root="productReferences",
        fragment_root="productReference",
        filename_prefix="product_reference",
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

GENERATION_TASK_ALIASES = {
    "product": "odps_data_products",
    "data-product": "odps_data_products",
    "data-products": "odps_data_products",
    "odps": "odps_data_products",
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


def list_generation_prompts() -> List[str]:
    """List bundled local generation prompt filenames."""
    return sorted(path.name for path in _PROMPT_DIR.glob("*.md"))


def load_generation_prompt(name: str) -> str:
    """Load a bundled local generation prompt by filename."""
    if "/" in name or "\\" in name:
        raise KeyError(f"Unknown generation prompt: {name}")

    prompt_path = _PROMPT_DIR / name
    if not prompt_path.is_file():
        raise KeyError(f"Unknown generation prompt: {name}")
    return prompt_path.read_text(encoding="utf-8")


PathLike = Union[str, Path]


def load_source_documents(source_dir: PathLike) -> str:
    """Load Markdown and text source documents as one prompt context."""
    root = Path(source_dir)
    if root.is_file():
        paths = [root]
    elif root.is_dir():
        paths = sorted(
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in {".md", ".txt"}
        )
    else:
        raise FileNotFoundError(f"Source document path not found: {root}")

    if not paths:
        raise ValueError(f"No Markdown or text source documents found at {root}")

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


def render_generation_prompt(prompt_name: str, source_dir: PathLike) -> str:
    """Render a generation prompt with source documents inlined."""
    return load_generation_prompt(prompt_name).replace(
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
        raise RuntimeError(
            message
        ) from exc
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


def resolve_generation_settings(
    config_path: Optional[PathLike] = None,
    input_path: Optional[PathLike] = None,
    output_path: Optional[PathLike] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    ollama_url: Optional[str] = None,
) -> GenerationSettings:
    """Resolve generation settings from config plus CLI-style overrides."""
    config: Dict[str, Any] = load_generation_config(config_path) if config_path else {}
    providers = config.get("providers")
    providers = providers if isinstance(providers, dict) else {}

    provider_name = str(provider or config.get("provider") or "ollama")
    provider_config = providers.get(provider_name)
    provider_config = provider_config if isinstance(provider_config, dict) else {}
    provider_type = str(provider_config.get("type") or provider_name)

    resolved_model = str(
        model
        or provider_config.get("model")
        or config.get("model")
        or DEFAULT_GENERATION_MODEL
    )
    resolved_input = str(input_path or config.get("input") or "")
    resolved_output = str(output_path or config.get("output") or "")
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
) -> List[GeneratedArtifact]:
    """Generate YAML fragments and graph YAML from source documents."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if client is None:
        ensure_ollama_model(model, ollama_url)
    model_client = client or (
        lambda prompt, model_name: ollama_generate(prompt, model_name, ollama_url)
    )

    artifacts: List[GeneratedArtifact] = []
    for task in GENERATION_TASKS:
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
) -> GeneratedArtifact:
    """Generate one selected YAML artifact from source documents."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if client is None:
        ensure_ollama_model(model, ollama_url)
    model_client = client or (
        lambda prompt, model_name: ollama_generate(prompt, model_name, ollama_url)
    )
    artifacts = _run_generation_task(
        _generation_task_for(artifact_kind),
        source,
        destination,
        model,
        model_client,
    )
    if not artifacts:
        raise RuntimeError(f"No artifacts generated for kind: {artifact_kind}")
    return artifacts[0]


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
) -> List[GeneratedArtifact]:
    prompt = (
        _render_generation_prompt_context(task.prompt_name, prompt_context)
        if prompt_context is not None
        else render_generation_prompt(task.prompt_name, source)
    )
    raw_output = model_client(prompt, model)
    yaml_output = _normalize_generated_output(
        task,
        _extract_yaml_document(task, _strip_markdown_fence(raw_output).strip()),
        expected_graph_nodes=expected_graph_nodes,
    ) + "\n"
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

    document = yaml.safe_load(yaml_output)
    if not isinstance(document, dict):
        return []
    items = document.get(task.expected_root)
    if not isinstance(items, list) or not task.fragment_root or not task.filename_prefix:
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


def _render_generation_prompt_context(prompt_name: str, context: str) -> str:
    return load_generation_prompt(prompt_name).replace("{source_documents}", context)


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


def _normalize_objective_fragments(document: dict) -> None:
    for objective in document.get("businessObjectives", []):
        if not isinstance(objective, dict):
            continue
        objective.pop("linkedUseCases", None)
        objective.pop("dataProducts", None)


def _normalize_graph_nodes(document: dict, expected_graph_nodes: Sequence[dict]) -> None:
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
                signal[signal_field] = _normalize_signal_enum(
                    signal.get(signal_field)
                )

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
    "create_generation_client",
    "ensure_ollama_model",
    "generate_local_artifact",
    "generate_local_artifacts",
    "list_generation_prompts",
    "list_ollama_models",
    "load_generation_config",
    "load_generation_prompt",
    "load_source_documents",
    "ollama_generate",
    "openai_generate",
    "render_generation_prompt",
    "resolve_generation_settings",
]
