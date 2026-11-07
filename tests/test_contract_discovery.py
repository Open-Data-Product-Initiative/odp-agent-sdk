"""Tests for deterministic ODCS contract portfolio discovery."""

import json
from collections import Counter
from pathlib import Path

REAL_CORPUS = (
    Path(__file__).parent
    / "fixtures"
    / "external_contract_sources"
    / "datacontract-cli"
)


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


def test_discovery_runs_against_pinned_real_odcs_corpus(tmp_path: Path) -> None:
    from open_data_products import discover_contract_portfolio

    provenance = json.loads((REAL_CORPUS / "SOURCE.json").read_text(encoding="utf-8"))
    result = discover_contract_portfolio(directory=REAL_CORPUS, output=tmp_path / "out")

    assert provenance["commit"] == "09e779dfeaec63ee60edc102e7a3d6970e34e16b"
    assert provenance["license"] == "MIT"
    assert len(result.inventory) == 146
    assert {item.status for item in result.inventory} == {"loaded"}
    assert Counter(item.odcs_version for item in result.inventory) == {
        "v3.0.0": 4,
        "v3.0.1": 2,
        "v3.0.2": 28,
        "v3.1.0": 52,
        "v3.2.0": 60,
    }
    assert any(item.kind == "exact_duplicate" for item in result.relationships)


def test_discovery_uses_relative_source_references(tmp_path: Path) -> None:
    from open_data_products import discover_contract_portfolio

    contracts = tmp_path / "contracts"
    (contracts / "nested").mkdir(parents=True)
    source = REAL_CORPUS / "examples" / "orders" / "orders.odcs.yaml"
    (contracts / "nested" / "orders.yaml").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )

    result = discover_contract_portfolio(directory=contracts, output=tmp_path / "out")

    assert result.inventory[0].source_reference == "nested/orders.yaml"
    assert str(contracts) not in json.dumps(result.to_dict())


def test_discovery_detects_duplicate_real_contract_copies(tmp_path: Path) -> None:
    from open_data_products import discover_contract_portfolio

    source = REAL_CORPUS / "examples" / "orders" / "orders.odcs.yaml"
    (tmp_path / "orders-a.yaml").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "orders-b.yaml").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )

    result = discover_contract_portfolio(directory=tmp_path, output=tmp_path / "out")

    assert any(item.kind == "exact_duplicate" for item in result.relationships)
    assert all(item.status == "proposed" for item in result.candidates)


def test_ai_discovery_proposals_are_traceable_and_review_only(tmp_path: Path) -> None:
    from open_data_products import discover_contract_portfolio

    source = REAL_CORPUS / "examples" / "orders" / "orders.odcs.yaml"
    (tmp_path / "orders-a.yaml").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "orders-b.yaml").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )

    def client(prompt: str, model: str) -> str:
        request = json.loads(prompt)
        inventory = request["inventory"]
        assert "document" not in prompt
        assert request["allowedContractIds"] == [
            inventory[0]["logical_id"],
            inventory[1]["logical_id"],
        ]
        assert request["technicalRelationships"]
        return "```json\n{}\n```".format(
            json.dumps(
                {
                    "suggestions": [
                        {
                            "contractIds": [
                                inventory[0]["logical_id"],
                                inventory[1]["logical_id"],
                            ],
                            "rationale": "Potential shared order capability.",
                        }
                    ]
                }
            )
        )

    result = discover_contract_portfolio(
        directory=tmp_path,
        output=tmp_path / "out",
        use_ai=True,
        client=client,
        model="test-model",
    )

    assert result.ai_enabled is True
    assert result.ai_proposals[0].status == "proposed"
    assert result.ai_proposals[0].supporting_contract_ids == [
        result.inventory[0].logical_id,
        result.inventory[1].logical_id,
    ]


def test_ai_discovery_rejects_unknown_contract_references(tmp_path: Path) -> None:
    from open_data_products import discover_contract_portfolio

    source = REAL_CORPUS / "examples" / "orders" / "orders.odcs.yaml"
    (tmp_path / "orders-a.yaml").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "orders-b.yaml").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )

    result = discover_contract_portfolio(
        directory=tmp_path,
        output=tmp_path / "out",
        use_ai=True,
        client=lambda prompt, model: (
            '{"suggestions":[{"contractIds":["unknown"],"rationale":"Nope"}]}'
        ),
    )

    assert result.ai_proposals == []
    assert "unknown contract" in result.warnings[0].lower()
