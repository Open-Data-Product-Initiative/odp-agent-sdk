"""Review and execute a restricted OpenMetadata ODPS create operation."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.client import HTTPException
import hashlib
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING, cast
from urllib import error, request
from urllib.parse import urlencode
from urllib.parse import urlparse, urlsplit

import yaml

from ..agent import validate_document
from ..odps.versions import detect_version, normalize_version
from ..results import ValidationResult
from .config import IntegrationError

if TYPE_CHECKING:
    from .openmetadata import OpenMetadataAdapter


class UnknownCreateOutcome(IntegrationError):
    """A create may have reached the server; inspect the target before retrying."""


class _UnambiguousLoader(yaml.SafeLoader):
    """Reject YAML mappings whose interpretation depends on key ordering."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in result:
                    raise IntegrationError("ODPS YAML contains duplicate mapping keys")
                result[key] = self.construct_object(value_node, deep=deep)
            except TypeError:
                raise IntegrationError(
                    "ODPS YAML contains an invalid mapping key"
                ) from None
        return result


def _load_unambiguous_yaml(source: str) -> object:
    """Reject aliases, excessive nesting and duplicate keys before platform writes."""
    depth = 0
    try:
        for event in yaml.parse(source, Loader=yaml.SafeLoader):
            if isinstance(event, yaml.AliasEvent):
                raise IntegrationError(
                    "ODPS YAML aliases are not supported for platform creation"
                )
            if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
                depth += 1
                if depth > 64:
                    raise IntegrationError("ODPS YAML exceeds the nesting limit")
            elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
                depth -= 1
        return yaml.load(source, Loader=_UnambiguousLoader)
    except (yaml.YAMLError, RecursionError):
        raise IntegrationError("Source is not valid ODPS YAML") from None


@dataclass(frozen=True)
class CreateReview:
    """Locally computed create review bound to its target and exact source."""

    profile: str
    domain: str
    language: str
    source_version: Optional[str]
    product_id: Optional[str]
    product_name: Optional[str]
    validation: ValidationResult
    field_mapping: Dict[str, str]
    unsupported_fields: Tuple[str, ...]
    warnings: Tuple[str, ...]
    review_sha256: str
    compatible: bool
    write_enabled: bool
    executable: bool
    contract_import: Optional[Dict[str, object]] = None
    assignments: Optional[Dict[str, List[Dict[str, str]]]] = None

    def to_dict(self) -> Dict[str, object]:
        """Return review details without source document or credentials."""
        return asdict(self)


@dataclass(frozen=True)
class CreateResult:
    """Creation outcome and comparison of returned supported fields."""

    status: str
    profile: str
    domain: str
    product_id: str
    fqn: Optional[str]
    review_sha256: str
    created_at: str
    field_mapping: Dict[str, str]
    unsupported_fields: Tuple[str, ...]
    comparison: Dict[str, str]
    warnings: Tuple[str, ...]
    contract_import: Optional[Dict[str, object]] = None
    assignments: Optional[Dict[str, object]] = None

    def to_dict(self) -> Dict[str, object]:
        """Return the sanitized creation result."""
        return asdict(self)


def _resolve_product_contract(
    document: object, source_path: Optional[str]
) -> Optional[str]:
    """Resolve one inline or linked ODCS 3.1 contract from an ODPS 4.1 product."""
    product = document.get("product") if isinstance(document, dict) else None
    contract = product.get("contract") if isinstance(product, dict) else None
    if contract is None:
        return None
    if not isinstance(contract, dict) or not contract:
        raise IntegrationError("Product contract is missing or invalid")
    if contract.get("type") not in (None, "ODCS"):
        raise IntegrationError("Only ODCS contracts can be imported with a product")
    inline = contract.get("spec")
    data: object
    links = [contract[key] for key in ("contractURL", "$ref") if key in contract]
    if (inline is not None and links) or len(links) > 1:
        raise IntegrationError(
            "Product contract must specify exactly one inline or linked source"
        )
    if inline is not None:
        if not isinstance(inline, dict):
            raise IntegrationError("Inline product contract must be a mapping")
        data = inline
        raw_source = None
    elif len(links) == 1 and isinstance(links[0], str) and links[0].strip():
        from ..contracts.loader import (
            _file_uri_path,
            _safe_http_uri,
            _safe_source_location,
        )

        location = links[0]
        parsed = urlsplit(location)
        if not parsed.scheme and not Path(location).is_absolute():
            if not source_path:
                raise IntegrationError(
                    "Relative contract links require the ODPS source file path"
                )
            location = str(Path(source_path).resolve().parent / location)
        try:
            parsed = urlsplit(location)
            if parsed.scheme in ("http", "https"):
                import ssl
                import certifi
                from .openmetadata import _NoRedirect

                _safe_http_uri(location)
                opener = request.build_opener(
                    _NoRedirect(),
                    request.HTTPSHandler(
                        context=ssl.create_default_context(cafile=certifi.where())
                    ),
                )
                with opener.open(
                    request.Request(
                        location,
                        headers={
                            "Accept": "application/yaml, text/yaml, application/json"
                        },
                    ),
                    timeout=10,
                ) as response:
                    raw = response.read(1024 * 1024 + 1)
            elif parsed.scheme in ("", "file"):
                _safe_source_location(location)
                path = (
                    _file_uri_path(urlparse(location))
                    if parsed.scheme == "file"
                    else Path(location)
                )
                with path.open("rb") as handle:
                    raw = handle.read(1024 * 1024 + 1)
            else:
                raise ValueError("Unsupported contract URI")
            if len(raw) > 1024 * 1024:
                raise ValueError("Contract exceeds source limit")
            raw_source = raw.decode("utf-8")
            data = _load_unambiguous_yaml(raw_source)
        except (OSError, UnicodeError, ValueError, TypeError, IntegrationError):
            raise IntegrationError(
                "Cannot resolve the linked product contract"
            ) from None
    else:
        raise IntegrationError("Product contract has no resolvable inline spec or link")
    if (
        not isinstance(data, dict)
        or data.get("kind") != "DataContract"
        or data.get("apiVersion")
        not in (
            "v3.1.0",
            "3.1.0",
        )
    ):
        raise IntegrationError("Product contract must be an ODCS 3.1.0 DataContract")
    if not isinstance(data.get("version"), str) or not data["version"].strip():
        raise IntegrationError("ODCS contract version must be a nonempty string")
    source = (
        raw_source
        if raw_source is not None
        else yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    )
    if len(source.encode("utf-8")) > 1024 * 1024:
        raise IntegrationError("ODCS contract source exceeds the 1 MiB limit")
    return source


def review_odps_create(
    adapter: "OpenMetadataAdapter",
    source_yaml: str,
    *,
    domain: str,
    language: str = "en",
    source_path: Optional[str] = None,
    owners: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> CreateReview:
    """Review ODPS creation; linked contracts may require source retrieval."""
    if (
        not isinstance(domain, str)
        or not domain.strip()
        or domain != domain.strip()
        or len(domain) > 1024
    ):
        raise IntegrationError("An explicit domain FQN is required")
    if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2}", language):
        raise IntegrationError("Language must be an ISO 639-1 code")
    if (
        not isinstance(source_yaml, str)
        or len(source_yaml.encode("utf-8")) > 5 * 1024 * 1024
    ):
        raise IntegrationError("ODPS source is missing or too large")
    document = _load_unambiguous_yaml(source_yaml)
    version = detect_version(document) if isinstance(document, dict) else None
    declared_version = (
        normalize_version(document.get("version"))
        if isinstance(document, dict)
        else None
    )
    compatible_version = declared_version == "4.1" and version == "4.1"
    contract_source = (
        _resolve_product_contract(document, source_path) if compatible_version else None
    )
    try:
        if not isinstance(document, dict):
            raise ValueError("Unsupported document")
        validation = validate_document(document)
        if validation.spec != "odps":
            raise ValueError("Unsupported document")
    except (ValueError, TypeError, AttributeError):
        validation = ValidationResult(
            False, "odps", "OpenDataProduct", ["Source is not a valid ODPS document"]
        )
    product = document.get("product") if isinstance(document, dict) else None
    product = product if isinstance(product, dict) else {}
    details = product.get("details")
    details = details if isinstance(details, dict) else {}
    selected = details.get(language)
    selected = selected if isinstance(selected, dict) else {}
    product_id = selected.get("productID")
    product_name = selected.get("name")
    product_id = product_id if isinstance(product_id, str) else None
    product_name = product_name if isinstance(product_name, str) else None
    issues: List[str] = []
    if not compatible_version:
        issues.append(
            "Creation requires an explicitly declared ODPS 4.1 document with a matching schema. Generate a new draft with --odps-version 4.1; version conversion is not available."
        )
    if language not in details:
        issues.append("Requested language is missing; server fallback is not allowed")
    if (
        not product_id
        or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", product_id)
        or re.sub(r"_+", "_", product_id).strip("_") != product_id
    ):
        issues.append(
            "Product ID must already be a 1–64 character OpenMetadata-safe identifier"
        )
    unsupported: List[str] = []
    if isinstance(document, dict):
        unsupported.extend(
            "/" + str(key)
            for key in document
            if key not in ("schema", "version", "product")
        )
    for key in product:
        if key not in ("details",) and not (
            key == "contract" and contract_source is not None
        ):
            unsupported.append("/product/" + str(key))
    mapped = {
        "name",
        "productID",
        "description",
        "valueProposition",
        "type",
        "visibility",
        "portfolioPriority",
        "tags",
    }
    for lang, block in details.items():
        if lang != language:
            unsupported.append("/product/details/" + str(lang))
        elif isinstance(block, dict):
            for key in block:
                if key not in mapped:
                    unsupported.append("/product/details/" + str(lang) + "/" + str(key))
    warnings = [
        "OpenMetadata import does not carry ODPS lifecycle status; the platform controls lifecycle.",
        "Only selected native metadata is imported; unsupported fields are not retained by OpenMetadata.",
        "The server's create endpoint and field mapping must be verified on the target deployment.",
        "The server can normalize fields and resolves tags against its own catalog; review the retained source after creation.",
        "After creation supported fields are compared; fields without a verified mapping require separate review.",
    ] + issues
    if adapter.profile.read_only:
        warnings.append(
            "This profile is read-only and cannot execute the create request"
        )
    if contract_source is not None:
        warnings.append(
            "The contract will be imported separately after product creation; platform validation is only possible after the product exists, and a failure leaves the product in place."
        )
        warnings.append(
            "The complete ODCS source and its version are stored in contract metadata. OpenMetadata does not apply the product contract schema natively or reproduce this source through its native ODCS export."
        )
    if selected.get("description") and selected.get("valueProposition"):
        unsupported.append("/product/details/" + language + "/valueProposition")
    mapping_names = {
        "name": "displayName",
        "productID": "name",
        "description": "description",
        "valueProposition": "description (fallback)",
        "type": "dataProductType",
        "visibility": "visibility",
        "portfolioPriority": "portfolioPriority",
        "tags": "tags (resolved by the server)",
    }
    field_mapping = {
        "/product/details/" + language + "/" + key: target
        for key, target in mapping_names.items()
        if key in selected
        and not (key == "valueProposition" and selected.get("description"))
    }
    effective_owners = ["current"] if owners is None else owners
    assignments: Optional[Dict[str, List[Dict[str, str]]]] = None
    if (effective_owners or tags) and validation.valid and not issues:
        from .update import resolve_owner, resolve_tag

        assignments = {
            "owners": [resolve_owner(adapter, owner) for owner in effective_owners],
            "tags": [resolve_tag(adapter, tag) for tag in tags or []],
        }
        warnings.append(
            "Owners and tags are assigned after creation in a separate non-atomic update; the product remains if that step fails."
        )
    fingerprint = json.dumps(
        {
            "source": source_yaml,
            "domain": domain,
            "language": language,
            "connection": adapter.profile.name,
            "base_url": adapter.profile.base_url,
            "resolved_contract": contract_source,
            "assignment_names": (
                {"owners": effective_owners, "tags": tags} if assignments else None
            ),
            "assignments": assignments,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return CreateReview(
        adapter.profile.name,
        domain,
        language,
        version,
        product_id,
        product_name,
        validation,
        field_mapping,
        tuple(unsupported),
        tuple(warnings),
        digest,
        validation.valid and not issues,
        not adapter.profile.read_only,
        validation.valid and not issues and not adapter.profile.read_only,
        (
            {
                "planned": True,
                "name": yaml.safe_load(contract_source).get("name"),
                "odcs_version": yaml.safe_load(contract_source).get("apiVersion"),
                "contract_version": yaml.safe_load(contract_source).get("version"),
                "schema_preserved_in_source_only": bool(
                    yaml.safe_load(contract_source).get("schema")
                ),
                "source_sha256": hashlib.sha256(
                    contract_source.encode("utf-8")
                ).hexdigest(),
                "platform_validation": "after_product_creation",
            }
            if contract_source is not None
            else None
        ),
        assignments,
    )


def execute_odps_create(
    adapter: "OpenMetadataAdapter",
    source_yaml: str,
    *,
    domain: str,
    language: str,
    reviewed_sha256: str,
    source_path: Optional[str] = None,
    owners: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> CreateResult:
    """Create once after review, then read back supported fields when possible."""
    from .openmetadata import PlatformError

    adapter.require_write_access()
    effective_owners = ["current"] if owners is None else owners
    if adapter._closed:
        raise IntegrationError("Adapter is closed")
    review = review_odps_create(
        adapter,
        source_yaml,
        domain=domain,
        language=language,
        source_path=source_path,
        owners=owners,
        tags=tags,
    )
    if not review.executable:
        for warning in review.warnings:
            if warning.startswith("Creation requires an explicitly declared ODPS 4.1"):
                raise IntegrationError(warning)
        raise IntegrationError(
            "Create blocked by local validation or compatibility findings"
        )
    if not reviewed_sha256 or reviewed_sha256 != review.review_sha256:
        raise IntegrationError(
            "Review digest does not match the candidate and destination"
        )
    version = adapter._json("system/version").get("version")
    if version != "2.1.0":
        raise IntegrationError(
            "ODPS create is only supported for the reviewed OpenMetadata 2.1.0 API"
        )
    token = adapter.profile.token()
    base = adapter.profile.base_url
    url = (
        base
        + ("/v1/" if base.endswith("/api") else "/api/v1/")
        + "dataProducts/odps/yaml?"
        + urlencode({"domain": domain, "languageCode": language})
    )
    req = request.Request(
        url,
        data=source_yaml.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/yaml",
            "Accept": "application/json",
        },
    )
    try:
        with adapter._opener.open(
            req, timeout=adapter.profile.timeout_seconds
        ) as response:
            if response.status not in (200, 201):
                raise UnknownCreateOutcome(
                    "Create was not confirmed as complete; inspect destination before retrying"
                )
            raw = response.read(5 * 1024 * 1024 + 1)
            if len(raw) > 5 * 1024 * 1024:
                raise UnknownCreateOutcome(
                    "Create response exceeded limit; inspect destination before retrying"
                )
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeError, ValueError):
                raise UnknownCreateOutcome(
                    "Create response was unreadable; inspect destination before retrying"
                ) from None
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code == 408 or code >= 500 or 300 <= code < 400:
            raise UnknownCreateOutcome(
                "Create outcome is unknown; inspect destination before retrying"
            ) from None
        raise PlatformError(
            "Platform create returned HTTP " + str(code), code
        ) from None
    except (error.URLError, TimeoutError, OSError, HTTPException):
        raise UnknownCreateOutcome(
            "Create outcome is unknown; inspect destination before retrying"
        ) from None
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("id"), str)
        or not payload["id"].strip()
    ):
        raise UnknownCreateOutcome(
            "Create response lacked a product ID; inspect destination before retrying"
        )
    entity_id = payload["id"]
    warnings = list(review.warnings)
    comparison: Dict[str, str] = {}
    status = "created"
    try:
        actual = adapter.get_product(entity_id, include_domains=True)
        returned = actual.data if isinstance(actual.data, dict) else {}
        comparison["name"] = (
            "matched"
            if returned.get("displayName") == review.product_name
            else "different_or_missing"
        )
        comparison["productID"] = (
            "matched"
            if returned.get("name") == review.product_id
            else "different_or_missing"
        )
        document = _load_unambiguous_yaml(source_yaml)
        if not isinstance(document, dict):
            raise IntegrationError("Reviewed source could not be read back")
        selected = document["product"]["details"][language]
        description = selected.get("description") or selected.get("valueProposition")
        if description:
            comparison["description"] = (
                "matched"
                if returned.get("description") == description
                else "different_or_missing"
            )
        for field, native_field, supported in (
            ("type", "dataProductType", {"dataset": "DATASET"}),
            ("visibility", "visibility", {"private": "PRIVATE"}),
        ):
            value = selected.get(field)
            if value is not None:
                expected = supported.get(value)
                comparison[field] = (
                    "unverified"
                    if expected is None
                    else (
                        "matched"
                        if returned.get(native_field) == expected
                        else "different_or_missing"
                    )
                )
        for field in ("portfolioPriority", "tags"):
            if field in selected:
                comparison[field] = "unverified"
        if returned.get("id") != entity_id:
            comparison["identity"] = "different_or_missing"
        actual_domains = returned.get("domains")
        if not isinstance(actual_domains, list) or any(
            not isinstance(item, dict)
            or not isinstance(item.get("fullyQualifiedName"), str)
            for item in actual_domains
        ):
            comparison["domain"] = "unverified"
        else:
            comparison["domain"] = (
                "matched"
                if any(item["fullyQualifiedName"] == domain for item in actual_domains)
                else "different_or_missing"
            )
        if any(value == "different_or_missing" for value in comparison.values()):
            status = "created_with_mismatches"
            warnings.append(
                "Product was created but readback differed; inspect the product before retrying"
            )
        elif any(value == "unverified" for value in comparison.values()):
            status = "created_unverified"
            warnings.append(
                "Some mapped fields could not be verified; inspect the product before retrying"
            )
        fqn = actual.provenance.fqn
    except IntegrationError:
        status = "created_unverified"
        comparison["readback"] = "unavailable"
        warnings.append("Product was created but post-write retrieval failed")
        fqn = None
    contract_result: Optional[Dict[str, object]] = None
    if review.contract_import is not None:
        if status != "created":
            contract_result = {
                "status": "not_imported",
                "reason": "Product readback was not verified",
            }
        else:
            try:
                contract_source = _resolve_product_contract(
                    _load_unambiguous_yaml(source_yaml), source_path
                )
                if (
                    contract_source is None
                    or hashlib.sha256(contract_source.encode("utf-8")).hexdigest()
                    != review.contract_import["source_sha256"]
                ):
                    contract_result = {
                        "status": "not_imported",
                        "reason": "Contract source changed after product creation",
                    }
                    status = "created_contract_failed"
                else:
                    contract_review = adapter.review_contract_import(
                        contract_source, product_id=entity_id
                    )
                    if not contract_review.executable:
                        contract_result = {
                            "status": "blocked",
                            "validation": contract_review.validation,
                        }
                        status = "created_contract_failed"
                    else:
                        imported = adapter.import_contract(
                            contract_source,
                            product_id=entity_id,
                            reviewed_sha256=contract_review.review_sha256,
                        )
                        contract_result = imported.to_dict()
                        if imported.status != "created":
                            status = "created_contract_unverified"
            except IntegrationError as exc:
                contract_result = {"status": "failed_or_unknown", "message": str(exc)}
                status = "created_contract_failed"
        if status != "created":
            warnings.append(
                "Product exists; inspect the product and contract before retrying or importing separately."
            )
    assignment_result: Optional[Dict[str, object]] = None
    if review.assignments:
        if status != "created":
            assignment_result = {
                "status": "not_applied",
                "reason": "Product creation was not fully verified",
            }
        else:
            try:
                from .update import resolve_owner, resolve_tag

                current = {
                    "owners": [
                        resolve_owner(adapter, item) for item in effective_owners
                    ],
                    "tags": [resolve_tag(adapter, item) for item in tags or []],
                }
                if current != review.assignments:
                    raise IntegrationError(
                        "Owner or tag identity changed since the creation review"
                    )
                assignment_review = adapter.review_update(
                    entity_id, owners=effective_owners or None, tags=tags
                )
                proposed_owners = cast(
                    List[Dict[str, str]], assignment_review.proposed.get("owners", [])
                )
                if any(
                    not any(
                        item.get("id") == owner["id"]
                        and item.get("type") == owner["type"]
                        for item in proposed_owners
                    )
                    for owner in review.assignments["owners"]
                ):
                    raise IntegrationError(
                        "Resolved owner changed since the creation review"
                    )
                assignment_update = adapter.update_product(
                    entity_id,
                    owners=effective_owners or None,
                    tags=tags,
                    reviewed_sha256=assignment_review.review_sha256,
                )
                assignment_result = assignment_update.to_dict()
                if any(
                    value != "matched"
                    for value in assignment_update.comparison.values()
                ):
                    status = "created_assignments_unverified"
            except IntegrationError as exc:
                assignment_result = {"status": "failed_or_unknown", "message": str(exc)}
                status = "created_assignments_failed"
        if status != "created":
            warnings.append(
                "Product exists; inspect owner and tag assignments before retrying."
            )
    return CreateResult(
        status,
        review.profile,
        domain,
        entity_id,
        fqn,
        review.review_sha256,
        datetime.now(timezone.utc).isoformat(),
        review.field_mapping,
        review.unsupported_fields,
        comparison,
        tuple(warnings),
        contract_result,
        assignment_result,
    )
