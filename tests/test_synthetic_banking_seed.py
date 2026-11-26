"""Offline checks for synthetic seed review and cleanup boundaries."""

from types import SimpleNamespace
import json
from uuid import uuid4

import pytest

from examples.integrations import synthetic_banking_seed as seed
from examples.integrations.synthetic_banking_plan import build_plan
from open_data_products.integrations.config import IntegrationError
from open_data_products.integrations.openmetadata import PlatformError


@pytest.fixture
def setup(tmp_path):
    config = tmp_path / "connections.yaml"
    config.write_text("""version: 1
default_connection: om
connections:
  om:
    platform: openmetadata
    base_url: https://metadata.example.org
    read_only: false
    auth:
      type: bearer_token
      token: {source: env, name: TOKEN}
""")
    plan = build_plan(config, "om")

    class Fake:
        profile = SimpleNamespace(
            base_url="https://metadata.example.org", read_only=False
        )

        def require_write_access(self):
            pass

        def _json(self, path):
            if path == "system/version":
                return {"version": "2.1.0"}
            if path.startswith("permissions/"):
                return {
                    "permissions": [
                        {"operation": "Create", "access": "allow"},
                        {"operation": "EditAll", "access": "allow"},
                    ]
                }
            if path.startswith("domains/name/"):
                return {"name": seed.DOMAIN}
            raise PlatformError("Missing", 404)

    return plan, Fake()


def test_review_covers_all_proposed_entities_and_conflicts(setup):
    plan, adapter = setup
    result = seed.review(plan, adapter)
    assert len([op for op in result["operations"] if op["kind"] == "table"]) == 7
    assert len([op for op in result["operations"] if op["kind"] == "dataProduct"]) == 6
    assert len([op for op in result["operations"] if op["kind"] == "lineage"]) == 3
    assert any(
        op["kind"] == "contract" and "schema:" in op["source"]
        for op in result["operations"]
    )
    original = adapter._json
    adapter._json = lambda path: (
        {"id": "exists"} if path.startswith("dataProducts/name/") else original(path)
    )
    with pytest.raises(IntegrationError, match="already exists"):
        seed.review(plan, adapter)


def test_partial_and_unknown_are_recorded_without_retry(setup, tmp_path, monkeypatch):
    plan, adapter = setup
    reviewed = seed.review(plan, adapter)
    calls = []

    def post(adapter, method, path, payload=None):
        calls.append(path)
        if len(calls) == 2:
            raise seed.UnknownOutcome("timeout; inspect before retry")
        return {"id": str(uuid4())}

    monkeypatch.setattr(seed, "_request_write", post)
    path = tmp_path / "manifest.json"
    result = seed.execute(
        plan, adapter, reviewed_sha256=reviewed["review_sha256"], manifest_path=path
    )
    assert result["status"] == "unknown"
    assert len(result["created"]) == 1 and len(calls) == 2
    assert json.loads(path.read_text())["pending"]["kind"] == "database"
    with pytest.raises(IntegrationError, match="investigated"):
        seed.review_cleanup(adapter, path)
    with pytest.raises(FileExistsError):
        seed.execute(
            plan, adapter, reviewed_sha256=reviewed["review_sha256"], manifest_path=path
        )


def test_cleanup_refuses_unrelated_entities(setup, tmp_path):
    plan, adapter = setup
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "format": "synthetic-banking-seed-v1",
                "destination_sha256": plan["destination_sha256"],
                "status": "created",
                "created": [
                    {
                        "kind": "table",
                        "id": str(uuid4()),
                        "fqn": "production.bank.table",
                        "path": "tables",
                    }
                ],
            }
        )
    )
    with pytest.raises(IntegrationError, match="outside"):
        seed.review_cleanup(adapter, path)
    with pytest.raises(IntegrationError, match="confirmation"):
        seed.execute_cleanup(adapter, path, reviewed_sha256="x", confirm=False)


def test_successful_seed_records_each_created_entity_and_relationship(
    setup, tmp_path, monkeypatch
):
    plan, adapter = setup
    reviewed = seed.review(plan, adapter)
    adapter.review_contract_import = lambda source, product_id: SimpleNamespace(
        executable=True, review_sha256="contract-review"
    )
    adapter.import_contract = (
        lambda source, product_id, reviewed_sha256: SimpleNamespace(
            contract_id=str(uuid4()), status="created"
        )
    )
    calls = []

    def write(adapter, method, path, payload=None):
        calls.append((method, path, payload))
        return {"id": str(uuid4())} if method == "POST" else {}

    monkeypatch.setattr(seed, "_request_write", write)
    manifest_path = tmp_path / "created.json"
    result = seed.execute(
        plan,
        adapter,
        reviewed_sha256=reviewed["review_sha256"],
        manifest_path=manifest_path,
    )
    assert result["status"] == "created"
    assert len(result["created"]) == 20
    assert sum(item["kind"] == "lineage" for item in result["created"]) == 3
    assert sum(item["kind"] == "contract" for item in result["created"]) == 1
    assert all(method != "DELETE" for method, _, _ in calls)
    assert all("sampleData" not in json.dumps(payload) for _, _, payload in calls)
    assert json.loads(manifest_path.read_text())["pending"] is None


def test_clear_failure_records_partial_without_blind_retry(
    setup, tmp_path, monkeypatch
):
    plan, adapter = setup
    reviewed = seed.review(plan, adapter)
    calls = []

    def denied(adapter, method, path, payload=None):
        calls.append(path)
        if len(calls) == 2:
            raise PlatformError("Write returned HTTP 403", 403)
        return {"id": str(uuid4())}

    monkeypatch.setattr(seed, "_request_write", denied)
    result = seed.execute(
        plan,
        adapter,
        reviewed_sha256=reviewed["review_sha256"],
        manifest_path=tmp_path / "partial.json",
    )
    assert result["status"] == "partial"
    assert len(result["created"]) == 1 and len(calls) == 2


def test_contract_preservation_uncertainty_keeps_confirmed_id(
    setup, tmp_path, monkeypatch
):
    plan, adapter = setup
    reviewed = seed.review(plan, adapter)
    contract_id = str(uuid4())
    adapter.review_contract_import = lambda source, product_id: SimpleNamespace(
        executable=True, review_sha256="r"
    )
    adapter.import_contract = (
        lambda source, product_id, reviewed_sha256: SimpleNamespace(
            contract_id=contract_id, status="created_unverified"
        )
    )
    monkeypatch.setattr(
        seed,
        "_request_write",
        lambda adapter, method, path, payload=None: {"id": str(uuid4())},
    )
    result = seed.execute(
        plan,
        adapter,
        reviewed_sha256=reviewed["review_sha256"],
        manifest_path=tmp_path / "manifest.json",
    )
    assert result["status"] == "unknown"
    assert any(item.get("id") == contract_id for item in result["created"])
    with pytest.raises(IntegrationError, match="investigated"):
        seed.review_cleanup(adapter, tmp_path / "manifest.json")


def test_cleanup_only_deletes_reviewed_recorded_ids(setup, tmp_path, monkeypatch):
    plan, adapter = setup
    service_id, table_id = str(uuid4()), str(uuid4())
    path = tmp_path / "manifest.json"
    records = [
        {
            "kind": "service",
            "id": service_id,
            "fqn": seed.SERVICE,
            "path": "services/databaseServices",
        },
        {
            "kind": "table",
            "id": table_id,
            "fqn": seed.SCHEMA + ".customers",
            "path": "tables",
        },
    ]
    path.write_text(
        json.dumps(
            {
                "format": "synthetic-banking-seed-v1",
                "destination_sha256": plan["destination_sha256"],
                "status": "created",
                "created": records,
            }
        )
    )

    def get(path):
        if path.startswith("lineage/table/"):
            return {"upstreamEdges": [], "downstreamEdges": []}
        if path.split("?")[0].endswith(table_id):
            return {
                "id": table_id,
                "fullyQualifiedName": seed.SCHEMA + ".customers",
                "description": "Synthetic test metadata",
                "version": 1,
            }
        if path.endswith(service_id):
            return {
                "id": service_id,
                "fullyQualifiedName": seed.SERVICE,
                "description": seed.LABEL,
                "version": 1,
            }
        raise AssertionError(path)

    adapter._json = get
    reviewed = seed.review_cleanup(adapter, path)
    calls = []
    monkeypatch.setattr(
        seed,
        "_request_write",
        lambda adapter, method, target, payload=None: calls.append((method, target))
        or {},
    )
    result = seed.execute_cleanup(
        adapter, path, reviewed_sha256=reviewed["review_sha256"], confirm=True
    )
    assert result["status"] == "completed"
    assert len(calls) == 2 and all(
        method == "DELETE" and "recursive=false&hardDelete=false" in target
        for method, target in calls
    )
    assert json.loads(path.read_text())["status"] == "cleaned"


def test_dotenv_loader_reads_only_referenced_variable(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('TOKEN="synthetic-secret"\nOTHER=$(touch unsafe)\n')
    monkeypatch.delenv("TOKEN", raising=False)
    monkeypatch.delenv("OTHER", raising=False)
    profile = SimpleNamespace(token_source="env", token_env="TOKEN")
    seed.load_referenced_env(profile, env)
    import os

    assert os.environ["TOKEN"] == "synthetic-secret"
    assert "OTHER" not in os.environ
    assert not (tmp_path / "unsafe").exists()


def test_http_timeout_is_unknown_and_not_retried(monkeypatch):
    from urllib.error import URLError

    calls = []

    def fail(req, timeout):
        calls.append(req.method)
        raise URLError("timeout")

    adapter = SimpleNamespace(
        profile=SimpleNamespace(
            base_url="https://metadata.example.org",
            timeout_seconds=1,
            token=lambda: "fake",
        ),
        _opener=SimpleNamespace(open=fail),
    )
    with pytest.raises(seed.UnknownOutcome, match="unknown"):
        seed._request_write(adapter, "POST", "tables", {"name": "x"})
    assert calls == ["POST"]


def test_reviewed_resume_only_adds_varchar_lengths_and_reuses_created_ids(
    setup, tmp_path, monkeypatch
):
    plan, adapter = setup
    old_plan = json.loads(json.dumps(plan))
    for table in old_plan["tables"]:
        for column in table["columns"]:
            column.pop("dataLength", None)
    original = seed.review(old_plan, adapter)
    original_path = tmp_path / "review.json"
    original_path.write_text(json.dumps(original))
    first = original["operations"][:9]
    records = [
        {"kind": op["kind"], "path": op["path"], "fqn": op["fqn"], "id": str(uuid4())}
        for op in first
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "format": "synthetic-banking-seed-v1",
                "destination_sha256": plan["destination_sha256"],
                "review_sha256": original["review_sha256"],
                "status": "partial",
                "created": records,
                "pending": original["operations"][9],
                "error": "HTTP 400: dataLength required",
            }
        )
    )
    fallback = adapter._json

    def read(path):
        for item in records:
            if path == item["path"] + "/" + item["id"]:
                return {
                    "id": item["id"],
                    "fullyQualifiedName": item["fqn"],
                    "description": seed.LABEL,
                    "version": 1,
                }
        return fallback(path)

    adapter._json = read
    adapter.get_contract_for_product = lambda product_id: (_ for _ in ()).throw(
        PlatformError("Not found", 404)
    )
    adapter.review_contract_import = lambda source, product_id: SimpleNamespace(
        executable=True, review_sha256="contract-review"
    )
    adapter.import_contract = (
        lambda source, product_id, reviewed_sha256: SimpleNamespace(
            contract_id=str(uuid4()), status="created"
        )
    )
    preview = seed.review_resume(plan, adapter, manifest_path, original_path)
    assert len(preview["existing"]) == 9
    assert len(preview["remaining_operations"]) == 11
    assert all(
        col["dataLength"] == 255
        for op in preview["remaining_operations"]
        if op["kind"] == "table"
        for col in op["payload"]["columns"]
        if col["dataType"] == "VARCHAR"
    )
    writes = []
    monkeypatch.setattr(
        seed,
        "_request_write",
        lambda adapter, method, path, payload=None: writes.append((method, path))
        or {"id": str(uuid4())},
    )
    with pytest.raises(IntegrationError, match="review changed"):
        seed.resume(
            plan,
            adapter,
            manifest_path=manifest_path,
            original_review_path=original_path,
            reviewed_sha256="wrong",
        )
    result = seed.resume(
        plan,
        adapter,
        manifest_path=manifest_path,
        original_review_path=original_path,
        reviewed_sha256=preview["review_sha256"],
    )
    assert result["status"] == "created"
    assert len(result["created"]) == 20
    assert sum(method == "POST" and path == "tables" for method, path in writes) == 7
    assert not any(
        path
        in ("services/databaseServices", "databases", "databaseSchemas", "dataProducts")
        for method, path in writes
    )


def test_domain_resume_requires_confirmed_rule_and_changes_only_domain(
    setup, tmp_path, monkeypatch
):
    plan, adapter = setup
    old_plan = json.loads(json.dumps(plan))
    for table in old_plan["tables"]:
        for column in table["columns"]:
            column.pop("dataLength", None)
    original = seed.review(old_plan, adapter)
    original_path = tmp_path / "original.json"
    original_path.write_text(json.dumps(original))
    records = [
        {"kind": op["kind"], "path": op["path"], "fqn": op["fqn"], "id": str(uuid4())}
        for op in original["operations"][:9]
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "format": "synthetic-banking-seed-v1",
                "destination_sha256": plan["destination_sha256"],
                "review_sha256": original["review_sha256"],
                "status": "partial",
                "created": records,
                "pending": original["operations"][9],
                "error": "HTTP 400: dataLength required",
            }
        )
    )
    fallback = adapter._json

    def read(path):
        for item in records:
            if path == item["path"] + "/" + item["id"]:
                return {
                    "id": item["id"],
                    "fullyQualifiedName": item["fqn"],
                    "description": seed.LABEL,
                    "version": 1,
                }
        if path == "permissions/table":
            return {
                "permissions": [
                    {"operation": name, "access": "allow"}
                    for name in ("Create", "EditAll", "EditDomains")
                ]
            }
        return fallback(path)

    adapter._json = read
    adapter.get_contract_for_product = lambda product_id: (_ for _ in ()).throw(
        PlatformError("Not found", 404)
    )
    previous = seed.review_resume(plan, adapter, manifest_path, original_path)
    previous_path = tmp_path / "previous.json"
    previous_path.write_text(json.dumps(previous))

    def domain_denied(*args):
        raise PlatformError(
            "Write returned HTTP 400: Rule [Data Product Domain Validation] failed", 400
        )

    monkeypatch.setattr(seed, "_request_write", domain_denied)
    partial = seed.resume(
        plan,
        adapter,
        manifest_path=manifest_path,
        original_review_path=original_path,
        reviewed_sha256=previous["review_sha256"],
    )
    assert partial["status"] == "partial" and len(partial["created"]) == 9
    reviewed = seed.review_domain_resume(
        plan, adapter, manifest_path, original_path, previous_path
    )
    assert all(
        op["payload"]["domains"] == [seed.DOMAIN]
        for op in reviewed["remaining_operations"]
        if op["kind"] == "table"
    )
    adapter.review_contract_import = lambda source, product_id: SimpleNamespace(
        executable=True, review_sha256="contract"
    )
    adapter.import_contract = (
        lambda source, product_id, reviewed_sha256: SimpleNamespace(
            contract_id=str(uuid4()), status="created"
        )
    )
    writes = []
    monkeypatch.setattr(
        seed,
        "_request_write",
        lambda adapter, method, path, payload=None: writes.append((method, path))
        or {"id": str(uuid4())},
    )
    with pytest.raises(IntegrationError, match="review changed"):
        seed.resume_domain(
            plan,
            adapter,
            manifest_path=manifest_path,
            original_review_path=original_path,
            previous_review_path=previous_path,
            reviewed_sha256="wrong",
        )
    result = seed.resume_domain(
        plan,
        adapter,
        manifest_path=manifest_path,
        original_review_path=original_path,
        previous_review_path=previous_path,
        reviewed_sha256=reviewed["review_sha256"],
    )
    assert result["status"] == "created" and len(result["created"]) == 20
    assert sum(method == "POST" and path == "tables" for method, path in writes) == 7


def test_seed_cleanup_refuses_unrecorded_source_lineage(setup, tmp_path):
    plan, adapter = setup
    table_id, foreign_id = str(uuid4()), str(uuid4())
    path = tmp_path / "seed.json"
    path.write_text(
        json.dumps(
            {
                "format": "synthetic-banking-seed-v1",
                "destination_sha256": plan["destination_sha256"],
                "status": "created",
                "created": [
                    {
                        "kind": "table",
                        "id": table_id,
                        "fqn": seed.SCHEMA + ".customers",
                        "path": "tables",
                    }
                ],
            }
        )
    )

    def get(path):
        if path.startswith("tables/"):
            return {
                "id": table_id,
                "fullyQualifiedName": seed.SCHEMA + ".customers",
                "description": "Synthetic table",
                "dataProducts": [],
            }
        if path.startswith("lineage/"):
            return {
                "upstreamEdges": [{"fromEntity": foreign_id, "toEntity": table_id}],
                "downstreamEdges": [],
            }
        raise AssertionError(path)

    adapter._json = get
    with pytest.raises(IntegrationError, match="unrecorded"):
        seed.review_cleanup(adapter, path)
