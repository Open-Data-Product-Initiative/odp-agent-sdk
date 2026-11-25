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


def test_intelligence_additions_preserve_discovery_result_fields() -> None:
    from open_data_products.contracts.discovery import ContractDiscoveryResult

    payload = ContractDiscoveryResult(
        source_id="contracts", inventory=[], relationships=[], candidates=[]
    ).to_dict()

    assert {
        "kind",
        "source_id",
        "source_status",
        "inventory",
        "relationships",
        "candidates",
        "artifacts",
        "warnings",
        "ai_enabled",
        "ai_proposals",
    }.issubset(payload)
    assert payload["intelligence_findings"] == []
    assert payload["intelligence_summary"] == {}


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


def test_discovery_groups_real_contracts_with_a_shared_domain_and_capability(
    tmp_path: Path,
) -> None:
    from open_data_products import discover_contract_portfolio

    result = discover_contract_portfolio(directory=REAL_CORPUS, output=tmp_path / "out")
    records = {item.source_reference: item for item in result.inventory}
    source = records[
        "examples/business-definitions/top-artists-by-year.odcs.yaml"
    ].logical_id
    target = records[
        "examples/business-definitions/top-artists-by-year-view.odcs.yaml"
    ].logical_id

    assert any(
        item.kind == "shared_domain_capability"
        and {item.source_id, item.target_id} == {source, target}
        for item in result.relationships
    )
    assert any(
        set(item.supporting_contract_ids) == {source, target}
        and item.evidence_class == "inferred"
        and item.opportunity_type == "boundary_proposal"
        for item in result.candidates
    )


def test_discovery_exposes_source_linked_gaps_and_reuse_findings(
    tmp_path: Path,
) -> None:
    from open_data_products import discover_contract_portfolio

    result = discover_contract_portfolio(directory=REAL_CORPUS, output=tmp_path / "out")
    records = {item.source_reference: item for item in result.inventory}
    orders = records["examples/orders/orders.odcs.yaml"]

    assert any(
        item.kind == "missing_domain"
        and item.category == "information_gap"
        and item.source_contract_ids == [orders.logical_id]
        for item in result.intelligence_findings
    )
    assert any(
        item.kind == "exact_duplicate"
        and item.category == "reuse"
        and len(item.source_contract_ids) == 2
        for item in result.intelligence_findings
    )
    duplicate_contract_ids = {
        identifier
        for item in result.intelligence_findings
        if item.kind == "exact_duplicate"
        for identifier in item.source_contract_ids
    }
    assert all(
        not set(item.supporting_contract_ids).issubset(duplicate_contract_ids)
        for item in result.candidates
        if item.opportunity_type == "boundary_proposal"
    )
    reuse = next(
        item for item in result.intelligence_findings if item.kind == "exact_duplicate"
    )
    assert reuse.evidence
    assert "diverge" in reuse.why_it_matters.lower()
    assert reuse.suggested_action.startswith("Review")


def test_discovery_distinguishes_three_opportunity_types_and_unclassified_contracts(
    tmp_path: Path,
) -> None:
    from open_data_products import discover_contract_portfolio

    output = tmp_path / "out"
    result = discover_contract_portfolio(directory=REAL_CORPUS, output=output)
    counts = Counter(item.opportunity_type for item in result.candidates)
    candidates = json.loads((output / "product-candidates.json").read_text())

    assert counts == {
        "standalone_product_candidate": 7,
        "boundary_proposal": 2,
        "rationalisation_opportunity": 2,
    }
    assert all(
        item.evidence_class == "source_fact" and len(item.supporting_contract_ids) == 1
        for item in result.candidates
        if item.opportunity_type == "standalone_product_candidate"
    )
    assert all(
        item.evidence_class == "inferred" and len(item.supporting_contract_ids) == 2
        for item in result.candidates
        if item.opportunity_type == "rationalisation_opportunity"
    )
    assert len(candidates["unclassified_contracts"]) == 134
    assert all(
        "source_reference" in item for item in candidates["unclassified_contracts"]
    )


def test_discovery_extracts_declared_technical_interfaces_and_shared_resources(
    tmp_path: Path,
) -> None:
    from open_data_products import discover_contract_portfolio

    result = discover_contract_portfolio(directory=REAL_CORPUS, output=tmp_path / "out")
    records = {item.source_reference: item for item in result.inventory}
    weather = records["tests/fixtures/api/weather-service.odcs.yaml"]
    weather_array = records["tests/fixtures/api/weather-service-array.odcs.yaml"]

    assert weather.owner == "Weather Data Team"
    assert weather.technical_interfaces == ["api"]
    assert weather.server_count == 1
    assert any(
        item.kind == "shared_technical_resource"
        and item.evidence_class == "source_fact"
        and {item.source_id, item.target_id}
        == {weather.logical_id, weather_array.logical_id}
        for item in result.relationships
    )
    assert all(
        "production" not in item.rationale.lower()
        for item in result.relationships
        if item.kind == "shared_technical_resource"
    )


def test_discovery_writes_contract_intelligence_summary_artifact(
    tmp_path: Path,
) -> None:
    from open_data_products import discover_contract_portfolio

    output = tmp_path / "out"
    result = discover_contract_portfolio(directory=REAL_CORPUS, output=output)
    payload = json.loads((output / "contract-intelligence.json").read_text())

    assert payload["summary"] == result.intelligence_summary
    assert payload["summary"]["contracts_analyzed"] == 146
    assert payload["summary"]["reuse_findings"] == 2
    assert payload["summary"]["proposed_product_groups"] == 2
    assert payload["summary"]["product_opportunities"] == len(result.candidates)
    assert payload["interface_analysis"]["interface_type_count"] == 28
    assert payload["interface_analysis"]["contracts_with_declared_interface"] == 102
    assert payload["interface_analysis"]["contracts_with_one_interface"] == 99
    assert payload["interface_analysis"]["contracts_with_multiple_interfaces"] == 3
    assert payload["interface_analysis"]["types"][0]["interface_type"] == "local"
    assert payload["interface_analysis"]["types"][0]["contract_count"] == 18
    assert all("source_contract_ids" in item for item in payload["findings"])
    assert "document" not in json.dumps(payload)


def test_intelligence_report_renders_explorer_and_evidence_links(
    tmp_path: Path,
) -> None:
    from open_data_products import discover_contract_portfolio

    output = tmp_path / "out"
    discover_contract_portfolio(directory=REAL_CORPUS, output=output)
    report = (output / "discovery-report.html").read_text(encoding="utf-8")

    assert "Data Contract Intelligence" in report
    assert 'role="tablist"' in report
    assert 'id="tab-overview"' in report
    assert 'id="tab-priority-findings"' in report
    assert 'id="tab-explorer"' in report
    assert 'id="tab-interfaces"' in report
    assert 'id="tab-opportunities"' in report
    assert 'role="tabpanel"' in report
    assert "Contracts analyzed" in report
    assert "Priority findings" in report
    assert "Contract Intelligence Explorer" in report
    assert "Interface Analysis" in report
    assert "Product Opportunities" in report
    assert 'id="contract-search"' in report
    assert "data-relationship-id=" in report
    assert 'id="relationship-' in report
    assert 'id="finding-' in report
    assert "Why it matters" in report
    assert "Suggested action" in report
    assert "#7436EB" in report
    assert '<header class="report-header">' in report
    assert 'class="brand-mark"' in report
    assert 'class="section-heading"' in report
    assert 'class="surface-card metric"' in report
    interfaces = report.split('id="panel-interfaces"', 1)[1].split(
        'id="panel-opportunities"', 1
    )[0]
    assert "28 declared interface types" in interfaces
    assert "102 contracts declare at least one interface" in interfaces
    assert "99 contracts declare one interface" in interfaces
    assert "3 contracts declare multiple interfaces" in interfaces
    assert "44 contracts do not declare an interface" in interfaces
    assert '<table class="interface-table">' in interfaces
    assert "local" in interfaces
    assert "18 contracts" in interfaces
    assert "tests/fixtures/api/weather-service.odcs.yaml" in interfaces
    opportunities = report.split('id="panel-opportunities"', 1)[1]
    assert "Standalone product candidates" in opportunities
    assert "Boundary proposals" in opportunities
    assert "Rationalisation opportunities" in opportunities
    assert "No current opportunity signal · 134 contracts" in opportunities
    assert "Supporting contracts (2)" in opportunities
    assert "Contract 1" in opportunities
    assert "Contract 2" in opportunities
    assert (
        "examples/business-definitions/top-artists-by-year.odcs.yaml" in opportunities
    )
    assert (
        "examples/business-definitions/top-artists-by-year-view.odcs.yaml"
        in opportunities
    )
    priority = report.split('id="panel-priority-findings"', 1)[1].split(
        'id="panel-explorer"', 1
    )[0]
    assert "Top Artists by Year" in priority
    assert "examples/business-definitions/top-artists-by-year.odcs.yaml" in priority
    assert "Shared domain" in priority
    assert "media" in priority
    assert 'class="evidence-card priority-finding"' in priority
    assert 'class="finding-title"' in priority
    assert 'class="finding-contracts"' in priority
    assert 'class="finding-divider"' in priority
    assert 'class="evidence-copy"' in priority
    assert 'class="action-copy"' in priority
    assert '<a class="priority-finding"' not in priority


def test_intelligence_report_explains_when_no_product_groups_exist(
    tmp_path: Path,
) -> None:
    from open_data_products import discover_contract_portfolio

    source = REAL_CORPUS / "examples" / "orders" / "orders.odcs.yaml"
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "orders.yaml").write_text(source.read_text(encoding="utf-8"))

    output = tmp_path / "out"
    result = discover_contract_portfolio(directory=contracts, output=output)
    report = (output / "discovery-report.html").read_text(encoding="utf-8")

    assert result.candidates == []
    assert "No boundary proposals detected" in report
    assert "not a failure" in report


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
