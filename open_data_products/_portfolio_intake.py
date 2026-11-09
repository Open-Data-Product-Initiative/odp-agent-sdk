"""Read-only Portfolio source intake workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Union

from .generation.models import PortfolioPrivacySettings, PortfolioSourceBudget
from .portfolio_budget import (
    PORTFOLIO_PROMPT_OVERHEAD_RESERVE_CHARS,
    PORTFOLIO_SOURCE_CHUNK_CHARS,
    PORTFOLIO_SOURCE_PROMPT_CHARS,
    estimated_word_count,
    int_value,
    reduce_source_lanes_for_prompt,
)
from .portfolio_privacy import apply_source_privacy
from .portfolio_sources import (
    SOURCE_WARNING_KEY,
    collect_source_lanes,
    source_extraction_warnings,
)


def inspect_portfolio_intake(
    *,
    objectives: Optional[Union[str, Path]] = None,
    use_cases: Optional[Union[str, Path]] = None,
    signals: Optional[Union[str, Path]] = None,
    products: Optional[Union[str, Path]] = None,
    source_budget: Optional[PortfolioSourceBudget] = None,
    source_privacy: Optional[PortfolioPrivacySettings] = None,
) -> Dict[str, object]:
    """Inspect portfolio source intake without calling an LLM."""
    lanes = collect_source_lanes(
        objectives=Path(objectives) if objectives is not None else None,
        use_cases=Path(use_cases) if use_cases is not None else None,
        signals=Path(signals) if signals is not None else None,
        products=Path(products) if products is not None else None,
    )
    source_budget_settings = source_budget or PortfolioSourceBudget(
        max_source_chars=PORTFOLIO_SOURCE_CHUNK_CHARS,
        max_prompt_chars=PORTFOLIO_SOURCE_PROMPT_CHARS,
    )
    privacy_settings = source_privacy or PortfolioPrivacySettings()
    private_lanes, source_privacy_report = apply_source_privacy(
        lanes,
        privacy_settings=privacy_settings,
    )
    reduced_lanes, source_budget_report = reduce_source_lanes_for_prompt(
        private_lanes,
        max_source_chars=source_budget_settings.max_source_chars,
        max_prompt_chars=source_budget_settings.max_prompt_chars,
        prompt_overhead_chars=PORTFOLIO_PROMPT_OVERHEAD_RESERVE_CHARS,
    )
    reduced_by_id = {
        str(source.get("sourceId")): source
        for files in reduced_lanes.values()
        for source in files
        if source.get("sourceId")
    }
    sources = []
    for lane_name, files in private_lanes.items():
        if lane_name == SOURCE_WARNING_KEY:
            continue
        for source in files:
            source_id = str(source.get("sourceId", ""))
            reduced = reduced_by_id.get(source_id, {})
            extracted_chars = len(str(source.get("text", "")))
            included_chars = len(str(reduced.get("text", "")))
            chunk_count = int_value(reduced.get("chunkCount"), default=1)
            included_chunk_count = int_value(
                reduced.get("includedChunkCount"), default=1
            )
            omitted_chunk_count = int_value(reduced.get("omittedChunkCount"), default=0)
            status = "included"
            if omitted_chunk_count:
                status = "reduced"
            if extracted_chars == 0:
                status = "empty"
            sources.append(
                {
                    "lane": lane_name,
                    "path": source.get("path", ""),
                    "sourceId": source_id,
                    "sourceType": source.get("sourceType", ""),
                    "detectionMethod": source.get("detectionMethod", ""),
                    "sourceUnit": source.get("sourceUnit", ""),
                    "sourceUnitId": source.get("sourceUnitId", ""),
                    "preview": str(source.get("text", ""))[:500],
                    "extractedChars": extracted_chars,
                    "estimatedWords": estimated_word_count(str(source.get("text", ""))),
                    "includedChars": included_chars,
                    "omittedChars": max(extracted_chars - included_chars, 0),
                    "chunkCount": chunk_count,
                    "includedChunkCount": included_chunk_count,
                    "omittedChunkCount": omitted_chunk_count,
                    "status": status,
                }
            )

    source_counts = {
        name: len(files) for name, files in lanes.items() if name != SOURCE_WARNING_KEY
    }
    warnings = source_extraction_warnings(lanes)
    warnings.extend(str(item) for item in source_budget_report.get("warnings", []))
    warnings.extend(str(item) for item in source_privacy_report.get("warnings", []))
    skipped_sources = [
        {
            "lane": source.get("lane", ""),
            "path": source.get("path", ""),
            "sourceId": source.get("sourceId", ""),
            "sourceType": source.get("sourceType", ""),
            "detectionMethod": source.get("detectionMethod", ""),
            "warning": source.get("warning", ""),
            "status": "skipped",
        }
        for source in lanes.get(SOURCE_WARNING_KEY, [])
    ]
    return {
        "spec": "portfolio",
        "kind": "PortfolioIntake",
        "llmCallCount": 0,
        "sourceCounts": source_counts,
        "sourceBudget": source_budget_report,
        "sourcePrivacy": source_privacy_report,
        "sourceExtraction": {
            "warnings": source_extraction_warnings(lanes),
            "skippedSourceCount": len(skipped_sources),
            "skippedSources": skipped_sources,
        },
        "sources": sources,
        "warnings": warnings,
    }
