"""Versioned connection profiles with lazily resolved credentials."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union
from urllib.parse import urlsplit, urlunsplit
import os
import re
import subprocess

import yaml


class IntegrationError(Exception):
    """A sanitized integration error."""


class ConfigurationError(IntegrationError):
    """An invalid integration configuration."""


class _UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise ConfigurationError("Configuration has a duplicate or invalid key")
        result[key] = loader.construct_object(value_node)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _object(value: object, keys: set, label: str) -> dict:
    if not isinstance(value, dict) or set(value) - set(keys):
        raise ConfigurationError("Invalid or unknown fields in " + label)
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(label + " must be a boolean")
    return value


@dataclass(frozen=True)
class ConnectionProfile:
    """A named connection without a resolved credential."""

    name: str
    platform: str
    base_url: str
    token_env: str
    read_only: bool = True
    timeout_seconds: float = 30
    verify_tls: bool = True
    allow_insecure_http: bool = False
    ca_bundle: Optional[str] = None
    token_source: str = "env"
    keychain_service: Optional[str] = None
    keychain_account: Optional[str] = None

    def token(self) -> str:
        """Resolve the bearer token only when making a request."""
        value: Optional[str]
        if self.token_source == "keychain":
            try:
                result = subprocess.run(
                    [
                        "/usr/bin/security",
                        "find-generic-password",
                        "-s",
                        self.keychain_service or "",
                        "-a",
                        self.keychain_account or "",
                        "-w",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                raise ConfigurationError(
                    "Could not access the configured Keychain credential"
                ) from None
            if result.returncode != 0:
                raise ConfigurationError(
                    "Configured Keychain credential is unavailable"
                )
            value = result.stdout.rstrip("\n")
        elif self.token_source == "env":
            value = os.environ.get(self.token_env)
        else:
            raise ConfigurationError("Unsupported credential source")
        if not value:
            raise ConfigurationError("Configured credential is missing")
        if "\r" in value or "\n" in value:
            raise ConfigurationError("Credential contains invalid characters")
        return value


@dataclass(frozen=True)
class IntegrationConfig:
    """A set of named connection profiles."""

    connections: Dict[str, ConnectionProfile]
    default_connection: Optional[str] = None

    def select(self, name: Optional[str] = None) -> ConnectionProfile:
        """Select an explicitly named or configured default connection."""
        selected = name if name is not None else self.default_connection
        if not selected or selected not in self.connections:
            raise ConfigurationError("Connection is missing or not configured")
        return self.connections[selected]


def load_integration_config(path: Union[str, Path]) -> IntegrationConfig:
    """Read and validate configuration without resolving secrets or contacting hosts."""
    try:
        with Path(path).open(encoding="utf-8") as handle:
            root = yaml.load(handle, Loader=_UniqueLoader)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise ConfigurationError("Cannot read integration configuration") from None
    root = _object(
        root, {"version", "default_connection", "connections"}, "configuration"
    )
    if type(root.get("version")) is not int or root["version"] != 1:
        raise ConfigurationError("Unsupported integration configuration version")
    entries = root.get("connections")
    if not isinstance(entries, dict) or not entries:
        raise ConfigurationError("At least one named connection is required")
    profiles = {}
    for name, raw in entries.items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
            raise ConfigurationError("Invalid connection name")
        raw = _object(
            raw, {"platform", "base_url", "read_only", "auth", "http"}, "connection"
        )
        if raw.get("platform") != "openmetadata":
            raise ConfigurationError("Connection adapter is unavailable")
        auth = _object(raw.get("auth"), {"type", "token"}, "authentication")
        token = _object(
            auth.get("token"),
            {"source", "name", "service", "account"},
            "credential reference",
        )
        source = token.get("source")
        if auth.get("type") != "bearer_token" or source not in ("env", "keychain"):
            raise ConfigurationError(
                "Only environment or Keychain bearer token references are supported"
            )
        env: Optional[str] = ""
        service = account = None
        if source == "env":
            env = token.get("name")
            if (
                set(token) != {"source", "name"}
                or not isinstance(env, str)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env)
            ):
                raise ConfigurationError("Invalid credential environment variable name")
        else:
            service, account = token.get("service"), token.get("account")
            if set(token) != {"source", "service", "account"} or any(
                not isinstance(v, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}", v)
                for v in (service, account)
            ):
                raise ConfigurationError("Invalid Keychain service or account")
        http = _object(
            raw.get("http", {}),
            {"timeout_seconds", "verify_tls", "allow_insecure_http", "ca_bundle"},
            "HTTP settings",
        )
        timeout = http.get("timeout_seconds", 30)
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 0 < timeout <= 300
        ):
            raise ConfigurationError(
                "HTTP timeout must be greater than 0 and at most 300 seconds"
            )
        verify = _boolean(http.get("verify_tls", True), "verify_tls")
        insecure = _boolean(
            http.get("allow_insecure_http", False), "allow_insecure_http"
        )
        read_only = _boolean(raw.get("read_only", True), "read_only")
        ca = http.get("ca_bundle")
        if ca is not None and (not isinstance(ca, str) or not ca or not verify):
            raise ConfigurationError("A CA bundle requires TLS verification")
        url = raw.get("base_url")
        if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 for c in url):
            raise ConfigurationError("Invalid base URL")
        try:
            parts = urlsplit(url)
            _ = parts.port
        except ValueError:
            raise ConfigurationError("Invalid base URL") from None
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or (parts.scheme == "http" and not insecure)
        ):
            raise ConfigurationError("Invalid or disallowed base URL")
        normalized = urlunsplit(
            (parts.scheme, parts.netloc, parts.path.rstrip("/"), "", "")
        )
        profiles[name] = ConnectionProfile(
            name,
            "openmetadata",
            normalized,
            env or "",
            read_only,
            float(timeout),
            verify,
            insecure,
            ca,
            source,
            service,
            account,
        )
    default = root.get("default_connection")
    if default is not None and (
        not isinstance(default, str) or default not in profiles
    ):
        raise ConfigurationError("Default connection is not configured")
    return IntegrationConfig(profiles, default)
