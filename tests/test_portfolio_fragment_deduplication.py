"""Regression tests for portable portfolio fragment synchronization."""

import os

from open_data_products.portfolio import _fragment_collections


def test_fragment_collections_select_newest_duplicate_logical_id(tmp_path):
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    generated = fragments / "use_case_generated.yaml"
    curated = fragments / "use_case_curated.yaml"
    generated.write_text(
        "useCase:\n  id: UC-RETENTION\n  name:\n    en: Generated\n",
        encoding="utf-8",
    )
    curated.write_text(
        "useCase:\n  id: UC-RETENTION\n  name:\n    en: Curated\n",
        encoding="utf-8",
    )
    os.utime(generated, ns=(1, 1))
    os.utime(curated, ns=(2, 2))

    collections = _fragment_collections(fragments)

    assert collections["useCases"] == [
        {"id": "UC-RETENTION", "name": {"en": "Curated"}}
    ]
