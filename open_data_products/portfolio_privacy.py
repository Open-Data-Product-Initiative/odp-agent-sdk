"""Portfolio source privacy helpers."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .generation.models import PortfolioPrivacySettings
from .portfolio_sources import SOURCE_WARNING_KEY
from .privacy import OBFUSCATION_WARNING, _obfuscate_personal_data_with_state

PORTFOLIO_PRIVACY_DISABLED_WARNING = (
    "Personal data obfuscation is disabled for portfolio document intake."
)


def apply_source_privacy(
    lanes: Dict[str, List[Dict[str, str]]],
    *,
    privacy_settings: PortfolioPrivacySettings,
) -> Tuple[Dict[str, List[Dict[str, str]]], Dict[str, object]]:
    """Apply configured source privacy controls before prompt reduction."""
    source_count = sum(
        len(files) for name, files in lanes.items() if name != SOURCE_WARNING_KEY
    )
    if not privacy_settings.obfuscate_personal_data:
        return dict(lanes), {
            "method": "deterministic-personal-data-obfuscation",
            "enabled": False,
            "sourceCount": source_count,
            "replacementCounts": {},
            "replacements": [],
            "warnings": [PORTFOLIO_PRIVACY_DISABLED_WARNING],
        }

    value_to_placeholder: Dict[str, str] = {}
    replacement_counts: Dict[str, int] = {}
    replacements: List[Dict[str, str]] = []
    private_lanes: Dict[str, List[Dict[str, str]]] = {}
    for lane_name, files in lanes.items():
        if lane_name == SOURCE_WARNING_KEY:
            continue
        private_files: List[Dict[str, str]] = []
        for source in files:
            private_source = dict(source)
            private_source["text"] = _obfuscate_personal_data_with_state(
                str(source.get("text", "")),
                value_to_placeholder=value_to_placeholder,
                replacement_counts=replacement_counts,
                replacements=replacements,
            )
            private_files.append(private_source)
        private_lanes[lane_name] = private_files

    warnings = [OBFUSCATION_WARNING] if replacements else []
    return private_lanes, {
        "method": "deterministic-personal-data-obfuscation",
        "enabled": True,
        "sourceCount": source_count,
        "replacementCounts": replacement_counts,
        "replacements": replacements,
        "warnings": warnings,
    }
