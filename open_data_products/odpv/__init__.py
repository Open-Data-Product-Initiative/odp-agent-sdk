"""Open Data Product Vocabulary (ODPV) namespace."""

from .vocabulary import (
    ValidationResult,
    agent_vocabulary_context,
    build_artifacts,
    build_terms_jsonl,
    check_vocabulary_relationship,
    explain_vocabulary_term,
    iter_sections,
    iter_terms,
    load_vocabulary,
    render_search_results,
    resolve_vocabulary_term,
    search_vocabulary,
    term_packet,
    validate_vocabulary,
    vocabulary_index,
    write_artifacts,
)

SPEC_ID = "odpv"
SPEC_NAME = "Open Data Product Vocabulary"

__all__ = [
    "SPEC_ID",
    "SPEC_NAME",
    "ValidationResult",
    "agent_vocabulary_context",
    "build_artifacts",
    "build_terms_jsonl",
    "check_vocabulary_relationship",
    "explain_vocabulary_term",
    "iter_sections",
    "iter_terms",
    "load_vocabulary",
    "render_search_results",
    "resolve_vocabulary_term",
    "search_vocabulary",
    "term_packet",
    "validate_vocabulary",
    "vocabulary_index",
    "write_artifacts",
]
