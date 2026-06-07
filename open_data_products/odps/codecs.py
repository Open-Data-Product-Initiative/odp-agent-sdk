"""Parsing and serialization helpers for ODPS component models."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, cast

from .models import (
    DataAccess,
    DataAccessMethod,
    DataContract,
    DataHolder,
    DataQuality,
    DataQualityDimension,
    DataQualityProfile,
    KPI,
    License,
    PaymentGateway,
    PaymentGateways,
    PricingPlan,
    PricingPlans,
    ProductDetails,
    ProductStrategy,
    SLA,
    SLADimension,
    SLAProfile,
    SpecificationExtensions,
    UseCase,
)

PRODUCT_DETAILS_MAPPING = {
    "product_id": "productID",
    "value_proposition": "valueProposition",
    "logo_url": "logoURL",
    "product_series": "productSeries",
    "product_version": "productVersion",
    "version_notes": "versionNotes",
    "content_sample": "contentSample",
    "brand_slogan": "brandSlogan",
    "use_cases": "useCases",
    "recommended_data_products": "recommendedDataProducts",
    "output_file_formats": "outputFileFormats",
}

DATA_CONTRACT_MAPPING = {
    "contract_version": "contractVersion",
    "contract_url": "contractURL",
    "dollar_ref": "$ref",
}

PRODUCT_STRATEGY_MAPPING = {
    "contributes_to_kpi": "contributesToKPI",
    "product_kpis": "productKPIs",
    "related_kpis": "relatedKPIs",
    "strategic_alignment": "strategicAlignment",
}

LICENSE_MAPPING = {
    "scope_of_use": "scopeOfUse",
    "geographical_area": "geographicalArea",
    "right_to_sublicense": "rightToSublicense",
    "right_to_modify": "rightToModify",
    "valid_from": "validFrom",
    "valid_until": "validUntil",
    "license_grant": "licenseGrant",
    "license_name": "licenseName",
    "license_url": "licenseURL",
    "scope_details": "scopeDetails",
    "termination_conditions": "terminationConditions",
    "governance_specifics": "governanceSpecifics",
    "audit_terms": "auditTerms",
    "confidentiality_clauses": "confidentialityClauses",
}

DATA_HOLDER_MAPPING = {
    "phone_number": "phoneNumber",
    "business_identifiers": "businessIdentifiers",
    "contact_person": "contactPerson",
    "contact_phone": "contactPhone",
    "contact_email": "contactEmail",
    "address_street": "addressStreet",
    "address_city": "addressCity",
    "address_state": "addressState",
    "address_postal_code": "addressPostalCode",
    "address_country": "addressCountry",
    "organizational_description": "organizationalDescription",
}

PRICING_PLAN_MAPPING = {
    "price_currency": "priceCurrency",
    "billing_duration": "billingDuration",
    "max_transactions_per_second": "maxTransactionsPerSecond",
    "max_transactions_per_month": "maxTransactionsPerMonth",
    "min_price": "minPrice",
    "max_price": "maxPrice",
    "value_added_tax": "valueAddedTax",
    "valid_from": "validFrom",
    "valid_to": "validTo",
    "additional_pricing_details": "additionalPricingDetails",
    "quality_profile_reference": "qualityProfileReference",
    "sla_profile_reference": "slaProfileReference",
    "access_profile_reference": "accessProfileReference",
}

DATA_ACCESS_MAPPING = {
    "output_port_type": "outputPortType",
    "access_url": "accessURL",
    "authentication_method": "authenticationMethod",
    "specs_url": "specsURL",
    "documentation_url": "documentationURL",
    "dollar_ref": "$ref",
}

PAYMENT_GATEWAY_MAPPING = {
    "executable_specifications": "executableSpecifications",
    "dollar_ref": "$ref",
}

SLA_PROFILE_MAPPING = {
    "monitoring_specification": "monitoring_specification",
    "support_contact": "support_contact",
    "support_phone": "support_phone",
    "support_email": "support_email",
    "service_hours": "service_hours",
    "documentation_url": "documentation_url",
    "dollar_ref": "$ref",
}

DATA_QUALITY_DIMENSION_MAPPING = {
    "display_title": "display_title",
}

DATA_QUALITY_PROFILE_MAPPING = {
    "quality_checks": "quality_checks",
    "dollar_ref": "$ref",
}

COLLECTION_REF_MAPPING = {
    "dollar_ref": "$ref",
}


def convert_snake_to_camel(data_dict: Dict[str, Any], mapping: Dict[str, str]) -> None:
    """Convert keys in ``data_dict`` in place using ``mapping``."""
    for snake_key, camel_key in mapping.items():
        if snake_key in data_dict:
            data_dict[camel_key] = data_dict.pop(snake_key)


def clean_none(value: Any) -> Any:
    """Remove ``None`` values recursively from dictionaries and lists."""
    if isinstance(value, dict):
        return {
            key: clean_none(item) for key, item in value.items() if item is not None
        }
    if isinstance(value, list):
        return [clean_none(item) for item in value]
    return value


def _preferred_language_block(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return the English language block or the first available block."""
    english = data.get("en")
    if isinstance(english, dict):
        return cast(Dict[str, Any], english)
    for value in data.values():
        if isinstance(value, dict):
            return cast(Dict[str, Any], value)
    return {}


def _language_plan_map(data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Return language-keyed pricing plans from canonical ODPS data."""
    return {
        language: plans
        for language, plans in data.items()
        if isinstance(language, str) and isinstance(plans, list)
    }


def parse_kpi(data: Dict[str, Any]) -> KPI:
    """Parse a KPI object from ODPS dictionary data."""
    return KPI(
        name=data.get("name", ""),
        id=data.get("id"),
        description=data.get("description"),
        unit=data.get("unit"),
        target=data.get("target"),
        direction=data.get("direction"),
        timeframe=data.get("timeframe"),
        frequency=data.get("frequency"),
        owner=data.get("owner"),
        calculation=data.get("calculation"),
    )


def parse_product_details(product_data: Dict[str, Any]) -> ProductDetails:
    """Parse required product details from the ODPS product section."""
    if isinstance(product_data.get("details"), dict):
        product_data = _preferred_language_block(product_data["details"])

    use_cases = [
        UseCase(
            title=use_case_data.get("title", ""),
            description=use_case_data.get("description", ""),
            url=use_case_data.get("url"),
        )
        for use_case_data in product_data.get("useCases", [])
    ]

    return ProductDetails(
        name=product_data.get("name", ""),
        product_id=product_data.get("productID", ""),
        visibility=product_data.get("visibility", ""),
        status=product_data.get("status", ""),
        type=product_data.get("type", ""),
        value_proposition=product_data.get("valueProposition"),
        description=product_data.get("description"),
        categories=product_data.get("categories", []),
        tags=product_data.get("tags", []),
        brand=product_data.get("brand"),
        keywords=product_data.get("keywords", []),
        themes=product_data.get("themes", []),
        geography=product_data.get("geography"),
        language=product_data.get("language", []),
        homepage=product_data.get("homepage"),
        logo_url=product_data.get("logoURL"),
        created=product_data.get("created"),
        updated=product_data.get("updated"),
        product_series=product_data.get("productSeries"),
        standards=product_data.get("standards", []),
        product_version=product_data.get("productVersion"),
        version_notes=product_data.get("versionNotes"),
        issues=product_data.get("issues"),
        content_sample=product_data.get("contentSample"),
        brand_slogan=product_data.get("brandSlogan"),
        use_cases=use_cases,
        recommended_data_products=product_data.get("recommendedDataProducts", []),
        output_file_formats=product_data.get("outputFileFormats", []),
    )


def parse_product_strategy(data: Dict[str, Any]) -> ProductStrategy:
    """Parse product strategy and nested KPI values."""
    contributes_to_kpi = None
    if "contributesToKPI" in data:
        contributes_to_kpi = parse_kpi(data["contributesToKPI"])

    return ProductStrategy(
        objectives=data.get("objectives", []),
        contributes_to_kpi=contributes_to_kpi,
        product_kpis=[parse_kpi(kpi) for kpi in data.get("productKPIs", [])],
        related_kpis=[parse_kpi(kpi) for kpi in data.get("relatedKPIs", [])],
        strategic_alignment=data.get("strategicAlignment", []),
    )


def parse_data_holder(data: Dict[str, Any]) -> DataHolder:
    """Parse data holder details."""
    return DataHolder(
        name=data.get("name", ""),
        email=data.get("email", ""),
        url=data.get("url"),
        phone_number=data.get("phoneNumber"),
        address=data.get("address"),
        business_identifiers=data.get("businessIdentifiers", []),
        contact_person=data.get("contactPerson"),
        contact_phone=data.get("contactPhone"),
        contact_email=data.get("contactEmail"),
        address_street=data.get("addressStreet"),
        address_city=data.get("addressCity"),
        address_state=data.get("addressState"),
        address_postal_code=data.get("addressPostalCode"),
        address_country=data.get("addressCountry"),
        ratings=data.get("ratings"),
        organizational_description=data.get("organizationalDescription"),
    )


def parse_pricing_plan(data: Dict[str, Any]) -> PricingPlan:
    """Parse a pricing plan."""
    return PricingPlan(
        name=data.get("name", ""),
        price_currency=data.get("priceCurrency", ""),
        price=data.get("price"),
        billing_duration=data.get("billingDuration"),
        unit=data.get("unit"),
        max_transactions_per_second=data.get("maxTransactionsPerSecond"),
        max_transactions_per_month=data.get("maxTransactionsPerMonth"),
        min_price=data.get("minPrice"),
        max_price=data.get("maxPrice"),
        value_added_tax=data.get("valueAddedTax"),
        valid_from=data.get("validFrom"),
        valid_to=data.get("validTo"),
        additional_pricing_details=data.get("additionalPricingDetails"),
        quality_profile_reference=data.get("qualityProfileReference"),
        sla_profile_reference=data.get("slaProfileReference"),
        access_profile_reference=data.get("accessProfileReference"),
    )


def parse_pricing_plans(data: Dict[str, Any]) -> PricingPlans:
    """Parse pricing plans."""
    declarative_plans = _language_plan_map(data.get("declarative", {}))
    language_specific_plans = {
        language: [parse_pricing_plan(plan) for plan in plans]
        for language, plans in data.get("languageSpecificPlans", {}).items()
    }
    language_specific_plans.update(
        {
            language: [parse_pricing_plan(plan) for plan in plans]
            for language, plans in declarative_plans.items()
        }
    )

    return PricingPlans(
        plans=[
            parse_pricing_plan(plan)
            for plan in data.get("plans", [])
            + [plan for plans in declarative_plans.values() for plan in plans]
        ],
        language_specific_plans=language_specific_plans,
    )


def parse_data_contract(data: Dict[str, Any]) -> DataContract:
    """Parse a data contract."""
    return DataContract(
        id=data.get("id"),
        type=data.get("type"),
        contract_version=data.get("contractVersion"),
        contract_url=data.get("contractURL"),
        spec=data.get("spec"),
        ref=data.get("ref"),
        dollar_ref=data.get("$ref"),
    )


def parse_sla_dimension(data: Dict[str, Any]) -> SLADimension:
    """Parse an SLA dimension."""
    return SLADimension(
        name=data.get("name") or data.get("dimension", ""),
        objective=data.get("objective", ""),
        unit=data.get("unit"),
        display_title=data.get("displayTitle")
        or data.get("displaytitle")
        or data.get("display_title"),
        description=data.get("description"),
        weight=data.get("weight"),
    )


def parse_sla_profile(data: Dict[str, Any]) -> SLAProfile:
    """Parse an SLA profile."""
    return SLAProfile(
        dimensions=[
            parse_sla_dimension(dimension) for dimension in data.get("dimensions", [])
        ],
        monitoring_specification=data.get("monitoring_specification"),
        support_contact=data.get("support_contact"),
        support_phone=data.get("support_phone"),
        support_email=data.get("support_email"),
        service_hours=data.get("service_hours"),
        documentation_url=data.get("documentation_url"),
        dollar_ref=data.get("$ref"),
    )


def parse_sla(data: Dict[str, Any]) -> SLA:
    """Parse SLA data."""
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        declarative = data.get("declarative", {})
        if isinstance(declarative, dict):
            profiles = declarative
        else:
            profiles = {
                f"declarative{index}": profile
                for index, profile in enumerate(declarative, start=1)
                if isinstance(profile, dict)
            }
    return SLA(
        profiles={
            name: parse_sla_profile(profile) for name, profile in profiles.items()
        },
        dollar_ref=data.get("$ref"),
    )


def parse_data_quality_dimension(data: Dict[str, Any]) -> DataQualityDimension:
    """Parse a data quality dimension."""
    return DataQualityDimension(
        name=data.get("name") or data.get("dimension", ""),
        objective=data.get("objective", ""),
        unit=data.get("unit"),
        display_title=data.get("displayTitle") or data.get("display_title"),
        description=data.get("description"),
    )


def parse_data_quality_profile(data: Dict[str, Any]) -> DataQualityProfile:
    """Parse a data quality profile."""
    return DataQualityProfile(
        dimensions=[
            parse_data_quality_dimension(dimension)
            for dimension in data.get("dimensions", [])
        ],
        quality_checks=data.get("quality_checks"),
        dollar_ref=data.get("$ref"),
    )


def parse_data_quality(data: Dict[str, Any]) -> DataQuality:
    """Parse data quality data."""
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        declarative = data.get("declarative", {})
        if isinstance(declarative, dict):
            profiles = declarative
        else:
            profiles = {
                f"declarative{index}": profile
                for index, profile in enumerate(declarative, start=1)
                if isinstance(profile, dict)
            }
    return DataQuality(
        profiles={
            name: parse_data_quality_profile(profile)
            for name, profile in profiles.items()
        },
        dollar_ref=data.get("$ref"),
    )


def parse_data_access_method(data: Dict[str, Any]) -> DataAccessMethod:
    """Parse one data access method."""
    return DataAccessMethod(
        name=data.get("name"),
        description=data.get("description"),
        output_port_type=data.get("outputPortType") or data.get("outputPorttype"),
        format=data.get("format"),
        access_url=data.get("accessURL"),
        authentication_method=data.get("authenticationMethod"),
        specs_url=data.get("specsURL"),
        documentation_url=data.get("documentationURL"),
        specification=data.get("specification"),
        version=data.get("version"),
        reference=data.get("reference"),
        dollar_ref=data.get("$ref"),
    )


def parse_data_access(data: Any) -> DataAccess:
    """Parse data access configuration."""
    if isinstance(data, list):
        methods = [method for method in data if isinstance(method, dict)]
        default_method = parse_data_access_method(methods[0] if methods else {})
        additional_methods = {
            f"method{index}": parse_data_access_method(method)
            for index, method in enumerate(methods[1:], start=2)
        }
        return DataAccess(default=default_method, additional_methods=additional_methods)
    if "default" in data:
        default_key = "default"
    else:
        default_key = next(iter(data), "default")
    default_method = parse_data_access_method(data.get(default_key, {}))
    additional_methods = {
        key: parse_data_access_method(method_data)
        for key, method_data in data.items()
        if key not in {default_key, "$ref"}
    }
    return DataAccess(
        default=default_method,
        additional_methods=additional_methods,
        dollar_ref=data.get("$ref"),
    )


def parse_license(data: Dict[str, Any]) -> License:
    """Parse license data."""
    return License(
        scope_of_use=data.get("scopeOfUse", ""),
        scope=data.get("scope"),
        termination=data.get("termination"),
        governance=data.get("governance"),
        geographical_area=data.get("geographicalArea", []),
        permanent=data.get("permanent", True),
        exclusive=data.get("exclusive", False),
        right_to_sublicense=data.get("rightToSublicense", False),
        right_to_modify=data.get("rightToModify", False),
        valid_from=data.get("validFrom"),
        valid_until=data.get("validUntil"),
        license_grant=data.get("licenseGrant"),
        license_name=data.get("licenseName"),
        license_url=data.get("licenseURL"),
        scope_details=data.get("scopeDetails"),
        termination_conditions=data.get("terminationConditions"),
        governance_specifics=data.get("governanceSpecifics"),
        audit_terms=data.get("auditTerms"),
        warranties=data.get("warranties"),
        damages=data.get("damages"),
        confidentiality_clauses=data.get("confidentialityClauses"),
    )


def parse_payment_gateway(data: Dict[str, Any]) -> PaymentGateway:
    """Parse one payment gateway."""
    return PaymentGateway(
        name=data.get("name", ""),
        url=data.get("url", ""),
        specification=data.get("specification"),
        description=data.get("description"),
        version=data.get("version"),
        reference=data.get("reference"),
        executable_specifications=data.get("executableSpecifications"),
        dollar_ref=data.get("$ref"),
    )


def parse_payment_gateways(data: Dict[str, Any]) -> PaymentGateways:
    """Parse payment gateway collection."""
    if not isinstance(data.get("gateways"), list) and not isinstance(
        data.get("named_gateways"), dict
    ):
        return PaymentGateways(
            named_gateways={
                name: parse_payment_gateway(gateway)
                for name, gateway in data.items()
                if name != "$ref" and isinstance(gateway, dict)
            },
            dollar_ref=data.get("$ref"),
        )
    return PaymentGateways(
        gateways=[
            parse_payment_gateway(gateway) for gateway in data.get("gateways", [])
        ],
        named_gateways={
            name: parse_payment_gateway(gateway)
            for name, gateway in data.get("named_gateways", {}).items()
        },
        dollar_ref=data.get("$ref"),
    )


def parse_extensions(product_data: Dict[str, Any]) -> SpecificationExtensions:
    """Parse x-prefixed custom extension fields from product data."""
    extensions = SpecificationExtensions()
    for key, value in product_data.items():
        if key.startswith("x-"):
            extensions.add_extension(key, value)
    return extensions


def serialize_product_details(product_details: ProductDetails) -> Dict[str, Any]:
    """Serialize product details to ODPS dictionary keys."""
    product = asdict(product_details)
    convert_snake_to_camel(product, PRODUCT_DETAILS_MAPPING)
    return product


def serialize_product_strategy(product_strategy: ProductStrategy) -> Dict[str, Any]:
    """Serialize product strategy."""
    product_strategy_dict = asdict(product_strategy)
    convert_snake_to_camel(product_strategy_dict, PRODUCT_STRATEGY_MAPPING)
    return product_strategy_dict


def serialize_data_contract(data_contract: DataContract) -> Dict[str, Any]:
    """Serialize data contract."""
    data = asdict(data_contract)
    convert_snake_to_camel(data, DATA_CONTRACT_MAPPING)
    return data


def serialize_sla(sla: SLA) -> Dict[str, Any]:
    """Serialize SLA data."""
    data = asdict(sla)
    convert_snake_to_camel(data, COLLECTION_REF_MAPPING)
    for profile in data.get("profiles", {}).values():
        convert_snake_to_camel(profile, SLA_PROFILE_MAPPING)
    return cast(Dict[str, Any], clean_none(data))


def serialize_data_quality(data_quality: DataQuality) -> Dict[str, Any]:
    """Serialize data quality data."""
    data = asdict(data_quality)
    convert_snake_to_camel(data, COLLECTION_REF_MAPPING)
    for profile in data.get("profiles", {}).values():
        convert_snake_to_camel(profile, DATA_QUALITY_PROFILE_MAPPING)
        for dimension in profile.get("dimensions", []):
            convert_snake_to_camel(dimension, DATA_QUALITY_DIMENSION_MAPPING)
    return cast(Dict[str, Any], clean_none(data))


def serialize_data_access(data_access: DataAccess) -> List[Dict[str, Any]]:
    """Serialize data access configuration."""
    default = asdict(data_access.default)
    convert_snake_to_camel(default, DATA_ACCESS_MAPPING)
    methods = [default]
    for method in data_access.additional_methods.values():
        method_dict = asdict(method)
        convert_snake_to_camel(method_dict, DATA_ACCESS_MAPPING)
        methods.append(method_dict)
    return methods


def serialize_license(license_data: License) -> Dict[str, Any]:
    """Serialize license data."""
    data = asdict(license_data)
    convert_snake_to_camel(data, LICENSE_MAPPING)
    return data


def serialize_data_holder(data_holder: DataHolder) -> Dict[str, Any]:
    """Serialize data holder data."""
    data = asdict(data_holder)
    convert_snake_to_camel(data, DATA_HOLDER_MAPPING)
    return data


def serialize_pricing_plans(pricing_plans: PricingPlans) -> Dict[str, Any]:
    """Serialize pricing plans."""
    data: Dict[str, Any] = {"plans": []}
    for plan in pricing_plans.plans:
        plan_dict = asdict(plan)
        convert_snake_to_camel(plan_dict, PRICING_PLAN_MAPPING)
        data["plans"].append(plan_dict)
    if pricing_plans.language_specific_plans:
        data["languageSpecificPlans"] = {
            language: [serialize_pricing_plan(plan) for plan in plans]
            for language, plans in pricing_plans.language_specific_plans.items()
        }
    return data


def serialize_pricing_plan(pricing_plan: PricingPlan) -> Dict[str, Any]:
    """Serialize a single pricing plan."""
    data = asdict(pricing_plan)
    convert_snake_to_camel(data, PRICING_PLAN_MAPPING)
    return data


def serialize_payment_gateways(payment_gateways: PaymentGateways) -> Dict[str, Any]:
    """Serialize payment gateways."""
    data: Dict[str, Any] = {
        "gateways": [
            serialize_payment_gateway(gateway) for gateway in payment_gateways.gateways
        ]
    }
    if payment_gateways.named_gateways:
        data["named_gateways"] = {
            name: serialize_payment_gateway(gateway)
            for name, gateway in payment_gateways.named_gateways.items()
        }
    if payment_gateways.dollar_ref:
        data["$ref"] = payment_gateways.dollar_ref
    return cast(Dict[str, Any], clean_none(data))


def serialize_payment_gateway(payment_gateway: PaymentGateway) -> Dict[str, Any]:
    """Serialize a single payment gateway."""
    data = asdict(payment_gateway)
    convert_snake_to_camel(data, PAYMENT_GATEWAY_MAPPING)
    return cast(Dict[str, Any], clean_none(data))
