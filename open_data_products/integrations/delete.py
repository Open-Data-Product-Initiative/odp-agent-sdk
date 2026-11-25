"""Reviewed permanent deletion of an OpenMetadata 2.1.0 product."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.client import HTTPException
import hashlib
import json
from typing import Dict, Optional, Tuple, TYPE_CHECKING
from urllib import error, request
from urllib.parse import quote
from uuid import UUID

from .config import IntegrationError

if TYPE_CHECKING:
    from .openmetadata import OpenMetadataAdapter


class UnknownDeleteOutcome(IntegrationError):
    """Deletion may have reached the server; inspect the product before retrying."""


@dataclass(frozen=True)
class DeleteReview:
    """The target and snapshot to review before a permanent deletion."""

    profile: str
    product_id: str
    product_name: Optional[str]
    fqn: Optional[str]
    revision: Optional[str]
    server_version: str
    permanent: bool
    recursive: bool
    write_enabled: bool
    review_sha256: str
    warnings: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        """Return review details without credentials or the native body."""
        return asdict(self)


@dataclass(frozen=True)
class DeleteResult:
    """A platform deletion result with a read-back observation."""

    status: str
    profile: str
    product_id: str
    fqn: Optional[str]
    permanent: bool
    recursive: bool
    reviewed_sha256: str
    timestamp: str
    verification: str
    warnings: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        """Return a sanitized deletion result."""
        return asdict(self)


def review_product_delete(
    adapter: "OpenMetadataAdapter", product_id: str
) -> DeleteReview:
    """Retrieve a product and review the permanent delete without mutating it."""
    try:
        if not isinstance(product_id, str):
            raise ValueError
        canonical = str(UUID(product_id))
    except ValueError:
        raise IntegrationError("A valid product UUID is required") from None
    version = adapter._json("system/version").get("version")
    if version != "2.1.0":
        raise IntegrationError(
            "Product deletion is supported only for the reviewed OpenMetadata 2.1.0 API"
        )
    result = adapter.get_product(canonical)
    data = result.data
    if not isinstance(data, dict) or data.get("id") != canonical:
        raise IntegrationError("The platform returned an unexpected product identity")
    fingerprint = json.dumps(
        {
            "operation": "delete-permanent-recursive",
            "profile": adapter.profile.name,
            "base_url": adapter.profile.base_url,
            "server_version": version,
            "product": data,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    name = data.get("displayName") or data.get("name")
    if not isinstance(name, str):
        name = None
    warnings = (
        "OpenMetadata 2.1.0 deletes this product permanently and recursively; it cannot be restored through the platform.",
        "Recursive deletion may also remove child entities; inspect dependencies before execution.",
        "The target is rechecked before deletion, but the server does not provide atomic revision protection for this operation.",
    )
    return DeleteReview(
        adapter.profile.name,
        canonical,
        name,
        result.provenance.fqn,
        result.provenance.revision,
        version,
        True,
        True,
        not adapter.profile.read_only,
        digest,
        warnings,
    )


def execute_product_delete(
    adapter: "OpenMetadataAdapter",
    product_id: str,
    *,
    reviewed_sha256: str,
    confirm_permanent: bool,
) -> DeleteResult:
    """Recheck and permanently delete a reviewed product once."""
    from .openmetadata import PlatformError

    adapter.require_write_access()
    if confirm_permanent is not True:
        raise IntegrationError(
            "Permanent recursive deletion requires explicit confirmation"
        )
    if not reviewed_sha256:
        raise IntegrationError("Deletion requires a review digest")
    review = review_product_delete(adapter, product_id)
    if reviewed_sha256 != review.review_sha256:
        raise IntegrationError(
            "Product or destination changed since review; review again"
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
        method="DELETE",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    try:
        with adapter._opener.open(
            req, timeout=adapter.profile.timeout_seconds
        ) as response:
            if response.status not in (200, 204):
                raise UnknownDeleteOutcome(
                    "Deletion was not confirmed as complete; inspect the target before retrying"
                )
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code == 408 or code >= 500 or 300 <= code < 400:
            raise UnknownDeleteOutcome(
                "Deletion outcome is unknown; inspect the target before retrying"
            ) from None
        raise PlatformError(
            "Platform deletion returned HTTP " + str(code), code
        ) from None
    except (error.URLError, TimeoutError, OSError, HTTPException):
        raise UnknownDeleteOutcome(
            "Deletion outcome is unknown; inspect the target before retrying"
        ) from None
    warnings = list(review.warnings)
    try:
        adapter.get_product(review.product_id)
        verification = "product_still_visible"
        warnings.append("Deletion returned success but the product remains visible")
    except PlatformError as exc:
        if exc.status == 404:
            verification = "not_found_by_id"
        else:
            verification = "unavailable"
            warnings.append(
                "Post-deletion retrieval failed; deletion could not be independently verified"
            )
    except IntegrationError:
        verification = "unavailable"
        warnings.append(
            "Post-deletion retrieval failed; deletion could not be independently verified"
        )
    return DeleteResult(
        "delete_accepted",
        review.profile,
        review.product_id,
        review.fqn,
        True,
        True,
        reviewed_sha256,
        datetime.now(timezone.utc).isoformat(),
        verification,
        tuple(warnings),
    )
