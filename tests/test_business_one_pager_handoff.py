"""Compare handoffs from two business briefs with the same provider and context."""

import json
from pathlib import Path

import yaml

from open_data_products import (
    generate_implementation_handoff,
    preview_implementation_handoff,
)
from open_data_products.agent import validate_document
from open_data_products.generation import resolve_generation_settings

FIXTURES = Path(__file__).parent / "fixtures" / "business_one_pager"


def _provider_reply(brief):
    if "previous 90 calendar days" in brief:
        source = "For a selected customer, show a separate entry for each account, card or loan the customer holds. The first version should include active products and products closed during the previous 90 calendar days. It should not include applications that never became active."
        field_source = "- The product name or type as it appears in the source system, for example current account or credit card."
        question = "How should joint ownership be represented?"
    else:
        source = "The meaning of “recently” still needs to be agreed."
        field_source = "For each customer, we need to know which accounts, cards and loans they hold. For each product, the teams need to see the product type, whether it is active or closed, and when it was opened or closed, if available."
        question = "What does recently mean?"
    citations = json.loads(brief.split("\nCITATION INDEX (JSON):\n", 1)[1])
    field_ref = next(
        key
        for key, item in citations.items()
        if item["source"] == "business" and item["quote"] == field_source
    )
    return yaml.safe_dump(
        {
            "business_intent": [
                {
                    "text": "Propose a customer product view",
                    "source": "business",
                    "quote": source,
                }
            ],
            "known_requirements": [
                {
                    "text": "Review the requested product scope",
                    "source": "business",
                    "quote": source,
                    "when": "the scope is reviewed",
                    "then": "the relevant decisions are recorded",
                }
            ],
            "open_questions": [question],
            "implementation_tasks": [
                {
                    "text": "Investigate the requested scope",
                    "source": "business",
                    "quote": source,
                }
            ],
            "odps_enrichment": [],
            "output_attributes": [
                {
                    "name": "product_type",
                    "classification": "explicit",
                    "business_quote": field_ref,
                    "reason": "The business asks for product type",
                    "source_columns": ["C1"],
                    "mapping_kind": "direct",
                    "transformation": None,
                    "questions": ["Confirm product type semantics?"],
                }
            ],
        },
        allow_unicode=True,
    )


def test_small_and_rich_briefs_produce_separate_evidence_bound_handoffs(
    tmp_path, monkeypatch
):
    settings = resolve_generation_settings(provider="openai", model="gpt-5.2")
    context = {
        "assets": [
            {
                "id": "asset-1",
                "name": "holdings",
                "type": "table",
                "fullyQualifiedName": "test.catalog.holdings",
                "columns": [{"name": "product_type", "dataType": "VARCHAR"}],
            }
        ]
    }
    product = FIXTURES / "product.odps.yaml"
    captured = []

    def client(_settings):
        def generate(prompt, _model):
            captured.append(prompt)
            return _provider_reply(prompt)

        return generate

    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client", client
    )
    results = {}
    for variant in ("small", "rich"):
        preview = preview_implementation_handoff(
            FIXTURES / (variant + ".md"),
            product,
            settings,
            context_snapshot=context,
            asset_id="asset-1",
        )
        root = generate_implementation_handoff(
            preview,
            tmp_path / variant,
            "product-holdings",
            settings,
            reviewed_sha256=preview.digest,
        )
        support = root / "supporting"
        trace = yaml.safe_load((support / "requirements-traceability.yaml").read_text())
        decisions = yaml.safe_load((support / "open-decisions.yaml").read_text())
        enriched = yaml.safe_load((support / "product-enriched.odps.yaml").read_text())
        assert validate_document(enriched).valid
        assert (root / "specs/data-product-draft/spec.md").is_file()
        assert (support / "odcs-draft.yaml").is_file()
        results[variant] = {
            "root": root,
            "trace": trace,
            "decisions": decisions,
            "source": "\n".join(x["source"]["text"] for x in trace["requirements"]),
        }
    assert len(captured) == 2
    assert "previous 90 calendar days" not in results["small"]["source"]
    assert "previous 90 calendar days" in results["rich"]["source"]
    assert "08:00 Abu Dhabi time" not in results["small"]["source"]
    assert "08:00 Abu Dhabi time" in results["rich"]["source"]
    assert (
        "meaning of “recently” still needs to be agreed" in results["small"]["source"]
    )
    assert len(results["rich"]["trace"]["requirements"]) > len(
        results["small"]["trace"]["requirements"]
    )
    assert any(
        "joint ownership" in d["question"]
        for d in results["rich"]["decisions"]["decisions"]
    )
    assert any(
        "recently" in d["question"] for d in results["small"]["decisions"]["decisions"]
    )


def test_natural_language_business_day_deadline_remains_in_draft_sla(
    tmp_path, monkeypatch
):
    settings = resolve_generation_settings(provider="openai", model="gpt-5.2")
    context = {
        "assets": [
            {
                "id": "asset-1",
                "name": "holdings",
                "type": "table",
                "fullyQualifiedName": "test.catalog.holdings",
                "columns": [{"name": "product_type", "dataType": "VARCHAR"}],
            }
        ]
    }
    brief = FIXTURES / "rich.md"
    preview = preview_implementation_handoff(
        brief,
        FIXTURES / "product.odps.yaml",
        settings,
        context_snapshot=context,
        asset_id="asset-1",
    )

    def client(_):
        def generate(prompt, model):
            reply = yaml.safe_load(_provider_reply(prompt))
            quote = "The overview should be refreshed on each UAE business day and available to staff by 08:00 Abu Dhabi time. Each source should provide its latest available update before that deadline. A record should show the time of the latest successful update from its source."
            reply["odps_enrichment"].append(
                {
                    "field": "SLA",
                    "text": "Draft business-day refresh deadline",
                    "source": "business",
                    "quote": quote,
                }
            )
            return yaml.safe_dump(reply, allow_unicode=True)

        return generate

    monkeypatch.setattr(
        "open_data_products._handoff_implementation.create_generation_client", client
    )
    root = generate_implementation_handoff(
        preview, tmp_path, "product-holdings", settings, reviewed_sha256=preview.digest
    )
    product = yaml.safe_load(
        (root / "supporting/product-enriched.odps.yaml").read_text()
    )
    sla = product["product"]["SLA"]["declarative"]["default"]
    assert "08:00 Abu Dhabi time" in sla["description"]["en"]
    assert not sla.get("dimensions")
