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
Type protocols for ODPS library to enable better duck typing and type checking.
"""

from typing import Protocol, Optional, List, Dict, Any, Union


class ValidatableProtocol(Protocol):
    """Protocol for objects that can be validated."""

    def validate(self) -> bool:
        """Validate the object and return True if valid."""
        ...


class SerializableProtocol(Protocol):
    """Protocol for objects that can be serialized to dict/JSON/YAML."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert object to dictionary representation."""
        ...

    def to_json(self, indent: int = 2) -> str:
        """Convert object to JSON string."""
        ...


class LoadableProtocol(Protocol):
    """Protocol for objects that can be loaded from external sources."""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoadableProtocol":
        """Create instance from dictionary."""
        ...

    @classmethod
    def from_json(cls, json_str: str) -> "LoadableProtocol":
        """Create instance from JSON string."""
        ...


class ODPSDocumentProtocol(
    ValidatableProtocol, SerializableProtocol, LoadableProtocol, Protocol
):
    """Protocol for complete ODPS documents."""

    schema: str
    version: str

    @property
    def is_valid(self) -> bool:
        """Check if document is valid without raising exceptions."""
        ...

    @property
    def validation_errors(self) -> List[str]:
        """Get validation errors without raising exceptions."""
        ...


class ProductDetailsProtocol(Protocol):
    """Protocol for product details component."""

    name: str
    product_id: str
    visibility: str
    status: str
    type: str
    description: Optional[str]
    categories: List[str]
    tags: List[str]


class DataHolderProtocol(Protocol):
    """Protocol for data holder component."""

    name: str
    email: str
    url: Optional[str]
    phone_number: Optional[str]
    address: Optional[str]


class DataAccessMethodProtocol(Protocol):
    """Protocol for data access methods."""

    name: Optional[str]
    description: Optional[str]
    format: Optional[str]
    access_url: Optional[str]
    authentication_method: Optional[str]


class DataAccessProtocol(Protocol):
    """Protocol for data access component."""

    default: DataAccessMethodProtocol
    additional_methods: Dict[str, DataAccessMethodProtocol]


class LicenseProtocol(Protocol):
    """Protocol for license component."""

    scope_of_use: str
    geographical_area: List[str]
    permanent: bool
    exclusive: bool
    right_to_sublicense: bool
    right_to_modify: bool


class PricingPlanProtocol(Protocol):
    """Protocol for individual pricing plans."""

    name: str
    price_currency: str
    price: Optional[float]
    billing_duration: Optional[str]
    unit: Optional[str]


class PricingPlansProtocol(Protocol):
    """Protocol for pricing plans component."""

    plans: List[PricingPlanProtocol]


class DataContractProtocol(Protocol):
    """Protocol for data contract component."""

    id: Optional[str]
    type: Optional[str]
    url: Optional[str]
    specification: Optional[Dict[str, Any]]


class SLAProtocol(Protocol):
    """Protocol for SLA component."""

    url: Optional[str]
    specification: Optional[Dict[str, Any]]


class DataQualityProtocol(Protocol):
    """Protocol for data quality component."""

    specification: Optional[Dict[str, Any]]


class ValidationRuleProtocol(Protocol):
    """Protocol for validation rules."""

    def validate(self, obj: Any) -> List[str]:
        """Validate an object and return list of error messages."""
        ...


class ValidationFrameworkProtocol(Protocol):
    """Protocol for validation frameworks."""

    def validate(self, obj: Any) -> List[str]:
        """Validate an object using all registered validators."""
        ...

    def add_validator(self, validator: ValidationRuleProtocol) -> None:
        """Add a validator to the framework."""
        ...


class ExtensionProtocol(Protocol):
    """Protocol for specification extensions (x- prefixed fields)."""

    extensions: Dict[str, Any]

    def add_extension(self, key: str, value: Any) -> None:
        """Add an extension field."""
        ...

    def get_extension(self, key: str, default: Any = None) -> Any:
        """Get an extension field value."""
        ...


class UseCaseProtocol(Protocol):
    """Protocol for use case objects."""

    title: str
    description: str
    url: Optional[str]


class PaymentGatewayProtocol(Protocol):
    """Protocol for payment gateway objects."""

    name: str
    description: Optional[str]
    url: Optional[str]
    executable_specifications: Optional[List[str]]


class PaymentGatewaysProtocol(Protocol):
    """Protocol for payment gateways component."""

    gateways: List[PaymentGatewayProtocol]


# Type unions for common protocol combinations
ODPSComponent = Union[
    DataContractProtocol,
    SLAProtocol,
    DataQualityProtocol,
    PricingPlansProtocol,
    LicenseProtocol,
    DataAccessProtocol,
    DataHolderProtocol,
    PaymentGatewaysProtocol,
]

ValidatableComponent = Union[ValidatableProtocol, ODPSComponent]
SerializableComponent = Union[SerializableProtocol, ODPSComponent]


def is_validatable(obj: Any) -> bool:
    """Check if an object implements the ValidatableProtocol."""
    return hasattr(obj, "validate") and callable(getattr(obj, "validate"))


def is_serializable(obj: Any) -> bool:
    """Check if an object implements the SerializableProtocol."""
    return (
        hasattr(obj, "to_dict")
        and callable(getattr(obj, "to_dict"))
        and hasattr(obj, "to_json")
        and callable(getattr(obj, "to_json"))
    )


def is_loadable(obj: Any) -> bool:
    """Check if an object (class) implements the LoadableProtocol."""
    return (
        hasattr(obj, "from_dict")
        and callable(getattr(obj, "from_dict"))
        and hasattr(obj, "from_json")
        and callable(getattr(obj, "from_json"))
    )


def is_odps_component(obj: Any) -> bool:
    """Check if an object is a valid ODPS component."""
    # Check if it has basic component attributes
    required_attrs = (
        ["__dataclass_fields__"] if hasattr(obj, "__dataclass_fields__") else []
    )
    return len(required_attrs) > 0 or any(
        hasattr(obj, attr) for attr in ["name", "specification", "url"]
    )


def validate_protocol_compliance(obj: Any, protocol_name: str) -> List[str]:
    """Validate that an object complies with a specific protocol."""
    errors = []

    if protocol_name == "ValidatableProtocol":
        if not is_validatable(obj):
            errors.append(
                f"Object {type(obj).__name__} does not implement ValidatableProtocol (missing validate method)"
            )

    elif protocol_name == "SerializableProtocol":
        if not is_serializable(obj):
            errors.append(
                f"Object {type(obj).__name__} does not implement SerializableProtocol (missing to_dict or to_json methods)"
            )

    elif protocol_name == "LoadableProtocol":
        if not is_loadable(obj):
            errors.append(
                f"Object {type(obj).__name__} does not implement LoadableProtocol (missing from_dict or from_json class methods)"
            )

    elif protocol_name == "ODPSDocumentProtocol":
        required_attrs = ["schema", "version"]
        for attr in required_attrs:
            if not hasattr(obj, attr):
                errors.append(
                    f"Object {type(obj).__name__} missing required attribute '{attr}' for ODPSDocumentProtocol"
                )

        if not is_validatable(obj):
            errors.append(
                f"Object {type(obj).__name__} does not implement ValidatableProtocol"
            )

        if not is_serializable(obj):
            errors.append(
                f"Object {type(obj).__name__} does not implement SerializableProtocol"
            )

    return errors
