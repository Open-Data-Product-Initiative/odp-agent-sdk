"""Offline tests for initial OpenSpec handoffs."""

from pathlib import Path

import pytest
import yaml

from open_data_products.generation import resolve_generation_settings
from open_data_products.handoff import generate_handoff, preview_handoff

FIXTURES = Path(__file__).parent / "fixtures" / "openmetadata_banking_poc"


def inputs(tmp_path):
    source = tmp_path / "brief.md"
    source.write_text("Business teams need a customer view.\n", encoding="utf-8")
    product = tmp_path / "product.yaml"
    product.write_bytes(
        (
            FIXTURES / "products" / "odps_product_customer-lifetime-value.yaml"
        ).read_bytes()
    )
    return source, product


def model_reply():
    return yaml.safe_dump(
        {
            "business_intent": [
                {
                    "text": "Provide a customer view",
                    "source": "business",
                    "quote": "Business teams need a customer view.",
                }
            ],
            "known_requirements": [],
            "open_questions": [
                {"text": "Which users need access?", "source": "unknown", "quote": ""}
            ],
        }
    )


def test_generate_default_openspec_draft_without_integrations(tmp_path, monkeypatch):
    source, product = inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_handoff(source, product, settings)
    monkeypatch.setattr(
        "open_data_products.handoff.create_generation_client",
        lambda _: lambda prompt, model: model_reply(),
    )
    root = generate_handoff(
        preview,
        tmp_path / "out",
        "customer-view",
        settings,
        reviewed_sha256=preview.digest,
    )
    assert (
        yaml.safe_load((root / ".openspec.yaml").read_text())["schema"] == "spec-driven"
    )
    assert "Provide a customer view" in (root / "proposal.md").read_text()
    assert "ODCS" in (root / "preparation.md").read_text()
    assert not (root / "design.md").exists()
    assert not (root / "tasks.md").exists()
    assert not (root / "specs").exists()
    assert not (root / "supporting" / "business-brief.txt").exists()
    assert (
        yaml.safe_load((root / "supporting" / "manifest.yaml").read_text())[
            "openspec_cli_compatibility"
        ]
        == "unverified"
    )


def test_reject_changed_input_or_invented_quote(tmp_path, monkeypatch):
    source, product = inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_handoff(source, product, settings)
    source.write_text("Changed brief", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        generate_handoff(
            preview, tmp_path, "change", settings, reviewed_sha256=preview.digest
        )
    source.write_text("Business teams need a customer view.\n", encoding="utf-8")
    monkeypatch.setattr(
        "open_data_products.handoff.create_generation_client",
        lambda _: lambda prompt, model: model_reply().replace(
            "Business teams need a customer view.", "not a source quote"
        ),
    )
    with pytest.raises(ValueError, match="unsupported"):
        generate_handoff(
            preview, tmp_path, "change", settings, reviewed_sha256=preview.digest
        )


def test_conflicting_identifiers_stop(tmp_path):
    source, product = inputs(tmp_path)
    with pytest.raises(ValueError, match="identifiers conflict"):
        preview_handoff(
            source,
            product,
            resolve_generation_settings(),
            business_product_id="other-product",
        )


def test_openmetadata_discovery_is_read_only_and_bounded(monkeypatch):
    from open_data_products.integrations import ConnectionProfile, OpenMetadataAdapter

    adapter = OpenMetadataAdapter(
        ConnectionProfile("test", "openmetadata", "https://example.org", "TOKEN")
    )
    calls = []

    def get(path):
        calls.append(path)
        if path.startswith("dataProducts/"):
            return {"id": "product-1", "name": "Customer", "assets": []}
        return {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "id": "asset-1",
                            "entityType": "table",
                            "name": "customer",
                            "sampleData": ["secret"],
                        }
                    }
                ]
            }
        }

    monkeypatch.setattr(adapter, "_json", get)
    result = adapter.discover_context(product_id="product-1", query="customer", limit=2)
    assert result["product"]["assets"] == []
    assert result["candidates"][0]["id"] == "asset-1"
    assert "sampleData" not in str(result)
    assert result["incomplete"]
    assert len(calls) <= 5 and all("sample" not in path.lower() for path in calls)
    with pytest.raises(Exception, match="limit"):
        adapter.discover_context(query="customer", limit=101)


def test_combined_context_and_jira_handoff(tmp_path, monkeypatch):
    from open_data_products.handoff import handoff_jira_request
    from open_data_products.integrations.jira import JiraCloudAdapter, JiraConnection

    source, product = inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_handoff(source, product, settings)
    monkeypatch.setattr(
        "open_data_products.handoff.create_generation_client",
        lambda _: lambda prompt, model: model_reply(),
    )
    from open_data_products.integrations import ConnectionProfile, OpenMetadataAdapter

    metadata = OpenMetadataAdapter(
        ConnectionProfile(
            "metadata", "openmetadata", "https://metadata.example.org", "TOKEN"
        )
    )

    def get_metadata(path):
        if path.startswith("search/"):
            return {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "id": "table-1",
                                "entityType": "table",
                                "name": "candidate",
                            }
                        }
                    ]
                }
            }
        if path.startswith("tables/"):
            return {
                "id": "table-1",
                "columns": [{"name": "customer_id", "dataType": "STRING"}],
            }
        if path.startswith("lineage/"):
            return {"nodes": [], "upstreamEdges": [], "downstreamEdges": []}
        raise AssertionError(path)

    monkeypatch.setattr(metadata, "_json", get_metadata)
    context = metadata.discover_context(query="customer", limit=2)
    assert context["assets"][0]["columns"][0]["name"] == "customer_id"
    root = generate_handoff(
        preview,
        tmp_path / "out",
        "customer-view",
        settings,
        reviewed_sha256=preview.digest,
        context_snapshot=context,
    )
    assert (
        yaml.safe_load((root / "supporting" / "catalog-evidence.yaml").read_text())
        == context
    )

    def request():
        return handoff_jira_request(
            root,
            project="DATA",
            issue_type_id="10",
            package_url="https://example.org/package",
            business_url="https://example.org/brief",
            product_url="https://example.org/product",
        )

    issue = request()
    adapter = JiraCloudAdapter(
        JiraConnection(
            "jira", "https://example.atlassian.net", "EMAIL", "TOKEN", read_only=False
        )
    )
    calls = []

    def fake(method, path, body=None):
        calls.append(method)
        return (
            {"values": [{"fieldId": "summary", "required": True}]}
            if method == "GET"
            else {"key": "DATA-3"}
        )

    monkeypatch.setattr(adapter, "_request", fake)
    review = adapter.review_issue(issue)
    (root / "proposal.md").write_text("Changed", encoding="utf-8")
    with pytest.raises(Exception, match="changed"):
        adapter.create_issue(request(), reviewed_sha256=review["reviewed_sha256"])
    assert "POST" not in calls
    review = adapter.review_issue(request())
    assert (
        adapter.create_issue(request(), reviewed_sha256=review["reviewed_sha256"])[
            "key"
        ]
        == "DATA-3"
    )


def test_discovery_collects_schema_and_reports_lineage_access(monkeypatch):
    from open_data_products.integrations import (
        ConnectionProfile,
        OpenMetadataAdapter,
        PlatformError,
    )

    adapter = OpenMetadataAdapter(
        ConnectionProfile(
            "metadata", "openmetadata", "https://metadata.example.org", "TOKEN"
        )
    )

    def get(path):
        if path.startswith("dataProducts/"):
            return {
                "id": "00000000-0000-0000-0000-000000000001",
                "assets": [{"id": "asset-1", "type": "table"}],
            }
        if path.startswith("tables/"):
            return {
                "id": "asset-1",
                "columns": [
                    {
                        "name": "customer_id",
                        "dataType": "STRING",
                        "description": "Identifier",
                        "sampleData": "secret",
                    }
                ],
            }
        if path.startswith("lineage/"):
            raise PlatformError("Permission denied", 403)
        if path.startswith("dataContracts/"):
            return {"id": "contract-1", "name": "contract"}
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_json", get)
    result = adapter.discover_context(
        product_id="00000000-0000-0000-0000-000000000001", limit=2
    )
    assert result["assets"][0]["columns"] == [
        {"name": "customer_id", "dataType": "STRING", "description": "Identifier"}
    ]
    assert result["contracts"][0]["validation_status"] == "not validated by discovery"
    assert any(error["status"] == 403 for error in result["errors"])
    assert "secret" not in str(result)


def test_unsupported_declared_odps_version_rejected(tmp_path):
    source, product = inputs(tmp_path)
    document = yaml.safe_load(product.read_text())
    document["version"] = "4.3"
    product.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match="4.1 or 4.2"):
        preview_handoff(source, product, resolve_generation_settings())


def test_conflicting_labeled_business_product_id_rejected(tmp_path):
    source, product = inputs(tmp_path)
    source.write_text("productID: another-product\nBusiness intent.\n")
    with pytest.raises(ValueError, match="identifiers conflict"):
        preview_handoff(source, product, resolve_generation_settings())


@pytest.mark.parametrize("provider", ["ollama", "openai"])
def test_generation_uses_selected_provider_offline(tmp_path, monkeypatch, provider):
    source, product = inputs(tmp_path)
    settings = resolve_generation_settings(provider=provider)
    preview = preview_handoff(source, product, settings)
    used = []

    def create_client(resolved):
        used.append(resolved.provider)
        return lambda prompt, model: model_reply()

    monkeypatch.setattr(
        "open_data_products.handoff.create_generation_client", create_client
    )
    root = generate_handoff(
        preview, tmp_path, "customer-view", settings, reviewed_sha256=preview.digest
    )
    assert used == [provider]
    assert (
        yaml.safe_load((root / "supporting" / "manifest.yaml").read_text())["provider"]
        == provider
    )


def test_full_and_preserved_contract_in_discovery_and_bundle(tmp_path, monkeypatch):
    import hashlib
    from open_data_products.integrations import ConnectionProfile, OpenMetadataAdapter

    product_id = "00000000-0000-0000-0000-000000000001"
    odcs = "version: '3.1'\nschema:\n  - name: customer\n"
    contract = {
        "id": "contract-1",
        "name": "native",
        "terms": {"note": "full contract"},
    }
    adapter = OpenMetadataAdapter(
        ConnectionProfile("catalog", "openmetadata", "https://example.org", "TOKEN")
    )

    def get(path):
        if path.startswith("dataProducts/"):
            return {"id": product_id, "assets": []}
        if path.startswith("dataContracts/entity?"):
            return contract
        if path.startswith("dataContracts/contract-1?"):
            return {
                "entity": {"id": product_id, "type": "dataProduct"},
                "odcsPreservedFields": {
                    "odpsSdkSource": {
                        "format": "odcs-yaml-v1",
                        "yaml": odcs,
                        "version": "3.1",
                        "sha256": hashlib.sha256(odcs.encode()).hexdigest(),
                    }
                },
            }
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_json", get)
    context = adapter.discover_context(product_id=product_id)
    native, preserved = context["contracts"]
    assert native["data"] == contract
    assert native["provenance"]["connection"] == "catalog"
    assert preserved["yaml"] == odcs
    assert "not validated by OpenMetadata" in preserved["validation_status"]
    source, product = inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_handoff(source, product, settings)
    monkeypatch.setattr(
        "open_data_products.handoff.create_generation_client",
        lambda _: lambda prompt, model: model_reply(),
    )
    root = generate_handoff(
        preview,
        tmp_path / "out",
        "customer-view",
        settings,
        reviewed_sha256=preview.digest,
        context_snapshot=context,
    )
    assert (
        yaml.safe_load((root / "supporting" / "catalog-evidence.yaml").read_text())[
            "contracts"
        ][1]["yaml"]
        == odcs
    )


def test_contract_evidence_errors_and_size_bounds(monkeypatch):
    from open_data_products.integrations import (
        ConnectionProfile,
        OpenMetadataAdapter,
        PlatformError,
    )

    adapter = OpenMetadataAdapter(
        ConnectionProfile("catalog", "openmetadata", "https://example.org", "TOKEN")
    )
    monkeypatch.setattr(adapter, "_json", lambda path: {"assets": []})
    monkeypatch.setattr(
        adapter,
        "get_contract_for_product",
        lambda product_id: {"description": "x" * (1024 * 1024)},
    )

    def denied(product_id, contract, **kwargs):
        raise PlatformError("Permission denied", 403)

    monkeypatch.setattr(adapter, "_preserved_contract_source", denied)
    result = adapter.discover_context(product_id="00000000-0000-0000-0000-000000000001")
    assert result["contracts"] == []
    assert any("1 MiB" in item["message"] for item in result["errors"])
    assert any(
        item.get("status") == 403 and item["incomplete"] for item in result["errors"]
    )


def test_package_delivery_modes_bind_content_and_explain_access(tmp_path, monkeypatch):
    from zipfile import ZipFile
    from open_data_products.handoff import handoff_jira_request
    from open_data_products.integrations.jira import JiraCloudAdapter, JiraConnection

    source, product = inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_handoff(source, product, settings)
    monkeypatch.setattr(
        "open_data_products.handoff.create_generation_client",
        lambda _: lambda prompt, model: model_reply(),
    )
    root = generate_handoff(
        preview,
        tmp_path / "out",
        "customer-view",
        settings,
        reviewed_sha256=preview.digest,
    )
    archive = tmp_path / "handoff.zip"
    with ZipFile(archive, "w") as zipped:
        for file in root.rglob("*"):
            if file.is_file():
                zipped.write(file, file.relative_to(root).as_posix())
    adapter = JiraCloudAdapter(
        JiraConnection(
            "jira", "https://example.atlassian.net", "EMAIL", "TOKEN", read_only=False
        )
    )
    monkeypatch.setattr(
        adapter,
        "_request",
        lambda method, *args: (
            {"values": [{"fieldId": "summary", "required": True}]}
            if method == "GET"
            else {"key": "DATA-10"}
        ),
    )
    common = {"project": "DATA", "issue_type_id": "10"}
    attached = handoff_jira_request(root, package_attachment=archive, **common)
    shared = handoff_jira_request(
        root, shared_filesystem="/shared/changes/customer-view", **common
    )
    url = handoff_jira_request(
        root, package_url="https://example.org/handoff", **common
    )
    review = adapter.review_issue(attached)
    assert review["attachments"][0]["filename"] == "handoff.zip"
    assert "Package content-manifest SHA-256:" in review["description"]
    assert "It is not the ZIP file hash" in review["description"]
    assert (
        "Package ZIP SHA-256: " + review["attachments"][0]["sha256"]
        in review["description"]
    )
    assert "not supplied" in review["description"]
    with_sources = handoff_jira_request(
        root,
        package_attachment=archive,
        attachments=(str(source), str(product)),
        **common,
    )
    assert "Business document: Jira attachment brief.md" in with_sources.description
    assert "ODPS draft: Jira attachment product.yaml" in with_sources.description
    assert "not supplied" not in with_sources.description
    assert "valid only if" in shared.description
    assert (
        len(
            {
                review["reviewed_sha256"],
                adapter.review_issue(shared)["reviewed_sha256"],
                adapter.review_issue(url)["reviewed_sha256"],
            }
        )
        == 3
    )
    archive.write_bytes(b"changed")
    with pytest.raises(Exception, match="changed"):
        adapter.create_issue(attached, reviewed_sha256=review["reviewed_sha256"])
    with pytest.raises(ValueError, match="ZIP"):
        handoff_jira_request(root, package_attachment=archive, **common)
    with pytest.raises(ValueError, match="exactly one"):
        handoff_jira_request(root, **common)


def test_corrupt_preserved_contract_is_reported(monkeypatch):
    from open_data_products.integrations import ConnectionProfile, OpenMetadataAdapter

    product_id = "00000000-0000-0000-0000-000000000001"
    adapter = OpenMetadataAdapter(
        ConnectionProfile("catalog", "openmetadata", "https://example.org", "TOKEN")
    )

    def get(path):
        if path.startswith("dataProducts/"):
            return {"id": product_id, "assets": []}
        if path.startswith("dataContracts/entity?"):
            return {"id": "contract-1"}
        return {
            "entity": {"id": product_id, "type": "dataProduct"},
            "odcsPreservedFields": {
                "odpsSdkSource": {
                    "format": "odcs-yaml-v1",
                    "yaml": "version: '3.1'\n",
                    "version": "3.1",
                    "sha256": "wrong",
                }
            },
        }

    monkeypatch.setattr(adapter, "_json", get)
    result = adapter.discover_context(product_id=product_id)
    assert len(result["contracts"]) == 1
    assert any(
        item["resource"] == "preserved ODCS source" and "integrity" in item["message"]
        for item in result["errors"]
    )


def test_oversized_preserved_odcs_is_reported_before_parsing(monkeypatch):
    from open_data_products.integrations import ConnectionProfile, OpenMetadataAdapter

    product_id = "00000000-0000-0000-0000-000000000001"
    adapter = OpenMetadataAdapter(
        ConnectionProfile("catalog", "openmetadata", "https://example.org", "TOKEN")
    )

    def get(path):
        if path.startswith("dataProducts/"):
            return {"id": product_id, "assets": []}
        if path.startswith("dataContracts/entity?"):
            return {"id": "contract-1"}
        return {
            "entity": {"id": product_id, "type": "dataProduct"},
            "odcsPreservedFields": {
                "odpsSdkSource": {
                    "format": "odcs-yaml-v1",
                    "yaml": "x" * (1024 * 1024 + 1),
                }
            },
        }

    monkeypatch.setattr(adapter, "_json", get)
    result = adapter.discover_context(product_id=product_id)
    assert len(result["contracts"]) == 1
    assert any(
        item["resource"] == "preserved ODCS source" and "size limit" in item["message"]
        for item in result["errors"]
    )


def test_discovery_reads_v21_product_assets_and_plural_domains(monkeypatch):
    from urllib.parse import unquote
    from open_data_products.integrations import (
        ConnectionProfile,
        OpenMetadataAdapter,
        PlatformError,
    )

    adapter = OpenMetadataAdapter(
        ConnectionProfile("catalog", "openmetadata", "https://example.org", "TOKEN")
    )
    paths = []

    def get(path):
        paths.append(unquote(path))
        if path.startswith("dataProducts/") and "/assets?" in path:
            return {
                "data": [{"id": "table-id", "type": "table", "name": "accounts"}],
                "paging": {"total": 1},
            }
        if path.startswith("dataProducts/"):
            return {"id": "product-id", "name": "product"}
        if path.startswith("tables/"):
            assert "owners,domains,tags" in unquote(path)
            return {
                "id": "table-id",
                "domains": [{"name": "Banking"}],
                "columns": [{"name": "id", "dataType": "VARCHAR"}],
            }
        if path.startswith("lineage/"):
            return {"nodes": [], "upstreamEdges": [], "downstreamEdges": []}
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_json", get)

    def unavailable(*args, **kwargs):
        raise PlatformError("Not found", 404)

    monkeypatch.setattr(adapter, "get_contract_for_product", unavailable)
    monkeypatch.setattr(adapter, "get_preserved_contract_source", unavailable)
    result = adapter.discover_context(product_id="product-id", limit=5)
    assert result["product"]["assets"][0]["id"] == "table-id"
    assert result["assets"][0]["domains"][0]["name"] == "Banking"
    assert result["assets"][0]["columns"][0]["name"] == "id"
    assert any("/assets?" in p for p in paths)


def test_fenced_yaml_provider_response_is_accepted(tmp_path, monkeypatch):
    source, product = inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_handoff(source, product, settings)
    monkeypatch.setattr(
        "open_data_products.handoff.create_generation_client",
        lambda _: lambda prompt, model: "```yaml\n" + model_reply() + "```\n",
    )
    root = generate_handoff(
        preview, tmp_path, "fenced-response", settings, reviewed_sha256=preview.digest
    )
    assert (root / "proposal.md").is_file()


def test_discovery_keeps_product_search_hits_as_candidates(monkeypatch):
    from open_data_products.integrations import ConnectionProfile, OpenMetadataAdapter

    adapter = OpenMetadataAdapter(
        ConnectionProfile("test", "openmetadata", "https://example.org", "TOKEN")
    )
    calls = []

    def get(path):
        calls.append(path)
        return {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "id": "product-1",
                            "entityType": "dataProduct",
                            "name": "Customer",
                        }
                    }
                ]
            }
        }

    monkeypatch.setattr(adapter, "_json", get)
    result = adapter.discover_context(query='"Customer"', limit=4)
    assert result["candidates"][0]["id"] == "product-1"
    assert not result["errors"]
    assert any("select a product" in note for note in result["notes"])
    assert len(calls) == 1


def test_preparation_package_withholds_preserved_contract_samples(
    tmp_path, monkeypatch
):
    source, product = inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_handoff(source, product, settings)
    monkeypatch.setattr(
        "open_data_products.handoff.create_generation_client",
        lambda _: lambda prompt, model: model_reply(),
    )
    context = {
        "contracts": [
            {
                "origin": "SDK-preserved ODCS source",
                "yaml": "schema:\n- sampleData:\n  - private-value\n",
                "sha256": "original-hash",
            }
        ]
    }
    root = generate_handoff(
        preview,
        tmp_path / "out",
        "customer-view",
        settings,
        reviewed_sha256=preview.digest,
        context_snapshot=context,
    )
    evidence = (root / "supporting/catalog-evidence.yaml").read_text()
    assert "private-value" not in evidence
    assert "withheld" in evidence
    assert "original-hash" in evidence


def test_missing_contract_lookup_is_reported_once_without_claiming_absence(monkeypatch):
    from open_data_products.integrations import (
        ConnectionProfile,
        OpenMetadataAdapter,
        PlatformError,
    )

    product_id = "00000000-0000-0000-0000-000000000001"
    adapter = OpenMetadataAdapter(
        ConnectionProfile("catalog", "openmetadata", "https://example.org", "TOKEN")
    )
    calls = []

    def get(path):
        calls.append(path)
        if path.startswith("dataProducts/"):
            return {"id": product_id, "assets": []}
        if path.startswith("dataContracts/entity?"):
            raise PlatformError("Platform request returned HTTP 404", 404)
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_json", get)
    result = adapter.discover_context(product_id=product_id)
    assert len([p for p in calls if p.startswith("dataContracts/entity?")]) == 1
    product_error = next(
        e for e in result["errors"] if e["resource"] == "product contract"
    )
    source_error = next(
        e for e in result["errors"] if e["resource"] == "preserved ODCS source"
    )
    assert product_error["status"] == 404
    assert "cannot be distinguished" in product_error["message"]
    assert source_error["status"] is None and "not checked" in source_error["message"]


def test_preparation_package_includes_metadata_reference(tmp_path, monkeypatch):
    source, product = inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_handoff(source, product, settings)
    monkeypatch.setattr(
        "open_data_products.handoff.create_generation_client",
        lambda _: lambda prompt, model: model_reply(),
    )
    context = {
        "discovery_target": {"platform": "datahub", "connection": "catalog"},
        "product": {"id": "product-1", "name": "customer"},
        "assets": [{"id": "asset-1", "fullyQualifiedName": "warehouse.customer"}],
        "incomplete": True,
        "errors": [],
    }
    root = generate_handoff(
        preview,
        tmp_path / "out",
        "customer-view",
        settings,
        reviewed_sha256=preview.digest,
        context_snapshot=context,
    )
    refs = yaml.safe_load((root / "supporting/metadata-discovery.yaml").read_text())
    assert refs["platform"] == "datahub" and refs["product"]["id"] == "product-1"
    assert refs["platform_url"] is None
    assert "not available" in refs["platform_url_status"]
    assert refs["assets"][0]["fullyQualifiedName"] == "warehouse.customer"
    assert "metadata-discovery.yaml" in (root / "preparation.md").read_text()
