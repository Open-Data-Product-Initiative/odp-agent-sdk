"""Tests for optional Data Contract integration."""

from pathlib import Path

import pytest

from open_data_products.cli import main
from open_data_products.contracts import validate_contract
from open_data_products.contracts.models import (
    ContractExportResult,
    ContractToolAvailability,
    ContractValidationResult,
    Finding,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ODPS_PRODUCT = REPO_ROOT / "apps" / "pricing_402_builder" / "priced_product.yaml"


def test_validate_contract_returns_install_hint_when_dependency_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products.contracts import datacontract_cli_adapter

    monkeypatch.setattr(
        datacontract_cli_adapter,
        "detect_datacontract_cli",
        lambda: ContractToolAvailability(python_package=False),
    )

    result = validate_contract("contract.yaml")

    assert result.passed is False
    assert result.tool == "datacontract-cli"
    assert result.findings[0].code == "DATACONTRACT_CLI_NOT_INSTALLED"
    assert "open-data-products[contracts]" in result.findings[0].message


def test_validate_contract_normalizes_valid_python_api_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products.contracts import datacontract_cli_adapter

    monkeypatch.setattr(
        datacontract_cli_adapter,
        "detect_datacontract_cli",
        lambda: ContractToolAvailability(
            python_package=True,
            tool_version="0.12.3",
        ),
    )
    monkeypatch.setattr(
        datacontract_cli_adapter,
        "_validate_with_python_api",
        lambda path, version: ContractValidationResult(
            passed=True,
            tool="datacontract-cli",
            tool_version=version,
            contract_format="yaml",
        ),
    )

    result = validate_contract("valid.contract.yaml")

    assert result.passed is True
    assert result.tool_version == "0.12.3"
    assert result.contract_format == "yaml"
    assert result.findings == []


def test_validate_contract_normalizes_invalid_python_api_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products.contracts import datacontract_cli_adapter

    monkeypatch.setattr(
        datacontract_cli_adapter,
        "detect_datacontract_cli",
        lambda: ContractToolAvailability(python_package=True),
    )
    monkeypatch.setattr(
        datacontract_cli_adapter,
        "_validate_with_python_api",
        lambda path, version: ContractValidationResult(
            passed=False,
            tool="datacontract-cli",
            tool_version=version,
            contract_format="yaml",
            findings=[
                Finding(
                    code="DATACONTRACT_VALIDATION_FAILED",
                    message="model name is required",
                    severity="error",
                    path="/models/0/name",
                )
            ],
        ),
    )

    result = validate_contract("invalid.contract.yaml")

    assert result.passed is False
    assert result.findings[0].code == "DATACONTRACT_VALIDATION_FAILED"
    assert result.findings[0].path == "/models/0/name"


def test_summarize_contract_counts_models_fields_and_servers(tmp_path: Path) -> None:
    from open_data_products.contracts import summarize_contract

    contract = tmp_path / "orders.contract.yaml"
    contract.write_text(
        """
id: orders-contract
info:
  title: Orders Contract
  version: 1.0.0
servers:
  production:
    type: s3
models:
  orders:
    fields:
      order_id:
        type: string
      amount:
        type: number
""",
        encoding="utf-8",
    )

    summary = summarize_contract(str(contract))

    assert summary.contract_id == "orders-contract"
    assert summary.name == "Orders Contract"
    assert summary.model_count == 1
    assert summary.field_count == 2
    assert summary.server_count == 1


def test_extract_contract_schema_normalizes_models_and_fields(tmp_path: Path) -> None:
    from open_data_products.contracts import extract_contract_schema

    contract = tmp_path / "orders.contract.yaml"
    contract.write_text(
        """
models:
  orders:
    description: Order facts
    fields:
      order_id:
        type: string
        required: true
        description: Stable order id
      amount:
        type: number
        nullable: true
""",
        encoding="utf-8",
    )

    schema = extract_contract_schema(str(contract))

    assert schema.model_count == 1
    assert schema.field_count == 2
    assert schema.models[0].name == "orders"
    assert schema.models[0].fields[0].name == "order_id"
    assert schema.models[0].fields[0].required is True
    assert schema.models[0].fields[1].required is False


def test_extract_contract_schema_reports_empty_models(tmp_path: Path) -> None:
    from open_data_products.contracts import extract_contract_schema

    contract = tmp_path / "empty.contract.yaml"
    contract.write_text("id: empty-contract\n", encoding="utf-8")

    schema = extract_contract_schema(str(contract))

    assert schema.model_count == 0
    assert schema.findings[0].code == "CONTRACT_SCHEMA_EMPTY"


def test_export_contract_returns_install_hint_when_dependency_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products.contracts import export_contract
    from open_data_products.contracts import datacontract_cli_adapter

    monkeypatch.setattr(
        datacontract_cli_adapter,
        "detect_datacontract_cli",
        lambda: ContractToolAvailability(python_package=False),
    )

    result = export_contract("contract.yaml", "jsonschema")

    assert result.exported is False
    assert result.format == "jsonschema"
    assert result.findings[0].code == "DATACONTRACT_CLI_NOT_INSTALLED"


def test_export_contract_normalizes_python_api_json_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_data_products.contracts import export_contract
    from open_data_products.contracts import datacontract_cli_adapter

    monkeypatch.setattr(
        datacontract_cli_adapter,
        "detect_datacontract_cli",
        lambda: ContractToolAvailability(
            python_package=True,
            tool_version="0.12.3",
        ),
    )
    monkeypatch.setattr(
        datacontract_cli_adapter,
        "_export_with_python_api",
        lambda path, format, version: ContractExportResult(
            exported=True,
            format=format,
            content={"type": "object"},
            tool_version=version,
        ),
    )

    result = export_contract("contract.yaml", "jsonschema")

    assert result.exported is True
    assert result.content == {"type": "object"}
    assert result.tool_version == "0.12.3"


def test_resolve_product_contracts_finds_extension_reference(tmp_path: Path) -> None:
    from open_data_products.contracts import resolve_product_contracts

    product = tmp_path / "product.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: '4.0'
product:
  name: Contracted Product
  productID: contracted-product
  visibility: public
  status: production
  type: dataset
extensions:
  dataContract:
    href: ./contracts/orders.contract.yaml
    format: datacontract-cli
""",
        encoding="utf-8",
    )

    references = resolve_product_contracts(str(product))

    assert len(references) == 1
    assert references[0].href == "./contracts/orders.contract.yaml"
    assert references[0].format == "datacontract-cli"


def test_resolve_product_contracts_finds_native_odps_contract_ref(
    tmp_path: Path,
) -> None:
    from open_data_products.contracts import resolve_product_contracts

    product = tmp_path / "product.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.1/schema/odps.json
version: '4.1'
product:
  details:
    en:
      name: Contracted Product
      productID: contracted-product
      visibility: public
      status: production
      type: dataset
  contract:
    type: DCS
    "$ref": ./contracts/orders.contract.yaml
""",
        encoding="utf-8",
    )

    references = resolve_product_contracts(str(product))

    assert len(references) == 1
    assert references[0].href == "./contracts/orders.contract.yaml"
    assert references[0].format == "DCS"


def test_resolve_product_contracts_finds_native_odps_contract_url(
    tmp_path: Path,
) -> None:
    from open_data_products.contracts import resolve_product_contracts

    product = tmp_path / "product.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.1/schema/odps.json
version: '4.1'
product:
  details:
    en:
      name: Contracted Product
      productID: contracted-product
      visibility: public
      status: production
      type: dataset
  contract:
    type: ODCS
    contractURL: https://example.com/contracts/orders.yaml
""",
        encoding="utf-8",
    )

    references = resolve_product_contracts(str(product))

    assert len(references) == 1
    assert references[0].href == "https://example.com/contracts/orders.yaml"
    assert references[0].format == "ODCS"


def test_product_contract_report_uses_inline_odps_contract_spec(
    tmp_path: Path,
) -> None:
    from open_data_products.contracts import generate_product_contract_report

    product = tmp_path / "product.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: '4.0'
product:
  name: Orders
  productID: orders
  visibility: public
  status: production
  type: dataset
  datasets:
    orders:
      fields:
        order_id:
          type: string
  contract:
    type: DCS
    spec:
      name: Orders
      models:
        orders:
          fields:
            order_id:
              type: string
              required: true
""",
        encoding="utf-8",
    )

    report = generate_product_contract_report(str(product))

    assert report.passed is True
    assert report.references[0].inline_spec is not None
    assert report.validations[0].tool == "open-data-products"
    assert report.summaries[0].name == "Orders"
    assert report.alignments[0].passed is True


def test_generate_product_contract_report_uses_explicit_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products.contracts import generate_product_contract_report
    import open_data_products.contracts.alignment as alignment
    import open_data_products.contracts.product as product_contracts

    contract = tmp_path / "orders.contract.yaml"
    contract.write_text(
        """
id: orders-contract
models:
  orders:
    fields:
      order_id:
        type: string
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        product_contracts,
        "validate_contract",
        lambda contract: ContractValidationResult(
            passed=True,
            tool="datacontract-cli",
            contract_format="yaml",
        ),
    )
    monkeypatch.setattr(
        alignment,
        "validate_contract",
        lambda contract: ContractValidationResult(
            passed=True,
            tool="datacontract-cli",
            contract_format="yaml",
        ),
    )

    report = generate_product_contract_report(ODPS_PRODUCT, str(contract))

    assert report.passed is True
    assert report.product_valid is True
    assert report.contract_count == 1
    assert report.contract_tests_run is False
    assert report.summaries[0].contract_id == "orders-contract"


def test_product_check_contract_cli_json_success(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import open_data_products.contracts

    monkeypatch.setattr(
        open_data_products.contracts,
        "validate_contract",
        lambda contract: ContractValidationResult(
            passed=True,
            tool="datacontract-cli",
            tool_version="0.12.3",
            contract_format="yaml",
        ),
    )

    exit_code = main(
        [
            "product",
            "check-contract",
            str(ODPS_PRODUCT),
            "orders.contract.yaml",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["passed"] is True
    assert payload["product"]["valid"] is True
    assert payload["contract"]["passed"] is True


def test_product_resolve_contracts_cli_json(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    import json

    product = tmp_path / "product.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: '4.0'
product:
  name: Contracted Product
  productID: contracted-product
  visibility: public
  status: production
  type: dataset
extensions:
  dataContract:
    href: ./orders.contract.yaml
""",
        encoding="utf-8",
    )

    exit_code = main(["product", "resolve-contracts", str(product), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["references"][0]["href"] == "./orders.contract.yaml"


def test_product_contract_report_cli_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import json
    import open_data_products.contracts.alignment as alignment
    import open_data_products.contracts.product as product_contracts

    contract = tmp_path / "orders.contract.yaml"
    contract.write_text(
        """
id: orders-contract
models:
  orders:
    fields:
      order_id:
        type: string
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        product_contracts,
        "validate_contract",
        lambda contract: ContractValidationResult(
            passed=True,
            tool="datacontract-cli",
            contract_format="yaml",
        ),
    )
    monkeypatch.setattr(
        alignment,
        "validate_contract",
        lambda contract: ContractValidationResult(
            passed=True,
            tool="datacontract-cli",
            contract_format="yaml",
        ),
    )

    exit_code = main(
        [
            "product",
            "contract-report",
            str(ODPS_PRODUCT),
            str(contract),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["contract_count"] == 1
    assert payload["summaries"][0]["contract_id"] == "orders-contract"


def test_check_product_contract_alignment_passes_for_matching_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products.contracts import check_product_contract_alignment
    import open_data_products.contracts.alignment as alignment

    product = tmp_path / "product.yaml"
    contract = tmp_path / "orders.contract.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: '4.0'
product:
  name: Orders
  productID: orders
  visibility: public
  status: production
  type: dataset
  datasets:
    orders:
      fields:
        order_id:
          type: string
        amount:
          type: number
""",
        encoding="utf-8",
    )
    contract.write_text(
        """
name: Orders
models:
  orders:
    fields:
      order_id:
        type: string
        required: true
      amount:
        type: number
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        alignment,
        "validate_contract",
        lambda contract: ContractValidationResult(
            passed=True,
            tool="datacontract-cli",
            contract_format="yaml",
        ),
    )

    result = check_product_contract_alignment(str(product), str(contract))

    assert result.passed is True
    assert result.findings == []


def test_check_product_contract_alignment_finds_missing_required_field(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from open_data_products.contracts import check_product_contract_alignment
    import open_data_products.contracts.alignment as alignment

    product = tmp_path / "product.yaml"
    contract = tmp_path / "orders.contract.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: '4.0'
product:
  name: Orders
  productID: orders
  visibility: public
  status: production
  type: dataset
  datasets:
    orders:
      fields:
        order_id:
          type: string
""",
        encoding="utf-8",
    )
    contract.write_text(
        """
name: Orders
models:
  orders:
    fields:
      order_id:
        type: string
        required: true
      amount:
        type: number
        required: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        alignment,
        "validate_contract",
        lambda contract: ContractValidationResult(
            passed=True,
            tool="datacontract-cli",
            contract_format="yaml",
        ),
    )

    result = check_product_contract_alignment(str(product), str(contract))

    assert result.passed is False
    assert result.findings[0].code == "REQUIRED_FIELD_MISSING_IN_ODPS"
    assert result.findings[0].severity == "error"


def test_product_align_contract_cli_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import json
    import open_data_products.contracts.alignment as alignment

    product = tmp_path / "product.yaml"
    contract = tmp_path / "orders.contract.yaml"
    product.write_text(
        """
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: '4.0'
product:
  name: Orders
  productID: orders
  visibility: public
  status: production
  type: dataset
  datasets:
    orders:
      fields:
        order_id:
          type: string
""",
        encoding="utf-8",
    )
    contract.write_text(
        """
name: Orders
models:
  orders:
    fields:
      order_id:
        type: string
        required: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        alignment,
        "validate_contract",
        lambda contract: ContractValidationResult(
            passed=True,
            tool="datacontract-cli",
            contract_format="yaml",
        ),
    )

    exit_code = main(
        ["product", "align-contract", str(product), str(contract), "--json"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["passed"] is True
    assert payload["contract_tests_run"] is False


def test_product_contract_schema_cli_json(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    import json

    contract = tmp_path / "orders.contract.yaml"
    contract.write_text(
        """
models:
  orders:
    fields:
      order_id:
        type: string
        required: true
""",
        encoding="utf-8",
    )

    exit_code = main(["product", "contract-schema", str(contract), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["model_count"] == 1
    assert payload["field_count"] == 1
    assert payload["models"][0]["fields"][0]["required"] is True


def test_product_export_contract_cli_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import open_data_products.contracts

    monkeypatch.setattr(
        open_data_products.contracts,
        "export_contract",
        lambda contract, format: ContractExportResult(
            exported=True,
            format=format,
            content={"type": "object"},
        ),
    )

    exit_code = main(
        [
            "product",
            "export-contract",
            "orders.contract.yaml",
            "--format",
            "jsonschema",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["exported"] is True
    assert payload["content"] == {"type": "object"}


def test_product_check_contract_cli_json_failure(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import open_data_products.contracts

    monkeypatch.setattr(
        open_data_products.contracts,
        "validate_contract",
        lambda contract: ContractValidationResult(
            passed=False,
            tool="datacontract-cli",
            findings=[
                Finding(
                    code="DATACONTRACT_VALIDATION_FAILED",
                    message="invalid contract",
                    severity="error",
                )
            ],
        ),
    )

    exit_code = main(
        [
            "product",
            "check-contract",
            str(ODPS_PRODUCT),
            "orders.contract.yaml",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["passed"] is False
    assert payload["contract"]["findings"][0]["message"] == "invalid contract"
