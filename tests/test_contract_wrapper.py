"""ODCS-to-ODPS contract wrapper coverage."""

from pathlib import Path

import pytest

from open_data_products.cli import main


def test_wrap_contract_generates_valid_external_odps_draft(tmp_path: Path) -> None:
    """Wrap an ODCS 3.1 contract without duplicating its specification."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "orders contract.yaml"
    contract.write_text(
        """
apiVersion: v3.1.0
kind: DataContract
id: ORDERS-001
name: Orders Contract
version: 1.2.3
description: Confirmed orders published by fulfilment.
domain: commerce
servers:
  production:
    type: http
    url: https://api.example.test/orders
models:
  orders:
    fields:
      order_id:
        type: string
""",
        encoding="utf-8",
    )

    result = wrap_contract(str(contract))

    contract_profile = result.document["product"]["contract"]["default"]
    details = result.document["product"]["details"]["en"]
    assert result.validation.valid is True
    assert result.source_standard == "ODCS"
    assert result.source_specification_version == "3.1.0"
    assert contract_profile["id"] == "ORDERS-001"
    assert contract_profile["type"] == "ODCS"
    assert contract_profile["contractVersion"] == "3.1.0"
    assert contract_profile["contractURL"] == contract.resolve().as_uri()
    assert "spec" not in contract_profile
    assert details["status"] == "draft"
    assert details["visibility"] == "private"
    assert "product.contract.default.id" in {
        item.target for item in result.mapped_fields
    }
    assert result.provisional_defaults
    assert "business owner" in result.missing_business_information
    assert result.warnings == [
        "LOCAL_CONTRACT_REFERENCE: file URI portability is limited to systems with access to the same path"
    ]


def test_wrap_contract_maps_native_odcs_v32_product_metadata(tmp_path: Path) -> None:
    """Map the native v3.2 product and purpose fields into the ODPS draft."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "seller.yaml"
    contract.write_text(
        """
apiVersion: v3.2.0
kind: DataContract
id: seller-metrics
dataProduct: Seller Metrics
version: 2.0.0
description:
  purpose: Metrics for seller performance analysis.
schema:
  - name: seller_metrics
    physicalType: table
""",
        encoding="utf-8",
    )

    result = wrap_contract(str(contract))

    details = result.document["product"]["details"]["en"]
    assert result.validation.valid is True
    assert result.source_specification_version == "3.2.0"
    assert details["name"] == "Seller Metrics"
    assert details["description"] == "Metrics for seller performance analysis."
    assert {item.source for item in result.mapped_fields} >= {
        "/dataProduct",
        "/description/purpose",
    }


def test_wrap_contract_cli_writes_yaml_and_json_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Use the same wrapper implementation through the product CLI group."""
    contract = tmp_path / "orders.yaml"
    output = tmp_path / "products" / "orders.yaml"
    contract.write_text(
        """
apiVersion: v3.1.0
kind: DataContract
id: ORDERS-001
name: Orders
version: 1.0.0
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "product",
            "wrap-contract",
            str(contract),
            "--output",
            str(output),
            "--json",
        ]
    )

    report = capsys.readouterr().out
    assert exit_code == 0
    assert output.is_file()
    assert '"target_odps_version": "4.2"' in report


def test_wrap_contract_cli_accepts_named_input(tmp_path: Path) -> None:
    """Prefer an explicit input path for the wrapper source contract."""
    contract = tmp_path / "orders.yaml"
    output = tmp_path / "orders-product.yaml"
    contract.write_text(
        "apiVersion: v3.2.0\nkind: DataContract\nid: ORDERS\ndataProduct: Orders\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "product",
            "wrap-contract",
            "--input",
            str(contract),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert output.is_file()


def test_wrap_contract_inline_preserves_complete_contract_and_access_profile(
    tmp_path: Path,
) -> None:
    """Inline mode retains ODCS details and only maps an evidenced HTTP server."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
apiVersion: v3.1.0
kind: DataContract
id: ORDERS-001
name: Orders
version: 1.0.0
servers:
  public-api:
    type: http
    url: https://api.example.test/orders
    format: JSON
models:
  orders:
    fields:
      id:
        type: string
quality:
  type: SodaCL
teams:
  platform:
    type: technical
""",
        encoding="utf-8",
    )

    result = wrap_contract(str(contract), inline_contract=True)

    profile = result.document["product"]["contract"]["default"]
    access = result.document["product"]["dataAccess"]["default"]
    assert result.validation.valid is True
    assert profile["spec"]["models"]["orders"]["fields"]["id"]["type"] == "string"
    assert profile["spec"]["quality"]["type"] == "SodaCL"
    assert "contractURL" not in profile
    assert access == {
        "outputPortType": "API",
        "contract": {"$ref": "#/product/contract/default"},
        "accessURL": "https://api.example.test/orders",
        "format": "JSON",
    }


def test_wrap_contract_protects_output_and_honours_contract_url_override(
    tmp_path: Path,
) -> None:
    """Refuse accidental output replacement while allowing an explicit reference."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "orders.yaml"
    output = tmp_path / "orders-product.yaml"
    contract.write_text(
        "apiVersion: v3.0.0\nkind: DataContract\nid: ORDERS\nname: Orders\n",
        encoding="utf-8",
    )
    output.write_text("unchanged", encoding="utf-8")

    with pytest.raises(FileExistsError, match="overwrite"):
        wrap_contract(str(contract), str(output))

    result = wrap_contract(
        str(contract),
        str(output),
        contract_url="https://contracts.example.test/orders.yaml",
        overwrite=True,
    )

    assert result.document["product"]["contract"]["default"]["contractURL"] == (
        "https://contracts.example.test/orders.yaml"
    )
    assert "contracts.example.test" in output.read_text(encoding="utf-8")


def test_wrap_contract_keeps_ai_proposals_separate_from_deterministic_document(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Optional provider output remains proposed and cannot rewrite ODCS facts."""
    from open_data_products.contracts import wrap_contract
    import open_data_products.generation as generation

    contract = tmp_path / "orders.yaml"
    contract.write_text(
        "apiVersion: v3.1.0\nkind: DataContract\nid: ORDERS\nname: Orders\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: lambda prompt, model: (
            '{"valueProposition": "Potentially supports fulfilment planning"}'
        ),
    )

    result = wrap_contract(str(contract), use_ai=True)

    assert result.ai_enriched is True
    assert result.ai_proposals[0].field == "valueProposition"
    assert result.ai_proposals[0].review_status == "proposed"
    assert "valueProposition" not in result.document["product"]["details"]["en"]


def test_wrap_contract_applies_ai_business_description_as_proposed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Use AI to restate an ODCS purpose in business language for review."""
    from open_data_products.contracts import wrap_contract
    import open_data_products.generation as generation

    contract = tmp_path / "seller.yaml"
    contract.write_text(
        """
apiVersion: v3.2.0
kind: DataContract
id: seller-metrics
dataProduct: Seller Metrics
description:
  purpose: Views built on top of seller tables.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: lambda prompt, model: (
            '{"description": "Helps commercial teams understand seller performance."}'
        ),
    )

    result = wrap_contract(str(contract), use_ai=True)

    assert result.document["product"]["details"]["en"]["description"] == (
        "Helps commercial teams understand seller performance."
    )
    assert result.ai_proposals[0].field == "description"
    assert result.ai_proposals[0].review_status == "proposed"
    assert any(
        "AI_PROPOSED_DESCRIPTION_APPLIED" in warning for warning in result.warnings
    )


def test_wrap_contract_applies_ai_tags_as_proposed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Use AI-suggested discovery tags in the review-required ODPS draft."""
    from open_data_products.contracts import wrap_contract
    import open_data_products.generation as generation

    contract = tmp_path / "seller.yaml"
    contract.write_text(
        """
apiVersion: v3.2.0
kind: DataContract
id: seller-metrics
dataProduct: Seller Metrics
description:
  purpose: Views built on top of seller tables.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: lambda prompt, model: (
            '{"suggestedTags": ["seller-performance", "commercial-insights"]}'
        ),
    )

    result = wrap_contract(str(contract), use_ai=True)

    assert result.document["product"]["details"]["en"]["tags"] == [
        "seller-performance",
        "commercial-insights",
    ]
    assert [proposal.field for proposal in result.ai_proposals] == [
        "suggestedTags",
        "suggestedTags",
    ]
    assert all(proposal.review_status == "proposed" for proposal in result.ai_proposals)
    assert not any("AI_PROPOSED_TAGS_APPLIED" in warning for warning in result.warnings)


def test_wrap_contract_extend_applies_broader_ai_draft_details(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Extend an AI-enabled draft with wider ODPS product details."""
    from open_data_products.contracts import wrap_contract
    import open_data_products.generation as generation

    contract = tmp_path / "seller.yaml"
    contract.write_text(
        """
apiVersion: v3.2.0
kind: DataContract
id: seller-metrics
dataProduct: Seller Metrics
description:
  purpose: Views built on top of seller tables.
domain: commerce
version: 2.0.0
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generation,
        "create_generation_client",
        lambda settings: lambda prompt, model: """
{
  "description": "Helps commercial teams understand seller performance.",
  "suggestedTags": ["seller-performance"],
  "valueProposition": "Helps teams prioritize seller support.",
  "suggestedCategories": ["sales-operations"],
  "potentialUseCases": ["Prioritize seller support"],
  "productSeries": "Seller intelligence",
  "brandSlogan": "Make seller performance visible.",
  "versionNotes": "Initial business draft.",
  "issues": "https://example.test/seller-metrics/draft-issues",
  "recommendedDataProducts": ["https://example.test/products/seller-profile"]
}
""",
    )

    result = wrap_contract(str(contract), use_ai=True, extend=True)

    details = result.document["product"]["details"]["en"]
    assert result.validation.valid is True
    assert details["valueProposition"] == "Helps teams prioritize seller support."
    assert details["categories"] == ["commerce", "sales-operations"]
    assert details["useCases"] == [
        {"useCase": {"useCaseTitle": "Prioritize seller support"}}
    ]
    assert details["productSeries"] == "Seller intelligence"
    assert details["brandSlogan"] == "Make seller performance visible."
    assert details["versionNotes"] == "Initial business draft."
    assert details["issues"] == "https://example.test/seller-metrics/draft-issues"
    assert details["recommendedDataProducts"] == [
        "https://example.test/products/seller-profile"
    ]
    assert details["productVersion"] == "2.0.0"


def test_wrap_contract_cli_exposes_full_draft(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Expose extended draft filling through the product CLI."""
    contract = tmp_path / "seller.yaml"
    contract.write_text(
        """
apiVersion: v3.2.0
kind: DataContract
id: seller-metrics
dataProduct: Seller Metrics
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires use_ai"):
        from open_data_products.contracts import wrap_contract

        wrap_contract(str(contract), extend=True)

    with pytest.raises(SystemExit) as exc_info:
        main(["product", "wrap-contract", "--help"])

    assert exc_info.value.code == 0
    help_output = capsys.readouterr().out
    assert "--input" in help_output
    assert "--enrich" in help_output
    assert "--full-draft" in help_output
    assert "--ai" not in help_output
    assert "--extend" not in help_output


def test_wrap_contract_reports_ai_failure_without_losing_valid_draft(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Provider failures do not falsely mark deterministic output as enriched."""
    from open_data_products.contracts import wrap_contract
    import open_data_products.generation as generation

    contract = tmp_path / "orders.yaml"
    contract.write_text(
        "apiVersion: v3.1.0\nkind: DataContract\nid: ORDERS\nname: Orders\n",
        encoding="utf-8",
    )

    def fail_client(settings: object) -> object:
        raise RuntimeError("provider is unavailable")

    monkeypatch.setattr(generation, "create_generation_client", fail_client)

    result = wrap_contract(str(contract), use_ai=True)

    assert result.validation.valid is True
    assert result.ai_enabled is True
    assert result.ai_enriched is False
    assert result.ai_proposals == []
    assert result.errors == ["AI enrichment failed: RuntimeError"]


def test_wrap_contract_does_not_create_an_ai_client_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The deterministic default never contacts a configured provider."""
    from open_data_products.contracts import wrap_contract
    import open_data_products.generation as generation

    contract = tmp_path / "orders.yaml"
    contract.write_text(
        "apiVersion: v3.1.0\nkind: DataContract\nid: ORDERS\nname: Orders\n",
        encoding="utf-8",
    )

    def unexpected_client(settings: object) -> object:
        raise AssertionError("AI client must not be created")

    monkeypatch.setattr(generation, "create_generation_client", unexpected_client)

    result = wrap_contract(str(contract))

    assert result.validation.valid is True
    assert result.ai_enabled is False
    assert result.ai_enriched is False


def test_wrap_contract_dry_run_does_not_create_output(tmp_path: Path) -> None:
    """Dry-run validates a prospective destination without changing the filesystem."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "orders.yaml"
    output = tmp_path / "products" / "orders.yaml"
    contract.write_text(
        "apiVersion: v3.0.0\nkind: DataContract\nid: ORDERS\nname: Orders\n",
        encoding="utf-8",
    )

    result = wrap_contract(str(contract), str(output), dry_run=True)

    assert result.validation.valid is True
    assert result.output == str(output)
    assert output.exists() is False


def test_wrap_contract_omits_data_access_without_a_safe_server_url(
    tmp_path: Path,
) -> None:
    """A transport type alone is not enough evidence for an access profile."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
apiVersion: v3.1.0
kind: DataContract
id: ORDERS
name: Orders
servers:
  incomplete:
    type: http
""",
        encoding="utf-8",
    )

    result = wrap_contract(str(contract))

    assert result.validation.valid is True
    assert "dataAccess" not in result.document["product"]
    assert (
        "DATA_ACCESS_OMITTED: source servers do not establish a supported output port type"
        in result.warnings
    )


def test_wrap_contract_omits_data_access_for_wrong_transport_uri(
    tmp_path: Path,
) -> None:
    """An HTTP server must provide an HTTP(S) endpoint, not another URI type."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
apiVersion: v3.1.0
kind: DataContract
id: ORDERS
name: Orders
servers:
  wrong-scheme:
    type: http
    url: mailto:owner@example.test
""",
        encoding="utf-8",
    )

    result = wrap_contract(str(contract))

    assert result.validation.valid is True
    assert "dataAccess" not in result.document["product"]


def test_wrap_contract_rejects_credential_bearing_reference_override(
    tmp_path: Path,
) -> None:
    """An override cannot write a secret-bearing URI into an ODPS contractURL."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "orders.yaml"
    contract.write_text(
        "apiVersion: v3.1.0\nkind: DataContract\nid: ORDERS\nname: Orders\n",
        encoding="utf-8",
    )

    for query in (
        "accessToken=secret",
        "clientSecret=secret",
        "Authorization=Bearer",
        "sig=secret",
        "jwt=secret",
    ):
        with pytest.raises(ValueError, match="Credential-bearing contract URL"):
            wrap_contract(
                str(contract),
                contract_url=f"https://contracts.example.test/orders?{query}",
            )

    with pytest.raises(ValueError, match="Credential-bearing contract URL"):
        wrap_contract(
            str(contract),
            contract_url="https://@contracts.example.test/orders",
        )


def test_wrap_contract_omits_credential_bearing_server_url(tmp_path: Path) -> None:
    """A server URL with credentials cannot become an ODPS access endpoint."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
apiVersion: v3.1.0
kind: DataContract
id: ORDERS
name: Orders
servers:
  private-api:
    type: http
    url: https://user:secret@api.example.test/orders
""",
        encoding="utf-8",
    )

    result = wrap_contract(str(contract))

    assert result.validation.valid is True
    assert "dataAccess" not in result.document["product"]


def test_wrap_contract_omits_server_url_with_a_fragment(tmp_path: Path) -> None:
    """Access URLs with opaque fragments cannot be serialized into the draft."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
apiVersion: v3.1.0
kind: DataContract
id: ORDERS
name: Orders
servers:
  private-api:
    type: http
    url: https://api.example.test/orders#access_token=secret
""",
        encoding="utf-8",
    )

    result = wrap_contract(str(contract))

    assert result.validation.valid is True
    assert "dataAccess" not in result.document["product"]


def test_wrap_contract_rejects_inline_contract_containing_credential_uri(
    tmp_path: Path,
) -> None:
    """Inline mode never serializes source URL credentials into the draft."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
apiVersion: v3.1.0
kind: DataContract
id: ORDERS
name: Orders
servers:
  private-api:
    type: http
    url: https://api.example.test/orders?access_token=secret
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Cannot inline.*credential-bearing URI"):
        wrap_contract(str(contract), inline_contract=True)


def test_wrap_contract_rejects_non_odcs_mapping(tmp_path: Path) -> None:
    """Do not label an arbitrary versioned mapping as an ODCS contract."""
    from open_data_products.contracts import wrap_contract

    contract = tmp_path / "not-odcs.yaml"
    contract.write_text("apiVersion: v3.1.0\nname: Orders\n", encoding="utf-8")

    with pytest.raises(ValueError, match="kind must be DataContract"):
        wrap_contract(str(contract))
