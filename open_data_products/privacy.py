"""Best-effort privacy helpers for extracted source text."""

from __future__ import annotations

import re
from typing import Dict, List

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?\d[\d .()/-]{6,}\d)(?!\w)"
)
DATE_LIKE_PATTERN = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}")
OBFUSCATION_WARNING = (
    "Personal data obfuscation is best effort; review before external LLM use."
)


def obfuscate_personal_data(text: str) -> Dict[str, object]:
    """Mask clear personal data with stable placeholders."""
    value_to_placeholder: Dict[str, str] = {}
    replacement_counts: Dict[str, int] = {}
    replacements: List[Dict[str, str]] = []
    obfuscated = _obfuscate_personal_data_with_state(
        text,
        value_to_placeholder=value_to_placeholder,
        replacement_counts=replacement_counts,
        replacements=replacements,
    )
    warnings = [OBFUSCATION_WARNING] if replacements else []
    return {
        "text": obfuscated,
        "replacements": replacements,
        "replacementCounts": replacement_counts,
        "warnings": warnings,
    }


def _obfuscate_personal_data_with_state(
    text: str,
    *,
    value_to_placeholder: Dict[str, str],
    replacement_counts: Dict[str, int],
    replacements: List[Dict[str, str]],
) -> str:
    def replace_matches(value: str, kind: str) -> str:
        key = f"{kind}:{value}"
        placeholder = value_to_placeholder.get(key)
        if placeholder is None:
            replacement_counts[kind] = replacement_counts.get(kind, 0) + 1
            placeholder = f"[{kind.upper()}_{replacement_counts[kind]}]"
            value_to_placeholder[key] = placeholder
            replacements.append(
                {
                    "type": kind,
                    "placeholder": placeholder,
                    "confidence": "high",
                }
            )
        return placeholder

    obfuscated = EMAIL_PATTERN.sub(
        lambda match: replace_matches(match.group(0), "email"),
        text,
    )
    obfuscated = PHONE_PATTERN.sub(
        lambda match: (
            match.group(0)
            if _looks_like_date(match.group(0))
            else replace_matches(match.group(0), "phone")
        ),
        obfuscated,
    )
    return obfuscated


def _looks_like_date(value: str) -> bool:
    normalized = value.strip()
    return bool(DATE_LIKE_PATTERN.fullmatch(normalized))
