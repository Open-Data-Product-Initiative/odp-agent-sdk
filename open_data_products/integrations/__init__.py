"""Versioned platform connection configuration and adapters."""

from .adapter import PlatformAdapter, open_integration
from .create import CreateResult, CreateReview, UnknownCreateOutcome
from .delete import DeleteResult, DeleteReview, UnknownDeleteOutcome
from .domains import DomainCreateResult, DomainCreateReview, UnknownDomainCreateOutcome
from .contracts import (
    ContractImportResult,
    ContractImportReview,
    UnknownContractImportOutcome,
)
from .update import UnknownUpdateOutcome, UpdateResult, UpdateReview
from .config import (
    ConfigurationError,
    ConnectionProfile,
    IntegrationConfig,
    IntegrationError,
    load_integration_config,
)
from .openmetadata import (
    NormalizedOdpsExport,
    OpenMetadataAdapter,
    PlatformError,
    ProductPage,
    ProductSearchPage,
    ProductResult,
    Provenance,
    UnsupportedOperation,
    UpdatedDateChange,
    normalize_openmetadata_updated_dates,
)
from ._comparison import FieldComparison, ProductComparison

__all__ = [
    "ConfigurationError",
    "CreateResult",
    "CreateReview",
    "DeleteResult",
    "DeleteReview",
    "DomainCreateResult",
    "DomainCreateReview",
    "ContractImportResult",
    "ContractImportReview",
    "ConnectionProfile",
    "IntegrationConfig",
    "IntegrationError",
    "OpenMetadataAdapter",
    "NormalizedOdpsExport",
    "PlatformAdapter",
    "PlatformError",
    "ProductPage",
    "FieldComparison",
    "ProductComparison",
    "ProductSearchPage",
    "ProductResult",
    "Provenance",
    "UnsupportedOperation",
    "UnknownCreateOutcome",
    "UnknownDeleteOutcome",
    "UnknownDomainCreateOutcome",
    "UnknownContractImportOutcome",
    "UnknownUpdateOutcome",
    "UpdateResult",
    "UpdateReview",
    "UpdatedDateChange",
    "load_integration_config",
    "open_integration",
    "normalize_openmetadata_updated_dates",
]
