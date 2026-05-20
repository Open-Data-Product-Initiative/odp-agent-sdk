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

"""Internal validation utilities for ODPS field values."""

import re
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from ._iso_codes import ISO_639_1, ISO_3166_1_ALPHA_2, ISO_4217

# E.164: leading +, country digit 1-9, then up to 14 more digits.
_E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")


class ODPSValidator:
    """Validation utilities for ODPS specification compliance"""

    @staticmethod
    def validate_iso639_language_code(code: str) -> bool:
        """
        Validate ISO 639-1 language code (2-letter)

        Args:
            code: Language code to validate

        Returns:
            True if valid ISO 639-1 code
        """
        if not isinstance(code, str) or len(code) != 2:
            return False
        return code.lower() in ISO_639_1

    @staticmethod
    def validate_language_codes(codes: List[str]) -> List[str]:
        """
        Validate list of ISO 639-1 language codes

        Args:
            codes: List of language codes to validate

        Returns:
            List of invalid codes (empty if all valid)
        """
        if not isinstance(codes, list):
            return ["Language codes must be a list"]

        invalid_codes = []
        for code in codes:
            if not ODPSValidator.validate_iso639_language_code(code):
                invalid_codes.append(f"Invalid ISO 639-1 language code: '{code}'")

        return invalid_codes

    @staticmethod
    def validate_multilingual_dict(
        data: Dict[str, Any], field_name: str = "field"
    ) -> List[str]:
        """
        Validate multilingual dictionary with ISO 639-1 keys

        Args:
            data: Dictionary with language codes as keys
            field_name: Name of field for error messages

        Returns:
            List of validation errors (empty if valid)
        """
        if not isinstance(data, dict):
            return [f"{field_name} must be a dictionary with language codes as keys"]

        errors = []
        for lang_code in data.keys():
            if not ODPSValidator.validate_iso639_language_code(lang_code):
                errors.append(
                    f"Invalid ISO 639-1 language code in {field_name}: '{lang_code}'"
                )

        return errors

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        URL validation (uses enhanced RFC 3986 validation for HTTP/HTTPS)

        Args:
            url: URL to validate

        Returns:
            True if valid URL format
        """
        if not isinstance(url, str):
            return False

        # Check if it's HTTP/HTTPS and use RFC 3986 validation
        if url.lower().startswith(("http://", "https://")):
            return ODPSValidator.validate_rfc3986_uri(url)

        # Fallback for other schemes
        return ODPSValidator.validate_rfc3986_uri(url)

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Email validation (uses enhanced RFC 5322 validation)

        Args:
            email: Email to validate

        Returns:
            True if valid email format
        """
        return ODPSValidator.validate_rfc5322_email(email)

    @staticmethod
    def validate_currency_code(code: str) -> bool:
        """
        Validate ISO 4217 currency code

        Args:
            code: Currency code to validate

        Returns:
            True if valid ISO 4217 code
        """
        if not isinstance(code, str) or len(code) != 3:
            return False
        return code.upper() in ISO_4217

    @staticmethod
    def validate_country_code(code: str) -> bool:
        """
        Validate ISO 3166-1 alpha-2 country code

        Args:
            code: Country code to validate

        Returns:
            True if valid ISO 3166-1 alpha-2 code
        """
        if not isinstance(code, str) or len(code) != 2:
            return False
        return code.upper() in ISO_3166_1_ALPHA_2

    @staticmethod
    def validate_phone_number(phone: str, country_code: Optional[str] = None) -> bool:
        """
        Validate E.164 phone number format

        Args:
            phone: Phone number to validate
            country_code: Optional ISO 3166-1 alpha-2 country code for context

        Returns:
            True if valid E.164 format
        """
        if not isinstance(phone, str):
            return False
        return bool(_E164_RE.match(phone))

    @staticmethod
    def validate_iso8601_date(date_str: str) -> bool:
        """
        Validate ISO 8601 date/datetime format

        Args:
            date_str: Date string to validate

        Returns:
            True if valid ISO 8601 format
        """
        if not isinstance(date_str, str):
            return False

        # Common ISO 8601 patterns
        iso_patterns = [
            r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",  # YYYY-MM-DDTHH:MM:SS
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",  # YYYY-MM-DDTHH:MM:SSZ
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$",  # YYYY-MM-DDTHH:MM:SS±HH:MM
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+$",  # YYYY-MM-DDTHH:MM:SS.fff
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z$",  # YYYY-MM-DDTHH:MM:SS.fffZ
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+[+-]\d{2}:\d{2}$",  # YYYY-MM-DDTHH:MM:SS.fff±HH:MM
        ]

        for pattern in iso_patterns:
            if re.match(pattern, date_str):
                try:
                    # Additional validation by parsing
                    datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    return True
                except ValueError:
                    continue

        return False

    @staticmethod
    def validate_rfc5322_email(email: str) -> bool:
        """
        Enhanced RFC 5322 compliant email validation

        Args:
            email: Email to validate

        Returns:
            True if valid RFC 5322 email format
        """
        if not isinstance(email, str):
            return False

        # More comprehensive RFC 5322 pattern
        rfc5322_pattern = re.compile(
            r"^[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+)*"
            r"@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)"
            r"+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$"
        )

        return bool(rfc5322_pattern.match(email))

    @staticmethod
    def validate_rfc3986_uri(uri: str) -> bool:
        """
        Enhanced RFC 3986 compliant URI validation

        Args:
            uri: URI to validate

        Returns:
            True if valid RFC 3986 URI format
        """
        if not isinstance(uri, str):
            return False

        # RFC 3986 URI pattern
        rfc3986_pattern = re.compile(
            r"^[a-zA-Z][a-zA-Z0-9+.-]*:"  # scheme
            r"(?://"  # authority start
            r"(?:[a-zA-Z0-9._~!$&\'()*+,;=:-]|%[0-9a-fA-F]{2})*"  # userinfo
            r"@?"  # @ separator
            r"(?:\[[0-9a-fA-F:.]+\]|[a-zA-Z0-9._~!$&\'()*+,;=-]|%[0-9a-fA-F]{2})*"  # host
            r"(?::[0-9]*)?"  # port
            r")?"  # authority end
            r"(?:[a-zA-Z0-9._~!$&\'()*+,;=:@/%-]|%[0-9a-fA-F]{2})*"  # path
            r"(?:\?(?:[a-zA-Z0-9._~!$&\'()*+,;=:@/?%-]|%[0-9a-fA-F]{2})*)?"  # query
            r"(?:#(?:[a-zA-Z0-9._~!$&\'()*+,;=:@/?%-]|%[0-9a-fA-F]{2})*)?$",  # fragment
            re.IGNORECASE,
        )

        return bool(rfc3986_pattern.match(uri))

    @staticmethod
    def validate_value_proposition_length(value_proposition: str) -> bool:
        """Validate value proposition length (max 512 chars according to spec)"""
        if not isinstance(value_proposition, str):
            return False
        return len(value_proposition) <= 512

    @staticmethod
    def validate_data_contract_type(contract_type: str) -> bool:
        """Validate data contract type (ODCS or DCS)"""
        if not isinstance(contract_type, str):
            return False
        return contract_type.upper() in ["ODCS", "DCS"]

    @staticmethod
    def validate_use_case(use_case: dict) -> List[str]:
        """Validate use case structure"""
        errors = []
        if not isinstance(use_case, dict):
            return ["Use case must be a dictionary"]

        if "title" not in use_case or not isinstance(use_case["title"], str):
            errors.append("Use case must have a 'title' field")

        if "description" not in use_case or not isinstance(
            use_case["description"], str
        ):
            errors.append("Use case must have a 'description' field")

        if (
            "url" in use_case
            and use_case["url"]
            and not ODPSValidator.validate_url(use_case["url"])
        ):
            errors.append("Use case URL must be a valid RFC 3986 URI")

        return errors

    @staticmethod
    def validate_pricing_plan_multilingual_name(
        name: Union[str, Dict[str, str]],
    ) -> List[str]:
        """Validate pricing plan name (string or multilingual dict)"""
        if isinstance(name, str):
            return []  # Simple string is valid
        elif isinstance(name, dict):
            return ODPSValidator.validate_multilingual_dict(name, "pricing plan name")
        else:
            return ["Pricing plan name must be a string or multilingual dictionary"]

    @staticmethod
    def validate_payment_gateway_multilingual_name(
        name: Union[str, Dict[str, str]],
    ) -> List[str]:
        """Validate payment gateway name (string or multilingual dict)"""
        if isinstance(name, str):
            return []  # Simple string is valid
        elif isinstance(name, dict):
            return ODPSValidator.validate_multilingual_dict(
                name, "payment gateway name"
            )
        else:
            return ["Payment gateway name must be a string or multilingual dictionary"]

    @staticmethod
    def validate_extension_field_name(field_name: str) -> bool:
        """Validate that extension field name starts with 'x-'"""
        if not isinstance(field_name, str):
            return False
        return field_name.startswith("x-")

    @staticmethod
    def validate_vat_percentage(vat: float) -> bool:
        """Validate VAT percentage (0-100)"""
        if not isinstance(vat, (int, float)):
            return False
        return 0 <= vat <= 100
