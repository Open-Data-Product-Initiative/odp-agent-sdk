"""Tests for the Open Data Products SDK namespace layout."""

import importlib.util


def test_public_spec_namespaces_are_importable():
    from open_data_products import odpc, odpg, odps, odpv

    assert odps.SPEC_ID == "odps"
    assert odpc.SPEC_ID == "odpc"
    assert odpg.SPEC_ID == "odpg"
    assert odpv.SPEC_ID == "odpv"


def test_top_level_package_exposes_version_alias():
    import open_data_products

    assert isinstance(open_data_products.__version__, str)
    assert open_data_products.__version__
    assert open_data_products.version == open_data_products.__version__


def test_odps_namespace_exports_existing_api():
    from open_data_products.odps import OpenDataProduct
    from open_data_products.odps.core import OpenDataProduct as CoreOpenDataProduct

    assert OpenDataProduct is CoreOpenDataProduct


def test_top_level_package_does_not_export_odps_specific_models():
    import open_data_products

    assert not hasattr(open_data_products, "OpenDataProduct")


def test_legacy_odps_package_is_not_part_of_the_sdk():
    assert importlib.util.find_spec("odps") is None
