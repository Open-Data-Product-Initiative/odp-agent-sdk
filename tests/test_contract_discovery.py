"""Tests for deterministic ODCS contract portfolio discovery."""

import json
from pathlib import Path

ODCS_ORDERS = """\
apiVersion: v3.2.0
kind: DataContract
id: orders
name: Orders
domain: commerce
owner: commerce-team
models:
  orders:
    fields:
      order_id:
        type: string
      amount:
        type: number
"""


def _write_contract(path: Path, content: str = ODCS_ORDERS) -> None:
    path.write_text(content, encoding="utf-8")


def test_discovery_result_serializes_metadata_not_document_bodies() -> None:
    from open_data_products.contracts.discovery import ContractDiscoveryResult

    result = ContractDiscoveryResult(
        source_id="contracts", inventory=[], relationships=[], candidates=[]
    )

    payload = result.to_dict()

    assert payload["kind"] == "ContractDiscovery"
    assert payload["inventory"] == []
    assert "document" not in json.dumps(payload)


def test_discovery_api_is_explicitly_exported() -> None:
    from open_data_products import discover_contract_portfolio

    assert callable(discover_contract_portfolio)


def test_discovery_keeps_valid_invalid_and_unsupported_records(tmp_path: Path) -> None:
    from open_data_products import discover_contract_portfolio

    _write_contract(tmp_path / "orders.yaml")
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "notes.yaml").write_text("title: notes\n", encoding="utf-8")

    result = discover_contract_portfolio(directory=tmp_path, output=tmp_path / "out")

    assert {item.status for item in result.inventory} == {
        "loaded",
        "invalid",
        "unsupported",
    }


def test_discovery_uses_relative_source_references(tmp_path: Path) -> None:
    from open_data_products import discover_contract_portfolio

    contracts = tmp_path / "contracts"
    (contracts / "nested").mkdir(parents=True)
    _write_contract(contracts / "nested" / "orders.yaml")

    result = discover_contract_portfolio(directory=contracts, output=tmp_path / "out")

    assert result.inventory[0].source_reference == "nested/orders.yaml"
    assert str(contracts) not in json.dumps(result.to_dict())


def test_discovery_distinguishes_exact_duplicates_from_schema_overlap(
    tmp_path: Path,
) -> None:
    from open_data_products import discover_contract_portfolio

    _write_contract(tmp_path / "orders-a.yaml")
    _write_contract(tmp_path / "orders-b.yaml")
    _write_contract(
        tmp_path / "orders-copy.yaml",
        ODCS_ORDERS.replace("id: orders", "id: orders-copy").replace(
            "name: Orders", "name: Order copy"
        ),
    )

    result = discover_contract_portfolio(directory=tmp_path, output=tmp_path / "out")

    assert any(item.kind == "exact_duplicate" for item in result.relationships)
    assert any(item.kind == "schema_overlap" for item in result.relationships)
    assert all(item.status == "proposed" for item in result.candidates)
