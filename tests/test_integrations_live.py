"""Opt-in live checks against a user-supplied OpenMetadata deployment."""

import os

import pytest

from open_data_products import OpenMetadataAdapter, load_integration_config


def _adapter():
    path = os.environ.get("ODPS_INTEGRATION_CONFIG")
    if not path:
        pytest.skip("Set ODPS_INTEGRATION_CONFIG to enable live read tests")
    return OpenMetadataAdapter(load_integration_config(path).select())


def test_live_check_and_list():
    with _adapter() as adapter:
        assert adapter.check_connection()["status"] == "connected"
        assert isinstance(adapter.list_products().products, list)


@pytest.mark.parametrize("use_default_owner", [False, True])
def test_live_create_with_owner_and_tag(use_default_owner):
    """Create, verify, and remove a temporary product with explicit assignments."""
    if os.environ.get("ODPS_INTEGRATION_ASSIGNMENT_TEST") != "1":
        pytest.skip(
            "Set ODPS_INTEGRATION_ASSIGNMENT_TEST=1 for the live assignment test"
        )
    from pathlib import Path
    from uuid import uuid4
    import yaml

    path = os.environ.get("ODPS_INTEGRATION_CONFIG")
    domain = os.environ.get("ODPS_INTEGRATION_TEST_DOMAIN")
    profile = os.environ.get("ODPS_INTEGRATION_WRITE_PROFILE")
    owner = os.environ.get("ODPS_INTEGRATION_TEST_OWNER")
    tag = os.environ.get("ODPS_INTEGRATION_TEST_TAG")
    if not all((path, domain, profile, owner, tag)):
        pytest.fail(
            "Live assignment test requires config, write profile, domain, owner and tag"
        )
    fixture = (
        Path(__file__).parent
        / "fixtures/openmetadata_banking_poc/products/odps_product_campaign-eligibility.yaml"
    )
    document = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    details = document["product"]["details"]["en"]
    details["productID"] = "sdk_assignment_test_" + uuid4().hex[:10]
    details["name"] = "SDK owner and tag test"
    source = yaml.safe_dump(document, sort_keys=False)
    owners = None if use_default_owner else [owner]
    with OpenMetadataAdapter(load_integration_config(path).select(profile)) as adapter:
        review = adapter.review_create(source, domain=domain, owners=owners, tags=[tag])
        result = adapter.create_product(
            source,
            domain=domain,
            owners=owners,
            tags=[tag],
            reviewed_sha256=review.review_sha256,
        )
        try:
            assert result.status == "created", result.to_dict()
            assert result.assignments["comparison"] == {
                "owners": "matched",
                "tags": "matched",
            }
        finally:
            deletion = adapter.review_delete(result.product_id)
            removed = adapter.delete_product(
                result.product_id,
                reviewed_sha256=deletion.review_sha256,
                confirm_permanent=True,
            )
            assert removed.verification == "not_found_by_id"


def test_live_odps_export_and_validation():
    product_id = os.environ.get("ODPS_INTEGRATION_PRODUCT_ID")
    if not product_id:
        pytest.skip("Set ODPS_INTEGRATION_PRODUCT_ID to test ODPS export")
    with _adapter() as adapter:
        result = adapter.export_odps(product_id)
        assert result.validation is not None
        assert result.validation.valid, "Exported ODPS did not pass SDK validation"


def _assert_listed_and_searchable(adapter, product_id, product_name):
    """Find a created test product with bounded listing and search polling."""
    import time
    from uuid import uuid4

    cursor = None
    seen_cursors = set()
    for _ in range(20):
        page = adapter.list_products(limit=1000, after=cursor)
        if any(
            isinstance(item, dict) and item.get("id") == product_id
            for item in page.products
        ):
            break
        cursor = page.after
        if cursor is None:
            pytest.fail("Created product was not found in the product listing")
        if cursor in seen_cursors:
            pytest.fail("Product listing returned a repeated pagination cursor")
        seen_cursors.add(cursor)
    else:
        pytest.fail("Product listing exceeded the bounded page limit")
    print("Created product found in listing", flush=True)
    deadline = time.monotonic() + 30
    while True:
        page_search = adapter.search_products(product_name, limit=100)
        if any(item.get("id") == product_id for item in page_search.products):
            break
        if time.monotonic() >= deadline:
            pytest.fail(
                "Created product did not appear in search within the indexing wait"
            )
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
    print("Created product found in search", flush=True)
    no_match = adapter.search_products(uuid4().hex, limit=10)
    assert not no_match.products and no_match.total == 0


def _delete_test_product(adapter, product_id, product_name):
    """Delete only the uniquely named test product and verify its absence."""
    review = adapter.review_delete(product_id)
    assert review.product_id == product_id
    assert review.fqn == product_name, "Refusing to delete a different product"
    deleted = adapter.delete_product(
        product_id, reviewed_sha256=review.review_sha256, confirm_permanent=True
    )
    assert deleted.verification == "not_found_by_id", deleted.to_dict()
    print("Live test product deleted and absent:", product_id, flush=True)


def test_live_create_retrieve_update_and_verify():
    """Exercise a real write-enabled profile only with explicit live-test opt-in."""
    from uuid import uuid4
    from urllib import error, request
    import json
    import yaml

    if os.environ.get("ODPS_INTEGRATION_WRITE_TEST") != "1":
        pytest.skip(
            "Set ODPS_INTEGRATION_WRITE_TEST=1 to enable live creation and updates"
        )
    path = os.environ.get("ODPS_INTEGRATION_CONFIG")
    profile_name = os.environ.get("ODPS_INTEGRATION_WRITE_PROFILE")
    domain = os.environ.get("ODPS_INTEGRATION_TEST_DOMAIN")
    if not path or not profile_name or not domain:
        pytest.fail(
            "Write test requires configuration, an explicit write profile, and a test domain"
        )
    profile = load_integration_config(path).select(profile_name)
    if profile.read_only:
        pytest.fail("The specified live-test profile is read-only")
    product_name = "odps_sdk_roundtrip_" + uuid4().hex[:12]
    document = {
        "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "name": "SDK Round-Trip Test",
                    "productID": product_name,
                    "visibility": "private",
                    "status": "development",
                    "type": "dataset",
                    "description": "Initial non-sensitive SDK round-trip test.",
                }
            }
        },
    }
    source = yaml.safe_dump(document, sort_keys=False)
    with OpenMetadataAdapter(profile) as adapter:
        review = adapter.review_create(source, domain=domain)
        assert review.executable, review.to_dict()
        created = adapter.create_product(
            source, domain=domain, reviewed_sha256=review.review_sha256
        )
        print("Live test product ID:", created.product_id, flush=True)
        try:
            assert created.status == "created"
            assert created.comparison["domain"] == "matched"
            initial = adapter.get_product(created.product_id)
            assert initial.data["displayName"] == "SDK Round-Trip Test"
            _assert_listed_and_searchable(adapter, created.product_id, product_name)
            recovery = adapter.find_create_candidates(source, domain=domain)
            assert recovery["complete"]
            assert any(
                item["id"] == created.product_id for item in recovery["candidates"]
            )
            baseline = adapter.get_product(created.product_id)
            assert baseline.provenance.revision is not None
            review_update = adapter.review_update(
                created.product_id,
                title="SDK Round-Trip Test Updated",
                description="Updated non-sensitive SDK round-trip test.",
            )
            changed = adapter.update_product(
                created.product_id,
                title="SDK Round-Trip Test Updated",
                description="Updated non-sensitive SDK round-trip test.",
                reviewed_sha256=review_update.review_sha256,
            )
            assert changed.comparison == {
                "displayName": "matched",
                "description": "matched",
            }
            latest = adapter.get_product(created.product_id)
            assert latest.data["displayName"] == "SDK Round-Trip Test Updated"
            assert (
                latest.data["description"]
                == "Updated non-sensitive SDK round-trip test."
            )
            assert latest.provenance.revision != baseline.provenance.revision
            base = profile.base_url
            url = (
                base
                + ("/v1/" if base.endswith("/api") else "/api/v1/")
                + "dataProducts/"
                + created.product_id
            )
            stale_patch = request.Request(
                url,
                data=json.dumps(
                    [
                        {
                            "op": "add",
                            "path": "/description",
                            "value": "Stale revision probe.",
                        }
                    ]
                ).encode("utf-8"),
                method="PATCH",
                headers={
                    "Authorization": "Bearer " + profile.token(),
                    "Content-Type": "application/json-patch+json",
                    "If-Match": 'W/"' + review_update.revision + '"',
                },
            )
            try:
                with adapter._opener.open(
                    stale_patch, timeout=profile.timeout_seconds
                ) as response:
                    assert response.status in (200, 204)
                after_stale = adapter.get_product(created.product_id)
                assert after_stale.data.get("description") == "Stale revision probe."
                print(
                    "Conflict probe: server accepted stale revision; atomic If-Match protection unavailable",
                    flush=True,
                )
            except error.HTTPError as exc:
                status = exc.code
                exc.close()
                assert status in (409, 412), "Unexpected conflict probe status: " + str(
                    status
                )
                after_stale = adapter.get_product(created.product_id)
                assert (
                    after_stale.data.get("description")
                    == "Updated non-sensitive SDK round-trip test."
                )
                print("Conflict probe: server rejected stale revision", flush=True)
            print(
                "Platform revision:",
                baseline.provenance.revision,
                "->",
                latest.provenance.revision,
                flush=True,
            )
        finally:
            _delete_test_product(adapter, created.product_id, product_name)


@pytest.mark.parametrize("document_format", ["md", "docx"])
def test_live_business_document_to_marketplace(tmp_path, document_format):
    """Generate from a synthetic document, create, discover and remove the product."""
    from uuid import uuid4
    from xml.sax.saxutils import escape
    from zipfile import ZipFile
    import yaml
    from open_data_products import validate_document
    from open_data_products.generation import (
        generate_local_artifact,
    )
    from open_data_products.odps.versions import detect_version

    if (
        os.environ.get("ODPS_INTEGRATION_DOCUMENT_TEST") != "1"
        or os.environ.get("ODPS_INTEGRATION_WRITE_TEST") != "1"
    ):
        pytest.skip(
            "Set both ODPS_INTEGRATION_DOCUMENT_TEST=1 and ODPS_INTEGRATION_WRITE_TEST=1 to run this live test"
        )
    path = os.environ.get("ODPS_INTEGRATION_CONFIG")
    profile_name = os.environ.get("ODPS_INTEGRATION_WRITE_PROFILE")
    domain = os.environ.get("ODPS_INTEGRATION_TEST_DOMAIN")
    if not path or not profile_name or not domain:
        pytest.fail(
            "Document test requires configuration, an explicit write profile, and a test domain"
        )
    profile = load_integration_config(path).select(profile_name)
    if profile.read_only:
        pytest.fail("The specified live-test profile is read-only")
    product_name = "odps_sdk_document_" + uuid4().hex[:12]
    brief = (
        "# Airport Turnaround Monitoring\n\n"
        f"Product ID: {product_name}\n"
        "Name: Airport Turnaround Monitoring\n"
        "Visibility: private\n"
        "Lifecycle status: development\n"
        "Type: dataset\n"
        "Description: A dataset for airport operations teams to monitor aircraft "
        "turnaround delays and identify bottlenecks.\n"
    )
    source = tmp_path / ("business-brief." + document_format)
    if document_format == "md":
        source.write_text(brief, encoding="utf-8")
    else:
        paragraphs = "".join(
            "<w:p><w:r><w:t>" + escape(line) + "</w:t></w:r></w:p>"
            for line in brief.splitlines()
        )
        xml = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            + paragraphs
            + "</w:body></w:document>"
        )
        with ZipFile(source, "w") as archive:
            archive.writestr("word/document.xml", xml)
    model = os.environ.get("ODPS_INTEGRATION_OLLAMA_MODEL", "qwen2.5:latest")
    base_url = os.environ.get("ODPS_INTEGRATION_OLLAMA_URL", "http://localhost:11434")
    print(
        "Generating ODPS from", document_format, "with local model", model, flush=True
    )
    artifact = generate_local_artifact(
        "odps-product",
        source,
        tmp_path / "generated",
        model=model,
        ollama_url=base_url,
        odps_version="4.1",
    )
    assert artifact.valid_yaml, artifact.errors
    generated = yaml.safe_load(artifact.output_path.read_text(encoding="utf-8"))
    assert (
        detect_version(generated) == "4.1"
    ), "Generated output must natively declare ODPS 4.1"
    validation = validate_document(generated)
    assert validation.valid, validation.errors
    details = generated["product"]["details"]["en"]
    assert details["productID"] == product_name
    assert details["name"] == "Airport Turnaround Monitoring"
    assert details["visibility"] == "private" and details["type"] == "dataset"
    assert "turnaround" in details.get("description", "").lower()
    with OpenMetadataAdapter(profile) as adapter:
        source_yaml = artifact.output_path.read_text(encoding="utf-8")
        review = adapter.review_create(source_yaml, domain=domain)
        assert review.executable, review.to_dict()
        created = adapter.create_product(
            source_yaml, domain=domain, reviewed_sha256=review.review_sha256
        )
        print("Live generated test product ID:", created.product_id, flush=True)
        try:
            assert created.status == "created"
            actual = adapter.get_product(created.product_id)
            assert actual.data["name"] == product_name
            assert actual.data["displayName"] == details["name"]
            assert actual.data["description"] == details["description"]
            _assert_listed_and_searchable(adapter, created.product_id, product_name)
        finally:
            _delete_test_product(adapter, created.product_id, product_name)


def test_live_domain_create_and_product_move():
    """Create an explicitly named persistent test domain and move a disposable product."""
    from uuid import uuid4
    import yaml
    from open_data_products import PlatformError

    if os.environ.get("ODPS_INTEGRATION_DOMAIN_WRITE_TEST") != "1":
        pytest.skip(
            "Set ODPS_INTEGRATION_DOMAIN_WRITE_TEST=1 to create a persistent test domain"
        )
    path = os.environ.get("ODPS_INTEGRATION_CONFIG")
    profile_name = os.environ.get("ODPS_INTEGRATION_WRITE_PROFILE")
    initial_domain = os.environ.get("ODPS_INTEGRATION_TEST_DOMAIN")
    new_domain = os.environ.get("ODPS_INTEGRATION_NEW_TEST_DOMAIN")
    if not path or not profile_name or not initial_domain or not new_domain:
        pytest.fail(
            "Domain test requires config, write profile, initial domain and unique new domain name"
        )
    profile = load_integration_config(path).select(profile_name)
    if profile.read_only:
        pytest.fail("Domain test requires a write-enabled profile")
    product_name = "odps_sdk_domain_test_" + uuid4().hex[:12]
    document = {
        "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "name": "SDK Domain Change Test",
                    "productID": product_name,
                    "visibility": "private",
                    "status": "draft",
                    "type": "dataset",
                    "description": "Disposable product for domain change testing.",
                }
            }
        },
    }
    source = yaml.safe_dump(document, sort_keys=False)
    with OpenMetadataAdapter(profile) as adapter:
        try:
            adapter._json("domains/name/" + new_domain)
        except PlatformError as exc:
            if exc.status != 404:
                raise
        else:
            pytest.fail("The explicitly selected test domain already exists")
        domain_review = adapter.review_domain_create(
            name=new_domain,
            description="Persistent SDK integration test domain.",
            domain_type="Aggregate",
        )
        created_domain = adapter.create_domain(
            name=new_domain,
            description="Persistent SDK integration test domain.",
            domain_type="Aggregate",
            reviewed_sha256=domain_review.review_sha256,
        )
        print(
            "Persistent test domain:",
            created_domain.fqn,
            "status:",
            created_domain.status,
            flush=True,
        )
        assert created_domain.status == "created" and created_domain.fqn == new_domain
        create_review = adapter.review_create(source, domain=initial_domain)
        product = adapter.create_product(
            source, domain=initial_domain, reviewed_sha256=create_review.review_sha256
        )
        print("Disposable domain-change product:", product.product_id, flush=True)
        try:
            assert product.status == "created", product.to_dict()
            move_review = adapter.review_update(product.product_id, domain=new_domain)
            assert move_review.before["domain"] == [initial_domain]
            result = adapter.update_product(
                product.product_id,
                domain=new_domain,
                reviewed_sha256=move_review.review_sha256,
            )
            assert result.comparison["domain"] == "matched", result.to_dict()
            latest = adapter.get_product(product.product_id, include_domains=True)
            assert [item["fullyQualifiedName"] for item in latest.data["domains"]] == [
                new_domain
            ]
        finally:
            latest = adapter.get_product(product.product_id, include_domains=True)
            assert latest.data.get("name") == product_name
            deletion = adapter.review_delete(product.product_id)
            assert deletion.product_id == product.product_id
            deleted = adapter.delete_product(
                product.product_id,
                reviewed_sha256=deletion.review_sha256,
                confirm_permanent=True,
            )
            assert deleted.verification == "not_found_by_id"
            print("Disposable product deleted; test domain retained", flush=True)


def test_live_odcs_contract_import(tmp_path):
    """Preserve a complete schema-bearing ODCS contract on a disposable product."""
    from uuid import uuid4
    import yaml

    if os.environ.get("ODPS_INTEGRATION_CONTRACT_WRITE_TEST") != "1":
        pytest.skip("Set ODPS_INTEGRATION_CONTRACT_WRITE_TEST=1 to test ODCS import")
    path = os.environ.get("ODPS_INTEGRATION_CONFIG")
    profile_name = os.environ.get("ODPS_INTEGRATION_WRITE_PROFILE")
    domain = os.environ.get("ODPS_INTEGRATION_TEST_DOMAIN")
    if not path or not profile_name or not domain:
        pytest.fail("Contract test requires config, write profile and domain")
    profile = load_integration_config(path).select(profile_name)
    product_name = "odps_sdk_contract_" + uuid4().hex[:12]
    product_source = yaml.safe_dump(
        {
            "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "SDK ODCS Contract Test",
                        "productID": product_name,
                        "visibility": "private",
                        "status": "draft",
                        "type": "dataset",
                        "description": "Disposable ODCS integration test product.",
                    }
                }
            },
        },
        sort_keys=False,
    )
    contract_source = yaml.safe_dump(
        {
            "apiVersion": "v3.1.0",
            "kind": "DataContract",
            "id": product_name + "_contract",
            "name": product_name + "_contract",
            "version": "0.1.0",
            "status": "draft",
            "description": {"purpose": "Fictional SDK contract association test."},
            "schema": [
                {
                    "name": "records",
                    "properties": [
                        {
                            "name": "customer_id",
                            "logicalType": "string",
                            "required": True,
                        }
                    ],
                }
            ],
        },
        sort_keys=False,
    )
    with OpenMetadataAdapter(profile) as adapter:
        review = adapter.review_create(product_source, domain=domain)
        created = adapter.create_product(
            product_source, domain=domain, reviewed_sha256=review.review_sha256
        )
        print("Disposable ODCS product:", created.product_id, flush=True)
        try:
            assert created.status == "created", created.to_dict()
            contract_review = adapter.review_contract_import(
                contract_source, product_id=created.product_id
            )
            assert contract_review.executable, contract_review.to_dict()
            assert contract_review.schema_preserved
            assert contract_review.source_validation["valid"] is False
            result = adapter.import_contract(
                contract_source,
                product_id=created.product_id,
                reviewed_sha256=contract_review.review_sha256,
            )
            print(
                "ODCS contract:",
                result.contract_id,
                "status:",
                result.status,
                flush=True,
            )
            assert result.status == "created", result.to_dict()
            assert result.comparison["association"] == "matched"
            preserved = adapter.get_preserved_contract_source(created.product_id)
            assert preserved["yaml"] == contract_source
            assert preserved["version"] == "0.1.0"
            assert (
                yaml.safe_load(preserved["yaml"])["schema"][0]["properties"][0]["name"]
                == "customer_id"
            )
            from open_data_products.cli import main

            output = tmp_path / "restored-contract.yaml"
            assert (
                main(
                    [
                        "openmetadata",
                        "api",
                        "products",
                        "contract-source",
                        profile_name,
                        "--config",
                        path,
                        "--id",
                        created.product_id,
                        "--output",
                        str(output),
                        "--json",
                    ]
                )
                == 0
            )
            assert output.read_text() == contract_source
            platform_export = yaml.safe_load(
                adapter._get(
                    "dataContracts/" + result.contract_id + "/odcs/yaml",
                    "application/yaml",
                ).decode("utf-8")
            )
            assert (
                platform_export.get("schema")
                != yaml.safe_load(contract_source)["schema"]
            )
        finally:
            _delete_test_product(adapter, created.product_id, product_name)


@pytest.mark.parametrize("contract_mode", ["inline", "linked"])
def test_live_product_create_with_odcs_contract(tmp_path, contract_mode):
    """Create a disposable ODPS product with its ODCS contract in one workflow."""
    from uuid import uuid4
    import yaml

    if os.environ.get("ODPS_INTEGRATION_CONTRACT_WRITE_TEST") != "1":
        pytest.skip("Set ODPS_INTEGRATION_CONTRACT_WRITE_TEST=1 to test ODCS import")
    path = os.environ.get("ODPS_INTEGRATION_CONFIG")
    profile_name = os.environ.get("ODPS_INTEGRATION_WRITE_PROFILE")
    domain = os.environ.get("ODPS_INTEGRATION_TEST_DOMAIN")
    if not path or not profile_name or not domain:
        pytest.fail("Contract test requires config, write profile and domain")
    profile = load_integration_config(path).select(profile_name)
    product_name = "odps_sdk_with_contract_" + uuid4().hex[:12]
    contract = {
        "apiVersion": "v3.1.0",
        "kind": "DataContract",
        "id": product_name + "_contract",
        "name": product_name + "_contract",
        "version": "0.1.0",
        "status": "draft",
        "description": {"purpose": "Fictional SDK inline contract test."},
        "schema": [
            {"name": "records", "properties": [{"name": "id", "logicalType": "string"}]}
        ],
    }
    contract_path = tmp_path / "contract.yaml"
    contract_path.write_text(yaml.safe_dump(contract, sort_keys=False))
    association = (
        {"type": "ODCS", "spec": contract}
        if contract_mode == "inline"
        else {"type": "ODCS", "$ref": "contract.yaml"}
    )
    document = {
        "schema": "https://opendataproducts.org/v4.1/schema/odps.json",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "name": "SDK ODCS Product Test",
                    "productID": product_name,
                    "visibility": "private",
                    "status": "draft",
                    "type": "dataset",
                    "description": "Disposable ODCS product creation test.",
                }
            },
            "contract": association,
        },
    }
    source = yaml.safe_dump(document, sort_keys=False)
    source_path = tmp_path / "product.yaml"
    source_path.write_text(source)
    with OpenMetadataAdapter(profile) as adapter:
        review = adapter.review_create(
            source, domain=domain, source_path=str(source_path)
        )
        assert review.executable and review.contract_import["planned"], review.to_dict()
        created = adapter.create_product(
            source,
            domain=domain,
            source_path=str(source_path),
            reviewed_sha256=review.review_sha256,
        )
        print(
            "Disposable product with",
            contract_mode,
            "contract:",
            created.product_id,
            "status:",
            created.status,
            flush=True,
        )
        try:
            assert created.status == "created", created.to_dict()
            assert created.contract_import["status"] == "created"
            assert created.contract_import["comparison"]["association"] == "matched"
            restored = adapter.get_preserved_contract_source(created.product_id)
            assert yaml.safe_load(restored["yaml"]) == contract
            assert restored["version"] == "0.1.0"
            if contract_mode == "linked":
                assert restored["yaml"] == contract_path.read_text()
        finally:
            _delete_test_product(adapter, created.product_id, product_name)
