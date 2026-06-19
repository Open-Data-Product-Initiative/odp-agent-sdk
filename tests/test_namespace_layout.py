"""Tests for the Open Data Products SDK namespace layout."""

import ast
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_public_spec_namespaces_are_importable():
    from open_data_products import odpc, odpg, odpr, odps, odpv

    assert odps.SPEC_ID == "odps"
    assert odpc.SPEC_ID == "odpc"
    assert odpg.SPEC_ID == "odpg"
    assert odpr.SPEC_ID == "odpr"
    assert odpv.SPEC_ID == "odpv"


def test_top_level_package_exposes_version_alias():
    import open_data_products

    assert isinstance(open_data_products.__version__, str)
    assert open_data_products.__version__
    assert open_data_products.version == open_data_products.__version__


def test_top_level_package_exposes_stable_workflow_facades():
    import open_data_products
    from open_data_products import agent, generation, odpr, portfolio
    from open_data_products.contracts import product as contracts_product
    from open_data_products.odpc import catalog as odpc_catalog
    from open_data_products.odpg import graph as odpg_graph
    from open_data_products.odpv import vocabulary as odpv_vocabulary

    assert "validate_document" in open_data_products.__all__
    assert open_data_products.validate_document is agent.validate_document
    assert open_data_products.build_catalog is odpc_catalog.build_catalog
    assert open_data_products.build_graph is odpg_graph.build_graph
    assert open_data_products.resolve_vocabulary_term is (
        odpv_vocabulary.resolve_vocabulary_term
    )
    assert open_data_products.generate_local_artifacts_for_kind is (
        generation.generate_local_artifacts_for_kind
    )
    assert open_data_products.build_portfolio is portfolio.build_portfolio
    assert open_data_products.validate_recipe is odpr.validate_recipe
    assert open_data_products.generate_product_contract_report is (
        contracts_product.generate_product_contract_report
    )


def test_odps_namespace_exports_existing_api():
    from open_data_products.odps import OpenDataProduct
    from open_data_products.odps.core import OpenDataProduct as CoreOpenDataProduct

    assert OpenDataProduct is CoreOpenDataProduct


def test_top_level_package_does_not_export_odps_specific_models():
    import open_data_products

    assert not hasattr(open_data_products, "OpenDataProduct")


def test_legacy_odps_package_is_not_part_of_the_sdk():
    assert importlib.util.find_spec("odps") is None


def test_cli_uses_concrete_generation_namespace_internally():
    """Guard internal CLI imports from routing through the root package facade."""
    cli_path = REPO_ROOT / "open_data_products" / "cli.py"
    tree = ast.parse(cli_path.read_text(encoding="utf-8"))

    root_generation_imports = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is None
        and node.level == 1
        and any(alias.name == "generation" for alias in node.names)
    ]

    assert root_generation_imports == []


def test_mcp_tools_use_concrete_modules_internally():
    """Guard MCP handlers from depending on the root public API barrel."""
    tools_path = REPO_ROOT / "open_data_products" / "mcp" / "tools.py"
    tree = ast.parse(tools_path.read_text(encoding="utf-8"))

    parent_barrel_imports = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is None and node.level == 2
    ]

    assert parent_barrel_imports == []
