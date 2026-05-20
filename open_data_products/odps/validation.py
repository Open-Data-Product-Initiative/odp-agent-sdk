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
Validation framework with validator pattern for ODPS documents
"""

from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import OpenDataProduct
    from .models import KPI


from .validators import ODPSValidator
from .enums import ProductStatus, ProductVisibility, DataContractType


class ValidationRule(ABC):
    """Abstract base class for validation rules"""

    @abstractmethod
    def validate(self, odp: "OpenDataProduct") -> List[str]:
        """
        Validate an OpenDataProduct instance

        Args:
            odp: OpenDataProduct instance to validate

        Returns:
            List of error messages (empty if valid)
        """
        pass


class RequiredFieldsValidator(ValidationRule):
    """Validates that all required fields are present"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors: List[str] = []

        if not odp.product_details.name:
            errors.append("Product name is required")
        if not odp.product_details.product_id:
            errors.append("Product ID is required")
        if not odp.product_details.visibility:
            errors.append("Product visibility is required")
        if not odp.product_details.status:
            errors.append("Product status is required")
        if not odp.product_details.type:
            errors.append("Product type is required")

        return errors


class EnumFieldsValidator(ValidationRule):
    """Validates enum field values"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors: List[str] = []

        # Validate visibility
        if odp.product_details.visibility not in ProductVisibility.values():
            errors.append(
                f"Invalid visibility. Must be one of: {ProductVisibility.values()}"
            )

        # Validate status
        if odp.product_details.status not in ProductStatus.values():
            errors.append(f"Invalid status. Must be one of: {ProductStatus.values()}")

        # Validate data contract type
        if odp.data_contract and odp.data_contract.type:
            if odp.data_contract.type not in DataContractType.values():
                errors.append(
                    f"Data contract type must be one of: {DataContractType.values()}"
                )

        return errors


class DataAccessValidator(ValidationRule):
    """Validates data access requirements"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors: List[str] = []

        if odp.data_access:
            if not odp.data_access.default:
                errors.append("dataAccess requires a 'default' method")
            else:
                # Validate default method has minimum required fields
                if not odp.data_access.default.output_port_type:
                    errors.append("dataAccess.default requires 'outputPorttype' field")

        return errors


class LicenseValidator(ValidationRule):
    """Validates license requirements"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors = []

        if odp.license:
            if not odp.license.scope_of_use:
                errors.append("license requires 'scopeOfUse' field")

        return errors


class LanguageCodesValidator(ValidationRule):
    """Validates ISO 639-1 language codes"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors = []

        # Validate product details language codes
        lang_errors = ODPSValidator.validate_language_codes(
            odp.product_details.language
        )
        errors.extend(lang_errors)

        # Validate multilingual fields in dataAccess
        if odp.data_access:
            if odp.data_access.default.name:
                name_errors = ODPSValidator.validate_multilingual_dict(
                    odp.data_access.default.name, "dataAccess.default.name"
                )
                errors.extend(name_errors)

            if odp.data_access.default.description:
                desc_errors = ODPSValidator.validate_multilingual_dict(
                    odp.data_access.default.description,
                    "dataAccess.default.description",
                )
                errors.extend(desc_errors)

            # Validate additional methods
            for method_name, method in odp.data_access.additional_methods.items():
                if method.name:
                    name_errors = ODPSValidator.validate_multilingual_dict(
                        method.name, f"dataAccess.{method_name}.name"
                    )
                    errors.extend(name_errors)

                if method.description:
                    desc_errors = ODPSValidator.validate_multilingual_dict(
                        method.description, f"dataAccess.{method_name}.description"
                    )
                    errors.extend(desc_errors)

        return errors


class DataHolderValidator(ValidationRule):
    """Validates data holder information"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors = []

        if odp.data_holder:
            if not ODPSValidator.validate_email(odp.data_holder.email):
                errors.append("dataHolder email must be a valid RFC 5322 email address")
            if odp.data_holder.url and not ODPSValidator.validate_url(
                odp.data_holder.url
            ):
                errors.append("dataHolder url must be a valid RFC 3986 URI")
            if (
                odp.data_holder.phone_number
                and not ODPSValidator.validate_phone_number(
                    odp.data_holder.phone_number
                )
            ):
                errors.append(
                    "dataHolder phoneNumber must be a valid E.164 phone number"
                )

            # Validate additional contact fields
            if (
                odp.data_holder.contact_phone
                and not ODPSValidator.validate_phone_number(
                    odp.data_holder.contact_phone
                )
            ):
                errors.append(
                    "dataHolder contactPhone must be a valid E.164 phone number"
                )

            if odp.data_holder.contact_email and not ODPSValidator.validate_email(
                odp.data_holder.contact_email
            ):
                errors.append(
                    "dataHolder contactEmail must be a valid RFC 5322 email address"
                )

            if (
                odp.data_holder.address_country
                and not ODPSValidator.validate_country_code(
                    odp.data_holder.address_country
                )
            ):
                errors.append(
                    "dataHolder addressCountry must be a valid ISO 3166-1 alpha-2 country code"
                )

        return errors


class URLValidator(ValidationRule):
    """Validates all URL fields"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors = []

        # Product details URLs
        if odp.product_details.homepage and not ODPSValidator.validate_url(
            odp.product_details.homepage
        ):
            errors.append("product homepage must be a valid RFC 3986 URI")
        if odp.product_details.logo_url and not ODPSValidator.validate_url(
            odp.product_details.logo_url
        ):
            errors.append("product logoURL must be a valid RFC 3986 URI")
        if odp.product_details.issues and not ODPSValidator.validate_url(
            odp.product_details.issues
        ):
            errors.append("Product issues must be a valid RFC 3986 URI")
        if odp.product_details.content_sample and not ODPSValidator.validate_url(
            odp.product_details.content_sample
        ):
            errors.append("Product contentSample must be a valid RFC 3986 URI")

        # Validate recommended data products URLs
        for i, url in enumerate(odp.product_details.recommended_data_products):
            if not ODPSValidator.validate_url(url):
                errors.append(
                    f"Recommended data product {i} must be a valid RFC 3986 URI"
                )

        # Component URLs
        if odp.data_contract and odp.data_contract.contract_url:
            if not ODPSValidator.validate_url(odp.data_contract.contract_url):
                errors.append("Data contract contractURL must be a valid RFC 3986 URI")

        # DataAccess URLs
        if odp.data_access:
            if odp.data_access.default.access_url and not ODPSValidator.validate_url(
                odp.data_access.default.access_url
            ):
                errors.append(
                    "dataAccess.default.accessURL must be a valid RFC 3986 URI"
                )
            if odp.data_access.default.specs_url and not ODPSValidator.validate_url(
                odp.data_access.default.specs_url
            ):
                errors.append(
                    "dataAccess.default.specsURL must be a valid RFC 3986 URI"
                )
            if (
                odp.data_access.default.documentation_url
                and not ODPSValidator.validate_url(
                    odp.data_access.default.documentation_url
                )
            ):
                errors.append(
                    "dataAccess.default.documentationURL must be a valid RFC 3986 URI"
                )

            for method_name, method in odp.data_access.additional_methods.items():
                if method.access_url and not ODPSValidator.validate_url(
                    method.access_url
                ):
                    errors.append(
                        f"dataAccess.{method_name}.accessURL must be a valid RFC 3986 URI"
                    )
                if method.specs_url and not ODPSValidator.validate_url(
                    method.specs_url
                ):
                    errors.append(
                        f"dataAccess.{method_name}.specsURL must be a valid RFC 3986 URI"
                    )
                if method.documentation_url and not ODPSValidator.validate_url(
                    method.documentation_url
                ):
                    errors.append(
                        f"dataAccess.{method_name}.documentationURL must be a valid RFC 3986 URI"
                    )

        return errors


class DateValidator(ValidationRule):
    """Validates ISO 8601 date fields"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors = []

        # Product details dates
        if odp.product_details.created and not ODPSValidator.validate_iso8601_date(
            odp.product_details.created
        ):
            errors.append("Product created must be a valid ISO 8601 date")

        if odp.product_details.updated and not ODPSValidator.validate_iso8601_date(
            odp.product_details.updated
        ):
            errors.append("Product updated must be a valid ISO 8601 date")

        # License dates
        if odp.license:
            if odp.license.valid_from and not ODPSValidator.validate_iso8601_date(
                odp.license.valid_from
            ):
                errors.append("license validFrom must be a valid ISO 8601 date")
            if odp.license.valid_until and not ODPSValidator.validate_iso8601_date(
                odp.license.valid_until
            ):
                errors.append("license validUntil must be a valid ISO 8601 date")

        # Pricing plan dates
        if odp.pricing_plans:
            for i, plan in enumerate(odp.pricing_plans.plans):
                if plan.valid_from and not ODPSValidator.validate_iso8601_date(
                    plan.valid_from
                ):
                    errors.append(
                        f"Pricing plan {i} validFrom must be a valid ISO 8601 date"
                    )

                if plan.valid_to and not ODPSValidator.validate_iso8601_date(
                    plan.valid_to
                ):
                    errors.append(
                        f"Pricing plan {i} validTo must be a valid ISO 8601 date"
                    )

        return errors


class PricingPlansValidator(ValidationRule):
    """Validates pricing plans"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors = []

        if odp.pricing_plans:
            for i, plan in enumerate(odp.pricing_plans.plans):
                # Validate currency codes
                if not ODPSValidator.validate_currency_code(plan.price_currency):
                    errors.append(
                        f"Invalid ISO 4217 currency code in pricing plan {i}: '{plan.price_currency}'"
                    )

                # Validate multilingual names
                name_errors = ODPSValidator.validate_pricing_plan_multilingual_name(
                    plan.name
                )
                for error in name_errors:
                    errors.append(f"Pricing plan {i} name: {error}")

                # Validate VAT percentage
                if (
                    plan.value_added_tax is not None
                    and not ODPSValidator.validate_vat_percentage(plan.value_added_tax)
                ):
                    errors.append(
                        f"Pricing plan {i} valueAddedTax must be between 0 and 100"
                    )

        return errors


class UseCasesValidator(ValidationRule):
    """Validates use cases"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors = []

        # Validate use cases
        for i, use_case in enumerate(odp.product_details.use_cases):
            use_case_dict = {
                "title": use_case.title,
                "description": use_case.description,
            }
            if use_case.url:
                use_case_dict["url"] = use_case.url
            use_case_errors = ODPSValidator.validate_use_case(use_case_dict)
            for error in use_case_errors:
                errors.append(f"Use case {i}: {error}")

        return errors


class PaymentGatewaysValidator(ValidationRule):
    """Validates payment gateways"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors = []

        if odp.payment_gateways:
            for i, gateway in enumerate(odp.payment_gateways.gateways):
                # Validate multilingual names
                name_errors = ODPSValidator.validate_payment_gateway_multilingual_name(
                    gateway.name
                )
                for error in name_errors:
                    errors.append(f"Payment gateway {i} name: {error}")

                # Validate multilingual descriptions
                if gateway.description:
                    desc_errors = ODPSValidator.validate_multilingual_dict(
                        gateway.description, f"payment gateway {i} description"
                    )
                    errors.extend(desc_errors)

        return errors


class ExtensionsValidator(ValidationRule):
    """Validates extension fields"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors = []

        if odp.extensions:
            for field_name in odp.extensions.extensions.keys():
                if not ODPSValidator.validate_extension_field_name(field_name):
                    errors.append(
                        f"Extension field '{field_name}' must start with 'x-'"
                    )

        return errors


class ValuePropositionValidator(ValidationRule):
    """Validates value proposition length"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors = []

        if (
            odp.product_details.value_proposition
            and not ODPSValidator.validate_value_proposition_length(
                odp.product_details.value_proposition
            )
        ):
            errors.append("Product valueProposition must be 512 characters or less")

        return errors


class ProductStrategyValidator(ValidationRule):
    """Validates product strategy and KPIs (ODPS v4.1)"""

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        errors: List[str] = []

        if not odp.product_strategy:
            return errors  # Optional component

        ps = odp.product_strategy

        # Validate contributesToKPI
        if ps.contributes_to_kpi:
            kpi_errors = self._validate_kpi(ps.contributes_to_kpi, "contributesToKPI")
            errors.extend(kpi_errors)

        # Validate productKPIs
        for i, kpi in enumerate(ps.product_kpis):
            kpi_errors = self._validate_kpi(kpi, f"productKPIs[{i}]")
            errors.extend(kpi_errors)

        # Validate relatedKPIs
        for i, kpi in enumerate(ps.related_kpis):
            kpi_errors = self._validate_kpi(kpi, f"relatedKPIs[{i}]")
            errors.extend(kpi_errors)

        # Validate objectives (optional but should be list if present)
        if ps.objectives is not None and not isinstance(ps.objectives, list):
            errors.append("productStrategy.objectives must be a list")

        # Validate strategicAlignment (optional but should be list if present)
        if ps.strategic_alignment is not None and not isinstance(
            ps.strategic_alignment, list
        ):
            errors.append("productStrategy.strategicAlignment must be a list")

        return errors

    def _validate_kpi(self, kpi: "KPI", field_name: str) -> List[str]:
        """Validate individual KPI"""
        errors: List[str] = []
        from .enums import KPIDirection, KPIUnit

        # Name is required
        if not kpi.name:
            errors.append(f"{field_name}.name is required")

        # Validate direction if present
        if kpi.direction and kpi.direction not in KPIDirection.values():
            errors.append(
                f"{field_name}.direction must be one of: {KPIDirection.values()}"
            )

        # Validate unit if present
        if kpi.unit and kpi.unit not in KPIUnit.values():
            errors.append(f"{field_name}.unit must be one of: {KPIUnit.values()}")

        return errors


class ODPSValidationFramework:
    """Main validation framework that orchestrates all validation rules"""

    def __init__(self) -> None:
        """Initialize with default set of validation rules"""
        self.validators = [
            RequiredFieldsValidator(),
            EnumFieldsValidator(),
            DataAccessValidator(),
            LicenseValidator(),
            LanguageCodesValidator(),
            DataHolderValidator(),
            URLValidator(),
            DateValidator(),
            PricingPlansValidator(),
            UseCasesValidator(),
            PaymentGatewaysValidator(),
            ExtensionsValidator(),
            ValuePropositionValidator(),
            ProductStrategyValidator(),
        ]

    def add_validator(self, validator: ValidationRule) -> None:
        """Add a custom validator to the framework"""
        self.validators.append(validator)

    def remove_validator(self, validator_class: type) -> None:
        """Remove all validators of the specified class"""
        self.validators = [
            v for v in self.validators if not isinstance(v, validator_class)
        ]

    def validate(self, odp: "OpenDataProduct") -> List[str]:
        """
        Run all validation rules against an OpenDataProduct

        Args:
            odp: OpenDataProduct instance to validate

        Returns:
            List of all error messages from all validators
        """
        all_errors = []

        for validator in self.validators:
            errors = validator.validate(odp)
            all_errors.extend(errors)

        return all_errors
