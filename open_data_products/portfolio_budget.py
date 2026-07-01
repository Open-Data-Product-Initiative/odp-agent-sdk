"""Portfolio source prompt budget helpers."""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Tuple

from .portfolio_sources import SOURCE_WARNING_KEY

PORTFOLIO_SOURCE_CHUNK_CHARS = 2000
PORTFOLIO_SOURCE_PROMPT_CHARS = 32000
PORTFOLIO_PROMPT_OVERHEAD_RESERVE_CHARS = 16000

PortfolioBuildClient = Callable[[str, str], str]


def reduce_source_lanes_for_prompt(
    lanes: Dict[str, List[Dict[str, str]]],
    *,
    max_source_chars: int = PORTFOLIO_SOURCE_CHUNK_CHARS,
    max_prompt_chars: int = PORTFOLIO_SOURCE_PROMPT_CHARS,
    prompt_overhead_chars: int = 0,
) -> Tuple[Dict[str, List[Dict[str, str]]], Dict[str, object]]:
    """Reduce source lane text deterministically before LLM prompt rendering."""
    if max_source_chars <= 0:
        raise ValueError("max_source_chars must be a positive integer.")
    if max_prompt_chars <= 0:
        raise ValueError("max_prompt_chars must be a positive integer.")
    if prompt_overhead_chars < 0:
        raise ValueError("prompt_overhead_chars must be zero or a positive integer.")
    chunk_limit = min(max_source_chars, max_prompt_chars)
    source_prompt_chars = max(max_prompt_chars - prompt_overhead_chars, 0)
    reduced: Dict[str, List[Dict[str, str]]] = {}
    estimated_chars = 0
    included_chars = 0
    chunk_count = 0
    included_chunk_count = 0
    omitted_chunk_count = 0
    reduced_source_count = 0
    source_count = 0

    for lane_name, files in lanes.items():
        if lane_name == SOURCE_WARNING_KEY:
            continue
        reduced_files: List[Dict[str, str]] = []
        for source in files:
            source_count += 1
            text = str(source.get("text", ""))
            estimated_chars += len(text)
            chunks = chunk_source_text(text, chunk_limit)
            chunk_count += len(chunks)
            included_chunks: List[str] = []
            remaining_prompt_chars = source_prompt_chars
            for chunk in chunks:
                chunk_size = len(chunk)
                separator_size = 2 if included_chunks else 0
                required_chars = chunk_size + separator_size
                if required_chars > remaining_prompt_chars:
                    break
                included_chunks.append(chunk)
                remaining_prompt_chars -= required_chars
                included_chars += required_chars
            omitted_chunks = len(chunks) - len(included_chunks)
            included_chunk_count += len(included_chunks)
            omitted_chunk_count += omitted_chunks
            if omitted_chunks:
                reduced_source_count += 1
            reduced_source = dict(source)
            reduced_source["text"] = "\n\n".join(included_chunks)
            reduced_source["chunkCount"] = str(len(chunks))
            reduced_source["includedChunkCount"] = str(len(included_chunks))
            reduced_source["omittedChunkCount"] = str(omitted_chunks)
            reduced_files.append(reduced_source)
        reduced[lane_name] = reduced_files

    warnings = []
    if omitted_chunk_count:
        warnings.append(
            "Content omitted from prompt: "
            f"{omitted_chunk_count} chunks over context budget"
        )
    budget: Dict[str, object] = {
        "method": "deterministic-chunk-budget",
        "budgetScope": "per-source",
        "maxSourceChars": max_source_chars,
        "maxPromptChars": max_prompt_chars,
        "promptOverheadReserveChars": prompt_overhead_chars,
        "sourcePromptChars": source_prompt_chars,
        "estimatedInputChars": estimated_chars,
        "includedChars": included_chars,
        "omittedChars": max(estimated_chars - included_chars, 0),
        "sourceCount": source_count,
        "reducedSourceCount": reduced_source_count,
        "chunkCount": chunk_count,
        "includedChunkCount": included_chunk_count,
        "omittedChunkCount": omitted_chunk_count,
        "warnings": warnings,
    }
    return reduced, budget


def chunk_source_text(text: str, max_chars: int) -> List[str]:
    """Split source text into deterministic prompt chunks."""
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs and text.strip():
        paragraphs = [text.strip()]
    chunks: List[str] = []
    current = ""
    for paragraph in paragraphs:
        paragraph_parts = split_long_text(paragraph, max_chars)
        for part in paragraph_parts:
            candidate = part if not current else current + "\n\n" + part
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks


def split_long_text(text: str, max_chars: int) -> List[str]:
    """Split one long source paragraph into fixed-size chunks."""
    if len(text) <= max_chars:
        return [text]
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def int_value(value: object, *, default: int) -> int:
    """Coerce a value to int with a fallback."""
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def estimated_word_count(text: str) -> int:
    """Return a simple whitespace-delimited word estimate."""
    return len(re.findall(r"\S+", text))


def prompt_budget_guarded_client(
    client: PortfolioBuildClient,
    *,
    max_prompt_chars: int,
    report: Dict[str, object],
) -> PortfolioBuildClient:
    """Return a client wrapper that blocks over-budget prompts before LLM calls."""

    def guarded(prompt: str, model: str) -> str:
        prompt_chars = len(prompt)
        report["checkedPromptCount"] = int(report.get("checkedPromptCount", 0)) + 1
        report["maxObservedPromptChars"] = max(
            int(report.get("maxObservedPromptChars", 0)),
            prompt_chars,
        )
        if prompt_chars > max_prompt_chars:
            raise ValueError(
                "Portfolio prompt exceeds configured budget: "
                f"estimatedPromptChars={prompt_chars}, "
                f"maxPromptChars={max_prompt_chars}. "
                "Increase portfolio.sourceBudget.maxPromptChars or reduce source input."
            )
        return client(prompt, model)

    return guarded
