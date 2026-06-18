"""Open Knowledge Format bundle helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import yaml

from .odpc import load_catalog
from .odpc.catalog import text_value

RESERVED_FILENAMES = {"index.md", "log.md"}
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
DATE_HEADING_PATTERN = re.compile(r"^##\s+\d{4}-\d{2}-\d{2}\s*$")
SCALAR_TYPES = (str, int, float, bool)


@dataclass(frozen=True)
class OkfConcept:
    """One OKF concept document."""

    id: str
    path: str
    type: str
    title: str = ""
    description: str = ""
    resource: str = ""
    tags: Tuple[str, ...] = ()
    body: str = ""

    def to_dict(self, *, include_body: bool = False) -> Dict[str, object]:
        """Return a JSON-serializable concept packet."""
        payload: Dict[str, object] = {
            "id": self.id,
            "path": self.path,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "resource": self.resource,
            "tags": list(self.tags),
        }
        if include_body:
            payload["body"] = self.body
        return payload


@dataclass(frozen=True)
class OkfValidationResult:
    """Result from validating an OKF bundle."""

    valid: bool
    concept_count: int
    errors: List[str]
    warnings: List[str]
    concepts: List[OkfConcept]

    def to_dict(self, *, include_body: bool = False) -> Dict[str, object]:
        """Return a JSON-serializable validation packet."""
        return {
            "valid": self.valid,
            "spec": "okf",
            "version": "0.1",
            "kind": "KnowledgeBundle",
            "concept_count": self.concept_count,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "concepts": [
                concept.to_dict(include_body=include_body) for concept in self.concepts
            ],
        }


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _concept_id(path: Path, root: Path) -> str:
    return path.relative_to(root).with_suffix("").as_posix()


def _split_frontmatter(text: str) -> Tuple[Optional[Dict[str, object]], str]:
    if not text.startswith("---\n"):
        return None, text
    marker = text.find("\n---", 4)
    if marker == -1:
        return None, text
    raw = text[4:marker]
    body_start = marker + len("\n---")
    if body_start < len(text) and text[body_start] == "\n":
        body_start += 1
    loaded = yaml.safe_load(raw) or {}
    if not isinstance(loaded, dict):
        raise ValueError("frontmatter must be a mapping")
    return dict(loaded), text[body_start:]


def _string_value(value: object) -> str:
    if isinstance(value, SCALAR_TYPES):
        return str(value)
    return ""


def _tags(value: object) -> Tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value if isinstance(item, SCALAR_TYPES))
    return ()


def _concept_from_file(path: Path, root: Path) -> OkfConcept:
    frontmatter, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    if frontmatter is None:
        raise ValueError("parseable YAML frontmatter is required")
    return OkfConcept(
        id=_concept_id(path, root),
        path=_relative_path(path, root),
        type=_string_value(frontmatter.get("type")),
        title=_string_value(frontmatter.get("title")),
        description=_string_value(frontmatter.get("description")),
        resource=_string_value(frontmatter.get("resource")),
        tags=_tags(frontmatter.get("tags")),
        body=body,
    )


def iter_okf_concept_files(bundle_dir: Union[str, Path]) -> List[Path]:
    """Return OKF concept markdown files under a bundle directory."""
    root = Path(bundle_dir)
    return sorted(
        path
        for path in root.rglob("*.md")
        if path.is_file() and path.name not in RESERVED_FILENAMES
    )


def load_okf_bundle(bundle_dir: Union[str, Path]) -> List[OkfConcept]:
    """Load all valid concept documents from an OKF bundle."""
    root = Path(bundle_dir)
    return [_concept_from_file(path, root) for path in iter_okf_concept_files(root)]


def _link_target(path: Path, root: Path, target: str) -> Optional[Path]:
    target = target.split("#", 1)[0].strip()
    if not target or "://" in target or target.startswith(("mailto:", "#")):
        return None
    if target.startswith("/"):
        return root / target.lstrip("/")
    return path.parent / target


def _validate_reserved_file(path: Path, root: Path) -> List[str]:
    rel = _relative_path(path, root)
    text = path.read_text(encoding="utf-8")
    errors: List[str] = []
    if path.name == "index.md":
        frontmatter, _body = _split_frontmatter(text)
        if frontmatter is not None and path != root / "index.md":
            errors.append(f"{rel}: frontmatter is only allowed in the root index.md")
    if path.name == "log.md":
        headings = [
            line
            for line in text.splitlines()
            if line.startswith("## ") and not DATE_HEADING_PATTERN.match(line)
        ]
        errors.extend(
            f"{rel}: invalid log date heading: {heading}" for heading in headings
        )
    return errors


def validate_okf_bundle(bundle_dir: Union[str, Path]) -> OkfValidationResult:
    """Validate an OKF v0.1 bundle with permissive-consumer semantics."""
    root = Path(bundle_dir)
    errors: List[str] = []
    warnings: List[str] = []
    concepts: List[OkfConcept] = []
    if not root.is_dir():
        return OkfValidationResult(
            valid=False,
            concept_count=0,
            errors=[f"{root}: OKF bundle directory not found"],
            warnings=[],
            concepts=[],
        )

    for path in sorted(root.rglob("*.md")):
        if path.name in RESERVED_FILENAMES:
            errors.extend(_validate_reserved_file(path, root))
            continue
        rel = _relative_path(path, root)
        try:
            concept = _concept_from_file(path, root)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{rel}: {exc}")
            continue
        if not concept.type.strip():
            errors.append(f"{rel}: frontmatter.type is required")
        concepts.append(concept)
        for match in LINK_PATTERN.finditer(concept.body):
            target_path = _link_target(path, root, match.group(1))
            if target_path is not None and not target_path.exists():
                warnings.append(f"{rel}: link target not found: {match.group(1)}")

    return OkfValidationResult(
        valid=not errors,
        concept_count=len(concepts),
        errors=errors,
        warnings=warnings,
        concepts=sorted(concepts, key=lambda concept: concept.id),
    )


def summarize_okf_bundle(bundle_dir: Union[str, Path]) -> Dict[str, object]:
    """Return a lightweight OKF bundle summary without concept bodies."""
    result = validate_okf_bundle(bundle_dir)
    return result.to_dict(include_body=False)


def import_okf_bundle(
    bundle_dir: Union[str, Path],
    output_dir: Union[str, Path],
) -> List[Path]:
    """Write OKF concepts as generation-ready Markdown source documents."""
    result = validate_okf_bundle(bundle_dir)
    if not result.valid:
        raise ValueError("; ".join(result.errors))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for concept in result.concepts:
        target = output / f"{concept.id.replace('/', '_')}.md"
        lines = [
            f"# {concept.title or concept.id}",
            "",
            f"OKF concept: {concept.id}",
            f"Type: {concept.type}",
        ]
        if concept.description:
            lines.append(f"Description: {concept.description}")
        if concept.resource:
            lines.append(f"Resource: {concept.resource}")
        lines.extend(["", concept.body.strip(), ""])
        target.write_text("\n".join(lines), encoding="utf-8")
        written.append(target)
    return written


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text or "concept"


def _yaml_block(value: Dict[str, object]) -> str:
    return yaml.safe_dump(value, sort_keys=False, allow_unicode=False).strip()


def _frontmatter(fields: Dict[str, object]) -> str:
    clean = {
        key: value
        for key, value in fields.items()
        if value not in ("", None, []) and value != {}
    }
    return "---\n" + yaml.safe_dump(clean, sort_keys=False).strip() + "\n---\n"


def _collection_label(collection: str) -> Tuple[str, str]:
    labels = {
        "productReferences": ("ODPC ProductReference", "product-references"),
        "useCases": ("ODPC UseCase", "use-cases"),
        "businessObjectives": ("ODPC BusinessObjective", "business-objectives"),
        "signals": ("ODPC Signal", "signals"),
    }
    return labels[collection]


def _item_resource(item: Dict[str, object]) -> str:
    model = item.get("productModel")
    if isinstance(model, dict):
        return _string_value(model.get("$ref") or model.get("ref"))
    return _string_value(item.get("resource"))


def _catalog_source(source: Union[str, Path]) -> Dict[str, object]:
    path = Path(source)
    if path.is_dir():
        catalog_path = path / "odpc" / "catalog.yaml"
        if not catalog_path.is_file():
            catalog_path = path / "catalog.yaml"
        return load_catalog(catalog_path)
    return load_catalog(path)


def export_okf_bundle(
    source: Union[str, Path],
    output_dir: Union[str, Path],
) -> List[Path]:
    """Export an ODPC catalog or portfolio workspace as an OKF bundle."""
    catalog = _catalog_source(source)
    catalog_root = catalog.get("catalog")
    if not isinstance(catalog_root, dict):
        raise ValueError("source must be an ODPC catalog or portfolio workspace")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    metadata = catalog_root.get("metadata")
    metadata_name = metadata.get("name") if isinstance(metadata, dict) else None
    title = text_value(metadata_name, "ODPC Catalog")
    index = output / "index.md"
    index.write_text(
        f"# {title}\n\nGenerated from ODPC catalog artifacts.\n", encoding="utf-8"
    )
    written.append(index)
    for collection in (
        "productReferences",
        "useCases",
        "businessObjectives",
        "signals",
    ):
        concept_type, folder = _collection_label(collection)
        values = catalog_root.get(collection)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            item_id = _string_value(value.get("id")) or _string_value(
                value.get("productID")
            )
            target = output / folder / f"{_slug(item_id)}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            name = text_value(value.get("name"), item_id)
            description = text_value(value.get("description"), "")
            content = _frontmatter(
                {
                    "type": concept_type,
                    "title": name,
                    "description": description,
                    "resource": _item_resource(value),
                    "tags": ["odpc", collection],
                }
            )
            content += f"\n# Summary\n\n{description or name}\n\n"
            content += "# ODPC Source\n\n```yaml\n" + _yaml_block(value) + "\n```\n"
            target.write_text(content, encoding="utf-8")
            written.append(target)
    return written
