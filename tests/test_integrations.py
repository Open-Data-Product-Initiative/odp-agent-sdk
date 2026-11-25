"""Offline tests for connection profiles and OpenMetadata reads."""

import io
from dataclasses import replace
from http.client import IncompleteRead
import json
from urllib.error import HTTPError

import pytest
from open_data_products import (
    ConfigurationError,
    IntegrationError,
    OpenMetadataAdapter,
    PlatformError,
    load_integration_config,
)
from open_data_products.cli import main


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "connections.yaml"
    path.write_text("""version: 1
default_connection: dev
connections:
  dev:
    platform: openmetadata
    base_url: https://example.test/prefix/
    auth:
      type: bearer_token
      token: {source: env, name: TEST_INTEGRATION_TOKEN}
  second:
    platform: openmetadata
    base_url: https://second.test/api
    auth:
      type: bearer_token
      token: {source: env, name: SECOND_INTEGRATION_TOKEN}
""")
    return path


def test_profiles_lazy_and_independent(config_file, monkeypatch):
    monkeypatch.delenv("TEST_INTEGRATION_TOKEN", raising=False)
    config = load_integration_config(config_file)
    assert config.select().base_url == "https://example.test/prefix"
    assert config.select("second").base_url == "https://second.test/api"
    with pytest.raises(ConfigurationError, match="missing"):
        config.select().token()
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "test-secret")
    assert config.select().token() == "test-secret"
    assert "test-secret" not in repr(config)


def test_config_rejects_duplicates_and_bad_tls(config_file):
    original = config_file.read_text()
    config_file.write_text(original + "  dev: {}\n")
    with pytest.raises(ConfigurationError, match="duplicate"):
        load_integration_config(config_file)
    config_file.write_text(
        original.replace("https://example.test", "http://example.test")
    )
    with pytest.raises(ConfigurationError, match="URL"):
        load_integration_config(config_file)
    config_file.write_text(original.replace("source: env", "source: literal", 1))
    with pytest.raises(ConfigurationError, match="environment"):
        load_integration_config(config_file)


def test_non_utf8_configuration_is_sanitized(config_file):
    config_file.write_bytes(b"\xffprivate")
    with pytest.raises(
        ConfigurationError, match="Cannot read integration configuration"
    ):
        load_integration_config(config_file)


def test_non_utf8_create_source_is_sanitized(config_file, tmp_path, capsys):
    source = tmp_path / "bad.yaml"
    source.write_bytes(b"\xffprivate")
    assert (
        main(
            [
                "integrations",
                "products",
                "create",
                "--no-owner",
                "dev",
                "--config",
                str(config_file),
                "--source",
                str(source),
                "--domain",
                "test",
            ]
        )
        == 1
    )
    assert "Unable to read or write a local file" in capsys.readouterr().err


class Response:
    def __init__(self, data):
        self.data = data
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit):
        return self.data[:limit]


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, req, timeout):
        self.requests.append(req)
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return Response(result)


def test_list_pages_native_and_url_encoding(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "secret-value")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    adapter._opener = Opener(
        [
            b'{"data": [], "paging": {"after": "next+/="}}',
            b'{"data": [{"id": "id1"}], "paging": {}}',
            b'{"id":"a/b", "fullyQualifiedName":"a.b", "version":1.2}',
        ]
    )
    page = adapter.list_products(limit=1)
    assert page.products == [] and page.after == "next+/="
    assert adapter.list_products(after=page.after).products == [{"id": "id1"}]
    product = adapter.get_product("a/b")
    assert product.provenance.revision == "1.2"
    assert "%2F" in adapter._opener.requests[-1].full_url
    assert "after=next%2B%2F%3D" in adapter._opener.requests[1].full_url
    assert "secret-value" not in repr(product)
    assert adapter.capabilities()["permissions"] == "unknown"
    with pytest.raises(IntegrationError, match="read-only"):
        adapter.create_product("", domain="domain", reviewed_sha256="x", owners=[])
    write_adapter = OpenMetadataAdapter(replace(adapter.profile, read_only=False))
    with pytest.raises(IntegrationError, match="ODPS 4.1"):
        write_adapter.create_product(
            "", domain="domain", reviewed_sha256="x", owners=[]
        )


@pytest.mark.parametrize("status", [401, 403, 404, 429])
def test_http_errors_are_sanitized(config_file, monkeypatch, status):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "private-token")
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.time.sleep", lambda _: None
    )
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())

    def err():
        return HTTPError(
            "https://private-host/path?private-token",
            status,
            "private-token",
            {},
            io.BytesIO(b"private-token"),
        )

    adapter._opener = Opener([err(), err(), err()])
    with pytest.raises(PlatformError) as caught:
        adapter.list_products()
    assert caught.value.status == status
    assert "private-token" not in str(caught.value)
    assert "private-host" not in str(caught.value)


def test_redirects_and_long_retry_after_do_not_resend_token(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "private-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    for status, headers in [
        (302, {"Location": "https://elsewhere.test/"}),
        (429, {"Retry-After": "120"}),
    ]:
        response = HTTPError(
            "https://example.test/", status, "error", headers, io.BytesIO()
        )
        adapter._opener = Opener([response])
        with pytest.raises(PlatformError) as caught:
            adapter.list_products()
        assert caught.value.status == status
        assert len(adapter._opener.requests) == 1


def test_invalid_odps_and_cli_preserves_original(
    config_file, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "private-token")
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: Opener([b"not: [valid", b'{"id":"id1","version":0.1}']),
    )
    output = tmp_path / "product.yaml"
    provenance = tmp_path / "provenance.json"
    exit_code = main(
        [
            "integrations",
            "products",
            "get",
            "dev",
            "--config",
            str(config_file),
            "--id",
            "11111111-1111-4111-8111-111111111111",
            "--output",
            str(output),
            "--provenance",
            str(provenance),
            "--strict",
            "false",
        ]
    )
    assert exit_code == 0
    assert output.read_text() == "not: [valid"
    assert (
        json.loads((tmp_path / "product.yaml.validation.json").read_text())["valid"]
        is False
    )
    assert json.loads(provenance.read_text())["profile"] == "dev"
    assert "private-token" not in capsys.readouterr().out


def test_legacy_get_cli_rejects_name_without_platform_request(
    config_file, monkeypatch, capsys
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    opener = Opener([])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    assert (
        main(
            [
                "integrations",
                "products",
                "get",
                "dev",
                "--config",
                str(config_file),
                "--id",
                "Campaign Eligibility",
                "--json",
            ]
        )
        == 1
    )
    assert "UUID" in capsys.readouterr().err
    assert not opener.requests


def test_cli_list_does_not_require_credentials(config_file, monkeypatch, capsys):
    monkeypatch.delenv("TEST_INTEGRATION_TOKEN", raising=False)
    assert main(["integrations", "list", "--config", str(config_file), "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 2


def test_normalization_preserves_source_and_reports_loss():
    from open_data_products import normalize_openmetadata_updated_dates

    source = """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      name: SDK Read-Only Test Product
      productID: SDKReadOnlyTestProduct
      visibility: private
      status: development
      updated: 1795580308927
"""
    result = normalize_openmetadata_updated_dates(source)
    assert result.original_yaml == source
    assert '"2026-11-25"' in result.normalized_yaml
    assert result.changes[0].original_milliseconds == 1795580308927
    assert result.changes[0].pointer == "/product/details/en/updated"
    assert not result.validation.valid  # Missing product type is not invented.
    assert not any("updated" in message for message in result.validation.errors)


def test_normalization_rejects_ambiguous_seconds():
    from open_data_products import (
        IntegrationError,
        normalize_openmetadata_updated_dates,
    )

    with pytest.raises(IntegrationError, match="millisecond"):
        normalize_openmetadata_updated_dates(
            'version: "4.1"\nproduct: {details: {en: {updated: 1795580308}}}'
        )


def test_cli_normalization_retains_original_and_timestamp(
    config_file, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "private-token")
    source = b"""schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      name: Test
      productID: test
      visibility: private
      status: development
      updated: 1795580308927
"""
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: Opener([source, b'{"id":"id1"}']),
    )
    output = tmp_path / "derived.yaml"
    provenance = tmp_path / "provenance.json"
    status = main(
        [
            "integrations",
            "products",
            "get",
            "dev",
            "--config",
            str(config_file),
            "--id",
            "11111111-1111-4111-8111-111111111111",
            "--output",
            str(output),
            "--provenance",
            str(provenance),
            "--normalize-updated-timestamps",
            "--strict",
            "false",
        ]
    )
    assert status == 0
    assert (tmp_path / "derived.yaml.original.yaml").read_bytes() == source
    assert "2026-11-25" in output.read_text()
    assert (
        json.loads(provenance.read_text())["timestamp_normalizations"][0][
            "original_milliseconds"
        ]
        == 1795580308927
    )
    assert not json.loads((tmp_path / "derived.yaml.validation.json").read_text())[
        "valid"
    ]
    assert "private-token" not in capsys.readouterr().out


def test_strict_validation_blocks_saving_and_reports_reasons(
    config_file, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "private-token")
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: Opener([b"not: [valid", b'{"id":"id1"}']),
    )
    output = tmp_path / "invalid.yaml"
    status = main(
        [
            "integrations",
            "products",
            "get",
            "dev",
            "--config",
            str(config_file),
            "--id",
            "11111111-1111-4111-8111-111111111111",
            "--output",
            str(output),
            "--strict",
            "true",
        ]
    )
    response = json.loads(capsys.readouterr().out)
    assert status == 1
    assert not output.exists()
    assert response["strict"] is True
    assert response["validation"]["valid"] is False
    assert response["validation"]["errors"]
    assert response["saved"] is False


def test_strict_is_enabled_by_default(config_file, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "private-token")
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: Opener([b"not: [valid", b'{"id":"id1"}']),
    )
    output = tmp_path / "invalid.yaml"
    status = main(
        [
            "integrations",
            "products",
            "get",
            "dev",
            "--config",
            str(config_file),
            "--id",
            "11111111-1111-4111-8111-111111111111",
            "--output",
            str(output),
        ]
    )
    assert status == 1
    assert json.loads(capsys.readouterr().out)["strict"] is True
    assert not output.exists()


VALID_ODPS = """schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      name: Sample product
      productID: sample_product
      visibility: private
      status: development
      type: dataset
"""


@pytest.mark.parametrize(
    "source, message",
    [
        (
            VALID_ODPS.replace(
                "      visibility: private",
                "      visibility: private\n      visibility: public",
            ),
            "duplicate",
        ),
        (VALID_ODPS + "extra: &item {a: 1}\nother: *item\n", "aliases"),
        (VALID_ODPS + "deep: " + "[" * 70 + "0" + "]" * 70 + "\n", "nesting"),
    ],
)
def test_create_review_rejects_ambiguous_yaml(config_file, source, message):
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    adapter._opener = Opener([])
    with pytest.raises(IntegrationError, match=message):
        adapter.review_create(source, domain="test-domain", owners=[])
    assert not adapter._opener.requests


def test_find_create_candidates_reports_ambiguity_and_unknown_domain(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    adapter._opener = Opener(
        [
            b'{"data":[{"id":"1","name":"sample_product","domains":[{"fullyQualifiedName":"test-domain"}]},{"id":"2","name":"sample_product"}],"paging":{"after":"next"}}',
            b'{"data":[{"id":"3","name":"other"}],"paging":{}}',
        ]
    )
    result = adapter.find_create_candidates(VALID_ODPS, domain="test-domain")
    assert result["complete"] is True
    assert [item["domain_match"] for item in result["candidates"]] == [True, None]
    assert all(req.method == "GET" for req in adapter._opener.requests)


def test_find_create_candidates_marks_incomplete_and_repeated_cursor(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    page = b'{"data":[],"paging":{"after":"same"}}'
    adapter._opener = Opener([page])
    assert (
        adapter.find_create_candidates(VALID_ODPS, domain="test-domain", max_pages=1)[
            "complete"
        ]
        is False
    )
    adapter._opener = Opener([page, page])
    with pytest.raises(PlatformError, match="repeated"):
        adapter.find_create_candidates(VALID_ODPS, domain="test-domain")


def test_review_create_is_offline_and_describes_loss(config_file):
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    adapter._opener = Opener([])
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    assert review.compatible and review.validation.valid
    assert not review.executable and not review.write_enabled
    assert "/product/details/en/status" in review.unsupported_fields
    assert review.field_mapping["/product/details/en/productID"] == "name"
    assert review.review_sha256
    assert not adapter._opener.requests


def test_create_checks_read_only_validation_and_review_digest(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    adapter._opener = Opener([])
    with pytest.raises(IntegrationError, match="read-only"):
        adapter.create_product(
            VALID_ODPS,
            domain="test-domain",
            reviewed_sha256=review.review_sha256,
            owners=[],
        )
    writable = OpenMetadataAdapter(replace(adapter.profile, read_only=False))
    writable._opener = Opener([])
    writable_review = writable.review_create(
        VALID_ODPS, domain="test-domain", owners=[]
    )
    with pytest.raises(IntegrationError, match="digest"):
        writable.create_product(
            VALID_ODPS,
            domain="other-domain",
            reviewed_sha256=writable_review.review_sha256,
            owners=[],
        )
    with pytest.raises(IntegrationError, match="validation"):
        writable.create_product(
            VALID_ODPS.replace("type: dataset", ""),
            domain="test-domain",
            reviewed_sha256=writable_review.review_sha256,
            owners=[],
        )
    assert not writable._opener.requests


def test_create_once_then_retrieves_and_compares(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    profile = replace(load_integration_config(config_file).select(), read_only=False)
    adapter = OpenMetadataAdapter(profile)
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            b'{"id":"new-id"}',
            b'{"id":"new-id","name":"sample_product","displayName":"Sample product","fullyQualifiedName":"sample_product","dataProductType":"DATASET","visibility":"PRIVATE","domains":[{"fullyQualifiedName":"test-domain"}]}',
        ]
    )
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    result = adapter.create_product(
        VALID_ODPS,
        domain="test-domain",
        reviewed_sha256=review.review_sha256,
        owners=[],
    )
    assert result.status == "created" and result.product_id == "new-id"
    assert result.comparison == {
        "name": "matched",
        "productID": "matched",
        "type": "matched",
        "visibility": "matched",
        "domain": "matched",
    }
    requests = adapter._opener.requests
    assert [req.method for req in requests] == ["GET", "POST", "GET"]
    assert "domain=test-domain" in requests[1].full_url
    assert requests[1].get_header("Content-type") == "application/yaml"


def test_create_preserves_multiword_domain_fqn(config_file, monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    domain = "Retail Banking Services"
    product = {
        "id": "11111111-1111-4111-8111-111111111111",
        "name": "sample_product",
        "displayName": "Sample product",
        "dataProductType": "DATASET",
        "visibility": "PRIVATE",
        "domains": [{"fullyQualifiedName": domain}],
    }
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            json.dumps({"id": product["id"]}).encode(),
            json.dumps(product).encode(),
        ]
    )
    review = adapter.review_create(VALID_ODPS, domain=domain, owners=[])
    result = adapter.create_product(
        VALID_ODPS, domain=domain, owners=[], reviewed_sha256=review.review_sha256
    )
    assert result.status == "created" and result.comparison["domain"] == "matched"
    assert parse_qs(urlsplit(adapter._opener.requests[1].full_url).query)["domain"] == [
        domain
    ]
    assert (
        adapter.review_create(
            VALID_ODPS, domain="Retail Banking", owners=[]
        ).review_sha256
        != review.review_sha256
    )


@pytest.mark.parametrize(
    "domains, expected, outcome",
    [
        ([], "different_or_missing", "created_with_mismatches"),
        (
            [{"fullyQualifiedName": "another-domain"}],
            "different_or_missing",
            "created_with_mismatches",
        ),
        (None, "unverified", "created_unverified"),
        ([{"name": "test-domain"}], "unverified", "created_unverified"),
        ([{"fullyQualifiedName": "test-domain"}], "matched", "created"),
    ],
)
def test_create_verifies_selected_domain(
    config_file, monkeypatch, domains, expected, outcome
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    native = {
        "id": "new-id",
        "name": "sample_product",
        "displayName": "Sample product",
        "dataProductType": "DATASET",
        "visibility": "PRIVATE",
    }
    if domains is not None:
        native["domains"] = domains
    adapter._opener = Opener(
        [b'{"version":"2.1.0"}', b'{"id":"new-id"}', json.dumps(native).encode()]
    )
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    result = adapter.create_product(
        VALID_ODPS,
        domain="test-domain",
        reviewed_sha256=review.review_sha256,
        owners=[],
    )
    assert result.comparison["domain"] == expected and result.status == outcome
    assert "fields=domains" in adapter._opener.requests[-1].full_url


def test_list_domains_and_native_domain_retrieval(config_file, monkeypatch, capsys):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    opener = Opener(
        [
            b'{"data":[{"name":"Sales","fullyQualifiedName":"Retail.Sales"}],"paging":{"after":"next"}}',
            b'{"id":"product","domains":[{"fullyQualifiedName":"Retail.Sales"}]}',
        ]
    )
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    assert (
        main(["integrations", "domains", "dev", "--config", str(config_file), "--json"])
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["domains"][0]["fullyQualifiedName"] == "Retail.Sales"
    assert result["after"] == "next"
    assert (
        main(
            [
                "integrations",
                "products",
                "get",
                "dev",
                "--config",
                str(config_file),
                "--id",
                "11111111-1111-4111-8111-111111111111",
                "--format",
                "native",
                "--include-domains",
                "--json",
            ]
        )
        == 0
    )
    assert (
        json.loads(capsys.readouterr().out)["data"]["domains"][0]["fullyQualifiedName"]
        == "Retail.Sales"
    )
    assert "fields=domains" in opener.requests[1].full_url


def test_create_timeout_reports_unknown_without_retry(config_file, monkeypatch):
    from open_data_products import UnknownCreateOutcome

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    adapter._opener = Opener([b'{"version":"2.1.0"}', TimeoutError("secret")])
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    with pytest.raises(UnknownCreateOutcome, match="unknown"):
        adapter.create_product(
            VALID_ODPS,
            domain="test-domain",
            reviewed_sha256=review.review_sha256,
            owners=[],
        )
    assert len(adapter._opener.requests) == 2


def test_create_refuses_unverified_server_version(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    adapter._opener = Opener([b'{"version":"2.2.0"}'])
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    with pytest.raises(IntegrationError, match="2.1.0"):
        adapter.create_product(
            VALID_ODPS,
            domain="test-domain",
            reviewed_sha256=review.review_sha256,
            owners=[],
        )
    assert [req.method for req in adapter._opener.requests] == ["GET"]


def test_create_review_cli_reports_invalid_without_network(
    config_file, tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("TEST_INTEGRATION_TOKEN", raising=False)
    source = tmp_path / "invalid.yaml"
    source.write_text(VALID_ODPS.replace("type: dataset", ""))
    status = main(
        [
            "integrations",
            "products",
            "create",
            "--no-owner",
            "dev",
            "--config",
            str(config_file),
            "--source",
            str(source),
            "--domain",
            "test-domain",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert status == 1 and not result["executable"]
    assert result["validation"]["errors"]


def test_create_pending_response_is_not_claimed_as_created(config_file, monkeypatch):
    from open_data_products import UnknownCreateOutcome

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )

    class PendingResponse(Response):
        def __init__(self):
            super().__init__(b'{"id":"request-id"}')
            self.status = 202

    class PendingOpener(Opener):
        def open(self, req, timeout):
            self.requests.append(req)
            result = next(self.responses)
            return result if isinstance(result, PendingResponse) else Response(result)

    adapter._opener = PendingOpener([b'{"version":"2.1.0"}', PendingResponse()])
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    with pytest.raises(UnknownCreateOutcome, match="not confirmed"):
        adapter.create_product(
            VALID_ODPS,
            domain="test-domain",
            reviewed_sha256=review.review_sha256,
            owners=[],
        )
    assert [req.method for req in adapter._opener.requests] == ["GET", "POST"]


def test_create_readback_failure_does_not_retry_create(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    failure = HTTPError("https://example.test", 403, "forbidden", {}, io.BytesIO())
    adapter._opener = Opener([b'{"version":"2.1.0"}', b'{"id":"new-id"}', failure])
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    result = adapter.create_product(
        VALID_ODPS,
        domain="test-domain",
        reviewed_sha256=review.review_sha256,
        owners=[],
    )
    assert result.status == "created_unverified"
    assert result.comparison["readback"] == "unavailable"
    assert [req.method for req in adapter._opener.requests].count("POST") == 1


def test_create_reports_mismatched_description(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            b'{"id":"new-id"}',
            b'{"id":"new-id","name":"sample_product","displayName":"Sample product","description":"wrong"}',
        ]
    )
    source = VALID_ODPS + "      description: Expected description\n"
    review = adapter.review_create(source, domain="test-domain", owners=[])
    result = adapter.create_product(
        source, domain="test-domain", reviewed_sha256=review.review_sha256, owners=[]
    )
    assert result.status == "created_with_mismatches"
    assert result.comparison["description"] == "different_or_missing"
    assert result.product_id == "new-id"


def test_cli_create_reports_unverified_without_retry(
    config_file, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    config_file.write_text(
        config_file.read_text().replace(
            "    platform: openmetadata\n",
            "    read_only: false\n    platform: openmetadata\n",
            1,
        )
    )
    source = tmp_path / "source.yaml"
    source.write_text(VALID_ODPS)
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    failure = HTTPError("https://example.test", 403, "forbidden", {}, io.BytesIO())
    opener = Opener([b'{"version":"2.1.0"}', b'{"id":"new-id"}', failure])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    status = main(
        [
            "integrations",
            "products",
            "create",
            "--no-owner",
            "dev",
            "--config",
            str(config_file),
            "--source",
            str(source),
            "--domain",
            "test-domain",
            "--execute",
            "--reviewed-sha256",
            review.review_sha256,
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert status == 1 and result["status"] == "created_unverified"
    assert result["product_id"] == "new-id"
    assert [req.method for req in opener.requests].count("POST") == 1


def test_export_save_failure_rolls_back_new_files(tmp_path, monkeypatch):
    from open_data_products.integrations.cli import _save_output_set
    import os

    first = tmp_path / "product.yaml"
    second = tmp_path / "provenance.json"
    real_link = os.link
    calls = []

    def fail_second(source, destination):
        calls.append(destination)
        if len(calls) == 2:
            raise OSError("disk failure")
        real_link(source, destination)

    monkeypatch.setattr("open_data_products.integrations.cli.os.link", fail_second)
    with pytest.raises(IntegrationError, match="complete output set"):
        _save_output_set([(first, "document"), (second, "provenance")])
    assert not first.exists() and not second.exists()
    assert list(tmp_path.iterdir()) == []


def test_export_save_interrupt_rolls_back_owned_files(tmp_path, monkeypatch):
    from open_data_products.integrations.cli import _save_output_set
    import os

    real_link = os.link
    calls = []

    def interrupt_second(source, destination):
        calls.append(destination)
        if len(calls) == 2:
            raise KeyboardInterrupt
        real_link(source, destination)

    monkeypatch.setattr("open_data_products.integrations.cli.os.link", interrupt_second)
    with pytest.raises(KeyboardInterrupt):
        _save_output_set(
            [
                (tmp_path / "product.yaml", "data"),
                (tmp_path / "provenance.json", "metadata"),
            ]
        )
    assert list(tmp_path.iterdir()) == []


def test_create_recovery_cli_is_read_only(config_file, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    source = tmp_path / "candidate.yaml"
    source.write_text(VALID_ODPS)
    opener = Opener(
        [b'{"data":[{"id":"candidate","name":"sample_product"}],"paging":{}}']
    )
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    status = main(
        [
            "integrations",
            "products",
            "recover-create",
            "dev",
            "--config",
            str(config_file),
            "--source",
            str(source),
            "--domain",
            "test-domain",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert status == 0 and result["candidates"][0]["id"] == "candidate"
    assert result["candidates"][0]["domain_match"] is None
    assert [request.method for request in opener.requests] == ["GET"]


DELETE_PRODUCT_ID = "2ae0905f-bf50-4491-bd19-e82e6ae6f05f"
DELETE_PRODUCT = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"test","fullyQualifiedName":"test","version":0.1}'

VALID_ODCS = """apiVersion: v3.1.0
kind: DataContract
id: sdk-test-contract
name: SDK Test Contract
version: 0.1.0
status: draft
description:
  purpose: Test association.
"""


def _contract_absent():
    return HTTPError("https://example.test", 404, "not found", {}, io.BytesIO())


def _odps_with_contract(contract):
    import yaml

    document = yaml.safe_load(VALID_ODPS)
    document["product"]["contract"] = contract
    return yaml.safe_dump(document, sort_keys=False)


def test_product_creation_imports_reviewed_inline_contract(config_file, monkeypatch):
    from types import SimpleNamespace
    import yaml

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    source = _odps_with_contract({"type": "ODCS", "spec": yaml.safe_load(VALID_ODCS)})
    native = b'{"id":"new-id","name":"sample_product","displayName":"Sample product","dataProductType":"DATASET","visibility":"PRIVATE","domains":[{"fullyQualifiedName":"test-domain"}]}'
    adapter._opener = Opener([b'{"version":"2.1.0"}', b'{"id":"new-id"}', native])
    monkeypatch.setattr(
        adapter,
        "review_contract_import",
        lambda source, product_id: SimpleNamespace(
            executable=True, review_sha256="contract-review"
        ),
    )
    monkeypatch.setattr(
        adapter,
        "import_contract",
        lambda source, product_id, reviewed_sha256: SimpleNamespace(
            status="created",
            to_dict=lambda: {"status": "created", "contract_id": "contract-id"},
        ),
    )
    review = adapter.review_create(source, domain="test-domain", owners=[])
    assert (
        review.contract_import["planned"]
        and "/product/contract" not in review.unsupported_fields
    )
    result = adapter.create_product(
        source, domain="test-domain", reviewed_sha256=review.review_sha256, owners=[]
    )
    assert (
        result.status == "created"
        and result.contract_import["contract_id"] == "contract-id"
    )


def test_product_creation_records_contract_failure_without_losing_product_id(
    config_file, monkeypatch
):
    from types import SimpleNamespace
    import yaml

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    source = _odps_with_contract({"type": "ODCS", "spec": yaml.safe_load(VALID_ODCS)})
    native = b'{"id":"new-id","name":"sample_product","displayName":"Sample product","dataProductType":"DATASET","visibility":"PRIVATE","domains":[{"fullyQualifiedName":"test-domain"}]}'
    adapter._opener = Opener([b'{"version":"2.1.0"}', b'{"id":"new-id"}', native])
    monkeypatch.setattr(
        adapter,
        "review_contract_import",
        lambda source, product_id: SimpleNamespace(
            executable=False, validation={"valid": False}
        ),
    )
    review = adapter.review_create(source, domain="test-domain", owners=[])
    result = adapter.create_product(
        source, domain="test-domain", reviewed_sha256=review.review_sha256, owners=[]
    )
    assert result.status == "created_contract_failed" and result.product_id == "new-id"
    assert result.contract_import["status"] == "blocked"


def test_product_creation_preserves_id_if_link_disappears_after_create(
    config_file, monkeypatch
):
    import yaml

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    source = _odps_with_contract({"type": "ODCS", "spec": yaml.safe_load(VALID_ODCS)})
    native = b'{"id":"new-id","name":"sample_product","displayName":"Sample product","dataProductType":"DATASET","visibility":"PRIVATE","domains":[{"fullyQualifiedName":"test-domain"}]}'
    adapter._opener = Opener([b'{"version":"2.1.0"}', b'{"id":"new-id"}', native])
    from open_data_products.integrations import create as create_module

    original = create_module._resolve_product_contract
    calls = []

    def resolver(*args):
        calls.append(1)
        if len(calls) == 3:
            raise IntegrationError("Contract link is unavailable")
        return original(*args)

    monkeypatch.setattr(create_module, "_resolve_product_contract", resolver)
    review = adapter.review_create(source, domain="test-domain", owners=[])
    result = adapter.create_product(
        source, domain="test-domain", reviewed_sha256=review.review_sha256, owners=[]
    )
    assert result.status == "created_contract_failed" and result.product_id == "new-id"
    assert result.contract_import["status"] == "failed_or_unknown"


def test_linked_contract_is_resolved_relative_and_bound_to_review(
    config_file, tmp_path
):
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    product_path = tmp_path / "product.yaml"
    contract_path = tmp_path / "contract.yaml"
    contract_path.write_text(VALID_ODCS)
    source = _odps_with_contract({"type": "ODCS", "$ref": "contract.yaml"})
    product_path.write_text(source)
    with pytest.raises(IntegrationError, match="source file path"):
        adapter.review_create(source, domain="test-domain", owners=[])
    review = adapter.review_create(
        source, domain="test-domain", source_path=str(product_path), owners=[]
    )
    contract_path.write_text(VALID_ODCS.replace("Test association", "Changed"))
    with pytest.raises(IntegrationError, match="digest"):
        adapter.create_product(
            source,
            domain="test-domain",
            source_path=str(product_path),
            reviewed_sha256=review.review_sha256,
            owners=[],
        )


def test_cli_review_product_with_relative_contract(
    config_file, tmp_path, monkeypatch, capsys
):
    config_file.write_text(
        config_file.read_text().replace(
            "    platform: openmetadata\n",
            "    read_only: false\n    platform: openmetadata\n",
            1,
        )
    )
    contract = tmp_path / "contract.yaml"
    contract.write_text(VALID_ODCS)
    product = tmp_path / "product.yaml"
    product.write_text(_odps_with_contract({"type": "ODCS", "$ref": "contract.yaml"}))
    opener = Opener([])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    command = [
        "integrations",
        "products",
        "create",
        "--no-owner",
        "dev",
        "--config",
        str(config_file),
        "--source",
        str(product),
        "--domain",
        "test-domain",
        "--json",
    ]
    assert main(command) == 0
    review = json.loads(capsys.readouterr().out)
    assert review["contract_import"]["planned"]
    contract.write_text(VALID_ODCS.replace("Test association", "Changed"))
    assert (
        main(command + ["--execute", "--reviewed-sha256", review["review_sha256"]]) == 1
    )
    assert not opener.requests


def test_linked_odcs_duplicate_keys_are_rejected(config_file, tmp_path):
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    product = tmp_path / "product.yaml"
    (tmp_path / "contract.yaml").write_text(VALID_ODCS + "version: 9.9.9\n")
    source = _odps_with_contract({"type": "ODCS", "$ref": "contract.yaml"})
    with pytest.raises(IntegrationError, match="Cannot resolve"):
        adapter.review_create(
            source, domain="test-domain", source_path=str(product), owners=[]
        )


def test_product_creation_reviews_schema_contract_before_network(config_file):
    import yaml

    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    contract = yaml.safe_load(VALID_ODCS)
    contract["schema"] = [
        {"name": "orders", "properties": [{"name": "id", "logicalType": "string"}]}
    ]
    source = _odps_with_contract({"type": "ODCS", "spec": contract})
    adapter._opener = Opener([])
    review = adapter.review_create(source, domain="test-domain", owners=[])
    assert review.contract_import["planned"]
    assert not adapter._opener.requests


def test_review_and_import_odcs_contract_to_product(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    preview = b'{"valid":true,"odcsImportReport":{"canImport":true,"issues":[]}}'
    contract_id = "43742f9e-5c5d-45e0-b78b-a479a67c3347"
    import hashlib

    native = json.dumps(
        {
            "id": contract_id,
            "version": 0.1,
            "entity": {"id": DELETE_PRODUCT_ID, "type": "dataProduct"},
            "odcsPreservedFields": {"document": "{}"},
        }
    ).encode()
    saved = json.dumps(
        {
            "id": contract_id,
            "version": 0.2,
            "entity": {"id": DELETE_PRODUCT_ID, "type": "dataProduct"},
            "odcsPreservedFields": {
                "document": "{}",
                "odpsSdkSource": {
                    "format": "odcs-yaml-v1",
                    "version": "0.1.0",
                    "sha256": hashlib.sha256(VALID_ODCS.encode()).hexdigest(),
                    "yaml": VALID_ODCS,
                },
            },
        }
    ).encode()
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            _contract_absent(),
            preview,
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            _contract_absent(),
            preview,
            native,
            native,
            b"{}",
            saved,
            native,
        ]
    )
    review = adapter.review_contract_import(VALID_ODCS, product_id=DELETE_PRODUCT_ID)
    assert review.executable and review.validation["valid"]
    result = adapter.import_contract(
        VALID_ODCS, product_id=DELETE_PRODUCT_ID, reviewed_sha256=review.review_sha256
    )
    assert result.status == "created" and result.contract_id == contract_id
    assert result.comparison == {
        "contract_id": "matched",
        "product": "matched",
        "association": "matched",
        "source": "matched",
    }
    methods = [r.method for r in adapter._opener.requests]
    assert methods.count("POST") == 3  # Two non-writing validations and one import.
    assert "createTestCases=false" in adapter._opener.requests[8].full_url
    assert adapter._opener.requests[8].get_header("Content-type") == "application/yaml"
    assert adapter._opener.requests[10].method == "PATCH"
    assert adapter._opener.requests[10].get_header("If-match") == 'W/"0.1"'


def test_contract_import_cli_review_and_execute(
    config_file, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    config_file.write_text(
        config_file.read_text().replace(
            "    platform: openmetadata\n",
            "    read_only: false\n    platform: openmetadata\n",
            1,
        )
    )
    source = tmp_path / "contract.yaml"
    source.write_text(VALID_ODCS)
    preview = b'{"valid":true,"odcsImportReport":{"canImport":true,"issues":[]}}'
    import hashlib

    native = json.dumps(
        {
            "id": "43742f9e-5c5d-45e0-b78b-a479a67c3347",
            "version": 0.1,
            "entity": {"id": DELETE_PRODUCT_ID, "type": "dataProduct"},
            "odcsPreservedFields": {"document": "{}"},
        }
    ).encode()
    saved = json.dumps(
        {
            "id": "43742f9e-5c5d-45e0-b78b-a479a67c3347",
            "version": 0.2,
            "entity": {"id": DELETE_PRODUCT_ID, "type": "dataProduct"},
            "odcsPreservedFields": {
                "document": "{}",
                "odpsSdkSource": {
                    "format": "odcs-yaml-v1",
                    "version": "0.1.0",
                    "sha256": hashlib.sha256(VALID_ODCS.encode()).hexdigest(),
                    "yaml": VALID_ODCS,
                },
            },
        }
    ).encode()
    opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            _contract_absent(),
            preview,
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            _contract_absent(),
            preview,
            native,
            native,
            b"{}",
            saved,
            native,
        ]
    )
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    command = [
        "integrations",
        "products",
        "contract-import",
        "dev",
        "--config",
        str(config_file),
        "--id",
        DELETE_PRODUCT_ID,
        "--source",
        str(source),
        "--json",
    ]
    assert main(command) == 0
    review = json.loads(capsys.readouterr().out)
    assert review["executable"]
    assert (
        main(command + ["--execute", "--reviewed-sha256", review["review_sha256"]]) == 0
    )
    assert json.loads(capsys.readouterr().out)["comparison"]["association"] == "matched"


def test_contract_get_cli_returns_product_contract(config_file, monkeypatch, capsys):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    native = b'{"id":"43742f9e-5c5d-45e0-b78b-a479a67c3347","entity":{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","type":"dataProduct"}}'
    opener = Opener([native])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    assert (
        main(
            [
                "integrations",
                "products",
                "contract-get",
                "dev",
                "--config",
                str(config_file),
                "--id",
                DELETE_PRODUCT_ID,
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["entity"]["id"] == DELETE_PRODUCT_ID
    assert [r.method for r in opener.requests] == ["GET"]


def test_preserved_contract_source_cli_saves_exact_yaml(
    config_file, monkeypatch, capsys, tmp_path
):
    import hashlib
    import yaml

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    contract_id = "43742f9e-5c5d-45e0-b78b-a479a67c3347"
    source_yaml = (
        VALID_ODCS
        + "schema:\n  - name: records\n    properties:\n      - name: customer_id\n        logicalType: string\n"
    )
    native = {
        "id": contract_id,
        "entity": {"id": DELETE_PRODUCT_ID, "type": "dataProduct"},
        "odcsPreservedFields": {
            "odpsSdkSource": {
                "format": "odcs-yaml-v1",
                "version": "0.1.0",
                "sha256": hashlib.sha256(source_yaml.encode()).hexdigest(),
                "yaml": source_yaml,
            }
        },
    }
    opener = Opener(
        [json.dumps({"id": contract_id}).encode(), json.dumps(native).encode()]
    )
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    output = tmp_path / "contract.yaml"
    assert (
        main(
            [
                "integrations",
                "products",
                "contract-source",
                "dev",
                "--config",
                str(config_file),
                "--id",
                DELETE_PRODUCT_ID,
                "--output",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["version"] == "0.1.0" and result["saved"]
    assert output.read_text() == source_yaml
    restored = yaml.safe_load(output.read_text())
    assert restored["version"] == "0.1.0"
    assert restored["schema"][0]["properties"][0]["name"] == "customer_id"


def test_preserved_contract_source_detects_tampering(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    native = {
        "id": "43742f9e-5c5d-45e0-b78b-a479a67c3347",
        "entity": {"id": DELETE_PRODUCT_ID, "type": "dataProduct"},
        "odcsPreservedFields": {
            "odpsSdkSource": {
                "format": "odcs-yaml-v1",
                "version": "0.1.0",
                "sha256": "wrong",
                "yaml": VALID_ODCS,
            }
        },
    }
    adapter._opener = Opener(
        [b'{"id":"43742f9e-5c5d-45e0-b78b-a479a67c3347"}', json.dumps(native).encode()]
    )
    with pytest.raises(IntegrationError, match="integrity"):
        adapter.get_preserved_contract_source(DELETE_PRODUCT_ID)


def test_contract_import_blocks_platform_validation_and_existing_contract(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    invalid = b'{"valid":false,"odcsImportReport":{"canImport":false,"issues":[{"message":"Schema unsupported"}]}}'
    adapter._opener = Opener(
        [b'{"version":"2.1.0"}', DELETE_PRODUCT, _contract_absent(), invalid]
    )
    review = adapter.review_contract_import(VALID_ODCS, product_id=DELETE_PRODUCT_ID)
    assert not review.executable and not review.validation["valid"]
    adapter._opener = Opener(
        [b'{"version":"2.1.0"}', DELETE_PRODUCT, b'{"id":"existing"}']
    )
    with pytest.raises(IntegrationError, match="already has"):
        adapter.review_contract_import(VALID_ODCS, product_id=DELETE_PRODUCT_ID)
    assert all("/odcs/yaml?" not in req.full_url for req in adapter._opener.requests)


def test_schema_contract_review_uses_schema_free_native_projection(
    config_file, monkeypatch
):
    import yaml

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    source = (
        VALID_ODCS
        + "schema:\n  - name: rows\n    properties:\n      - name: id\n        logicalType: string\n"
    )
    invalid = json.dumps(
        {
            "valid": False,
            "odcsImportReport": {
                "canImport": False,
                "issues": [
                    {
                        "severity": "blocking",
                        "message": "Schema validation is not supported for dataProduct entities",
                    }
                ],
            },
        }
    ).encode()
    projection = b'{"valid":true,"odcsImportReport":{"canImport":true,"issues":[]}}'
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            _contract_absent(),
            invalid,
            projection,
        ]
    )
    review = adapter.review_contract_import(source, product_id=DELETE_PRODUCT_ID)
    assert review.executable and review.schema_preserved
    assert review.source_version == "0.1.0" and not review.source_validation["valid"]
    assert any("does not validate product schemas" in item for item in review.warnings)
    assert "schema" in yaml.safe_load(adapter._opener.requests[-2].data)
    assert "schema" not in yaml.safe_load(adapter._opener.requests[-1].data)


def test_schema_source_with_other_blocking_findings_is_not_imported(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    source = (
        VALID_ODCS
        + "schema:\n  - name: rows\n    properties:\n      - name: id\n        logicalType: string\n"
    )
    invalid = b'{"valid":false,"odcsImportReport":{"canImport":false,"issues":[{"severity":"blocking","message":"Other source problem"}]}}'
    projection = b'{"valid":true,"odcsImportReport":{"canImport":true,"issues":[]}}'
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            _contract_absent(),
            invalid,
            projection,
        ]
    )
    review = adapter.review_contract_import(source, product_id=DELETE_PRODUCT_ID)
    assert not review.executable and review.source_validation["valid"] is False


def test_contract_import_timeout_does_not_retry(config_file, monkeypatch):
    from open_data_products import UnknownContractImportOutcome

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    preview = b'{"valid":true,"odcsImportReport":{"canImport":true,"issues":[]}}'
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            _contract_absent(),
            preview,
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            _contract_absent(),
            preview,
            TimeoutError("private"),
        ]
    )
    review = adapter.review_contract_import(VALID_ODCS, product_id=DELETE_PRODUCT_ID)
    with pytest.raises(UnknownContractImportOutcome, match="unknown"):
        adapter.import_contract(
            VALID_ODCS,
            product_id=DELETE_PRODUCT_ID,
            reviewed_sha256=review.review_sha256,
        )
    assert (
        sum(
            "/dataContracts/odcs/yaml?" in req.full_url
            for req in adapter._opener.requests
        )
        == 1
    )


def test_contract_preservation_timeout_reports_contract_id_without_retry(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    preview = b'{"valid":true,"odcsImportReport":{"canImport":true,"issues":[]}}'
    native = b'{"id":"43742f9e-5c5d-45e0-b78b-a479a67c3347","version":0.1,"entity":{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","type":"dataProduct"},"odcsPreservedFields":{}}'
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            _contract_absent(),
            preview,
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            _contract_absent(),
            preview,
            native,
            native,
            TimeoutError("private"),
        ]
    )
    review = adapter.review_contract_import(VALID_ODCS, product_id=DELETE_PRODUCT_ID)
    result = adapter.import_contract(
        VALID_ODCS, product_id=DELETE_PRODUCT_ID, reviewed_sha256=review.review_sha256
    )
    assert result.status == "created_preservation_unknown"
    assert result.contract_id == "43742f9e-5c5d-45e0-b78b-a479a67c3347"
    assert [r.method for r in adapter._opener.requests].count("PATCH") == 1


def test_contract_import_rejects_unknown_schema_object(config_file):
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    source = VALID_ODCS + "schema:\n  - name: one\n  - name: two\n"
    with pytest.raises(IntegrationError, match="exactly one"):
        adapter.review_contract_import(
            source, product_id=DELETE_PRODUCT_ID, object_name="missing"
        )


def test_delete_review_reports_permanent_recursive_without_mutation(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    adapter._opener = Opener([b'{"version":"2.1.0"}', DELETE_PRODUCT])
    review = adapter.review_delete(DELETE_PRODUCT_ID)
    assert review.product_id == DELETE_PRODUCT_ID
    assert review.permanent and review.recursive and not review.write_enabled
    assert "cannot be restored" in review.warnings[0]
    assert [r.method for r in adapter._opener.requests] == ["GET", "GET"]


def test_delete_requires_write_profile_confirmation_and_unchanged_target(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    profile = load_integration_config(config_file).select()
    readonly = OpenMetadataAdapter(profile)
    readonly._opener = Opener([])
    with pytest.raises(IntegrationError, match="read-only"):
        readonly.delete_product(
            DELETE_PRODUCT_ID, reviewed_sha256="x", confirm_permanent=True
        )
    adapter = OpenMetadataAdapter(replace(profile, read_only=False))
    adapter._opener = Opener([])
    with pytest.raises(IntegrationError, match="confirmation"):
        adapter.delete_product(
            DELETE_PRODUCT_ID, reviewed_sha256="x", confirm_permanent=False
        )
    assert not adapter._opener.requests
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT.replace(b"0.1", b"0.2"),
        ]
    )
    review = adapter.review_delete(DELETE_PRODUCT_ID)
    with pytest.raises(IntegrationError, match="changed"):
        adapter.delete_product(
            DELETE_PRODUCT_ID,
            reviewed_sha256=review.review_sha256,
            confirm_permanent=True,
        )
    assert all(r.method == "GET" for r in adapter._opener.requests)


def test_delete_executes_once_and_verifies_absence(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    absent = HTTPError("https://example.test", 404, "not found", {}, io.BytesIO())
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            b"",
            absent,
        ]
    )
    review = adapter.review_delete(DELETE_PRODUCT_ID)
    result = adapter.delete_product(
        DELETE_PRODUCT_ID, reviewed_sha256=review.review_sha256, confirm_permanent=True
    )
    assert (
        result.status == "delete_accepted" and result.verification == "not_found_by_id"
    )
    assert result.permanent and result.recursive
    assert [r.method for r in adapter._opener.requests] == [
        "GET",
        "GET",
        "GET",
        "GET",
        "DELETE",
        "GET",
    ]


def test_delete_cli_unverified_returns_nonzero_with_target(
    config_file, monkeypatch, capsys
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    config_file.write_text(
        config_file.read_text().replace(
            "    platform: openmetadata\n",
            "    read_only: false\n    platform: openmetadata\n",
            1,
        )
    )
    profile = load_integration_config(config_file).select()
    review_adapter = OpenMetadataAdapter(profile)
    review_adapter._opener = Opener([b'{"version":"2.1.0"}', DELETE_PRODUCT])
    review = review_adapter.review_delete(DELETE_PRODUCT_ID)
    forbidden = HTTPError("https://example.test", 403, "forbidden", {}, io.BytesIO())
    opener = Opener([b'{"version":"2.1.0"}', DELETE_PRODUCT, b"", forbidden])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    status = main(
        [
            "integrations",
            "products",
            "delete",
            "dev",
            "--config",
            str(config_file),
            "--id",
            DELETE_PRODUCT_ID,
            "--execute",
            "--confirm-permanent",
            "--reviewed-sha256",
            review.review_sha256,
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert status == 1 and result["verification"] == "unavailable"
    assert result["product_id"] == DELETE_PRODUCT_ID
    assert [req.method for req in opener.requests].count("DELETE") == 1


def test_create_detects_visibility_mismatch(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            b'{"id":"new-id"}',
            b'{"id":"new-id","name":"sample_product","displayName":"Sample product","dataProductType":"DATASET","visibility":"PUBLIC"}',
        ]
    )
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    result = adapter.create_product(
        VALID_ODPS,
        domain="test-domain",
        reviewed_sha256=review.review_sha256,
        owners=[],
    )
    assert result.status == "created_with_mismatches"
    assert result.comparison["visibility"] == "different_or_missing"


def test_delete_timeout_is_unknown_and_never_retried(config_file, monkeypatch):
    from open_data_products import UnknownDeleteOutcome

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            TimeoutError("private"),
        ]
    )
    review = adapter.review_delete(DELETE_PRODUCT_ID)
    with pytest.raises(UnknownDeleteOutcome, match="unknown"):
        adapter.delete_product(
            DELETE_PRODUCT_ID,
            reviewed_sha256=review.review_sha256,
            confirm_permanent=True,
        )
    assert [r.method for r in adapter._opener.requests].count("DELETE") == 1


def test_delete_cli_requires_confirmation_before_any_network(
    config_file, monkeypatch, capsys
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    original = config_file.read_text().replace(
        "    platform: openmetadata\n",
        "    read_only: false\n    platform: openmetadata\n",
        1,
    )
    config_file.write_text(original)
    opener = Opener([])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    status = main(
        [
            "integrations",
            "products",
            "delete",
            "dev",
            "--config",
            str(config_file),
            "--id",
            DELETE_PRODUCT_ID,
            "--execute",
            "--reviewed-sha256",
            "abcd",
        ]
    )
    captured = capsys.readouterr()
    assert status == 1
    assert "confirmation" in captured.err
    assert not opener.requests


def test_review_and_update_title_description_with_revision(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    old = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"sample_product","displayName":"Old","description":"Before","version":0.1}'
    new = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"sample_product","displayName":"New","description":"After","version":0.2}'
    adapter._opener = Opener(
        [b'{"version":"2.1.0"}', old, b'{"version":"2.1.0"}', old, b"{}", new]
    )
    review = adapter.review_update(DELETE_PRODUCT_ID, title="New", description="After")
    assert review.before == {"displayName": "Old", "description": "Before"}
    result = adapter.update_product(
        DELETE_PRODUCT_ID,
        title="New",
        description="After",
        reviewed_sha256=review.review_sha256,
    )
    assert result.comparison == {"displayName": "matched", "description": "matched"}
    assert result.previous_revision == "0.1" and result.current_revision == "0.2"
    request = adapter._opener.requests[4]
    assert request.method == "PATCH"
    assert request.get_header("If-match") == 'W/"0.1"'
    assert json.loads(request.data) == [
        {"op": "add", "path": "/displayName", "value": "New"},
        {"op": "add", "path": "/description", "value": "After"},
    ]


def test_update_from_odps_reviews_and_applies_supported_fields(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    source = VALID_ODPS + "      description: Updated description\n"
    old = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"sample_product","displayName":"Old","description":"Before","version":0.1}'
    new = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"sample_product","displayName":"Sample product","description":"Updated description","version":0.2}'
    adapter._opener = Opener(
        [b'{"version":"2.1.0"}', old, b'{"version":"2.1.0"}', old, b"{}", new]
    )
    review = adapter.review_update(DELETE_PRODUCT_ID, source_yaml=source)
    assert review.proposed == {
        "displayName": "Sample product",
        "description": "Updated description",
    }
    assert review.source_validation["valid"] is True
    assert "/product/details/en/status" in review.source_unsupported_fields
    result = adapter.update_product(
        DELETE_PRODUCT_ID, source_yaml=source, reviewed_sha256=review.review_sha256
    )
    assert all(value == "matched" for value in result.comparison.values())
    assert adapter._opener.requests[4].method == "PATCH"


def test_odps_update_blocks_invalid_wrong_product_and_changed_source(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    adapter._opener = Opener([])
    with pytest.raises(IntegrationError, match="validation"):
        adapter.review_update(
            DELETE_PRODUCT_ID, source_yaml=VALID_ODPS.replace("type: dataset", "")
        )
    assert not adapter._opener.requests
    other = (
        b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"other","version":0.1}'
    )
    adapter._opener = Opener([b'{"version":"2.1.0"}', other])
    with pytest.raises(IntegrationError, match="productID"):
        adapter.review_update(DELETE_PRODUCT_ID, source_yaml=VALID_ODPS)
    old = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"sample_product","version":0.1}'
    adapter._opener = Opener([b'{"version":"2.1.0"}', old, b'{"version":"2.1.0"}', old])
    review = adapter.review_update(DELETE_PRODUCT_ID, source_yaml=VALID_ODPS)
    with pytest.raises(IntegrationError, match="changed"):
        adapter.update_product(
            DELETE_PRODUCT_ID,
            source_yaml=VALID_ODPS + "# changed\n",
            reviewed_sha256=review.review_sha256,
        )
    assert all(req.method == "GET" for req in adapter._opener.requests)


def test_review_and_add_owner_and_tag_preserves_existing_assignments(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    prior = {
        "id": DELETE_PRODUCT_ID,
        "version": 0.1,
        "owners": [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "type": "team",
                "name": "existing",
            }
        ],
        "tags": [
            {
                "tagFQN": "Tier.Tier1",
                "source": "Classification",
                "labelType": "Manual",
                "state": "Confirmed",
            }
        ],
    }
    user = {
        "id": "22222222-2222-4222-8222-222222222222",
        "fullyQualifiedName": "jarkko",
        "deleted": False,
    }
    tag = {
        "id": "33333333-3333-4333-8333-333333333333",
        "fullyQualifiedName": "PII.Sensitive",
        "deleted": False,
    }
    updated = dict(
        prior,
        version=0.2,
        owners=prior["owners"] + [{"id": user["id"], "type": "user", "name": "jarkko"}],
        tags=prior["tags"]
        + [
            {
                "tagFQN": "PII.Sensitive",
                "source": "Classification",
                "labelType": "Manual",
                "state": "Confirmed",
            }
        ],
    )
    enc = lambda x: json.dumps(x).encode()
    baseline = [b'{"version":"2.1.0"}', enc(prior), enc(user), enc(tag)]
    adapter._opener = Opener(baseline + baseline + [b"{}", enc(updated)])
    review = adapter.review_update(
        DELETE_PRODUCT_ID, owners=["user:jarkko"], tags=["PII.Sensitive"]
    )
    assert len(review.proposed["owners"]) == 2 and len(review.proposed["tags"]) == 2
    result = adapter.update_product(
        DELETE_PRODUCT_ID,
        owners=["user:jarkko"],
        tags=["PII.Sensitive"],
        reviewed_sha256=review.review_sha256,
    )
    assert result.comparison == {"owners": "matched", "tags": "matched"}
    patch = json.loads(adapter._opener.requests[-2].data)
    assert [x["path"] for x in patch] == ["/owners", "/tags"]
    assert len(patch[0]["value"]) == len(patch[1]["value"]) == 2


def test_owner_update_blocks_missing_current_assignments(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    adapter._opener = Opener([b'{"version":"2.1.0"}', DELETE_PRODUCT])
    with pytest.raises(IntegrationError, match="owners are unavailable"):
        adapter.review_update(DELETE_PRODUCT_ID, owners=["user:jarkko"])
    assert all(req.method == "GET" for req in adapter._opener.requests)


def test_create_defaults_to_authenticated_account_and_binds_identity(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    first = b'{"id":"22222222-2222-4222-8222-222222222222","fullyQualifiedName":"jarkko","deleted":false}'
    second = b'{"id":"33333333-3333-4333-8333-333333333333","fullyQualifiedName":"other","deleted":false}'
    adapter._opener = Opener([first, second])
    review = adapter.review_create(VALID_ODPS, domain="test-domain")
    assert review.assignments["owners"] == [
        {"id": "22222222-2222-4222-8222-222222222222", "type": "user", "name": "jarkko"}
    ]
    assert "users/loggedInUser" in adapter._opener.requests[0].full_url
    with pytest.raises(IntegrationError, match="digest"):
        adapter.create_product(
            VALID_ODPS, domain="test-domain", reviewed_sha256=review.review_sha256
        )
    assert all(req.method == "GET" for req in adapter._opener.requests)


def test_create_blocks_missing_authenticated_account(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    adapter._opener = Opener([b'{"name":"unknown"}'])
    with pytest.raises(IntegrationError, match="Authenticated user"):
        adapter.review_create(VALID_ODPS, domain="test-domain")


@pytest.mark.parametrize("assignment_fails", [False, True])
def test_create_reports_assignment_outcome(config_file, monkeypatch, assignment_fails):
    from types import SimpleNamespace

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    user = b'{"id":"22222222-2222-4222-8222-222222222222","fullyQualifiedName":"jarkko","deleted":false}'
    tag = b'{"id":"33333333-3333-4333-8333-333333333333","fullyQualifiedName":"PII.NonSensitive","deleted":false}'
    native = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"sample_product","displayName":"Sample product","visibility":"PRIVATE","dataProductType":"DATASET","domains":[{"fullyQualifiedName":"test-domain"}]}'
    adapter._opener = Opener(
        [
            user,
            tag,
            user,
            tag,
            b'{"version":"2.1.0"}',
            b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f"}',
            native,
            user,
            tag,
        ]
    )

    def review_update(*args, **kwargs):
        if assignment_fails:
            raise IntegrationError("Assignment failed")
        return SimpleNamespace(
            review_sha256="assignment-digest",
            proposed={
                "owners": [
                    {"id": "22222222-2222-4222-8222-222222222222", "type": "user"}
                ]
            },
        )

    monkeypatch.setattr(adapter, "review_update", review_update)
    monkeypatch.setattr(
        adapter,
        "update_product",
        lambda *args, **kwargs: SimpleNamespace(
            comparison={"owners": "matched", "tags": "matched"},
            to_dict=lambda: {"comparison": {"owners": "matched", "tags": "matched"}},
        ),
    )
    review = adapter.review_create(
        VALID_ODPS,
        domain="test-domain",
        owners=["user:jarkko"],
        tags=["PII.NonSensitive"],
    )
    result = adapter.create_product(
        VALID_ODPS,
        domain="test-domain",
        owners=["user:jarkko"],
        tags=["PII.NonSensitive"],
        reviewed_sha256=review.review_sha256,
    )
    assert result.status == (
        "created_assignments_failed" if assignment_fails else "created"
    )
    assert result.product_id == "2ae0905f-bf50-4491-bd19-e82e6ae6f05f"
    if assignment_fails:
        assert result.assignments["status"] == "failed_or_unknown"
    else:
        assert result.assignments["comparison"] == {
            "owners": "matched",
            "tags": "matched",
        }


def test_update_blocks_changed_target_and_read_only(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    profile = load_integration_config(config_file).select()
    readonly = OpenMetadataAdapter(profile)
    readonly._opener = Opener([])
    with pytest.raises(IntegrationError, match="read-only"):
        readonly.update_product(DELETE_PRODUCT_ID, title="New", reviewed_sha256="x")
    adapter = OpenMetadataAdapter(replace(profile, read_only=False))
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT.replace(b"0.1", b"0.2"),
        ]
    )
    review = adapter.review_update(DELETE_PRODUCT_ID, title="New")
    with pytest.raises(IntegrationError, match="changed"):
        adapter.update_product(
            DELETE_PRODUCT_ID, title="New", reviewed_sha256=review.review_sha256
        )
    assert all(r.method == "GET" for r in adapter._opener.requests)


def test_update_timeout_is_unknown_and_never_retried(config_file, monkeypatch):
    from open_data_products import UnknownUpdateOutcome

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            b'{"version":"2.1.0"}',
            DELETE_PRODUCT,
            TimeoutError("private"),
        ]
    )
    review = adapter.review_update(DELETE_PRODUCT_ID, title="New")
    with pytest.raises(UnknownUpdateOutcome, match="unknown"):
        adapter.update_product(
            DELETE_PRODUCT_ID, title="New", reviewed_sha256=review.review_sha256
        )
    assert [r.method for r in adapter._opener.requests].count("PATCH") == 1


def test_reviewed_domain_creation_and_readback(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    domain_id = "2ae0905f-bf50-4491-bd19-e82e6ae6f05f"
    native = json.dumps(
        {
            "id": domain_id,
            "name": "Retail",
            "fullyQualifiedName": "Retail",
            "description": "Retail data",
            "domainType": "Aggregate",
        }
    ).encode()
    adapter._opener = Opener([b'{"version":"2.1.0"}', native, native])
    review = adapter.review_domain_create(
        name="Retail", description="Retail data", domain_type="Aggregate"
    )
    result = adapter.create_domain(
        name="Retail",
        description="Retail data",
        domain_type="Aggregate",
        reviewed_sha256=review.review_sha256,
    )
    assert result.status == "created" and result.fqn == "Retail"
    assert [r.method for r in adapter._opener.requests] == ["GET", "POST", "GET"]
    assert json.loads(adapter._opener.requests[1].data)["domainType"] == "Aggregate"


def test_domain_creation_validates_parent_and_preserves_fqn(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    domain_id = "2ae0905f-bf50-4491-bd19-e82e6ae6f05f"
    native = json.dumps(
        {
            "id": domain_id,
            "name": "Sales",
            "fullyQualifiedName": "Retail.Sales",
            "description": "Sales data",
            "domainType": "Consumer-aligned",
            "parent": {"fullyQualifiedName": "Retail"},
        }
    ).encode()
    adapter._opener = Opener([b'{"version":"2.1.0"}', native, native])
    review = adapter.review_domain_create(
        name="Sales",
        description="Sales data",
        domain_type="Consumer-aligned",
        parent="Retail",
    )
    result = adapter.create_domain(
        name="Sales",
        description="Sales data",
        domain_type="Consumer-aligned",
        parent="Retail",
        reviewed_sha256=review.review_sha256,
    )
    assert result.status == "created" and result.fqn == "Retail.Sales"
    assert result.comparison["parent"] == "matched"
    assert json.loads(adapter._opener.requests[1].data)["parent"] == "Retail"


def test_domain_creation_blocks_readonly_changed_review_and_unknown_outcome(
    config_file, monkeypatch
):
    from open_data_products import UnknownDomainCreateOutcome

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    profile = load_integration_config(config_file).select()
    readonly = OpenMetadataAdapter(profile)
    review = readonly.review_domain_create(
        name="Retail", description="Retail data", domain_type="Aggregate"
    )
    with pytest.raises(IntegrationError, match="read-only"):
        readonly.create_domain(
            name="Retail",
            description="Retail data",
            domain_type="Aggregate",
            reviewed_sha256=review.review_sha256,
        )
    adapter = OpenMetadataAdapter(replace(profile, read_only=False))
    review = adapter.review_domain_create(
        name="Retail", description="Retail data", domain_type="Aggregate"
    )
    adapter._opener = Opener([])
    with pytest.raises(IntegrationError, match="digest"):
        adapter.create_domain(
            name="Retail",
            description="changed",
            domain_type="Aggregate",
            reviewed_sha256=review.review_sha256,
        )
    assert not adapter._opener.requests
    adapter._opener = Opener([b'{"version":"2.1.0"}', TimeoutError("secret")])
    with pytest.raises(UnknownDomainCreateOutcome, match="unknown"):
        adapter.create_domain(
            name="Retail",
            description="Retail data",
            domain_type="Aggregate",
            reviewed_sha256=review.review_sha256,
        )
    assert [r.method for r in adapter._opener.requests] == ["GET", "POST"]


def test_domain_create_cli_review_and_execute(config_file, monkeypatch, capsys):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    config_file.write_text(
        config_file.read_text().replace(
            "    platform: openmetadata\n",
            "    read_only: false\n    platform: openmetadata\n",
            1,
        )
    )
    domain_id = "2ae0905f-bf50-4491-bd19-e82e6ae6f05f"
    native = json.dumps(
        {
            "id": domain_id,
            "name": "Retail",
            "fullyQualifiedName": "Retail",
            "description": "Retail data",
            "domainType": "Aggregate",
        }
    ).encode()
    opener = Opener([b'{"version":"2.1.0"}', native, native])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    command = [
        "integrations",
        "domain-create",
        "dev",
        "--config",
        str(config_file),
        "--name",
        "Retail",
        "--description",
        "Retail data",
        "--type",
        "Aggregate",
        "--json",
    ]
    assert main(command) == 0
    digest = json.loads(capsys.readouterr().out)["review_sha256"]
    assert main(command + ["--execute", "--reviewed-sha256", digest]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "created" and result["fqn"] == "Retail"


def test_domain_create_rejects_invalid_values(config_file):
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    with pytest.raises(IntegrationError, match="Domain name"):
        adapter.review_domain_create(
            name="../bad", description="x", domain_type="Aggregate"
        )
    with pytest.raises(IntegrationError, match="Domain type"):
        adapter.review_domain_create(
            name="Retail", description="x", domain_type="Unknown"
        )


def test_review_and_change_domain_with_revision(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    domain_id = "43742f9e-5c5d-45e0-b78b-a479a67c3347"
    old = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"test","version":0.1,"domains":[{"fullyQualifiedName":"Old"}]}'
    new = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"test","version":0.2,"domains":[{"fullyQualifiedName":"New"}]}'
    target = json.dumps({"id": domain_id, "fullyQualifiedName": "New"}).encode()
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            old,
            target,
            b'{"version":"2.1.0"}',
            old,
            target,
            b"{}",
            new,
        ]
    )
    review = adapter.review_update(DELETE_PRODUCT_ID, domain="New")
    assert review.before["domain"] == ["Old"] and review.proposed["domain"] == "New"
    assert "migrate" in review.warnings[-1]
    result = adapter.update_product(
        DELETE_PRODUCT_ID, domain="New", reviewed_sha256=review.review_sha256
    )
    assert result.comparison == {"domain": "matched"}
    patch = adapter._opener.requests[6]
    assert patch.get_header("If-match") == 'W/"0.1"'
    assert json.loads(patch.data) == [
        {
            "op": "add",
            "path": "/domains",
            "value": [{"id": domain_id, "type": "domain"}],
        }
    ]


def test_domain_update_blocks_changed_baseline(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    old = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"test","version":0.1,"domains":[]}'
    target = b'{"id":"43742f9e-5c5d-45e0-b78b-a479a67c3347","fullyQualifiedName":"New"}'
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            old,
            target,
            b'{"version":"2.1.0"}',
            old.replace(b"0.1", b"0.2"),
            target,
        ]
    )
    review = adapter.review_update(DELETE_PRODUCT_ID, domain="New")
    with pytest.raises(IntegrationError, match="changed"):
        adapter.update_product(
            DELETE_PRODUCT_ID, domain="New", reviewed_sha256=review.review_sha256
        )
    assert all(req.method == "GET" for req in adapter._opener.requests)


@pytest.mark.parametrize(
    "version,schema", [("4.2", "4.2"), ("4.1", "4.2"), (None, "4.1")]
)
def test_create_review_requires_explicit_compatible_version(
    config_file, version, schema
):
    import yaml

    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    document = yaml.safe_load(VALID_ODPS)
    document["schema"] = "https://opendataproducts.org/v" + schema + "/schema/odps.json"
    if version is None:
        del document["version"]
    else:
        document["version"] = version
    review = adapter.review_create(
        yaml.safe_dump(document), domain="test-domain", owners=[]
    )
    assert not review.compatible and not review.executable
    assert any(
        "--odps-version 4.1" in warning and "conversion" in warning
        for warning in review.warnings
    )
    writable = OpenMetadataAdapter(replace(adapter.profile, read_only=False))
    writable._opener = Opener([])
    with pytest.raises(IntegrationError, match="--odps-version 4.1"):
        writable.create_product(
            yaml.safe_dump(document),
            domain="test-domain",
            reviewed_sha256="unused",
            owners=[],
        )
    assert not writable._opener.requests


def test_compare_source_with_native_and_invalid_export(config_file, monkeypatch):
    import yaml

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    source = yaml.safe_load(VALID_ODPS)
    detail = source["product"]["details"]["en"]
    detail.update(
        {
            "description": "Source description",
            "updated": "2026-11-25",
            "status": "draft",
        }
    )
    source["product"]["contract"] = {"type": "ODCS"}
    native = {
        "id": "product-id",
        "name": "sample_product",
        "displayName": "Sample product",
        "description": None,
        "visibility": "PRIVATE",
        "dataProductType": "DATASET",
        "domains": [{"fullyQualifiedName": "test-domain"}],
        "updatedAt": 1795580308927,
        "version": 0.3,
    }
    export = {
        "schema": source["schema"],
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "name": "Sample product",
                    "productID": "sample_product",
                    "visibility": "private",
                    "status": "development",
                    "type": "dataset",
                    "updated": 1795580308927,
                }
            }
        },
    }
    adapter._opener = Opener(
        [
            json.dumps(native).encode(),
            yaml.safe_dump(export).encode(),
            json.dumps(native).encode(),
        ]
    )
    report = adapter.compare_product(
        yaml.safe_dump(source), product_id="product-id", domain="test-domain"
    )
    fields = {field.path: field for field in report.fields}
    assert fields["/version"].status == "preserved"
    assert fields["/schema"].status == "preserved"
    assert fields["/destination/domain"].status == "preserved"
    assert fields["/product/details/en/name"].status == "preserved"
    assert fields["/product/details/en/visibility"].status == "normalized"
    assert fields["/product/details/en/description"].status == "omitted"
    assert fields["/product/details/en/status"].status == "changed"
    assert fields["/product/details/en/updated"].status == "normalized"
    assert fields["/product/contract"].status == "omitted"
    assert "may exist elsewhere" in fields["/product/contract"].explanation
    assert (
        report.platform_updated_at == 1795580308927
        and report.export_updated == 1795580308927
    )
    assert report.export_validation is not None and not report.export_validation.valid
    assert report.native_provenance.revision == "0.3"


def test_compare_marks_missing_native_and_unavailable_export_unverified(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    native = b'{"id":"product-id","name":"sample_product","domains":[],"version":0.1}'
    missing = HTTPError("https://example.test", 404, "not found", {}, io.BytesIO())
    adapter._opener = Opener([native, missing])
    report = adapter.compare_product(
        VALID_ODPS, product_id="product-id", domain="test-domain"
    )
    fields = {field.path: field for field in report.fields}
    assert fields["/destination/domain"].status == "changed"
    assert fields["/product/details/en/name"].status == "unverified"
    assert fields["/product/details/en/status"].status == "unverified"
    assert report.export_validation is None and "unavailable" in report.warnings[-1]


def test_compare_cli_saves_report_without_platform_writes(
    config_file, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    native = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"sample_product","displayName":"Sample product","visibility":"PRIVATE","dataProductType":"DATASET","domains":[{"fullyQualifiedName":"test-domain"}],"version":0.1}'
    missing = HTTPError("https://example.test", 404, "not found", {}, io.BytesIO())
    opener = Opener([native, missing])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    source = tmp_path / "source.yaml"
    source.write_text(VALID_ODPS)
    output = tmp_path / "comparison.json"
    assert (
        main(
            [
                "integrations",
                "products",
                "compare",
                "dev",
                "--config",
                str(config_file),
                "--source",
                str(source),
                "--id",
                "2ae0905f-bf50-4491-bd19-e82e6ae6f05f",
                "--domain",
                "test-domain",
                "--output",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    report = json.loads(output.read_text())
    assert (
        report["product_id"] == "2ae0905f-bf50-4491-bd19-e82e6ae6f05f"
        and report["source_validation"]["valid"]
    )
    assert (
        json.loads(capsys.readouterr().out)["source_sha256"] == report["source_sha256"]
    )
    assert all(req.method == "GET" for req in opener.requests)


def test_legacy_compare_cli_rejects_names_without_platform_request(
    config_file, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    opener = Opener([])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    source = tmp_path / "source.yaml"
    source.write_text(VALID_ODPS)
    assert (
        main(
            [
                "integrations",
                "products",
                "compare",
                "dev",
                "--config",
                str(config_file),
                "--source",
                str(source),
                "--id",
                "Campaign Eligibility",
                "--domain",
                "test-domain",
                "--json",
            ]
        )
        == 1
    )
    assert "UUID" in capsys.readouterr().err
    assert not opener.requests


def test_domain_update_cli_review_and_execute(config_file, monkeypatch, capsys):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    config_file.write_text(
        config_file.read_text().replace(
            "    platform: openmetadata\n",
            "    read_only: false\n    platform: openmetadata\n",
            1,
        )
    )
    old = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"test","version":0.1,"domains":[{"fullyQualifiedName":"Old"}]}'
    new = b'{"id":"2ae0905f-bf50-4491-bd19-e82e6ae6f05f","name":"test","version":0.2,"domains":[{"fullyQualifiedName":"New"}]}'
    target = b'{"id":"43742f9e-5c5d-45e0-b78b-a479a67c3347","fullyQualifiedName":"New"}'
    opener = Opener(
        [
            b'{"version":"2.1.0"}',
            old,
            target,
            b'{"version":"2.1.0"}',
            old,
            target,
            b"{}",
            new,
        ]
    )
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    command = [
        "integrations",
        "products",
        "update",
        "dev",
        "--config",
        str(config_file),
        "--id",
        DELETE_PRODUCT_ID,
        "--domain",
        "New",
        "--json",
    ]
    assert main(command) == 0
    review = json.loads(capsys.readouterr().out)
    assert (
        review["before"]["domain"] == ["Old"] and review["proposed"]["domain"] == "New"
    )
    assert (
        main(command + ["--execute", "--reviewed-sha256", review["review_sha256"]]) == 0
    )
    assert json.loads(capsys.readouterr().out)["comparison"]["domain"] == "matched"


@pytest.mark.parametrize("operation", ["read", "create", "update", "delete"])
def test_truncated_platform_responses_are_sanitized_and_writes_not_retried(
    config_file, monkeypatch, operation
):
    from open_data_products import (
        UnknownCreateOutcome,
        UnknownDeleteOutcome,
        UnknownUpdateOutcome,
    )

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    failure = IncompleteRead(b"private response", 10)
    if operation == "read":
        adapter._opener = Opener([failure])
        with pytest.raises(PlatformError) as caught:
            adapter.list_products()
    elif operation == "create":
        adapter._opener = Opener([b'{"version":"2.1.0"}', failure])
        review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
        with pytest.raises(UnknownCreateOutcome) as caught:
            adapter.create_product(
                VALID_ODPS,
                domain="test-domain",
                reviewed_sha256=review.review_sha256,
                owners=[],
            )
    else:
        adapter._opener = Opener(
            [
                b'{"version":"2.1.0"}',
                DELETE_PRODUCT,
                b'{"version":"2.1.0"}',
                DELETE_PRODUCT,
                failure,
            ]
        )
        if operation == "update":
            review = adapter.review_update(DELETE_PRODUCT_ID, title="New")
            with pytest.raises(UnknownUpdateOutcome) as caught:
                adapter.update_product(
                    DELETE_PRODUCT_ID, title="New", reviewed_sha256=review.review_sha256
                )
        else:
            review = adapter.review_delete(DELETE_PRODUCT_ID)
            with pytest.raises(UnknownDeleteOutcome) as caught:
                adapter.delete_product(
                    DELETE_PRODUCT_ID,
                    reviewed_sha256=review.review_sha256,
                    confirm_permanent=True,
                )
    assert "private response" not in str(caught.value)
    assert len([r for r in adapter._opener.requests if r.method != "GET"]) <= 1


@pytest.mark.parametrize("body", [b'{"id":""}', b'{"id":"  "}', b'{"id":null}'])
def test_create_missing_identity_is_unknown_and_not_retried(
    config_file, monkeypatch, body
):
    from open_data_products import UnknownCreateOutcome

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(
        replace(load_integration_config(config_file).select(), read_only=False)
    )
    adapter._opener = Opener([b'{"version":"2.1.0"}', body])
    review = adapter.review_create(VALID_ODPS, domain="test-domain", owners=[])
    with pytest.raises(UnknownCreateOutcome, match="product ID"):
        adapter.create_product(
            VALID_ODPS,
            domain="test-domain",
            reviewed_sha256=review.review_sha256,
            owners=[],
        )
    assert [r.method for r in adapter._opener.requests] == ["GET", "POST"]


@pytest.mark.parametrize(
    "body",
    [
        b'{"data":[null]}',
        b'{"data":["invalid"]}',
        b'{"data":[],"paging":{"after":NaN}}',
    ],
)
def test_list_rejects_malformed_product_pages(config_file, monkeypatch, body):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    adapter._opener = Opener([body])
    with pytest.raises(PlatformError):
        adapter.list_products()


def test_keychain_token_is_lazy_and_redacted(config_file, monkeypatch):
    config_file.write_text(
        config_file.read_text().replace(
            "{source: env, name: TEST_INTEGRATION_TOKEN}",
            "{source: keychain, service: odps-openmetadata, account: odps-sdk}",
        )
    )
    calls = []

    class Result:
        returncode = 0
        stdout = "private-token\n"

    def fake_run(args, **kwargs):
        calls.append(args)
        return Result()

    monkeypatch.setattr(
        "open_data_products.integrations.config.subprocess.run", fake_run
    )
    profile = load_integration_config(config_file).select()
    assert calls == []
    assert profile.token() == "private-token"
    assert calls[0] == [
        "/usr/bin/security",
        "find-generic-password",
        "-s",
        "odps-openmetadata",
        "-a",
        "odps-sdk",
        "-w",
    ]
    assert "private-token" not in repr(profile)


def test_keychain_errors_are_sanitized(config_file, monkeypatch):
    config_file.write_text(
        config_file.read_text().replace(
            "{source: env, name: TEST_INTEGRATION_TOKEN}",
            "{source: keychain, service: odps-openmetadata, account: odps-sdk}",
        )
    )

    class Result:
        returncode = 1
        stderr = "private-token"

    monkeypatch.setattr(
        "open_data_products.integrations.config.subprocess.run",
        lambda *args, **kwargs: Result(),
    )
    with pytest.raises(ConfigurationError) as err:
        load_integration_config(config_file).select().token()
    assert "private-token" not in str(err.value)


def test_native_cli_can_retrieve_extensions(config_file, monkeypatch, capsys):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    opener = Opener([b'{"id":"id1","extension":{"notes":"example"}}'])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    status = main(
        [
            "integrations",
            "products",
            "get",
            "dev",
            "--config",
            str(config_file),
            "--id",
            "11111111-1111-4111-8111-111111111111",
            "--format",
            "native",
            "--include-extensions",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert status == 0
    assert result["data"]["extension"]["notes"] == "example"
    assert "fields=extension" in opener.requests[0].full_url


def test_live_roundtrip_cleans_up_after_assertion_failure(monkeypatch):
    from types import SimpleNamespace
    import yaml
    from tests import test_integrations_live as live

    monkeypatch.setenv("ODPS_INTEGRATION_WRITE_TEST", "1")
    monkeypatch.setenv("ODPS_INTEGRATION_CONFIG", "unused")
    monkeypatch.setenv("ODPS_INTEGRATION_WRITE_PROFILE", "write")
    monkeypatch.setenv("ODPS_INTEGRATION_TEST_DOMAIN", "test-domain")
    monkeypatch.setattr(
        live,
        "load_integration_config",
        lambda path: SimpleNamespace(
            select=lambda name: SimpleNamespace(read_only=False)
        ),
    )
    deleted = []

    class FakeAdapter:
        def __init__(self, profile):
            self.product_name = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def review_create(self, source, domain):
            self.product_name = yaml.safe_load(source)["product"]["details"]["en"][
                "productID"
            ]
            return SimpleNamespace(
                executable=True, review_sha256="create", to_dict=lambda: {}
            )

        def create_product(self, source, domain, reviewed_sha256):
            return SimpleNamespace(
                status="created", product_id="test-id", comparison={"domain": "matched"}
            )

        def get_product(self, product_id):
            return SimpleNamespace(data={"displayName": "Unexpected"})

        def review_delete(self, product_id):
            return SimpleNamespace(
                product_id=product_id, fqn=self.product_name, review_sha256="delete"
            )

        def delete_product(self, product_id, reviewed_sha256, confirm_permanent):
            deleted.append((product_id, reviewed_sha256, confirm_permanent))
            return SimpleNamespace(verification="not_found_by_id", to_dict=lambda: {})

    monkeypatch.setattr(live, "OpenMetadataAdapter", FakeAdapter)
    with pytest.raises(AssertionError):
        live.test_live_create_retrieve_update_and_verify()
    assert deleted == [("test-id", "delete", True)]


def test_product_search_limits_fields_and_encodes_query(config_file, monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    body = {
        "timed_out": False,
        "_shards": {"failed": 0},
        "hits": {
            "total": {"value": 2, "relation": "eq"},
            "hits": [
                {
                    "_id": "id1",
                    "_source": {
                        "id": "id1",
                        "name": "one",
                        "displayName": "One",
                        "entityType": "dataProduct",
                        "extension": {"private": "secret"},
                        "href": "http://private",
                    },
                }
            ],
        },
    }
    adapter._opener = Opener([json.dumps(body).encode()])
    page = adapter.search_products('sales + "2026"', offset=0, limit=1)
    assert page.products == [{"id": "id1", "name": "one", "displayName": "One"}]
    assert page.total == 2 and page.total_relation == "eq" and page.next_offset == 1
    params = parse_qs(urlsplit(adapter._opener.requests[0].full_url).query)
    assert params["q"] == ['sales + "2026"']
    assert params["index"] == ["data_product_search_index"]
    assert params["deleted"] == ["false"]
    assert "secret" not in repr(page)


def test_product_search_pagination_and_no_matches(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    bodies = [
        {
            "hits": {
                "total": {"value": 1, "relation": "gte"},
                "hits": [{"_id": "id1", "_source": {"id": "id1"}}],
            }
        },
        {"hits": {"total": {"value": 1, "relation": "gte"}, "hits": []}},
    ]
    adapter._opener = Opener([json.dumps(x).encode() for x in bodies])
    first = adapter.search_products("example", limit=1)
    assert first.next_offset == 1 and first.total_relation == "gte"
    assert any("lower bound" in warning for warning in first.warnings)
    last = adapter.search_products("example", limit=1, offset=1)
    assert last.products == [] and last.next_offset is None


@pytest.mark.parametrize(
    "body",
    [
        {"timed_out": True, "hits": {"total": 0, "hits": []}},
        {"_shards": {"failed": 1}, "hits": {"total": 0, "hits": []}},
        {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [{"_source": {"entityType": "table", "id": "id1"}}],
            }
        },
        {"hits": {"total": {"value": 1, "relation": "eq"}, "hits": [{"_source": {}}]}},
        {"hits": {"total": {"value": 1, "relation": "invalid"}, "hits": []}},
    ],
)
def test_product_search_rejects_incomplete_or_invalid_responses(
    config_file, monkeypatch, body
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    adapter._opener = Opener([json.dumps(body).encode()])
    with pytest.raises(PlatformError):
        adapter.search_products("example")


@pytest.mark.parametrize(
    "query,offset,limit",
    [("", 0, 20), ("x\n", 0, 20), ("x", -1, 20), ("x", 0, 101), ("x", 9999, 2)],
)
def test_product_search_rejects_invalid_parameters(config_file, query, offset, limit):
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    with pytest.raises(IntegrationError):
        adapter.search_products(query, offset=offset, limit=limit)


def test_product_search_cli(config_file, monkeypatch, capsys):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    body = b'{"hits":{"total":{"value":0,"relation":"eq"},"hits":[]}}'
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: Opener([body, b'{"version":"2.1.0"}']),
    )
    status = main(
        [
            "integrations",
            "products",
            "search",
            "dev",
            "--config",
            str(config_file),
            "--query",
            "example",
            "--limit",
            "10",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert status == 0 and payload["catalog"]["productReferences"] == []
    source = payload["catalog"]["metadata"]["x-source"]
    assert source["total"] == 0 and source["offset"] == 0 and source["limit"] == 10


@pytest.mark.parametrize("status", [401, 403])
def test_product_search_propagates_sanitized_access_errors(
    config_file, monkeypatch, status
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "private-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    failure = HTTPError(
        "https://private-host/secret",
        status,
        "private-token",
        {},
        io.BytesIO(b"private-token"),
    )
    adapter._opener = Opener([failure])
    with pytest.raises(PlatformError) as captured:
        adapter.search_products("private-query")
    assert captured.value.status == status
    assert "private-token" not in str(captured.value)
    assert "private-query" not in str(captured.value)


def test_openmetadata_listing_yields_valid_odpc_catalog(config_file, monkeypatch):
    from open_data_products.odpc import validate_catalog

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    first = {
        "id": "11111111-1111-4111-8111-111111111111",
        "name": "one",
        "displayName": "One",
        "description": "A product",
        "version": 0.2,
        "visibility": "PRIVATE",
    }
    second = {
        "id": "22222222-2222-4222-8222-222222222222",
        "name": "two",
        "version": 0.3,
    }
    adapter._opener = Opener(
        [
            b'{"version":"2.1.0"}',
            json.dumps({"data": [first], "paging": {"after": "next"}}).encode(),
            json.dumps({"data": [second], "paging": {}}).encode(),
        ]
    )
    catalog = adapter.list_products_odpc(page_size=1)
    assert validate_catalog(catalog).valid
    entries = catalog["catalog"]["productReferences"]
    assert [entry["productID"] for entry in entries] == ["one", "two"]
    assert entries[0]["productVersion"] == "0.2"
    assert "metadata revision" in entries[0]["x-productVersion-source"]
    assert entries[0]["productModel"]["standard"] == "OpenMetadata"
    assert entries[0]["productModel"]["$ref"].endswith(
        "/api/v1/dataProducts/" + first["id"]
    )
    assert entries[1]["x-description-source"].startswith("placeholder")
    assert catalog["catalog"]["metadata"]["x-source"]["operation"] == "list"
    assert all(request.method == "GET" for request in adapter._opener.requests)


def test_cli_list_outputs_odpc_catalog(config_file, monkeypatch, capsys):
    from open_data_products.odpc import validate_catalog

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    item = {"id": "11111111-1111-4111-8111-111111111111", "name": "one", "version": 0.1}
    opener = Opener([b'{"version":"2.1.0"}', json.dumps({"data": [item]}).encode()])
    monkeypatch.setattr(
        "open_data_products.integrations.openmetadata.request.build_opener",
        lambda *args: opener,
    )
    assert (
        main(
            [
                "integrations",
                "products",
                "list",
                "dev",
                "--config",
                str(config_file),
                "--json",
            ]
        )
        == 0
    )
    catalog = json.loads(capsys.readouterr().out)
    assert validate_catalog(catalog).valid
    assert catalog["catalog"]["productReferences"][0]["productID"] == "one"


def test_openmetadata_search_yields_valid_odpc_with_pagination(
    config_file, monkeypatch
):
    from open_data_products.odpc import validate_catalog

    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    ident = "11111111-1111-4111-8111-111111111111"
    hits = {
        "hits": {
            "total": {"value": 2, "relation": "eq"},
            "hits": [{"_source": {"id": ident, "name": "one", "version": 0.1}}],
        }
    }
    native = {
        "id": ident,
        "name": "one",
        "displayName": "One",
        "description": "A product",
        "version": 0.2,
    }
    adapter._opener = Opener(
        [json.dumps(hits).encode(), b'{"version":"2.1.0"}', json.dumps(native).encode()]
    )
    catalog = adapter.search_products_odpc("one", limit=1)
    assert validate_catalog(catalog).valid
    entry = catalog["catalog"]["productReferences"][0]
    assert entry["productVersion"] == "0.2"
    context = catalog["catalog"]["metadata"]["x-source"]
    assert (
        context["query"] == "one"
        and context["total"] == 2
        and context["nextOffset"] == 1
    )
    assert "index" in context["warnings"][0]
    assert all(request.method == "GET" for request in adapter._opener.requests)


@pytest.mark.parametrize("revision", [None, True, float("inf"), ""])
def test_odpc_listing_blocks_missing_or_invalid_revisions(
    config_file, monkeypatch, revision
):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    item = {
        "id": "11111111-1111-4111-8111-111111111111",
        "name": "one",
        "version": revision,
    }
    adapter._opener = Opener(
        [b'{"version":"2.1.0"}', json.dumps({"data": [item]}).encode()]
    )
    with pytest.raises(IntegrationError, match="revision"):
        adapter.list_products_odpc()


def test_odpc_listing_blocks_incomplete_pagination(config_file, monkeypatch):
    monkeypatch.setenv("TEST_INTEGRATION_TOKEN", "fake-token")
    adapter = OpenMetadataAdapter(load_integration_config(config_file).select())
    page = b'{"data":[],"paging":{"after":"next"}}'
    adapter._opener = Opener([b'{"version":"2.1.0"}', page])
    with pytest.raises(IntegrationError, match="incomplete"):
        adapter.list_products_odpc(max_pages=1)
