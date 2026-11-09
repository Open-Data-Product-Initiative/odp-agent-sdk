"""ODPS output normalization for Portfolio-generated products."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from ._portfolio_normalization_constants import (
    ODPS_PRICING_UNIT_ALIASES,
    ODPS_PRICING_UNITS,
    ODPS_STATUS_ALIASES,
    ODPS_STATUSES,
    ODPS_VISIBILITY_ALIASES,
    ODPS_VISIBILITIES,
)
from ._portfolio_values import (
    path_id as _path_id,
    text as _text,
    title_from_text as _title_from_text,
)
from .odps._normalization import (
    ODPS_DATA_QUALITY_DIMENSION_ALIASES,
    ODPS_DATA_QUALITY_DIMENSIONS,
    ODPS_DATA_QUALITY_UNIT_ALIASES,
    ODPS_DATA_QUALITY_UNITS,
    ODPS_SLA_DIMENSION_ALIASES,
    ODPS_SLA_DIMENSIONS,
    ODPS_SLA_UNIT_ALIASES,
    ODPS_SLA_UNITS,
    hours_to_minutes,
)


def normalize_odps_product(value: Any) -> None:
    if not isinstance(value, dict):
        return
    product = value.get("product")
    if isinstance(product, dict):
        _normalize_odps_generated_sections(product)
        _normalize_odps_pricing_plans(product)
        _normalize_odps_data_access(product, _is_odps_v42(value))
        _normalize_odps_license(product.get("license"))
    details = _odps_details_mapping(value)
    if details is None:
        return
    details["status"] = _normalize_enum(
        details.get("status"), ODPS_STATUSES, ODPS_STATUS_ALIASES, "draft"
    )
    details["visibility"] = _normalize_enum(
        details.get("visibility"),
        ODPS_VISIBILITIES,
        ODPS_VISIBILITY_ALIASES,
        "private",
    )


def normalize_generated_odps_product(value: Any) -> None:
    """Normalize generated portfolio products to the supported ODPS version."""
    if not isinstance(value, dict):
        return
    value["schema"] = "https://opendataproducts.org/v4.2/schema/odps.json"
    value["version"] = "4.2"
    normalize_odps_product(value)


def _odps_details_mapping(value: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    product = value.get("product")
    if not isinstance(product, dict):
        return None
    details = product.get("details")
    if isinstance(details, dict):
        english = details.get("en")
        if isinstance(english, dict):
            return english
    return product if isinstance(product, dict) else None


def _normalize_odps_generated_sections(product: Dict[str, Any]) -> None:
    data_ops = product.pop("dataOps", None)
    if data_ops is not None:
        data_ops = _normalize_loose_data_ops(data_ops)
        if data_ops is not None:
            product["x-dataOps"] = data_ops

    details = product.get("details")
    detail_sla = None
    if isinstance(details, dict):
        english = details.get("en")
        if isinstance(english, dict):
            _normalize_odps_detail_use_cases(english)
            detail_sla = english.pop("SLA", None)

    sla = product.get("SLA")
    if isinstance(sla, list):
        normalized_sla = _normalize_sla_list(sla)
        if isinstance(detail_sla, dict):
            _merge_sla_dimensions(normalized_sla, _sla_from_loose_details(detail_sla))
        if isinstance(data_ops, dict):
            _merge_sla_dimensions(
                normalized_sla, _sla_from_data_ops_update_frequency(data_ops)
            )
        product["SLA"] = normalized_sla
    elif isinstance(sla, dict):
        normalized_sla = _normalize_loose_sla(sla)
        if isinstance(detail_sla, dict):
            _merge_sla_dimensions(normalized_sla, _sla_from_loose_details(detail_sla))
        if isinstance(data_ops, dict):
            _merge_sla_dimensions(
                normalized_sla, _sla_from_data_ops_update_frequency(data_ops)
            )
        product["SLA"] = normalized_sla
    elif isinstance(detail_sla, dict):
        product["SLA"] = _sla_from_loose_details(detail_sla)
        if isinstance(data_ops, dict):
            _merge_sla_dimensions(
                product["SLA"], _sla_from_data_ops_update_frequency(data_ops)
            )
    elif isinstance(data_ops, dict):
        data_ops_sla = _sla_from_data_ops_update_frequency(data_ops)
        if _first_named_profile(data_ops_sla.get("declarative")) is not None:
            product["SLA"] = data_ops_sla

    data_quality = product.get("dataQuality")
    if isinstance(data_quality, list):
        product["dataQuality"] = _normalize_data_quality_list(data_quality)
    elif isinstance(data_quality, dict):
        product["dataQuality"] = _normalize_loose_data_quality(data_quality)


def _normalize_loose_data_ops(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, list):
        merged: Dict[str, Any] = {}
        for item in value:
            if isinstance(item, dict):
                merged.update(item)
        value = merged
    if not isinstance(value, dict):
        return None
    normalized = dict(value)
    for key in ("infrastructure", "format", "dataQuality", "updateFrequency"):
        item = normalized.get(key)
        if isinstance(item, list):
            first = next((entry for entry in item if isinstance(entry, dict)), None)
            if first is not None:
                normalized[key] = first
    return normalized


def _normalize_odps_detail_use_cases(details: Dict[str, Any]) -> None:
    use_cases = details.get("useCases")
    if isinstance(use_cases, str):
        text = use_cases.strip()
        details["useCases"] = (
            [{"useCase": {"useCaseTitle": text, "useCaseDescription": text}}]
            if text
            else []
        )
        return
    if isinstance(use_cases, list):
        normalized = []
        for item in use_cases:
            if isinstance(item, str) and item.strip():
                normalized.append(
                    {
                        "useCase": {
                            "useCaseTitle": item.strip(),
                            "useCaseDescription": item.strip(),
                        }
                    }
                )
            elif isinstance(item, dict):
                normalized.append(item)
        details["useCases"] = normalized


def _normalize_odps_license(license_data: Any) -> None:
    if not isinstance(license_data, dict):
        return
    scope = license_data.get("scope")
    if isinstance(scope, dict):
        _truncate_mapping_strings(
            scope,
            {
                "definition": 512,
                "restrictions": 255,
            },
        )
    termination = license_data.get("termination")
    if isinstance(termination, dict):
        _truncate_mapping_strings(
            termination,
            {
                "terminationConditions": 512,
                "continuityConditions": 512,
            },
        )
    governance = license_data.get("governance")
    if isinstance(governance, dict):
        _truncate_mapping_strings(
            governance,
            {
                "ownership": 512,
                "audit": 512,
                "warranties": 512,
                "damages": 512,
                "confidentiality": 512,
                "applicableLaws": 512,
                "forceMajeure": 512,
            },
        )


def _truncate_mapping_strings(mapping: Dict[str, Any], limits: Dict[str, int]) -> None:
    for key, limit in limits.items():
        value = mapping.get(key)
        if isinstance(value, str) and len(value) > limit:
            mapping[key] = _truncate_text(value, limit)


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3].rstrip() + "..."


def _normalize_loose_sla(sla: Dict[str, Any]) -> Dict[str, Any]:
    declarative = sla.get("declarative")
    if isinstance(declarative, dict):
        normalized = {"declarative": {}}
        for key, profile in declarative.items():
            normalized["declarative"][_path_id(str(key)) or "default"] = (
                _normalize_sla_profile(profile, str(key))
            )
        return normalized
    if isinstance(declarative, list):
        return {"declarative": _named_profiles_from_list(declarative, "default")}
    description = _text(sla.get("description"))
    normalized = _sla_from_loose_details(sla)
    profile = normalized["declarative"]["default"]
    if description:
        profile["description"] = {"en": description}
    return normalized


def _normalize_sla_list(items: List[Any]) -> Dict[str, Any]:
    profiles = [
        profile
        for item in items
        if isinstance(item, dict)
        for profile in [_sla_profile_from_loose_mapping(item)]
        if profile is not None
    ]
    if not profiles:
        profiles = [{"name": {"en": "Default SLA"}, "dimensions": []}]
    return {"declarative": _named_profiles_from_list(profiles, "default")}


def _normalize_sla_profile(value: Any, fallback_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "name": {"en": _title_from_text(_text(value) or fallback_name or "SLA")},
            "dimensions": [],
        }
    if isinstance(value.get("dimensions"), list):
        profile = dict(value)
        profile["dimensions"] = [
            _normalize_sla_dimension(dimension)
            for dimension in value["dimensions"]
            if isinstance(dimension, dict)
        ]
        if not isinstance(profile.get("name"), dict):
            profile["name"] = {
                "en": _text(profile.get("name"), _title_from_text(fallback_name))
            }
        return profile
    profile = _sla_profile_from_loose_mapping(value)
    if profile is None:
        return {"name": {"en": _title_from_text(fallback_name)}, "dimensions": []}
    return profile


def _named_profiles_from_list(
    profiles: List[Dict[str, Any]], first_key: str
) -> Dict[str, Dict[str, Any]]:
    named: Dict[str, Dict[str, Any]] = {}
    for index, profile in enumerate(profiles):
        key = first_key if index == 0 else _profile_key(profile, index)
        while key in named:
            key = f"{key}-{index + 1}"
        named[key] = profile
    return named


def _profile_key(profile: Dict[str, Any], index: int) -> str:
    name = _text(profile.get("id") or profile.get("key"))
    if not name:
        name = _text(profile.get("name"))
    normalized = _path_id(name)
    if normalized in {"", "default-sla", "default-data-quality"}:
        return f"profile-{index + 1}"
    if "premium" in normalized:
        return "premium"
    return normalized or f"profile-{index + 1}"


def _sla_profile_from_loose_mapping(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if isinstance(item.get("dimensions"), list):
        profile = dict(item)
        profile["dimensions"] = [
            _normalize_sla_dimension(dimension)
            for dimension in item["dimensions"]
            if isinstance(dimension, dict)
        ]
        if not isinstance(profile.get("name"), dict):
            profile["name"] = {"en": _text(profile.get("name"), "Default SLA")}
        return profile

    language, content = _language_content(item)
    source = content if isinstance(content, dict) else item
    description = _text(source.get("description"))
    profile: Dict[str, Any] = {
        "name": {"en": _text(source.get("name"), "Default SLA")},
        "dimensions": _sla_dimensions_from_loose_mapping(source),
    }
    if description:
        profile["description"] = {language: description}
    return profile


def _language_content(item: Dict[str, Any]) -> Tuple[str, Any]:
    for key, value in item.items():
        if isinstance(key, str) and len(key) == 2 and isinstance(value, dict):
            return key, value
    return "en", item


def _sla_dimensions_from_loose_mapping(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    dimensions = []
    for key, value in item.items():
        if key in {"name", "description", "dimensions"}:
            continue
        dimension = key
        if key == "availability":
            dimension = "uptime"
        if dimension not in ODPS_SLA_DIMENSIONS:
            continue
        objective = _text(value)
        if objective:
            dimensions.append(
                {
                    "dimension": dimension,
                    "objective": objective,
                    "unit": "null",
                }
            )
    if not dimensions and _text(item.get("objective")):
        dimensions.append(
            {
                "dimension": "updateFrequency",
                "objective": _text(item.get("objective")),
                "unit": "null",
            }
        )
    return dimensions


def _normalize_sla_dimension(dimension: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(dimension)
    raw_dimension = _text(normalized.get("dimension") or normalized.get("name"))
    raw_unit = _text(normalized.get("unit"))
    normalized["dimension"] = _normalize_enum(
        raw_dimension,
        ODPS_SLA_DIMENSIONS,
        ODPS_SLA_DIMENSION_ALIASES,
        "updateFrequency",
    )
    if "objective" not in normalized:
        normalized["objective"] = _text(normalized.get("target"), "pending")
    if raw_unit.casefold() in {"hour", "hours"}:
        normalized["objective"] = hours_to_minutes(normalized.get("objective"))
    if not _text(normalized.get("unit")):
        normalized["unit"] = "null"
    else:
        normalized["unit"] = _normalize_enum(
            normalized.get("unit"), ODPS_SLA_UNITS, ODPS_SLA_UNIT_ALIASES, "null"
        )
    return normalized


def _sla_from_data_ops_update_frequency(data_ops: Dict[str, Any]) -> Dict[str, Any]:
    update_frequency = data_ops.get("updateFrequency")
    if not isinstance(update_frequency, dict):
        return {"declarative": []}
    objective = update_frequency.get("value")
    unit = _normalize_enum(
        update_frequency.get("unit"), ODPS_SLA_UNITS, ODPS_SLA_UNIT_ALIASES, "days"
    )
    if objective is None or objective == "":
        return {"declarative": []}
    return {
        "declarative": {
            "default": {
                "name": {"en": "Default SLA"},
                "dimensions": [
                    {
                        "dimension": "updateFrequency",
                        "objective": objective,
                        "unit": unit,
                    }
                ],
            }
        }
    }


def _merge_sla_dimensions(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    target_profile = _first_named_profile(target.get("declarative"))
    source_profile = _first_named_profile(source.get("declarative"))
    if target_profile is None or source_profile is None:
        return
    target_dimensions = target_profile.setdefault("dimensions", [])
    if not isinstance(target_dimensions, list):
        target_profile["dimensions"] = []
        target_dimensions = target_profile["dimensions"]
    existing = {
        _text(item.get("dimension"))
        for item in target_dimensions
        if isinstance(item, dict)
    }
    for item in source_profile.get("dimensions", []):
        if not isinstance(item, dict):
            continue
        dimension = _text(item.get("dimension"))
        if dimension and dimension not in existing:
            target_dimensions.append(item)
            existing.add(dimension)


def _first_named_profile(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        for profile in value.values():
            if isinstance(profile, dict):
                return profile
    if isinstance(value, list):
        for profile in value:
            if isinstance(profile, dict):
                return profile
    return None


def _normalize_loose_data_quality(data_quality: Dict[str, Any]) -> Dict[str, Any]:
    declarative = data_quality.get("declarative")
    if isinstance(declarative, dict):
        normalized = {"declarative": {}}
        for key, profile in declarative.items():
            if isinstance(profile, dict):
                normalized["declarative"][_path_id(str(key)) or "default"] = (
                    _normalize_data_quality_profile(profile)
                )
        return normalized
    if isinstance(declarative, list):
        return {
            "declarative": _named_profiles_from_list(
                [_normalize_data_quality_profile(item) for item in declarative],
                "default",
            )
        }
    description = _text(data_quality.get("policyDescription"))
    if not description:
        description = _text(data_quality.get("description"))
    return {
        "declarative": {
            "default": {
                "dimensions": [
                    {
                        "dimension": "validity",
                        "objective": 0,
                        "unit": "percentage",
                        "description": description or "Data quality policy pending.",
                    }
                ]
            }
        }
    }


def _normalize_data_quality_list(items: List[Any]) -> Dict[str, Any]:
    profiles = []
    for item in items:
        if not isinstance(item, dict):
            continue
        language, content = _language_content(item)
        source = content if isinstance(content, dict) else item
        description = _text(source.get("description"))
        profiles.append(
            {
                "description": description or "Data quality policy pending.",
                "dimensions": [
                    {
                        "dimension": "validity",
                        "objective": 0,
                        "unit": "percentage",
                        "description": description
                        or f"Data quality policy pending ({language}).",
                    }
                ],
            }
        )
    return {
        "declarative": (
            _named_profiles_from_list(profiles, "default") if profiles else {}
        )
    }


def _normalize_data_quality_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(profile)
    dimensions = normalized.get("dimensions")
    if isinstance(dimensions, list):
        normalized["dimensions"] = [
            dimension
            for dimension in (
                _normalize_data_quality_dimension(dimension)
                for dimension in dimensions
                if isinstance(dimension, dict)
            )
            if dimension
        ]
    return normalized


def _normalize_data_quality_dimension(dimension: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(dimension)
    normalized["dimension"] = _normalize_enum(
        normalized.get("dimension") or normalized.get("name"),
        ODPS_DATA_QUALITY_DIMENSIONS,
        ODPS_DATA_QUALITY_DIMENSION_ALIASES,
        "validity",
    )
    if "objective" in normalized:
        normalized["objective"] = _normalize_integer_value(normalized["objective"])
    if "unit" in normalized:
        normalized["unit"] = _normalize_enum(
            normalized.get("unit"),
            ODPS_DATA_QUALITY_UNITS,
            ODPS_DATA_QUALITY_UNIT_ALIASES,
            "percentage",
        )
    return normalized


def _normalize_integer_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    text = _text(value)
    if text.isdigit():
        return int(text)
    return value


def _sla_from_loose_details(sla: Dict[str, Any]) -> Dict[str, Any]:
    dimensions = []
    update_frequency = _text(sla.get("updateFrequency"))
    if update_frequency:
        dimensions.append(
            {
                "dimension": "updateFrequency",
                "objective": update_frequency,
                "unit": "days",
            }
        )
    for key, value in sla.items():
        if key == "updateFrequency":
            continue
        objective = _text(value)
        if objective and key in ODPS_SLA_DIMENSIONS:
            dimensions.append(
                {"dimension": key, "objective": objective, "unit": "null"}
            )
    return {
        "declarative": {
            "default": {
                "name": {"en": "Default SLA"},
                "dimensions": dimensions,
            }
        }
    }


def _normalize_odps_pricing_plans(product: Dict[str, Any]) -> None:
    legacy_pricing = product.pop("pricing", None)
    if "pricingPlans" not in product and legacy_pricing is not None:
        product["pricingPlans"] = legacy_pricing

    pricing = product.get("pricingPlans")
    if isinstance(pricing, list):
        product["pricingPlans"] = {"declarative": _pricing_language_map(pricing)}
        return
    if not isinstance(pricing, dict):
        return
    plans = pricing.pop("plans", None)
    if isinstance(plans, list):
        declarative = pricing.setdefault("declarative", {})
        if isinstance(declarative, dict):
            existing = declarative.get("en")
            normalized_plans = [
                _normalize_portfolio_pricing_plan(plan)
                for plan in plans
                if isinstance(plan, dict)
            ]
            if isinstance(existing, list):
                declarative["en"] = existing + normalized_plans
            else:
                declarative["en"] = normalized_plans
    declarative = pricing.get("declarative")
    if isinstance(declarative, dict):
        for language, plans_for_language in list(declarative.items()):
            if isinstance(plans_for_language, list):
                declarative[language] = [
                    _normalize_portfolio_pricing_plan(plan)
                    for plan in plans_for_language
                    if isinstance(plan, dict)
                ]


def _is_odps_v42(document: Dict[str, Any]) -> bool:
    """Return whether a portfolio product explicitly targets ODPS v4.2."""
    schema = _text(document.get("schema")).lower()
    version = _text(document.get("version")).lower()
    return version in {"4.2", "v4.2"} or "/v4.2/" in schema


def _normalize_odps_data_access(product: Dict[str, Any], v42: bool) -> None:
    data_access = product.get("dataAccess")
    if isinstance(data_access, list):
        named_items = [
            (
                _data_access_key(item, None),
                _normalize_odps_data_access_item(item),
            )
            for item in data_access
            if isinstance(item, dict)
        ]
        if named_items:
            product["dataAccess"] = _named_data_access_items(named_items, v42, product)
        return

    if not isinstance(data_access, dict):
        return

    if _looks_like_data_access_method(data_access):
        product["dataAccess"] = _named_data_access_items(
            [
                (
                    _data_access_key(data_access, None),
                    _normalize_odps_data_access_item(data_access),
                )
            ],
            v42,
            product,
        )
        return

    items = []
    for key, value in list(data_access.items()):
        if key == "$ref" or not isinstance(value, dict):
            continue
        if v42 and set(value) == {"$ref"}:
            items.append((key, value))
            continue
        method = _normalize_odps_data_access_item(value, method_name=key)
        items.append((_data_access_key(method, key), method))

    if items:
        product["dataAccess"] = _named_data_access_items(items, v42, product)


def _named_data_access_items(
    items: List[Tuple[str, Dict[str, Any]]], v42: bool, product: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """Return named access profiles, adding v4.2's required default profile."""
    named = _unique_named_items(items)
    if not v42 or "default" in named or not named:
        return named
    first_name = next(iter(named))
    primary = named[first_name]
    named = {
        "default": primary,
        **{key: value for key, value in named.items() if key != first_name},
    }
    _rewrite_data_access_references(product, first_name, "default")
    return named


def _rewrite_data_access_references(value: Any, old_name: str, new_name: str) -> None:
    """Update internal profile pointers after normalizing the primary profile."""
    old_ref = "#/product/dataAccess/{0}".format(old_name)
    new_ref = "#/product/dataAccess/{0}".format(new_name)
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and item == old_ref:
                value[key] = new_ref
            else:
                _rewrite_data_access_references(item, old_name, new_name)
    elif isinstance(value, list):
        for item in value:
            _rewrite_data_access_references(item, old_name, new_name)


def _unique_named_items(
    items: List[Tuple[str, Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    named: Dict[str, Dict[str, Any]] = {}
    for index, (key, value) in enumerate(items, start=1):
        candidate = key or f"item{index}"
        while candidate in named:
            candidate = f"{key}-{index}"
        named[candidate] = value
    return named


def _data_access_key(item: Dict[str, Any], fallback: Optional[str]) -> str:
    output_port_type = _text(item.get("outputPortType") or item.get("outputPorttype"))
    name = _text(item.get("name"))
    key = output_port_type or name or _text(fallback) or "API"
    if key.casefold() == "api":
        return "API"
    return _path_id(key)


def _looks_like_data_access_method(value: Dict[str, Any]) -> bool:
    method_keys = {
        "name",
        "description",
        "outputPorttype",
        "outputPortType",
        "format",
        "accessURL",
        "authenticationMethod",
        "specsURL",
        "documentationURL",
        "specification",
        "version",
        "reference",
        "accessInstructions",
    }
    return any(key in value for key in method_keys)


def _normalize_odps_data_access_item(
    item: Dict[str, Any], method_name: Optional[str] = None
) -> Dict[str, Any]:
    normalized = dict(item)
    legacy_output_port_type = normalized.pop("outputPorttype", None)
    output_port_type = normalized.get("outputPortType")
    if output_port_type is None:
        normalized["outputPortType"] = (
            _text(legacy_output_port_type)
            or _infer_output_port_type(method_name)
            or "API"
        )
    elif legacy_output_port_type is not None:
        normalized["outputPortType"] = _text(output_port_type) or _text(
            legacy_output_port_type
        )
    return normalized


def _infer_output_port_type(method_name: Optional[str]) -> Optional[str]:
    if not method_name:
        return None
    lowered = method_name.casefold()
    if "file" in lowered or "download" in lowered:
        return "file"
    if "database" in lowered or "sql" in lowered or "query" in lowered:
        return "database"
    if "stream" in lowered:
        return "stream"
    if "webhook" in lowered:
        return "webhook"
    if "ai" in lowered or "agent" in lowered or "mcp" in lowered:
        return "AI"
    if "api" in lowered:
        return "API"
    return None


def _pricing_language_map(plans: List[Any]) -> Dict[str, List[Dict[str, Any]]]:
    language_map: Dict[str, List[Dict[str, Any]]] = {}
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        language_keys = {
            key: value
            for key, value in plan.items()
            if isinstance(key, str) and isinstance(value, dict) and len(key) == 2
        }
        if language_keys:
            for language, value in language_keys.items():
                language_map.setdefault(language, []).append(
                    _normalize_portfolio_pricing_plan(value)
                )
        else:
            language_map.setdefault("en", []).append(
                _normalize_portfolio_pricing_plan(plan)
            )
    return language_map or {"en": []}


def _normalize_portfolio_pricing_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(plan)
    plan_name = normalized.pop("plan", None)
    if "price" not in normalized and "priceAmount" in normalized:
        normalized["price"] = normalized.pop("priceAmount")
    else:
        normalized.pop("priceAmount", None)
    if "name" not in normalized and "pricingPlanName" in normalized:
        normalized["name"] = normalized.pop("pricingPlanName")
    if "name" not in normalized and plan_name is not None:
        normalized["name"] = plan_name
    elif _text(normalized.get("name")) == "On-request" and plan_name is not None:
        normalized["name"] = plan_name
    if "description" not in normalized and "license" in normalized:
        normalized["description"] = normalized.pop("license")
    for key in ("name", "description"):
        value = normalized.get(key)
        if isinstance(value, dict):
            normalized[key] = _text(value)
    if not _text(normalized.get("name")):
        normalized["name"] = "On-request"
    if not _text(normalized.get("priceCurrency")):
        normalized["priceCurrency"] = "XXX"
    if not _text(normalized.get("price")):
        normalized["price"] = "0"
    if not _text(normalized.get("billingDuration")):
        normalized["billingDuration"] = "month"
    unit = _text(normalized.get("unit"))
    normalized["unit"] = _normalize_enum(
        unit,
        ODPS_PRICING_UNITS,
        ODPS_PRICING_UNIT_ALIASES,
        "On-request",
    )
    normalized["price"] = str(normalized["price"])
    return normalized


def _normalize_enum(
    value: Any,
    allowed: Iterable[str],
    aliases: Dict[str, str],
    default: str,
) -> str:
    text = _text(value)
    if text in allowed:
        return text
    lowered = text.casefold().strip()
    if lowered in aliases:
        return aliases[lowered]
    for candidate in allowed:
        if candidate.casefold() == lowered:
            return candidate
    return default
