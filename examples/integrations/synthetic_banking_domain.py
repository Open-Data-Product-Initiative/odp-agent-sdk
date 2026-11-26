"""Review and move the recorded synthetic banking catalog to Banking."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote, urlencode
from uuid import UUID

from examples.integrations.synthetic_banking_plan import LINKS
from examples.integrations.synthetic_banking_seed import (
    _digest,
    _request_write,
    _save,
    load_referenced_env,
)
from open_data_products.integrations import (
    IntegrationError,
    OpenMetadataAdapter,
    load_integration_config,
)

DOMAIN = "Banking"
KINDS = {
    "service": "databaseService",
    "database": "database",
    "databaseSchema": "databaseSchema",
    "table": "table",
    "dataProduct": "dataProduct",
}


def _one_page(adapter, path, expected_count):
    result = adapter._json(path)
    data, paging = result.get("data"), result.get("paging")
    if (
        not isinstance(data, list)
        or not isinstance(paging, dict)
        or paging.get("after")
        or paging.get("total") != expected_count
        or len(data) != expected_count
    ):
        raise IntegrationError(
            "Hierarchy or asset listing is incomplete or changed: " + path.split("?")[0]
        )
    return data


def _product_assets(adapter, product, expected_count):
    return _one_page(
        adapter,
        "dataProducts/" + quote(product["id"], safe="") + "/assets?limit=100",
        expected_count,
    )


def inspect_catalog(
    adapter, manifest_path, *, expected_domain=None, require_links=True
):
    """Read only the seed-owned entities and their association graph."""
    path = Path(manifest_path)
    seed = json.loads(path.read_text(encoding="utf-8"))
    destination = hashlib.sha256(adapter.profile.base_url.encode()).hexdigest()
    if (
        seed.get("format") != "synthetic-banking-seed-v1"
        or seed.get("status") != "created"
        or seed.get("destination_sha256") != destination
    ):
        raise IntegrationError(
            "Seed manifest is incomplete or belongs to another destination"
        )
    records = [x for x in seed.get("created", []) if x.get("kind") in KINDS]
    if len(records) != 16 or len({x.get("id") for x in records}) != 16:
        raise IntegrationError("Expected exactly sixteen distinct seed-owned entities")
    counts = {kind: sum(1 for x in records if x["kind"] == kind) for kind in KINDS}
    if counts != {
        "service": 1,
        "database": 1,
        "databaseSchema": 1,
        "table": 7,
        "dataProduct": 6,
    }:
        raise IntegrationError("Unexpected seed entity counts")
    expected_paths = {
        "service": "services/databaseServices",
        "database": "databases",
        "databaseSchema": "databaseSchemas",
        "table": "tables",
        "dataProduct": "dataProducts",
    }
    roots = {
        "service": "sdk_synthetic_banking",
        "database": "sdk_synthetic_banking.synthetic_bank",
        "databaseSchema": "sdk_synthetic_banking.synthetic_bank.sdk_test",
    }
    for item in records:
        if item.get("path") != expected_paths[item["kind"]]:
            raise IntegrationError("Seed entity endpoint does not match its type")
        if item["kind"] in roots and item.get("fqn") != roots[item["kind"]]:
            raise IntegrationError("Seed hierarchy is outside the synthetic namespace")
        if item["kind"] == "table" and not str(item.get("fqn", "")).startswith(
            roots["databaseSchema"] + "."
        ):
            raise IntegrationError("Table is outside the synthetic namespace")
        if item["kind"] == "dataProduct" and not str(item.get("fqn", "")).startswith(
            "sdk_synthetic_"
        ):
            raise IntegrationError("Product is outside the synthetic namespace")
    tables = {x["fqn"].rsplit(".", 1)[-1]: x for x in records if x["kind"] == "table"}
    products = {
        x["fqn"][len("sdk_synthetic_") :].replace("_", "-"): x
        for x in records
        if x["kind"] == "dataProduct"
    }
    if set(products) != set(LINKS) or set(tables) != {
        name for items in LINKS.values() for name in items
    }:
        raise IntegrationError(
            "Seed identities do not match the known synthetic catalog"
        )
    hierarchy = [
        ("databases", {"service": "sdk_synthetic_banking"}, "database"),
        (
            "databaseSchemas",
            {"database": "sdk_synthetic_banking.synthetic_bank"},
            "databaseSchema",
        ),
        (
            "tables",
            {"databaseSchema": "sdk_synthetic_banking.synthetic_bank.sdk_test"},
            "table",
        ),
    ]
    for endpoint, filters, kind in hierarchy:
        expected = {x["id"] for x in records if x["kind"] == kind}
        actual = _one_page(
            adapter,
            endpoint + "?" + urlencode({**filters, "limit": 100}),
            len(expected),
        )
        if {x.get("id") for x in actual} != expected:
            raise IntegrationError(
                "Foreign or missing entities in the synthetic hierarchy"
            )
    entities = []
    for record in records:
        identifier = str(UUID(record["id"]))
        fields = "domains,dataProducts" if record["kind"] == "table" else "domains"
        item = adapter._json(
            record["path"] + "/" + identifier + "?" + urlencode({"fields": fields})
        )
        if (
            item.get("id") != identifier
            or item.get("fullyQualifiedName") != record["fqn"]
            or "Synthetic" not in str(item.get("description", ""))
        ):
            raise IntegrationError("A seed entity identity or synthetic label changed")
        domains = item.get("domains", [])
        if domains is None:
            domains = []
        if not isinstance(domains, list):
            raise IntegrationError("Entity domain state is unavailable")
        names = sorted(
            x.get("fullyQualifiedName") or x.get("name")
            for x in domains
            if isinstance(x, dict)
        )
        if expected_domain is not None and names != [expected_domain]:
            raise IntegrationError(
                "Entity is not in the expected domain: " + record["fqn"]
            )
        if expected_domain is None and names not in ([], ["SDKIntegrationTest"]):
            raise IntegrationError("Unexpected existing domain on " + record["fqn"])
        entities.append(
            {
                "kind": record["kind"],
                "type": KINDS[record["kind"]],
                "id": identifier,
                "fqn": record["fqn"],
                "version": item.get("version"),
                "domains": names,
            }
        )
        if record["kind"] == "table":
            linked = item.get("dataProducts", []) or []
            if not isinstance(linked, list) or any(
                not isinstance(x, dict) for x in linked
            ):
                raise IntegrationError("Table product references are unavailable")
            expected = {
                products[slug]["id"]
                for slug, assets in LINKS.items()
                if record["fqn"].rsplit(".", 1)[-1] in assets
            }
            actual = {x.get("id") for x in linked}
            if not actual <= expected or (require_links and actual != expected):
                raise IntegrationError(
                    "Table has foreign or missing product links: " + record["fqn"]
                )
    links = []
    for slug, product in sorted(products.items()):
        expected = {tables[name]["id"] for name in LINKS[slug]}
        page = adapter._json(
            "dataProducts/" + quote(product["id"], safe="") + "/assets?limit=100"
        )
        assets, paging = page.get("data"), page.get("paging")
        if (
            not isinstance(assets, list)
            or not isinstance(paging, dict)
            or paging.get("after")
            or paging.get("total") != len(assets)
        ):
            raise IntegrationError("Product asset page is incomplete")
        actual = {
            x.get("id")
            for x in assets
            if isinstance(x, dict) and x.get("type") == "table"
        }
        if (
            len(actual) != len(assets)
            or not actual <= expected
            or (require_links and actual != expected)
        ):
            raise IntegrationError(
                "Product has foreign or missing asset links: " + product["fqn"]
            )
        links.append(
            {
                "product_id": product["id"],
                "product_name": product["fqn"],
                "asset_ids": sorted(expected),
                "actual_asset_ids": sorted(actual),
            }
        )
    lineage_records = [x for x in seed["created"] if x.get("kind") == "lineage"]
    table_ids = {x["id"] for x in tables.values()}
    if len(lineage_records) != 3 or any(
        x.get("source_id") not in table_ids or x.get("target_id") not in table_ids
        for x in lineage_records
    ):
        raise IntegrationError(
            "Seed lineage manifest is incomplete or outside the synthetic tables"
        )
    lineage = []
    for edge in lineage_records:
        source_id, target_id = edge["source_id"], edge["target_id"]
        graph = adapter._json(
            "lineage/table/"
            + quote(source_id, safe="")
            + "?upstreamDepth=1&downstreamDepth=1"
        )
        if not any(
            isinstance(row, dict)
            and row.get("fromEntity") == source_id
            and row.get("toEntity") == target_id
            for row in graph.get("downstreamEdges", [])
        ):
            raise IntegrationError("A recorded synthetic lineage edge is unavailable")
        lineage.append({"source_id": source_id, "target_id": target_id})
    product = products["product-holdings"]
    source = adapter.get_preserved_contract_source(product["id"], max_bytes=1024 * 1024)
    contract = next((x for x in seed["created"] if x.get("kind") == "contract"), None)
    if not contract or source["contract_id"] != contract.get("id"):
        raise IntegrationError("Preserved ODCS contract identity changed")
    return {
        "destination_sha256": destination,
        "seed_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "entities": entities,
        "links": links,
        "lineage": lineage,
        "preserved_contract_sha256": source["sha256"],
    }


def review_domain_move(adapter, manifest_path):
    """Preview a bounded move and the restoration of the original synthetic links."""
    if (
        adapter.profile.read_only
        or adapter._json("system/version").get("version") != "2.1.0"
    ):
        raise IntegrationError("A writable OpenMetadata 2.1.0 profile is required")
    target = adapter._json("domains/name/" + quote(DOMAIN, safe=""))
    if target.get("fullyQualifiedName") != DOMAIN:
        raise IntegrationError("Target domain identity is invalid")
    permission = adapter._json("permissions/domain/" + quote(target["id"], safe=""))
    if not any(
        x.get("operation") == "EditAll" and x.get("access") == "allow"
        for x in permission.get("permissions", [])
        if isinstance(x, dict)
    ):
        raise IntegrationError("Banking domain EditAll permission is required")
    before = inspect_catalog(adapter, manifest_path)
    refs = [{"id": x["id"], "type": x["type"]} for x in before["entities"]]
    dry_run = _request_write(
        adapter,
        "PUT",
        "domains/" + quote(DOMAIN, safe="") + "/assets/add",
        {"assets": refs, "dryRun": True},
    )
    if (
        dry_run.get("dryRun") is not True
        or str(dry_run.get("status", "")).lower() != "success"
        or dry_run.get("numberOfRowsFailed") != 0
        or dry_run.get("numberOfRowsPassed") != len(refs)
        or dry_run.get("numberOfRowsPendingApproval", 0) != 0
    ):
        raise IntegrationError("Domain dry run was incomplete or rejected")
    dry_summary = [
        {
            "message": x.get("message"),
            "hasSideEffects": x.get("hasSideEffects"),
            "id": (x.get("request") or {}).get("id"),
        }
        for x in dry_run.get("successRequest", [])
        if isinstance(x, dict)
    ]
    if len(dry_summary) != len(refs):
        raise IntegrationError("Domain dry run did not describe every entity")
    payload = {
        "target_domain": DOMAIN,
        "target_id": target["id"],
        "before": before,
        "bulk_request": {"assets": refs, "dryRun": False},
        "dry_run": dry_summary,
        "restore_product_links": [
            {
                "product_id": x["product_id"],
                "product_name": x["product_name"],
                "asset_ids": x["asset_ids"],
            }
            for x in before["links"]
        ],
        "warnings": [
            "The domain bulk operation may remove product-asset relationships; the original twenty synthetic links will be restored and verified.",
            "The move is not atomic. Partial or unknown results stop the workflow and require inspection.",
            "No physical data, database connection, or unrelated domain asset is changed.",
        ],
    }
    return {"review_sha256": _digest(payload), **payload}


def execute_domain_move(adapter, seed_manifest, *, reviewed_sha256, migration_manifest):
    """Apply the reviewed move once, then restore and verify recorded links."""
    adapter.require_write_access()
    review = review_domain_move(adapter, seed_manifest)
    if review["review_sha256"] != reviewed_sha256:
        raise IntegrationError("Domain move review changed; review again")
    path = Path(migration_manifest)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    journal = {
        "format": "synthetic-banking-domain-migration-v1",
        "review_sha256": reviewed_sha256,
        "destination_sha256": review["before"]["destination_sha256"],
        "status": "in_progress",
        "pending": None,
        "completed": [],
    }
    _save(path, journal)
    try:
        journal["pending"] = {"kind": "domain_bulk_move", "target": DOMAIN}
        _save(path, journal)
        result = _request_write(
            adapter,
            "PUT",
            "domains/" + quote(DOMAIN, safe="") + "/assets/add",
            review["bulk_request"],
        )
        journal["completed"].append({"kind": "domain_bulk_move", "response": result})
        journal["pending"] = None
        _save(path, journal)
        if (
            str(result.get("status", "")).lower() != "success"
            or result.get("numberOfRowsFailed", 0) != 0
            or result.get("numberOfRowsPendingApproval", 0) != 0
        ):
            raise IntegrationError(
                "Domain move reported partial results; inspect before continuing"
            )
        state = inspect_catalog(
            adapter, seed_manifest, expected_domain=DOMAIN, require_links=False
        )
        if (
            state["preserved_contract_sha256"]
            != review["before"]["preserved_contract_sha256"]
        ):
            raise IntegrationError("Preserved contract changed during the move")
        for link in state["links"]:
            missing = sorted(set(link["asset_ids"]) - set(link["actual_asset_ids"]))
            if not missing:
                continue
            refs = [{"id": identifier, "type": "table"} for identifier in missing]
            journal["pending"] = {
                "kind": "restore_product_assets",
                "product_id": link["product_id"],
                "asset_ids": missing,
            }
            _save(path, journal)
            result = _request_write(
                adapter,
                "PUT",
                "dataProducts/" + quote(link["product_name"], safe="") + "/assets/add",
                {"assets": refs, "dryRun": False},
            )
            journal["completed"].append(
                {
                    "kind": "restore_product_assets",
                    "product_id": link["product_id"],
                    "response": result,
                }
            )
            journal["pending"] = None
            _save(path, journal)
            if (
                str(result.get("status", "")).lower() != "success"
                or result.get("numberOfRowsFailed", 0) != 0
                or result.get("numberOfRowsPendingApproval", 0) != 0
            ):
                raise IntegrationError(
                    "Product asset restoration reported partial results"
                )
        after = inspect_catalog(
            adapter, seed_manifest, expected_domain=DOMAIN, require_links=True
        )
        if (
            after["preserved_contract_sha256"]
            != review["before"]["preserved_contract_sha256"]
        ):
            raise IntegrationError("Preserved contract changed during the move")
        journal["status"] = "completed"
        journal["verification"] = {
            "entity_count": len(after["entities"]),
            "product_count": len(after["links"]),
            "link_count": sum(len(x["actual_asset_ids"]) for x in after["links"]),
            "lineage_count": len(after["lineage"]),
            "preserved_contract_sha256": after["preserved_contract_sha256"],
        }
    except (IntegrationError, OSError, ValueError, KeyError) as exc:
        journal["status"] = (
            "unknown" if "unknown" in type(exc).__name__.lower() else "partial"
        )
        journal["error"] = str(exc)
    _save(path, journal)
    return journal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("review", "execute"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--connection", default="openmetadata")
    parser.add_argument("--env-file")
    parser.add_argument("--seed-manifest", required=True)
    parser.add_argument("--migration-manifest")
    parser.add_argument("--reviewed-sha256")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    profile = load_integration_config(args.config).select(args.connection)
    load_referenced_env(profile, args.env_file)
    with OpenMetadataAdapter(profile) as adapter:
        if args.action == "review":
            result = review_domain_move(adapter, args.seed_manifest)
        else:
            if (
                not args.confirm
                or not args.reviewed_sha256
                or not args.migration_manifest
            ):
                raise IntegrationError(
                    "Execution requires --confirm, --reviewed-sha256 and --migration-manifest"
                )
            result = execute_domain_move(
                adapter,
                args.seed_manifest,
                reviewed_sha256=args.reviewed_sha256,
                migration_manifest=args.migration_manifest,
            )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") not in ("partial", "unknown") else 1


if __name__ == "__main__":
    raise SystemExit(main())
