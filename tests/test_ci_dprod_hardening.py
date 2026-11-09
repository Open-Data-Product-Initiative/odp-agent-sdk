"""CI guardrails for DPROD cross-engine and installed-wheel verification."""

from pathlib import Path


def test_ci_cross_checks_dprod_export_with_verified_apache_jena() -> None:
    """CI uses an independently implemented SHACL validator for exported RDF."""
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "JENA_VERSION: 6.2.0" in workflow
    assert "apache-jena-${JENA_VERSION}.tar.gz" in workflow
    assert "sha512sum -c" in workflow
    assert 'bin/shacl" validate' in workflow
    assert "export_odps_to_dprod" in workflow


def test_ci_jena_validation_is_independent_of_remote_ontology_imports() -> None:
    """Jena validates local shapes without relying on ontology-host redirects."""
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "dprod-shapes-no-imports.ttl" in workflow
    assert 'if "owl:imports" not in line' in workflow


def test_ci_wheel_smoke_loads_packaged_dprod_and_dcat_features() -> None:
    """The installed-wheel check exercises packaged DPROD and DCAT features."""
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "from open_data_products.dprod import export_odps_to_dprod" in workflow
    assert "dprod_export.validation.conforms" in workflow
    assert "from open_data_products.dcat import discover_dcat_catalog" in workflow
    assert "dcat_inventory = discover_dcat_catalog" in workflow


def test_ci_wheel_smoke_exercises_stdio_mcp_transport() -> None:
    """The installed distribution starts the MCP JSON-RPC process itself."""
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert '"-m", "open_data_products.mcp.server"' in workflow
    assert "subprocess.run(" in workflow
