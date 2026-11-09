"""Safe RDF source loading shared by interoperability namespaces."""

from __future__ import annotations

import json
from http.client import HTTPMessage
from pathlib import Path
import re
import ssl
from typing import IO, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

import certifi
from rdflib import Graph

_HTTP_TIMEOUT_SECONDS = 10.0
_MAX_HTTP_DOCUMENT_BYTES = 5 * 1024 * 1024
_MAX_HTTP_REDIRECTS = 3
_RDF_SUFFIXES = {".rdf", ".xml", ".ttl", ".jsonld", ".json-ld", ".nt", ".n3"}
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


def load_graphs(source: str, *, label: str) -> List[Tuple[Graph, str]]:
    """Load safe local or bounded remote RDF without crawling references."""
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        text, resolved = _load_remote(source, label=label)
        return [(_parse_rdf(text, _rdf_format(resolved), label=label), resolved)]
    if parsed.scheme == "file":
        if parsed.netloc not in {"", "localhost"}:
            raise ValueError(label + " file URI must reference the local host")
        return _load_local(Path(unquote(parsed.path)), label=label)
    if parsed.scheme:
        raise ValueError("Unsupported " + label + " URI scheme")
    return _load_local(Path(source), label=label)


def safe_access_url(value: str) -> bool:
    """Accept only credential-free HTTP(S) access references."""
    try:
        safe_http_uri(value)
    except ValueError:
        return False
    return True


def safe_http_uri(source: str) -> str:
    """Return a credential-free HTTP(S) URI without a fragment."""
    parsed = urlparse(source)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or "@" in parsed.netloc
        or "#" in source
        or _credential_query(parsed.query)
    ):
        raise ValueError("Credential-bearing or malformed RDF URL is not supported")
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, "")
    )


def _load_local(path: Path, *, label: str) -> List[Tuple[Graph, str]]:
    """Load supported local RDF files without following linked resources."""
    paths = (
        sorted(item for item in path.iterdir() if item.suffix.lower() in _RDF_SUFFIXES)
        if path.is_dir()
        else [path]
    )
    if not paths:
        raise ValueError("No supported RDF files were found")
    loaded: List[Tuple[Graph, str]] = []
    for item in paths:
        if not item.is_file():
            continue
        text = item.read_text(encoding="utf-8")
        loaded.append(
            (
                _parse_rdf(text, _rdf_format(str(item)), label=label),
                item.resolve().as_uri(),
            )
        )
    return loaded


def _load_remote(source: str, *, label: str) -> Tuple[str, str]:
    """Retrieve one bounded public RDF document over HTTP(S)."""
    safe_source = safe_http_uri(source)
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        opener = build_opener(
            HTTPSHandler(context=context), _BoundedRedirectHandler(_MAX_HTTP_REDIRECTS)
        )
        with opener.open(safe_source, timeout=_HTTP_TIMEOUT_SECONDS) as response:
            payload = response.read(_MAX_HTTP_DOCUMENT_BYTES + 1)
            resolved = safe_http_uri(str(response.geturl()))
    except (HTTPError, URLError, OSError, ValueError):
        raise ValueError("Could not load remote " + label) from None
    if len(payload) > _MAX_HTTP_DOCUMENT_BYTES:
        raise ValueError("Remote " + label + " response exceeds the maximum size")
    try:
        return payload.decode("utf-8"), resolved
    except UnicodeDecodeError:
        raise ValueError("Remote " + label + " is not UTF-8") from None


class _BoundedRedirectHandler(HTTPRedirectHandler):
    """Follow only a small number of credential-free HTTP redirects."""

    def __init__(self, maximum: int) -> None:
        super().__init__()
        self._maximum = maximum
        self._count = 0

    def redirect_request(  # type: ignore[override]
        self,
        request: Request,
        file_pointer: IO[bytes],
        code: int,
        message: str,
        headers: HTTPMessage,
        new_url: str,
    ) -> Request:
        """Reject excessive or credential-bearing redirect destinations."""
        self._count += 1
        if self._count > self._maximum:
            raise ValueError("RDF source redirect limit exceeded")
        return super().redirect_request(
            request, file_pointer, code, message, headers, safe_http_uri(new_url)
        )


def _parse_rdf(text: str, rdf_format: Optional[str], *, label: str) -> Graph:
    """Parse RDF while refusing network-loaded JSON-LD contexts."""
    if rdf_format == "json-ld":
        _reject_remote_jsonld_context(text)
    graph = Graph()
    try:
        graph.parse(data=text, format=rdf_format)
    except Exception as exc:
        raise ValueError(label + " source is not valid supported RDF") from exc
    return graph


def _reject_remote_jsonld_context(text: str) -> None:
    """Reject JSON-LD documents that would dereference external contexts."""
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("RDF JSON-LD is not valid JSON") from exc
    if any(
        isinstance(value, str) and urlparse(value).scheme in {"http", "https"}
        for value in _contexts(document)
    ):
        raise ValueError("Remote JSON-LD contexts are not supported")


def _contexts(value: object) -> Iterable[object]:
    """Yield JSON-LD context declarations recursively."""
    if isinstance(value, dict):
        if "@context" in value:
            context = value["@context"]
            yield from context if isinstance(context, list) else [context]
        for item in value.values():
            yield from _contexts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _contexts(item)


def _rdf_format(source: str) -> Optional[str]:
    """Infer an RDFLib parser format from a source suffix."""
    suffix = Path(urlparse(source).path).suffix.lower()
    return {
        ".ttl": "turtle",
        ".rdf": "xml",
        ".xml": "xml",
        ".jsonld": "json-ld",
        ".json-ld": "json-ld",
        ".nt": "nt",
        ".n3": "n3",
    }.get(suffix)


def _credential_query(query: str) -> bool:
    """Identify credential-like query parameter keys."""
    for parameter in re.split(r"[&;]", query):
        key = re.sub(r"[^a-z0-9]", "", unquote(parameter.split("=", 1)[0]).lower())
        if key in {"apikey", "auth", "key"} or any(
            part in key for part in _CREDENTIAL_QUERY_FRAGMENTS
        ):
            return True
    return False
