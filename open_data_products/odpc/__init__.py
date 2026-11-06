"""Open Data Product Catalog (ODPC) namespace."""

from .ai_product import (
    AI_PRODUCT_SCHEMA_URL,
    load_ai_product,
    load_ai_product_schema,
    validate_ai_product,
)

from .catalog import (
    CatalogValidationResult,
    DEFAULT_CATALOG_HTML_TEMPLATE,
    build_catalog,
    build_catalog_artifacts,
    collect_ids,
    count_items,
    explain_catalog,
    load_catalog,
    load_object_records,
    load_schema,
    render_catalog_gcf,
    render_catalog_html,
    render_catalog_toon,
    render_catalog_schema_json,
    render_object_records,
    search_objects,
    validate_catalog,
    write_catalog,
    write_catalog_gcf,
    write_catalog_html,
    write_catalog_toon,
    write_catalog_artifacts,
)

SPEC_ID = "odpc"
SPEC_NAME = "Open Data Product Catalog"

__all__ = [
    "SPEC_ID",
    "SPEC_NAME",
    "AI_PRODUCT_SCHEMA_URL",
    "CatalogValidationResult",
    "DEFAULT_CATALOG_HTML_TEMPLATE",
    "build_catalog",
    "build_catalog_artifacts",
    "collect_ids",
    "count_items",
    "explain_catalog",
    "load_catalog",
    "load_ai_product",
    "load_ai_product_schema",
    "load_object_records",
    "load_schema",
    "render_catalog_gcf",
    "render_catalog_html",
    "render_catalog_toon",
    "render_catalog_schema_json",
    "render_object_records",
    "search_objects",
    "validate_catalog",
    "validate_ai_product",
    "write_catalog",
    "write_catalog_gcf",
    "write_catalog_html",
    "write_catalog_toon",
    "write_catalog_artifacts",
]
