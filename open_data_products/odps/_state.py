"""Internal state and cache helpers for ODPS documents."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Tuple

STATE_FIELDS: Tuple[str, ...] = (
    "schema",
    "version",
    "product_details",
    "product_strategy",
    "data_contract",
    "sla",
    "data_quality",
    "pricing_plans",
    "license",
    "data_access",
    "data_holder",
    "payment_gateways",
    "extensions",
)

OPTIONAL_COMPONENT_FIELDS: Tuple[str, ...] = (
    "data_contract",
    "sla",
    "data_quality",
    "pricing_plans",
    "license",
    "data_access",
    "data_holder",
    "payment_gateways",
    "extensions",
)


def generate_hash(document: Any) -> str:
    """Return a stable hash of the document's current state."""
    state_data = {field: str(getattr(document, field)) for field in STATE_FIELDS}
    state_str = json.dumps(state_data, sort_keys=True)
    return hashlib.sha256(state_str.encode()).hexdigest()


def clear_caches(
    validation_cache: Dict[str, Any],
    serialization_cache: Dict[Any, str],
) -> None:
    """Clear validation and serialization caches."""
    validation_cache.clear()
    serialization_cache.clear()


def has_optional_components(document: Any) -> bool:
    """Return whether any optional ODPS component is present."""
    return any(getattr(document, field) is not None for field in OPTIONAL_COMPONENT_FIELDS)


def component_count(document: Any) -> int:
    """Return the count of populated optional ODPS components."""
    return sum(
        1 for field in OPTIONAL_COMPONENT_FIELDS if getattr(document, field) is not None
    )
