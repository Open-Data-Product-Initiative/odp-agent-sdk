"""Offline checks for the reviewed Banking domain migration."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from examples.integrations import synthetic_banking_domain as move
from examples.integrations.synthetic_banking_plan import LINKS
from examples.integrations.synthetic_banking_seed import UnknownOutcome
from open_data_products.integrations.config import IntegrationError


@pytest.fixture
def environment(tmp_path):
    base = "https://metadata.example.org"
    import hashlib

    ids = lambda: str(uuid4())
    records = [
        {
            "kind": "service",
            "path": "services/databaseServices",
            "fqn": "sdk_synthetic_banking",
            "id": ids(),
        },
        {
            "kind": "database",
            "path": "databases",
            "fqn": "sdk_synthetic_banking.synthetic_bank",
            "id": ids(),
        },
        {
            "kind": "databaseSchema",
            "path": "databaseSchemas",
            "fqn": "sdk_synthetic_banking.synthetic_bank.sdk_test",
            "id": ids(),
        },
    ]
    names = sorted({name for items in LINKS.values() for name in items})
    for name in names:
        records.append(
            {
                "kind": "table",
                "path": "tables",
                "fqn": "sdk_synthetic_banking.synthetic_bank.sdk_test." + name,
                "id": ids(),
            }
        )
    for slug in LINKS:
        records.append(
            {
                "kind": "dataProduct",
                "path": "dataProducts",
                "fqn": "sdk_synthetic_" + slug.replace("-", "_"),
                "id": ids(),
            }
        )
    tables = {r["fqn"].rsplit(".", 1)[-1]: r for r in records if r["kind"] == "table"}
    products = {
        slug: next(
            r for r in records if r["fqn"] == "sdk_synthetic_" + slug.replace("-", "_")
        )
        for slug in LINKS
    }
    edges = [
        {"kind": "lineage", "source_id": tables[a]["id"], "target_id": tables[b]["id"]}
        for a, b in (
            ("customers", "product_holdings"),
            ("accounts", "transactions"),
            ("accounts", "payment_obligations"),
        )
    ]
    contract_id = ids()
    manifest = {
        "format": "synthetic-banking-seed-v1",
        "status": "created",
        "destination_sha256": hashlib.sha256(base.encode()).hexdigest(),
        "created": records
        + edges
        + [
            {
                "kind": "contract",
                "id": contract_id,
                "product_id": products["product-holdings"]["id"],
            }
        ],
    }
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(manifest))
    state = {
        "domains": {
            r["id"]: (
                []
                if r["kind"] in ("service", "database", "databaseSchema")
                else ["SDKIntegrationTest"]
            )
            for r in records
        },
        "links": {
            p["id"]: {tables[name]["id"] for name in LINKS[slug]}
            for slug, p in products.items()
        },
    }

    class Adapter:
        profile = SimpleNamespace(base_url=base, read_only=False)

        def require_write_access(self):
            pass

        def get_preserved_contract_source(self, product_id, max_bytes=None):
            return {"contract_id": contract_id, "sha256": "source-digest"}

        def _json(self, path):
            if path == "system/version":
                return {"version": "2.1.0"}
            if path == "domains/name/Banking":
                return {"id": "domain-1", "fullyQualifiedName": "Banking"}
            if path.startswith("permissions/domain/"):
                return {"permissions": [{"operation": "EditAll", "access": "allow"}]}
            if (
                path.startswith("databases?")
                or path.startswith("databaseSchemas?")
                or path.startswith("tables?")
            ):
                kind = (
                    "database"
                    if path.startswith("databases?")
                    else (
                        "databaseSchema"
                        if path.startswith("databaseSchemas?")
                        else "table"
                    )
                )
                rows = [{"id": r["id"]} for r in records if r["kind"] == kind]
                return {"data": rows, "paging": {"total": len(rows)}}
            if path.startswith("lineage/table/"):
                source = path.split("/")[2].split("?")[0]
                return {
                    "downstreamEdges": [
                        {"fromEntity": e["source_id"], "toEntity": e["target_id"]}
                        for e in edges
                        if e["source_id"] == source
                    ]
                }
            if path.startswith("dataProducts/") and "/assets?" in path:
                product_id = path.split("/")[1]
                values = [
                    {"id": i, "type": "table"} for i in state["links"][product_id]
                ]
                return {"data": values, "paging": {"total": len(values)}}
            for r in records:
                if path.split("?")[0] == r["path"] + "/" + r["id"]:
                    data = {
                        "id": r["id"],
                        "fullyQualifiedName": r["fqn"],
                        "description": "Synthetic test metadata",
                        "version": 1,
                        "domains": [
                            {"name": name} for name in state["domains"][r["id"]]
                        ],
                    }
                    if r["kind"] == "table":
                        data["dataProducts"] = [
                            {"id": pid}
                            for pid, assets in state["links"].items()
                            if r["id"] in assets
                        ]
                    return data
            raise AssertionError(path)

    return Adapter(), path, state, records, products


def test_domain_review_and_restores_original_links(environment, tmp_path, monkeypatch):
    adapter, path, state, records, products = environment
    calls = []

    def write(adapter, method, endpoint, payload):
        calls.append((method, endpoint, payload))
        if payload["dryRun"]:
            return {
                "dryRun": True,
                "status": "success",
                "numberOfRowsFailed": 0,
                "numberOfRowsPassed": 16,
                "successRequest": [
                    {
                        "request": x,
                        "message": "synthetic preview",
                        "hasSideEffects": True,
                    }
                    for x in payload["assets"]
                ],
            }
        if endpoint.startswith("domains/"):
            for item in state["domains"]:
                state["domains"][item] = ["Banking"]
            for item in state["links"]:
                state["links"][item] = set()
        else:
            name = endpoint.split("/")[1]
            product_id = next(p["id"] for p in products.values() if p["fqn"] == name)
            state["links"][product_id].update(x["id"] for x in payload["assets"])
        return {
            "status": "success",
            "numberOfRowsFailed": 0,
            "numberOfRowsPendingApproval": 0,
        }

    monkeypatch.setattr(move, "_request_write", write)
    review = move.review_domain_move(adapter, path)
    assert sum(len(link["asset_ids"]) for link in review["restore_product_links"]) == 20
    assert all(call[2]["dryRun"] is True for call in calls)
    result = move.execute_domain_move(
        adapter,
        path,
        reviewed_sha256=review["review_sha256"],
        migration_manifest=tmp_path / "migration.json",
    )
    assert result["status"] == "completed"
    assert result["verification"]["entity_count"] == 16
    assert result["verification"]["link_count"] == 20
    assert result["verification"]["lineage_count"] == 3
    assert sum(not call[2]["dryRun"] for call in calls) == 7


def test_domain_review_rejects_foreign_product_assets(environment, monkeypatch):
    adapter, path, state, records, products = environment
    state["links"][products["product-holdings"]["id"]].add(str(uuid4()))
    calls = []
    monkeypatch.setattr(move, "_request_write", lambda *args: calls.append(args))
    with pytest.raises(IntegrationError, match="foreign"):
        move.review_domain_move(adapter, path)
    assert calls == []


def test_unknown_domain_outcome_stops_without_reattaching(
    environment, tmp_path, monkeypatch
):
    adapter, path, state, records, products = environment
    calls = []

    def write(adapter, method, endpoint, payload):
        calls.append(payload["dryRun"])
        if payload["dryRun"]:
            return {
                "dryRun": True,
                "status": "success",
                "numberOfRowsFailed": 0,
                "numberOfRowsPassed": 16,
                "successRequest": [
                    {"request": x, "message": "preview", "hasSideEffects": True}
                    for x in payload["assets"]
                ],
            }
        raise UnknownOutcome("timeout; do not retry")

    monkeypatch.setattr(move, "_request_write", write)
    review = move.review_domain_move(adapter, path)
    result = move.execute_domain_move(
        adapter,
        path,
        reviewed_sha256=review["review_sha256"],
        migration_manifest=tmp_path / "migration.json",
    )
    assert result["status"] == "unknown"
    assert result["pending"]["kind"] == "domain_bulk_move"
    assert calls.count(False) == 1


def test_partial_domain_move_stops_without_reattaching(
    environment, tmp_path, monkeypatch
):
    adapter, path, state, records, products = environment
    calls = []

    def write(adapter, method, endpoint, payload):
        calls.append(payload["dryRun"])
        if payload["dryRun"]:
            return {
                "dryRun": True,
                "status": "success",
                "numberOfRowsFailed": 0,
                "numberOfRowsPassed": 16,
                "successRequest": [
                    {"request": x, "message": "preview", "hasSideEffects": True}
                    for x in payload["assets"]
                ],
            }
        return {
            "status": "partialSuccess",
            "numberOfRowsFailed": 1,
            "numberOfRowsPassed": 15,
        }

    monkeypatch.setattr(move, "_request_write", write)
    review = move.review_domain_move(adapter, path)
    result = move.execute_domain_move(
        adapter,
        path,
        reviewed_sha256=review["review_sha256"],
        migration_manifest=tmp_path / "migration.json",
    )
    assert result["status"] == "partial"
    assert len(result["completed"]) == 1
    assert calls.count(False) == 1


def test_mismatched_review_digest_never_moves_domain(
    environment, tmp_path, monkeypatch
):
    adapter, path, state, records, products = environment
    calls = []

    def write(adapter, method, endpoint, payload):
        calls.append(payload["dryRun"])
        return {
            "dryRun": True,
            "status": "success",
            "numberOfRowsFailed": 0,
            "numberOfRowsPassed": 16,
            "successRequest": [
                {"request": x, "message": "preview", "hasSideEffects": True}
                for x in payload["assets"]
            ],
        }

    monkeypatch.setattr(move, "_request_write", write)
    with pytest.raises(IntegrationError, match="review changed"):
        move.execute_domain_move(
            adapter,
            path,
            reviewed_sha256="not-a-review",
            migration_manifest=tmp_path / "migration.json",
        )
    assert calls == [True]
    assert not (tmp_path / "migration.json").exists()
