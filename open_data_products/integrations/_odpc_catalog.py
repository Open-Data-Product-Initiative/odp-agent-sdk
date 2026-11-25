"""Map OpenMetadata product results to validated ODPC 1.0 catalogs."""

import math
from typing import Dict, List, Optional, TYPE_CHECKING
from urllib.parse import quote
from uuid import UUID

from ..odpc.catalog import SCHEMA_URI, default_catalog_metadata, validate_catalog
from .config import IntegrationError

if TYPE_CHECKING:
    from .openmetadata import OpenMetadataAdapter


def _server_version(adapter: "OpenMetadataAdapter") -> str:
    version = adapter._json("system/version").get("version")
    if not isinstance(version, str) or not version.strip():
        raise IntegrationError(
            "OpenMetadata version is unavailable; ODPC product model cannot be identified"
        )
    return version


def _product_reference(
    adapter: "OpenMetadataAdapter", item: dict, version: str
) -> Dict[str, object]:
    try:
        product_id = str(UUID(item.get("id")))
    except (ValueError, TypeError, AttributeError):
        raise IntegrationError(
            "OpenMetadata product has no valid UUID; cannot create an ODPC catalog"
        ) from None
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise IntegrationError(
            "OpenMetadata product name is missing; cannot create an ODPC catalog"
        )
    revision = item.get("version")
    if (
        isinstance(revision, bool)
        or not isinstance(revision, (str, int, float))
        or not str(revision).strip()
        or (isinstance(revision, float) and not math.isfinite(revision))
    ):
        raise IntegrationError(
            "OpenMetadata revision is missing for product "
            + product_id
            + "; cannot create an ODPC catalog"
        )
    display_name = item.get("displayName")
    if not isinstance(display_name, str) or not display_name.strip():
        display_name = name
    description = item.get("description")
    has_description = isinstance(description, str) and bool(description.strip())
    if not has_description:
        description = "No description was provided by OpenMetadata."
    base = adapter.profile.base_url
    uri = (
        base
        + ("/v1/" if base.endswith("/api") else "/api/v1/")
        + "dataProducts/"
        + quote(product_id, safe="")
    )
    reference: Dict[str, object] = {
        "id": product_id,
        "productID": name,
        "productVersion": str(revision),
        "name": {"en": display_name},
        "description": {"en": description},
        "productModel": {
            "standard": "OpenMetadata",
            "version": version,
            "format": "api",
            "$ref": uri,
        },
        "x-productVersion-source": "OpenMetadata entity metadata revision; not an independently verified product release version",
        "x-language-mapping": "OpenMetadata text is not language-tagged; mapped to required en without translation",
        "x-description-source": (
            "OpenMetadata"
            if has_description
            else "placeholder: description missing in OpenMetadata"
        ),
    }
    visibility = item.get("visibility")
    if isinstance(visibility, str) and visibility.lower() in (
        "public",
        "internal",
        "restricted",
        "private",
    ):
        reference["visibility"] = visibility.lower()
    fqn = item.get("fullyQualifiedName")
    if isinstance(fqn, str) and fqn:
        reference["x-openmetadata-fqn"] = fqn
    return reference


def _catalog(
    adapter: "OpenMetadataAdapter", items: List[object], version: str, source: dict
) -> dict:
    references: List[Dict[str, object]] = []
    identifiers = set()
    for item in items:
        if not isinstance(item, dict):
            raise IntegrationError(
                "OpenMetadata returned an invalid product in the catalog"
            )
        reference = _product_reference(adapter, item, version)
        product_id = reference["id"]
        if product_id in identifiers:
            raise IntegrationError(
                "OpenMetadata returned a repeated product; cannot create a reliable ODPC catalog"
            )
        identifiers.add(product_id)
        references.append(reference)
    metadata = default_catalog_metadata(
        catalog_id="openmetadata-" + adapter.profile.name,
        name="OpenMetadata product catalog",
        description="Product references derived from OpenMetadata product metadata.",
    )
    metadata["x-source"] = {
        "platform": "openmetadata",
        "connection": adapter.profile.name,
        "serverVersion": version,
        **source,
    }
    document = {
        "schema": SCHEMA_URI,
        "version": "1.0",
        "kind": "Catalog",
        "catalog": {"metadata": metadata, "productReferences": references},
    }
    validation = validate_catalog(document)
    if not validation.valid:
        raise IntegrationError(
            "Generated ODPC catalog did not validate: " + "; ".join(validation.errors)
        )
    return document


def list_odpc_catalog(
    adapter: "OpenMetadataAdapter",
    *,
    page_size: int = 100,
    max_pages: int = 100,
    after: Optional[str] = None,
) -> dict:
    """Build a validated ODPC catalog from paginated product metadata."""
    if (
        isinstance(max_pages, bool)
        or not isinstance(max_pages, int)
        or not 1 <= max_pages <= 1000
    ):
        raise IntegrationError("Catalog page limit must be between 1 and 1000")
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= 1000
    ):
        raise IntegrationError("Page limit must be between 1 and 1000")
    version = _server_version(adapter)
    cursor = after
    cursors = {after} if after else set()
    items: List[object] = []
    retrieved_at = None
    for _ in range(max_pages):
        page = adapter.list_products(limit=page_size, after=cursor)
        items.extend(page.products)
        retrieved_at = page.provenance.retrieved_at
        cursor = page.after
        if not cursor:
            break
        if cursor in cursors:
            raise IntegrationError(
                "OpenMetadata repeated a pagination cursor; ODPC catalog is incomplete"
            )
        cursors.add(cursor)
    else:
        raise IntegrationError(
            "OpenMetadata listing exceeded the page limit; ODPC catalog is incomplete"
        )
    return _catalog(
        adapter,
        items,
        version,
        {
            "retrievedAt": retrieved_at,
            "operation": "list",
            "listing": "paginated; not an atomic snapshot",
            "startsAfterCursor": after is not None,
        },
    )


def search_odpc_catalog(
    adapter: "OpenMetadataAdapter", query: str, *, offset: int = 0, limit: int = 20
) -> dict:
    """Map one search page to an ODPC catalog with explicit pagination."""
    page = adapter.search_products(query, offset=offset, limit=limit)
    version = _server_version(adapter)
    items: List[object] = []
    for hit in page.products:
        identifier = hit.get("id")
        if not isinstance(identifier, str):
            raise IntegrationError(
                "OpenMetadata search result has no valid product UUID"
            )
        try:
            canonical = str(UUID(identifier))
        except (ValueError, TypeError, AttributeError):
            raise IntegrationError(
                "OpenMetadata search result has no valid product UUID"
            ) from None
        result = adapter.get_product(canonical)
        item = result.data
        if not isinstance(item, dict) or item.get("id") != canonical:
            raise IntegrationError(
                "OpenMetadata search result resolved to an unexpected product"
            )
        items.append(item)
    return _catalog(
        adapter,
        items,
        version,
        {
            "operation": "search",
            "retrievedAt": page.provenance.retrieved_at,
            "query": query,
            "offset": page.offset,
            "limit": page.limit,
            "total": page.total,
            "totalRelation": page.total_relation,
            "nextOffset": page.next_offset,
            "warnings": list(page.warnings),
        },
    )
