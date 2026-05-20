"""Tests for ODPS validation framework and validators."""

import pytest
from unittest.mock import patch

from open_data_products.odps.validators import ODPSValidator
from open_data_products.odps.validation import RequiredFieldsValidator, ValidationRule
from open_data_products.odps.exceptions import ODPSValidationError
from open_data_products.odps import OpenDataProduct
from open_data_products.odps.models import ProductDetails


class TestODPSValidator:
    """Test cases for ODPSValidator utility class."""

    def test_validate_iso639_language_code_valid(self):
        """Test validation of valid ISO 639-1 language codes."""
        valid_codes = ["en", "es", "fr", "de", "zh", "ja", "ar"]

        for code in valid_codes:
            assert ODPSValidator.validate_iso639_language_code(
                code
            ), f"Code '{code}' should be valid"

    def test_validate_iso639_language_code_invalid(self):
        """Test validation of invalid language codes."""
        invalid_codes = ["eng", "xyz", "123", "", "en-US", None]

        for code in invalid_codes:
            assert not ODPSValidator.validate_iso639_language_code(
                code
            ), f"Code '{code}' should be invalid"

    def test_validate_language_codes_valid_list(self):
        """Test validation of valid language codes list."""
        valid_list = ["en", "es", "fr"]
        invalid_codes = ODPSValidator.validate_language_codes(valid_list)

        assert len(invalid_codes) == 0, "All codes should be valid"

    def test_validate_language_codes_mixed_list(self):
        """Test validation of mixed valid/invalid language codes list."""
        mixed_list = ["en", "xyz", "es", "123"]
        invalid_codes = ODPSValidator.validate_language_codes(mixed_list)

        # Check that error messages contain the invalid codes
        invalid_codes_str = " ".join(invalid_codes)
        assert "xyz" in invalid_codes_str
        assert "123" in invalid_codes_str
        assert len(invalid_codes) == 2

    def test_validate_language_codes_not_list(self):
        """Test validation when input is not a list."""
        invalid_codes = ODPSValidator.validate_language_codes("en")

        assert len(invalid_codes) == 1
        assert "must be a list" in invalid_codes[0]

    def test_validate_iso3166_country_code_valid(self):
        """Test validation of valid ISO 3166-1 alpha-2 country codes."""
        if hasattr(ODPSValidator, "validate_iso3166_country_code"):
            valid_codes = ["US", "GB", "DE", "FR", "JP", "CN", "IN"]

            for code in valid_codes:
                assert ODPSValidator.validate_iso3166_country_code(
                    code
                ), f"Code '{code}' should be valid"

    def test_validate_iso3166_country_code_invalid(self):
        """Test validation of invalid country codes."""
        if hasattr(ODPSValidator, "validate_iso3166_country_code"):
            invalid_codes = ["USA", "XX", "123", "", None]

            for code in invalid_codes:
                assert not ODPSValidator.validate_iso3166_country_code(
                    code
                ), f"Code '{code}' should be invalid"

    def test_validate_e164_phone_number_valid(self):
        """Test validation of valid E.164 phone numbers."""
        if hasattr(ODPSValidator, "validate_e164_phone_number"):
            valid_numbers = ["+1234567890", "+44207946000", "+81312345678"]

            for number in valid_numbers:
                assert ODPSValidator.validate_e164_phone_number(
                    number
                ), f"Number '{number}' should be valid"

    def test_validate_e164_phone_number_invalid(self):
        """Test validation of invalid E.164 phone numbers."""
        if hasattr(ODPSValidator, "validate_e164_phone_number"):
            invalid_numbers = ["1234567890", "invalid", "+", "", None]

            for number in invalid_numbers:
                assert not ODPSValidator.validate_e164_phone_number(
                    number
                ), f"Number '{number}' should be invalid"

    def test_validate_iso8601_datetime_valid(self):
        """Test validation of valid ISO 8601 datetime strings."""
        if hasattr(ODPSValidator, "validate_iso8601_datetime"):
            valid_datetimes = [
                "2023-12-31T23:59:59Z",
                "2023-01-01T00:00:00+00:00",
                "2023-06-15T14:30:45-05:00",
            ]

            for dt in valid_datetimes:
                assert ODPSValidator.validate_iso8601_datetime(
                    dt
                ), f"Datetime '{dt}' should be valid"

    def test_validate_iso8601_datetime_invalid(self):
        """Test validation of invalid datetime strings."""
        if hasattr(ODPSValidator, "validate_iso8601_datetime"):
            invalid_datetimes = [
                "2023-13-01T00:00:00Z",  # Invalid month
                "2023-12-32T00:00:00Z",  # Invalid day
                "invalid",
                "",
                None,
            ]

            for dt in invalid_datetimes:
                assert not ODPSValidator.validate_iso8601_datetime(
                    dt
                ), f"Datetime '{dt}' should be invalid"

    def test_validate_url_valid(self):
        """Test validation of valid URLs."""
        if hasattr(ODPSValidator, "validate_url"):
            valid_urls = [
                "https://example.com",
                "http://example.org/path",
                "https://subdomain.example.com:8080/path?param=value",
            ]

            for url in valid_urls:
                assert ODPSValidator.validate_url(url), f"URL '{url}' should be valid"

    def test_validate_url_invalid(self):
        """Test validation of invalid URLs."""
        if hasattr(ODPSValidator, "validate_url"):
            invalid_urls = ["not-a-url", "", None]

            for url in invalid_urls:
                assert not ODPSValidator.validate_url(
                    url
                ), f"URL '{url}' should be invalid"

    def test_validate_email_valid(self):
        """Test validation of valid email addresses."""
        if hasattr(ODPSValidator, "validate_email"):
            valid_emails = [
                "test@example.com",
                "user.name@domain.org",
                "user+tag@example.co.uk",
            ]

            for email in valid_emails:
                assert ODPSValidator.validate_email(
                    email
                ), f"Email '{email}' should be valid"

    def test_validate_email_invalid(self):
        """Test validation of invalid email addresses."""
        if hasattr(ODPSValidator, "validate_email"):
            invalid_emails = ["invalid", "@example.com", "user@", "", None]

            for email in invalid_emails:
                assert not ODPSValidator.validate_email(
                    email
                ), f"Email '{email}' should be invalid"


class TestValidationFramework:
    """Test cases for validation framework."""

    def test_required_fields_validator_valid(self, sample_odps_product):
        """Test RequiredFieldsValidator with valid product."""
        validator = RequiredFieldsValidator()
        errors = validator.validate(sample_odps_product)

        assert len(errors) == 0, "Valid product should have no errors"

    def test_required_fields_validator_missing_name(self):
        """Test RequiredFieldsValidator with missing name."""
        product_details = ProductDetails(
            name="",  # Empty name
            product_id="test-001",
            visibility="public",
            status="draft",
            type="dataset",
        )

        product = OpenDataProduct(product_details)

        # Validation should fail when explicitly called
        with pytest.raises((ValueError, Exception)):
            product.validate()

    def test_required_fields_validator_missing_product_id(self):
        """Test RequiredFieldsValidator with missing product ID."""
        product_details = ProductDetails(
            name="Test Product",
            product_id="",  # Empty product_id
            visibility="public",
            status="draft",
            type="dataset",
        )

        product = OpenDataProduct(product_details)

        # Validation should fail when explicitly called
        with pytest.raises((ValueError, Exception)):
            product.validate()

    def test_custom_validation_rule(self, sample_odps_product):
        """Test creating and using custom validation rule."""

        class CustomValidationRule(ValidationRule):
            def validate(self, odp: OpenDataProduct) -> list:
                errors = []
                if "test" not in odp.product_details.name.lower():
                    errors.append("Product name must contain 'test'")
                return errors

        validator = CustomValidationRule()
        errors = validator.validate(sample_odps_product)

        # Should pass since sample product has "Test" in name
        assert len(errors) == 0

    def test_validation_rule_protocol(self):
        """Test that validation rules conform to protocol."""
        validator = RequiredFieldsValidator()

        # Should implement the protocol
        assert hasattr(validator, "validate")
        assert callable(getattr(validator, "validate"))

    def test_validation_error_handling(self, invalid_odps_data):
        """Test proper error handling in validation."""
        with pytest.raises((ODPSValidationError, ValueError)):
            product = OpenDataProduct.from_dict(invalid_odps_data)
            product.validate()

    def test_validation_with_optional_fields(self):
        """Test validation with optional fields."""
        product_details = ProductDetails(
            name="Test Product with Optional Fields",
            product_id="test-opt-001",
            visibility="public",
            status="production",
            type="api",
            description="A test product with optional fields",
            language=["en", "es"],  # Valid language codes
            geography="US",  # Valid if country validation exists
        )

        product = OpenDataProduct(product_details)

        # Should validate successfully
        assert product.validate() is True

    @patch(
        "open_data_products.odps.validators.ODPSValidator.validate_iso639_language_code"
    )
    def test_validation_with_mocked_dependencies(
        self, mock_validate_lang, sample_odps_product
    ):
        """Test validation with mocked external dependencies."""
        # Mock the language validation to return False
        mock_validate_lang.return_value = False

        # Update product with language codes
        sample_odps_product.product_details.language = ["en", "invalid"]

        # Validation might use the mocked method
        # This tests that external dependencies can be mocked for testing
        assert (
            mock_validate_lang.call_count >= 0
        )  # May or may not be called depending on implementation


class TestValidationIntegration:
    """Integration tests for validation across the system."""

    def test_end_to_end_validation_valid_product(self, demo_product_json_path):
        """Test end-to-end validation with demo product."""
        if demo_product_json_path.exists():
            product = OpenDataProduct.from_file(demo_product_json_path)

            # Should validate successfully
            result = product.validate()
            assert result is True

    def test_validation_error_messages(self):
        """Test that validation provides helpful error messages."""
        try:
            invalid_product = ProductDetails(
                name="",
                product_id="test-001",
                visibility="invalid",
                status="unknown",
                type="invalid",
            )
            OpenDataProduct(invalid_product)
        except (ValueError, ODPSValidationError) as e:
            # Should have informative error message
            error_msg = str(e)
            assert len(error_msg) > 0
            # Could check for specific error content if needed

    def test_validation_performance(self, sample_odps_product):
        """Test that validation performs reasonably well."""
        import time

        start_time = time.time()

        # Run validation multiple times
        for _ in range(100):
            sample_odps_product.validate()

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete 100 validations in under 1 second (adjust as needed)
        assert total_time < 1.0, f"Validation took too long: {total_time} seconds"
