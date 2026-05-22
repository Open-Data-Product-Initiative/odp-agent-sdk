"""Optional Data Contract integration for product-level workflows."""

from .alignment import check_product_contract_alignment
from .datacontract_cli_adapter import (
    detect_datacontract_cli,
    export_contract,
    validate_contract,
)
from .loader import (
    explain_contract,
    extract_contract_schema,
    extract_contract_schema_from_document,
    load_contract,
    summarize_contract,
    summarize_contract_document,
)
from .models import (
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
    AlignmentFinding,
    ProductContractReport,
    ProductContractAlignmentResult,
)
from .product import generate_product_contract_report, resolve_product_contracts

__all__ = [
    "AlignmentFinding",
    "ContractDocument",
    "ContractExportResult",
    "ContractReference",
    "ContractSchemaField",
    "ContractSchemaModel",
    "ContractSchemaSummary",
    "ContractSummary",
    "ContractToolAvailability",
    "ContractValidationResult",
    "Finding",
    "ProductContractAlignmentResult",
    "ProductContractReport",
    "check_product_contract_alignment",
    "detect_datacontract_cli",
    "explain_contract",
    "export_contract",
    "extract_contract_schema",
    "extract_contract_schema_from_document",
    "generate_product_contract_report",
    "load_contract",
    "resolve_product_contracts",
    "summarize_contract",
    "summarize_contract_document",
    "validate_contract",
]
