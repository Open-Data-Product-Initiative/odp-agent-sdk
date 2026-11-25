"""Reviewed OpenMetadata domain creation."""

from dataclasses import asdict, dataclass
import hashlib
from http.client import HTTPException
import json
import re
from typing import Dict, Optional, TYPE_CHECKING
from urllib import error, request
from urllib.parse import quote
from uuid import UUID

from .config import IntegrationError

if TYPE_CHECKING:
    from .openmetadata import OpenMetadataAdapter


class UnknownDomainCreateOutcome(IntegrationError):
    """Domain creation may have reached the platform."""


@dataclass(frozen=True)
class DomainCreateReview:
    """An exact domain creation candidate and review digest."""

    profile: str
    name: str
    description: str
    domain_type: str
    display_name: Optional[str]
    parent: Optional[str]
    review_sha256: str
    write_enabled: bool

    def to_dict(self) -> Dict[str, object]:
        """Return the domain creation review."""
        return asdict(self)


@dataclass(frozen=True)
class DomainCreateResult:
    """Created domain identity and verification status."""

    status: str
    domain_id: str
    fqn: Optional[str]
    comparison: Dict[str, str]
    review_sha256: str

    def to_dict(self) -> Dict[str, object]:
        """Return the sanitized domain creation result."""
        return asdict(self)


def review_domain_create(
    adapter: "OpenMetadataAdapter",
    *,
    name: str,
    description: str,
    domain_type: str,
    display_name: Optional[str] = None,
    parent: Optional[str] = None,
) -> DomainCreateReview:
    """Review a domain create without sending platform requests."""
    if not isinstance(name, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name
    ):
        raise IntegrationError("Domain name must be a 1–64 character identifier")
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > 65536
    ):
        raise IntegrationError(
            "Domain description must be nonempty and at most 65536 characters"
        )
    if domain_type not in ("Source-aligned", "Consumer-aligned", "Aggregate"):
        raise IntegrationError(
            "Domain type must be Source-aligned, Consumer-aligned or Aggregate"
        )
    for value in (display_name, parent):
        if value is not None and (
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
            or len(value) > 1024
        ):
            raise IntegrationError(
                "Domain display name and parent must be nonempty strings"
            )
    candidate = {
        "profile": adapter.profile.name,
        "base_url": adapter.profile.base_url,
        "name": name,
        "description": description,
        "domain_type": domain_type,
        "display_name": display_name,
        "parent": parent,
    }
    digest = hashlib.sha256(
        json.dumps(
            candidate, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return DomainCreateReview(
        adapter.profile.name,
        name,
        description,
        domain_type,
        display_name,
        parent,
        digest,
        not adapter.profile.read_only,
    )


def execute_domain_create(
    adapter: "OpenMetadataAdapter",
    *,
    name: str,
    description: str,
    domain_type: str,
    display_name: Optional[str],
    parent: Optional[str],
    reviewed_sha256: str,
) -> DomainCreateResult:
    """Create a reviewed domain once and verify its platform record."""
    from .openmetadata import PlatformError

    adapter.require_write_access()
    if adapter._closed:
        raise IntegrationError("Adapter is closed")
    review = review_domain_create(
        adapter,
        name=name,
        description=description,
        domain_type=domain_type,
        display_name=display_name,
        parent=parent,
    )
    if not reviewed_sha256 or reviewed_sha256 != review.review_sha256:
        raise IntegrationError("Domain create review digest does not match")
    if adapter._json("system/version").get("version") != "2.1.0":
        raise IntegrationError(
            "Domain creation is supported only for OpenMetadata 2.1.0"
        )
    body = {"name": name, "description": description, "domainType": domain_type}
    if display_name is not None:
        body["displayName"] = display_name
    if parent is not None:
        body["parent"] = parent
    base = adapter.profile.base_url
    url = base + ("/v1/" if base.endswith("/api") else "/api/v1/") + "domains"
    req = request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": "Bearer " + adapter.profile.token(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with adapter._opener.open(
            req, timeout=adapter.profile.timeout_seconds
        ) as response:
            if response.status not in (200, 201):
                raise UnknownDomainCreateOutcome(
                    "Domain create was not confirmed; inspect the platform before retrying"
                )
            raw = response.read(5 * 1024 * 1024 + 1)
            if len(raw) > 5 * 1024 * 1024:
                raise UnknownDomainCreateOutcome(
                    "Domain create response exceeded limit; inspect before retrying"
                )
            try:
                payload = json.loads(raw.decode("utf-8"))
                domain_id = str(UUID(payload["id"]))
            except (UnicodeError, ValueError, TypeError, KeyError, AttributeError):
                raise UnknownDomainCreateOutcome(
                    "Domain create response was unreadable; inspect before retrying"
                ) from None
    except error.HTTPError as exc:
        http_status = exc.code
        exc.close()
        if http_status == 408 or http_status >= 500 or 300 <= http_status < 400:
            raise UnknownDomainCreateOutcome(
                "Domain create outcome is unknown; inspect before retrying"
            ) from None
        raise PlatformError(
            "Platform domain create returned HTTP " + str(http_status), http_status
        ) from None
    except (error.URLError, TimeoutError, OSError, HTTPException):
        raise UnknownDomainCreateOutcome(
            "Domain create outcome is unknown; inspect before retrying"
        ) from None
    try:
        actual = adapter._json("domains/" + quote(domain_id, safe=""))
        comparison = {
            key: "matched" if actual.get(key) == value else "different_or_missing"
            for key, value in body.items()
            if key != "parent"
        }
        if parent is not None:
            ref = actual.get("parent")
            comparison["parent"] = (
                "matched"
                if isinstance(ref, dict) and ref.get("fullyQualifiedName") == parent
                else "different_or_missing"
            )
        comparison["identity"] = (
            "matched" if actual.get("id") == domain_id else "different_or_missing"
        )
        fqn = (
            actual.get("fullyQualifiedName")
            if isinstance(actual.get("fullyQualifiedName"), str)
            else None
        )
        if parent is None:
            comparison["fullyQualifiedName"] = (
                "matched" if fqn == name else "different_or_missing"
            )
        status = (
            "created"
            if all(value == "matched" for value in comparison.values()) and fqn
            else "created_with_mismatches"
        )
    except IntegrationError:
        status, fqn, comparison = (
            "created_unverified",
            None,
            {"readback": "unavailable"},
        )
    return DomainCreateResult(status, domain_id, fqn, comparison, review.review_sha256)
