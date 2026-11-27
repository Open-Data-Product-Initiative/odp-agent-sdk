"""Guided local configuration and secret-free status reporting."""

import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit

import yaml

from ._guided_handoff import _load_env_file, _resolve_discovery_profile
from .generation import BUILT_IN_PROVIDERS, resolve_generation_settings
from .integrations.adapter import open_integration
from .integrations.config import _UniqueLoader
from .integrations.jira import JiraCloudAdapter, load_jira_connection


def _read(path):
    if path.is_symlink():
        raise ValueError("Configuration paths cannot be symbolic links")
    if not path.exists():
        return b""
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("Configuration must be a regular file at most 1 MiB")
    return path.read_bytes()


def require_llm_configuration(
    config_path=None, env_file=None, *, provider=None, check_credentials=False
):
    """Require user-owned LLM settings before CLI generation."""
    path = Path(config_path or "generation.config.yaml").expanduser()
    if not path.is_file():
        raise ValueError(
            "LLM configuration is required. Run 'open-data-products config setup' "
            "in this project directory or pass an existing generation config with --config."
        )
    environment = Path(env_file or ".env").expanduser()
    if env_file or environment.exists() or environment.is_symlink():
        _load_env_file(str(environment))
    if check_credentials:
        settings = resolve_generation_settings(config_path=str(path), provider=provider)
        key = settings.api_key_env
        if key and not os.environ.get(key):
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise ValueError(
                    "LLM credential "
                    + key
                    + " is missing. Run 'open-data-products config credentials set --name "
                    + key
                    + "'."
                )
            raise ValueError(
                "LLM credential reference is invalid. Run 'open-data-products config setup'."
            )
    return str(path)


def _mapping(data, label):
    if not data:
        return {}
    try:
        result = yaml.load(data.decode("utf-8"), Loader=_UniqueLoader)
    except (UnicodeError, yaml.YAMLError):
        raise ValueError("Cannot parse " + label) from None
    if not isinstance(result, dict):
        raise ValueError(label + " must be a YAML mapping")
    return result


def _prompt(label, default=None):
    value = input(label + (" [" + default + "]" if default else "") + ": ").strip()
    value = value or default
    if not value or "\n" in value or "\r" in value:
        raise ValueError(label + " is required")
    return value


def _secret(label):
    value = getpass.getpass(label + " (leave blank to keep existing): ")
    if "\n" in value or "\r" in value:
        raise ValueError("Credentials cannot contain newlines")
    return value


def _provider_url(value):
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError:
        raise ValueError("Invalid provider URL") from None
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or any(c.isspace() or ord(c) < 32 for c in value)
        or (
            parts.scheme == "http"
            and parts.hostname not in ("localhost", "127.0.0.1", "::1")
        )
    ):
        raise ValueError(
            "Provider URL must use HTTPS, except for localhost; credentials and query strings are not allowed"
        )
    return value


def _origin(value):
    """Return an endpoint origin without credential-bearing URL components."""
    try:
        parts = urlsplit(value or "")
        hostname = parts.hostname
        port = parts.port
        if parts.scheme not in ("http", "https") or not hostname:
            return None
        host = "[" + hostname + "]" if ":" in hostname else hostname
        return urlunsplit(
            (parts.scheme, host + ((":" + str(port)) if port else ""), "", "", "")
        )
    except (TypeError, ValueError):
        return None


def _test_failure(exc):
    """Report a safe status code without exposing remote error bodies."""
    status = getattr(exc, "status", None) or getattr(exc, "code", None)
    if not isinstance(status, int):
        match = re.search(r"\bHTTP\s+([1-5][0-9]{2})\b", str(exc))
        status = int(match.group(1)) if match else None
    if isinstance(status, int) and 100 <= status <= 599:
        return (
            "failed (HTTP " + str(status) + "); inspect configuration and credentials"
        )
    return "failed; inspect configuration and credentials"


def _record_test_failure(result, scope, status, *, credential=None, llm=False):
    if (
        "HTTP 401" in status
        and credential
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", credential)
    ):
        step = {
            "scope": scope,
            "reason": "authentication failed (HTTP 401)",
            "command": "open-data-products config credentials set --name " + credential,
        }
    else:
        reason = (
            "access denied; verify permissions"
            if "HTTP 403" in status
            else (
                "rate limit or quota; check provider usage"
                if "HTTP 429" in status
                else "connection test failed; verify endpoint and network"
            )
        )
        step = {
            "scope": scope,
            "reason": reason,
            "command": (
                "open-data-products config test"
                if llm
                else "open-data-products config status --test"
            ),
        }
    if step not in result["next_steps"]:
        result["next_steps"].append(step)


def _profile_env(prefix, name, suffix, default_name):
    if name == default_name:
        return prefix + "_" + suffix
    identifier = re.sub(r"[^A-Za-z0-9_]", "_", name).upper()
    return prefix + "_" + identifier + "_" + suffix


def _connection_mode(profile, action):
    if action == "add":
        mode = _prompt("Access mode (read-only or read-write)", "read-write")
    elif action == "edit":
        mode = input("Access mode (read-only/read-write; blank to keep): ").strip()
        if not mode:
            return
    else:
        return
    if mode not in ("read-only", "read-write"):
        raise ValueError("Access mode must be read-only or read-write")
    profile["read_only"] = mode == "read-only"


def _env_update(original, values):
    text = original.decode("utf-8") if original else ""
    lines = text.splitlines(keepends=True)
    keys = set(values)
    kept = []
    for line in lines:
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if not match or match.group(1) not in keys:
            kept.append(line)
    out = "".join(kept)
    if out and not out.endswith("\n"):
        out += "\n"
    for name, value in values.items():
        out += name + "=" + shlex.quote(value) + "\n"
    return out.encode("utf-8")


def _ignored_env():
    try:
        return (
            subprocess.run(
                ["git", "check-ignore", "-q", "--", ".env"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            == 0
        )
    except OSError:
        return False


def _write(path, data, previous):
    if hashlib.sha256(_read(path)).digest() != hashlib.sha256(previous).digest():
        raise ValueError(str(path) + " changed since review; no further files written")
    fd, name = tempfile.mkstemp(prefix=".odp-config-", dir=str(path.parent))
    try:
        mode = (
            0o600
            if path.name == ".env"
            else (path.stat().st_mode & 0o777 if path.exists() else 0o644)
        )
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as out:
            out.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _print_setup_overview():
    """Show existing local settings without contacting services or revealing secrets."""
    print("Current settings (local checks only):")
    try:
        status = config_status()
    except Exception:
        print(
            "  Some settings cannot be read. Check generation.config.yaml, connections.yaml and .env."
        )
        return
    generation = status["generation"]
    if generation.get("status") == "configured":
        print(
            "  LLM: "
            + generation["provider"]
            + " / "
            + generation["model"]
            + "; credential "
            + generation["credential"]
        )
    else:
        print("  LLM: " + generation.get("status", "unknown"))
    for platform, label in (("openmetadata", "OpenMetadata"), ("jira_cloud", "Jira")):
        connections = [
            item for item in status["connections"] if item.get("platform") == platform
        ]
        if not connections:
            print("  " + label + ": not configured")
        for item in connections:
            print(
                "  "
                + label
                + ": "
                + str(item.get("name"))
                + "; "
                + item.get("status", "unknown")
                + (
                    "; credential " + item["credential"]
                    if item.get("credential")
                    else ""
                )
            )


def run_setup(*, llm_only=False, connection_action=None, connection_name=None):
    """Review and save selected local configuration interactively."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Configuration setup requires an interactive terminal")
    if llm_only:
        choice = "1"
    elif connection_action == "add":
        print("Connection type: 1) OpenMetadata  2) Jira Cloud")
        selected = _prompt("Selection")
        if selected not in ("1", "2"):
            raise ValueError("Choose 1 or 2")
        choice = "2" if selected == "1" else "3"
    elif connection_action == "edit":
        root = _mapping(_read(Path("connections.yaml")), "connection configuration")
        entries = root.get("connections")
        entry = entries.get(connection_name) if isinstance(entries, dict) else None
        platform = entry.get("platform") if isinstance(entry, dict) else None
        if platform not in ("openmetadata", "jira_cloud"):
            raise ValueError(
                "Connection is missing or its platform is not supported for editing"
            )
        choice = "2" if platform == "openmetadata" else "3"
    else:
        _print_setup_overview()
        print("Configure: 1) LLM provider  2) OpenMetadata  3) Jira  4) All")
        choice = _prompt("Selection")
    if choice not in ("1", "2", "3", "4"):
        raise ValueError("Choose 1, 2, 3 or 4")
    llm, metadata, jira = (
        choice in ("1", "4"),
        choice in ("2", "4"),
        choice in ("3", "4"),
    )
    generation, connections, env = (
        Path("generation.config.yaml"),
        Path("connections.yaml"),
        Path(".env"),
    )
    original = {
        generation: _read(generation) if llm else b"",
        connections: _read(connections) if metadata or jira else b"",
        env: _read(env),
    }
    gen = _mapping(original[generation], "generation configuration") if llm else {}
    conn = (
        _mapping(original[connections], "connection configuration")
        if metadata or jira
        else {}
    )
    if metadata or jira:
        if conn and (
            conn.get("version") != 1 or not isinstance(conn.get("connections"), dict)
        ):
            raise ValueError("Existing connection configuration is invalid")
        conn.setdefault("version", 1)
        conn.setdefault("connections", {})
    values = {}
    changed = []
    metadata_name = None
    jira_name = None
    review = []
    if llm:
        providers = gen.setdefault("providers", {})
        if not isinstance(providers, dict):
            raise ValueError("Existing providers must be a mapping")
        print("Built-in providers: " + ", ".join(sorted(BUILT_IN_PROVIDERS)))
        if providers:
            print("Configured providers: " + ", ".join(sorted(providers)))
        print(
            "Enter an existing provider name, or a new name to add a custom provider."
        )
        provider = _prompt("Provider", str(gen.get("provider") or "ollama"))
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", provider):
            raise ValueError("Invalid provider name")
        existing = providers.get(provider)
        if llm_only and provider in providers:
            raise ValueError("Provider already exists; use config llm use to select it")
        new_custom = existing is None and provider not in BUILT_IN_PROVIDERS
        if existing is not None and not isinstance(existing, dict):
            raise ValueError("Existing provider must be a mapping")
        if existing is not None:
            profile = dict(existing)
        elif provider in BUILT_IN_PROVIDERS:
            profile = dict(BUILT_IN_PROVIDERS[provider])
        else:
            provider_type = _prompt(
                "Provider type (openai, openai-chat, anthropic, ollama, llama-cpp)",
                "openai-chat",
            )
            if provider_type not in (
                "openai",
                "openai-chat",
                "anthropic",
                "ollama",
                "llama-cpp",
            ):
                raise ValueError("Unsupported provider type")
            profile = {"type": provider_type}
            if provider_type != "llama-cpp":
                profile["baseUrl"] = _provider_url(_prompt("Provider base URL"))
            if provider_type in ("openai", "anthropic"):
                default_key = (
                    re.sub(r"[^A-Za-z0-9_]", "_", provider).upper() + "_API_KEY"
                )
                if default_key[0].isdigit():
                    default_key = "PROVIDER_" + default_key
                profile["apiKeyEnv"] = _prompt(
                    "API key environment variable", default_key
                )
            elif provider_type == "openai-chat":
                key = input(
                    "API key environment variable (optional; blank for none): "
                ).strip()
                if key:
                    profile["apiKeyEnv"] = key
            review.append(
                "Custom provider type: "
                + provider_type
                + ("; URL: " + profile["baseUrl"] if "baseUrl" in profile else "")
            )
        model = _prompt(
            "Model",
            None if new_custom else str(profile.get("model") or gen.get("model") or ""),
        )
        profile["model"] = model
        if profile.get("type") == "llama-cpp":
            profile["modelPath"] = _prompt(
                "Local model file path", str(profile.get("modelPath") or "")
            )
        providers[provider] = profile
        if not llm_only:
            gen["provider"] = provider
        review.append("LLM provider: " + provider + "; model: " + model)
        if llm_only:
            review.append(
                "The active provider will not change; use config llm use to select the new provider."
            )
        key = profile.get("apiKeyEnv")
        if key:
            if not isinstance(key, str) or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*", key
            ):
                raise ValueError(
                    "Invalid provider credential environment variable name"
                )
            secret = _secret("API key for " + str(key))
            if secret:
                values[key] = secret
        changed.append(generation)
    if metadata:
        name = (
            connection_name
            if connection_action == "edit"
            else _prompt("OpenMetadata connection name", "openmetadata")
        )
        metadata_name = name
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
            raise ValueError("Invalid connection name")
        existing = conn["connections"].get(name)
        if connection_action == "add" and name in conn["connections"]:
            raise ValueError(
                "Connection already exists; use config connections edit --name NAME"
            )
        if existing is not None and (
            not isinstance(existing, dict) or existing.get("platform") != "openmetadata"
        ):
            raise ValueError("Connection name already belongs to another platform")
        url = _prompt(
            "OpenMetadata base URL", existing.get("base_url") if existing else None
        )
        token_env = _profile_env("OPENMETADATA", name, "TOKEN", "openmetadata")
        profile = (
            dict(existing)
            if existing
            else {
                "platform": "openmetadata",
                "read_only": False,
                "auth": {
                    "type": "bearer_token",
                    "token": {"source": "env", "name": token_env},
                },
            }
        )
        profile["base_url"] = url
        _connection_mode(profile, connection_action)
        if urlsplit(url).scheme == "http" and not profile.get("http", {}).get(
            "allow_insecure_http", False
        ):
            print("Warning: HTTP sends the OpenMetadata token without TLS.")
            if input("Allow HTTP for this connection? [y/N]: ").strip().lower() not in (
                "y",
                "yes",
            ):
                raise ValueError(
                    "Use HTTPS or explicitly allow HTTP for this connection"
                )
            http = dict(profile.get("http") or {})
            http["allow_insecure_http"] = True
            profile["http"] = http
            review.append(
                "OpenMetadata transport: HTTP explicitly allowed; token is not protected by TLS"
            )
        token_config = profile.get("auth", {}).get("token", {})
        source = token_config.get("source")
        token_env = token_config.get("name") if source == "env" else None
        if source not in ("env", "keychain") or (
            source == "env"
            and (
                not isinstance(token_env, str)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token_env)
            )
        ):
            raise ValueError("Invalid OpenMetadata credential reference")
        conn["connections"][name] = profile
        conn.setdefault("default_connection", name)
        review.append(
            "OpenMetadata connection: "
            + name
            + "; URL: "
            + url
            + "; credential: "
            + (token_env or "Keychain (unchanged)")
            + "; mode: "
            + ("read-only" if profile.get("read_only", True) else "read-write")
        )
        if token_env:
            secret = _secret("OpenMetadata token")
            if secret:
                values[token_env] = secret
        changed.append(connections)
    if jira:
        name = (
            connection_name
            if connection_action == "edit"
            else _prompt("Jira connection name", "jira")
        )
        jira_name = name
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
            raise ValueError("Invalid connection name")
        if metadata and name == metadata_name:
            raise ValueError(
                "Jira and OpenMetadata must use different connection names"
            )
        existing = conn["connections"].get(name)
        if connection_action == "add" and name in conn["connections"]:
            raise ValueError(
                "Connection already exists; use config connections edit --name NAME"
            )
        if existing is not None and (
            not isinstance(existing, dict) or existing.get("platform") != "jira_cloud"
        ):
            raise ValueError("Connection name already belongs to another platform")
        url = _prompt(
            "Jira Cloud site URL", existing.get("base_url") if existing else None
        )
        email_env = _profile_env("JIRA", name, "EMAIL", "jira")
        token_env = _profile_env("JIRA", name, "API_TOKEN", "jira")
        profile = (
            dict(existing)
            if existing
            else {
                "platform": "jira_cloud",
                "read_only": False,
                "auth": {
                    "type": "basic_env",
                    "email_env": email_env,
                    "token_env": token_env,
                },
            }
        )
        profile["base_url"] = url
        _connection_mode(profile, connection_action)
        auth = profile.get("auth", {})
        email_env, token_env = auth.get("email_env"), auth.get("token_env")
        if not all(
            isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)
            for value in (email_env, token_env)
        ):
            raise ValueError("Invalid Jira credential references")
        conn["connections"][name] = profile
        conn.setdefault("default_connection", name)
        email = _secret("Jira account email")
        token = _secret("Jira API token")
        if email:
            values[email_env] = email
        if token:
            values[token_env] = token
        if connection_action == "edit":
            project = input("Jira project key (blank to leave unchanged): ").strip()
            issue_type = input(
                "Jira numeric issue type ID (blank to leave unchanged): "
            ).strip()
        else:
            project = _prompt("Jira project key")
            issue_type = _prompt("Jira numeric issue type ID")
        if issue_type and not issue_type.isdigit():
            raise ValueError("Jira issue type ID must be numeric")
        if project:
            values["JIRA_PROJECT"] = project
        if issue_type:
            values["JIRA_ISSUE_TYPE_ID"] = issue_type
        review.append(
            "Jira connection: "
            + name
            + "; URL: "
            + url
            + "; credentials: "
            + email_env
            + ", "
            + token_env
            + "; mode: "
            + ("read-only" if profile.get("read_only", True) else "read-write")
            + "; project: "
            + (project or "unchanged")
            + "; issue type ID: "
            + (issue_type or "unchanged")
        )
        review.append(
            "Jira project and issue type are shared by guided Jira delivery across connections."
        )
        if connections not in changed:
            changed.append(connections)
    if values:
        changed.append(env)
    payload = {
        generation: yaml.safe_dump(gen, sort_keys=False).encode(),
        connections: yaml.safe_dump(conn, sort_keys=False).encode(),
        env: _env_update(original[env], values),
    }
    with tempfile.TemporaryDirectory(prefix="odp-setup-validation-") as directory:
        temp = Path(directory)
        if llm:
            path = temp / "generation.config.yaml"
            path.write_bytes(payload[generation])
            resolve_generation_settings(config_path=str(path), provider=provider)
        if metadata or jira:
            path = temp / "connections.yaml"
            path.write_bytes(payload[connections])
            if metadata:
                _resolve_discovery_profile(str(path), metadata_name)
            if jira:
                load_jira_connection(path, jira_name)
    for line in review:
        print(line)
    print("Files to create or update: " + ", ".join(str(p) for p in changed))
    if values:
        print("Environment variables to update: " + ", ".join(sorted(values)))
    print(
        "Existing selected settings may be replaced; unrelated YAML values are retained. YAML comments and formatting may change."
    )
    if env in changed and not _ignored_env():
        print(
            "Warning: .env is not known to be ignored by Git. Keep it out of commits."
        )
    print(
        "Secrets are not displayed. Existing process environment values take precedence over .env."
    )
    if input("Save these settings? [y/N]: ").strip().lower() not in ("y", "yes"):
        print("No files changed.")
        return 0
    written = []
    try:
        for path in changed:
            _write(path, payload[path], original[path])
            written.append(str(path))
    except (OSError, ValueError):
        print("Saved before error: " + (", ".join(written) or "none"), file=sys.stderr)
        raise
    print("Saved. Run open-data-products config show to inspect local configuration.")
    if llm_only:
        print("Next: open-data-products config llm use --name " + shlex.quote(provider))
    elif llm:
        print(
            "Next: open-data-products config test (sends a short LLM prompt; may incur cost)"
        )
    elif metadata or jira:
        print(
            "Next: open-data-products config status --test (read-only platform checks)"
        )
    return 0


def config_status(*, test=False, llm_test=False):
    """Inspect local settings and optionally test read-only connections."""
    result = {
        "generation": {"status": "not configured"},
        "connections": [],
        "next_steps": [],
        "notes": [
            "Local checks only; connectivity was not tested.",
            "Generation, guided handover and platform CLI commands load .env; other workflows may require exported environment variables.",
            "Endpoint origins are shown without paths, user information or query strings.",
        ],
    }
    if test and not llm_test:
        result["notes"][
            0
        ] = "Read-only OpenMetadata and Jira connection checks requested; LLM connectivity was not tested."
    elif llm_test:
        result["notes"][
            0
        ] = "OpenMetadata and Jira checks are read-only; the LLM test sends a short prompt and may incur cost."
    saved = dict(os.environ)
    try:
        if Path(".env").exists() or Path(".env").is_symlink():
            _read(Path(".env"))
            _load_env_file(".env")
        path = Path("generation.config.yaml")
        if path.exists() or path.is_symlink():
            _read(path)
            try:
                settings = resolve_generation_settings(config_path=str(path))
                key = settings.api_key_env
                result["generation"] = {
                    "status": "configured",
                    "provider": settings.provider,
                    "model": settings.model,
                    "credential": (
                        "present"
                        if key and os.environ.get(key)
                        else "missing" if key else "not required"
                    ),
                }
                if key:
                    result["generation"]["credential_variable"] = key
                    if not os.environ.get(key) and re.fullmatch(
                        r"[A-Za-z_][A-Za-z0-9_]*", key
                    ):
                        result["next_steps"].append(
                            {
                                "scope": "LLM",
                                "reason": "credential missing",
                                "command": "open-data-products config credentials set --name "
                                + key,
                            }
                        )
                origin = _origin(settings.base_url)
                if origin:
                    result["generation"]["endpoint_origin"] = origin
                if llm_test:
                    if key and not os.environ.get(key):
                        result["generation"][
                            "connectivity"
                        ] = "failed; credential missing"
                    else:
                        try:
                            from .generation import create_generation_client

                            response = create_generation_client(settings)(
                                "Reply with OK.", settings.model
                            )
                            if not isinstance(response, str) or not response.strip():
                                raise ValueError("Empty model response")
                            result["generation"]["connectivity"] = "passed"
                        except Exception as exc:
                            result["generation"]["connectivity"] = _test_failure(exc)
                            _record_test_failure(
                                result,
                                "LLM",
                                result["generation"]["connectivity"],
                                credential=key,
                                llm=True,
                            )
            except (ValueError, OSError):
                result["generation"] = {"status": "invalid configuration"}
                result["next_steps"].append(
                    {
                        "scope": "LLM",
                        "reason": "invalid configuration",
                        "command": "open-data-products config setup",
                    }
                )
        else:
            result["next_steps"].append(
                {
                    "scope": "LLM",
                    "reason": "not configured",
                    "command": "open-data-products config setup",
                }
            )
        path = Path("connections.yaml")
        if path.exists() or path.is_symlink():
            root = _mapping(_read(path), "connection configuration")
            entries = root.get("connections")
            if root.get("version") != 1 or not isinstance(entries, dict):
                raise ValueError("Invalid connection configuration")
            for name, entry in entries.items():
                if not isinstance(entry, dict):
                    result["connections"].append(
                        {"name": name, "status": "invalid configuration"}
                    )
                    continue
                platform = entry.get("platform")
                item = {
                    "name": name,
                    "platform": platform,
                    "status": "configured",
                    "default": name == root.get("default_connection"),
                }
                try:
                    if platform == "openmetadata":
                        profile = _resolve_discovery_profile(str(path), name)
                        item["endpoint_origin"] = _origin(profile.base_url)
                        item["mode"] = (
                            "read-only" if profile.read_only else "read-write"
                        )
                        item["credential"] = (
                            "not checked (Keychain)"
                            if profile.token_source == "keychain"
                            else (
                                "present"
                                if os.environ.get(profile.token_env)
                                else "missing"
                            )
                        )
                        if profile.token_source == "env":
                            item["credential_variable"] = profile.token_env
                            if not os.environ.get(profile.token_env):
                                result["next_steps"].append(
                                    {
                                        "scope": name,
                                        "reason": "credential missing",
                                        "command": "open-data-products config credentials set --name "
                                        + profile.token_env,
                                    }
                                )
                        if test:
                            try:
                                with open_integration(profile) as adapter:
                                    adapter.check_connection()
                                item["connectivity"] = "passed"
                            except Exception as exc:
                                item["connectivity"] = _test_failure(exc)
                                _record_test_failure(
                                    result,
                                    name,
                                    item["connectivity"],
                                    credential=(
                                        profile.token_env
                                        if profile.token_source == "env"
                                        else None
                                    ),
                                )
                    elif platform == "jira_cloud":
                        profile = load_jira_connection(path, name)
                        item["endpoint_origin"] = _origin(profile.base_url)
                        item["mode"] = (
                            "read-only" if profile.read_only else "read-write"
                        )
                        item["credential"] = (
                            "present"
                            if os.environ.get(profile.email_env)
                            and os.environ.get(profile.token_env)
                            else "missing"
                        )
                        item["credential_variables"] = [
                            profile.email_env,
                            profile.token_env,
                        ]
                        for variable in (profile.email_env, profile.token_env):
                            if not os.environ.get(variable):
                                result["next_steps"].append(
                                    {
                                        "scope": name,
                                        "reason": "credential missing",
                                        "command": "open-data-products config credentials set --name "
                                        + variable,
                                    }
                                )
                        item["project"] = (
                            "present" if os.environ.get("JIRA_PROJECT") else "missing"
                        )
                        project = os.environ.get("JIRA_PROJECT", "")
                        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", project):
                            item["project_key"] = project
                        issue_type = os.environ.get("JIRA_ISSUE_TYPE_ID", "")
                        item["issue_type"] = (
                            "present" if issue_type.isdigit() else "missing or invalid"
                        )
                        if (
                            issue_type.isascii()
                            and issue_type.isdigit()
                            and len(issue_type) <= 20
                        ):
                            item["issue_type_id"] = issue_type
                        if not item.get("project_key") or not item.get("issue_type_id"):
                            result["next_steps"].append(
                                {
                                    "scope": name,
                                    "reason": "Jira project or issue type missing",
                                    "command": "open-data-products config connections edit --name "
                                    + shlex.quote(name),
                                }
                            )
                        if test:
                            try:
                                JiraCloudAdapter(profile)._request("GET", "myself")
                                item["connectivity"] = "passed"
                            except Exception as exc:
                                item["connectivity"] = _test_failure(exc)
                                _record_test_failure(
                                    result,
                                    name,
                                    item["connectivity"],
                                    credential=profile.token_env,
                                )
                    else:
                        item["status"] = "unsupported platform"
                except Exception:
                    item["status"] = "invalid configuration"
                    result["next_steps"].append(
                        {
                            "scope": str(name),
                            "reason": "invalid connection configuration",
                            "command": "open-data-products config show",
                        }
                    )
                result["connections"].append(item)
        else:
            result["next_steps"].append(
                {
                    "scope": "Connections",
                    "reason": "not configured",
                    "command": "open-data-products config connections add",
                }
            )
    finally:
        os.environ.clear()
        os.environ.update(saved)
    return result


def run_status(*, as_json=False, test=False, llm_test=False):
    """Print local configuration status without exposing credential values."""
    if llm_test and not as_json:
        print("Testing services. The LLM test sends a short prompt and may incur cost.")
    result = config_status(test=test, llm_test=llm_test)
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        generation = result["generation"]
        print("LLM generation:")
        if generation.get("status") == "configured":
            print("  Provider: " + generation["provider"])
            print("  Model: " + generation["model"])
            if generation.get("endpoint_origin"):
                print("  Endpoint origin: " + generation["endpoint_origin"])
            print("  Credential: " + generation["credential"])
            if generation.get("credential_variable"):
                print("  Credential variable: " + generation["credential_variable"])
            if generation.get("connectivity"):
                print("  Model test: " + generation["connectivity"])
        else:
            print("  " + generation["status"])
        print("Connections:")
        for connection in result["connections"]:
            print(
                "  "
                + str(connection.get("name"))
                + " ("
                + str(connection.get("platform", "unknown"))
                + "): "
                + connection["status"]
                + ("; default" if connection.get("default") else "")
            )
            for key, label in (
                ("endpoint_origin", "Endpoint origin"),
                ("mode", "Access mode"),
                ("credential", "Credential"),
                ("credential_variable", "Credential variable"),
                ("project_key", "Jira project"),
                ("issue_type_id", "Jira issue type ID"),
                ("connectivity", "Connection test"),
            ):
                if connection.get(key):
                    print("    " + label + ": " + str(connection[key]))
            if connection.get("credential_variables"):
                print(
                    "    Credential variables: "
                    + ", ".join(connection["credential_variables"])
                )
            if connection.get("platform") == "jira_cloud":
                if not connection.get("project_key"):
                    print("    Jira project: " + connection.get("project", "missing"))
                if not connection.get("issue_type_id"):
                    print(
                        "    Jira issue type ID: "
                        + connection.get("issue_type", "missing")
                    )
        if not result["connections"]:
            print("  none configured")
        if result["next_steps"]:
            print("Next steps:")
            for step in result["next_steps"]:
                print(
                    "  "
                    + step["scope"]
                    + " ("
                    + step["reason"]
                    + "): "
                    + step["command"]
                )
        for note in result["notes"]:
            print(note)
    llm_failed = llm_test and (
        result["generation"].get("status") == "invalid configuration"
        or result["generation"].get("connectivity", "").startswith("failed")
    )
    nothing_tested = (
        llm_test
        and not result["generation"].get("connectivity")
        and not any(item.get("connectivity") for item in result["connections"])
    )
    return (
        1
        if llm_failed
        or nothing_tested
        or (
            test
            and any(
                item.get("status") == "invalid configuration"
                or item.get("connectivity", "").startswith("failed")
                for item in result["connections"]
            )
        )
        else 0
    )


def run_credentials_set(name):
    """Review and store one credential in the local environment file."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Credential entry requires an interactive terminal")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Invalid credential environment variable name")
    path = Path(".env")
    original = _read(path)
    saved = dict(os.environ)
    try:
        if original:
            _load_env_file(str(path))
    finally:
        os.environ.clear()
        os.environ.update(saved)
    value = getpass.getpass("Value for " + name + " (hidden): ")
    if not value or "\r" in value or "\n" in value:
        raise ValueError("Credential must be nonempty and cannot contain newlines")
    updated = _env_update(original, {name: value})
    print("Set " + name + " in .env; the value will not be displayed.")
    if not _ignored_env():
        print(
            "Warning: .env is not known to be ignored by Git. Keep it out of commits."
        )
    if name in os.environ:
        print("The current process environment takes precedence over .env.")
    if input("Save this credential? [y/N]: ").strip().lower() not in ("y", "yes"):
        print("No files changed.")
        return 0
    _write(path, updated, original)
    print("Credential saved to .env.")
    return 0


def run_llm_add():
    """Add an LLM provider without changing the active provider."""
    return run_setup(llm_only=True)


def run_connections_add():
    """Add a named connection using a supported platform type."""
    return run_setup(connection_action="add")


def run_connections_edit(name):
    """Review changes to an existing named connection."""
    return run_setup(connection_action="edit", connection_name=name)


def run_connections_list(*, as_json=False):
    """List named connections without resolving credentials."""
    root = _mapping(_read(Path("connections.yaml")), "connection configuration")
    if not root:
        entries = {}
    elif root.get("version") == 1 and isinstance(root.get("connections"), dict):
        entries = root["connections"]
    else:
        raise ValueError("Invalid connection configuration")
    default = root.get("default_connection")
    items = []
    for name, entry in sorted(entries.items()):
        if not isinstance(entry, dict):
            items.append({"name": name, "status": "invalid configuration"})
            continue
        platform = entry.get("platform")
        mode = entry.get("read_only", True)
        items.append(
            {
                "name": name,
                "platform": platform,
                "supported": platform in ("openmetadata", "jira_cloud"),
                "mode": (
                    ("read-only" if mode else "read-write")
                    if isinstance(mode, bool)
                    else "invalid"
                ),
                "default": name == default,
            }
        )
    if as_json:
        print(json.dumps({"connections": items}, indent=2))
    else:
        if not items:
            print(
                "No connections configured. Run open-data-products config connections add."
            )
        for item in items:
            print(
                item["name"]
                + ": "
                + str(item.get("platform", "invalid"))
                + "; "
                + str(item.get("mode", "invalid"))
                + ("; default" if item.get("default") else "")
                + ("; unsupported platform" if not item.get("supported", False) else "")
            )
    return 0


def run_llm_list(*, as_json=False):
    """List built-in and locally configured provider names."""
    generation = _mapping(
        _read(Path("generation.config.yaml")), "generation configuration"
    )
    configured = generation.get("providers", {})
    if not isinstance(configured, dict):
        raise ValueError("Existing providers must be a mapping")
    active = generation.get("provider") or "ollama"
    items = [
        {
            "name": name,
            "built_in": name in BUILT_IN_PROVIDERS,
            "configured": name in configured,
            "active": name == active,
        }
        for name in sorted(set(BUILT_IN_PROVIDERS) | set(configured) | {active})
    ]
    if as_json:
        print(json.dumps({"providers": items}, indent=2))
    else:
        for item in items:
            labels = [key for key in ("active", "configured", "built_in") if item[key]]
            print(item["name"] + " (" + ", ".join(labels) + ")")
    return 0


def run_llm_use(name):
    """Review and select an existing configured LLM provider."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Selecting an LLM provider requires an interactive terminal")
    path = Path("generation.config.yaml")
    original = _read(path)
    generation = _mapping(original, "generation configuration")
    providers = generation.get("providers", {})
    if (
        not isinstance(providers, dict)
        or name not in providers
        or not isinstance(providers[name], dict)
    ):
        raise ValueError("Provider is not configured; use config llm add first")
    generation["provider"] = name
    payload = yaml.safe_dump(generation, sort_keys=False).encode()
    with tempfile.TemporaryDirectory(prefix="odp-provider-validation-") as directory:
        candidate = Path(directory) / "generation.config.yaml"
        candidate.write_bytes(payload)
        settings = resolve_generation_settings(config_path=str(candidate))
    print("Select provider: " + name + "; model: " + settings.model)
    print("Update generation.config.yaml; YAML comments and formatting may change.")
    if input("Save this selection? [y/N]: ").strip().lower() not in ("y", "yes"):
        print("No files changed.")
        return 0
    _write(path, payload, original)
    print("Active LLM provider: " + name)
    return 0
