"""Open Data Product Catalog (ODPC) namespace."""

from .catalog import (
    CatalogValidationResult,
    collect_ids,
    count_items,
    explain_catalog,
    load_catalog,
    load_object_records,
    load_schema,
    render_object_records,
    search_objects,
    validate_catalog,
)

SPEC_ID = "odpc"
SPEC_NAME = "Open Data Product Catalog"

__all__ = [
    "SPEC_ID",
    "SPEC_NAME",
    "CatalogValidationResult",
    "collect_ids",
    "count_items",
    "explain_catalog",
    "load_catalog",
    "load_object_records",
    "load_schema",
    "render_object_records",
    "search_objects",
    "validate_catalog",
]
