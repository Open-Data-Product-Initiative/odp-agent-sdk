"""Internal helpers for measuring compact context formats."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Mapping, Optional

TokenCounter = Callable[[str], int]


@dataclass(frozen=True)
class ContextFormatMetric:
    """Measurement for one context format."""

    format: str
    bytes: int
    tokens: int
    byte_reduction_vs_baseline: Optional[float]
    token_reduction_vs_baseline: Optional[float]


@dataclass(frozen=True)
class ContextMeasurement:
    """Measurements for one fixture across context formats."""

    label: str
    formats: List[ContextFormatMetric]


def count_tokens(text: str, *, tokenizer: TokenCounter) -> int:
    """Count tokens in text using the provided tokenizer."""
    return tokenizer(text)


def measure_context_formats(
    label: str,
    texts: Mapping[str, str],
    *,
    tokenizer: TokenCounter,
    baseline: str = "yaml",
) -> ContextMeasurement:
    """Measure bytes and tokens for context format texts."""
    if baseline not in texts:
        raise ValueError(f"Baseline format not found: {baseline}")
    baseline_bytes = len(texts[baseline].encode("utf-8"))
    baseline_tokens = count_tokens(texts[baseline], tokenizer=tokenizer)
    metrics: List[ContextFormatMetric] = []
    for name, text in texts.items():
        byte_count = len(text.encode("utf-8"))
        token_count = count_tokens(text, tokenizer=tokenizer)
        if name == baseline:
            byte_reduction = None
            token_reduction = None
        else:
            byte_reduction = _reduction_percent(baseline_bytes, byte_count)
            token_reduction = _reduction_percent(baseline_tokens, token_count)
        metrics.append(
            ContextFormatMetric(
                format=name,
                bytes=byte_count,
                tokens=token_count,
                byte_reduction_vs_baseline=byte_reduction,
                token_reduction_vs_baseline=token_reduction,
            )
        )
    return ContextMeasurement(label=label, formats=metrics)


def _reduction_percent(baseline: int, observed: int) -> float:
    if baseline == 0:
        return 0.0
    return round((baseline - observed) / baseline * 100, 1)
