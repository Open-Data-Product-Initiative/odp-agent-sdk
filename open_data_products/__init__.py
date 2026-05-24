"""Open Data Products Python SDK.

This package provides Python support for the OpenDataProducts.org standards
family. Each standard lives in its own namespace:

- :mod:`open_data_products.odps`
- :mod:`open_data_products.odpc`
- :mod:`open_data_products.odpg`
- :mod:`open_data_products.odpv`
"""

__version__ = "0.2.4"
version = __version__

from . import odpc
from . import odpg
from . import odps
from . import odpv
from .agent import (
    detect_document,
    explain_document,
    explain_product,
    explain_vocabulary,
    load_document,
    resolve_references,
    validate_document,
)
from .contracts import (
    AlignmentFinding,
    ContractDocument,
    ContractExportResult,
    ContractReference,
    ContractSchemaField,
    ContractSchemaModel,
    ContractSchemaSummary,
    ContractSummary,
    ContractToolAvailability,
    ContractValidationResult,
    Finding,
    ProductContractAlignmentResult,
    ProductContractReport,
    check_product_contract_alignment,
    detect_datacontract_cli,
    explain_contract,
    export_contract,
    extract_contract_schema,
    extract_contract_schema_from_document,
    generate_product_contract_report,
    load_contract,
    resolve_product_contracts,
    summarize_contract,
    summarize_contract_document,
    validate_contract,
)
from .odpc import (
    build_catalog_artifacts,
    render_catalog_schema_json,
    write_catalog_artifacts,
)
from .odpv import (
    agent_vocabulary_context,
    check_vocabulary_relationship,
    explain_vocabulary_term,
    resolve_vocabulary_term,
)
from .pricing import pricing_to_402
from .resources import get_resource, list_resources
from .results import Reference, Resource, ValidationResult
from .summary import load_summary

__all__ = [
    "__version__",
    "version",
    "odpc",
    "odpg",
    "odps",
    "odpv",
    "Reference",
    "Resource",
    "ValidationResult",
    "AlignmentFinding",
    "agent_vocabulary_context",
    "build_catalog_artifacts",
    "check_vocabulary_relationship",
    "ContractToolAvailability",
    "ContractValidationResult",
    "ContractDocument",
    "ContractExportResult",
    "ContractReference",
    "ContractSchemaField",
    "ContractSchemaModel",
    "ContractSchemaSummary",
    "ContractSummary",
    "Finding",
    "ProductContractAlignmentResult",
    "ProductContractReport",
    "check_product_contract_alignment",
    "detect_document",
    "detect_datacontract_cli",
    "explain_contract",
    "export_contract",
    "extract_contract_schema",
    "extract_contract_schema_from_document",
    "explain_document",
    "explain_product",
    "explain_vocabulary_term",
    "explain_vocabulary",
    "get_resource",
    "list_resources",
    "load_document",
    "load_contract",
    "load_summary",
    "pricing_to_402",
    "generate_product_contract_report",
    "render_catalog_schema_json",
    "resolve_references",
    "resolve_vocabulary_term",
    "resolve_product_contracts",
    "summarize_contract",
    "summarize_contract_document",
    "validate_contract",
    "validate_document",
    "write_catalog_artifacts",
]
