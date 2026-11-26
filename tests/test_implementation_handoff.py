"""Evidence-bound implementation handoff tests."""

import json
from pathlib import Path

import pytest
import yaml

from open_data_products import (
    preview_implementation_handoff,
    generate_implementation_handoff,
)
from open_data_products.generation import resolve_generation_settings
from open_data_products.handoff import handoff_jira_request
from open_data_products.integrations.jira import JiraCloudAdapter, JiraConnection

FIXTURES = Path(__file__).parent / "fixtures" / "openmetadata_banking_poc"


def test_source_inventory_keeps_uncovered_operational_requirements(
    tmp_path, monkeypatch
):
    brief, product, context = setup_inputs(tmp_path)
    brief.write_text(
        "Customers need holdings. Draft completeness target is 98 percent.\n\n## Service expectations\n- Deliver daily by 06:00 Gulf Standard Time, with intraday updates when events arrive.\n- Recover failed loads within the agreed window when source data is available.\n\n## Quality expectations\n- Reconcile values within an agreed tolerance before publication.\n- Enforce uniqueness for the approved key.\n"
    )
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, model: reply(),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "review-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    trace = yaml.safe_load(
        (root / "supporting/requirements-traceability.yaml").read_text()
    )
    for phrase in (
        "06:00 Gulf Standard Time",
        "intraday updates",
        "Recover failed loads",
        "agreed tolerance",
        "uniqueness",
    ):
        req = next(x for x in trace["requirements"] if phrase in x["source"]["text"])
        assert req["status"] == "unresolved"
        assert req["id"] in trace["unaddressed_requirement_ids"]
        assert req["id"] in (root / "tasks.md").read_text()
    assert "not verified" in trace["requirements"][0]["semantic_coverage"]


def test_vague_scenario_becomes_explicit_open_acceptance_decision(
    tmp_path, monkeypatch
):
    brief, product, context = setup_inputs(tmp_path)
    brief.write_text(
        brief.read_text() + "\n\n## Important attributes and measures\n- state\n"
    )
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["known_requirements"][0]["quote"] = "## Important attributes and measures"
    model["known_requirements"][0][
        "then"
    ] = "the system automatically approves an unspecified result"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "review-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    spec = (root / "specs/data-product-draft/spec.md").read_text()
    assert "missing acceptance criteria and decisions are recorded" in spec
    assert "automatically approves" not in spec
    decisions = yaml.safe_load((root / "supporting/open-decisions.yaml").read_text())
    assert any(
        d["priority"] == "blocks acceptance"
        and d["source_evidence"]["quote"].startswith("##")
        for d in decisions["decisions"]
    )


def test_source_scenario_uses_only_explicit_action_and_trigger():
    from open_data_products._handoff_implementation import _source_scenario

    explicit = {
        "source": "business",
        "quote": "- Start a quality review when mandatory identifiers fail validation.",
    }
    assert _source_scenario(explicit) == (
        "mandatory identifiers fail validation",
        "Start a quality review",
    )
    ambiguous = {
        "source": "business",
        "quote": "- Consumers can understand when the product was refreshed.",
    }
    assert _source_scenario(ambiguous) is None
    assert _source_scenario({"source": "catalog", "quote": explicit["quote"]}) is None


def test_explicit_source_failure_creates_grounded_scenario(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    quote = "- Start a quality review when mandatory identifiers fail validation."
    brief.write_text(brief.read_text() + "\n\n## Operational response\n" + quote + "\n")
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["known_requirements"][0]["quote"] = quote
    model["known_requirements"][0]["then"] = "automatically open an incident"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "review-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    spec = (root / "specs/data-product-draft/spec.md").read_text()
    assert "**WHEN** mandatory identifiers fail validation" in spec
    assert "**THEN** Start a quality review" in spec
    assert "automatically open an incident" not in spec


def test_model_cannot_add_unsupported_failure_handling_to_scenario(
    tmp_path, monkeypatch
):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["known_requirements"][0]["quote"] = "Draft completeness target is 98 percent."
    model["known_requirements"][0][
        "then"
    ] = "publication is blocked and an incident is automatically opened"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "review-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    spec = (root / "specs/data-product-draft/spec.md").read_text()
    assert "publication is blocked" not in spec
    assert "Draft completeness target is 98 percent." in spec
    evidence = yaml.safe_load((root / "supporting/evidence.yaml").read_text())
    assert (
        "publication is blocked"
        in evidence["model_proposals"]["known_requirements"][0]["then"]
    )


def test_suggested_roles_require_source_evidence():
    from open_data_products._handoff_implementation import _decisions_report

    model = {
        "open_questions": ["Which source is authoritative?"],
        "known_requirements": [],
    }
    mapping = {"fields": []}
    no_roles = _decisions_report(model, {"requirements": []}, mapping)
    assert no_roles["decisions"][0]["suggested_role"] is None
    trace = {
        "requirements": [
            {
                "id": "REQ-001",
                "status": "unresolved",
                "source": {
                    "section": "Ownership context",
                    "text": "Product owner: Example team",
                },
            }
        ]
    }
    with_role = _decisions_report(model, trace, mapping)
    role = with_role["decisions"][0]["suggested_role"]
    assert role["role"] == "product owner" and role["source_requirement"] == "REQ-001"
    assert "Example team" not in str(role)


def test_preserved_contract_constraints_are_reported_without_copying(
    tmp_path, monkeypatch
):
    import hashlib

    brief, product, context = setup_inputs(tmp_path)
    source = "apiVersion: v3.1.0\nkind: DataContract\nschema:\n- name: source\n  properties:\n  - name: holding_id\n    logicalType: string\n    required: true\n    unique: true\n"
    context["contracts"] = [
        {
            "origin": "SDK-preserved ODCS source",
            "yaml": source,
            "sha256": hashlib.sha256(source.encode()).hexdigest(),
            "validation_status": "integrity checked only",
            "provenance": {"contract_id": "contract-1"},
        }
    ]
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, model: reply(),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "review-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    report = yaml.safe_load((root / "supporting/contract-constraints.yaml").read_text())
    assert {x["constraint"] for x in report["constraints"]} == {"required", "unique"}
    assert all(
        not x["draft_constraint_present"] and "unresolved" in x["applicability"]
        for x in report["constraints"]
    )
    contract = yaml.safe_load((root / "supporting/odcs-draft.yaml").read_text())
    assert "required" not in contract["schema"][0]["properties"][0]
    field_report = yaml.safe_load((root / "supporting/field-mapping.yaml").read_text())[
        "fields"
    ][0]["contract_reporting"]
    assert (
        field_report["field_present_in_draft"]
        and field_report["candidate_source_present"]
    )
    assert field_report["semantic_match_verification"] == "not_verified"
    assert field_report["owner_approval"] == "not_confirmed"
    status = yaml.safe_load((root / "supporting/validation-status.yaml").read_text())
    assert status["odps_to_odcs_alignment"]["status"] == "not_assessed"
    assert status["odcs_structure"]["status"] == "not_run"


@pytest.mark.parametrize(
    "quote",
    [
        "Availability target is at least 99.5 percent.",
        "Availability target was 99.5 percent over 30 days.",
        "Availability target is 105 percent.",
        "Availability is 99.5 percent today.",
        "No daily publication is planned.",
        "Daily publication occurs if a source is available.",
        "Incident acknowledgement is within 60 minutes.",
    ],
)
def test_service_dimension_does_not_invent_terms(quote):
    from open_data_products._handoff_implementation import _service_dimension

    assert _service_dimension(quote) is None


@pytest.mark.parametrize("version", ["4.1", "4.2"])
def test_service_expectations_form_a_source_linked_draft_sla(
    tmp_path, monkeypatch, version
):
    brief, product, context = setup_inputs(tmp_path)
    brief.write_text(
        brief.read_text()
        + "\n\n## Service expectations\n\n- Availability: Draft target of 99.5 percent during business hours.\n- Delivery timing: Draft daily publication by 06:00 Gulf Standard Time.\n- Incident acknowledgement: Draft acknowledgement within 60 minutes.\n"
    )
    if version == "4.2":
        product.write_bytes(
            (Path(__file__).parent / "fixtures/odps_v42_profiles.yaml").read_bytes()
        )
        doc = yaml.safe_load(product.read_text())
        doc["product"].pop("SLA", None)
        product.write_text(yaml.safe_dump(doc))
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["odps_enrichment"].append(
        {
            "field": "SLA",
            "text": "Draft service expectations",
            "source": "business",
            "quote": "## Service expectations",
        }
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "service-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    product = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    profile = product["product"]["SLA"]["declarative"]["default"]
    assert [
        (d["dimension"], d["objective"], d["unit"]) for d in profile["dimensions"]
    ] == [("uptime", "99.5", "percent"), ("updateFrequency", 1, "days")]
    assert "acknowledgement within 60 minutes" in profile["description"]["en"]
    assert all(d["dimension"] != "timeToNotify" for d in profile["dimensions"])
    evidence = yaml.safe_load((root / "supporting/evidence.yaml").read_text())
    assert (
        len(
            [
                x
                for x in evidence["odps_enrichment_evidence"]
                if x["field"] == "SLA.dimensions"
            ]
        )
        == 2
    )


@pytest.mark.parametrize(
    "quote",
    [
        "Completeness: current value is 98 percent.",
        "Completeness target is 98.5 percent.",
        "Completeness target is at least 98 percent.",
        "Completeness target is >= 98 percent.",
        "Completeness target is 98 percent over 30 days.",
        "Completeness and accuracy target is 98 percent.",
        "Completeness target is -98 percent.",
        "Completeness target is 101 percent.",
        "Completeness target is 98 records.",
    ],
)
def test_quality_dimension_rejects_ambiguous_and_unsupported_targets(quote):
    from open_data_products._handoff_implementation import _quality_dimension

    assert _quality_dimension(quote) is None


def test_conflicting_quality_targets_are_left_open(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    brief.write_text(
        "Customers need holdings.\nCompleteness target is 98 percent.\nCompleteness target is 95 percent.\n"
    )
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["odps_enrichment"] = [
        {"field": "dataQuality", "text": quote, "source": "business", "quote": quote}
        for quote in (
            "Completeness target is 98 percent.",
            "Completeness target is 95 percent.",
        )
    ]
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "quality-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    product = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    profile = product["product"]["dataQuality"]["declarative"]["default"]
    assert not profile.get("dimensions")
    assert (
        "98 percent" in profile["description"]
        and "95 percent" in profile["description"]
    )
    assert (
        "Conflicting source targets" in (root / "supporting/manifest.yaml").read_text()
    )


def test_quality_section_target_is_found_when_model_cites_heading(
    tmp_path, monkeypatch
):
    brief, product, context = setup_inputs(tmp_path)
    brief.write_text(
        "Customers need holdings.\n\n## Data quality expectations\n\n- Completeness: Draft target of 98 percent for mandatory fields.\n"
    )
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["odps_enrichment"] = [
        {
            "field": "dataQuality",
            "text": "Draft quality needs review",
            "source": "business",
            "quote": "## Data quality expectations",
        }
    ]
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "quality-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    enriched = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    dimension = enriched["product"]["dataQuality"]["declarative"]["default"][
        "dimensions"
    ][0]
    assert dimension["dimension"] == "completeness" and dimension["objective"] == 98
    evidence = yaml.safe_load((root / "supporting/evidence.yaml").read_text())
    assert any(
        x["field"] == "dataQuality.dimensions" and "98 percent" in x["quote"]
        for x in evidence["odps_enrichment_evidence"]
    )


@pytest.mark.parametrize("version", ["4.1", "4.2"])
def test_existing_quality_profiles_are_preserved(tmp_path, monkeypatch, version):
    brief, product, context = setup_inputs(tmp_path)
    if version == "4.2":
        product.write_bytes(
            (Path(__file__).parent / "fixtures/odps_v42_profiles.yaml").read_bytes()
        )
    document = yaml.safe_load(product.read_text())
    existing = {
        "declarative": {"premium": {"description": "Existing reviewed quality profile"}}
    }
    document["product"]["dataQuality"] = existing
    product.write_text(yaml.safe_dump(document))
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, model: reply(),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "quality-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    enriched = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    assert enriched["product"]["dataQuality"] == existing
    assert (
        "Existing dataQuality was preserved"
        in (root / "supporting/manifest.yaml").read_text()
    )


def test_existing_sla_is_preserved(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    brief.write_text(
        brief.read_text()
        + "\n\n## Service expectations\n- Availability: target 99 percent.\n"
    )
    document = yaml.safe_load(product.read_text())
    original = {"declarative": {"premium": {"description": {"en": "Existing profile"}}}}
    document["product"]["SLA"] = original
    product.write_text(yaml.safe_dump(document))
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["odps_enrichment"].append(
        {
            "field": "SLA",
            "text": "Draft service expectations",
            "source": "business",
            "quote": "## Service expectations",
        }
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "service-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    result = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    assert result["product"]["SLA"] == original
    assert (
        "Existing SLA was preserved" in (root / "supporting/manifest.yaml").read_text()
    )


def test_conflicting_service_targets_are_not_selected(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    brief.write_text(
        brief.read_text()
        + "\n\n## Service expectations\n- Availability: target 99 percent.\n- Availability: target 98 percent.\n"
    )
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: reply(),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "service-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    product = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    profile = product["product"]["SLA"]["declarative"]["default"]
    assert not profile.get("dimensions")
    assert (
        "99 percent" in profile["description"]["en"]
        and "98 percent" in profile["description"]["en"]
    )
    assert (
        "Conflicting service targets" in (root / "supporting/manifest.yaml").read_text()
    )


def test_business_led_mapping_across_assets_and_unresolved_fields(tmp_path):
    from open_data_products._handoff_implementation import _schema_drafts

    brief, product, context = setup_inputs(tmp_path)
    context["assets"].append(
        {
            "id": "asset-2",
            "name": "transactions",
            "fullyQualifiedName": "synthetic.bank.transactions",
            "type": "table",
            "columns": [
                {"name": "amount", "dataType": "DECIMAL"},
                {"name": "customer_id", "dataType": "VARCHAR"},
            ],
        }
    )
    preview = preview_implementation_handoff(
        brief,
        product,
        resolve_generation_settings(),
        context_snapshot=context,
        asset_id="asset-1",
    )

    def attribute(name, kind, refs):
        return {
            "name": name,
            "classification": "implied",
            "business_quote": "B1",
            "reason": "Review proposed business output",
            "mapping_kind": kind,
            "source_columns": refs,
            "transformation": None,
            "questions": [],
        }

    attributes = [
        attribute("holding_id", "direct", ["C1"]),
        attribute("customer_key", "multiple", ["C2", "C4"]),
        attribute("total_amount", "derived", ["C3"]),
        attribute("eligibility_status", "unresolved", []),
    ]
    mapping, output, contract, _ = _schema_drafts(attributes, preview, "draft")
    assert [x["mapping_status"] for x in mapping["fields"]] == [
        "candidate_direct",
        "candidate_multiple",
        "candidate_derived",
        "unresolved",
    ]
    assert {x["asset_id"] for x in mapping["fields"][1]["catalog_observations"]} == {
        "asset-1",
        "asset-2",
    }
    assert mapping["fields"][2]["model_proposal"]["transformation"] is None
    assert mapping["fields"][1]["model_proposal"]["type_status"] == "unresolved"
    assert mapping["fields"][1]["decisions_required"]
    assert [x["name"] for x in output["fields"]] == [x["name"] for x in attributes]
    properties = contract["schema"][0]["properties"]
    assert [x["name"] for x in properties] == [x["name"] for x in attributes]
    assert properties[0]["logicalType"] == "string"
    assert "logicalType" not in properties[1]
    assert "logicalType" not in properties[2]
    assert "logicalType" not in properties[3]
    assert "mapping: unresolved; type: unresolved" in properties[3]["description"]
    assert mapping["fields"][3]["omitted_from_odcs_reason"] is None
    assert all(x["name"] != "amount" for x in output["fields"])
    with pytest.raises(ValueError, match="unavailable catalog column"):
        _schema_drafts([attribute("invented", "direct", ["C99"])], preview, "draft")
    unsupported = attribute("total", "derived", ["C3"])
    unsupported["transformation"] = "Sum revenue over the last 12 months"
    proposal, _, _, _ = _schema_drafts([unsupported], preview, "draft")
    assert proposal["fields"][0]["model_proposal"]["transformation"] is None
    assert any(
        "lacked an exact supporting excerpt" in q
        for q in proposal["fields"][0]["decisions_required"]
    )
    mismatched, _, contract, _ = _schema_drafts(
        [attribute("vulnerability_type", "direct", ["C1"])], preview, "draft"
    )
    assert mismatched["fields"][0]["mapping_status"] == "unresolved"
    assert mismatched["fields"][0]["catalog_observations"][0]["column"] == "holding_id"
    assert "logicalType" not in contract["schema"][0]["properties"][0]
    assert (
        "mapping: unresolved" in contract["schema"][0]["properties"][0]["description"]
    )
    conflicting = attribute("customer_key", "multiple", ["C2", "C3"])
    _, _, contract, _ = _schema_drafts([conflicting], preview, "draft")
    assert "logicalType" not in contract["schema"][0]["properties"][0]


def test_explicit_brief_fields_are_not_lost_if_model_omits_them(tmp_path):
    from open_data_products._handoff_implementation import _complete_explicit_attributes

    brief, product, context = setup_inputs(tmp_path)
    brief.write_text(
        "# Overview\nA proposed output.\n## Attributes\n- requested_value\n- `other_field`\n"
    )
    preview = preview_implementation_handoff(
        brief,
        product,
        resolve_generation_settings(),
        context_snapshot=context,
        asset_id="asset-1",
    )
    attributes = _complete_explicit_attributes([], preview)
    assert [a["name"] for a in attributes] == ["requested_value", "other_field"]
    assert all(a["mapping_kind"] == "unresolved" for a in attributes)
    assert all(a["classification"] == "explicit" for a in attributes)


def setup_inputs(tmp_path):
    brief = tmp_path / "brief.md"
    brief.write_text(
        "Customers need holdings. Draft completeness target is 98 percent."
    )
    product = tmp_path / "product.yaml"
    product.write_bytes(
        (FIXTURES / "products/odps_product_product-holdings.yaml").read_bytes()
    )
    context = {
        "assets": [
            {
                "id": "asset-1",
                "name": "holdings",
                "type": "table",
                "fullyQualifiedName": "synthetic.bank.holdings",
                "columns": [
                    {"name": "holding_id", "dataType": "VARCHAR"},
                    {"name": "customer_id", "dataType": "VARCHAR"},
                ],
                "sampleData": ["secret sample"],
            }
        ],
        "incomplete": True,
    }
    return brief, product, context


def reply():
    return yaml.safe_dump(
        {
            "business_intent": [
                {
                    "text": "Provide holdings",
                    "source": "business",
                    "quote": "Customers need holdings.",
                }
            ],
            "known_requirements": [
                {
                    "text": "Provide holdings to consumers",
                    "source": "business",
                    "quote": "Customers need holdings.",
                    "when": "a permitted consumer requests holdings",
                    "then": "holdings are made available subject to agreed controls",
                }
            ],
            "open_questions": ["Which source is authoritative?"],
            "implementation_tasks": [
                {
                    "text": "Review the selected holdings source",
                    "source": "business",
                    "quote": "Customers need holdings.",
                }
            ],
            "odps_enrichment": [
                {
                    "field": "valueProposition",
                    "text": "Provide a holdings view",
                    "source": "business",
                    "quote": "Customers need holdings.",
                },
                {
                    "field": "dataQuality",
                    "text": "Draft completeness target is 98 percent",
                    "source": "business",
                    "quote": "Draft completeness target is 98 percent.",
                },
            ],
            "output_attributes": [
                {
                    "name": name,
                    "classification": "implied",
                    "business_quote": "B1",
                    "reason": "Proposed identifier for holdings",
                    "source_columns": [ref],
                    "mapping_kind": "direct",
                    "transformation": None,
                    "questions": ["Confirm identifier semantics?"],
                }
                for name, ref in (("holding_id", "C1"), ("customer_id", "C2"))
            ],
        }
    )


def test_complete_draft_and_jira_delivery(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    assert "secret sample" not in json.dumps(
        preview.to_dict()["selected_catalog_evidence_sent"]
    )
    prompts = []

    def client(settings):
        def call(prompt, model):
            prompts.append(prompt)
            return reply()

        return call

    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client", client
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    assert "Return only one valid JSON object" in prompts[0]
    assert "secret sample" not in prompts[0]
    assert (
        "secret sample" not in (root / "supporting/catalog-evidence.yaml").read_text()
    )
    for path in (
        "proposal.md",
        "specs/data-product-draft/spec.md",
        "design.md",
        "tasks.md",
        "preparation.md",
        "supporting/product-enriched.odps.yaml",
        "supporting/output-schema.yaml",
        "supporting/odcs-draft.yaml",
    ):
        assert (root / path).is_file()
    product_draft = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    quality = product_draft["product"]["dataQuality"]["declarative"]
    assert "draft" not in quality
    assert quality["default"]["dimensions"][0]["dimension"] == "completeness"
    assert quality["default"]["dimensions"][0]["objective"] == 98
    assert quality["default"]["dimensions"][0]["unit"] == "percentage"
    assert product_draft["product"]["contract"]["$ref"] == "odcs-draft.yaml"
    assert (
        product_draft["product"]["details"]["en"]["valueProposition"]
        == "Provide a holdings view"
    )
    contract = yaml.safe_load((root / "supporting/odcs-draft.yaml").read_text())
    assert [x["name"] for x in contract["schema"][0]["properties"]] == [
        "holding_id",
        "customer_id",
    ]
    assert "required" not in contract["schema"][0]["properties"][0]
    assert not (root / "supporting/business-brief.txt").exists()
    assert not (root / "supporting/source-odps.yaml").exists()
    from zipfile import ZipFile

    archive = tmp_path / "handoff.zip"
    with ZipFile(archive, "w") as zipped:
        for file in root.rglob("*"):
            if file.is_file():
                zipped.write(file, file.relative_to(root).as_posix())
    issue = handoff_jira_request(
        root,
        project="DATA",
        issue_type_id="10",
        package_attachment=archive,
        attachments=(
            str(brief),
            str(root / "supporting/odcs-draft.yaml"),
        ),
    )
    assert issue.summary.startswith("Implement data product:")
    assert (
        "Enriched ODPS deliverable (draft): Jira attachment product-enriched.odps.yaml"
        in issue.description
    )
    assert "Original ODPS source: not delivered" in issue.description
    with pytest.raises(ValueError, match="Do not attach the original ODPS"):
        handoff_jira_request(
            root,
            project="DATA",
            issue_type_id="10",
            package_attachment=archive,
            attachments=(str(product),),
        )
    with pytest.raises(ValueError, match="Original ODPS source URLs"):
        handoff_jira_request(
            root,
            project="DATA",
            issue_type_id="10",
            package_attachment=archive,
            product_url="https://example.org/original.yaml",
        )
    explicit = handoff_jira_request(
        root,
        project="DATA",
        issue_type_id="10",
        package_attachment=archive,
        attachments=(str(root / "supporting/product-enriched.odps.yaml"),),
    )
    assert len(explicit.attachments) == 3
    adapter = JiraCloudAdapter(
        JiraConnection(
            "test", "https://example.atlassian.net", "EMAIL", "TOKEN", read_only=False
        )
    )
    monkeypatch.setattr(
        adapter,
        "_request",
        lambda method, path, body=None: (
            {"key": "DATA-1"}
            if method == "POST"
            else (
                {"values": [{"fieldId": "summary", "required": True}]}
                if path.startswith("issue/createmeta")
                else {"issues": []}
            )
        ),
    )
    uploads = []
    monkeypatch.setattr(
        adapter, "_upload_attachment", lambda key, name, data: uploads.append(name)
    )
    review = adapter.review_issue(issue)
    result = adapter.create_issue(issue, reviewed_sha256=review["reviewed_sha256"])
    assert result["key"] == "DATA-1"
    assert uploads == [
        "handoff.zip",
        "product-enriched.odps.yaml",
        "brief.md",
        "odcs-draft.yaml",
    ]


def test_no_asset_stays_open_without_integrations(tmp_path, monkeypatch):
    brief, product, _ = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(brief, product, settings)
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, model: yaml.safe_dump(
            dict(yaml.safe_load(reply()), output_attributes=[])
        ),
    )
    root = generate_implementation_handoff(
        preview, tmp_path, "holdings-change", settings, reviewed_sha256=preview.digest
    )
    assert not (root / "supporting/output-schema.yaml").exists()
    contract = yaml.safe_load((root / "supporting/odcs-draft.yaml").read_text())
    assert contract["kind"] == "DataContract" and contract["status"] == "draft"
    assert "schema" not in contract
    assert "no output attributes" in contract["description"]["purpose"]
    status = yaml.safe_load((root / "supporting/validation-status.yaml").read_text())
    assert status["output_schema_to_odcs"]["status"] == "not_assessed"
    product_draft = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    assert product_draft["product"]["contract"]["$ref"] == "odcs-draft.yaml"
    (root / "supporting/odcs-draft.yaml").unlink()
    with pytest.raises(ValueError, match="requires an ODCS draft"):
        handoff_jira_request(
            root,
            project="DATA",
            issue_type_id="10",
            shared_filesystem="/shared/package",
        )
    assert (
        "No output attributes were extracted"
        in (root / "supporting/manifest.yaml").read_text()
    )


def test_context_change_and_bad_quote_stop_before_writing(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    context["assets"][0]["columns"][0]["name"] = "changed"
    with pytest.raises(ValueError, match="changed"):
        generate_implementation_handoff(
            preview,
            tmp_path,
            "holdings-change",
            settings,
            reviewed_sha256=preview.digest,
        )
    context["assets"][0]["columns"][0]["name"] = "holding_id"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, model: reply().replace(
            "Customers need holdings.", "fabricated quotation"
        ),
    )
    with pytest.raises(ValueError, match="unsupported"):
        generate_implementation_handoff(
            preview,
            tmp_path,
            "holdings-change",
            settings,
            reviewed_sha256=preview.digest,
        )
    assert not (tmp_path / "openspec").exists()


def test_selected_asset_must_be_unique_and_have_columns(tmp_path):
    brief, product, context = setup_inputs(tmp_path)
    with pytest.raises(ValueError, match="exactly one"):
        preview_implementation_handoff(
            brief,
            product,
            resolve_generation_settings(),
            context_snapshot=context,
            asset_id="missing",
        )


def test_cli_implementation_preview_and_execution(tmp_path, monkeypatch, capsys):
    from open_data_products.cli import main

    brief, product, context = setup_inputs(tmp_path)
    snapshot = tmp_path / "context.json"
    snapshot.write_text(json.dumps(context))
    args = [
        "handoff",
        str(brief),
        str(product),
        "--output",
        str(tmp_path / "out"),
        "--change",
        "holdings-change",
        "--context",
        str(snapshot),
        "--asset-id",
        "asset-1",
    ]
    assert main(args) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["mode"] == "implementation-draft"
    assert preview["selected_catalog_evidence_sent"]["id"] == "asset-1"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, model: reply(),
    )
    assert (
        main(args + ["--execute", "--reviewed-sha256", preview["reviewed_sha256"]]) == 0
    )
    assert (
        tmp_path / "out/openspec/changes/holdings-change/supporting/odcs-draft.yaml"
    ).is_file()


def test_v42_existing_contract_is_preserved(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    product.write_bytes(
        (Path(__file__).parent / "fixtures/odps_v42_profiles.yaml").read_bytes()
    )
    original = yaml.safe_load(product.read_text())["product"]["contract"]
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, model: reply(),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    enriched = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    assert enriched["product"]["contract"] == original
    assert (
        "Existing ODPS contract preserved"
        in (root / "supporting/manifest.yaml").read_text()
    )


def test_unsupported_types_remain_open(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    context["assets"][0]["columns"][0]["dataType"] = "GEOGRAPHY"
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, model: reply(),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    properties = yaml.safe_load((root / "supporting/odcs-draft.yaml").read_text())[
        "schema"
    ][0]["properties"]
    holding = next(f for f in properties if f["name"] == "holding_id")
    assert "logicalType" not in holding
    assert "type: unresolved" in holding["description"]


def test_v42_links_proposed_contract_as_default_profile(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    document = yaml.safe_load(
        (Path(__file__).parent / "fixtures/odps_v42_profiles.yaml").read_text()
    )
    document["product"].pop("contract")
    document["product"].pop("dataAccess")
    product.write_text(yaml.safe_dump(document))
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, model: reply(),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    enriched = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    assert enriched["version"] == "4.2"
    assert enriched["product"]["contract"]["default"]["$ref"] == "odcs-draft.yaml"


def test_provider_citation_ids_resolve_to_exact_excerpts(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    for group in (
        "business_intent",
        "known_requirements",
        "implementation_tasks",
        "odps_enrichment",
    ):
        for item in model[group]:
            item["quote"] = "B1"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    evidence = yaml.safe_load((root / "supporting/evidence.yaml").read_text())
    assert (
        evidence["model_proposals"]["business_intent"][0]["quote"] == brief.read_text()
    )


def test_wrong_source_citation_id_is_rejected(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["known_requirements"][0]["quote"] = "C1"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    with pytest.raises(ValueError, match="unsupported source quotation"):
        generate_implementation_handoff(
            preview,
            tmp_path / "out",
            "holdings-change",
            settings,
            reviewed_sha256=preview.digest,
        )


def test_provider_nested_scenarios_and_extra_fields_are_reported(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    item = model["known_requirements"][0]
    item["scenario"] = {"when": item.pop("when"), "then": item.pop("then")}
    item["confidence"] = "unverified"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    assert (
        "Additional provider fields omitted from known_requirements"
        in (root / "supporting/manifest.yaml").read_text()
    )
    assert "**WHEN**" in (root / "specs/data-product-draft/spec.md").read_text()


def test_numeric_proposal_without_cited_numeric_evidence_is_flagged(
    tmp_path, monkeypatch
):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["odps_enrichment"].append(
        {
            "field": "SLA",
            "text": "Deliver in 2 hours",
            "source": "business",
            "quote": "Customers need holdings.",
        }
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    manifest = yaml.safe_load((root / "supporting/manifest.yaml").read_text())
    assert any(
        "source quotation does not identify a service expectation" in x
        for x in manifest["findings"]
    )
    product = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    assert "SLA" not in product["product"]
    evidence = yaml.safe_load((root / "supporting/evidence.yaml").read_text())
    assert (
        evidence["odps_enrichment_evidence"][-1]["validation"]
        == "quotation matched; semantic support not verified"
    )


def test_business_enrichment_preserves_original_and_marks_description_draft(
    tmp_path, monkeypatch
):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    before = yaml.safe_load(product.read_text())["product"]["details"]["en"][
        "description"
    ]
    model = yaml.safe_load(reply())
    model["odps_enrichment"].append(
        {
            "field": "description",
            "text": "Scope covers customer holdings",
            "source": "business",
            "quote": "Customers need holdings.",
        }
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    enriched = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    assert enriched["product"]["details"]["en"]["description"].startswith(before)
    assert (
        "Draft business proposal: Scope covers customer holdings"
        in enriched["product"]["details"]["en"]["description"]
    )
    assert (
        yaml.safe_load(product.read_text())["product"]["details"]["en"]["description"]
        == before
    )


def test_unsupported_optional_enrichment_is_omitted_and_reported(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["odps_enrichment"].append(
        {
            "field": "SLA",
            "text": "An invented promise",
            "source": "business",
            "quote": "not in the brief",
        }
    )
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    enriched = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    manifest = yaml.safe_load((root / "supporting/manifest.yaml").read_text())
    assert "SLA" not in enriched["product"]
    assert any("source quotation was unsupported" in x for x in manifest["findings"])


def test_existing_target_openspec_config_is_not_modified(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    target = tmp_path / "target"
    config = target / "openspec/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("schema: custom-workflow\n")
    calls = []
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: calls.append(1),
    )
    with pytest.raises(ValueError, match="configuration detected"):
        generate_implementation_handoff(
            preview, target, "holdings-change", settings, reviewed_sha256=preview.digest
        )
    assert not calls
    assert config.read_text() == "schema: custom-workflow\n"
    assert not (target / "openspec/changes").exists()


def test_repository_without_openspec_is_not_initialized(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    target = tmp_path / "target"
    (target / ".git").mkdir(parents=True)
    calls = []
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: calls.append(1),
    )
    with pytest.raises(
        ValueError, match="Repository or OpenSpec configuration detected"
    ):
        generate_implementation_handoff(
            preview, target, "holdings-change", settings, reviewed_sha256=preview.digest
        )
    assert not calls
    assert not (target / "openspec").exists()


def test_core_requirement_numeric_details_need_cited_support(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["known_requirements"][0]["then"] = "holdings are delivered within 2 hours"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    with pytest.raises(
        ValueError, match="unsupported numeric details in known_requirements"
    ):
        generate_implementation_handoff(
            preview,
            tmp_path / "out",
            "holdings-change",
            settings,
            reviewed_sha256=preview.digest,
        )
    assert not (tmp_path / "out").exists()


def test_numeric_details_can_use_additional_exact_source_excerpt(tmp_path, monkeypatch):
    brief, product, context = setup_inputs(tmp_path)
    brief.write_text("Customers need holdings.\nDraft publication by 06:00.")
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["odps_enrichment"] = [model["odps_enrichment"][0]]
    model["implementation_tasks"][0]["text"] = "Review draft publication by 06:00"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    evidence = yaml.safe_load((root / "supporting/evidence.yaml").read_text())
    extra = evidence["model_proposals"]["implementation_tasks"][0][
        "additional_numeric_evidence"
    ]
    assert any(
        e["number"] == "06" and e["quote"] == "Draft publication by 06:00."
        for e in extra
    )
    manifest = yaml.safe_load((root / "supporting/manifest.yaml").read_text())
    assert any("semantic support requires review" in x for x in manifest["findings"])


def test_ambiguous_numeric_evidence_is_not_assigned_to_first_match(
    tmp_path, monkeypatch
):
    brief, product, context = setup_inputs(tmp_path)
    brief.write_text(
        brief.read_text() + "\nClosed in 90 days.\nTarget 90% trial satisfaction.\n"
    )
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["implementation_tasks"][0]["text"] = "Review the 90 percent trial target"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "review-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    e = yaml.safe_load((root / "supporting/evidence.yaml").read_text())[
        "model_proposals"
    ]["implementation_tasks"][0]["additional_numeric_evidence"][0]
    assert e["number"] == "90" and e["quote"] is None
    assert set(e["candidate_quotes"]) == {
        "Closed in 90 days.",
        "Target 90% trial satisfaction.",
    }
    assert "ambiguous" in e["status"]


def test_odps_version_is_attributed_to_product_draft_not_business(
    tmp_path, monkeypatch
):
    brief, product, context = setup_inputs(tmp_path)
    settings = resolve_generation_settings()
    preview = preview_implementation_handoff(
        brief, product, settings, context_snapshot=context, asset_id="asset-1"
    )
    model = yaml.safe_load(reply())
    model["implementation_tasks"][0]["text"] = "Validate ODPS (v4.1) draft"
    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client",
        lambda _: lambda prompt, name: yaml.safe_dump(model),
    )
    root = generate_implementation_handoff(
        preview,
        tmp_path / "out",
        "holdings-change",
        settings,
        reviewed_sha256=preview.digest,
    )
    evidence = yaml.safe_load((root / "supporting/evidence.yaml").read_text())
    extra = evidence["model_proposals"]["implementation_tasks"][0][
        "additional_numeric_evidence"
    ]
    assert extra[0]["number"] == "4.1" and extra[0]["source"] == "odps"
    assert "4.1" in extra[0]["quote"]


def test_preserved_contract_sample_content_is_withheld_from_package():
    from open_data_products._handoff_implementation import _without_samples

    context = {
        "contracts": [
            {
                "origin": "SDK-preserved ODCS source",
                "sha256": "original",
                "yaml": "schema:\n- sampleData:\n  - private-value\n",
            }
        ]
    }
    result = _without_samples(context)["contracts"][0]
    assert "private-value" not in str(result)
    assert "yaml" not in result
    assert result["sha256"] == "original"
    assert "withheld" in result["content_status"]
