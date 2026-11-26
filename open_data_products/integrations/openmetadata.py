"""OpenMetadata read operations and reviewed ODPS creation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
import json
import re
import ssl
import time
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from urllib import error, request
from urllib.parse import quote, urlencode

import certifi
import yaml

from ..agent import validate_document
from ..odps.versions import detect_version
from ..results import ValidationResult
from .adapter import PlatformAdapter
from .config import ConnectionProfile, IntegrationError

if TYPE_CHECKING:
    from .create import CreateResult, CreateReview
    from .delete import DeleteResult, DeleteReview
    from .domains import DomainCreateResult, DomainCreateReview
    from .contracts import ContractImportResult, ContractImportReview
    from ._comparison import ProductComparison
    from .update import UpdateResult, UpdateReview


class PlatformError(IntegrationError):
    """A sanitized platform request error."""

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class UnsupportedOperation(IntegrationError):
    """An operation not implemented by this adapter."""


@dataclass(frozen=True)
class Provenance:
    """Source identity and retrieval evidence without connection credentials."""

    profile: str
    platform: str
    product_id: Optional[str]
    fqn: Optional[str]
    source_format: str
    retrieved_at: str
    revision: Optional[str] = None


@dataclass
class ProductResult:
    """Retrieved data with provenance and optional validation findings."""

    data: object
    provenance: Provenance
    validation: Optional[ValidationResult] = None
    warnings: Tuple[str, ...] = ()


@dataclass
class ProductPage:
    """A page of native products and an opaque continuation cursor."""

    products: List[object]
    after: Optional[str]
    provenance: Provenance


@dataclass
class ProductSearchPage:
    """A bounded product-search page with platform total and offset state."""

    products: List[Dict[str, object]]
    offset: int
    limit: int
    total: int
    total_relation: str
    next_offset: Optional[int]
    provenance: Provenance
    warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class UpdatedDateChange:
    """A UTC date derived from an OpenMetadata millisecond timestamp."""

    pointer: str
    original_milliseconds: int
    utc_date: str


@dataclass(frozen=True)
class NormalizedOdpsExport:
    """An explicit derived document alongside its unchanged source."""

    original_yaml: str
    normalized_yaml: str
    changes: Tuple[UpdatedDateChange, ...]
    validation: ValidationResult


class _DateStringDumper(yaml.SafeDumper):
    """Quote date-looking strings so YAML parsers preserve their type."""


def _represent_string(dumper: _DateStringDumper, value: str) -> yaml.ScalarNode:
    style = '"' if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_DateStringDumper.add_representer(str, _represent_string)


def normalize_openmetadata_updated_dates(source_yaml: str) -> NormalizedOdpsExport:
    """Convert supported OpenMetadata millisecond updated values to UTC dates."""
    try:
        document = yaml.safe_load(source_yaml)
    except yaml.YAMLError:
        raise IntegrationError("Cannot normalize invalid ODPS YAML") from None
    if not isinstance(document, dict):
        raise IntegrationError("Cannot normalize an ODPS document without a mapping")
    if detect_version(document) not in ("4.1", "4.2"):
        raise IntegrationError(
            "Normalization requires a declared ODPS 4.1 or 4.2 document"
        )
    product = document.get("product")
    details = product.get("details") if isinstance(product, dict) else None
    changes = []
    if isinstance(details, dict):
        for language, detail in details.items():
            if not isinstance(language, str) or not isinstance(detail, dict):
                continue
            value = detail.get("updated")
            if not isinstance(value, int) or isinstance(value, bool):
                continue
            # Reject ambiguous seconds and out-of-range values instead of guessing.
            if value < 100_000_000_000:
                raise IntegrationError(
                    "Numeric updated value is not a supported millisecond timestamp"
                )
            try:
                date = (
                    datetime.fromtimestamp(value / 1000, timezone.utc)
                    .date()
                    .isoformat()
                )
            except (OverflowError, OSError, ValueError):
                raise IntegrationError(
                    "Numeric updated timestamp is outside the supported range"
                ) from None
            detail["updated"] = date
            escaped = language.replace("~", "~0").replace("/", "~1")
            changes.append(
                UpdatedDateChange(
                    "/product/details/" + escaped + "/updated", value, date
                )
            )
    normalized = (
        yaml.dump(
            document, Dumper=_DateStringDumper, sort_keys=False, allow_unicode=True
        )
        if changes
        else source_yaml
    )
    try:
        validation = validate_document(document)
    except (ValueError, TypeError, AttributeError):
        validation = ValidationResult(
            False, "odps", "OpenDataProduct", ["Source is not a valid ODPS document"]
        )
    return NormalizedOdpsExport(source_yaml, normalized, tuple(changes), validation)


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(
        self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


class OpenMetadataAdapter(PlatformAdapter):
    """Expose read operations and reviewed creation for an OpenMetadata connection."""

    def __init__(self, profile: ConnectionProfile):
        if profile.platform != "openmetadata":
            raise IntegrationError("Unsupported adapter")
        super().__init__(profile)
        self._closed = False
        try:
            if profile.verify_tls:
                context = ssl.create_default_context(
                    cafile=profile.ca_bundle or certifi.where()
                )
            else:
                context = ssl._create_unverified_context()
        except (OSError, ssl.SSLError):
            raise IntegrationError("Unable to load TLS configuration") from None
        self._opener = request.build_opener(
            _NoRedirect(), request.HTTPSHandler(context=context)
        )

    def __enter__(self) -> "OpenMetadataAdapter":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        """Close this adapter for further use."""
        self._closed = True

    def capabilities(self) -> Dict[str, object]:
        """Describe adapter implementation separately from deployment and permission."""
        return {
            "metadata_discovery": "supported",
            "list_products": "supported",
            "list_domains": "supported",
            "search_products": "supported",
            "get_native": "supported",
            "odps_export": "unknown",
            "writes": "experimental_create_update_and_permanent_delete",
            "create_odps_4_1": "experimental",
            "create_domain": "experimental",
            "import_odcs_contract": "experimental",
            "delete_product": "experimental_permanent_recursive",
            "update_product": "experimental_native_title_description_and_domain",
            "server_version": "unknown",
            "permissions": "unknown",
        }

    def _get(self, path: str, accept: str = "application/json") -> bytes:
        if self._closed:
            raise IntegrationError("Adapter is closed")
        token = self.profile.token()
        base = self.profile.base_url
        url = base + ("/v1/" if base.endswith("/api") else "/api/v1/") + path
        for attempt in range(3):
            try:
                req = request.Request(
                    url,
                    headers={"Authorization": "Bearer " + token, "Accept": accept},
                    method="GET",
                )
                with self._opener.open(
                    req, timeout=self.profile.timeout_seconds
                ) as response:
                    body = response.read(5 * 1024 * 1024 + 1)
                    if len(body) > 5 * 1024 * 1024:
                        raise PlatformError("Platform response exceeds size limit")
                    return bytes(body)
            except error.HTTPError as exc:
                status = exc.code
                if status in (429, 502, 503, 504) and attempt < 2:
                    delay = _retry_delay(exc.headers.get("Retry-After"), attempt)
                    if delay is not None:
                        exc.close()
                        time.sleep(delay)
                        continue
                exc.close()
                raise PlatformError(
                    "Platform request returned HTTP " + str(status), status
                ) from None
            except (error.URLError, TimeoutError, OSError, ValueError, HTTPException):
                raise PlatformError("Platform request failed or timed out") from None
        raise PlatformError("Platform request failed")

    def _json(self, path: str) -> dict:
        try:
            value = json.loads(self._get(path).decode("utf-8"))
        except (ValueError, UnicodeError):
            raise PlatformError("Platform returned invalid JSON") from None
        if not isinstance(value, dict):
            raise PlatformError("Platform returned an unexpected JSON shape")
        return value

    def _provenance(
        self,
        fmt: str,
        product_id: Optional[str] = None,
        fqn: Optional[str] = None,
        revision: Optional[str] = None,
    ) -> Provenance:
        return Provenance(
            self.profile.name,
            self.profile.platform,
            product_id,
            fqn,
            fmt,
            datetime.now(timezone.utc).isoformat(),
            revision,
        )

    def check_connection(self) -> Dict[str, str]:
        """Check read access without inferring write permissions."""
        self.list_products(limit=1)
        return {
            "status": "connected",
            "read": "listing succeeded",
            "write_permission": "unknown",
            "server_version": "unknown",
        }

    def list_products(
        self, *, limit: int = 100, after: Optional[str] = None
    ) -> ProductPage:
        """Retrieve one page of native product references."""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 1000
        ):
            raise IntegrationError("Page limit must be between 1 and 1000")
        params = {"limit": str(limit)}
        if after is not None:
            if not isinstance(after, str) or len(after) > 4096:
                raise IntegrationError("Invalid pagination cursor")
            params["after"] = after
        result = self._json("dataProducts?" + urlencode(params))
        data, paging = result.get("data"), result.get("paging", {})
        if (
            not isinstance(data, list)
            or any(not isinstance(product, dict) for product in data)
            or not isinstance(paging, dict)
            or (
                paging.get("after") is not None
                and not isinstance(paging.get("after"), str)
            )
        ):
            raise PlatformError("Platform returned an unexpected product page")
        return ProductPage(
            data, paging.get("after"), self._provenance("openmetadata-json")
        )

    def list_products_odpc(
        self, *, page_size: int = 100, max_pages: int = 100, after: Optional[str] = None
    ) -> dict:
        """Return a validated ODPC catalog of OpenMetadata product references."""
        from ._odpc_catalog import list_odpc_catalog

        return list_odpc_catalog(
            self, page_size=page_size, max_pages=max_pages, after=after
        )

    def list_domains(
        self, *, limit: int = 100, after: Optional[str] = None
    ) -> ProductPage:
        """Retrieve one page of available OpenMetadata domains."""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 1000
        ):
            raise IntegrationError("Page limit must be between 1 and 1000")
        params = {"limit": str(limit)}
        if after is not None:
            if not isinstance(after, str) or len(after) > 4096:
                raise IntegrationError("Invalid pagination cursor")
            params["after"] = after
        result = self._json("domains?" + urlencode(params))
        data, paging = result.get("data"), result.get("paging", {})
        if (
            not isinstance(data, list)
            or any(not isinstance(domain, dict) for domain in data)
            or not isinstance(paging, dict)
            or (
                paging.get("after") is not None
                and not isinstance(paging.get("after"), str)
            )
        ):
            raise PlatformError("Platform returned an unexpected domain page")
        return ProductPage(
            data, paging.get("after"), self._provenance("openmetadata-domains")
        )

    def search_products(
        self, query: str, *, offset: int = 0, limit: int = 20
    ) -> ProductSearchPage:
        """Search the OpenMetadata data-product index with native query syntax."""
        if not isinstance(query, str) or not query.strip() or len(query) > 1024:
            raise IntegrationError("Search query must contain 1 to 1024 characters")
        if any(ord(c) < 32 for c in query):
            raise IntegrationError("Search query contains invalid control characters")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise IntegrationError("Search offset must be a nonnegative integer")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            raise IntegrationError("Search limit must be between 1 and 100")
        if offset + limit > 10000:
            raise IntegrationError("Search offset and limit cannot exceed 10000")
        params = {
            "q": query,
            "index": "data_product_search_index",
            "from": str(offset),
            "size": str(limit),
            "deleted": "false",
        }
        response = self._json("search/query?" + urlencode(params))
        shards = response.get("_shards", {})
        if (
            response.get("timed_out") is True
            or response.get("terminated_early") is True
        ):
            raise PlatformError("Platform search returned incomplete results")
        if not isinstance(shards, dict) or shards.get("failed", 0) != 0:
            raise PlatformError("Platform search returned incomplete results")
        hits_object = response.get("hits")
        if not isinstance(hits_object, dict) or not isinstance(
            hits_object.get("hits"), list
        ):
            raise PlatformError("Platform returned an unexpected search response")
        hits = hits_object["hits"]
        if len(hits) > limit:
            raise PlatformError("Platform returned an unexpected search response")
        total_value = hits_object.get("total")
        if isinstance(total_value, dict):
            total, relation = total_value.get("value"), total_value.get("relation")
        else:
            total, relation = total_value, "eq"
        if (
            isinstance(total, bool)
            or not isinstance(total, int)
            or total < 0
            or relation not in ("eq", "gte")
        ):
            raise PlatformError("Platform returned an unexpected search total")
        products: List[Dict[str, object]] = []
        for hit in hits:
            if not isinstance(hit, dict) or not isinstance(hit.get("_source"), dict):
                raise PlatformError(
                    "Platform returned an unexpected product search hit"
                )
            source = hit["_source"]
            identifier = source.get("id") or hit.get("_id")
            if not isinstance(identifier, str) or not identifier:
                raise PlatformError(
                    "Platform returned a product search hit without an ID"
                )
            if source.get("entityType") not in (None, "dataProduct"):
                raise PlatformError("Platform returned a non-product search hit")
            item: Dict[str, object] = {"id": identifier}
            for field in (
                "name",
                "displayName",
                "fullyQualifiedName",
                "description",
                "version",
            ):
                value = source.get(field)
                if (
                    value is not None
                    and isinstance(value, (str, int, float))
                    and not isinstance(value, bool)
                ):
                    item[field] = value
            products.append(item)
        end = offset + len(products)
        has_more = len(products) == limit and (relation == "gte" or end < total)
        next_offset = end if has_more and end + limit <= 10000 else None
        warnings = [
            "Search results depend on the platform index and may lag recent changes."
        ]
        if relation == "gte":
            warnings.append("The reported total is a lower bound.")
        if has_more and next_offset is None:
            warnings.append("The SDK search offset limit was reached.")
        return ProductSearchPage(
            products,
            offset,
            limit,
            total,
            relation,
            next_offset,
            self._provenance("openmetadata-search"),
            tuple(warnings),
        )

    def search_products_odpc(
        self, query: str, *, offset: int = 0, limit: int = 20
    ) -> dict:
        """Return a validated ODPC catalog for one OpenMetadata search page."""
        from ._odpc_catalog import search_odpc_catalog

        return search_odpc_catalog(self, query, offset=offset, limit=limit)

    def find_create_candidates(
        self,
        source_yaml: str,
        *,
        domain: str,
        language: str = "en",
        max_pages: int = 10,
        source_path: Optional[str] = None,
    ) -> Dict[str, object]:
        """Find possible outcomes of an uncertain create without making changes."""
        if (
            isinstance(max_pages, bool)
            or not isinstance(max_pages, int)
            or not 1 <= max_pages <= 100
        ):
            raise IntegrationError("Recovery page limit must be between 1 and 100")
        review = self.review_create(
            source_yaml,
            domain=domain,
            language=language,
            source_path=source_path,
            owners=[],
        )
        if not review.compatible or not review.product_id:
            raise IntegrationError(
                "Recovery requires a compatible ODPS create candidate"
            )
        candidates: List[Dict[str, object]] = []
        cursor = None
        seen = set()
        complete = False
        for _ in range(max_pages):
            page = self.list_products(limit=1000, after=cursor)
            for product in page.products:
                if (
                    not isinstance(product, dict)
                    or product.get("name") != review.product_id
                ):
                    continue
                identifier = product.get("id")
                if not isinstance(identifier, str) or not identifier:
                    raise PlatformError("Recovery candidate has no platform ID")
                raw_domains = product.get("domains", product.get("domain"))
                refs = raw_domains if isinstance(raw_domains, list) else [raw_domains]
                fqns = [
                    ref.get("fullyQualifiedName")
                    for ref in refs
                    if isinstance(ref, dict)
                    and isinstance(ref.get("fullyQualifiedName"), str)
                ]
                domain_match = (domain in fqns) if fqns else None
                candidates.append(
                    {
                        "id": identifier,
                        "name": review.product_id,
                        "fullyQualifiedName": product.get("fullyQualifiedName"),
                        "domain_match": domain_match,
                    }
                )
            cursor = page.after
            if not cursor:
                complete = True
                break
            if cursor in seen:
                raise PlatformError(
                    "Platform repeated a pagination cursor during recovery"
                )
            seen.add(cursor)
        return {
            "product_id": review.product_id,
            "domain": domain,
            "candidates": candidates,
            "complete": complete,
            "warnings": [
                "Candidates are not proof of creation and may include other domains; inspect them before deciding what to do.",
                "Results reflect platform permissions and pagination, not a consistent snapshot.",
            ],
        }

    def get_product(
        self,
        product_id: str,
        *,
        include_extensions: bool = False,
        include_domains: bool = False,
        include_owners_tags: bool = False,
    ) -> ProductResult:
        """Retrieve one native product by platform ID."""
        if not isinstance(product_id, str) or not product_id or len(product_id) > 1024:
            raise IntegrationError("A product ID is required")
        path = "dataProducts/" + quote(product_id, safe="")
        fields = []
        if include_extensions:
            fields.append("extension")
        if include_domains:
            fields.append("domains")
        if include_owners_tags:
            fields.extend(("owners", "tags"))
        if fields:
            path += "?" + urlencode({"fields": ",".join(fields)})
        data = self._json(path)
        revision = data.get("version")
        return ProductResult(
            data,
            self._provenance(
                "openmetadata-json",
                str(data.get("id") or product_id),
                data.get("fullyQualifiedName"),
                str(revision) if revision is not None else None,
            ),
        )

    def discover_context(
        self,
        *,
        product_id: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 20,
    ) -> dict:
        """Collect bounded, read-only candidate metadata for a preparation task."""
        if not product_id and not query:
            raise IntegrationError("Provide a product ID or search query")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            raise IntegrationError("Discovery limit must be between 1 and 100")
        result = {
            "product": None,
            "candidates": [],
            "errors": [],
            "incomplete": True,
            "notes": [
                "Candidates require independent review; no sample rows were retrieved.",
                "Asset and lineage retrieval is bounded; unsupported or inaccessible resources are reported.",
            ],
        }
        if product_id:
            try:
                path = (
                    "dataProducts/"
                    + quote(product_id, safe="")
                    + "?"
                    + urlencode({"fields": "assets,owners,domains,tags"})
                )
                data = self._json(path)
                result["product"] = {
                    k: data[k]
                    for k in (
                        "id",
                        "name",
                        "displayName",
                        "description",
                        "fullyQualifiedName",
                        "owners",
                        "domains",
                        "tags",
                        "assets",
                    )
                    if k in data
                }
                if isinstance(result["product"].get("assets"), list):
                    result["product"]["assets"] = [
                        {
                            k: ref[k]
                            for k in (
                                "id",
                                "type",
                                "name",
                                "displayName",
                                "fullyQualifiedName",
                                "description",
                            )
                            if k in ref
                        }
                        for ref in result["product"]["assets"][:limit]
                        if isinstance(ref, dict)
                    ]
            except PlatformError as exc:
                result["errors"].append(
                    {"resource": "product", "message": str(exc), "status": exc.status}
                )
                result["incomplete"] = True
            if result["product"] is not None:
                try:
                    asset_page = self._json(
                        "dataProducts/"
                        + quote(product_id, safe="")
                        + "/assets?"
                        + urlencode({"limit": limit})
                    )
                    linked = asset_page.get("data")
                    if not isinstance(linked, list) or len(linked) > limit:
                        raise PlatformError(
                            "Platform returned an unexpected product-assets page"
                        )
                    result["product"]["assets"] = [
                        {
                            k: ref[k]
                            for k in (
                                "id",
                                "type",
                                "name",
                                "displayName",
                                "fullyQualifiedName",
                                "description",
                            )
                            if k in ref
                        }
                        for ref in linked
                        if isinstance(ref, dict)
                    ]
                    paging = asset_page.get("paging", {})
                    if isinstance(paging, dict) and (
                        paging.get("after")
                        or (
                            isinstance(paging.get("total"), int)
                            and paging["total"] > len(linked)
                        )
                    ):
                        result["notes"].append(
                            "Product assets are limited to one page."
                        )
                except PlatformError as exc:
                    result["errors"].append(
                        {
                            "resource": "product assets",
                            "message": str(exc),
                            "status": exc.status,
                        }
                    )
                    result["incomplete"] = True
        if query:
            if (
                not isinstance(query, str)
                or not query.strip()
                or len(query) > 1024
                or any(ord(c) < 32 for c in query)
            ):
                raise IntegrationError("Invalid search query")
            try:
                params = {
                    "q": query,
                    "index": "all",
                    "from": "0",
                    "size": str(limit),
                    "deleted": "false",
                }
                data = self._json("search/query?" + urlencode(params))
                hits = data.get("hits", {}).get("hits")
                if not isinstance(hits, list) or len(hits) > limit:
                    raise PlatformError(
                        "Platform returned an unexpected search response"
                    )
                for hit in hits:
                    source = hit.get("_source", {}) if isinstance(hit, dict) else {}
                    if isinstance(source, dict):
                        result["candidates"].append(
                            {
                                k: source[k]
                                for k in (
                                    "id",
                                    "entityType",
                                    "name",
                                    "displayName",
                                    "fullyQualifiedName",
                                    "description",
                                    "domain",
                                    "owners",
                                    "tags",
                                )
                                if k in source
                            }
                        )
                result["incomplete"] = True
                result["notes"].append(
                    "Search is bounded to one page and may be incomplete."
                )
            except PlatformError as exc:
                result["errors"].append(
                    {
                        "resource": "catalog search",
                        "message": str(exc),
                        "status": exc.status,
                    }
                )
                result["incomplete"] = True
        # Linked and searched assets remain candidates until independently reviewed.
        assets = []
        product = result.get("product")
        if isinstance(product, dict) and isinstance(product.get("assets"), list):
            assets.extend(product["assets"])
        assets.extend(result["candidates"])
        result["assets"] = []
        result["lineage"] = []
        result["contracts"] = []
        if len(assets) > limit:
            result["notes"].append(
                "Asset inspection was truncated at the requested limit."
            )
        resource_types = {
            "table": "tables",
            "dashboard": "dashboards",
            "topic": "topics",
            "pipeline": "pipelines",
            "mlmodel": "mlmodels",
            "container": "containers",
        }
        for ref in assets[:limit]:
            if not isinstance(ref, dict):
                continue
            kind = str(ref.get("type") or ref.get("entityType") or "")
            identifier = ref.get("id")
            if kind.lower() in ("dataproduct", "data_product") and isinstance(
                identifier, str
            ):
                note = "Product search matches are candidates; select a product to inspect its linked assets and contract."
                if note not in result["notes"]:
                    result["notes"].append(note)
                continue
            if not isinstance(identifier, str) or kind not in resource_types:
                result["errors"].append(
                    {
                        "resource": "asset",
                        "message": "Unsupported asset type or missing ID",
                    }
                )
                continue
            safe_id = quote(identifier, safe="")
            try:
                data = self._json(
                    resource_types[kind]
                    + "/"
                    + safe_id
                    + "?"
                    + urlencode({"fields": "owners,domains,tags"})
                )
                item = {
                    k: data[k]
                    for k in (
                        "id",
                        "name",
                        "displayName",
                        "fullyQualifiedName",
                        "description",
                        "owners",
                        "domains",
                        "tags",
                    )
                    if k in data
                }
                item["type"] = kind
                if isinstance(data.get("columns"), list):
                    item["columns"] = [
                        {k: c[k] for k in ("name", "dataType", "description") if k in c}
                        for c in data["columns"]
                        if isinstance(c, dict)
                    ][:1000]
                    if len(data["columns"]) > 1000:
                        result["notes"].append("Asset columns were truncated at 1000.")
                result["assets"].append(item)
            except PlatformError as exc:
                result["errors"].append(
                    {
                        "resource": "asset " + identifier,
                        "message": str(exc),
                        "status": exc.status,
                    }
                )
            try:
                lineage = self._json(
                    "lineage/"
                    + quote(kind, safe="")
                    + "/"
                    + safe_id
                    + "?upstreamDepth=1&downstreamDepth=1"
                )

                def lineage_refs(key):
                    values = lineage.get(key, [])
                    if not isinstance(values, list):
                        return []
                    return [
                        {
                            k: entry[k]
                            for k in (
                                "id",
                                "type",
                                "name",
                                "fullyQualifiedName",
                                "fromEntity",
                                "toEntity",
                            )
                            if k in entry
                        }
                        for entry in values[:limit]
                        if isinstance(entry, dict)
                    ]

                result["lineage"].append(
                    {
                        "asset_id": identifier,
                        "nodes": lineage_refs("nodes"),
                        "upstreamEdges": lineage_refs("upstreamEdges"),
                        "downstreamEdges": lineage_refs("downstreamEdges"),
                    }
                )
            except PlatformError as exc:
                result["errors"].append(
                    {
                        "resource": "lineage " + identifier,
                        "message": str(exc),
                        "status": exc.status,
                    }
                )
        if product_id:
            import hashlib

            retrieved_at = datetime.now(timezone.utc).isoformat()
            provenance = {
                "connection": self.profile.name,
                "product_id": product_id,
                "retrieved_at": retrieved_at,
                "platform": "openmetadata",
            }
            max_contract_bytes = 1024 * 1024
            contract = None
            try:
                contract = self.get_contract_for_product(product_id)
                encoded = json.dumps(
                    contract, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
                if len(encoded) > max_contract_bytes:
                    raise IntegrationError(
                        "Product contract exceeds the 1 MiB evidence limit"
                    )
                result["contracts"].append(
                    {
                        "origin": "OpenMetadata product contract",
                        "provenance": dict(provenance, contract_id=contract.get("id")),
                        "validation_status": "not validated by discovery",
                        "content_status": "complete response within limit; platform completeness unknown",
                        "size_bytes": len(encoded),
                        "sha256": hashlib.sha256(encoded).hexdigest(),
                        "data": contract,
                    }
                )
            except (IntegrationError, TypeError, ValueError) as exc:
                message = str(exc)
                if getattr(exc, "status", None) == 404:
                    message = (
                        "No product contract returned by the entity lookup (HTTP 404); "
                        "absence, endpoint support and access cannot be distinguished "
                        "from this response alone"
                    )
                result["errors"].append(
                    {
                        "resource": "product contract",
                        "message": message,
                        "status": getattr(exc, "status", None),
                        "incomplete": True,
                    }
                )
            try:
                if contract is None:
                    raise IntegrationError(
                        "Preserved ODCS source was not checked because the product "
                        "contract lookup did not return a contract"
                    )
                source = self._preserved_contract_source(
                    product_id, contract, max_bytes=max_contract_bytes
                )
                body = source["yaml"]
                size = len(body.encode("utf-8"))
                if size > max_contract_bytes:
                    raise IntegrationError(
                        "Preserved ODCS source exceeds the 1 MiB evidence limit"
                    )
                result["contracts"].append(
                    {
                        "origin": "SDK-preserved ODCS source",
                        "provenance": dict(
                            provenance, contract_id=source["contract_id"]
                        ),
                        "validation_status": "integrity checked only; preserved schema not validated by OpenMetadata",
                        "content_status": "integrity-checked stored source; source completeness unknown",
                        "size_bytes": size,
                        "sha256": source["sha256"],
                        "version": source["version"],
                        "yaml": body,
                    }
                )
            except (IntegrationError, KeyError, TypeError, UnicodeError) as exc:
                result["errors"].append(
                    {
                        "resource": "preserved ODCS source",
                        "message": str(exc),
                        "status": getattr(exc, "status", None),
                        "incomplete": True,
                    }
                )
        result["notes"].append(
            "Stored ODCS source material is not evidence of a natively validated OpenMetadata contract."
        )
        return result

    def export_odps(self, product_id: str) -> ProductResult:
        """Retrieve and locally validate a server-provided ODPS YAML document."""
        if not isinstance(product_id, str) or not product_id or len(product_id) > 1024:
            raise IntegrationError("A product ID is required")
        try:
            body = self._get(
                "dataProducts/" + quote(product_id, safe="") + "/odps/yaml",
                "application/yaml, text/yaml, text/plain",
            ).decode("utf-8")
        except UnicodeError:
            raise PlatformError("Platform returned non-UTF-8 ODPS data") from None
        try:
            data = yaml.safe_load(body)
            result = validate_document(data)
            if result.spec != "odps":
                raise ValueError("Not an ODPS document")
        except (ValueError, TypeError, AttributeError, yaml.YAMLError):
            result = ValidationResult(
                False,
                "odps",
                "OpenDataProduct",
                ["Source is not a valid ODPS document"],
            )
        warnings = ("Native revision could not be retrieved",)
        fqn = None
        revision = None
        try:
            native = self.get_product(product_id)
            fqn = native.provenance.fqn
            revision = native.provenance.revision
            warnings = ("Native metadata and export were retrieved separately",)
        except PlatformError:
            pass
        return ProductResult(
            body,
            self._provenance("odps-yaml", product_id, fqn, revision),
            result,
            warnings,
        )

    def compare_product(
        self, source_yaml: str, *, product_id: str, domain: str, language: str = "en"
    ) -> "ProductComparison":
        """Compare supplied ODPS source with native and exported product metadata."""
        from ._comparison import compare_product_source

        return compare_product_source(
            self, source_yaml, product_id=product_id, domain=domain, language=language
        )

    def review_create(
        self,
        source_yaml: str,
        *,
        domain: str,
        language: str = "en",
        source_path: Optional[str] = None,
        owners: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> "CreateReview":
        """Review creation; linked contracts may require source retrieval."""
        from .create import review_odps_create

        return review_odps_create(
            self,
            source_yaml,
            domain=domain,
            language=language,
            source_path=source_path,
            owners=owners,
            tags=tags,
        )

    def review_contract_import(
        self, source_yaml: str, *, product_id: str, object_name: Optional[str] = None
    ) -> "ContractImportReview":
        """Review an ODCS contract import for a product."""
        from .contracts import review_contract_import

        return review_contract_import(
            self, source_yaml, product_id=product_id, object_name=object_name
        )

    def get_contract_for_product(self, product_id: str) -> dict:
        """Retrieve the platform's effective contract for a data product."""
        from uuid import UUID

        try:
            canonical = str(UUID(product_id))
        except (ValueError, TypeError, AttributeError):
            raise IntegrationError("A valid product UUID is required") from None
        return self._json(
            "dataContracts/entity?"
            + urlencode({"entityId": canonical, "entityType": "dataProduct"})
        )

    def get_preserved_contract_source(
        self, product_id: str, *, max_bytes: Optional[int] = None
    ) -> Dict[str, str]:
        """Retrieve and integrity-check an SDK-preserved ODCS source document."""
        from uuid import UUID

        try:
            product_id = str(UUID(product_id))
        except (ValueError, TypeError, AttributeError):
            raise IntegrationError("A valid product UUID is required") from None
        contract = self.get_contract_for_product(product_id)
        return self._preserved_contract_source(
            product_id, contract, max_bytes=max_bytes
        )

    def _preserved_contract_source(
        self, product_id: str, contract: dict, *, max_bytes: Optional[int] = None
    ) -> Dict[str, str]:
        import hashlib
        from .create import _load_unambiguous_yaml

        contract_id = contract.get("id")
        if not isinstance(contract_id, str) or not contract_id:
            raise IntegrationError("Platform contract has no usable ID")
        native = self._json(
            "dataContracts/"
            + quote(contract_id, safe="")
            + "?fields=entity,odcsPreservedFields"
        )
        entity = native.get("entity")
        if (
            not isinstance(entity, dict)
            or entity.get("id") != product_id
            or entity.get("type") != "dataProduct"
        ):
            raise IntegrationError(
                "Contract is not associated with the requested product"
            )
        preserved = native.get("odcsPreservedFields")
        source = preserved.get("odpsSdkSource") if isinstance(preserved, dict) else None
        if (
            not isinstance(source, dict)
            or source.get("format") != "odcs-yaml-v1"
            or not isinstance(source.get("yaml"), str)
        ):
            raise IntegrationError("No SDK-preserved ODCS source is available")
        body = source["yaml"]
        if max_bytes is not None and len(body.encode("utf-8")) > max_bytes:
            raise IntegrationError(
                "Preserved ODCS source exceeds the evidence size limit"
            )
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        try:
            document = _load_unambiguous_yaml(body)
        except IntegrationError:
            raise IntegrationError(
                "Preserved ODCS source failed integrity checks"
            ) from None
        if (
            source.get("sha256") != digest
            or not isinstance(document, dict)
            or not isinstance(document.get("version"), str)
            or source.get("version") != document["version"]
        ):
            raise IntegrationError("Preserved ODCS source failed integrity checks")
        return {
            "product_id": product_id,
            "contract_id": contract_id,
            "version": document["version"],
            "sha256": digest,
            "yaml": body,
        }

    def import_contract(
        self,
        source_yaml: str,
        *,
        product_id: str,
        reviewed_sha256: str,
        object_name: Optional[str] = None,
    ) -> "ContractImportResult":
        """Import an explicitly reviewed ODCS contract once."""
        from .contracts import execute_contract_import

        return execute_contract_import(
            self,
            source_yaml,
            product_id=product_id,
            object_name=object_name,
            reviewed_sha256=reviewed_sha256,
        )

    def review_domain_create(
        self,
        *,
        name: str,
        description: str,
        domain_type: str,
        display_name: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> "DomainCreateReview":
        """Review a new domain without contacting the platform."""
        from .domains import review_domain_create

        return review_domain_create(
            self,
            name=name,
            description=description,
            domain_type=domain_type,
            display_name=display_name,
            parent=parent,
        )

    def create_domain(
        self,
        *,
        name: str,
        description: str,
        domain_type: str,
        reviewed_sha256: str,
        display_name: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> "DomainCreateResult":
        """Create a reviewed domain once and verify the result."""
        from .domains import execute_domain_create

        return execute_domain_create(
            self,
            name=name,
            description=description,
            domain_type=domain_type,
            reviewed_sha256=reviewed_sha256,
            display_name=display_name,
            parent=parent,
        )

    def create_product(
        self,
        source_yaml: str,
        *,
        domain: str,
        language: str = "en",
        reviewed_sha256: str,
        source_path: Optional[str] = None,
        owners: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> "CreateResult":
        """Create the previously reviewed ODPS candidate once."""
        from .create import execute_odps_create

        return execute_odps_create(
            self,
            source_yaml,
            domain=domain,
            language=language,
            reviewed_sha256=reviewed_sha256,
            source_path=source_path,
            owners=owners,
            tags=tags,
        )

    def review_delete(self, product_id: str) -> "DeleteReview":
        """Review the target and consequences of permanent deletion."""
        from .delete import review_product_delete

        return review_product_delete(self, product_id)

    def delete_product(
        self, product_id: str, *, reviewed_sha256: str, confirm_permanent: bool
    ) -> "DeleteResult":
        """Permanently delete one reviewed product and inspect its absence."""
        from .delete import execute_product_delete

        return execute_product_delete(
            self,
            product_id,
            reviewed_sha256=reviewed_sha256,
            confirm_permanent=confirm_permanent,
        )

    def review_update(
        self,
        product_id: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        owners: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        source_yaml: Optional[str] = None,
    ) -> "UpdateReview":
        """Review native title, description, or domain changes against the product."""
        from .update import review_product_update

        return review_product_update(
            self,
            product_id,
            title=title,
            description=description,
            domain=domain,
            owners=owners,
            tags=tags,
            source_yaml=source_yaml,
        )

    def update_product(
        self,
        product_id: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        owners: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        source_yaml: Optional[str] = None,
        reviewed_sha256: str,
    ) -> "UpdateResult":
        """Apply reviewed changes with a revision precondition."""
        from .update import execute_product_update

        return execute_product_update(
            self,
            product_id,
            title=title,
            description=description,
            domain=domain,
            owners=owners,
            tags=tags,
            source_yaml=source_yaml,
            reviewed_sha256=reviewed_sha256,
        )


def _retry_delay(value: Optional[str], attempt: int) -> Optional[float]:
    if value:
        try:
            delay = max(0.0, float(value))
            return delay if delay <= 10 else None
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                delay = max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
                return delay if delay <= 10 else None
            except (ValueError, TypeError, OverflowError):
                pass
    return float(2**attempt)
