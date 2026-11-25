"""Compare an ODPS source with retrieved OpenMetadata and its ODPS export."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from typing import List, Optional, TYPE_CHECKING

import yaml

from ..agent import validate_document
from ..odps.versions import detect_version
from ..results import ValidationResult
from .config import IntegrationError
from .create import _load_unambiguous_yaml
from .openmetadata import ProductResult, Provenance

if TYPE_CHECKING:
    from .openmetadata import OpenMetadataAdapter


@dataclass(frozen=True)
class FieldComparison:
    """Evidence for one source field, scoped to native metadata or ODPS export."""

    path: str
    status: str
    source_value: object
    platform_value: object
    evidence: str
    explanation: str


@dataclass(frozen=True)
class ProductComparison:
    """Source validation and read-only comparison with a platform product."""

    product_id: str
    source_product_id: Optional[str]
    source_sha256: str
    source_version: Optional[str]
    requested_domain: str
    source_validation: ValidationResult
    native_provenance: Provenance
    platform_updated_at: object
    platform_updated_at_unit: Optional[str]
    export_provenance: Optional[Provenance]
    export_validation: Optional[ValidationResult]
    export_updated: object
    export_updated_kind: Optional[str]
    fields: List[FieldComparison]
    warnings: List[str]

    def to_dict(self) -> dict:
        """Return a structured comparison without full response bodies."""
        return asdict(self)


def _export_detail(export: Optional[ProductResult], language: str) -> tuple:
    if export is None or not isinstance(export.data, str):
        return None, None, None
    try:
        document = yaml.safe_load(export.data)
    except yaml.YAMLError:
        return None, None, None
    if not isinstance(document, dict):
        return None, None, None
    product = document.get("product")
    if not isinstance(product, dict):
        return document, None, None
    details = product.get("details")
    detail = details.get(language) if isinstance(details, dict) else None
    return document, product, detail if isinstance(detail, dict) else None


def _compare_value(
    path: str,
    value: object,
    target: dict,
    key: str,
    *,
    evidence: str,
    enum_case: bool = False,
) -> FieldComparison:
    if key not in target:
        return FieldComparison(
            path,
            "unverified",
            value,
            None,
            evidence,
            "The requested platform field was not returned.",
        )
    actual = target[key]
    if actual is None:
        return FieldComparison(
            path,
            "omitted",
            value,
            None,
            evidence,
            "The platform returned a null value for this field.",
        )
    if value == actual:
        return FieldComparison(
            path, "preserved", value, actual, evidence, "Values match."
        )
    if (
        enum_case
        and isinstance(value, str)
        and isinstance(actual, str)
        and value.casefold() == actual.casefold()
    ):
        return FieldComparison(
            path,
            "normalized",
            value,
            actual,
            evidence,
            "The platform changed enum letter case.",
        )
    return FieldComparison(
        path,
        "changed",
        value,
        actual,
        evidence,
        "The returned value differs from the source.",
    )


def _compare_export_field(
    path: str, value: object, target: Optional[dict], key: str
) -> FieldComparison:
    if target is None:
        return FieldComparison(
            path,
            "unverified",
            value,
            None,
            "odps_export",
            "The ODPS export or requested language was unavailable.",
        )
    if key not in target or target[key] is None:
        return FieldComparison(
            path,
            "omitted",
            value,
            None,
            "odps_export",
            "The field was absent from the ODPS export; it may exist elsewhere in OpenMetadata.",
        )
    actual = target[key]
    if (
        key == "updated"
        and isinstance(value, str)
        and isinstance(actual, int)
        and not isinstance(actual, bool)
        and actual >= 100_000_000_000
    ):
        try:
            day = (
                datetime.fromtimestamp(actual / 1000, tz=timezone.utc)
                .date()
                .isoformat()
            )
        except (ValueError, OSError, OverflowError):
            day = None
        if value == day:
            return FieldComparison(
                path,
                "normalized",
                value,
                actual,
                "odps_export",
                "Exported milliseconds correspond to the source UTC date; the date alone does not retain time-of-day precision.",
            )
    result = _compare_value(path, value, target, key, evidence="odps_export")
    if key == "status" and result.status == "changed":
        return FieldComparison(
            path,
            "changed",
            value,
            actual,
            "odps_export",
            "The exported lifecycle status differs; OpenMetadata controls lifecycle and the source status is not imported by the tested mapping.",
        )
    return result


def compare_product_source(
    adapter: "OpenMetadataAdapter",
    source_yaml: str,
    *,
    product_id: str,
    domain: str,
    language: str = "en",
) -> ProductComparison:
    """Compare supplied source with native and exported product metadata."""
    from .openmetadata import PlatformError

    if (
        not isinstance(source_yaml, str)
        or not source_yaml.strip()
        or len(source_yaml.encode("utf-8")) > 5 * 1024 * 1024
    ):
        raise IntegrationError("ODPS source is missing or too large")
    if not isinstance(domain, str) or not domain.strip() or domain != domain.strip():
        raise IntegrationError("An explicit destination domain FQN is required")
    if (
        not isinstance(language, str)
        or len(language) != 2
        or not language.isascii()
        or not language.islower()
        or not language.isalpha()
    ):
        raise IntegrationError("Language must be an ISO 639-1 code")
    document = _load_unambiguous_yaml(source_yaml)
    if not isinstance(document, dict):
        raise IntegrationError("ODPS source must be a mapping")
    try:
        validation = validate_document(document)
    except (ValueError, TypeError, AttributeError):
        validation = ValidationResult(
            False, "odps", "OpenDataProduct", ["Source is not a valid ODPS document"]
        )
    if validation.spec != "odps":
        raise IntegrationError("Comparison requires an ODPS document")
    product = document.get("product")
    product = product if isinstance(product, dict) else {}
    details = product.get("details")
    selected = details.get(language) if isinstance(details, dict) else None
    source_language_missing = not isinstance(selected, dict)
    selected = selected if isinstance(selected, dict) else {}
    native = adapter.get_product(product_id, include_domains=True)
    data = native.data
    if not isinstance(data, dict) or data.get("id") != product_id:
        raise PlatformError("Platform returned an unexpected product identity")
    warnings = [
        "Comparison reports metadata evidence, not business approval or verification of data and controls."
    ]
    if source_language_missing:
        warnings.append(
            "The requested language is missing from the source; its detail fields cannot be compared."
        )
    try:
        export = adapter.export_odps(product_id)
    except IntegrationError:
        export = None
        warnings.append(
            "ODPS export was unavailable; export-only fields could not be verified."
        )
    export_document, export_product, export_details = _export_detail(export, language)
    if (
        export is not None
        and export.validation is not None
        and not export.validation.valid
    ):
        warnings.append(
            "The platform ODPS export failed validation; its fields are shown as retrieved evidence."
        )
    fields: List[FieldComparison] = []
    for key in ("version", "schema"):
        if key in document:
            fields.append(
                _compare_export_field("/" + key, document[key], export_document, key)
            )
    domains = data.get("domains")
    if not isinstance(domains, list) or any(
        not isinstance(item, dict)
        or not isinstance(item.get("fullyQualifiedName"), str)
        for item in domains
    ):
        fields.append(
            FieldComparison(
                "/destination/domain",
                "unverified",
                domain,
                None,
                "native",
                "Domain references were not returned in a usable form.",
            )
        )
    else:
        names = [item["fullyQualifiedName"] for item in domains]
        fields.append(
            FieldComparison(
                "/destination/domain",
                "preserved" if domain in names else "changed",
                domain,
                names,
                "native",
                (
                    "Requested domain was found."
                    if domain in names
                    else "Requested domain was not found in the returned domains."
                ),
            )
        )
    native_fields = {
        "productID": "name",
        "name": "displayName",
        "description": "description",
        "type": "dataProductType",
        "visibility": "visibility",
        "portfolioPriority": "portfolioPriority",
    }
    for key, value in selected.items():
        path = "/product/details/" + language + "/" + key
        if key in native_fields:
            fields.append(
                _compare_value(
                    path,
                    value,
                    data,
                    native_fields[key],
                    evidence="native",
                    enum_case=key in ("type", "visibility", "portfolioPriority"),
                )
            )
        elif key == "valueProposition" and not selected.get("description"):
            fields.append(
                _compare_value(path, value, data, "description", evidence="native")
            )
        else:
            fields.append(_compare_export_field(path, value, export_details, key))
    for key, value in product.items():
        if key != "details":
            # Large source components may contain sensitive documents; report presence only.
            comparison = _compare_export_field(
                "/product/" + str(key), "present", export_product, key
            )
            if (
                export_product is not None
                and key in export_product
                and export_product[key] is not None
            ):
                comparison = FieldComparison(
                    comparison.path,
                    "unverified",
                    "present",
                    "present",
                    "odps_export",
                    "The component exists in the export; its full contents were not compared.",
                )
            fields.append(comparison)
    source_id = selected.get("productID")
    updated_at = data.get("updatedAt")
    exported_updated = (
        export_details.get("updated") if export_details is not None else None
    )
    export_kind = (
        "unix_milliseconds"
        if isinstance(exported_updated, int)
        and not isinstance(exported_updated, bool)
        and exported_updated >= 100_000_000_000
        else (
            "date_string"
            if isinstance(exported_updated, str)
            else "unknown" if exported_updated is not None else None
        )
    )
    return ProductComparison(
        product_id,
        source_id if isinstance(source_id, str) else None,
        hashlib.sha256(source_yaml.encode("utf-8")).hexdigest(),
        detect_version(document),
        domain,
        validation,
        native.provenance,
        updated_at,
        (
            "unix_milliseconds"
            if isinstance(updated_at, int) and not isinstance(updated_at, bool)
            else None
        ),
        export.provenance if export is not None else None,
        export.validation if export is not None else None,
        exported_updated,
        export_kind,
        fields,
        warnings,
    )
