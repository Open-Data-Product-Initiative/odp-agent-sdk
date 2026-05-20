"""Bridge ODPS pricing plans to HTTP 402 Payment Required responses.

The ODP standards already model paid data products via ``PricingPlans`` and
``PaymentGateways``. This helper renders that block as the headers an x402
facilitator (or any 402-aware client) expects, so an SDK consumer can mount
an ODPS document directly behind a paywalled endpoint.

Aligns with agenticpatterns.veso.ai/agent-payments.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .odps import OpenDataProduct


def pricing_to_402(product: OpenDataProduct) -> Optional[Dict[str, Any]]:
    """Return a 402 envelope for ``product`` or ``None`` when free/unpriced.

    Envelope shape::

        {
          "status": 402,
          "headers": {
            "X-Payment-Required": "<json>",
            "WWW-Authenticate": "L402 ...",   # only when invoiceable
          }
        }
    """
    plans = getattr(product, "pricing_plans", None)
    if plans is None or not getattr(plans, "plans", None):
        return None

    plan = plans.plans[0]
    payload = {
        "price": plan.price,
        "currency": plan.price_currency,
        "billing": plan.billing_duration,
        "plan": _flatten_label(plan.name),
        "product_id": product.product_details.product_id,
        "protocol": "x402",
    }
    headers = {"X-Payment-Required": json.dumps(payload, separators=(",", ":"))}
    return {"status": 402, "headers": headers}


def _flatten_label(name: Any) -> str:
    if isinstance(name, dict):
        value = name.get("en") or next(iter(name.values()), "")
        return str(value)
    return str(name) if name is not None else ""
