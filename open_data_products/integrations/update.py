"""Reviewed, conditional updates to native OpenMetadata product metadata."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.client import HTTPException
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING, cast
from urllib import error, request
from urllib.parse import quote
from uuid import UUID

from .config import IntegrationError

if TYPE_CHECKING:
    from .openmetadata import OpenMetadataAdapter


class UnknownUpdateOutcome(IntegrationError):
    """An update may have reached the server; inspect the target before retrying."""


def _read_update_source(path: str) -> str:
    """Read a bounded local ODPS input file for a reviewed update."""
    source = Path(path)
    if source.suffix.lower() not in (".yaml", ".yml", ".json"):
        raise IntegrationError("Update input must be a YAML or JSON file")
    try:
        if source.stat().st_size > 5 * 1024 * 1024:
            raise IntegrationError("ODPS input is too large")
        return source.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise IntegrationError("Unable to read ODPS update input") from None


def resolve_owner(adapter: "OpenMetadataAdapter", owner: str) -> dict:
    """Resolve a user or team to a verified platform identity."""
    if owner == "current":
        found = adapter._json("users/loggedInUser")
        try:
            ident = str(UUID(found.get("id")))
        except (ValueError, TypeError, AttributeError):
            raise IntegrationError(
                "Authenticated user has no valid platform identity"
            ) from None
        if (
            not isinstance(found.get("fullyQualifiedName"), str)
            or not found["fullyQualifiedName"]
            or found.get("deleted") is True
        ):
            raise IntegrationError(
                "Authenticated user identity is unavailable or inactive"
            )
        return {"id": ident, "type": "user", "name": found["fullyQualifiedName"]}
    if not isinstance(owner, str) or ":" not in owner:
        raise IntegrationError("Owner must be user:NAME or team:FQN")
    kind, name = owner.split(":", 1)
    if kind not in ("user", "team") or not name or name != name.strip():
        raise IntegrationError("Owner must be user:NAME or team:FQN")
    found = adapter._json(
        ("users/name/" if kind == "user" else "teams/name/") + quote(name, safe="")
    )
    try:
        ident = str(UUID(found.get("id")))
    except (ValueError, TypeError, AttributeError):
        raise IntegrationError("Owner has no valid platform identity") from None
    if found.get("fullyQualifiedName") != name or found.get("deleted") is True:
        raise IntegrationError(
            "Owner identity does not match the requested active owner"
        )
    return {"id": ident, "type": kind}


def resolve_tag(adapter: "OpenMetadataAdapter", tag: str) -> dict:
    """Resolve a classification tag to a verified platform identity."""
    if not isinstance(tag, str) or not tag or tag != tag.strip():
        raise IntegrationError("Tag must be an existing classification tag FQN")
    found = adapter._json("tags/name/" + quote(tag, safe=""))
    try:
        ident = str(UUID(found.get("id")))
    except (ValueError, TypeError, AttributeError):
        raise IntegrationError("Tag has no valid platform identity") from None
    if found.get("fullyQualifiedName") != tag or found.get("deleted") is True:
        raise IntegrationError("Tag identity does not match the requested active tag")
    return {"id": ident, "tagFQN": tag}


@dataclass(frozen=True)
class UpdateReview:
    """Baseline and proposed native product changes."""

    profile: str
    product_id: str
    fqn: Optional[str]
    revision: str
    before: Dict[str, object]
    proposed: Dict[str, object]
    review_sha256: str
    write_enabled: bool
    warnings: Tuple[str, ...]
    domain_id: Optional[str] = None
    source_sha256: Optional[str] = None
    source_validation: Optional[Dict[str, object]] = None
    source_unsupported_fields: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, object]:
        """Return the update review without credentials or the full native body."""
        result = asdict(self)
        if self.source_sha256 is None:
            for key in (
                "source_sha256",
                "source_validation",
                "source_unsupported_fields",
            ):
                result.pop(key)
        return result


@dataclass(frozen=True)
class UpdateResult:
    """Update response and comparison against a fresh retrieval."""

    status: str
    profile: str
    product_id: str
    previous_revision: str
    current_revision: Optional[str]
    recorded_at: str
    comparison: Dict[str, str]
    warnings: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        """Return the update outcome."""
        return asdict(self)


def review_product_update(
    adapter: "OpenMetadataAdapter",
    product_id: str,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    domain: Optional[str] = None,
    owners: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    source_yaml: Optional[str] = None,
) -> UpdateReview:
    """Review changes against a live product baseline."""
    try:
        if not isinstance(product_id, str):
            raise ValueError
        canonical = str(UUID(product_id))
    except ValueError:
        raise IntegrationError("A valid product UUID is required") from None
    source_document = None
    source_details = None
    source_validation = None
    source_sha256 = None
    unsupported: List[str] = []
    overridden: List[str] = []
    if source_yaml is not None:
        from ..agent import validate_document
        from .create import _load_unambiguous_yaml

        if (
            not isinstance(source_yaml, str)
            or len(source_yaml.encode("utf-8")) > 5 * 1024 * 1024
        ):
            raise IntegrationError("ODPS input is missing or too large")
        source_document = _load_unambiguous_yaml(source_yaml)
        try:
            if not isinstance(source_document, dict):
                raise ValueError("Invalid document")
            validation = validate_document(source_document)
        except (ValueError, TypeError, AttributeError):
            raise IntegrationError(
                "Input is not a valid ODPS product document"
            ) from None
        if validation.spec != "odps" or not validation.valid:
            raise IntegrationError(
                "ODPS input validation failed: "
                + "; ".join(validation.errors or ["Not an ODPS product"])
            )
        product = source_document.get("product")
        details = product.get("details") if isinstance(product, dict) else None
        source_details = details.get("en") if isinstance(details, dict) else None
        if (
            not isinstance(product, dict)
            or not isinstance(details, dict)
            or not isinstance(source_details, dict)
            or not isinstance(source_details.get("productID"), str)
            or not source_details["productID"].strip()
        ):
            raise IntegrationError(
                "ODPS input must have an English productID for target verification"
            )
        for key in source_document:
            if key not in ("schema", "version", "product"):
                unsupported.append("/" + str(key))
        for key in product:
            if key != "details":
                unsupported.append("/product/" + str(key))
        for language, block in details.items():
            if language != "en":
                unsupported.append("/product/details/" + str(language))
            elif isinstance(block, dict):
                for key in block:
                    if key not in ("name", "productID", "description"):
                        unsupported.append("/product/details/en/" + str(key))
        if title is not None and title != source_details.get("name"):
            overridden.append("/product/details/en/name")
        if description is not None and description != source_details.get("description"):
            overridden.append("/product/details/en/description")
        if title is None:
            title = source_details.get("name")
        if description is None:
            description = source_details.get("description") or source_details.get(
                "valueProposition"
            )
            if (
                description
                and not source_details.get("description")
                and "/product/details/en/valueProposition" in unsupported
            ):
                unsupported.remove("/product/details/en/valueProposition")
        unsupported.extend(overridden)
        source_validation = validation.to_dict()
        source_sha256 = hashlib.sha256(source_yaml.encode("utf-8")).hexdigest()
    if (
        title is None
        and description is None
        and domain is None
        and not owners
        and not tags
    ):
        raise IntegrationError(
            "At least one title, description, domain, owner or tag change is required"
        )
    if title is not None and (
        not isinstance(title, str) or not title.strip() or len(title) > 1024
    ):
        raise IntegrationError(
            "Title must be a nonempty string of at most 1024 characters"
        )
    if description is not None and (
        not isinstance(description, str) or len(description) > 65536
    ):
        raise IntegrationError(
            "Description must be a string of at most 65536 characters"
        )
    if domain is not None and (
        not isinstance(domain, str)
        or not domain.strip()
        or domain != domain.strip()
        or len(domain) > 1024
    ):
        raise IntegrationError("Domain must be a nonempty fully qualified name")
    version = adapter._json("system/version").get("version")
    if version != "2.1.0":
        raise IntegrationError(
            "Product update is supported only for the reviewed OpenMetadata 2.1.0 API"
        )
    if owners is not None or tags is not None:
        product = adapter.get_product(
            canonical, include_domains=domain is not None, include_owners_tags=True
        )
    elif domain is not None:
        product = adapter.get_product(canonical, include_domains=True)
    else:
        product = adapter.get_product(canonical)
    data = product.data
    if not isinstance(data, dict) or data.get("id") != canonical:
        raise IntegrationError("The platform returned an unexpected product identity")
    if source_details is not None and data.get("name") != source_details["productID"]:
        raise IntegrationError(
            "ODPS productID does not match the target OpenMetadata product"
        )
    revision = data.get("version")
    if isinstance(revision, bool) or not isinstance(revision, (int, float)):
        raise IntegrationError(
            "Product revision is unavailable; conditional update is blocked"
        )
    proposed: Dict[str, object] = {}
    if title is not None:
        proposed["displayName"] = title
    if description is not None:
        proposed["description"] = description
    if owners is not None:
        existing = data.get("owners")
        if not isinstance(existing, list) or any(
            not isinstance(x, dict)
            or not x.get("id")
            or x.get("type") not in ("user", "team")
            for x in existing
        ):
            raise IntegrationError(
                "Current product owners are unavailable; owner update is blocked"
            )
        refs = [{"id": x["id"], "type": x["type"]} for x in existing]
        for owner in owners:
            ref = resolve_owner(adapter, owner)
            if not any(x["id"] == ref["id"] and x["type"] == ref["type"] for x in refs):
                refs.append(ref)
        proposed["owners"] = refs
    if tags is not None:
        existing_tags = data.get("tags")
        if not isinstance(existing_tags, list) or any(
            not isinstance(x, dict) or not isinstance(x.get("tagFQN"), str)
            for x in existing_tags
        ):
            raise IntegrationError(
                "Current product tags are unavailable; tag update is blocked"
            )
        labels = list(existing_tags)
        for tag in tags:
            resolve_tag(adapter, tag)
            if not any(
                x.get("tagFQN") == tag
                and x.get("source", "Classification") == "Classification"
                for x in labels
            ):
                labels.append(
                    {
                        "tagFQN": tag,
                        "source": "Classification",
                        "labelType": "Manual",
                        "state": "Confirmed",
                    }
                )
        proposed["tags"] = labels
    domain_id = None
    if domain is not None:
        target = adapter._json("domains/name/" + quote(domain, safe=""))
        try:
            domain_id = str(UUID(target.get("id")))
        except (ValueError, TypeError, AttributeError):
            raise IntegrationError(
                "Target domain has no valid platform identity"
            ) from None
        if target.get("fullyQualifiedName") != domain:
            raise IntegrationError(
                "The platform returned an unexpected domain identity"
            )
        existing = data.get("domains")
        if not isinstance(existing, list) or any(
            not isinstance(item, dict)
            or not isinstance(item.get("fullyQualifiedName"), str)
            for item in existing
        ):
            raise IntegrationError(
                "Current product domains are unavailable; domain update is blocked"
            )
        proposed["domain"] = domain
    before = {key: data.get(key) for key in proposed}
    if domain is not None:
        before["domain"] = [item["fullyQualifiedName"] for item in data["domains"]]
    review_input = {
        "operation": "native-patch",
        "profile": adapter.profile.name,
        "base_url": adapter.profile.base_url,
        "server_version": version,
        "product": data,
        "proposed": proposed,
        "domain_id": domain_id,
    }
    if source_sha256 is not None:
        review_input["source_sha256"] = source_sha256
    fingerprint = json.dumps(
        review_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    warnings: Tuple[str, ...] = (
        "OpenMetadata's metadata revision is not the ODPS product version.",
        "If-Match is requested using the observed entity revision; enforcement must be verified for the deployment.",
    )
    if domain is not None:
        warnings += (
            "The selected domain replaces all current product domains. OpenMetadata may migrate associated assets and detach conflicting product relationships; inspect dependencies before execution.",
        )
    if owners is not None or tags is not None:
        warnings += (
            "Requested owners and tags are added to existing assignments; they are not replaced.",
        )
    if source_sha256 is not None:
        warnings += (
            "Only the ODPS name and description (or value proposition fallback) map to native update fields; other source fields are not applied.",
        )
        if overridden:
            warnings += (
                "Explicit command options override the listed ODPS input fields.",
            )
    return UpdateReview(
        adapter.profile.name,
        canonical,
        product.provenance.fqn,
        str(revision),
        before,
        proposed,
        hashlib.sha256(fingerprint.encode("utf-8")).hexdigest(),
        not adapter.profile.read_only,
        warnings,
        domain_id,
        source_sha256,
        source_validation,
        tuple(unsupported),
    )


def execute_product_update(
    adapter: "OpenMetadataAdapter",
    product_id: str,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    domain: Optional[str] = None,
    owners: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    source_yaml: Optional[str] = None,
    reviewed_sha256: str,
) -> UpdateResult:
    """Apply a reviewed native metadata patch once and compare a fresh read."""
    from .openmetadata import PlatformError

    adapter.require_write_access()
    if not reviewed_sha256:
        raise IntegrationError("Update requires a review digest")
    review = review_product_update(
        adapter,
        product_id,
        title=title,
        description=description,
        domain=domain,
        owners=owners,
        tags=tags,
        source_yaml=source_yaml,
    )
    if review.review_sha256 != reviewed_sha256:
        raise IntegrationError(
            "Product, changes or destination changed since review; review again"
        )
    patch: List[Dict[str, object]] = [
        {"op": "add", "path": "/" + key, "value": value}
        for key, value in review.proposed.items()
        if key != "domain"
    ]
    if domain is not None:
        patch.append(
            {
                "op": "add",
                "path": "/domains",
                "value": [{"id": review.domain_id, "type": "domain"}],
            }
        )
    token = adapter.profile.token()
    base = adapter.profile.base_url
    url = (
        base
        + ("/v1/" if base.endswith("/api") else "/api/v1/")
        + "dataProducts/"
        + quote(review.product_id, safe="")
    )
    req = request.Request(
        url,
        data=json.dumps(patch).encode("utf-8"),
        method="PATCH",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "Content-Type": "application/json-patch+json",
            "If-Match": 'W/"' + review.revision + '"',
        },
    )
    try:
        with adapter._opener.open(
            req, timeout=adapter.profile.timeout_seconds
        ) as response:
            if response.status not in (200, 204):
                raise UnknownUpdateOutcome(
                    "Update was not confirmed as complete; inspect the target before retrying"
                )
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code == 408 or code >= 500 or 300 <= code < 400:
            raise UnknownUpdateOutcome(
                "Update outcome is unknown; inspect the target before retrying"
            ) from None
        raise PlatformError(
            "Platform update returned HTTP " + str(code), code
        ) from None
    except (error.URLError, TimeoutError, OSError, HTTPException):
        raise UnknownUpdateOutcome(
            "Update outcome is unknown; inspect the target before retrying"
        ) from None
    warnings = list(review.warnings)
    comparison = {}
    current_revision = None
    try:
        if owners is not None or tags is not None:
            actual = adapter.get_product(
                review.product_id,
                include_domains=domain is not None,
                include_owners_tags=True,
            )
        elif domain is not None:
            actual = adapter.get_product(review.product_id, include_domains=True)
        else:
            actual = adapter.get_product(review.product_id)
        data = actual.data if isinstance(actual.data, dict) else {}
        current_revision = actual.provenance.revision
        comparison = {
            key: "matched" if data.get(key) == value else "different_or_missing"
            for key, value in review.proposed.items()
            if key not in ("domain", "owners", "tags")
        }
        if owners is not None:
            current = data.get("owners")
            expected = {
                (x["id"], x["type"])
                for x in cast(List[Dict[str, str]], review.proposed["owners"])
            }
            comparison["owners"] = (
                "matched"
                if isinstance(current, list)
                and {
                    (x.get("id"), x.get("type")) for x in current if isinstance(x, dict)
                }
                == expected
                else "different_or_missing"
            )
        if tags is not None:
            current = data.get("tags")
            expected_tags = {
                (x["tagFQN"], x.get("source", "Classification"))
                for x in cast(List[Dict[str, str]], review.proposed["tags"])
            }
            comparison["tags"] = (
                "matched"
                if isinstance(current, list)
                and {
                    (x.get("tagFQN"), x.get("source", "Classification"))
                    for x in current
                    if isinstance(x, dict)
                }
                == expected_tags
                else "different_or_missing"
            )
        if domain is not None:
            refs = data.get("domains")
            if not isinstance(refs, list) or any(
                not isinstance(item, dict)
                or not isinstance(item.get("fullyQualifiedName"), str)
                for item in refs
            ):
                comparison["domain"] = "unverified"
            else:
                comparison["domain"] = (
                    "matched"
                    if len(refs) == 1 and refs[0].get("fullyQualifiedName") == domain
                    else "different_or_missing"
                )
    except IntegrationError:
        warnings.append(
            "Post-update retrieval failed; the updated fields could not be verified"
        )
        comparison = {key: "unverified" for key in review.proposed}
    return UpdateResult(
        "update_accepted",
        review.profile,
        review.product_id,
        review.revision,
        current_revision,
        datetime.now(timezone.utc).isoformat(),
        comparison,
        tuple(warnings),
    )
