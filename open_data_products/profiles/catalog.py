"""Versioned interoperability profile catalog and validation helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Union

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from ..odpv.vocabulary import iter_terms, load_vocabulary, validate_vocabulary

_RELEASES = {
    "1.0.0": {
        "base_uri": "https://opendataproducts.org/odpv-v1.0/",
        "status": "stable",
        "vocabulary": "vocab/odpv.yaml",
    },
    "1.1.0": {
        "base_uri": "https://opendataproducts.org/odpv-v1.1/",
        "status": "draft",
        "vocabulary": "v1_1/vocab/odpv.yaml",
    },
}
_PROFILE_FILES = {
    "ODPV-DCAT-3": "dcat-3.yaml",
    "ODPV-ODCS-3": "odcs-3.yaml",
    "ODPV-OPENLINEAGE-1": "openlineage-1.yaml",
    "ODPV-PROV-O": "prov-o.yaml",
    "ODPV-ODRL-2": "odrl-2.yaml",
}


@dataclass(frozen=True)
class VocabularyRef:
    """Immutable identity of one ODPV vocabulary release."""

    id: str
    version: str
    base_uri: str
    status: str

    def to_dict(self) -> Dict[str, str]:
        """Return the public vocabulary identity."""
        return {
            "id": self.id,
            "version": self.version,
            "baseUri": self.base_uri,
            "status": self.status,
        }


@dataclass(frozen=True)
class ProfileRef:
    """Immutable identity of one ODPV interoperability profile."""

    id: str
    version: str
    vocabulary: VocabularyRef

    def to_dict(self) -> Dict[str, Any]:
        """Return the public profile identity."""
        return {
            "id": self.id,
            "version": self.version,
            "vocabulary": self.vocabulary.to_dict(),
        }


@dataclass(frozen=True)
class MappingResult:
    """One mapping with its scope, lifecycle, and evidence provenance."""

    profile: ProfileRef
    profile_status: str
    content_digest: str
    mapping_id: str
    mapping_kind: str
    mapping_status: str
    odpv_term: str
    external_reference: str
    rationale: str
    evidence: str
    relation: Optional[str] = None
    direction: Optional[str] = None
    implementation_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-safe mapping provenance."""
        payload: Dict[str, Any] = {
            "profile": self.profile.to_dict(),
            "profileStatus": self.profile_status,
            "contentDigest": self.content_digest,
            "mappingId": self.mapping_id,
            "mappingKind": self.mapping_kind,
            "mappingStatus": self.mapping_status,
            "odpvTerm": self.odpv_term,
            "externalReference": self.external_reference,
            "rationale": self.rationale,
            "evidence": self.evidence,
        }
        if self.relation:
            payload["relation"] = self.relation
        if self.direction:
            payload["direction"] = self.direction
        if self.implementation_notes:
            payload["implementationNotes"] = self.implementation_notes
        return payload


@dataclass(frozen=True)
class ProfileValidationResult:
    """Result of validating a version-pinned ODPV profile."""

    valid: bool
    errors: List[str]
    warnings: List[str]
    profile: Optional[ProfileRef]
    content_digest: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-safe profile validation output."""
        return {
            "valid": self.valid,
            "spec": "odpv",
            "kind": "InteroperabilityProfile",
            "errors": self.errors,
            "warnings": self.warnings,
            "profile": self.profile.to_dict() if self.profile else None,
            "contentDigest": self.content_digest,
        }


@dataclass(frozen=True)
class Profile:
    """Loaded, validated ODPV interoperability profile."""

    ref: ProfileRef
    status: str
    content_digest: str
    data: Dict[str, Any]

    def mappings(self) -> Sequence[MappingResult]:
        """Return mappings with complete profile provenance."""
        return tuple(
            _mapping_result(self, mapping) for mapping in self.data["mappings"]
        )


def _data_path(relative: str) -> Path:
    return Path(__file__).resolve().parents[1] / "odpv" / "data" / relative


def vocabulary_ref(version: str = "1.0.0") -> VocabularyRef:
    """Return the immutable reference for a bundled ODPV release."""
    try:
        release = _RELEASES[version]
    except KeyError as error:
        raise ValueError("Unsupported ODPV vocabulary version: %s" % version) from error
    return VocabularyRef(
        id="ODPV",
        version=version,
        base_uri=str(release["base_uri"]),
        status=str(release["status"]),
    )


def list_vocabulary_releases() -> List[Dict[str, str]]:
    """List bundled ODPV releases without selecting a draft."""
    return [vocabulary_ref(version).to_dict() for version in sorted(_RELEASES)]


def load_vocabulary_release(
    reference: Union[VocabularyRef, str] = "1.0.0",
) -> Dict[str, Any]:
    """Load the vocabulary selected by an explicit immutable reference."""
    ref = vocabulary_ref(reference) if isinstance(reference, str) else reference
    expected = vocabulary_ref(ref.version)
    if ref != expected:
        raise ValueError("Vocabulary reference does not match the bundled release")
    if ref.version == "1.0.0":
        return load_vocabulary()
    path = _data_path(str(_RELEASES[ref.version]["vocabulary"]))
    with path.open(encoding="utf-8") as source:
        return yaml.safe_load(source)


def validate_vocabulary_release(
    reference: Union[VocabularyRef, str] = "1.0.0",
) -> Dict[str, Any]:
    """Validate one selected bundled vocabulary against its release schema."""
    ref = vocabulary_ref(reference) if isinstance(reference, str) else reference
    vocabulary = load_vocabulary_release(ref)
    if ref.version == "1.0.0":
        result = validate_vocabulary(vocabulary).to_dict()
        result["version"] = ref.version
        return result
    schema = json.loads(
        _data_path("v1_1/schema/odpv.schema.json").read_text(encoding="utf-8")
    )
    errors = [
        "%s: %s" % ("/".join(str(part) for part in error.path) or "$", error.message)
        for error in Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(vocabulary)
    ]
    return {
        "valid": not errors,
        "spec": "odpv",
        "kind": "Vocabulary",
        "version": ref.version,
        "errors": errors,
        "warnings": ["Vocabulary status is draft."] if ref.status == "draft" else [],
    }


def profile_ref(
    profile_id: str,
    profile_version: str,
    vocabulary: Union[VocabularyRef, str] = "1.1.0",
) -> ProfileRef:
    """Create an exact, version-pinned ODPV profile reference."""
    return ProfileRef(
        id=profile_id,
        version=profile_version,
        vocabulary=(
            vocabulary_ref(vocabulary) if isinstance(vocabulary, str) else vocabulary
        ),
    )


def _profile_source(reference: ProfileRef) -> bytes:
    if reference.id not in _PROFILE_FILES:
        raise ValueError("Unsupported ODPV profile: %s" % reference.id)
    if reference.vocabulary.version != "1.1.0":
        raise ValueError("ODPV profiles require vocabulary version 1.1.0")
    return _data_path("v1_1/profiles/%s" % _PROFILE_FILES[reference.id]).read_bytes()


def _profile_schema() -> Dict[str, Any]:
    return json.loads(_data_path("v1_1/schema/odpv.profile.schema.json").read_text())


def _parse_profile(source: bytes) -> Dict[str, Any]:
    data = yaml.safe_load(source)
    if not isinstance(data, dict):
        raise ValueError("ODPV profile must be a YAML object")
    return data


def _profile_identity(data: Dict[str, Any]) -> Optional[ProfileRef]:
    vocabulary = data.get("vocabulary")
    if not isinstance(vocabulary, dict):
        return None
    try:
        ref = vocabulary_ref(str(vocabulary.get("version")))
    except ValueError:
        return None
    if vocabulary.get("id") != ref.id or vocabulary.get("baseUri") != ref.base_uri:
        return None
    profile_id = data.get("id")
    version = data.get("version")
    if not isinstance(profile_id, str) or not isinstance(version, str):
        return None
    return ProfileRef(profile_id, version, ref)


def validate_profile_data(
    data: Dict[str, Any], *, content_digest: Optional[str] = None
) -> ProfileValidationResult:
    """Validate profile structure, vocabulary identity, and mapping terms."""
    errors = [
        "%s: %s" % ("/".join(str(part) for part in error.path) or "$", error.message)
        for error in Draft202012Validator(
            _profile_schema(), format_checker=FormatChecker()
        ).iter_errors(data)
    ]
    reference = _profile_identity(data)
    if reference is None:
        errors.append("Profile vocabulary id, version, or baseUri is unsupported.")
    else:
        vocabulary = load_vocabulary_release(reference.vocabulary)
        vocabulary_validation = validate_vocabulary_release(reference.vocabulary)
        errors.extend(
            "Vocabulary: %s" % error for error in vocabulary_validation["errors"]
        )
        valid_terms = {term["id"] for _, term in iter_terms(vocabulary)}
        mappings = data.get("mappings", [])
        mapping_ids = [
            mapping.get("id") for mapping in mappings if isinstance(mapping, dict)
        ]
        duplicates = sorted(
            {
                mapping_id
                for mapping_id in mapping_ids
                if mapping_ids.count(mapping_id) > 1
            }
        )
        for mapping_id in duplicates:
            errors.append("Duplicate mapping id: %s" % mapping_id)
        for mapping in mappings:
            if isinstance(mapping, dict) and mapping.get("odpvTerm") not in valid_terms:
                errors.append(
                    "%s: unknown ODPV term %s"
                    % (mapping.get("id", "<unknown>"), mapping.get("odpvTerm"))
                )
    warnings = []
    if data.get("status") in ("draft", "deprecated"):
        warnings.append("Profile status is %s." % data["status"])
    for mapping in data.get("mappings", []):
        if isinstance(mapping, dict) and mapping.get("status") in (
            "draft",
            "deprecated",
        ):
            warnings.append(
                "Mapping %s status is %s."
                % (mapping.get("id", "<unknown>"), mapping["status"])
            )
    return ProfileValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        profile=reference,
        content_digest=content_digest,
    )


def validate_profile(reference: ProfileRef) -> ProfileValidationResult:
    """Validate one bundled ODPV profile without activating it."""
    source = _profile_source(reference)
    digest = hashlib.sha256(source).hexdigest()
    result = validate_profile_data(_parse_profile(source), content_digest=digest)
    if result.profile != reference:
        return ProfileValidationResult(
            valid=False,
            errors=result.errors
            + ["Profile id or version does not match the request."],
            warnings=result.warnings,
            profile=result.profile,
            content_digest=digest,
        )
    return result


def load_profile(reference: ProfileRef, *, allow_draft: bool = False) -> Profile:
    """Load a validated profile after an explicit draft opt-in."""
    validation = validate_profile(reference)
    if not validation.valid:
        raise ValueError("Invalid ODPV profile: %s" % "; ".join(validation.errors))
    if validation.profile is None or validation.content_digest is None:
        raise ValueError("Profile identity could not be established")
    data = _parse_profile(_profile_source(reference))
    if data["status"] == "retired":
        raise ValueError("Retired ODPV profiles require a compatibility override")
    if data["status"] in ("draft", "deprecated") and not allow_draft:
        raise ValueError("Draft or deprecated ODPV profiles require allow_draft=True")
    return Profile(reference, str(data["status"]), validation.content_digest, data)


def _mapping_result(profile: Profile, mapping: Dict[str, Any]) -> MappingResult:
    return MappingResult(
        profile=profile.ref,
        profile_status=profile.status,
        content_digest=profile.content_digest,
        mapping_id=str(mapping["id"]),
        mapping_kind=str(mapping["kind"]),
        mapping_status=str(mapping["status"]),
        odpv_term=str(mapping["odpvTerm"]),
        external_reference=str(mapping["externalReference"]),
        rationale=str(mapping["rationale"]),
        evidence=str(mapping["evidence"]),
        relation=mapping.get("relation"),
        direction=mapping.get("direction"),
        implementation_notes=mapping.get("implementationNotes"),
    )


def resolve_mapping(
    reference: ProfileRef,
    *,
    odpv_term: Optional[str] = None,
    external_reference: Optional[str] = None,
    allow_draft: bool = False,
) -> List[MappingResult]:
    """Resolve exact ODPV or external references within one profile scope."""
    if not odpv_term and not external_reference:
        raise ValueError("Specify odpv_term or external_reference")
    profile = load_profile(reference, allow_draft=allow_draft)
    return [
        mapping
        for mapping in profile.mappings()
        if (odpv_term is None or mapping.odpv_term == odpv_term)
        and (
            external_reference is None
            or mapping.external_reference == external_reference
        )
    ]


def explain_mapping(
    reference: ProfileRef, mapping_id: str, *, allow_draft: bool = False
) -> MappingResult:
    """Return one exact mapping with its provenance and lifecycle status."""
    profile = load_profile(reference, allow_draft=allow_draft)
    for mapping in profile.mappings():
        if mapping.mapping_id == mapping_id:
            return mapping
    raise KeyError("Unknown ODPV profile mapping: %s" % mapping_id)


def conformance_report(
    profile: Profile,
    *,
    operation: str,
    mappings: Sequence[MappingResult] = (),
    source_reference: Optional[str] = None,
    target_reference: Optional[str] = None,
    warnings: Sequence[str] = (),
) -> Dict[str, Any]:
    """Build an evidence-rich review report for a profile operation."""
    report_warnings = list(warnings)
    if profile.status == "draft":
        report_warnings.append("Profile is draft and is not stable conformance.")
    for mapping in mappings:
        if mapping.mapping_status != "reviewed":
            report_warnings.append(
                "Mapping %s status is %s."
                % (mapping.mapping_id, mapping.mapping_status)
            )
        if mapping.mapping_kind != "semanticMapping":
            report_warnings.append(
                "Mapping %s is %s, not a semantic equivalence claim."
                % (mapping.mapping_id, mapping.mapping_kind)
            )
        elif mapping.relation != "exactMatch":
            report_warnings.append(
                "Mapping %s is %s and must remain qualified."
                % (mapping.mapping_id, mapping.relation)
            )
    return {
        "spec": "odpv",
        "kind": "InteroperabilityConformanceReport",
        "operation": operation,
        "profile": profile.ref.to_dict(),
        "profileStatus": profile.status,
        "contentDigest": profile.content_digest,
        "mappings": [mapping.to_dict() for mapping in mappings],
        "sourceReference": source_reference,
        "targetReference": target_reference,
        "warnings": report_warnings,
    }


def transform(
    reference: ProfileRef,
    mapping_id: str,
    direction: str,
    source_document: Dict[str, Any],
    *,
    allow_draft: bool = False,
) -> Dict[str, Any]:
    """Transform one mapping through its profile's bounded adapter."""
    mapping = explain_mapping(reference, mapping_id, allow_draft=allow_draft)
    if mapping.mapping_kind != "transformation":
        raise ValueError("Mapping %s is not a transformation" % mapping_id)
    if mapping.direction not in ("bidirectional", direction):
        raise ValueError("Mapping %s does not support %s" % (mapping_id, direction))
    profile = load_profile(reference, allow_draft=allow_draft)
    selected = {mapping_id}
    selected.update(
        item.mapping_id
        for item in profile.mappings()
        if item.mapping_kind == "semanticMapping"
    )
    result = transform_profile(
        reference,
        direction,
        source_document,
        allow_draft=allow_draft,
        mapping_ids=selected,
    )
    return {
        **result,
        "direction": direction,
        "implementationNotes": mapping.implementation_notes,
    }


def transform_profile(
    reference: ProfileRef,
    direction: str,
    source_document: Dict[str, Any],
    *,
    allow_draft: bool = False,
    mapping_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Transform one bounded document through all applicable profile mappings."""
    from .adapters import transform_profile_document

    profile = load_profile(reference, allow_draft=allow_draft)
    raw = transform_profile_document(profile, direction, source_document, mapping_ids)
    mapping_index = {mapping.mapping_id: mapping for mapping in profile.mappings()}
    used_mapping_ids = set(raw["transformations"]["executed"])
    used_mapping_ids.update(
        item["mappingId"]
        for category in ("skipped", "refused")
        for item in raw["transformations"][category]
        if item["mappingId"] in mapping_index
    )
    mappings = tuple(
        mapping_index[mapping_id] for mapping_id in sorted(used_mapping_ids)
    )
    warnings = [
        "Transformation %s: %s" % (item["mappingId"], item["reason"])
        for category in ("skipped", "refused")
        for item in raw["transformations"][category]
    ]
    source_reference = source_document.get("reference")
    if not isinstance(source_reference, str):
        source_reference = source_document.get("id")
    target_reference = (
        raw["output"].get("reference") if isinstance(raw["output"], dict) else None
    )
    if not isinstance(target_reference, str):
        target_reference = None
    return {
        **conformance_report(
            profile,
            operation="transform",
            mappings=mappings,
            source_reference=source_reference,
            target_reference=target_reference,
            warnings=warnings,
        ),
        **raw,
        "direction": direction,
    }
