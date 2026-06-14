"""Tests for small internal SDK helpers."""

import pytest

from open_data_products._io import load_jsonl_records, load_mapping
from open_data_products._search import searchable_record_text
from open_data_products.odps._normalization import (
    ODPS_DATA_QUALITY_DIMENSION_ALIASES,
    ODPS_DATA_QUALITY_DIMENSIONS,
    ODPS_DATA_QUALITY_UNITS,
    ODPS_SLA_DIMENSION_ALIASES,
    ODPS_SLA_DIMENSIONS,
    ODPS_SLA_UNITS,
    normalize_odps_dimension,
)


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


def test_normalize_odps_dimension_handles_shared_aliases_and_units():
    sla_dimension = normalize_odps_dimension(
        {"name": "refreshTimeliness", "objective": 2, "unit": "hours"},
        allowed_dimensions=ODPS_SLA_DIMENSIONS,
        dimension_aliases=ODPS_SLA_DIMENSION_ALIASES,
        allowed_units=ODPS_SLA_UNITS,
        keep_description=False,
        stringify_objective=True,
    )

    quality_dimension = normalize_odps_dimension(
        {
            "dimension": "reconciliation",
            "displayTitle": "Source Reconciliation",
            "objective": "98",
            "unit": "percentage",
            "description": "CRM and billing counts reconcile.",
        },
        allowed_dimensions=ODPS_DATA_QUALITY_DIMENSIONS,
        dimension_aliases=ODPS_DATA_QUALITY_DIMENSION_ALIASES,
        allowed_units=ODPS_DATA_QUALITY_UNITS,
        keep_description=True,
        stringify_objective=False,
    )

    assert sla_dimension == {
        "dimension": "updateFrequency",
        "objective": "120",
        "unit": "minutes",
    }
    assert quality_dimension == {
        "dimension": "consistency",
        "objective": "98",
        "unit": "percentage",
        "displayTitle": "Source Reconciliation",
        "description": "CRM and billing counts reconcile.",
    }
