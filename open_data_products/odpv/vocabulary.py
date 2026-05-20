"""ODPV vocabulary loading, search, validation, and artifact helpers."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import yaml

from open_data_products._io import load_mapping

SECTION_IDS = ("core", "value", "governance", "relationships")
REQUIRED_TERM_FIELDS = (
    "id",
    "uri",
    "type",
    "status",
    "introducedIn",
    "preferredLabel",
    "definition",
    "alsoKnownAs",
    "relatedTerms",
    "usedIn",
    "examples",
)
FIELD_WEIGHTS = {
    "id": 5,
    "preferredLabel": 5,
    "alsoKnownAs": 4,
    "definition": 3,
    "examples": 3,
    "relatedTerms": 2,
    "section": 1,
}
WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ValidationResult:
    """Result from validating bundled or caller-supplied ODPV vocabulary data."""

    valid: bool
    errors: List[str]
    term_count: int
    relationship_count: int
    section_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""
        payload = asdict(self)
        payload["spec"] = "odpv"
        payload["kind"] = "Vocabulary"
        return payload


def _data_file(name: str) -> Path:
    return Path(__file__).resolve().parent / "data" / "vocab" / name


def _read_package_text(name: str) -> str:
    return _data_file(name).read_text(encoding="utf-8")


def load_vocabulary(path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load ODPV vocabulary YAML from ``path`` or bundled package data."""
    vocabulary_path = _data_file("odpv.yaml") if path is None else Path(path)
    return load_mapping(vocabulary_path, root_name="ODPV vocabulary")


def dump_yaml(data: Dict[str, Any]) -> str:
    """Serialize ODPV data using the same style as the source scripts."""
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=False,
        width=10_000,
    )


def dump_json(data: Dict[str, Any]) -> str:
    """Serialize ODPV data as formatted JSON."""
    return json.dumps(data, indent=2, ensure_ascii=True) + "\n"


def iter_sections(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return ODPV section mappings from vocabulary data."""
    sections = data.get("sections")
    if not isinstance(sections, list):
        raise ValueError("ODPV data must contain a sections array")
    return sections


def iter_terms(
    data: Dict[str, Any],
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Return ``(section, term)`` pairs from vocabulary data."""
    terms: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for section in iter_sections(data):
        for term in _section_terms(section):
            terms.append((section, term))
    return terms


def _section_terms(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    terms = section.get("terms", [])
    if not isinstance(terms, list):
        return []
    return [term for term in terms if isinstance(term, dict)]


def section_document(
    data: Dict[str, Any],
    section: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a single-section ODPV document."""
    return {**data, "sections": [section]}


def build_terms_jsonl(data: Optional[Dict[str, Any]] = None) -> str:
    """Build JSONL records for all ODPV terms."""
    vocabulary = data or load_vocabulary()
    lines = []
    for section, term in iter_terms(vocabulary):
        flattened = {
            "vocabulary": vocabulary["id"],
            "vocabularyVersion": vocabulary["version"],
            "section": section["id"],
            "sectionName": section["name"]["en"],
            **term,
        }
        lines.append(json.dumps(flattened, ensure_ascii=True, separators=(",", ":")))
    return "\n".join(lines) + "\n"


def build_artifacts(data: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Build derived ODPV artifact contents keyed by relative output path."""
    vocabulary = data or load_vocabulary()
    artifacts = {
        "odpv.json": dump_json(vocabulary),
        "terms.jsonl": build_terms_jsonl(vocabulary),
    }
    for section in iter_sections(vocabulary):
        section_id = section["id"]
        artifacts[f"{section_id}.yaml"] = dump_yaml(
            section_document(vocabulary, section)
        )
    return artifacts


def write_artifacts(
    output_dir: Union[str, Path],
    *,
    data: Optional[Dict[str, Any]] = None,
    check: bool = False,
) -> List[Path]:
    """Write or check generated ODPV artifacts under ``output_dir``.

    Returns relative paths that would change. When ``check`` is true, no files
    are written.
    """
    root = Path(output_dir)
    changed = []
    for relative_path, content in build_artifacts(data).items():
        path = root / relative_path
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        changed.append(Path(relative_path))
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    return changed


def validate_data(data: Dict[str, Any]) -> List[str]:
    """Return validation errors for ODPV vocabulary data."""
    errors: List[str] = []
    section_ids = [section.get("id") for section in iter_sections(data)]
    if section_ids != list(SECTION_IDS):
        errors.append(f"Expected sections {list(SECTION_IDS)}, found {section_ids}")

    seen_ids: Set[str] = set()
    for section in iter_sections(data):
        if not isinstance(section.get("terms", []), list):
            section_id = section.get("id", "<missing id>")
            errors.append(f"Section {section_id} terms must be an array")

    for section, term in iter_terms(data):
        term_id = term.get("id", "<missing id>")
        if term_id in seen_ids:
            errors.append(f"Duplicate term id: {term_id}")
        seen_ids.add(term_id)

        for field in REQUIRED_TERM_FIELDS:
            if field not in term:
                errors.append(f"{term_id}: missing required field {field}")

        examples = (
            term.get("examples", {}).get("en")
            if isinstance(term.get("examples"), dict)
            else None
        )
        if not isinstance(examples, list) or not examples:
            errors.append(f"{term_id}: examples.en must be a non-empty array")

        if term.get("type") == "relationship":
            if not term.get("domain"):
                errors.append(f"{term_id}: relationship term must include domain")
            if not term.get("range"):
                errors.append(f"{term_id}: relationship term must include range")

        used_in = term.get("usedIn")
        if not isinstance(used_in, list) or not used_in:
            errors.append(f"{term_id}: usedIn must be a non-empty array")

        if section.get("id") not in SECTION_IDS:
            errors.append(f"{term_id}: unknown section {section.get('id')}")

    return errors


def validate_vocabulary(data: Optional[Dict[str, Any]] = None) -> ValidationResult:
    """Validate ODPV vocabulary data and return counts plus errors."""
    vocabulary = data or load_vocabulary()
    terms = [term for _, term in iter_terms(vocabulary)]
    relationships = [term for term in terms if term.get("type") == "relationship"]
    errors = validate_data(vocabulary)
    return ValidationResult(
        valid=not errors,
        errors=errors,
        term_count=len(terms),
        relationship_count=len(relationships),
        section_count=len(iter_sections(vocabulary)),
    )


def tokenize(value: str) -> List[str]:
    """Tokenize search text the same way as the source ODPV scripts."""
    return WORD_RE.findall(value.lower())


def flatten_language_value(value: Any) -> str:
    """Flatten multilingual strings, lists, and dictionaries into search text."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(flatten_language_value(item) for item in value)
    if isinstance(value, dict):
        return " ".join(flatten_language_value(item) for item in value.values())
    return ""


def searchable_fields(
    section: Dict[str, Any],
    term: Dict[str, Any],
) -> Dict[str, str]:
    """Return weighted text fields for one ODPV term."""
    return {
        "id": term.get("id", ""),
        "preferredLabel": flatten_language_value(term.get("preferredLabel")),
        "alsoKnownAs": flatten_language_value(term.get("alsoKnownAs")),
        "definition": flatten_language_value(term.get("definition")),
        "examples": flatten_language_value(term.get("examples")),
        "relatedTerms": " ".join(term.get("relatedTerms", [])),
        "section": section.get("id", ""),
    }


def score_term(
    query_tokens: Iterable[str],
    fields: Dict[str, str],
) -> Tuple[int, List[str]]:
    """Score a term against tokenized query text."""
    score = 0
    matched_fields = []
    for field, text in fields.items():
        field_tokens = set(tokenize(text))
        matches = sum(1 for token in query_tokens if token in field_tokens)
        if matches:
            score += matches * FIELD_WEIGHTS[field]
            matched_fields.append(field)
    return score, matched_fields


def search_vocabulary(
    query: str,
    *,
    limit: int = 5,
    data: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Search ODPV vocabulary terms."""
    vocabulary = data or load_vocabulary()
    query_tokens = tokenize(query)
    results = []
    for section, term in iter_terms(vocabulary):
        fields = searchable_fields(section, term)
        score, matched_fields = score_term(query_tokens, fields)
        if score == 0:
            continue
        results.append(
            {
                "score": score,
                "matchedFields": matched_fields,
                "vocabularyVersion": vocabulary["version"],
                "section": section["id"],
                "id": term["id"],
                "uri": term["uri"],
                "preferredLabel": term["preferredLabel"],
                "definition": term["definition"],
                "relatedTerms": term.get("relatedTerms", []),
                "examples": term.get("examples", {}),
            }
        )
    return sorted(results, key=lambda item: (-item["score"], item["id"]))[:limit]


def render_search_results(results: List[Dict[str, Any]]) -> str:
    """Render ODPV search results in the source script text format."""
    lines = []
    for result in results:
        label = result["preferredLabel"].get("en", result["id"])
        definition = result["definition"].get("en", "")
        lines.extend(
            [
                f"{result['id']} ({label})",
                f"  uri: {result['uri']}",
                f"  section: {result['section']}",
                f"  score: {result['score']}",
                f"  matchedFields: {', '.join(result['matchedFields'])}",
                f"  definition: {definition}",
            ]
        )
    return "\n".join(lines) + ("\n" if lines else "")
