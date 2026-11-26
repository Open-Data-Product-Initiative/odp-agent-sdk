"""Offline safety tests for the synthetic source-service split."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from examples.integrations import synthetic_banking_split as split
from examples.integrations.synthetic_banking_plan import LINKS
from open_data_products.integrations import IntegrationError, PlatformError


@pytest.fixture
def environment(monkeypatch, tmp_path):
    ids = lambda: str(uuid4())
    service_id = ids()
    names = sorted({x for items in LINKS.values() for x in items})
    tables = [
        {
            "kind": "table",
            "id": ids(),
            "fqn": "sdk_synthetic_banking.synthetic_bank.sdk_test." + n,
            "version": 1,
        }
        for n in names
    ]
    baseline = {
        "destination_sha256": "destination",
        "seed_manifest_sha256": "seedhash",
        "entities": [
            {
                "kind": "service",
                "id": service_id,
                "fqn": "sdk_synthetic_banking",
                "version": 1,
            }
        ]
        + tables,
        "links": [{"asset_ids": ["a", "b"], "actual_asset_ids": ["a", "b"]}],
        "lineage": [{"source_id": "a", "target_id": "b"}],
        "preserved_contract_sha256": "hash",
    }
    monkeypatch.setattr(split, "inspect_catalog", lambda *args, **kwargs: baseline)
    state = {"created": {}, "edges": [], "description": "Synthetic test metadata"}

    class Fake:
        profile = SimpleNamespace(read_only=False)

        def require_write_access(self):
            pass

        def _json(self, path):
            if path == "system/version":
                return {"version": "2.1.0"}
            if path == "domains/name/Banking":
                return {"fullyQualifiedName": "Banking"}
            if path.startswith("permissions/"):
                return {
                    "permissions": [
                        {"operation": name, "access": "allow"}
                        for name in ("Create", "EditAll", "EditDescription")
                    ]
                }
            if "/name/" in path:
                raise PlatformError("Missing", 404)
            if path == "services/databaseServices/" + service_id:
                return {
                    "id": service_id,
                    "version": 1,
                    "description": state["description"],
                }
            if path.startswith("lineage/table/"):
                identifier = path.split("/")[2].split("?")[0]
                return {
                    "downstreamEdges": [
                        {"fromEntity": a, "toEntity": b}
                        for a, b in state["edges"]
                        if a == identifier
                    ]
                }
            for table in tables:
                if path.split("?")[0] == "tables/" + table["id"]:
                    return {
                        "id": table["id"],
                        "version": 1,
                        "columns": [
                            {"name": "id", "dataType": "VARCHAR", "dataLength": 255}
                        ],
                    }
            for obj in state["created"].values():
                if path.split("?")[0] == obj["path"] + "/" + obj["id"]:
                    return {
                        "id": obj["id"],
                        "fullyQualifiedName": obj["fqn"],
                        "domains": [{"name": "Banking"}],
                        "columns": obj["payload"].get("columns"),
                    }
            raise AssertionError(path)

    return Fake(), tmp_path / "seed.json", state, service_id


def test_split_review_and_success_preserve_curated_links(
    environment, tmp_path, monkeypatch
):
    adapter, seed_path, state, service_id = environment
    review = split.review_split(adapter, seed_path)
    assert len(review["creates"]) == 16
    assert len(review["source_to_curated_lineage"]) == 7
    calls = []

    def write(adapter, method, path, payload):
        calls.append((method, path))
        if method == "PUT":
            state["edges"].append(
                (payload["edge"]["fromEntity"]["id"], payload["edge"]["toEntity"]["id"])
            )
            return {}
        identifier = str(uuid4())
        op = next(
            x
            for x in review["creates"]
            if x["path"] == path and x["payload"] == payload
        )
        state["created"][identifier] = {
            "id": identifier,
            "path": path,
            "fqn": op["fqn"],
            "payload": payload,
        }
        return {"id": identifier}

    monkeypatch.setattr(split, "_request_write", write)
    monkeypatch.setattr(
        split,
        "_patch_service",
        lambda adapter, identifier, version, description: state.update(
            description=description
        ),
    )
    result = split.execute_split(
        adapter,
        seed_path,
        reviewed_sha256=review["review_sha256"],
        manifest_path=tmp_path / "split.json",
    )
    assert result["status"] == "created"
    assert result["verification"]["new_lineage"] == 7
    assert result["verification"]["existing_product_links"] == 2
    assert len(result["created"]) == 23
    assert not any(method == "DELETE" for method, path in calls)
    assert state["description"] == split.CURATED_DESCRIPTION


def test_split_stops_after_unknown_outcome(environment, tmp_path, monkeypatch):
    adapter, seed_path, state, service_id = environment
    review = split.review_split(adapter, seed_path)
    calls = []

    def write(adapter, method, path, payload):
        calls.append(path)
        if len(calls) == 2:
            raise split.UnknownOutcome("timeout; inspect before retry")
        return {"id": str(uuid4())}

    monkeypatch.setattr(split, "_request_write", write)
    result = split.execute_split(
        adapter,
        seed_path,
        reviewed_sha256=review["review_sha256"],
        manifest_path=tmp_path / "partial.json",
    )
    assert result["status"] == "unknown"
    assert len(result["created"]) == 1 and len(calls) == 2
    assert result["pending"]["kind"] == "database"


def test_split_rejects_existing_names_and_changed_review(
    environment, tmp_path, monkeypatch
):
    adapter, seed_path, state, service_id = environment
    original = adapter._json
    adapter._json = lambda path: (
        {"id": "existing"}
        if path.startswith("services/databaseServices/name/")
        else original(path)
    )
    with pytest.raises(IntegrationError, match="already exists"):
        split.review_split(adapter, seed_path)
    adapter._json = original
    with pytest.raises(IntegrationError, match="review changed"):
        split.execute_split(
            adapter,
            seed_path,
            reviewed_sha256="wrong",
            manifest_path=tmp_path / "not-created.json",
        )
    assert not (tmp_path / "not-created.json").exists()


def test_cleanup_confines_deletion_to_created_source_metadata(tmp_path, monkeypatch):
    import hashlib, json

    source_id, target_id = str(uuid4()), str(uuid4())
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps({"created": [{"kind": "table", "id": target_id}]}))
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "format": "synthetic-banking-split-v1",
                "status": "created",
                "destination_sha256": hashlib.sha256(
                    b"https://example.org"
                ).hexdigest(),
                "seed_manifest_sha256": hashlib.sha256(
                    seed_path.read_bytes()
                ).hexdigest(),
                "created": [
                    {
                        "kind": "table",
                        "path": "tables",
                        "fqn": "sdk_synthetic_customer_consent.synthetic_bank.source.customers",
                        "id": source_id,
                    },
                    {"kind": "lineage", "source_id": source_id, "target_id": target_id},
                ],
            }
        )
    )

    class Adapter:
        profile = SimpleNamespace(base_url="https://example.org")

        def require_write_access(self):
            pass

        def _json(self, path):
            if path.startswith("lineage/table/"):
                return {
                    "upstreamEdges": [],
                    "downstreamEdges": [
                        {"fromEntity": source_id, "toEntity": target_id}
                    ],
                }
            if path.startswith("tables/"):
                return {
                    "id": source_id,
                    "fullyQualifiedName": "sdk_synthetic_customer_consent.synthetic_bank.source.customers",
                    "description": "Synthetic source",
                    "dataProducts": [],
                    "version": 1,
                }
            raise AssertionError(path)

    adapter = Adapter()
    review = split.review_split_cleanup(adapter, seed_path, split_path)
    calls = []
    monkeypatch.setattr(
        split,
        "_request_write",
        lambda adapter, method, path: calls.append((method, path)) or {},
    )
    with pytest.raises(IntegrationError, match="explicit confirmation"):
        split.execute_split_cleanup(
            adapter,
            seed_path,
            split_path,
            reviewed_sha256=review["review_sha256"],
            confirm=False,
        )
    result = split.execute_split_cleanup(
        adapter,
        seed_path,
        split_path,
        reviewed_sha256=review["review_sha256"],
        confirm=True,
    )
    assert result["status"] == "completed"
    assert len(calls) == 2 and all(method == "DELETE" for method, path in calls)
    assert not any(path.startswith("tables/" + target_id) for method, path in calls)
    assert any("recursive=false&hardDelete=false" in path for method, path in calls)


def test_cleanup_rejects_unrecorded_lineage(tmp_path):
    import hashlib, json

    source_id, target_id = str(uuid4()), str(uuid4())
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps({"created": [{"kind": "table", "id": target_id}]}))
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "format": "synthetic-banking-split-v1",
                "status": "created",
                "destination_sha256": hashlib.sha256(
                    b"https://example.org"
                ).hexdigest(),
                "seed_manifest_sha256": hashlib.sha256(
                    seed_path.read_bytes()
                ).hexdigest(),
                "created": [
                    {
                        "kind": "table",
                        "path": "tables",
                        "fqn": "sdk_synthetic_payments.synthetic_bank.source.transactions",
                        "id": source_id,
                    }
                ],
            }
        )
    )

    class Adapter:
        profile = SimpleNamespace(base_url="https://example.org")

        def _json(self, path):
            if path.startswith("tables/"):
                return {
                    "id": source_id,
                    "fullyQualifiedName": "sdk_synthetic_payments.synthetic_bank.source.transactions",
                    "description": "Synthetic source",
                    "dataProducts": [],
                }
            if path.startswith("lineage/"):
                return {
                    "downstreamEdges": [
                        {"fromEntity": source_id, "toEntity": target_id}
                    ]
                }
            raise AssertionError(path)

    with pytest.raises(IntegrationError, match="unrecorded"):
        split.review_split_cleanup(Adapter(), seed_path, split_path)


def test_split_reports_definite_partial_failure_without_retry(
    environment, tmp_path, monkeypatch
):
    adapter, seed_path, state, service_id = environment
    review = split.review_split(adapter, seed_path)
    calls = []

    def write(adapter, method, path, payload):
        calls.append(path)
        if len(calls) == 2:
            raise PlatformError("Write returned HTTP 403", 403)
        return {"id": str(uuid4())}

    monkeypatch.setattr(split, "_request_write", write)
    result = split.execute_split(
        adapter,
        seed_path,
        reviewed_sha256=review["review_sha256"],
        manifest_path=tmp_path / "partial.json",
    )
    assert result["status"] == "partial" and len(result["created"]) == 1
    assert len(calls) == 2


def test_cleanup_refuses_foreign_children(tmp_path):
    import hashlib, json

    service_id, foreign_id = str(uuid4()), str(uuid4())
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps({"created": []}))
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "format": "synthetic-banking-split-v1",
                "status": "created",
                "destination_sha256": hashlib.sha256(
                    b"https://example.org"
                ).hexdigest(),
                "seed_manifest_sha256": hashlib.sha256(
                    seed_path.read_bytes()
                ).hexdigest(),
                "created": [
                    {
                        "kind": "service",
                        "path": "services/databaseServices",
                        "fqn": "sdk_synthetic_payments",
                        "id": service_id,
                    }
                ],
            }
        )
    )

    class Adapter:
        profile = SimpleNamespace(base_url="https://example.org")

        def _json(self, path):
            if path.startswith("services/databaseServices/"):
                return {
                    "id": service_id,
                    "fullyQualifiedName": "sdk_synthetic_payments",
                    "description": "Synthetic source",
                    "version": 1,
                }
            if path.startswith("databases?"):
                return {"data": [{"id": foreign_id}], "paging": {"total": 1}}
            raise AssertionError(path)

    with pytest.raises(IntegrationError, match="Unrecorded children"):
        split.review_split_cleanup(Adapter(), seed_path, split_path)
