"""Tests for ODPV vocabulary SDK helpers."""

import json
from pathlib import Path

from open_data_products.odpv import (
    build_artifacts,
    search_vocabulary,
    validate_vocabulary,
    write_artifacts,
)


def test_validate_vocabulary_reports_expected_counts():
    result = validate_vocabulary()

    assert result.valid is True
    assert result.term_count == 59
    assert result.relationship_count == 16
    assert result.section_count == 4
    assert result.errors == []


def test_validate_vocabulary_reports_invalid_section_terms_array():
    vocabulary = {
        "id": "ODPV",
        "version": "1.0",
        "sections": [
            {"id": "core", "name": {"en": "Core"}, "terms": "not-a-list"},
            {"id": "value", "name": {"en": "Value"}, "terms": []},
            {"id": "governance", "name": {"en": "Governance"}, "terms": []},
            {"id": "relationships", "name": {"en": "Relationships"}, "terms": []},
        ],
    }

    result = validate_vocabulary(vocabulary)

    assert result.valid is False
    assert "Section core terms must be an array" in result.errors


def test_search_vocabulary_returns_alias_and_example_matches():
    matches = search_vocabulary(
        "customer churn reusable data offering",
        limit=3,
    )

    assert len(matches) >= 1
    assert matches[0]["id"] == "DataProduct"
    assert "uri" in matches[0]
    assert "score" in matches[0]
    assert "matchedFields" in matches[0]


def test_build_artifacts_returns_package_artifact_contents():
    artifacts = build_artifacts()

    assert "odpv.json" in artifacts
    assert "terms.jsonl" in artifacts
    assert "core.yaml" in artifacts
    assert json.loads(artifacts["odpv.json"])["id"] == "ODPV"
    assert len([line for line in artifacts["terms.jsonl"].splitlines() if line]) == 59


def test_write_artifacts_can_check_and_generate_to_target_directory(tmp_path):
    changed = write_artifacts(tmp_path, check=True)

    assert sorted(changed) == [
        Path("core.yaml"),
        Path("governance.yaml"),
        Path("odpv.json"),
        Path("relationships.yaml"),
        Path("terms.jsonl"),
        Path("value.yaml"),
    ]

    written = write_artifacts(tmp_path)
    assert written == changed

    assert write_artifacts(tmp_path, check=True) == []
