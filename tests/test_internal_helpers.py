"""Tests for small internal SDK helpers."""

import pytest

from open_data_products._io import load_jsonl_records, load_mapping
from open_data_products._search import searchable_record_text


def test_load_mapping_reads_json_and_yaml(tmp_path):
    json_path = tmp_path / "document.json"
    yaml_path = tmp_path / "document.yaml"
    json_path.write_text('{"id": "json-doc"}', encoding="utf-8")
    yaml_path.write_text("id: yaml-doc\n", encoding="utf-8")

    assert load_mapping(json_path) == {"id": "json-doc"}
    assert load_mapping(yaml_path) == {"id": "yaml-doc"}


def test_load_mapping_rejects_non_mapping_roots(tmp_path):
    path = tmp_path / "document.yaml"
    path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="document root"):
        load_mapping(path)


def test_load_jsonl_records_reads_objects_and_reports_line_errors(tmp_path):
    path = tmp_path / "records.jsonl"
    path.write_text('{"id": "one"}\n\n[]\n', encoding="utf-8")

    with pytest.raises(ValueError, match="record is not an object"):
        load_jsonl_records(path)

    path.write_text('{"id": "one"}\n{"id": "two"}\n', encoding="utf-8")
    assert load_jsonl_records(path) == [{"id": "one"}, {"id": "two"}]


def test_searchable_record_text_flattens_nested_record_values():
    record = {
        "id": "DataProduct",
        "labels": ["analytics", "trusted"],
        "metadata": {"domain": "mobility", "owner": "platform"},
    }

    assert searchable_record_text(record) == (
        "dataproduct analytics trusted mobility platform"
    )
