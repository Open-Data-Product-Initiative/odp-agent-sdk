"""Load and summarize external Data Contract documents."""

from __future__ import annotations

import json
from pathlib import Path
import re
import ssl
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, unquote, urlparse, urlunparse
from urllib.request import urlopen

import certifi
import yaml

from .._io import load_mapping
from .models import (
    ContractDocument,
    ContractSchemaField,
    ContractSchemaModel,
    ContractSchemaSummary,
    ContractSummary,
    Finding,
)

_HTTP_TIMEOUT_SECONDS = 10.0
_MAX_HTTP_DOCUMENT_BYTES = 1024 * 1024
_CREDENTIAL_QUERY_FRAGMENTS = (
    "authorization",
    "credential",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
    "jwt",
)


def load_contract(path_or_url: str) -> ContractDocument:
    """Load a local or remote Data Contract YAML or JSON document."""
    parsed = urlparse(path_or_url)
    source_location = _safe_source_location(path_or_url)
    if "://" not in path_or_url:
        path = Path(path_or_url)
        document = load_mapping(path, root_name="Data Contract")
        resolved_uri = path.resolve().as_uri()
    elif parsed.scheme == "file":
        path = _file_uri_path(parsed)
        document = load_mapping(path, root_name="Data Contract")
        resolved_uri = path.resolve().as_uri()
    elif parsed.scheme in {"http", "https"}:
        document, resolved_uri = _load_remote_contract(path_or_url)
    else:
        raise ValueError(
            "Unsupported Data Contract URI scheme: " f"{parsed.scheme or '(missing)'}"
        )
    return ContractDocument(
        path=source_location,
        document=document,
        contract_format=_infer_contract_format(path_or_url),
        source=source_location,
        resolved_uri=resolved_uri,
    )


def _file_uri_path(parsed: ParseResult) -> Path:
    """Return a local path from a parsed file URI."""
    netloc = parsed.netloc
    if netloc not in {"", "localhost"}:
        raise ValueError("Data Contract file URI must reference the local host")
    decoded_path = unquote(parsed.path)
    if not decoded_path:
        raise ValueError("Data Contract file URI must include a path")
    return Path(decoded_path)


def _load_remote_contract(source: str) -> Tuple[Dict[str, object], str]:
    """Load a bounded Data Contract mapping over HTTP(S)."""
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(
            source, timeout=_HTTP_TIMEOUT_SECONDS, context=context
        ) as response:
            content = response.read(_MAX_HTTP_DOCUMENT_BYTES + 1)
            resolved_uri = _safe_http_uri(str(response.geturl()))
    except (HTTPError, URLError, OSError, ValueError):
        raise ValueError("Could not load remote Data Contract") from None
    if len(content) > _MAX_HTTP_DOCUMENT_BYTES:
        raise ValueError("Remote Data Contract response exceeds the maximum size")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Remote Data Contract response is not UTF-8") from None
    return _load_mapping_text(text, _infer_contract_format(source)), resolved_uri


def _safe_source_location(source: str) -> str:
    """Return a source location that cannot contain URL user credentials."""
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        return _safe_http_uri(source)
    if parsed.scheme == "file" and ("?" in source or "#" in source):
        raise ValueError(
            "Data Contract URL query parameters and fragments are not supported"
        )
    return source


def _safe_http_uri(source: str) -> str:
    """Return an HTTP(S) URI without user credentials or a fragment."""
    parsed = urlparse(source)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Could not load remote Data Contract")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("Could not load remote Data Contract") from None
    if "@" in parsed.netloc:
        raise ValueError("Credential-bearing Data Contract URL is not supported")
    if _has_credential_query(parsed.query):
        raise ValueError("Credential-bearing Data Contract URL is not supported")
    if "?" in source or "#" in source:
        raise ValueError(
            "Data Contract URL query parameters and fragments are not supported"
        )
    netloc = parsed.hostname if port is None else f"{parsed.hostname}:{port}"
    return urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, "")
    )


def _has_credential_query(query: str) -> bool:
    """Return whether decoded query keys indicate credential material."""
    for parameter in re.split(r"[&;]", query):
        key = unquote(parameter.split("=", 1)[0])
        normalized = re.sub(r"[^a-z0-9]", "", key.lower())
        if normalized in {"apikey", "auth", "key"} or any(
            fragment in normalized for fragment in _CREDENTIAL_QUERY_FRAGMENTS
        ):
            return True
    return False


def _load_mapping_text(
    text: str,
    contract_format: Optional[str],
) -> Dict[str, object]:
    """Load a YAML or JSON mapping from text."""
    try:
        parsed: object
        if contract_format == "json":
            parsed = json.loads(text)
        else:
            parsed = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError):
        raise ValueError("Remote Data Contract is not valid YAML or JSON") from None
    if not isinstance(parsed, dict):
        raise ValueError("Data Contract must contain an object at the document root")
    return {str(key): value for key, value in parsed.items()}


def summarize_contract(path_or_url: str) -> ContractSummary:
    """Return a compact Data Contract summary."""
    contract = load_contract(path_or_url)
    return summarize_contract_document(
        contract.document,
        path=contract.path,
        contract_format=contract.contract_format,
    )


def summarize_contract_document(
    document: Dict[str, object],
    *,
    path: str = "(inline)",
    contract_format: Optional[str] = None,
) -> ContractSummary:
    """Return a compact summary for an already-loaded Data Contract."""
    models = _mapping_values(document.get("models"))
    return ContractSummary(
        path=path,
        contract_format=contract_format,
        contract_id=_optional_str(
            document.get("id")
            or document.get("contractId")
            or _mapping(document.get("info")).get("id")
        ),
        name=_optional_str(
            document.get("name")
            or _mapping(document.get("info")).get("title")
            or _mapping(document.get("info")).get("name")
        ),
        version=_optional_str(
            document.get("version") or _mapping(document.get("info")).get("version")
        ),
        model_count=len(models),
        field_count=sum(_field_count(model) for model in models),
        server_count=len(_mapping_values(document.get("servers"))),
    )


def explain_contract(path_or_url: str) -> str:
    """Render a compact Data Contract summary."""
    summary = summarize_contract(path_or_url)
    return (
        f"File: {summary.path}\n"
        f"Format: {summary.contract_format or '(unknown)'}\n"
        f"Contract id: {summary.contract_id or '(missing)'}\n"
        f"Name: {summary.name or '(missing)'}\n"
        f"Version: {summary.version or '(missing)'}\n"
        f"Models: {summary.model_count}\n"
        f"Fields: {summary.field_count}\n"
        f"Servers: {summary.server_count}\n"
    )


def extract_contract_schema(path_or_url: str) -> ContractSchemaSummary:
    """Extract a normalized schema summary from a local Data Contract."""
    contract = load_contract(path_or_url)
    return extract_contract_schema_from_document(
        contract.document,
        path=contract.path,
        contract_format=contract.contract_format,
    )


def extract_contract_schema_from_document(
    document: Dict[str, object],
    *,
    path: str = "(inline)",
    contract_format: Optional[str] = None,
) -> ContractSchemaSummary:
    """Extract a normalized schema summary from an already-loaded contract."""
    models = _schema_models(document.get("models"))
    findings = []
    if not models:
        findings.append(
            Finding(
                code="CONTRACT_SCHEMA_EMPTY",
                message="No schema models were found in the Data Contract.",
                severity="warning",
                source="open-data-products",
            )
        )
    return ContractSchemaSummary(
        path=path,
        contract_format=contract_format,
        models=models,
        findings=findings,
    )


def _mapping(value: object) -> Dict[str, object]:
    return value if isinstance(value, dict) else {}


def _mapping_values(value: object) -> List[Dict[str, object]]:
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _field_count(model: Dict[str, object]) -> int:
    fields = model.get("fields") or model.get("columns")
    return len(list(_field_items(fields)))


def _field_items(value: object) -> Iterable[object]:
    if isinstance(value, dict):
        return value.values()
    if isinstance(value, list):
        return value
    return []


def _schema_models(value: object) -> List[ContractSchemaModel]:
    if isinstance(value, dict):
        return [
            _schema_model(str(name), model)
            for name, model in value.items()
            if isinstance(model, dict)
        ]
    if isinstance(value, list):
        return [
            _schema_model(_model_name(model, index), model)
            for index, model in enumerate(value)
            if isinstance(model, dict)
        ]
    return []


def _schema_model(name: str, model: Dict[str, object]) -> ContractSchemaModel:
    return ContractSchemaModel(
        name=_optional_str(model.get("name")) or name,
        description=_optional_str(model.get("description")),
        fields=_schema_fields(model.get("fields") or model.get("columns")),
    )


def _schema_fields(value: object) -> List[ContractSchemaField]:
    if isinstance(value, dict):
        return [
            _schema_field(str(name), field)
            for name, field in value.items()
            if isinstance(field, dict)
        ]
    if isinstance(value, list):
        return [
            _schema_field(_field_name(field, index), field)
            for index, field in enumerate(value)
            if isinstance(field, dict)
        ]
    return []


def _schema_field(name: str, field: Dict[str, object]) -> ContractSchemaField:
    return ContractSchemaField(
        name=_optional_str(field.get("name")) or name,
        type=_optional_str(field.get("type") or field.get("dataType")),
        required=_field_required(field),
        description=_optional_str(field.get("description")),
    )


def _field_required(field: Dict[str, object]) -> bool:
    required = field.get("required")
    if isinstance(required, bool):
        return required
    nullable = field.get("nullable")
    if isinstance(nullable, bool):
        return not nullable
    return False


def _model_name(model: Dict[str, object], index: int) -> str:
    return _optional_str(model.get("name")) or f"model_{index + 1}"


def _field_name(field: Dict[str, object], index: int) -> str:
    return _optional_str(field.get("name")) or f"field_{index + 1}"


def _infer_contract_format(path_or_url: str) -> Optional[str]:
    suffix = Path(path_or_url).suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".json":
        return "json"
    return None


def _optional_str(value: object) -> Optional[str]:
    return str(value) if value is not None else None
