"""Ten executable adapter cases for every bundled ODPV 1.1 profile."""

from typing import Callable, Dict, Tuple

import pytest

from open_data_products.profiles import (
    load_profile,
    profile_ref,
    transform_profile,
    validate_profile,
)

Case = Tuple[str, Callable[[], None]]


def _ref(profile_id: str):
    return profile_ref(profile_id, "0.1.0")


def _transform(profile_id: str, direction: str, document: Dict):
    return transform_profile(_ref(profile_id), direction, document, allow_draft=True)


def _dcat_document():
    return {
        "objects": [
            {"id": "catalog", "type": "DataProductCatalog"},
            {
                "id": "dataset-v1",
                "type": "Dataset",
                "properties": {"identifier": "sales-v1", "license": "MIT"},
            },
            {"id": "dataset-v2", "type": "Dataset"},
            {"id": "service", "type": "DataService"},
        ],
        "relationships": [
            {"source": "dataset-v1", "type": "exposes", "target": "service"},
            {"source": "dataset-v2", "type": "replaces", "target": "dataset-v1"},
            {"source": "dataset-v2", "type": "versionOf", "target": "dataset-v1"},
        ],
    }


def _dcat_nodes():
    return _transform("ODPV-DCAT-3", "odpvToExternal", _dcat_document())["output"][
        "@graph"
    ]


def _dcat_case_1():
    assert validate_profile(_ref("ODPV-DCAT-3")).valid


def _dcat_case_2():
    with pytest.raises(ValueError, match="allow_draft=True"):
        load_profile(_ref("ODPV-DCAT-3"))


def _dcat_case_3():
    assert len(load_profile(_ref("ODPV-DCAT-3"), allow_draft=True).mappings()) == 17


def _dcat_case_4():
    assert (
        next(node for node in _dcat_nodes() if node["@id"] == "catalog")["@type"]
        == "dcat:Catalog"
    )


def _dcat_case_5():
    node = next(node for node in _dcat_nodes() if node["@id"] == "dataset-v1")
    assert node["dcterms:identifier"] == "sales-v1"
    assert node["dcterms:license"] == "MIT"


def _dcat_case_6():
    node = next(node for node in _dcat_nodes() if node["@id"] == "dataset-v1")
    assert node["dcat:accessService"] == "service"


def _dcat_case_7():
    node = next(node for node in _dcat_nodes() if node["@id"] == "dataset-v2")
    assert node["dcterms:replaces"] == "dataset-v1"


def _dcat_case_8():
    nodes = {node["@id"]: node for node in _dcat_nodes()}
    assert nodes["dataset-v1"]["dcat:hasVersion"] == "dataset-v2"
    assert nodes["dataset-v2"]["dcat:previousVersion"] == "dataset-v1"


def _dcat_case_9():
    result = _transform(
        "ODPV-DCAT-3",
        "externalToOdpv",
        {"@graph": [{"@id": "dataset", "@type": "dcat:Dataset"}]},
    )
    assert result["output"]["objects"] == [
        {"id": "dataset", "type": "Dataset", "properties": {}}
    ]


def _dcat_case_10():
    result = _transform(
        "ODPV-DCAT-3",
        "odpvToExternal",
        {"objects": [{"id": "team", "type": "Team"}], "relationships": []},
    )
    assert result["unmappedConcepts"] == ["Team"]


DCAT_CASES: Tuple[Case, ...] = tuple(
    ("%02d" % number, globals()["_dcat_case_%d" % number]) for number in range(1, 11)
)


@pytest.mark.parametrize(
    ("case_id", "case"), DCAT_CASES, ids=[item[0] for item in DCAT_CASES]
)
def test_dcat_profile_has_ten_executable_cases(case_id: str, case: Callable[[], None]):
    case()


def _odcs_document():
    return {
        "objects": [
            {
                "id": "product",
                "type": "DataProduct",
                "properties": {
                    "identifier": "sales-contract",
                    "productDetails": {"name": "Sales"},
                    "schema": {"type": "object"},
                    "retention": "P30D",
                    "sla": {"freshness": "PT1H"},
                    "support": "support@example.test",
                    "license": "MIT",
                },
            }
        ]
    }


def _odcs_output():
    return _transform("ODPV-ODCS-3", "odpvToExternal", _odcs_document())["output"]


def _odcs_case_1():
    assert validate_profile(_ref("ODPV-ODCS-3")).valid


def _odcs_case_2():
    with pytest.raises(ValueError, match="allow_draft=True"):
        load_profile(_ref("ODPV-ODCS-3"))


def _odcs_case_3():
    assert len(load_profile(_ref("ODPV-ODCS-3"), allow_draft=True).mappings()) == 15


def _odcs_case_4():
    assert _odcs_output()["kind"] == "DataContract"


def _odcs_case_5():
    assert _odcs_output()["id"] == "sales-contract"


def _odcs_case_6():
    assert _odcs_output()["schema"] == {"type": "object"}


def _odcs_case_7():
    assert _odcs_output()["slaProperties"]["retention"] == "P30D"


def _odcs_case_8():
    assert _odcs_output()["support"] == "support@example.test"


def _odcs_case_9():
    result = _transform("ODPV-ODCS-3", "odpvToExternal", {"objects": []})
    assert result["status"] == "refused"
    assert result["transformations"]["refused"][0]["reason"] == "requires_data_product"


def _odcs_case_10():
    result = _transform("ODPV-ODCS-3", "externalToOdpv", {"id": "contract"})
    assert result["status"] == "refused"
    assert (
        result["transformations"]["refused"][0]["reason"]
        == "direction_not_supported_by_profile"
    )


ODCS_CASES: Tuple[Case, ...] = tuple(
    ("%02d" % number, globals()["_odcs_case_%d" % number]) for number in range(1, 11)
)


@pytest.mark.parametrize(
    ("case_id", "case"), ODCS_CASES, ids=[item[0] for item in ODCS_CASES]
)
def test_odcs_profile_has_ten_executable_cases(case_id: str, case: Callable[[], None]):
    case()


def _openlineage_document(state: str = "observed", bindings: bool = True):
    document = {
        "objects": [
            {"id": "job", "type": "Workflow"},
            {"id": "dataset", "type": "Dataset"},
        ],
        "relationships": [
            {"source": "job", "type": "uses", "target": "dataset"},
            {"source": "job", "type": "consumes", "target": "dataset"},
            {"source": "job", "type": "derivedFrom", "target": "dataset"},
            {"source": "job", "type": "produces", "target": "dataset", "state": state},
        ],
    }
    if bindings:
        document["bindings"] = {
            "openlineage": {
                "jobs": {"job": {"namespace": "acme", "name": "load"}},
                "datasets": {"dataset": {"namespace": "acme", "name": "sales"}},
            }
        }
    return document


def _openlineage_output():
    return _transform("ODPV-OPENLINEAGE-1", "odpvToExternal", _openlineage_document())


def _openlineage_case_1():
    assert validate_profile(_ref("ODPV-OPENLINEAGE-1")).valid


def _openlineage_case_2():
    with pytest.raises(ValueError, match="allow_draft=True"):
        load_profile(_ref("ODPV-OPENLINEAGE-1"))


def _openlineage_case_3():
    assert (
        len(load_profile(_ref("ODPV-OPENLINEAGE-1"), allow_draft=True).mappings()) == 10
    )


def _openlineage_case_4():
    assert len(_openlineage_output()["output"]["events"]) == 4


def _openlineage_case_5():
    assert len(_openlineage_output()["declaredState"]) == 3


def _openlineage_case_6():
    assert len(_openlineage_output()["observedState"]) == 1


def _openlineage_case_7():
    result = _transform(
        "ODPV-OPENLINEAGE-1", "odpvToExternal", _openlineage_document("declared")
    )
    assert (
        result["transformations"]["refused"][-1]["reason"]
        == "outputs_require_observed_state"
    )


def _openlineage_case_8():
    result = _transform(
        "ODPV-OPENLINEAGE-1", "odpvToExternal", _openlineage_document(bindings=False)
    )
    assert len(result["transformations"]["refused"]) == 4


def _openlineage_case_9():
    result = _openlineage_output()
    assert result["output"]["events"][0]["inputs"][0]["name"] == "sales"


def _openlineage_case_10():
    result = _transform("ODPV-OPENLINEAGE-1", "externalToOdpv", {"events": []})
    assert result["status"] == "refused"


OPENLINEAGE_CASES: Tuple[Case, ...] = tuple(
    ("%02d" % number, globals()["_openlineage_case_%d" % number])
    for number in range(1, 11)
)


@pytest.mark.parametrize(
    ("case_id", "case"), OPENLINEAGE_CASES, ids=[item[0] for item in OPENLINEAGE_CASES]
)
def test_openlineage_profile_has_ten_executable_cases(
    case_id: str, case: Callable[[], None]
):
    case()


def _prov_document():
    return {
        "objects": [
            {"id": "workflow", "type": "Workflow"},
            {"id": "dataset", "type": "Dataset"},
            {"id": "provider", "type": "Provider"},
        ],
        "relationships": [
            {"source": "workflow", "type": "uses", "target": "dataset"},
            {"source": "workflow", "type": "consumes", "target": "dataset"},
            {"source": "workflow", "type": "produces", "target": "dataset"},
            {"source": "dataset", "type": "providedBy", "target": "provider"},
            {"source": "dataset", "type": "versionOf", "target": "dataset"},
        ],
    }


def _prov_output():
    return _transform("ODPV-PROV-O", "odpvToExternal", _prov_document())["output"]


def _prov_case_1():
    assert validate_profile(_ref("ODPV-PROV-O")).valid


def _prov_case_2():
    with pytest.raises(ValueError, match="allow_draft=True"):
        load_profile(_ref("ODPV-PROV-O"))


def _prov_case_3():
    assert len(load_profile(_ref("ODPV-PROV-O"), allow_draft=True).mappings()) == 10


def _prov_case_4():
    assert {node["type"] for node in _prov_output()["entities"]} == {
        "prov:Activity",
        "prov:Entity",
        "prov:Agent",
    }


def _prov_case_5():
    assert {item["predicate"] for item in _prov_output()["relations"]} >= {
        "prov:used",
        "prov:wasGeneratedBy",
    }


def _prov_case_6():
    assert (
        next(
            item
            for item in _prov_output()["relations"]
            if item["predicate"] == "prov:wasGeneratedBy"
        )["subject"]
        == "dataset"
    )


def _prov_case_7():
    assert (
        next(
            item
            for item in _prov_output()["relations"]
            if item["predicate"] == "prov:wasAttributedTo"
        )["object"]
        == "provider"
    )


def _prov_case_8():
    result = _transform(
        "ODPV-PROV-O",
        "odpvToExternal",
        {
            "objects": [
                {"id": "consumer", "type": "Consumer"},
                {"id": "dataset", "type": "Dataset"},
            ],
            "relationships": [
                {"source": "consumer", "type": "consumes", "target": "dataset"}
            ],
        },
    )
    assert (
        result["transformations"]["skipped"][0]["reason"]
        == "requires_prov_bound_endpoints"
    )


def _prov_case_9():
    result = _transform(
        "ODPV-PROV-O",
        "externalToOdpv",
        {"entities": [{"id": "dataset", "type": "prov:Entity"}], "relations": []},
    )
    assert result["output"]["objects"][0]["type"] == "Dataset"


def _prov_case_10():
    result = _transform(
        "ODPV-PROV-O",
        "externalToOdpv",
        {
            "entities": [],
            "relations": [
                {"subject": "workflow", "predicate": "prov:used", "object": "dataset"}
            ],
        },
    )
    assert result["output"]["relationships"][0]["type"] == "uses"


PROV_CASES: Tuple[Case, ...] = tuple(
    ("%02d" % number, globals()["_prov_case_%d" % number]) for number in range(1, 11)
)


@pytest.mark.parametrize(
    ("case_id", "case"), PROV_CASES, ids=[item[0] for item in PROV_CASES]
)
def test_prov_profile_has_ten_executable_cases(case_id: str, case: Callable[[], None]):
    case()


def _odrl_document(rules=None):
    return {
        "objects": [
            {"id": "dataset", "type": "Dataset"},
            {
                "id": "policy",
                "type": "Policy",
                "properties": {
                    "rules": rules if rules is not None else [{"action": "use"}]
                },
            },
        ],
        "relationships": [
            {"source": "dataset", "type": "governedBy", "target": "policy"}
        ],
    }


def _odrl_case_1():
    assert validate_profile(_ref("ODPV-ODRL-2")).valid


def _odrl_case_2():
    with pytest.raises(ValueError, match="allow_draft=True"):
        load_profile(_ref("ODPV-ODRL-2"))


def _odrl_case_3():
    assert len(load_profile(_ref("ODPV-ODRL-2"), allow_draft=True).mappings()) == 11


def _odrl_case_4():
    result = _transform("ODPV-ODRL-2", "odpvToExternal", _odrl_document())
    assert result["output"]["policies"][0]["@type"] == "odrl:Policy"


def _odrl_case_5():
    result = _transform("ODPV-ODRL-2", "odpvToExternal", _odrl_document())
    assert result["output"]["policies"][0]["odrl:target"] == "dataset"


def _odrl_case_6():
    result = _transform("ODPV-ODRL-2", "odpvToExternal", _odrl_document([]))
    assert result["transformations"]["refused"][0]["reason"] == "requires_policy_rules"


def _odrl_case_7():
    result = _transform("ODPV-ODRL-2", "odpvToExternal", _odrl_document([{}]))
    assert (
        result["transformations"]["refused"][0]["reason"]
        == "every_rule_requires_action"
    )


def _odrl_case_8():
    result = _transform(
        "ODPV-ODRL-2",
        "externalToOdpv",
        {
            "policies": [
                {"@id": "policy", "@type": "odrl:Policy", "odrl:permission": []}
            ]
        },
    )
    assert result["output"]["objects"][0]["type"] == "Policy"


def _odrl_case_9():
    result = _transform(
        "ODPV-ODRL-2",
        "externalToOdpv",
        {
            "policies": [
                {"@id": "agreement", "@type": "odrl:Agreement", "odrl:permission": []}
            ]
        },
    )
    assert result["output"]["objects"][0]["type"] == "Agreement"


def _odrl_case_10():
    result = _transform(
        "ODPV-ODRL-2",
        "externalToOdpv",
        {
            "policies": [
                {
                    "@id": "policy",
                    "@type": "odrl:Policy",
                    "odrl:permission": [{"action": "use"}],
                }
            ]
        },
    )
    assert result["output"]["objects"][1]["type"] == "UsageRights"


ODRL_CASES: Tuple[Case, ...] = tuple(
    ("%02d" % number, globals()["_odrl_case_%d" % number]) for number in range(1, 11)
)


@pytest.mark.parametrize(
    ("case_id", "case"), ODRL_CASES, ids=[item[0] for item in ODRL_CASES]
)
def test_odrl_profile_has_ten_executable_cases(case_id: str, case: Callable[[], None]):
    case()
