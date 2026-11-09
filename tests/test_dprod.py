"""DPROD 1.0 Beta 2 interoperability coverage."""

from pathlib import Path
import hashlib
import json

import pytest

from open_data_products.cli import main

pytestmark = pytest.mark.functional

DPROD_PRODUCT = """\
@prefix dprod: <https://www.omg.org/spec/DPROD/> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix odrl: <http://www.w3.org/ns/odrl/2/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<https://example.test/products/air> a dprod:DataProduct ;
  rdfs:label "Air quality product" ;
  dct:description "Verified air-quality observations." ;
  dprod:purpose "Support environmental decisions." ;
  dprod:dataProductOwner <https://example.test/agents/environment> ;
  dprod:domain <https://example.test/domains/environment> ;
  dprod:lifecycleStatus <https://example.test/lifecycle/deploy> ;
  dprod:inputPort <https://example.test/services/input> ;
  dprod:outputPort <https://example.test/services/output> ;
  dprod:inputDataset <https://example.test/datasets/raw-air> ;
  dprod:outputDataset <https://example.test/datasets/air> ;
  odrl:hasPolicy <https://example.test/policies/air> .

<https://example.test/agents/environment> a prov:Agent ; rdfs:label "Environment Office" .
<https://example.test/lifecycle/deploy> a dprod:DataProductLifecycleStatus .
<https://example.test/policies/air> a odrl:Policy .
<https://example.test/datasets/raw-air> a dcat:Dataset ; rdfs:label "Raw air" ; dct:description "Input observations." ; dct:type "dataset" .
<https://example.test/datasets/air> a dcat:Dataset ;
  rdfs:label "Air quality" ; dct:description "Published observations." ; dct:type "dataset" ;
  dcat:distribution <https://example.test/distributions/air> ;
  dprod:informationSensitivityClassification <https://example.test/classifications/public> .
<https://example.test/classifications/public> a dprod:InformationSensitivityClassification .
<https://example.test/distributions/air> a dcat:Distribution ;
  dcat:accessService <https://example.test/services/output> ;
  dprod:isDistributionOf <https://example.test/datasets/air> ;
  dct:conformsTo <https://example.test/contracts/air> ; dct:format "CSV" .
<https://example.test/services/input> a dcat:DataService ;
  dprod:isAccessServiceOf <https://example.test/distributions/air> ;
  dprod:protocol <https://example.test/protocols/https> ;
  dprod:securitySchemaType <https://example.test/security/oauth> ;
  dcat:endpointURL <https://api.example.test/input> .
<https://example.test/services/output> a dcat:DataService ;
  dprod:isAccessServiceOf <https://example.test/distributions/air> ;
  dprod:protocol <https://example.test/protocols/https> ;
  dprod:securitySchemaType <https://example.test/security/oauth> ;
  dcat:endpointURL <https://api.example.test/air> .
<https://example.test/security/oauth> a dprod:SecuritySchemaType .
"""


def _dprod_file(tmp_path: Path, content: str = DPROD_PRODUCT) -> Path:
    """Write an isolated DPROD fixture."""
    path = tmp_path / "air-product.ttl"
    path.write_text(content, encoding="utf-8")
    return path


def test_validate_dprod_uses_pinned_beta2_shapes_and_reports_structured_failures(
    tmp_path: Path,
) -> None:
    """Validation remains local and distinguishes SHACL errors from parsing errors."""
    from open_data_products.dprod import validate_dprod

    valid = validate_dprod(str(_dprod_file(tmp_path)))
    assert valid.conforms is True
    assert valid.profile_version == "1.0 Beta 2"
    assert valid.parse_errors == []
    assert valid.violations == []

    invalid = validate_dprod(
        str(
            _dprod_file(
                tmp_path,
                DPROD_PRODUCT.replace(
                    "<https://example.test/agents/environment> ;",
                    '"not-an-agent" ;',
                ),
            )
        )
    )
    assert invalid.conforms is False
    assert invalid.parse_errors == []
    assert invalid.violations[0].property_path.endswith("dataProductOwner")
    assert invalid.violations[0].product_uri == "https://example.test/products/air"


def test_dprod_registry_verifies_bundled_normative_artifacts() -> None:
    """Pinned profile files cannot silently drift from their recorded package digests."""
    data_directory = (
        Path(__file__).resolve().parents[1] / "open_data_products" / "dprod" / "data"
    )
    registry = json.loads(
        (data_directory / "registry.json").read_text(encoding="utf-8")
    )
    for artifact in registry["artifacts"]:
        assert (
            hashlib.sha256((data_directory / artifact["file"]).read_bytes()).hexdigest()
            == artifact["bundled_sha256"]
        )
    assert (
        registry["informative_examples"]["compatibility"]
        == "unsupported-remote-context"
    )


def test_validate_dprod_rejects_development_namespace_and_unsafe_contexts(
    tmp_path: Path,
) -> None:
    """Only the pinned OMG Beta 2 namespace is accepted."""
    from open_data_products.dprod import validate_dprod

    development = _dprod_file(
        tmp_path,
        DPROD_PRODUCT.replace(
            "https://www.omg.org/spec/DPROD/", "https://www.omg.org/spec/DPROD/dprod/"
        ),
    )
    with pytest.raises(ValueError, match="Unsupported DPROD namespace"):
        validate_dprod(str(development))
    from open_data_products.dcat import discover_dcat_catalog

    with pytest.raises(ValueError, match="Unsupported DPROD namespace"):
        discover_dcat_catalog(str(development))

    unsafe = tmp_path / "unsafe.jsonld"
    unsafe.write_text(
        '{"@context":"https://example.test/context.jsonld", "@id":"https://example.test/p"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Remote JSON-LD contexts"):
        validate_dprod(str(unsafe))


def test_dprod_product_inventory_and_odps_draft_preserve_evidence_boundaries(
    tmp_path: Path,
) -> None:
    """Explicit DPROD products convert without treating ports as ODPS access profiles."""
    from open_data_products.dprod import discover_dprod_catalog, wrap_dprod_resource

    source = _dprod_file(tmp_path)
    inventory = discover_dprod_catalog(str(source))
    product = inventory.products[0]
    assert product.id == "https://example.test/products/air"
    assert product.owners == ["https://example.test/agents/environment"]
    assert product.output_ports == ["https://example.test/services/output"]
    assert product.output_datasets == ["https://example.test/datasets/air"]
    assert {item.resource_type for item in inventory.resources} >= {
        "DataProduct",
        "Dataset",
        "DataService",
        "Distribution",
        "Agent",
        "Policy",
    }
    assert {item.kind for item in inventory.relationships} >= {
        "product-owner",
        "product-output-port",
        "product-output-dataset",
        "dataset-distribution",
        "service-distribution",
    }

    wrapped = wrap_dprod_resource(str(source), product.id)
    assert wrapped.validation.valid is True
    assert wrapped.document["product"]["details"]["en"]["name"] == "Air quality product"
    assert "DPROD port" in " ".join(wrapped.warnings)
    assert any(
        item["classification"] == "conditional"
        for item in wrapped.mapping_report["mappings"]
    )
    assert "data product owner" in wrapped.missing_business_information


def test_odps_export_to_dprod_is_deterministic_and_shacl_valid(tmp_path: Path) -> None:
    """ODPS export supplies explicit semantic-loss records rather than equivalence claims."""
    from open_data_products.dprod import export_odps_to_dprod

    odps = {
        "schema": "https://opendataproducts.org/v4.2/schema/odps.json",
        "version": "4.2",
        "product": {
            "details": {
                "en": {
                    "productID": "air-quality",
                    "name": "Air quality product",
                    "description": "Verified air-quality observations.",
                    "visibility": "private",
                    "status": "draft",
                    "type": "dataset",
                }
            },
            "dataAccess": {
                "default": {
                    "outputPortType": "API",
                    "accessURL": "https://api.example.test/air",
                }
            },
        },
    }

    first = export_odps_to_dprod(odps, base_iri="https://example.test/products/")
    second = export_odps_to_dprod(odps, base_iri="https://example.test/products/")
    assert first.turtle == second.turtle
    assert first.jsonld == second.jsonld
    assert first.validation.conforms is True
    assert any(item["classification"] == "unsupported" for item in first.losses)


def test_dprod_cli_mcp_and_dcat_inventory_keep_explicit_products_distinct(
    capsys, tmp_path: Path
) -> None:
    """Each public surface exposes explicit products without recasting DCAT datasets."""
    from open_data_products.dcat import discover_dcat_catalog
    from open_data_products.mcp.server import handle

    source = _dprod_file(tmp_path)
    assert any(
        item.resource_type == "DPRODDataProduct"
        for item in discover_dcat_catalog(str(source)).resources
    )
    assert main(["portfolio", "discover-dprod", str(source), "--json"]) == 0
    assert '"products"' in capsys.readouterr().out

    response = handle(
        {
            "jsonrpc": "2.0",
            "id": "dprod-discovery",
            "method": "tools/call",
            "params": {
                "name": "discover_dprod_catalog",
                "arguments": {"source": str(source)},
            },
        }
    )
    assert response is not None
    payload = response["result"]["content"][0]["text"]
    assert "Air quality product" in payload
    assert str(source.parent) not in payload


def test_dprod_validation_and_export_are_available_in_cli_and_mcp(
    capsys, tmp_path: Path
) -> None:
    """Validation is safe while the deterministic RDF export writes explicit files."""
    from open_data_products.mcp.server import handle
    import yaml

    source = _dprod_file(tmp_path)
    assert main(["dprod-validate", str(source), "--json"]) == 0
    assert '"conforms": true' in capsys.readouterr().out
    response = handle(
        {
            "jsonrpc": "2.0",
            "id": "dprod-validation",
            "method": "tools/call",
            "params": {"name": "validate_dprod", "arguments": {"source": str(source)}},
        }
    )
    assert response is not None
    assert '"conforms": true' in response["result"]["content"][0]["text"]

    odps_path = tmp_path / "product.yaml"
    odps_path.write_text(
        yaml.safe_dump(
            {
                "schema": "https://opendataproducts.org/v4.2/schema/odps.json",
                "version": "4.2",
                "product": {
                    "details": {
                        "en": {
                            "productID": "air",
                            "name": "Air",
                            "visibility": "private",
                            "status": "draft",
                            "type": "dataset",
                        }
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "export"
    assert (
        main(
            [
                "product",
                "export-dprod",
                "--input",
                str(odps_path),
                "--output",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    assert output.with_suffix(".ttl").is_file()
    assert output.with_suffix(".jsonld").is_file()


def test_dprod_identity_precedes_dcat_dataset_and_invalid_source_cannot_wrap(
    tmp_path: Path,
) -> None:
    """An explicit DPROD product is never silently converted as a DCAT dataset."""
    from open_data_products.dcat import discover_dcat_catalog, wrap_dcat_resource
    from open_data_products.dprod import wrap_dprod_resource

    (tmp_path / "a-dataset.ttl").write_text(
        """@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct: <http://purl.org/dc/terms/> .
<https://example.test/products/air> a dcat:Dataset ; dct:title "Air" .
""",
        encoding="utf-8",
    )
    product = tmp_path / "b-product.ttl"
    product.write_text(DPROD_PRODUCT, encoding="utf-8")
    result = discover_dcat_catalog(str(tmp_path))
    assert (
        next(
            item
            for item in result.resources
            if item.id == "https://example.test/products/air"
        ).resource_type
        == "DPRODDataProduct"
    )
    with pytest.raises(ValueError, match="Only Dataset"):
        wrap_dcat_resource(str(tmp_path), "https://example.test/products/air")

    invalid = DPROD_PRODUCT.replace(
        "<https://example.test/agents/environment> ;", '"not-an-agent" ;'
    )
    invalid_path = _dprod_file(tmp_path, invalid)
    with pytest.raises(ValueError, match="does not conform"):
        wrap_dprod_resource(str(invalid_path), "https://example.test/products/air")
