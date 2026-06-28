"""Pytest configuration and fixtures for ODPS tests."""

import pytest
import json
import yaml
from pathlib import Path

from open_data_products.odps import OpenDataProduct
from open_data_products.odps.models import ProductDetails


@pytest.fixture(autouse=True)
def disable_activity_logging_by_default(monkeypatch):
    """Keep unrelated CLI tests from writing workspace activity logs."""
    monkeypatch.setenv("OPEN_DATA_PRODUCTS_ACTIVITY_LOG", "0")


@pytest.fixture
def sample_product_details():
    """Provide a basic ProductDetails instance for testing."""
    return ProductDetails(
        name="Test Product",
        product_id="test-001",
        visibility="public",
        status="draft",
        type="dataset",
    )


@pytest.fixture
def sample_odps_product(sample_product_details):
    """Provide a basic OpenDataProduct instance for testing."""
    return OpenDataProduct(sample_product_details)


@pytest.fixture
def demo_product_json_path():
    """Path to demo product JSON file."""
    return Path(__file__).parent.parent / "examples" / "demo_product.json"


@pytest.fixture
def demo_product_yaml_path():
    """Path to demo product YAML file."""
    return Path(__file__).parent.parent / "examples" / "demo_product.yaml"


@pytest.fixture
def demo_product_json_data(demo_product_json_path):
    """Load demo product JSON data."""
    with open(demo_product_json_path, "r") as f:
        return json.load(f)


@pytest.fixture
def demo_product_yaml_data(demo_product_yaml_path):
    """Load demo product YAML data."""
    with open(demo_product_yaml_path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def minimal_valid_odps_data():
    """Minimal valid ODPS document data."""
    return {
        "schema": "https://opendataproducts.org/v4.0/schema/odps.json",
        "version": "4.0",
        "product": {
            "name": "Test Dataset",
            "productID": "test-001",
            "visibility": "public",
            "status": "draft",
            "type": "dataset",
        },
    }


@pytest.fixture
def invalid_odps_data():
    """Invalid ODPS document data for testing validation."""
    return {
        "schema": "https://opendataproducts.org/v4.0/schema/odps.json",
        "version": "4.0",
        "product": {
            "name": "",  # Invalid: empty name
            "productID": "",  # Invalid: empty product ID
            "visibility": "invalid",  # Invalid: not in allowed values
            "status": "unknown",  # Invalid: not in allowed values
            "type": "invalid",  # Invalid: not in allowed values
        },
    }
