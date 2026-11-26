"""Offline checks for reviewed synthetic sample uploads."""

import json
from types import SimpleNamespace

import pytest

from examples.integrations import synthetic_banking_samples as samples
from examples.integrations.synthetic_banking_plan import TABLES
from open_data_products.integrations import IntegrationError


class Adapter:
    def __init__(self):
        self.profile = SimpleNamespace(base_url="https://example.invalid")
        self.tables = {}
        self.samples = {}

    def require_write_access(self):
        pass

    def _json(self, path):
        if path == "system/version":
            return {"version": "2.1.0"}
        if path.startswith("permissions/table/"):
            return {
                "permissions": [
                    {"operation": x, "access": "allow"}
                    for x in ("ViewSampleData", "EditSampleData")
                ]
            }
        identifier = path.split("/")[1].split("?")[0]
        if path.endswith("/sampleData"):
            return {"id": identifier, "sampleData": self.samples.get(identifier)}
        return self.tables[identifier]


@pytest.fixture
def setup(tmp_path):
    adapter = Adapter()
    paths = []
    for layer in ("source", "curated"):
        created = []
        for name, columns in TABLES.items():
            identifier = layer + "-" + name
            fqn = "sdk_synthetic_" + layer + ".bank.schema." + name
            created.append({"kind": "table", "id": identifier, "fqn": fqn})
            adapter.tables[identifier] = {
                "id": identifier,
                "fullyQualifiedName": fqn,
                "version": 1,
                "domains": [{"name": "Banking"}],
                "columns": [{"name": col[0], "dataType": col[1]} for col in columns],
            }
        path = tmp_path / (layer + ".json")
        path.write_text(
            json.dumps(
                {
                    "status": "created",
                    "destination_sha256": samples._destination(adapter),
                    "created": created,
                }
            )
        )
        paths.append(path)
    return adapter, paths, tmp_path / "samples.json"


def test_review_and_successful_upload(setup, monkeypatch):
    adapter, paths, manifest = setup
    review = samples.review(adapter, *paths)
    assert len(review["operations"]) == 14
    assert all(len(op["payload"]["rows"]) == 3 for op in review["operations"])

    def write(adapter, method, path, payload):
        adapter.samples[path.split("/")[1]] = payload

    monkeypatch.setattr(samples, "_request_write", write)
    result = samples.execute(adapter, *paths, review["review_sha256"], manifest)
    assert result["status"] == "created"
    assert len(result["created"]) == 14
    with pytest.raises(IntegrationError, match="Existing sample"):
        samples.review(adapter, *paths)


def test_changed_review_and_unknown_outcome(setup, monkeypatch):
    adapter, paths, manifest = setup
    review = samples.review(adapter, *paths)
    with pytest.raises(IntegrationError, match="Review changed"):
        samples.execute(adapter, *paths, "bad", manifest)

    def fail(*args):
        raise samples.UnknownOutcome("uncertain")

    monkeypatch.setattr(samples, "_request_write", fail)
    with pytest.raises(samples.UnknownOutcome):
        samples.execute(adapter, *paths, review["review_sha256"], manifest)
    data = json.loads(manifest.read_text())
    assert data["status"] == "unknown"
    assert data["pending"] and not data["created"]


def test_schema_and_domain_conflicts(setup):
    adapter, paths, _ = setup
    adapter.tables["source-customers"]["columns"] = []
    with pytest.raises(IntegrationError, match="schema changed"):
        samples.review(adapter, *paths)
