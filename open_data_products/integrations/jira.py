"""Jira Cloud REST v3 issue creation with explicit content review."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from http.client import HTTPException
from pathlib import Path
from uuid import uuid4
import hashlib
import json
import os
import re
import ssl
from typing import Dict, Optional
from urllib import error, request
from urllib.parse import quote, urlencode, urlsplit

import certifi

from .config import IntegrationError


class JiraUnknownOutcome(IntegrationError):
    """The issue create request may have succeeded; do not retry blindly."""


def _read_attachment(path: Path) -> bytes:
    with path.open("rb") as source:
        data = source.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise IntegrationError("Attachment exceeds the 10 MiB limit")
    return data


@dataclass(frozen=True)
class JiraConnection:
    """Named Jira Cloud connection with environment credential references."""

    name: str
    base_url: str
    email_env: str
    token_env: str
    timeout_seconds: float = 30
    read_only: bool = True

    def __post_init__(self):
        parts = urlsplit(self.base_url)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or parts.path not in ("", "/")
        ):
            raise IntegrationError("Jira base URL must be an HTTPS site origin")
        if not self.name or not all(
            re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", x)
            for x in (self.email_env, self.token_env)
        ):
            raise IntegrationError("Invalid Jira connection or credential reference")
        if not 0 < self.timeout_seconds <= 300:
            raise IntegrationError("Invalid Jira timeout")


@dataclass(frozen=True)
class JiraIssueRequest:
    """General issue input independent of data product handoffs."""

    project: str
    issue_type_id: str
    summary: str
    description: str
    fields: Dict[str, object] = field(default_factory=dict)
    attachments: tuple = ()


def markdown_to_adf(markdown: str) -> dict:
    """Render supported headings, paragraphs, lists and links into ADF."""

    def inline(value: str) -> list:
        result = []
        at = 0
        for match in re.finditer(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", value):
            if match.start() > at:
                result.append({"type": "text", "text": value[at : match.start()]})
            result.append(
                {
                    "type": "text",
                    "text": match.group(1),
                    "marks": [{"type": "link", "attrs": {"href": match.group(2)}}],
                }
            )
            at = match.end()
        if at < len(value):
            result.append({"type": "text", "text": value[at:]})
        return result

    blocks = []
    items = []
    list_kind = None

    def flush():
        if items:
            blocks.append({"type": list_kind, "content": list(items)})
            items.clear()

    for line in markdown.splitlines():
        if not line.strip():
            flush()
            list_kind = None
            continue
        if line.startswith(("```", "    ", ">", "|")) or "![" in line:
            raise IntegrationError("Unsupported Markdown in Jira description")
        ordered = re.match(r"^\d+\. (.+)$", line)
        if line.startswith("- ") or ordered:
            kind = "orderedList" if ordered else "bulletList"
            if list_kind != kind:
                flush()
                list_kind = kind
            text = ordered.group(1) if ordered else line[2:]
            items.append(
                {
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": inline(text)}],
                }
            )
            continue
        flush()
        list_kind = None
        heading = re.match(r"^(#{1,6}) (.+)$", line)
        if heading:
            blocks.append(
                {
                    "type": "heading",
                    "attrs": {"level": len(heading.group(1))},
                    "content": inline(heading.group(2)),
                }
            )
        else:
            blocks.append({"type": "paragraph", "content": inline(line)})
    flush()
    if not blocks:
        raise IntegrationError("Issue description cannot be empty")
    return {"version": 1, "type": "doc", "content": blocks}


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class JiraCloudAdapter:
    """Create general Jira issues using reviewed REST v3 requests."""

    def __init__(self, connection: JiraConnection):
        self.connection = connection
        self._opener = request.build_opener(
            _NoRedirect(),
            request.HTTPSHandler(
                context=ssl.create_default_context(cafile=certifi.where())
            ),
        )

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        email, token = os.getenv(self.connection.email_env), os.getenv(
            self.connection.token_env
        )
        if not email or not token or any(c in email + token for c in "\r\n"):
            raise IntegrationError("Jira credentials are missing or invalid")
        encoded = base64.b64encode((email + ":" + token).encode()).decode("ascii")
        data = json.dumps(body).encode() if body is not None else None
        req = request.Request(
            self.connection.base_url.rstrip("/") + "/rest/api/3/" + path,
            data=data,
            headers={
                "Authorization": "Basic " + encoded,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with self._opener.open(
                req, timeout=self.connection.timeout_seconds
            ) as response:
                raw = response.read(5 * 1024 * 1024 + 1)
                if len(raw) > 5 * 1024 * 1024:
                    if method == "POST":
                        raise JiraUnknownOutcome(
                            "Jira response exceeded size limit; search before retrying"
                        )
                    raise IntegrationError("Jira response exceeds size limit")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    if method == "POST":
                        raise JiraUnknownOutcome(
                            "Jira issue outcome is unknown; search before retrying"
                        )
                    raise IntegrationError("Unexpected Jira response")
                return value
        except error.HTTPError as exc:
            status = exc.code
            exc.close()
            if method == "POST" and (
                status == 408 or status >= 500 or 300 <= status < 400
            ):
                raise JiraUnknownOutcome(
                    "Jira issue outcome is unknown; search before retrying"
                ) from None
            raise IntegrationError(
                "Jira request returned HTTP " + str(status)
            ) from None
        except (error.URLError, TimeoutError, OSError, HTTPException):
            if method == "POST":
                raise JiraUnknownOutcome(
                    "Jira issue outcome is unknown; search the project before retrying"
                ) from None
            raise IntegrationError("Jira request failed or timed out") from None
        except (UnicodeError, ValueError):
            if method == "POST":
                raise JiraUnknownOutcome(
                    "Jira returned an unreadable creation result; search before retrying"
                ) from None
            raise IntegrationError("Jira returned invalid JSON") from None

    def review_issue(self, issue: JiraIssueRequest) -> dict:
        """Read required-field metadata and return the exact proposed issue."""
        if (
            not re.fullmatch(r"[A-Za-z0-9_-]+", issue.project)
            or not re.fullmatch(r"[0-9]+", issue.issue_type_id)
            or not issue.summary.strip()
            or len(issue.summary) > 255
            or any(ord(c) < 32 for c in issue.summary)
        ):
            raise IntegrationError(
                "Valid project, issue type ID and summary are required"
            )
        if set(issue.fields) & {
            "project",
            "issuetype",
            "summary",
            "description",
            "parent",
            "assignee",
        }:
            raise IntegrationError("Custom fields may not override core issue fields")
        project = quote(issue.project, safe="")
        issue_type = quote(issue.issue_type_id, safe="")
        path = "issue/createmeta/" + project + "/issuetypes/" + issue_type
        fields = {
            "project": {"id" if issue.project.isdigit() else "key": issue.project},
            "issuetype": {"id": issue.issue_type_id},
            "summary": issue.summary,
            "description": markdown_to_adf(issue.description),
            **issue.fields,
        }
        seen = []
        for offset in range(0, 1000, 50):
            meta = self._request(
                "GET", path + "?startAt=" + str(offset) + "&maxResults=50"
            )
            entries = meta.get("fields", meta.get("values"))
            if not isinstance(entries, list):
                raise IntegrationError("Jira create metadata is unavailable")
            seen.extend(entries)
            if meta.get("isLast") is True or len(entries) < 50:
                break
        else:
            raise IntegrationError("Jira create metadata exceeded page limit")
        if not seen:
            raise IntegrationError(
                "Jira create metadata contains no fields; verify project and issue type access"
            )
        missing = [
            x.get("fieldId")
            for x in seen
            if isinstance(x, dict)
            and x.get("required")
            and not x.get("hasDefaultValue")
            and x.get("fieldId") not in fields
        ]
        if missing:
            raise IntegrationError(
                "Missing required Jira fields: " + ", ".join(map(str, missing))
            )
        duplicates = []
        duplicate_warning = (
            "Search is advisory and cannot prevent concurrent duplicates."
        )
        try:
            safe_summary = issue.summary.replace("\\", " ").replace('"', " ")
            jql = (
                'project = "' + issue.project + '" AND summary ~ "' + safe_summary + '"'
            )
            matches = self._request(
                "GET",
                "search/jql?"
                + urlencode({"jql": jql, "maxResults": "10", "fields": "summary"}),
            )
            if isinstance(matches.get("issues"), list):
                duplicates = [
                    {"key": x.get("key"), "summary": x.get("fields", {}).get("summary")}
                    for x in matches["issues"][:10]
                    if isinstance(x, dict)
                ]
            else:
                duplicate_warning = "Duplicate search returned an unexpected response; no atomic duplicate protection."
        except IntegrationError:
            duplicate_warning = (
                "Duplicate search was unavailable; no atomic duplicate protection."
            )
        if len(issue.attachments) > 5:
            raise IntegrationError("At most five attachments may be selected")
        attachments = []
        filenames = set()
        for selected in issue.attachments:
            path = Path(selected)
            if (
                path.is_symlink()
                or not path.is_file()
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", path.name)
            ):
                raise IntegrationError("Invalid attachment path or filename")
            if path.name in filenames:
                raise IntegrationError("Attachment filenames must be unique")
            filenames.add(path.name)
            data = _read_attachment(path)
            attachments.append(
                {
                    "filename": path.name,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        payload = {"fields": fields}
        digest = hashlib.sha256(
            json.dumps(
                {
                    "destination": self.connection.base_url.rstrip("/"),
                    "payload": payload,
                    "attachments": attachments,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        return {
            "destination": self.connection.name,
            "project": issue.project,
            "issue_type_id": issue.issue_type_id,
            "summary": issue.summary,
            "description": issue.description,
            "payload": payload,
            "reviewed_sha256": digest,
            "attachments": attachments,
            "possible_duplicates": duplicates,
            "duplicate_warning": duplicate_warning,
        }

    def create_issue(self, issue: JiraIssueRequest, *, reviewed_sha256: str) -> dict:
        """Create one issue only after revalidating the reviewed request."""
        if self.connection.read_only:
            raise IntegrationError("Jira connection is read-only")
        review = self.review_issue(issue)
        if review["reviewed_sha256"] != reviewed_sha256:
            raise IntegrationError("Jira issue content changed since review")
        result = self._request("POST", "issue", review["payload"])
        key = result.get("key")
        if not isinstance(key, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_]*-[0-9]+", key
        ):
            raise JiraUnknownOutcome(
                "Jira returned no confirmed issue key; search before retrying"
            )
        result = {
            "key": key,
            "url": self.connection.base_url.rstrip("/") + "/browse/" + key,
            "attachments_uploaded": [],
            "attachment_failures": [],
        }
        for path, expected in zip(issue.attachments, review["attachments"]):
            try:
                attachment = Path(path)
                if attachment.is_symlink() or not attachment.is_file():
                    raise IntegrationError("Attachment is unavailable or changed")
                data = _read_attachment(attachment)
                if (
                    len(data) != expected["size"]
                    or hashlib.sha256(data).hexdigest() != expected["sha256"]
                ):
                    raise IntegrationError("Attachment changed after review")
                self._upload_attachment(key, expected["filename"], data)
                result["attachments_uploaded"].append(expected["filename"])
            except (IntegrationError, OSError):
                result["attachment_failures"].append(expected["filename"])
        return result

    def _upload_attachment(self, key: str, filename: str, data: bytes) -> None:
        """Upload one reviewed file without retrying an uncertain request."""
        email, token = os.getenv(self.connection.email_env), os.getenv(
            self.connection.token_env
        )
        if not email or not token or any(c in email + token for c in "\r\n"):
            raise IntegrationError("Jira credentials are missing or invalid")
        boundary = "odps-" + uuid4().hex
        body = (
            (
                "--"
                + boundary
                + '\r\nContent-Disposition: form-data; name="file"; filename="'
                + filename
                + '"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode()
            + data
            + ("\r\n--" + boundary + "--\r\n").encode()
        )
        encoded = base64.b64encode((email + ":" + token).encode()).decode("ascii")
        req = request.Request(
            self.connection.base_url.rstrip("/")
            + "/rest/api/3/issue/"
            + quote(key, safe="")
            + "/attachments",
            data=body,
            headers={
                "Authorization": "Basic " + encoded,
                "Accept": "application/json",
                "X-Atlassian-Token": "no-check",
                "Content-Type": "multipart/form-data; boundary=" + boundary,
            },
            method="POST",
        )
        try:
            with self._opener.open(
                req, timeout=self.connection.timeout_seconds
            ) as response:
                if not 200 <= response.status < 300:
                    raise IntegrationError("Attachment upload failed")
        except (error.URLError, TimeoutError, OSError, HTTPException):
            raise IntegrationError(
                "Attachment upload failed or outcome is unknown"
            ) from None


def load_jira_connection(path, name: Optional[str] = None) -> JiraConnection:
    """Load a named Jira Cloud profile without resolving credentials."""
    from pathlib import Path
    import yaml
    from .config import _UniqueLoader

    try:
        root = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=_UniqueLoader)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise IntegrationError("Cannot read Jira connection configuration") from None
    if (
        not isinstance(root, dict)
        or root.get("version") != 1
        or not isinstance(root.get("connections"), dict)
    ):
        raise IntegrationError("Invalid Jira connection configuration")
    selected = name or root.get("default_connection")
    profile = root["connections"].get(selected)
    if not isinstance(profile, dict) or profile.get("platform") != "jira_cloud":
        raise IntegrationError("Jira connection is missing or invalid")
    if set(profile) - {"platform", "base_url", "read_only", "auth", "http"}:
        raise IntegrationError("Unknown Jira connection fields")
    auth = profile.get("auth")
    http = profile.get("http", {})
    if (
        not isinstance(auth, dict)
        or set(auth) != {"type", "email_env", "token_env"}
        or auth.get("type") != "basic_env"
        or not isinstance(http, dict)
        or set(http) - {"timeout_seconds"}
    ):
        raise IntegrationError("Invalid Jira authentication or HTTP configuration")
    read_only = profile.get("read_only", True)
    if not isinstance(read_only, bool):
        raise IntegrationError("Jira read_only must be a boolean")
    try:
        return JiraConnection(
            str(selected),
            profile["base_url"],
            auth["email_env"],
            auth["token_env"],
            http.get("timeout_seconds", 30),
            read_only,
        )
    except (KeyError, TypeError, ValueError):
        raise IntegrationError("Invalid Jira connection configuration") from None
