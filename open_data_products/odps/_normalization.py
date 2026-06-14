"""Internal ODPS normalization helpers shared by workflow modules."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

ODPS_SLA_DIMENSIONS = {
    "latency",
    "uptime",
    "responseTime",
    "errorRate",
    "endOfSupport",
    "endOfLife",
    "updateFrequency",
    "timeToDetect",
    "timeToNotify",
    "timeToRepair",
    "emailResponseTime",
}
ODPS_SLA_DIMENSION_ALIASES = {
    "availability": "uptime",
    "available": "uptime",
    "freshness": "updateFrequency",
    "datafreshness": "updateFrequency",
    "data-freshness": "updateFrequency",
    "refresh": "updateFrequency",
    "refreshtimeliness": "updateFrequency",
    "refresh-timeliness": "updateFrequency",
    "refreshfrequency": "updateFrequency",
    "refresh-frequency": "updateFrequency",
}
ODPS_SLA_UNITS = {
    "percent",
    "milliseconds",
    "seconds",
    "minutes",
    "days",
    "weeks",
    "months",
    "years",
    "never",
    "date",
    "null",
}
ODPS_SLA_UNIT_ALIASES = {
    "hour": "minutes",
    "hours": "minutes",
    "day": "days",
    "daily": "days",
    "week": "weeks",
    "weekly": "weeks",
    "month": "months",
    "monthly": "months",
    "year": "years",
    "yearly": "years",
    "percentage": "percent",
}
ODPS_DATA_QUALITY_DIMENSIONS = {
    "accuracy",
    "completeness",
    "conformity",
    "consistency",
    "coverage",
    "timeliness",
    "validity",
    "uniqueness",
}
ODPS_DATA_QUALITY_DIMENSION_ALIASES = {
    "freshness": "timeliness",
    "datafreshness": "timeliness",
    "data-freshness": "timeliness",
    "reconcile": "consistency",
    "reconciliation": "consistency",
    "source-reconciliation": "consistency",
    "source-count-reconciliation": "consistency",
    "crm-reconciliation": "consistency",
    "billing-reconciliation": "consistency",
}
ODPS_DATA_QUALITY_UNITS = {"percentage", "number"}
ODPS_DATA_QUALITY_UNIT_ALIASES = {
    "percent": "percentage",
    "percentage": "percentage",
    "%": "percentage",
    "count": "number",
}


def normalize_odps_dimension(
    dimension: Dict[str, Any],
    *,
    allowed_dimensions: set,
    dimension_aliases: Dict[str, str],
    allowed_units: set,
    keep_description: bool,
    stringify_objective: bool,
) -> Dict[str, Any]:
    """Normalize one generated ODPS SLA or data-quality dimension."""
    raw_name = dimension.get("name") or dimension.get("dimension")
    name = normalize_odps_dimension_name(
        raw_name,
        allowed_dimensions=allowed_dimensions,
        dimension_aliases=dimension_aliases,
    )
    if not name:
        return {}
    normalized: Dict[str, Any] = {"dimension": name}
    if "objective" in dimension:
        objective = dimension["objective"]
        if is_hour_unit(dimension.get("unit")) and "minutes" in allowed_units:
            objective = hours_to_minutes(objective)
        normalized["objective"] = str(objective) if stringify_objective else objective
    unit = normalize_odps_unit(dimension.get("unit"), allowed_units)
    if not unit and is_hour_unit(dimension.get("unit")) and "minutes" in allowed_units:
        unit = "minutes"
    if unit:
        normalized["unit"] = unit
    display_title = dimension.get("displayTitle") or dimension.get("display_title")
    if display_title is not None:
        normalized["displayTitle"] = display_title
    description = dimension.get("description")
    if keep_description and isinstance(description, str) and description.strip():
        normalized["description"] = description.strip()
    return normalized


def normalize_odps_dimension_name(
    value: object,
    *,
    allowed_dimensions: set,
    dimension_aliases: Dict[str, str],
) -> Optional[str]:
    """Normalize a dimension name against allowed values and aliases."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped in allowed_dimensions:
        return stripped
    compact = re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-")
    return dimension_aliases.get(compact) or dimension_aliases.get(
        compact.replace("-", "")
    )


def normalize_odps_unit(value: object, allowed_units: set) -> Optional[str]:
    """Return an allowed unit value or None."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped if stripped in allowed_units else None


def is_hour_unit(value: object) -> bool:
    """Return whether a value represents an hour unit."""
    return isinstance(value, str) and value.strip().casefold() in {"hour", "hours"}


def hours_to_minutes(value: object) -> object:
    """Convert numeric hour values to minutes while preserving non-numeric values."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    minutes = number * 60
    return int(minutes) if minutes.is_integer() else minutes
