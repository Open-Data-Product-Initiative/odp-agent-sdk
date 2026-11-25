"""Reviewed ODCS contract imports for OpenMetadata data products."""

from dataclasses import asdict, dataclass
import hashlib
from http.client import HTTPException
import json
from typing import Dict, Optional, Tuple, TYPE_CHECKING
from urllib import error, request
from urllib.parse import quote, urlencode
from uuid import UUID

import yaml

from .config import IntegrationError
from .create import _load_unambiguous_yaml

if TYPE_CHECKING:
    from .openmetadata import OpenMetadataAdapter


class UnknownContractImportOutcome(IntegrationError):
    """An import may have reached the platform and must not be retried blindly."""


@dataclass(frozen=True)
class ContractImportReview:
    """Target, platform validation and exact source-bound import review."""

    profile: str
    product_id: str
    product_revision: str
    contract_name: Optional[str]
    object_name: Optional[str]
    validation: Dict[str, object]
    review_sha256: str
    write_enabled: bool
    executable: bool
    warnings: tuple
    source_validation: Optional[Dict[str, object]] = None
    source_version: Optional[str] = None
    schema_preserved: bool = False

    def to_dict(self) -> Dict[str, object]:
        """Return review details without the source document or credential."""
        return asdict(self)


@dataclass(frozen=True)
class ContractImportResult:
    """Imported contract identity and target association verification."""

    status: str
    product_id: str
    contract_id: str
    review_sha256: str
    comparison: Dict[str, str]
    warnings: tuple
    source_version: Optional[str] = None
    source_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Return sanitized import result."""
        return asdict(self)


def _post_yaml(
    adapter: "OpenMetadataAdapter", path: str, source: str, *, write: bool
) -> dict:
    """Send one bounded YAML request and sanitize transport failures."""
    from .openmetadata import PlatformError

    base = adapter.profile.base_url
    url = base + ("/v1/" if base.endswith("/api") else "/api/v1/") + path
    req = request.Request(
        url,
        data=source.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": "Bearer " + adapter.profile.token(),
            "Content-Type": "application/yaml",
            "Accept": "application/json",
        },
    )
    try:
        with adapter._opener.open(
            req, timeout=adapter.profile.timeout_seconds
        ) as response:
            if response.status not in (200, 201):
                raise (
                    UnknownContractImportOutcome(
                        "Contract import was not confirmed; inspect before retrying"
                    )
                    if write
                    else PlatformError("Platform contract validation was not confirmed")
                )
            raw = response.read(5 * 1024 * 1024 + 1)
            if len(raw) > 5 * 1024 * 1024:
                raise (
                    UnknownContractImportOutcome(
                        "Contract import response exceeded limit; inspect before retrying"
                    )
                    if write
                    else PlatformError(
                        "Platform contract validation response exceeds limit"
                    )
                )
            try:
                result = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeError):
                raise (
                    UnknownContractImportOutcome(
                        "Contract import response was unreadable; inspect before retrying"
                    )
                    if write
                    else PlatformError("Platform returned invalid contract validation")
                )
            if not isinstance(result, dict):
                raise (
                    UnknownContractImportOutcome(
                        "Contract import response was unexpected; inspect before retrying"
                    )
                    if write
                    else PlatformError(
                        "Platform returned unexpected contract validation"
                    )
                )
            return result
    except error.HTTPError as exc:
        status = exc.code
        exc.close()
        if write and (status == 408 or status >= 500 or 300 <= status < 400):
            raise UnknownContractImportOutcome(
                "Contract import outcome is unknown; inspect before retrying"
            ) from None
        raise PlatformError(
            "Platform contract request returned HTTP " + str(status), status
        ) from None
    except (error.URLError, TimeoutError, OSError, HTTPException):
        if write:
            raise UnknownContractImportOutcome(
                "Contract import outcome is unknown; inspect before retrying"
            ) from None
        raise PlatformError(
            "Platform contract validation failed or timed out"
        ) from None


def _product_and_absence(adapter: "OpenMetadataAdapter", product_id: str) -> dict:
    from .openmetadata import PlatformError

    product = adapter.get_product(product_id)
    if not isinstance(product.data, dict) or product.data.get("id") != product_id:
        raise IntegrationError("The platform returned an unexpected product identity")
    try:
        adapter._json(
            "dataContracts/entity?"
            + urlencode({"entityId": product_id, "entityType": "dataProduct"})
        )
    except PlatformError as exc:
        if exc.status != 404:
            raise
    else:
        raise IntegrationError("Product already has a data contract; import is blocked")
    revision = product.data.get("version")
    if isinstance(revision, bool) or not isinstance(revision, (int, float)):
        raise IntegrationError(
            "Product revision is unavailable; contract import is blocked"
        )
    return product.data


def review_contract_import(
    adapter: "OpenMetadataAdapter",
    source_yaml: str,
    *,
    product_id: str,
    object_name: Optional[str] = None,
) -> ContractImportReview:
    """Review an ODCS 3.1 import and ask OpenMetadata to validate without writing."""
    if adapter._closed:
        raise IntegrationError("Adapter is closed")
    try:
        canonical = str(UUID(product_id))
    except (TypeError, ValueError, AttributeError):
        raise IntegrationError("A valid product UUID is required") from None
    if (
        not isinstance(source_yaml, str)
        or not source_yaml.strip()
        or len(source_yaml.encode("utf-8")) > 1024 * 1024
    ):
        raise IntegrationError("ODCS source is missing or too large")
    try:
        document = _load_unambiguous_yaml(source_yaml)
    except IntegrationError:
        raise IntegrationError(
            "ODCS YAML is invalid, ambiguous or exceeds nesting limits"
        ) from None
    if (
        not isinstance(document, dict)
        or document.get("kind") != "DataContract"
        or document.get("apiVersion") not in ("v3.1.0", "3.1.0")
    ):
        raise IntegrationError("Only ODCS 3.1.0 DataContract documents are supported")
    if not isinstance(document.get("version"), str) or not document["version"].strip():
        raise IntegrationError("ODCS contract version must be a nonempty string")
    if object_name is not None and (
        not isinstance(object_name, str)
        or not object_name.strip()
        or len(object_name) > 1024
    ):
        raise IntegrationError("Schema object name must be a nonempty string")
    schema = document.get("schema")
    if object_name is not None and (
        not isinstance(schema, list)
        or sum(
            isinstance(item, dict) and item.get("name") == object_name
            for item in schema
        )
        != 1
    ):
        raise IntegrationError(
            "Schema object name must identify exactly one source object"
        )
    if adapter._json("system/version").get("version") != "2.1.0":
        raise IntegrationError("ODCS import is supported only for OpenMetadata 2.1.0")
    product = _product_and_absence(adapter, canonical)
    params = {
        "entityId": canonical,
        "entityType": "dataProduct",
        "createTestCases": "false",
    }
    if object_name is not None:
        params["objectName"] = object_name
    source_validation = _post_yaml(
        adapter,
        "dataContracts/odcs/validate/yaml?" + urlencode(params),
        source_yaml,
        write=False,
    )
    projection = dict(document)
    has_schema = bool(schema)
    if has_schema:
        projection.pop("schema", None)
        projection_params = {
            "entityId": canonical,
            "entityType": "dataProduct",
            "createTestCases": "false",
        }
        validation = _post_yaml(
            adapter,
            "dataContracts/odcs/validate/yaml?" + urlencode(projection_params),
            yaml.safe_dump(projection, sort_keys=False, allow_unicode=True),
            write=False,
        )
    else:
        validation = source_validation
    source_report = source_validation.get("odcsImportReport")
    if (
        not isinstance(source_validation.get("valid"), bool)
        or not isinstance(source_report, dict)
        or not isinstance(source_report.get("canImport"), bool)
    ):
        raise IntegrationError(
            "Platform returned an incomplete ODCS source validation report"
        )
    report = validation.get("odcsImportReport")
    if (
        not isinstance(validation.get("valid"), bool)
        or not isinstance(report, dict)
        or not isinstance(report.get("canImport"), bool)
    ):
        raise IntegrationError(
            "Platform returned an incomplete ODCS import validation report"
        )
    fingerprint = {
        "source": source_yaml,
        "profile": adapter.profile.name,
        "base_url": adapter.profile.base_url,
        "product": product,
        "object_name": object_name,
        "server_version": "2.1.0",
    }
    digest = hashlib.sha256(
        json.dumps(
            fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    valid = validation["valid"] is True and report["canImport"] is True
    if has_schema and source_validation["valid"] is not True:
        issues = source_report.get("issues")
        if not isinstance(issues, list):
            valid = False
        else:
            blocking = [
                item
                for item in issues
                if isinstance(item, dict) and item.get("severity") == "blocking"
            ]
            valid = (
                valid
                and bool(blocking)
                and all(
                    "Schema validation is not supported for dataProduct entities"
                    in str(item.get("message", ""))
                    for item in blocking
                )
            )
    warnings: Tuple[str, ...] = (
        "Only basic ODCS metadata checks and the platform validation are performed; no bundled ODCS schema validation is claimed.",
        "The server may omit or transform source fields; retain the source and inspect its import report.",
        "A fresh target and existing-contract check is performed before import, but the server does not provide an atomic absence precondition.",
        "The complete source YAML, including its contract version, will be stored in platform contract metadata and can be retrieved through the SDK.",
    )
    if has_schema:
        warnings += (
            "The native contract excludes the ODCS schema: OpenMetadata does not validate product schemas. The complete source is preserved separately; native ODCS export does not restore it.",
        )
    name = document.get("name")
    return ContractImportReview(
        adapter.profile.name,
        canonical,
        str(product["version"]),
        name if isinstance(name, str) else None,
        object_name,
        validation,
        digest,
        not adapter.profile.read_only,
        valid and not adapter.profile.read_only,
        warnings,
        source_validation,
        str(document.get("version")) if document.get("version") is not None else None,
        has_schema,
    )


def execute_contract_import(
    adapter: "OpenMetadataAdapter",
    source_yaml: str,
    *,
    product_id: str,
    object_name: Optional[str],
    reviewed_sha256: str,
) -> ContractImportResult:
    """Import a reviewed contract once and verify its product association."""
    adapter.require_write_access()
    if not reviewed_sha256:
        raise IntegrationError("Contract import requires a review digest")
    review = review_contract_import(
        adapter, source_yaml, product_id=product_id, object_name=object_name
    )
    if not review.executable:
        raise IntegrationError("Contract import is blocked by platform validation")
    if review.review_sha256 != reviewed_sha256:
        raise IntegrationError(
            "Contract, target or destination changed since review; review again"
        )
    params = {
        "entityId": review.product_id,
        "entityType": "dataProduct",
        "createTestCases": "false",
    }
    if object_name is not None and not review.schema_preserved:
        params["objectName"] = object_name
    projection = _load_unambiguous_yaml(source_yaml)
    if not isinstance(projection, dict):
        raise IntegrationError("ODCS source is not a mapping")
    if review.schema_preserved:
        projection.pop("schema", None)
        import_source = yaml.safe_dump(projection, sort_keys=False, allow_unicode=True)
    else:
        import_source = source_yaml
    payload = _post_yaml(
        adapter,
        "dataContracts/odcs/yaml?" + urlencode(params),
        import_source,
        write=True,
    )
    try:
        contract_id = str(UUID(payload["id"]))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise UnknownContractImportOutcome(
            "Contract import returned no usable ID; inspect before retrying"
        ) from None
    warnings = list(review.warnings)
    digest = hashlib.sha256(source_yaml.encode("utf-8")).hexdigest()
    try:
        path = (
            "dataContracts/"
            + quote(contract_id, safe="")
            + "?fields=entity,odcsPreservedFields"
        )
        native = adapter._json(path)
        preserved = native.get("odcsPreservedFields")
        if preserved is None:
            preserved = {}
        if not isinstance(preserved, dict) or "odpsSdkSource" in preserved:
            raise IntegrationError(
                "Contract preservation metadata is unavailable or already occupied"
            )
        revision = native.get("version")
        if isinstance(revision, bool) or not isinstance(revision, (int, float)):
            raise IntegrationError(
                "Contract revision is unavailable; source preservation is blocked"
            )
        saved = dict(preserved)
        saved["odpsSdkSource"] = {
            "format": "odcs-yaml-v1",
            "version": review.source_version,
            "sha256": digest,
            "yaml": source_yaml,
        }
        base = adapter.profile.base_url
        url = (
            base
            + ("/v1/" if base.endswith("/api") else "/api/v1/")
            + "dataContracts/"
            + quote(contract_id, safe="")
        )
        patch = request.Request(
            url,
            data=json.dumps(
                [{"op": "add", "path": "/odcsPreservedFields", "value": saved}],
                ensure_ascii=False,
            ).encode("utf-8"),
            method="PATCH",
            headers={
                "Authorization": "Bearer " + adapter.profile.token(),
                "Content-Type": "application/json-patch+json",
                "Accept": "application/json",
                "If-Match": 'W/"' + str(revision) + '"',
            },
        )
        try:
            with adapter._opener.open(
                patch, timeout=adapter.profile.timeout_seconds
            ) as response:
                if response.status not in (200, 204):
                    raise UnknownContractImportOutcome(
                        "Contract source preservation outcome is unknown; inspect before retrying"
                    )
        except error.HTTPError as exc:
            http_status = exc.code
            exc.close()
            if http_status == 408 or http_status >= 500 or 300 <= http_status < 400:
                raise UnknownContractImportOutcome(
                    "Contract source preservation outcome is unknown; inspect before retrying"
                ) from None
            raise IntegrationError(
                "Contract was created but source preservation failed (HTTP "
                + str(http_status)
                + ")"
            ) from None
        except (error.URLError, TimeoutError, OSError, HTTPException):
            raise UnknownContractImportOutcome(
                "Contract source preservation outcome is unknown; inspect before retrying"
            ) from None
        native = adapter._json(path)
        effective = adapter._json(
            "dataContracts/entity?"
            + urlencode({"entityId": review.product_id, "entityType": "dataProduct"})
        )
        entity = native.get("entity")
        stored_fields = native.get("odcsPreservedFields")
        stored = (
            stored_fields.get("odpsSdkSource")
            if isinstance(stored_fields, dict)
            else None
        )
        comparison = {
            "contract_id": (
                "matched" if native.get("id") == contract_id else "different_or_missing"
            ),
            "product": (
                "matched"
                if isinstance(entity, dict)
                and entity.get("id") == review.product_id
                and entity.get("type") == "dataProduct"
                else "different_or_missing"
            ),
            "association": (
                "matched"
                if effective.get("id") == contract_id
                else "different_or_missing"
            ),
            "source": (
                "matched"
                if isinstance(stored, dict)
                and stored.get("yaml") == source_yaml
                and stored.get("sha256") == digest
                and stored.get("version") == review.source_version
                else "different_or_missing"
            ),
        }
        status = (
            "created"
            if all(value == "matched" for value in comparison.values())
            else "created_with_mismatches"
        )
    except UnknownContractImportOutcome:
        status, comparison = "created_preservation_unknown", {"source": "unverified"}
        warnings.append(
            "Contract exists but source preservation outcome is unknown; inspect before retrying"
        )
    except IntegrationError:
        status, comparison = "created_unverified", {"source": "unverified"}
        warnings.append(
            "Contract was imported but source preservation or readback failed; inspect before retrying"
        )
    return ContractImportResult(
        status,
        review.product_id,
        contract_id,
        review.review_sha256,
        comparison,
        tuple(warnings),
        review.source_version,
        digest,
    )
