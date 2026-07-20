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
Open Data Product Specification (ODPS) Python Library

A comprehensive, high-performance Python library for creating, validating, and manipulating
Open Data Product Specification (ODPS) v4.1 documents with full international standards compliance.

Features:
    - Complete ODPS v4.1 specification support
    - ProductStrategy for business alignment (new in v4.1)
    - AI agent integration via MCP (new in v4.1)
    - Enhanced $ref support for component referencing (new in v4.1)
    - Full validation with detailed error reporting
    - Element support with international standards (ISO, RFC, ITU-T)
    - Validation caching and optimizations
    - Type-safe protocols and comprehensive error handling
    - JSON and YAML serialization/deserialization
    - Modular architecture with pluggable validators

Quick Start:
    >>> from open_data_products.odps import OpenDataProduct, ProductDetails, ProductStrategy, KPI
    >>>
    >>> # Create product details
    >>> details = ProductDetails(
    ...     name="My Dataset",
    ...     product_id="dataset-001",
    ...     visibility="public",
    ...     status="production",
    ...     type="dataset"
    ... )
    >>>
    >>> # Create ODPS document
    >>> product = OpenDataProduct(details)
    >>>
    >>> # Add product strategy (v4.1)
    >>> strategy = ProductStrategy(
    ...     objectives=["Improve customer retention"],
    ...     product_kpis=[KPI(name="Churn Rate", unit="percentage", target=5)]
    ... )
    >>> product.product_strategy = strategy
    >>>
    >>> # Validate and export
    >>> product.validate()  # True
    >>> json_str = product.to_json()
    >>> product.save("my_product.json")

Main Classes:
    OpenDataProduct: Main class for ODPS documents
    ProductDetails: Core product information model
    ProductStrategy: Business strategy alignment (v4.1)
    KPI: Key Performance Indicator (v4.1)
    ODPSValidator: Validation utilities
    ODPSValidationError: Validation error exception

Modules:
    core: Main OpenDataProduct class and functionality
    models: All ODPS component data models
    validation: Validation framework, rules, and utilities
    validators: Compatibility wrapper for ODPSValidator
    protocols: Type protocols for duck typing
    enums: Enumeration classes for constants
    exceptions: Exception hierarchy

For detailed documentation, see: https://github.com/Open-Data-Product-Initiative/odps-python
For ODPS specification: https://opendataproducts.org/v4.1/
"""

__version__ = "0.3.5"
SPEC_ID = "odps"
SPEC_NAME = "Open Data Product Specification"

from .core import OpenDataProduct
from .models import *
from .validation import ODPSValidator
from .enums import *
from .exceptions import *
from .protocols import *

__all__ = sorted(name for name in globals() if not name.startswith("_"))
