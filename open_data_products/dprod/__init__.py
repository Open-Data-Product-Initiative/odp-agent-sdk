"""DPROD 1.0 Beta 2 interoperability helpers."""

from .catalog import discover_dprod_catalog, wrap_dprod_resource
from .mapping import export_odps_to_dprod, write_dprod_export
from .models import (
    DprodCatalogResult,
    DprodExportResult,
    DprodProduct,
    DprodRelationship,
    DprodResource,
    DprodValidationResult,
    DprodViolation,
    DprodWrapResult,
)
from .validation import DPROD_NAMESPACE, validate_dprod

__all__ = [
    "DPROD_NAMESPACE",
    "DprodCatalogResult",
    "DprodExportResult",
    "DprodProduct",
    "DprodRelationship",
    "DprodResource",
    "DprodValidationResult",
    "DprodViolation",
    "DprodWrapResult",
    "discover_dprod_catalog",
    "export_odps_to_dprod",
    "validate_dprod",
    "wrap_dprod_resource",
    "write_dprod_export",
]
