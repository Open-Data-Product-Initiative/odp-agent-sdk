"""Directional ODPV interoperability adapters with explicit input boundaries."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set


def _object_index(document: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    objects = document.get("objects")
    if not isinstance(objects, list):
        raise ValueError("ODPV interchange documents require an objects array")
    index: Dict[str, Dict[str, Any]] = {}
    for item in objects:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("Every ODPV object requires a string id")
        if not isinstance(item.get("type"), str):
            raise ValueError("Every ODPV object requires a string type")
        if item["id"] in index:
            raise ValueError("Duplicate ODPV object id: %s" % item["id"])
        index[item["id"]] = item
    return index


def _relationships(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    relationships = document.get("relationships", [])
    if not isinstance(relationships, list):
        raise ValueError("ODPV interchange relationships must be an array")
    result = []
    for item in relationships:
        if not isinstance(item, dict):
            raise ValueError("Every ODPV relationship must be an object")
        for key in ("source", "type", "target"):
            if not isinstance(item.get(key), str):
                raise ValueError("Every ODPV relationship requires %s" % key)
        result.append(item)
    return result


def _bindings(document: Dict[str, Any], standard: str) -> Dict[str, Any]:
    bindings = document.get("bindings", {})
    if not isinstance(bindings, dict):
        return {}
    bound = bindings.get(standard, {})
    return bound if isinstance(bound, dict) else {}


def _mapping_index(profile: Any) -> Dict[str, Any]:
    return {mapping.mapping_id: mapping for mapping in profile.mappings()}


def _result(
    *,
    output: Any,
    executed: Iterable[str] = (),
    skipped: Iterable[Dict[str, str]] = (),
    refused: Iterable[Dict[str, str]] = (),
    fields_bound: Iterable[Dict[str, str]] = (),
    unmapped: Iterable[str] = (),
    declared: Iterable[Dict[str, Any]] = (),
    observed: Iterable[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    executed_items = list(executed)
    skipped_items = list(skipped)
    refused_items = list(refused)
    status = "executed"
    if refused_items and not executed_items:
        status = "refused"
    elif skipped_items or refused_items:
        status = "partial"
    return {
        "status": status,
        "output": output,
        "transformations": {
            "executed": executed_items,
            "skipped": skipped_items,
            "refused": refused_items,
        },
        "fieldsBound": list(fields_bound),
        "unmappedConcepts": list(unmapped),
        "ambiguousMatches": [],
        "unsupportedScope": [],
        "declaredState": list(declared),
        "observedState": list(observed),
    }


def _allow(mapping_id: str, selected: Optional[Set[str]]) -> bool:
    return selected is None or mapping_id in selected


def _dcat_export(
    profile: Any, document: Dict[str, Any], selected: Optional[Set[str]]
) -> Dict[str, Any]:
    objects = _object_index(document)
    relationships = _relationships(document)
    type_mappings = {
        "DataProductCatalog": ("catalog", "dcat:Catalog"),
        "Dataset": ("dataset", "dcat:Dataset"),
        "Distribution": ("distribution", "dcat:Distribution"),
        "DataService": ("data-service", "dcat:DataService"),
        "DataProduct": ("data-product-resource", "dcat:Resource"),
    }
    field_mappings = {
        "identifier": ("identifier", "dcterms:identifier"),
        "provider": ("provider", "dcterms:publisher"),
        "dataHolder": ("data-holder", "dcterms:rightsHolder"),
        "domain": ("domain", "dcat:theme"),
        "dataQuality": ("data-quality", "dcat:qualityMeasurement"),
        "license": ("license", "dcterms:license"),
        "dataAccess": ("access-rights", "dcterms:accessRights"),
        "policy": ("policy", "odrl:hasPolicy"),
        "accessMethod": ("access-method", "dcat:accessURL"),
    }
    graph: List[Dict[str, Any]] = []
    node_by_id: Dict[str, Dict[str, Any]] = {}
    executed: List[str] = []
    fields: List[Dict[str, str]] = []
    unmapped: List[str] = []
    for object_id, item in objects.items():
        node: Dict[str, Any] = {"@id": object_id}
        type_mapping = type_mappings.get(item["type"])
        if type_mapping and _allow(type_mapping[0], selected):
            node["@type"] = type_mapping[1]
            executed.append(type_mapping[0])
        else:
            unmapped.append(item["type"])
        properties = item.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError("ODPV object properties must be an object")
        for property_id, value in properties.items():
            field = field_mappings.get(property_id)
            if field and _allow(field[0], selected):
                node[field[1]] = value
                fields.append(
                    {"mappingId": field[0], "object": object_id, "field": field[1]}
                )
                executed.append(field[0])
        node_by_id[object_id] = node
        graph.append(node)
    skipped: List[Dict[str, str]] = []
    for relationship in relationships:
        source = objects.get(relationship["source"])
        target = objects.get(relationship["target"])
        if source is None or target is None:
            skipped.append(
                {"mappingId": relationship["type"], "reason": "unknown_endpoint"}
            )
            continue
        node = node_by_id[source["id"]]
        relation = relationship["type"]
        if relation == "exposes" and _allow("exposes", selected):
            if target["type"] != "DataService" or "@type" not in node:
                skipped.append(
                    {
                        "mappingId": "exposes",
                        "reason": "requires_cataloged_resource_and_service",
                    }
                )
            else:
                node["dcat:accessService"] = target["id"]
                executed.append("exposes")
        elif relation == "replaces" and _allow("replaces", selected):
            if "@type" not in node or "@type" not in node_by_id[target["id"]]:
                skipped.append(
                    {"mappingId": "replaces", "reason": "requires_cataloged_resources"}
                )
            else:
                node["dcterms:replaces"] = target["id"]
                executed.append("replaces")
        elif relation == "versionOf" and _allow("version-of", selected):
            if "@type" not in node or "@type" not in node_by_id[target["id"]]:
                skipped.append(
                    {
                        "mappingId": "version-of",
                        "reason": "requires_cataloged_resources",
                    }
                )
            else:
                node_by_id[target["id"]]["dcat:hasVersion"] = source["id"]
                node["dcat:previousVersion"] = target["id"]
                executed.append("version-of")
    return _result(
        output={"@context": "https://www.w3.org/ns/dcat.jsonld", "@graph": graph},
        executed=executed,
        skipped=skipped,
        fields_bound=fields,
        unmapped=sorted(set(unmapped)),
    )


def _dcat_import(
    profile: Any, document: Dict[str, Any], selected: Optional[Set[str]]
) -> Dict[str, Any]:
    graph = document.get("@graph")
    if not isinstance(graph, list):
        raise ValueError("DCAT import requires an @graph array")
    type_mappings = {
        "dcat:Catalog": ("catalog", "DataProductCatalog"),
        "dcat:Dataset": ("dataset", "Dataset"),
        "dcat:Distribution": ("distribution", "Distribution"),
        "dcat:DataService": ("data-service", "DataService"),
        "dcat:Resource": ("data-product-resource", "DataProduct"),
    }
    field_mappings = {
        "dcterms:identifier": ("identifier", "identifier"),
        "dcterms:publisher": ("provider", "provider"),
        "dcterms:rightsHolder": ("data-holder", "dataHolder"),
        "dcat:theme": ("domain", "domain"),
        "dcat:qualityMeasurement": ("data-quality", "dataQuality"),
        "dcterms:license": ("license", "license"),
        "dcterms:accessRights": ("access-rights", "dataAccess"),
        "odrl:hasPolicy": ("policy", "policy"),
        "dcat:accessURL": ("access-method", "accessMethod"),
    }
    objects: List[Dict[str, Any]] = []
    fields: List[Dict[str, str]] = []
    executed: List[str] = []
    unmapped: List[str] = []
    for node in graph:
        if not isinstance(node, dict) or not isinstance(node.get("@id"), str):
            raise ValueError("Every DCAT node requires an @id")
        raw_types = node.get("@type", [])
        types = raw_types if isinstance(raw_types, list) else [raw_types]
        selected_type = next((value for value in types if value in type_mappings), None)
        if selected_type is None:
            unmapped.extend(str(value) for value in types)
            continue
        mapping_id, odpv_type = type_mappings[selected_type]
        if not _allow(mapping_id, selected):
            continue
        properties: Dict[str, Any] = {}
        for external, field in field_mappings.items():
            if external in node and _allow(field[0], selected):
                properties[field[1]] = node[external]
                fields.append(
                    {"mappingId": field[0], "object": node["@id"], "field": external}
                )
                executed.append(field[0])
        objects.append({"id": node["@id"], "type": odpv_type, "properties": properties})
        executed.append(mapping_id)
    return _result(
        output={
            "format": "ODPV-Interchange-1.0",
            "objects": objects,
            "relationships": [],
        },
        executed=executed,
        fields_bound=fields,
        unmapped=sorted(set(unmapped)),
    )


def _prov_export(
    profile: Any, document: Dict[str, Any], selected: Optional[Set[str]]
) -> Dict[str, Any]:
    objects = _object_index(document)
    relationships = _relationships(document)
    object_types = {
        "Dataset": ("dataset", "prov:Entity"),
        "Agent": ("agent", "prov:Agent"),
        "Provider": ("provider", "prov:Agent"),
        "Workflow": ("workflow", "prov:Activity"),
    }
    nodes: List[Dict[str, Any]] = []
    executed: List[str] = []
    for item in objects.values():
        mapping = object_types.get(item["type"])
        if mapping and _allow(mapping[0], selected):
            nodes.append({"id": item["id"], "type": mapping[1]})
            executed.append(mapping[0])
    node_ids = {node["id"] for node in nodes}
    relations: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    relation_map = {
        "uses": ("uses", "prov:used", False),
        "derivedFrom": ("derived-from", "prov:wasDerivedFrom", False),
        "consumes": ("consumes", "prov:used", False),
        "providedBy": ("provided-by", "prov:wasAttributedTo", False),
        "produces": ("produces", "prov:wasGeneratedBy", True),
        "versionOf": ("version-of", "prov:wasRevisionOf", False),
    }
    for item in relationships:
        mapping = relation_map.get(item["type"])
        if not mapping or not _allow(mapping[0], selected):
            continue
        source = objects.get(item["source"])
        target = objects.get(item["target"])
        if (
            source is None
            or target is None
            or source["id"] not in node_ids
            or target["id"] not in node_ids
        ):
            skipped.append(
                {"mappingId": mapping[0], "reason": "requires_prov_bound_endpoints"}
            )
            continue
        if mapping[0] == "consumes" and source["type"] != "Workflow":
            skipped.append(
                {"mappingId": mapping[0], "reason": "consumer_must_be_activity"}
            )
            continue
        if mapping[0] == "provided-by" and target["type"] not in ("Provider", "Agent"):
            skipped.append(
                {"mappingId": mapping[0], "reason": "provider_must_be_agent"}
            )
            continue
        if mapping[0] == "produces" and source["type"] != "Workflow":
            skipped.append(
                {"mappingId": mapping[0], "reason": "producer_must_be_activity"}
            )
            continue
        left, right = (
            (target["id"], source["id"]) if mapping[2] else (source["id"], target["id"])
        )
        relations.append({"subject": left, "predicate": mapping[1], "object": right})
        executed.append(mapping[0])
    return _result(
        output={"entities": nodes, "relations": relations},
        executed=executed,
        skipped=skipped,
    )


def _prov_import(
    profile: Any, document: Dict[str, Any], selected: Optional[Set[str]]
) -> Dict[str, Any]:
    nodes = document.get("entities", [])
    relations = document.get("relations", [])
    if not isinstance(nodes, list) or not isinstance(relations, list):
        raise ValueError("PROV import requires entities and relations arrays")
    type_map = {
        "prov:Entity": ("dataset", "Dataset"),
        "prov:Agent": ("agent", "Agent"),
        "prov:Activity": ("workflow", "Workflow"),
    }
    objects: List[Dict[str, str]] = []
    executed: List[str] = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            raise ValueError("Every PROV node requires an id")
        mapping = type_map.get(node.get("type"))
        if mapping and _allow(mapping[0], selected):
            objects.append({"id": node["id"], "type": mapping[1]})
            executed.append(mapping[0])
    relation_map = {
        "prov:used": ("uses", "uses"),
        "prov:wasDerivedFrom": ("derived-from", "derivedFrom"),
    }
    output_relations: List[Dict[str, str]] = []
    for relation in relations:
        if not isinstance(relation, dict):
            raise ValueError("Every PROV relation must be an object")
        mapping = relation_map.get(relation.get("predicate"))
        if mapping and _allow(mapping[0], selected):
            output_relations.append(
                {
                    "source": relation["subject"],
                    "type": mapping[1],
                    "target": relation["object"],
                }
            )
            executed.append(mapping[0])
    return _result(
        output={
            "format": "ODPV-Interchange-1.0",
            "objects": objects,
            "relationships": output_relations,
        },
        executed=executed,
    )


def _odcs_export(
    profile: Any, document: Dict[str, Any], selected: Optional[Set[str]]
) -> Dict[str, Any]:
    objects = _object_index(document)
    product = next(
        (item for item in objects.values() if item["type"] == "DataProduct"), None
    )
    if product is None:
        return _result(
            output={},
            refused=(
                {"mappingId": "product-details", "reason": "requires_data_product"},
            ),
        )
    properties = product.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError("ODPV object properties must be an object")
    contract: Dict[str, Any] = {
        "apiVersion": "v3.2.0",
        "kind": "DataContract",
        "id": properties.get("identifier", product["id"]),
        "info": properties.get("productDetails", {}),
    }
    mapping_fields = {
        "productDetails": ("product-details", "info"),
        "identifier": ("identifier", "id"),
        "schema": ("schema", "schema"),
        "dataQuality": ("quality", "quality"),
        "retention": ("retention", "slaProperties.retention"),
        "sla": ("service-level", "slaProperties"),
        "owner": ("ownership-and-stewardship", "team"),
        "dataAccess": ("data-access", "servers"),
        "support": ("support", "support"),
        "pricingPlan": ("pricing-plan", "pricing"),
        "license": ("license", "terms.license"),
        "usageRights": ("terms", "terms"),
        "dataAgreement": ("data-agreement", "terms.parties"),
    }
    fields: List[Dict[str, str]] = []
    executed: List[str] = ["contract-document"]
    for key, value in properties.items():
        mapping = mapping_fields.get(key)
        if mapping and _allow(mapping[0], selected):
            _assign(contract, mapping[1], value)
            fields.append(
                {"mappingId": mapping[0], "object": product["id"], "field": mapping[1]}
            )
            executed.append(mapping[0])
    return _result(output=contract, executed=executed, fields_bound=fields)


def _assign(target: Dict[str, Any], dotted: str, value: Any) -> None:
    current = target
    pieces = dotted.split(".")
    for piece in pieces[:-1]:
        child = current.get(piece)
        if not isinstance(child, dict):
            child = {}
            current[piece] = child
        current = child
    existing = current.get(pieces[-1])
    if isinstance(existing, dict) and isinstance(value, dict):
        current[pieces[-1]] = {**existing, **value}
    else:
        current[pieces[-1]] = value


def _openlineage_export(
    profile: Any, document: Dict[str, Any], selected: Optional[Set[str]]
) -> Dict[str, Any]:
    relationships = _relationships(document)
    bindings = _bindings(document, "openlineage")
    jobs = (
        bindings.get("jobs", {}) if isinstance(bindings.get("jobs", {}), dict) else {}
    )
    datasets = (
        bindings.get("datasets", {})
        if isinstance(bindings.get("datasets", {}), dict)
        else {}
    )
    events: List[Dict[str, Any]] = []
    executed: List[str] = []
    refused: List[Dict[str, str]] = []
    declared: List[Dict[str, Any]] = []
    observed: List[Dict[str, Any]] = []
    mapping_ids = {
        "uses": "uses",
        "consumes": "consumes",
        "derivedFrom": "declared-lineage",
        "produces": "production-boundary",
    }
    for relationship in relationships:
        mapping_id = mapping_ids.get(relationship["type"])
        if not mapping_id or not _allow(mapping_id, selected):
            continue
        job_id = relationship.get("job", relationship["source"])
        job = jobs.get(job_id)
        target = datasets.get(relationship["target"])
        if not isinstance(job, dict) or not isinstance(target, dict):
            refused.append(
                {"mappingId": mapping_id, "reason": "requires_job_and_dataset_bindings"}
            )
            continue
        event: Dict[str, Any] = {
            "eventType": "COMPLETE" if mapping_id == "production-boundary" else "START",
            "job": job,
            "inputs": [],
            "outputs": [],
            "facets": {"odpv": {"mappingId": mapping_id}},
        }
        if mapping_id == "production-boundary":
            if relationship.get("state") != "observed":
                refused.append(
                    {
                        "mappingId": mapping_id,
                        "reason": "outputs_require_observed_state",
                    }
                )
                continue
            event["outputs"].append(target)
            observed.append({"mappingId": mapping_id, "relationship": relationship})
        else:
            event["inputs"].append(target)
            declared.append({"mappingId": mapping_id, "relationship": relationship})
        events.append(event)
        executed.append(mapping_id)
    return _result(
        output={"events": events},
        executed=executed,
        refused=refused,
        declared=declared,
        observed=observed,
    )


def _odrl_export(
    profile: Any, document: Dict[str, Any], selected: Optional[Set[str]]
) -> Dict[str, Any]:
    objects = _object_index(document)
    relationships = _relationships(document)
    policies: List[Dict[str, Any]] = []
    executed: List[str] = []
    refused: List[Dict[str, str]] = []
    for relationship in relationships:
        if relationship["type"] != "governedBy" or not _allow("governed-by", selected):
            continue
        asset = objects.get(relationship["source"])
        policy = objects.get(relationship["target"])
        properties = policy.get("properties", {}) if isinstance(policy, dict) else {}
        rules = properties.get("rules") if isinstance(properties, dict) else None
        if (
            asset is None
            or policy is None
            or policy["type"] not in ("Policy", "Agreement")
            or not isinstance(rules, list)
            or not rules
        ):
            refused.append(
                {"mappingId": "governed-by", "reason": "requires_policy_rules"}
            )
            continue
        if any(not isinstance(rule, dict) or not rule.get("action") for rule in rules):
            refused.append(
                {"mappingId": "governed-by", "reason": "every_rule_requires_action"}
            )
            continue
        policies.append(
            {
                "@id": policy["id"],
                "@type": "odrl:Policy",
                "odrl:target": asset["id"],
                "odrl:permission": rules,
            }
        )
        executed.append("governed-by")
    return _result(output={"policies": policies}, executed=executed, refused=refused)


def _odrl_import(
    profile: Any, document: Dict[str, Any], selected: Optional[Set[str]]
) -> Dict[str, Any]:
    policies = document.get("policies")
    if not isinstance(policies, list):
        raise ValueError("ODRL import requires a policies array")
    policy_types = {
        "odrl:Policy": ("policy", "Policy"),
        "odrl:Agreement": ("agreement", "Agreement"),
    }
    objects: List[Dict[str, Any]] = []
    executed: List[str] = []
    unmapped: List[str] = []
    for policy in policies:
        if not isinstance(policy, dict) or not isinstance(policy.get("@id"), str):
            raise ValueError("Every ODRL policy requires an @id")
        mapping = policy_types.get(policy.get("@type"))
        if mapping is None or not _allow(mapping[0], selected):
            unmapped.append(str(policy.get("@type")))
            continue
        objects.append({"id": policy["@id"], "type": mapping[1]})
        executed.append(mapping[0])
        permissions = policy.get("odrl:permission", [])
        if not isinstance(permissions, list):
            raise ValueError("ODRL permissions must be an array")
        if _allow("usage-rights", selected):
            for index, permission in enumerate(permissions):
                if isinstance(permission, dict):
                    objects.append(
                        {
                            "id": "%s#permission-%d" % (policy["@id"], index + 1),
                            "type": "UsageRights",
                            "properties": {"rule": permission},
                        }
                    )
                    executed.append("usage-rights")
    return _result(
        output={
            "format": "ODPV-Interchange-1.0",
            "objects": objects,
            "relationships": [],
        },
        executed=executed,
        unmapped=sorted(set(unmapped)),
    )


def transform_profile_document(
    profile: Any,
    direction: str,
    document: Dict[str, Any],
    selected: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Transform one bounded representation through a profile adapter."""
    if direction not in ("odpvToExternal", "externalToOdpv"):
        raise ValueError("Unsupported transformation direction: %s" % direction)
    if not isinstance(document, dict):
        raise ValueError("source_document must be an object")
    adapters = {
        "ODPV-DCAT-3": (_dcat_export, _dcat_import),
        "ODPV-ODCS-3": (_odcs_export, None),
        "ODPV-OPENLINEAGE-1": (_openlineage_export, None),
        "ODPV-PROV-O": (_prov_export, _prov_import),
        "ODPV-ODRL-2": (_odrl_export, _odrl_import),
    }
    outbound, inbound = adapters[profile.ref.id]
    adapter = outbound if direction == "odpvToExternal" else inbound
    if adapter is None:
        return _result(
            output={},
            refused=(
                {
                    "mappingId": "profile",
                    "reason": "direction_not_supported_by_profile",
                },
            ),
        )
    return adapter(profile, document, selected)
