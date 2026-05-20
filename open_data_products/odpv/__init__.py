"""Open Data Product Vocabulary (ODPV) namespace."""

from .vocabulary import (
    ValidationResult,
    build_artifacts,
    build_terms_jsonl,
    iter_sections,
    iter_terms,
    load_vocabulary,
    render_search_results,
    search_vocabulary,
    validate_vocabulary,
    write_artifacts,
)

SPEC_ID = "odpv"
SPEC_NAME = "Open Data Product Vocabulary"

__all__ = [
    "SPEC_ID",
    "SPEC_NAME",
    "ValidationResult",
    "build_artifacts",
    "build_terms_jsonl",
    "iter_sections",
    "iter_terms",
    "load_vocabulary",
    "render_search_results",
    "search_vocabulary",
    "validate_vocabulary",
    "write_artifacts",
]
