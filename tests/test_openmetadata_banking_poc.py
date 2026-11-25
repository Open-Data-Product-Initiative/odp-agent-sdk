"""Reusable banking brief fixtures and an opt-in persistent marketplace test."""

import os
from pathlib import Path

import pytest
import yaml

from open_data_products import (
    OpenMetadataAdapter,
    load_integration_config,
    validate_document,
)
from open_data_products.integrations import ConnectionProfile

FIXTURES = Path(__file__).parent / "fixtures" / "openmetadata_banking_poc"
PRODUCTS = (
    "campaign-eligibility",
    "customer-lifetime-value",
    "customer-vulnerability-profile",
    "financial-crime-risk-profile",
    "payment-delinquency-forecast",
    "product-holdings",
)


def _source_and_draft(product_id):
    source = (FIXTURES / "sources" / (product_id + ".md")).read_text(encoding="utf-8")
    front_matter = yaml.safe_load(source.split("---", 2)[1])
    draft = (
        FIXTURES / "products" / ("odps_product_" + product_id + ".yaml")
    ).read_text(encoding="utf-8")
    return front_matter, draft


@pytest.mark.parametrize("product_id", PRODUCTS)
def test_banking_brief_and_draft_are_private_and_valid(product_id):
    """Check the saved draft against the corresponding original brief."""
    front_matter, source = _source_and_draft(product_id)
    document = yaml.safe_load(source)
    details = document["product"]["details"]["en"]
    assert front_matter["product_id"] == details["productID"] == product_id
    assert front_matter["product_name"] == details["name"]
    assert document["version"] == "4.1"
    assert details["visibility"] == "private"
    assert details["status"] == "draft"
    assert details.get("description")
    original = (FIXTURES / "sources" / (product_id + ".md")).read_text(encoding="utf-8")
    business_need = (
        original.split("## Business need\n", 1)[1].split("\n\n", 1)[0].strip()
    )
    purpose = original.split("## Product purpose\n", 1)[1].split("\n\n", 1)[0].strip()
    assert business_need in details["description"]
    assert purpose in details["description"]
    assert validate_document(document).valid
    adapter = OpenMetadataAdapter(
        ConnectionProfile(
            "test", "openmetadata", "https://example.test", "UNUSED", read_only=False
        )
    )
    review = adapter.review_create(source, domain="test-domain", owners=[])
    assert review.executable, review.to_dict()


@pytest.mark.parametrize("product_id", PRODUCTS)
def test_banking_brief_can_generate_requested_41(product_id, tmp_path):
    """Exercise generation with each saved brief and a deterministic model."""
    from open_data_products.generation import generate_local_artifact

    front, draft = _source_and_draft(product_id)
    source = FIXTURES / "sources" / (product_id + ".md")

    def model(prompt, name):
        assert front["product_name"] in prompt
        if prompt.startswith("# Extract ODPS Product Facts"):
            return "product: {}\n"
        assert 'version: "4.1"' in prompt
        return draft

    result = generate_local_artifact(
        "odps-product", source, tmp_path / "generated", client=model, odps_version="4.1"
    )
    assert result.valid_yaml, result.errors
    assert yaml.safe_load(result.output_path.read_text())["version"] == "4.1"


def test_live_persistent_banking_products():
    """Explicitly create saved briefs as persistent products, without cleanup."""
    if os.environ.get("ODPS_BANKING_POC_PERSISTENT_TEST") != "1":
        pytest.skip(
            "Set ODPS_BANKING_POC_PERSISTENT_TEST=1 to create persistent products"
        )
    path = os.environ.get("ODPS_INTEGRATION_CONFIG")
    profile_name = os.environ.get("ODPS_INTEGRATION_WRITE_PROFILE")
    domain = os.environ.get("ODPS_INTEGRATION_TEST_DOMAIN")
    if not path or not profile_name or not domain:
        pytest.fail(
            "Persistent test requires a config, write profile and explicit domain"
        )
    profile = load_integration_config(path).select(profile_name)
    if profile.read_only:
        pytest.fail("Persistent test requires a write-enabled profile")
    with OpenMetadataAdapter(profile) as adapter:
        # Check every identity before the first write, but recheck before each create too.
        for product_id in PRODUCTS:
            _, source = _source_and_draft(product_id)
            candidates = adapter.find_create_candidates(source, domain=domain)
            assert candidates["complete"] and not candidates["candidates"], candidates
        for product_id in PRODUCTS:
            _, source = _source_and_draft(product_id)
            candidates = adapter.find_create_candidates(source, domain=domain)
            assert candidates["complete"] and not candidates["candidates"], candidates
            review = adapter.review_create(source, domain=domain)
            assert review.executable, review.to_dict()
            result = adapter.create_product(
                source, domain=domain, reviewed_sha256=review.review_sha256
            )
            print(
                "Persistent product:",
                product_id,
                result.product_id,
                result.status,
                flush=True,
            )
            assert result.status == "created", result.to_dict()
            actual = adapter.get_product(result.product_id)
            assert actual.data["name"] == product_id
            assert actual.data["visibility"] == "PRIVATE"


@pytest.mark.parametrize("product_id", PRODUCTS)
def test_live_verify_existing_banking_product(product_id):
    """Verify an existing product without changing or deleting it."""
    if os.environ.get("ODPS_BANKING_POC_VERIFY_TEST") != "1":
        pytest.skip("Set ODPS_BANKING_POC_VERIFY_TEST=1 to verify existing products")
    path = os.environ.get("ODPS_INTEGRATION_CONFIG")
    domain = os.environ.get("ODPS_INTEGRATION_TEST_DOMAIN")
    profile_name = os.environ.get("ODPS_INTEGRATION_READ_PROFILE")
    if not path or not domain:
        pytest.fail("Verification requires a configuration and domain")
    config = load_integration_config(path)
    profile = config.select(profile_name)
    front, source = _source_and_draft(product_id)
    expected = yaml.safe_load(source)["product"]["details"]["en"]
    with OpenMetadataAdapter(profile) as adapter:
        result = adapter.find_create_candidates(source, domain=domain)
        assert result["complete"] and len(result["candidates"]) == 1, result
        candidate = result["candidates"][0]
        assert candidate["domain_match"] is not False
        actual = adapter.get_product(candidate["id"], include_domains=True)
        assert actual.data["name"] == product_id
        assert actual.data["displayName"] == front["product_name"]
        assert actual.data["visibility"] == "PRIVATE"
        assert actual.data["description"] == expected["description"]
        assert any(
            item["fullyQualifiedName"] == domain for item in actual.data["domains"]
        )
        comparison = adapter.compare_product(
            source, product_id=candidate["id"], domain=domain
        )
        fields = {item.path: item.status for item in comparison.fields}
        assert fields["/destination/domain"] == "preserved"
        assert fields["/product/details/en/productID"] == "preserved"
        search = adapter.search_products(product_id, limit=100)
        assert any(item["id"] == candidate["id"] for item in search.products)


def test_live_banking_odpc_catalog_and_search():
    """Verify the live marketplace catalog and search map to valid ODPC."""
    if os.environ.get("ODPS_BANKING_POC_VERIFY_TEST") != "1":
        pytest.skip("Set ODPS_BANKING_POC_VERIFY_TEST=1 to verify existing products")
    from open_data_products.odpc import validate_catalog

    path = os.environ.get("ODPS_INTEGRATION_CONFIG")
    if not path:
        pytest.fail("Verification requires a configuration")
    config = load_integration_config(path)
    profile = config.select(os.environ.get("ODPS_INTEGRATION_READ_PROFILE"))
    with OpenMetadataAdapter(profile) as adapter:
        catalog = adapter.list_products_odpc()
        assert validate_catalog(catalog).valid
        references = catalog["catalog"]["productReferences"]
        assert set(PRODUCTS) <= {entry["productID"] for entry in references}
        assert all(
            "metadata revision" in entry["x-productVersion-source"]
            for entry in references
        )
        search = adapter.search_products_odpc("campaign-eligibility")
        assert validate_catalog(search).valid
        assert any(
            entry["productID"] == "campaign-eligibility"
            for entry in search["catalog"]["productReferences"]
        )
