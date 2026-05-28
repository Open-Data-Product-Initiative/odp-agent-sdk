# Open Data Products Python SDK API Reference

## Agent API

Use the top-level `open_data_products` API when an agent, pipeline, or tool
needs one surface across ODPS, ODPC, ODPG, and ODPV documents:

```python
from open_data_products import (
    detect_document,
    copy_config_template,
    copy_generation_prompts,
    explain_document,
    generate_local_artifact,
    generate_local_artifacts,
    get_config,
    get_config_path,
    get_resource,
    list_resources,
    load_generation_prompt,
    print_config,
    load_document,
    load_summary,
    resolve_references,
    validate_config,
    validate_document,
)

document = load_document("examples/product.yaml")
result = validate_document(document)
summary = explain_document(document)
references = resolve_references(document)
resources = list_resources()
metadata = load_summary("examples/product.yaml")
config = get_config("generation")
config_path = get_config_path("generation")
copy_config_template("generation", "my-generation.config.yaml")
copy_generation_prompts("prompts")
config_report = validate_config("generation", "my-generation.config.yaml")
config_yaml = print_config("generation", "my-generation.config.yaml")
prompt = load_generation_prompt("odps_data_product_fragment.md", prompt_dir="prompts")
signal = generate_local_artifact("signal", "signal.txt", "open_data_products/generation/fragments")
artifacts = generate_local_artifacts("open_data_products/generation/source_docs", "open_data_products/generation/fragments")
```

### Core Functions

- `load_document(path)`: load an ODPS, ODPC, ODPG, or ODPV YAML/JSON document.
- `detect_document(document)`: return `(spec, kind)` for a loaded document.
- `validate_document(document_or_path, path=None)`: return a shared
  `ValidationResult` with `valid`, `spec`, `kind`, `errors`, `warnings`,
  `hints`, and `path`.
- `explain_document(document_or_path, path=None)`: return a compact
  human-and-agent-readable summary.
- `resolve_references(document_or_path, path=None)`: return discovered `$ref`,
  `ref`, and `schema` references as `Reference` objects.
- `load_summary(path)`: return lightweight metadata (`path`, `byte_size`,
  `line_count`, `sha256`, `spec`, `kind`, and `id`) without returning the
  document body.
- `list_resources()` and `get_resource(id)`: discover bundled schemas,
  prompt templates, vocabularies, examples, and JSONL retrieval records.
- `get_config(domain="generation")`, `get_config_path(domain="generation")`,
  `copy_config_template("generation", destination)`, `copy_generation_prompts`,
  `print_config(...)`, and `validate_config("generation", path)`: discover the
  bundled config and prompt templates, copy them to user-editable files, print
  the selected YAML, and validate safe resolved provider/model settings without
  exposing secret values or contacting providers.
- `list_generation_prompts()` and `load_generation_prompt(name)`: discover and
  load editable LLM prompts for generating standards-ready YAML artifacts.
- `generate_local_artifact(kind, source, output_dir, model="qwen2.5")`: generate
  one selected artifact kind (`product`, `use-case`, `objective`, `signal`, or
  `graph`) from one Markdown/text source file or a source folder.
- `generate_local_artifacts(source_dir, output_dir, model="qwen2.5")`: use the
  editable prompts and configured generation client to generate separate ODPC
  `productReference`, `useCase`, `businessObjective`, and `signal` fragment
  files from Markdown/text source documents, then generate ODPG graph YAML from
  those fragment files.
- `load_generation_config(path)`, `resolve_generation_settings(...)`, and
  `create_generation_client(settings)`: load provider config and create the
  configured Ollama, OpenAI-compatible, or Anthropic generation client without
  storing API keys in source files.
- `ensure_ollama_model(model="qwen2.5")`: check that Ollama is reachable and
  that the requested local model is available before Ollama-backed generation.

### Shared Result Types

```python
from open_data_products import Reference, Resource, ValidationResult

result_dict = validate_document("examples/product.yaml").to_dict()
resource_dict = get_resource("odpv.terms").to_dict()
reference_dicts = [ref.to_dict() for ref in resolve_references("graph.yaml")]
```

`ValidationResult`, `Resource`, and `Reference` are dataclasses with `to_dict()`
helpers for JSON/MCP responses.

### Unified CLI and Agent Surfaces

The same cross-spec workflow is available through the unified CLI:

```bash
open-data-products validate examples/product.yaml --json
open-data-products explain examples/product.yaml --json
open-data-products refs graph.yaml --json
open-data-products resources --json
# Requires Ollama running locally and `ollama pull qwen2.5` for the default provider.
open-data-products generate --json
open-data-products generate --config my-generation.config.yaml --json
open-data-products generate --config my-generation.config.yaml --provider groq --json
open-data-products generate --config my-generation.config.yaml --provider claude --json
open-data-products summary examples/product.yaml
open-data-products manifest --json
open-data-products serve
```

`open-data-products serve` runs the local stdio MCP server. The MCP tool
registry and ARWS manifest expose the safe read-only tools documented in
`README.md` and `llms.txt`.

## Package Namespace

The SDK uses one namespace per Open Data Products standard:

- `open_data_products.odps` for Open Data Product Specification
- `open_data_products.odpc` for Open Data Product Catalog
- `open_data_products.odpg` for Open Data Product Graph
- `open_data_products.odpv` for Open Data Product Vocabulary
- `open_data_products.generation` for LLM generation prompts and provider config

Import ODPS APIs from `open_data_products.odps`:

```python
from open_data_products.odps import OpenDataProduct
from open_data_products.odps.models import ProductDetails
```

### Spec Helper Namespaces

Use the spec namespaces when the target standard is already known:

```python
from open_data_products.odpc import (
    build_catalog,
    explain_catalog,
    load_catalog,
    render_catalog_html,
    search_objects,
    validate_catalog,
    write_catalog_html,
)
from open_data_products.odpg import (
    agent_context,
    analyze_graph,
    load_graph,
    search_graph_objects,
    summarize_graph,
    traverse_graph,
    validate_graph,
)
from open_data_products.odpv import (
    build_artifacts,
    load_vocabulary,
    search_vocabulary,
    validate_vocabulary,
    write_artifacts,
)
from open_data_products.generation import (
    list_generation_prompts,
    load_generation_prompt,
)
```

- `open_data_products.odpc`: catalog building from ODPC fragments or ODPS
  product files, standalone catalog HTML rendering, loading, schema validation,
  compact explanations, and bundled catalog object guidance search.
- `open_data_products.odpg`: graph loading, validation, summaries,
  relationship traversal, strategic/governance analysis, focus-node agent
  context, object search, and standalone graph explorer generation.
- `open_data_products.odpv`: vocabulary loading, validation, search, generated
  JSON/JSONL/YAML artifacts, and artifact drift checks.
- `open_data_products.generation`: editable prompt files for guiding configured
  LLM providers to produce ODPS, ODPC, and ODPG YAML that can be validated by
  the SDK, plus local Ollama and OpenAI generation helpers.

## Table of Contents

1. [Agent API](#agent-api)
2. [Package Namespace](#package-namespace)
3. [Core Classes](#core-classes)
4. [Data Models](#data-models)
   - [ProductStrategy (v4.1)](#productstrategy-v41)
   - [KPI (v4.1)](#kpi-v41)
5. [Validation Framework](#validation-framework)
6. [Exception Hierarchy](#exception-hierarchy)
7. [Type Protocols](#type-protocols)
8. [Enumerations](#enumerations)
   - [KPI Enums (v4.1)](#kpi-enums-v41)
9. [Utility Functions](#utility-functions)
10. [v4.1 Features](#v41-features)

---

## Core Classes

### OpenDataProduct

The main class for handling ODPS v4.1 documents.

```python
class OpenDataProduct:
    """Main class for handling Open Data Product Specification documents."""
```

#### Constructor

```python
def __init__(self, product_details: ProductDetails) -> None:
    """Initialize with mandatory product details."""
```

**Parameters:**
- `product_details` (ProductDetails): Core product information (required)

#### Class Methods

##### from_dict
```python
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> 'OpenDataProduct':
    """Create OpenDataProduct from dictionary."""
```

##### from_json
```python
@classmethod
def from_json(cls, json_str: str) -> 'OpenDataProduct':
    """Load from JSON string."""
```

##### from_yaml
```python
@classmethod
def from_yaml(cls, yaml_str: str) -> 'OpenDataProduct':
    """Load from YAML string."""
```

##### from_file
```python
@classmethod
def from_file(cls, file_path: Union[str, Path]) -> 'OpenDataProduct':
    """Load from file (JSON or YAML)."""
```

#### Instance Methods

##### validate
```python
def validate(self) -> bool:
    """Validate the ODPS document using the validation framework."""
```

**Returns:** `bool` - True if valid

**Raises:** `ODPSValidationError` - If validation fails

##### to_dict
```python
def to_dict(self) -> Dict[str, Any]:
    """Convert to dictionary representation."""
```

##### to_json
```python
def to_json(self, indent: int = 2) -> str:
    """Convert to JSON string with caching."""
```

##### to_yaml
```python
def to_yaml(self) -> str:
    """Convert to YAML string with caching."""
```

##### save
```python
def save(self, file_path: Union[str, Path], format: str = 'auto') -> None:
    """Save to file."""
```

**Parameters:**
- `file_path` (str | Path): Path to save file
- `format` (str): Format to use ('json', 'yaml', or 'auto')

#### Component Management Methods

##### add_data_contract
```python
def add_data_contract(self, url: Optional[str] = None, 
                     specification: Optional[Dict[str, Any]] = None) -> None:
    """Add or update data contract."""
```

##### add_sla
```python
def add_sla(self, url: Optional[str] = None,
            specification: Optional[Dict[str, Any]] = None) -> None:
    """Add or update SLA."""
```

##### add_license
```python
def add_license(self, scope_of_use: str, **kwargs) -> None:
    """Add or update license."""
```

##### add_data_access
```python
def add_data_access(self, default_method: DataAccessMethod, 
                   **additional_methods) -> None:
    """Add or update data access methods."""
```

#### Properties

##### is_valid
```python
@property
def is_valid(self) -> bool:
    """Check if document is valid without raising exceptions."""
```

##### validation_errors
```python
@property
def validation_errors(self) -> List[str]:
    """Get list of validation errors without raising exceptions."""
```

##### has_optional_components
```python
@property
def has_optional_components(self) -> bool:
    """Check if document has any optional components."""
```

##### component_count
```python
@property
def component_count(self) -> int:
    """Count of non-None optional components."""
```

##### is_production_ready
```python
@property
def is_production_ready(self) -> bool:
    """Check if document is ready for production."""
```

##### compliance_level
```python
@property
def compliance_level(self) -> str:
    """Get compliance level based on components present."""
```

**Returns:** One of: `"invalid"`, `"minimal"`, `"basic"`, `"substantial"`, `"full"`

#### Performance Methods

##### check_component_protocols
```python
def check_component_protocols(self) -> Dict[str, bool]:
    """Check if all components follow their respective protocols."""
```

---

## Data Models

All data models are implemented as dataclasses with comprehensive type hints.

### ProductStrategy (v4.1)

**New in ODPS v4.1** - Connects data products to business intent, objectives, and KPIs.

```python
@dataclass
class ProductStrategy:
    """
    Product Strategy - New in ODPS v4.1

    This is "the first open specification where data products declare not just
    what they are but also why they exist."
    """

    objectives: List[str] = field(default_factory=list)
    contributes_to_kpi: Optional[KPI] = None
    product_kpis: List[KPI] = field(default_factory=list)
    related_kpis: List[KPI] = field(default_factory=list)
    strategic_alignment: List[str] = field(default_factory=list)
```

**Attributes:**

- `objectives` (List[str]): Natural-language business outcomes the product supports
- `contributes_to_kpi` (Optional[KPI]): Single higher-level business KPI the product is accountable for
- `product_kpis` (List[KPI]): Product-level metrics measuring direct contribution to business goals
- `related_kpis` (List[KPI]): Secondary measures tracking side effects and cross-unit value
- `strategic_alignment` (List[str]): References to corporate initiatives or policy documents

**Example:**

```python
from open_data_products.odps.models import ProductStrategy, KPI

strategy = ProductStrategy(
    objectives=[
        "Reduce customer churn by identifying at-risk customers early",
        "Improve customer lifetime value through targeted retention campaigns"
    ],
    contributes_to_kpi=KPI(
        name="Customer Retention Rate",
        unit="percentage",
        target=95,
        direction="increase"
    ),
    product_kpis=[
        KPI(
            name="Churn Prediction Accuracy",
            unit="percentage",
            target=85,
            direction="at_least"
        )
    ],
    strategic_alignment=[
        "Corporate Strategy 2024: Customer-First Initiative"
    ]
)
```

---

### KPI (v4.1)

**New in ODPS v4.1** - Key Performance Indicator for tracking business or product performance.

```python
@dataclass
class KPI:
    """
    Key Performance Indicator (KPI) - New in ODPS v4.1

    Represents a measurable metric for tracking business or product performance.
    Used within ProductStrategy to connect data products to business objectives.
    """

    # Required field
    name: str

    # Optional fields
    id: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    target: Optional[Union[str, int, float]] = None
    direction: Optional[str] = None
    timeframe: Optional[str] = None
    frequency: Optional[str] = None
    owner: Optional[str] = None
    calculation: Optional[str] = None
```

**Attributes:**

- `name` (str, **required**): Human-readable KPI name
- `id` (Optional[str]): Unique identifier for the KPI
- `description` (Optional[str]): Human-readable explanation of the KPI
- `unit` (Optional[str]): Measurement unit (use KPIUnit enum values: percentage, minutes, seconds, count, etc.)
- `target` (Optional[Union[str, int, float]]): Target value for the KPI
- `direction` (Optional[str]): How the KPI should move (use KPIDirection enum: increase, decrease, at_least, at_most, equals)
- `timeframe` (Optional[str]): When target should be met (e.g., "Q4 2024", "by end of year")
- `frequency` (Optional[str]): Measurement cadence (e.g., "hourly", "daily", "monthly", "quarterly")
- `owner` (Optional[str]): Responsible role/team for this KPI
- `calculation` (Optional[str]): Human-readable formula describing how the KPI is calculated

**Example:**

```python
from open_data_products.odps.models import KPI

kpi = KPI(
    name="Customer Retention Rate",
    id="kpi-retention-001",
    description="Primary business KPI measuring customer retention",
    unit="percentage",
    target=95,
    direction="increase",
    timeframe="Q4 2024",
    frequency="monthly",
    owner="Customer Success Team",
    calculation="(Customers at end of period / Customers at start) * 100"
)
```

---

### ProductDetails

Core product information (required).

```python
@dataclass
class ProductDetails:
    """Product information and metadata."""
    
    # Required fields
    name: str
    product_id: str
    visibility: str  # private, invitation, organisation, dataspace, public
    status: str      # draft, development, production, deprecated, etc.
    type: str        # dataset, algorithm, ml-model, etc.
    
    # Optional fields
    value_proposition: Optional[str] = None
    description: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    brand: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    geography: Optional[str] = None
    language: List[str] = field(default_factory=list)
    homepage: Optional[str] = None
    logo_url: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    product_series: Optional[str] = None
    standards: List[str] = field(default_factory=list)
    product_version: Optional[str] = None
    version_notes: Optional[str] = None
    issues: Optional[str] = None
    content_sample: Optional[str] = None
    brand_slogan: Optional[str] = None
    use_cases: List[UseCase] = field(default_factory=list)
    recommended_data_products: List[str] = field(default_factory=list)
    output_file_formats: List[str] = field(default_factory=list)
```

### DataHolder

Data provider/holder information.

```python
@dataclass
class DataHolder:
    """Data holder/provider information."""
    
    # Required fields
    name: str
    email: str
    
    # Optional fields
    url: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    business_identifiers: List[str] = field(default_factory=list)
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_postal_code: Optional[str] = None
    address_country: Optional[str] = None
    ratings: Optional[Dict[str, Any]] = None
    organizational_description: Optional[str] = None
```

### DataContract

Data contract specifications with v4.1 $ref support.

```python
@dataclass
class DataContract:
    """Data contract specifications with v4.1 $ref support."""

    id: Optional[str] = None
    type: Optional[str] = None  # ODCS or DCS
    contract_version: Optional[str] = None
    contract_url: Optional[str] = None
    spec: Optional[Dict[str, Any]] = None
    ref: Optional[str] = None  # URI reference
    dollar_ref: Optional[str] = None  # JSON Reference ($ref) - New in v4.1
```

### License

License terms and conditions.

```python
@dataclass
class License:
    """License terms and conditions."""
    
    # Required field
    scope_of_use: str
    
    # Core optional fields
    geographical_area: List[str] = field(default_factory=list)
    permanent: bool = True
    exclusive: bool = False
    right_to_sublicense: bool = False
    right_to_modify: bool = False
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    license_grant: Optional[str] = None
    license_name: Optional[str] = None
    license_url: Optional[str] = None
    
    # Extended optional attributes
    scope_details: Optional[str] = None
    termination_conditions: Optional[str] = None
    governance_specifics: Optional[str] = None
    audit_terms: Optional[str] = None
    warranties: Optional[str] = None
    damages: Optional[str] = None
    confidentiality_clauses: Optional[str] = None
```

### DataAccess & DataAccessMethod

Data access methods and endpoints with v4.1 AI agent support.

```python
@dataclass
class DataAccessMethod:
    """Individual data access method with v4.1 $ref and AI support."""

    name: Optional[Dict[str, str]] = None
    description: Optional[Dict[str, str]] = None
    output_port_type: Optional[str] = None  # file, API, AI (v4.1), etc.
    format: Optional[str] = None  # JSON, CSV, MCP (v4.1), etc.
    access_url: Optional[str] = None
    authentication_method: Optional[str] = None
    specs_url: Optional[str] = None
    documentation_url: Optional[str] = None
    specification: Optional[Dict[str, Any]] = None
    version: Optional[str] = None
    reference: Optional[str] = None
    dollar_ref: Optional[str] = None  # JSON Reference ($ref) - New in v4.1

@dataclass
class DataAccess:
    """Data access configuration with v4.1 $ref support."""

    default: DataAccessMethod
    additional_methods: Dict[str, DataAccessMethod] = field(default_factory=dict)
    dollar_ref: Optional[str] = None  # JSON Reference ($ref) - New in v4.1
```

**v4.1 AI Agent Integration Example:**

```python
from open_data_products.odps.models import DataAccess, DataAccessMethod

# AI Agent Access - NEW in v4.1
ai_agent_access = DataAccessMethod(
    name={"en": "AI Agent Access"},
    description={"en": "Model Context Protocol access for AI agents"},
    output_port_type="AI",  # NEW: AI output port type
    format="MCP",  # NEW: MCP (Model Context Protocol) format
    access_url="mcp://api.example.com/customer-analytics/agent",
    authentication_method="bearer-token",
    specification={
        "protocol": "MCP",
        "version": "1.0",
        "capabilities": ["query", "analyze", "predict"],
        "agent_description": "Autonomous agent for customer churn analysis"
    }
)

data_access = DataAccess(
    default=default_method,
    additional_methods={"aiAgent": ai_agent_access}
)
```

### PricingPlans & PricingPlan

Pricing information and plans.

```python
@dataclass
class PricingPlan:
    """Individual pricing plan."""
    
    # Required fields
    name: Union[str, Dict[str, str]]
    price_currency: str
    
    # Optional fields
    price: Optional[float] = None
    billing_duration: Optional[str] = None
    unit: Optional[str] = None
    max_transactions_per_second: Optional[int] = None
    max_transactions_per_month: Optional[int] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    value_added_tax: Optional[float] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    additional_pricing_details: Optional[str] = None
    quality_profile_reference: Optional[str] = None
    sla_profile_reference: Optional[str] = None
    access_profile_reference: Optional[str] = None

@dataclass
class PricingPlans:
    """Pricing plans container."""
    
    plans: List[PricingPlan] = field(default_factory=list)
```

---

## Validation Framework

### ODPSValidationFramework

Main validation coordinator.

```python
class ODPSValidationFramework:
    """Validation framework that orchestrates multiple validators."""
    
    def __init__(self) -> None:
        """Initialize with default validators."""
    
    def add_validator(self, validator: ValidationRule) -> None:
        """Add a custom validator to the framework."""
    
    def remove_validator(self, validator_class: type) -> None:
        """Remove all validators of the specified class."""
    
    def validate(self, odp: 'OpenDataProduct') -> List[str]:
        """Run all validation rules against an OpenDataProduct."""
```

### ValidationRule

Abstract base class for validation rules.

```python
class ValidationRule(ABC):
    """Abstract base class for validation rules."""
    
    @abstractmethod
    def validate(self, odp: 'OpenDataProduct') -> List[str]:
        """Validate an OpenDataProduct and return list of error messages."""
```

### Built-in Validators

The framework includes 14 built-in validator classes:

- `CoreFieldValidator`: Validates required core fields
- `ProductDetailsValidator`: Validates product details
- `ProductStrategyValidator`: Validates product strategy and KPIs (v4.1)
- `DataHolderValidator`: Validates data holder information
- `LicenseValidator`: Validates license information
- `DataAccessValidator`: Validates data access methods
- `PricingValidator`: Validates pricing plans
- `DataContractValidator`: Validates data contracts
- `SLAValidator`: Validates SLA specifications
- `DataQualityValidator`: Validates data quality specifications
- `PaymentGatewayValidator`: Validates payment gateways
- `ExtensionValidator`: Validates extension fields
- `FieldLengthValidator`: Validates field length limits
- `StandardsComplianceValidator`: Validates international standards compliance

---

## Exception Hierarchy

### Base Exception

```python
class ODPSError(Exception):
    """Base exception class for all ODPS library errors."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
```

### Validation Exceptions

```python
class ODPSValidationError(ODPSError):
    """Raised when ODPS document validation fails."""
    
    def __init__(self, message: str, errors: Optional[List[str]] = None, 
                 field: Optional[str] = None):
        # Implementation details...
    
    @classmethod
    def from_errors(cls, errors: List[str]) -> 'ODPSValidationError':
        """Create validation error from list of error messages."""

class ODPSFieldValidationError(ODPSValidationError):
    """Raised when a specific field fails validation."""
    
    def __init__(self, field: str, value: Any, message: str):
        # Implementation details...
```

### Parsing Exceptions

```python
class ODPSJSONParsingError(ODPSParsingError):
    """Raised when JSON parsing specifically fails."""

class ODPSYAMLParsingError(ODPSParsingError):
    """Raised when YAML parsing specifically fails."""
```

### Component Exceptions

Component-specific exceptions for detailed error handling:

- `ODPSDataContractError`
- `ODPSSLAError`
- `ODPSDataQualityError`
- `ODPSLicenseError`
- `ODPSDataAccessError`
- `ODPSDataHolderError`
- `ODPSPricingError`
- `ODPSPaymentGatewayError`

### Utility Functions

```python
def create_field_error(field: str, value: Any, message: str) -> ODPSFieldValidationError:
    """Create a field-specific validation error."""

def create_component_error(component: str, message: str) -> ODPSComponentError:
    """Create a component-specific error."""
```

---

## Type Protocols

### Core Protocols

```python
class ValidatableProtocol(Protocol):
    """Protocol for objects that can be validated."""
    
    def validate(self) -> bool:
        """Validate the object and return True if valid."""

class SerializableProtocol(Protocol):
    """Protocol for objects that can be serialized."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert object to dictionary representation."""
    
    def to_json(self, indent: int = 2) -> str:
        """Convert object to JSON string."""

class ODPSDocumentProtocol(ValidatableProtocol, SerializableProtocol, Protocol):
    """Protocol for complete ODPS documents."""
    
    schema: str
    version: str
    
    @property
    def is_valid(self) -> bool:
        """Check if document is valid without raising exceptions."""
```

### Component Protocols

Specific protocols for each ODPS component:

- `ProductDetailsProtocol`
- `DataHolderProtocol`
- `DataAccessProtocol`
- `LicenseProtocol`
- `PricingPlansProtocol`
- `DataContractProtocol`
- And more...

### Utility Functions

```python
def is_validatable(obj: Any) -> bool:
    """Check if an object implements the ValidatableProtocol."""

def is_serializable(obj: Any) -> bool:
    """Check if an object implements the SerializableProtocol."""

def validate_protocol_compliance(obj: Any, protocol_name: str) -> List[str]:
    """Validate that an object complies with a specific protocol."""
```

---

## Enumerations

### ProductStatus

```python
class ProductStatus(Enum):
    """Valid product status values according to ODPS v4.1."""

    ANNOUNCEMENT = "announcement"
    DRAFT = "draft"
    DEVELOPMENT = "development"
    TESTING = "testing"
    ACCEPTANCE = "acceptance"
    PRODUCTION = "production"
    SUNSET = "sunset"
    RETIRED = "retired"
```

### ProductVisibility

```python
class ProductVisibility(Enum):
    """Valid product visibility values."""
    
    PRIVATE = "private"
    INVITATION = "invitation"
    ORGANIZATION = "organisation"  # British spelling per spec
    DATASPACE = "dataspace"
    PUBLIC = "public"
```

### DataContractType

```python
class DataContractType(Enum):
    """Valid data contract types."""

    ODCS = "ODCS"  # Open Data Contract Specification
    DCS = "DCS"    # Data Contract Specification
```

### KPI Enums (v4.1)

**New in ODPS v4.1** - Enumerations for KPI validation.

#### KPIDirection

```python
class KPIDirection(Enum):
    """Valid KPI direction values - New in ODPS v4.1."""

    INCREASE = "increase"      # KPI target is to increase the value
    DECREASE = "decrease"      # KPI target is to decrease the value
    AT_LEAST = "at_least"      # KPI must be at least the target value
    AT_MOST = "at_most"        # KPI must be at most the target value
    EQUALS = "equals"          # KPI must equal the target value
```

**Usage:**

```python
from open_data_products.odps.models import KPI
from open_data_products.odps.enums import KPIDirection

kpi = KPI(
    name="Customer Retention Rate",
    target=95,
    direction=KPIDirection.INCREASE.value  # or simply "increase"
)
```

#### KPIUnit

```python
class KPIUnit(Enum):
    """Valid KPI unit values - New in ODPS v4.1."""

    # Time units
    PERCENTAGE = "percentage"
    MINUTES = "minutes"
    SECONDS = "seconds"
    HOURS = "hours"
    DAYS = "days"

    # Count units
    COUNT = "count"
    CURRENCY = "currency"
    RATIO = "ratio"
    SCORE = "score"

    # Data size units
    BYTES = "bytes"
    KILOBYTES = "kilobytes"
    MEGABYTES = "megabytes"
    GIGABYTES = "gigabytes"
    TERABYTES = "terabytes"

    # Domain-specific units
    REQUESTS = "requests"
    TRANSACTIONS = "transactions"
    USERS = "users"
    ERRORS = "errors"
    RECORDS = "records"
```

**Usage:**

```python
from open_data_products.odps.models import KPI
from open_data_products.odps.enums import KPIUnit

kpi = KPI(
    name="Average Response Time",
    target=200,
    unit=KPIUnit.MILLISECONDS.value  # or simply "milliseconds"
)
```

#### OutputPortType (Updated for v4.1)

```python
class OutputPortType(Enum):
    """Valid output port types."""

    FILE = "file"
    API = "API"
    DATABASE = "database"
    STREAM = "stream"
    WEBHOOK = "webhook"
    AI = "AI"  # New in v4.1 - for AI agent integration
```

**v4.1 AI Port Type Usage:**

```python
from open_data_products.odps.models import DataAccessMethod
from open_data_products.odps.enums import OutputPortType

ai_access = DataAccessMethod(
    output_port_type=OutputPortType.AI.value,  # or simply "AI"
    format="MCP"  # Model Context Protocol
)
```

---

## Utility Functions

### ODPSValidator

Utility class with individual validation methods:

```python
class ODPSValidator:
    """Utility class containing individual validation methods."""
    
    @staticmethod
    def validate_iso639_language_code(code: str) -> bool:
        """Validate ISO 639-1 language code."""
    
    @staticmethod
    def validate_iso3166_country_codes(codes: List[str]) -> bool:
        """Validate ISO 3166-1 alpha-2 country codes."""
    
    @staticmethod
    def validate_currency_code(code: str) -> bool:
        """Validate ISO 4217 currency code."""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email address according to RFC 5322."""
    
    @staticmethod
    def validate_phone_number(phone: str) -> bool:
        """Validate phone number according to ITU-T E.164."""
    
    @staticmethod
    def validate_iso8601_date(date_str: str) -> bool:
        """Validate ISO 8601 date format."""
    
    @staticmethod
    def validate_uri(uri: str) -> bool:
        """Validate URI according to RFC 3986."""
    
    # Additional validation methods...
```

---

## Performance Features

### Caching System

The library implements intelligent caching for optimal performance:

- **Validation Caching**: Results cached based on object state hash
- **Serialization Caching**: JSON/YAML output cached with invalidation
- **Hash-based Invalidation**: Automatic cache clearing on state changes

### Memory Optimization

- **__slots__**: Used in core classes for memory efficiency
- **Lazy Loading**: Components loaded only when accessed
- **Efficient Data Structures**: Optimized internal representations

---

## v4.1 Features

### What's New in ODPS v4.1

ODPS v4.1 introduces groundbreaking features that connect data products to business intent and enable AI agent integration.

#### 1. ProductStrategy - Business Alignment

**The first open specification where data products declare not just what they are but also why they exist.**

```python
from open_data_products.odps import OpenDataProduct
from open_data_products.odps.models import ProductStrategy, KPI

product = OpenDataProduct(product_details)

# Define business strategy and KPIs
product.product_strategy = ProductStrategy(
    objectives=[
        "Reduce customer churn by identifying at-risk customers early"
    ],
    contributes_to_kpi=KPI(
        name="Customer Retention Rate",
        target=95,
        unit="percentage",
        direction="increase"
    )
)
```

**Key Features:**
- `objectives`: Natural-language business outcomes
- `contributes_to_kpi`: Primary business KPI accountability
- `product_kpis`: Product-level performance metrics
- `related_kpis`: Secondary and cross-unit measures
- `strategic_alignment`: Links to corporate initiatives

#### 2. KPI Model - Performance Tracking

Comprehensive KPI model with 10 fields for complete performance tracking:

```python
from open_data_products.odps.models import KPI

kpi = KPI(
    name="Churn Prediction Accuracy",        # Required
    id="kpi-churn-accuracy",
    description="Measures accuracy of churn prediction model",
    unit="percentage",                        # Use KPIUnit enum
    target=85,
    direction="at_least",                     # Use KPIDirection enum
    timeframe="Q4 2024",
    frequency="monthly",
    owner="Data Science Team",
    calculation="(Correct predictions / Total predictions) * 100"
)
```

#### 3. AI Agent Integration

Native support for AI agents via Model Context Protocol (MCP):

```python
from open_data_products.odps.models import DataAccessMethod

ai_access = DataAccessMethod(
    output_port_type="AI",           # New AI output port type
    format="MCP",                    # Model Context Protocol
    access_url="mcp://api.example.com/agent",
    specification={
        "protocol": "MCP",
        "version": "1.0",
        "capabilities": ["query", "analyze", "predict"]
    }
)
```

#### 4. Enhanced $ref Support

JSON Reference ($ref) support across 9 components for reusability:

```python
# Internal reference
data_contract = DataContract(
    dollar_ref="#/product/dataContract/default"
)

# External reference
sla = SLA(
    dollar_ref="https://example.com/slas/premium.json"
)
```

**Supported Components:**
- DataContract, SLA, SLAProfile
- DataQuality, DataQualityProfile
- DataAccess, DataAccessMethod
- PaymentGateway, PaymentGateways

#### 5. New Enumerations

```python
from open_data_products.odps.enums import KPIDirection, KPIUnit, OutputPortType

# KPI Direction (5 values)
KPIDirection.INCREASE
KPIDirection.DECREASE
KPIDirection.AT_LEAST
KPIDirection.AT_MOST
KPIDirection.EQUALS

# KPI Unit (19 values)
KPIUnit.PERCENTAGE
KPIUnit.SECONDS
KPIUnit.COUNT
# ... and more

# Output Port Type (updated)
OutputPortType.AI  # New in v4.1
```

### Migration from v4.0

**100% Backward Compatible** - All v4.0 documents continue to work without modification.

All v4.1 features are optional:
- ProductStrategy is optional
- All KPI fields except `name` are optional
- AI output port doesn't affect existing DataAccess
- $ref fields are optional on all components

### Complete v4.1 Example

See [examples/odps_v41_example.py](../examples/odps_v41_example.py) for a comprehensive working example demonstrating all v4.1 features.

---

## Usage Examples

See the [examples directory](../examples/) for comprehensive usage examples:

- `odps_v41_example.py`: **NEW** - Complete v4.1 features demonstration
- `basic_usage.py`: Fundamental operations and features
- `advanced_features.py`: Advanced functionality and customization

For more information, see the [README](../README.md) and [CHANGELOG](../CHANGELOG.md).
