"""Internal ODPS document assembly helpers."""

from __future__ import annotations

from typing import Any, Dict, cast

from .codecs import (
    serialize_contract_profiles,
    serialize_data_access,
    serialize_data_contract,
    serialize_data_holder,
    serialize_data_quality,
    serialize_license,
    serialize_payment_gateways,
    serialize_pricing_plans,
    serialize_product_details,
    serialize_product_strategy,
    serialize_sla,
)


def build_document(product: Any) -> Dict[str, Any]:
    """Build the canonical dictionary representation for an ODPS product."""
    details = serialize_product_details(product.product_details)
    product_value: Dict[str, Any] = (
        {"details": {"en": details}}
        if product.version == "4.2"
        else details
    )
    result: Dict[str, Any] = {
        "schema": product.schema,
        "version": product.version,
        "product": product_value,
    }

    product_data = cast(Dict[str, Any], result["product"])

    if product.product_strategy:
        product_data["productStrategy"] = serialize_product_strategy(
            product.product_strategy
        )
    if product.data_contract:
        if product.version == "4.2":
            product_data["contract"] = serialize_contract_profiles(product.data_contract)
        else:
            product_data["contract"] = serialize_data_contract(product.data_contract)
    if product.sla:
        product_data["SLA"] = serialize_sla(product.sla)
    if product.data_quality:
        product_data["dataQuality"] = serialize_data_quality(product.data_quality)
    if product.data_access:
        product_data["dataAccess"] = serialize_data_access(
            product.data_access, product.version
        )
    if product.license:
        product_data["license"] = serialize_license(product.license)
    if product.data_holder:
        product_data["dataHolder"] = serialize_data_holder(product.data_holder)
    if product.pricing_plans:
        product_data["pricingPlans"] = serialize_pricing_plans(product.pricing_plans)
    if product.payment_gateways:
        product_data["paymentGateways"] = serialize_payment_gateways(
            product.payment_gateways
        )
    if product.extensions:
        product_data.update(product.extensions.extensions)

    return result
