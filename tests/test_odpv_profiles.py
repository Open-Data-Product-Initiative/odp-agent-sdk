"""Tests for ODPV 1.1 draft interoperability-profile helpers."""

from pathlib import Path

import pytest
import yaml

from open_data_products.profiles import (
    explain_mapping,
    list_vocabulary_releases,
    load_profile,
    load_vocabulary_release,
    profile_ref,
    resolve_mapping,
    transform,
    transform_profile,
    validate_vocabulary_release,
    validate_profile,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "odpv-profiles"


@pytest.mark.parametrize(
    ("profile_id", "mapping_count"),
    [
        ("ODPV-DCAT-3", 17),
        ("ODPV-ODCS-3", 15),
        ("ODPV-OPENLINEAGE-1", 10),
        ("ODPV-PROV-O", 10),
        ("ODPV-ODRL-2", 11),
    ],
)
def test_bundled_draft_profiles_validate_against_selected_vocabulary(
    profile_id, mapping_count
):
    reference = profile_ref(profile_id, "0.1.0")

    report = validate_profile(reference)

    assert report.valid is True
    assert report.profile == reference
    assert report.content_digest
    assert "Profile status is draft." in report.warnings
    assert len(load_profile(reference, allow_draft=True).mappings()) == mapping_count


def test_vocabulary_selection_keeps_v1_0_default_and_v1_1_explicit():
    releases = list_vocabulary_releases()

    assert releases[0]["version"] == "1.0.0"
    assert releases[1]["status"] == "draft"
    assert load_vocabulary_release()["version"] == "1.0.0"
    assert load_vocabulary_release("1.1.0")["version"] == "1.1.0"
    assert validate_vocabulary_release("1.1.0")["valid"] is True


def test_profile_operations_require_draft_opt_in_and_preserve_provenance():
    reference = profile_ref("ODPV-DCAT-3", "0.1.0")

    with pytest.raises(ValueError, match="allow_draft=True"):
        resolve_mapping(reference, odpv_term="Dataset")

    mapping = explain_mapping(reference, "dataset", allow_draft=True)

    assert mapping.mapping_kind == "semanticMapping"
    assert mapping.relation == "exactMatch"
    assert mapping.to_dict()["profile"]["vocabulary"]["version"] == "1.1.0"
    assert mapping.to_dict()["contentDigest"]


def test_dcat_adapter_exports_catalog_nodes_and_preserves_service_identity():
    reference = profile_ref("ODPV-DCAT-3", "0.1.0")
    source = {
        "objects": [
            {
                "id": "dataset-1",
                "type": "Dataset",
                "properties": {"identifier": "sales"},
            },
            {"id": "service-1", "type": "DataService", "properties": {}},
        ],
        "relationships": [
            {"source": "dataset-1", "type": "exposes", "target": "service-1"}
        ],
    }

    result = transform(reference, "exposes", "odpvToExternal", source, allow_draft=True)

    assert result["status"] == "executed"
    dataset = result["output"]["@graph"][0]
    assert dataset["@type"] == "dcat:Dataset"
    assert dataset["dcat:accessService"] == "service-1"
    assert result["contentDigest"]


def test_dcat_adapter_imports_only_bidirectional_profile_scope():
    reference = profile_ref("ODPV-DCAT-3", "0.1.0")

    result = transform_profile(
        reference,
        "externalToOdpv",
        {
            "@graph": [
                {
                    "@id": "dataset-1",
                    "@type": "dcat:Dataset",
                    "dcterms:identifier": "sales",
                }
            ]
        },
        allow_draft=True,
    )

    assert result["status"] == "executed"
    assert result["output"]["objects"][0]["type"] == "Dataset"
    assert result["output"]["objects"][0]["properties"]["identifier"] == "sales"


def test_odcs_adapter_exports_bindings_without_claiming_contract_compliance():
    reference = profile_ref("ODPV-ODCS-3", "0.1.0")

    result = transform_profile(
        reference,
        "odpvToExternal",
        {
            "objects": [
                {
                    "id": "product-1",
                    "type": "DataProduct",
                    "properties": {
                        "identifier": "sales-contract",
                        "schema": {"type": "object"},
                        "retention": "P30D",
                    },
                }
            ]
        },
        allow_draft=True,
    )

    assert result["status"] == "executed"
    assert result["output"]["id"] == "sales-contract"
    assert result["output"]["schema"] == {"type": "object"}
    assert "contract-document" in result["transformations"]["executed"]


def test_openlineage_adapter_keeps_declared_and_observed_facts_separate():
    reference = profile_ref("ODPV-OPENLINEAGE-1", "0.1.0")
    source = {
        "objects": [
            {"id": "workflow-1", "type": "Workflow"},
            {"id": "dataset-1", "type": "Dataset"},
        ],
        "relationships": [
            {"source": "workflow-1", "type": "uses", "target": "dataset-1"},
            {
                "source": "workflow-1",
                "type": "produces",
                "target": "dataset-1",
                "state": "observed",
            },
        ],
        "bindings": {
            "openlineage": {
                "jobs": {"workflow-1": {"namespace": "acme", "name": "load"}},
                "datasets": {"dataset-1": {"namespace": "acme", "name": "sales"}},
            }
        },
    }

    result = transform_profile(reference, "odpvToExternal", source, allow_draft=True)

    assert result["status"] == "executed"
    assert len(result["declaredState"]) == 1
    assert len(result["observedState"]) == 1
    assert result["output"]["events"][1]["outputs"]


def test_prov_adapter_exports_and_imports_directionally_valid_statements():
    reference = profile_ref("ODPV-PROV-O", "0.1.0")
    source = {
        "objects": [
            {"id": "workflow-1", "type": "Workflow"},
            {"id": "dataset-1", "type": "Dataset"},
        ],
        "relationships": [
            {"source": "workflow-1", "type": "produces", "target": "dataset-1"}
        ],
    }

    exported = transform_profile(reference, "odpvToExternal", source, allow_draft=True)
    imported = transform_profile(
        reference,
        "externalToOdpv",
        {
            "entities": [
                {"id": "dataset-1", "type": "prov:Entity"},
                {"id": "workflow-1", "type": "prov:Activity"},
            ],
            "relations": [
                {
                    "subject": "workflow-1",
                    "predicate": "prov:used",
                    "object": "dataset-1",
                }
            ],
        },
        allow_draft=True,
    )

    assert exported["output"]["relations"][0]["subject"] == "dataset-1"
    assert exported["output"]["relations"][0]["predicate"] == "prov:wasGeneratedBy"
    assert imported["output"]["relationships"][0]["type"] == "uses"


def test_odrl_adapter_requires_complete_policy_rules():
    reference = profile_ref("ODPV-ODRL-2", "0.1.0")
    source = {
        "objects": [
            {"id": "dataset-1", "type": "Dataset"},
            {
                "id": "policy-1",
                "type": "Policy",
                "properties": {"rules": [{"action": "use"}]},
            },
        ],
        "relationships": [
            {"source": "dataset-1", "type": "governedBy", "target": "policy-1"}
        ],
    }

    result = transform_profile(reference, "odpvToExternal", source, allow_draft=True)

    assert result["status"] == "executed"
    assert result["output"]["policies"][0]["odrl:target"] == "dataset-1"

    imported = transform_profile(
        reference,
        "externalToOdpv",
        {
            "policies": [
                {
                    "@id": "policy-1",
                    "@type": "odrl:Policy",
                    "odrl:permission": [{"action": "use"}],
                }
            ]
        },
        allow_draft=True,
    )
    assert {item["type"] for item in imported["output"]["objects"]} == {
        "Policy",
        "UsageRights",
    }


@pytest.mark.parametrize(
    ("profile_id", "fixture_name"),
    [
        ("ODPV-DCAT-3", "dcat-3.yaml"),
        ("ODPV-ODCS-3", "odcs-3.yaml"),
        ("ODPV-OPENLINEAGE-1", "openlineage-1.yaml"),
        ("ODPV-PROV-O", "prov-o.yaml"),
        ("ODPV-ODRL-2", "odrl-2.yaml"),
    ],
)
def test_version_pinned_adapter_fixtures_execute(profile_id, fixture_name):
    source = yaml.safe_load((FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8"))

    result = transform_profile(
        profile_ref(profile_id, "0.1.0"),
        "odpvToExternal",
        source,
        allow_draft=True,
    )

    assert result["status"] == "executed"
    assert result["contentDigest"]


def test_profile_mcp_tools_expose_validation_and_draft_opt_in():
    from open_data_products.mcp.tools import TOOLS

    validate = next(tool for tool in TOOLS if tool["name"] == "validate_odpv_profile")
    resolve = next(
        tool for tool in TOOLS if tool["name"] == "resolve_odpv_profile_mapping"
    )
    transform_tool = next(
        tool for tool in TOOLS if tool["name"] == "transform_odpv_profile"
    )

    validation = validate["handler"](
        {"profile_id": "ODPV-PROV-O", "profile_version": "0.1.0"}
    )
    assert '"valid": true' in validation["content"][0]["text"]

    resolved = resolve["handler"](
        {
            "profile_id": "ODPV-PROV-O",
            "profile_version": "0.1.0",
            "odpv_term": "Dataset",
            "allow_draft": True,
        }
    )
    assert '"mappingId": "dataset"' in resolved["content"][0]["text"]

    transformed = transform_tool["handler"](
        {
            "profile_id": "ODPV-DCAT-3",
            "profile_version": "0.1.0",
            "direction": "odpvToExternal",
            "allow_draft": True,
            "source_document": {
                "objects": [{"id": "dataset-1", "type": "Dataset"}],
                "relationships": [],
            },
        }
    )
    assert '"status": "executed"' in transformed["content"][0]["text"]
