# Copyright 2024 ODPS Python Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Core OpenDataProduct class for handling ODPS documents.

This module provides the main OpenDataProduct class that implements the Open Data Product
Specification (ODPS) v4.1. It supports creating, loading, validating, and manipulating
ODPS documents with full element compliance to appropriate international standards.

Key Features:
    - Full ODPS v4.1 specification compliance
    - JSON and YAML serialization/deserialization
    - Comprehensive validation with detailed error reporting
    - Performance optimizations with caching and __slots__
    - Protocol-based duck typing for better type safety
    - Modular component architecture

Example:
    Basic usage of OpenDataProduct:

    >>> from open_data_products.odps import OpenDataProduct, ProductDetails
    >>> details = ProductDetails(
    ...     name="My Data Product",
    ...     product_id="dp-001",
    ...     visibility="public",
    ...     status="draft",
    ...     type="dataset"
    ... )
    >>> product = OpenDataProduct(details)
    >>> product.validate()
    True
    >>> json_output = product.to_json()

Classes:
    OpenDataProduct: Main class for handling ODPS documents

See Also:
    - models.py: Data model classes for ODPS components
    - validation.py: Validation framework and rules
    - protocols.py: Type protocols for duck typing
"""

import json
import yaml
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from .models import (
    ProductDetails,
    ProductStrategy,
    DataContract,
    SLA,
    DataQuality,
    PricingPlans,
    License,
    DataAccess,
    DataAccessMethod,
    DataHolder,
    PaymentGateways,
    SpecificationExtensions,
)
from .codecs import (
    parse_data_access,
    parse_data_contract,
    parse_data_holder,
    parse_data_quality,
    parse_extensions,
    parse_license,
    parse_payment_gateways,
    parse_pricing_plans,
    parse_product_details,
    parse_product_strategy,
    parse_sla,
)
from ._document import build_document
from .validation import ODPSValidationFramework
from ._state import (
    clear_caches,
    component_count,
    generate_hash,
    has_optional_components,
)
from .exceptions import (
    ODPSValidationError,
    ODPSJSONParsingError,
    ODPSYAMLParsingError,
    ODPSFileNotFoundError,
)
from .protocols import is_validatable, validate_protocol_compliance


class OpenDataProduct:
    """
    Main class for handling Open Data Product Specification (ODPS) v4.1 documents.

    This class provides comprehensive support for creating, loading, validating, and
    manipulating ODPS documents. It implements the full ODPS v4.1 specification with
    performance optimizations and type safety.

    The class supports all ODPS components including:
    - Product Details (required)
    - Data Contract (optional)
    - Service Level Agreement (SLA) (optional)
    - Data Quality specifications (optional)
    - Pricing Plans (optional)
    - License information (optional)
    - Data Access methods (optional)
    - Data Holder information (optional)
    - Payment Gateways (optional)
    - Custom Extensions (optional)

    Attributes:
        schema (str): ODPS schema URL (https://opendataproducts.org/v4.1/schema/odps.json)
        version (str): ODPS version (4.1)
        product_details (ProductDetails): Core product information (required)
        data_contract (DataContract, optional): Data contract specifications
        sla (SLA, optional): Service level agreement
        data_quality (DataQuality, optional): Data quality specifications
        pricing_plans (PricingPlans, optional): Pricing information
        license (License, optional): License terms and conditions
        data_access (DataAccess, optional): Data access methods and endpoints
        data_holder (DataHolder, optional): Data holder/provider information
        payment_gateways (PaymentGateways, optional): Payment processing information
        extensions (SpecificationExtensions, optional): Custom extension fields

    Performance Features:
        - Validation result caching for repeated validation calls
        - Serialization caching for JSON/YAML output
        - __slots__ for memory efficiency
        - Automatic cache invalidation when object state changes

    Example:
        Creating a basic ODPS document:

        >>> from open_data_products.odps import OpenDataProduct, ProductDetails
        >>> details = ProductDetails(
        ...     name="Customer Demographics Dataset",
        ...     product_id="cust-demo-001",
        ...     visibility="public",
        ...     status="production",
        ...     type="dataset",
        ...     description="Anonymized customer demographic data"
        ... )
        >>> product = OpenDataProduct(details)
        >>>
        >>> # Add optional components
        >>> from open_data_products.odps.models import License
        >>> product.add_license(
        ...     scope_of_use="commercial",
        ...     geographical_area=["US", "EU"]
        ... )
        >>>
        >>> # Validate and export
        >>> is_valid = product.validate()  # True
        >>> json_str = product.to_json()
        >>> product.save("my_data_product.json")

        Loading from existing document:

        >>> product = OpenDataProduct.from_file("existing_product.json")
        >>> compliance_level = product.compliance_level  # "full", "substantial", etc.
        >>> has_license = product.license is not None

    Note:
        All appropriate element validation follows international standards including:
        - ISO 639-1 (language codes)
        - ISO 3166-1 (country codes)
        - ISO 4217 (currency codes)
        - ISO 8601 (date/time formats)
        - RFC 5322 (email addresses)
        - RFC 3986 (URIs)
        - ITU-T E.164 (phone numbers)
    """

    __slots__ = [
        "schema",
        "version",
        "product_details",
        "product_strategy",
        "data_contract",
        "sla",
        "data_quality",
        "pricing_plans",
        "license",
        "data_access",
        "data_holder",
        "payment_gateways",
        "extensions",
        "_validation_cache",
        "_serialization_cache",
        "_hash_cache",
    ]

    REQUIRED_SCHEMA = "https://opendataproducts.org/v4.1/schema/odps.json"
    REQUIRED_VERSION = "4.1"
    _validation_cache: Dict[str, Any]
    _serialization_cache: Dict[Any, str]
    _hash_cache: Optional[str]

    def _generate_hash(self) -> str:
        """Generate hash of current object state for cache invalidation."""
        if self._hash_cache is None:
            self._hash_cache = generate_hash(self)
        return self._hash_cache

    def _invalidate_cache(self) -> None:
        """Invalidate all caches when object state changes."""
        clear_caches(self._validation_cache, self._serialization_cache)
        self._hash_cache = None

    def __init__(self, product_details: ProductDetails):
        """
        Initialize with mandatory product details

        Args:
            product_details: ProductDetails instance with core product info
        """
        self.schema = self.REQUIRED_SCHEMA
        self.version = self.REQUIRED_VERSION
        self.product_details = product_details

        # Optional components
        self.product_strategy: Optional[ProductStrategy] = None  # New in v4.1
        self.data_contract: Optional[DataContract] = None
        self.sla: Optional[SLA] = None
        self.data_quality: Optional[DataQuality] = None
        self.pricing_plans: Optional[PricingPlans] = None
        self.license: Optional[License] = None
        self.data_access: Optional[DataAccess] = None
        self.data_holder: Optional[DataHolder] = None
        self.payment_gateways: Optional[PaymentGateways] = None
        self.extensions: Optional[SpecificationExtensions] = None

        # Performance caches
        self._validation_cache: Dict[str, Any] = {}
        self._serialization_cache: Dict[Any, str] = {}
        self._hash_cache: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpenDataProduct":
        """
        Create OpenDataProduct from dictionary

        Args:
            data: Dictionary containing ODPS document data

        Returns:
            OpenDataProduct instance
        """
        # Extract and validate core fields
        schema = data.get("schema")
        version = data.get("version")
        product_data = data.get("product", {})

        if not product_data:
            raise ODPSValidationError("Missing required 'product' section")

        product_details = parse_product_details(product_data)

        instance = cls(product_details)
        instance.schema = schema or cls.REQUIRED_SCHEMA
        instance.version = version or cls.REQUIRED_VERSION

        # Load product strategy (v4.1)
        if "productStrategy" in product_data:
            instance.product_strategy = parse_product_strategy(
                product_data["productStrategy"]
            )

        # Load data holder
        if "dataHolder" in product_data:
            instance.data_holder = parse_data_holder(product_data["dataHolder"])

        # Load pricing plans
        if "pricingPlans" in product_data:
            instance.pricing_plans = parse_pricing_plans(product_data["pricingPlans"])

        # Load optional components
        if "dataContract" in product_data:
            instance.data_contract = parse_data_contract(product_data["dataContract"])

        if "SLA" in product_data:
            instance.sla = parse_sla(product_data["SLA"])

        if "dataQuality" in product_data:
            instance.data_quality = parse_data_quality(product_data["dataQuality"])

        if "dataAccess" in product_data:
            da_data = product_data["dataAccess"]
            instance.data_access = parse_data_access(da_data)

        if "license" in product_data:
            instance.license = parse_license(product_data["license"])

        if "paymentGateways" in product_data:
            instance.payment_gateways = parse_payment_gateways(
                product_data["paymentGateways"]
            )

        # Load extensions (x- prefixed fields)
        extensions = parse_extensions(product_data)

        if extensions.extensions:
            instance.extensions = extensions

        return instance

    @classmethod
    def from_json(cls, json_str: str) -> "OpenDataProduct":
        """Load from JSON string"""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ODPSJSONParsingError(str(e))

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "OpenDataProduct":
        """Load from YAML string"""
        try:
            data = yaml.safe_load(yaml_str)
            return cls.from_dict(data)
        except yaml.YAMLError as e:
            raise ODPSYAMLParsingError(str(e))

    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> "OpenDataProduct":
        """Load from file (JSON or YAML)"""
        path = Path(file_path)

        if not path.exists():
            raise ODPSFileNotFoundError(str(file_path))

        content = path.read_text(encoding="utf-8")

        if path.suffix.lower() in [".json"]:
            return cls.from_json(content)
        elif path.suffix.lower() in [".yaml", ".yml"]:
            return cls.from_yaml(content)
        else:
            # Try JSON first, then YAML
            try:
                return cls.from_json(content)
            except (ODPSJSONParsingError, ODPSValidationError):
                return cls.from_yaml(content)

    def validate(self) -> bool:
        """
        Validate the ODPS document using the validation framework

        Returns:
            True if valid

        Raises:
            ODPSValidationError: If validation fails
        """
        # Check cache first
        current_hash = self._generate_hash()
        if current_hash in self._validation_cache:
            cached_result = self._validation_cache[current_hash]
            if cached_result.get("errors"):
                raise ODPSValidationError(cached_result["errors"])
            return bool(cached_result.get("valid", False))

        # First check protocol compliance
        protocol_errors = validate_protocol_compliance(self, "ODPSDocumentProtocol")
        if protocol_errors:
            error_msg = f"Protocol compliance errors: {'; '.join(protocol_errors)}"
            self._validation_cache[current_hash] = {"valid": False, "errors": error_msg}
            raise ODPSValidationError(error_msg)

        # Then run standard validation
        validator = ODPSValidationFramework()
        errors = validator.validate(self)

        if errors:
            error_msg = f"Validation errors: {'; '.join(errors)}"
            self._validation_cache[current_hash] = {"valid": False, "errors": error_msg}
            raise ODPSValidationError(error_msg)

        # Cache successful validation
        self._validation_cache[current_hash] = {"valid": True, "errors": None}
        return True

    @property
    def is_valid(self) -> bool:
        """Check if document is valid without raising exceptions."""
        try:
            self.validate()
            return True
        except ODPSValidationError:
            return False

    @property
    def validation_errors(self) -> List[str]:
        """Get list of validation errors without raising exceptions."""
        try:
            self.validate()
            return []
        except ODPSValidationError as e:
            # Extract error messages from the exception string
            error_msg = str(e)
            if ": " in error_msg:
                errors_part = error_msg.split(": ", 1)[1]
                return errors_part.split("; ")
            return [error_msg]

    @property
    def has_optional_components(self) -> bool:
        """Check if document has any optional components."""
        return has_optional_components(self)

    @property
    def component_count(self) -> int:
        """Count of non-None optional components."""
        return component_count(self)

    @property
    def is_production_ready(self) -> bool:
        """Check if document is ready for production (valid + has required components)."""
        if not self.is_valid:
            return False

        # Production-ready typically means having at least data access
        return self.data_access is not None

    @property
    def compliance_level(self) -> str:
        """Get compliance level based on components present."""
        if not self.is_valid:
            return "invalid"

        required_for_full = {
            "data_access": self.data_access is not None,
            "license": self.license is not None,
            "data_holder": self.data_holder is not None,
        }

        present_count = sum(required_for_full.values())

        if present_count == 3:
            return "full"
        elif present_count >= 2:
            return "substantial"
        elif present_count >= 1:
            return "basic"
        else:
            return "minimal"

    def check_component_protocols(self) -> Dict[str, bool]:
        """Check if all components follow their respective protocols."""
        results = {
            "product_details": (
                is_validatable(self.product_details)
                if hasattr(self.product_details, "validate")
                else True
            ),
            "data_contract": (
                is_validatable(self.data_contract)
                if self.data_contract and hasattr(self.data_contract, "validate")
                else True
            ),
            "sla": (
                is_validatable(self.sla)
                if self.sla and hasattr(self.sla, "validate")
                else True
            ),
            "data_quality": (
                is_validatable(self.data_quality)
                if self.data_quality and hasattr(self.data_quality, "validate")
                else True
            ),
            "pricing_plans": (
                is_validatable(self.pricing_plans)
                if self.pricing_plans and hasattr(self.pricing_plans, "validate")
                else True
            ),
            "license": (
                is_validatable(self.license)
                if self.license and hasattr(self.license, "validate")
                else True
            ),
            "data_access": (
                is_validatable(self.data_access)
                if self.data_access and hasattr(self.data_access, "validate")
                else True
            ),
            "data_holder": (
                is_validatable(self.data_holder)
                if self.data_holder and hasattr(self.data_holder, "validate")
                else True
            ),
            "payment_gateways": (
                is_validatable(self.payment_gateways)
                if self.payment_gateways and hasattr(self.payment_gateways, "validate")
                else True
            ),
        }
        return results

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return build_document(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string with caching"""
        current_hash = self._generate_hash()
        cache_key = (current_hash, "json", indent)

        if cache_key in self._serialization_cache:
            return self._serialization_cache[cache_key]

        result = json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
        self._serialization_cache[cache_key] = result
        return result

    def to_yaml(self) -> str:
        """Convert to YAML string with caching"""
        current_hash = self._generate_hash()
        cache_key = (current_hash, "yaml")

        if cache_key in self._serialization_cache:
            return self._serialization_cache[cache_key]

        result = yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True)
        self._serialization_cache[cache_key] = result
        return result

    def save(self, file_path: Union[str, Path], format: str = "auto") -> None:
        """
        Save to file

        Args:
            file_path: Path to save file
            format: Format to use ('json', 'yaml', or 'auto' to detect from extension)
        """
        path = Path(file_path)

        if format == "auto":
            if path.suffix.lower() in [".yaml", ".yml"]:
                format = "yaml"
            else:
                format = "json"

        if format == "yaml":
            content = self.to_yaml()
        else:
            content = self.to_json()

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def add_data_contract(
        self,
        contract_url: Optional[str] = None,
        spec: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
        type: Optional[str] = None,
        contract_version: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> None:
        """Add or update data contract"""
        self.data_contract = DataContract(
            id=id,
            type=type,
            contract_version=contract_version,
            contract_url=contract_url,
            spec=spec,
            ref=ref,
        )
        self._invalidate_cache()

    def add_sla(self, profiles: Optional[Dict[str, Any]] = None) -> None:
        """Add or update SLA"""
        if profiles is None:
            profiles = {}
        self.sla = SLA(profiles=profiles)
        self._invalidate_cache()

    def add_license(self, scope_of_use: str, **kwargs: Any) -> None:
        """Add or update license"""
        self.license = License(scope_of_use=scope_of_use, **kwargs)
        self._invalidate_cache()

    def add_data_access(
        self, default_method: DataAccessMethod, **additional_methods: DataAccessMethod
    ) -> None:
        """Add or update data access methods"""
        self.data_access = DataAccess(
            default=default_method, additional_methods=additional_methods
        )
        self._invalidate_cache()

    def __str__(self) -> str:
        return f"OpenDataProduct(name='{self.product_details.name}', id='{self.product_details.product_id}')"

    def __repr__(self) -> str:
        return self.__str__()
