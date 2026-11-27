"""Offline timing harness tests; external services are mocked."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.integrations.handoff_timing_benchmark import (
    PHASES,
    run_case,
    stage_synthetic_source,
    summarize,
    write_report,
)


def source(tmp_path):
    path = tmp_path / "brief.md"
    path.write_text(
        "---\nproduct_id: original\nproduct_name: Customer View\n---\n\n# Customer View\n\nA fictional banking test.\n"
    )
    return path


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return self.value


class FakeServices:
    config = "connections.yaml"
    jira_name = "jira"

    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []

    def preflight(self):
        return {"provider": "fake", "model": "fake"}

    def start_mcp(self, case_dir):
        self.case_dir = case_dir

    def call(self, name, args):
        self.calls.append(name)
        if name == "preview_business_handover":
            return {"reviewed_sha256": "business-review"}
        if name == "create_business_odps_draft":
            assert args["reviewed_sha256"] == "business-review"
            root = Path(args["output"])
            root.mkdir()
            (root / "odps").mkdir()
            (root / "business.md").write_text(
                Path(args["business_document"]).read_text()
            )
            (root / "odps/product.yaml").write_text(
                "product:\n  details:\n    en:\n      description: Fictional customer view.\n"
            )
            return {
                "business_document": "business.md",
                "odps_draft": "odps/product.yaml",
            }
        if name == "preview_implementation_handover":
            return {"reviewed_sha256": "package-review"}
        if name == "create_implementation_handover":
            assert args["reviewed_sha256"] == "package-review"
            root = Path(args["output"])
            (root / "change").mkdir(parents=True)
            (root / "handoff.zip").write_bytes(b"zip")
            return {"change": "change", "package": "handoff.zip"}
        if name == "review_jira_handover":
            return {
                "reviewed_sha256": "jira-review",
                "possible_duplicate_keys": [],
                "attachments": [],
            }
        if name == "deliver_jira_handover":
            assert args["reviewed_sha256"] == "jira-review"
            if self.failure == "jira":
                Path(args["journal_file"]).write_text(
                    json.dumps({"status": "unknown_or_failed"})
                )
                raise RuntimeError("Unknown outcome")
            return {"key": "TEST-1", "url": "https://example.org/TEST-1"}
        raise AssertionError(name)

    def review_marketplace(self, product_path, identity):
        return {"review_sha256": "marketplace-review"}

    def create_marketplace(self, product_path, review):
        assert review["review_sha256"] == "marketplace-review"
        if self.failure == "marketplace":
            raise RuntimeError("Unknown outcome")
        return {"status": "created", "product_id": "product-uuid"}

    def verify_marketplace(self, product_id, product_name):
        return {"product_id": product_id, "listed": True, "searchable": True}

    def discovery_concepts(self, business_path):
        return [{"phrase": "customer", "reason": "test", "source_quote": "customer"}]

    def discover(self, concepts, product_id):
        return {
            "assets": [],
            "lineage": [],
            "contracts": [],
            "errors": [],
            "incomplete": True,
        }

    def validate(self, change):
        return {"odps": "passed", "odcs": "passed", "openspec": {"status": "passed"}}

    def review_contract(self, product_id, contract_path):
        self.calls.append("contract_review")
        if self.failure == "contract_blocked":
            raise ValueError("Contract review blocked")
        return {"review_sha256": "contract-review", "executable": True}

    def import_contract(self, product_id, contract_path, review):
        self.calls.append("contract_import")
        assert review["review_sha256"] == "contract-review"
        if self.failure == "contract":
            raise RuntimeError("Unknown contract import outcome")
        return {"status": "created", "contract_id": "contract-uuid"}

    def verify_contract(self, product_id, contract_path):
        self.calls.append("contract_verification")
        if self.failure == "contract_unverified":
            raise ValueError("Contract readback could not be verified")
        return {"contract_id": "contract-uuid", "preserved_source_integrity": "matched"}

    def verify_jira(self, key, review):
        return {"issue_key": key, "sha256_verified": True}

    def close(self):
        pass


def test_synthetic_source_is_copied_and_identity_is_unique(tmp_path):
    original = source(tmp_path)
    original_text = original.read_text()
    staged = tmp_path / "staged.md"
    identity = stage_synthetic_source(original, staged, "sdk_perf_abc_1")
    assert original.read_text() == original_text
    assert "product_id: sdk_perf_abc_1" in staged.read_text()
    assert "fictional banking test" in staged.read_text()
    assert identity["original_sha256"] != identity["staged_sha256"]
    assert identity["product_name"].startswith("Synthetic benchmark")


def test_full_workflow_records_each_phase_and_total(tmp_path, monkeypatch):
    monkeypatch.setenv("JIRA_PROJECT", "TEST")
    monkeypatch.setenv("JIRA_ISSUE_TYPE_ID", "10")
    service = FakeServices()
    record = run_case(
        source(tmp_path), tmp_path / "case", "sdk_perf_abc_1", service, clock=Clock()
    )
    assert record["status"] == "success" and set(record["phase_seconds"]) == set(PHASES)
    assert all(value == 1 for value in record["phase_seconds"].values())
    assert record["total_seconds"] > sum(record["phase_seconds"].values())
    assert (
        record["marketplace_product_id"] == "product-uuid"
        and record["jira_issue_key"] == "TEST-1"
    )
    assert (
        json.loads((tmp_path / "case/result.json").read_text())["status"] == "success"
    )
    report = write_report(tmp_path, [record], 1)
    assert (
        report["average_under_60_seconds"] is True
        and (tmp_path / "benchmark-results.md").is_file()
    )
    assert report["average_phase_seconds_successful"]["odps_generation"] == 1
    assert record["contract_verification"]["preserved_source_integrity"] == "matched"
    assert service.calls.index("contract_import") < service.calls.index(
        "deliver_jira_handover"
    )


@pytest.mark.parametrize("phase", ["marketplace", "contract", "jira"])
def test_unknown_writes_stop_and_cannot_claim_a_successful_average(
    tmp_path, monkeypatch, phase
):
    monkeypatch.setenv("JIRA_PROJECT", "TEST")
    monkeypatch.setenv("JIRA_ISSUE_TYPE_ID", "10")
    service = FakeServices(failure=phase)
    record = run_case(
        source(tmp_path), tmp_path / "case", "sdk_perf_abc_1", service, clock=Clock()
    )
    assert record["status"] == "unknown_write_outcome"
    assert "inspect" in record["next_step"].lower()
    assert summarize([record], 6)["average_under_60_seconds"] is None
    assert service.calls.count("deliver_jira_handover") <= 1
    if phase in ("marketplace", "contract"):
        assert "deliver_jira_handover" not in service.calls
    if phase == "contract":
        assert service.calls.count("contract_import") == 1


def test_average_is_only_assessed_when_every_case_succeeds():
    cases = [
        {"status": "success", "total_seconds": 40.0},
        {"status": "success", "total_seconds": 100.0},
    ]
    assert summarize(cases, 2)["average_seconds_successful"] == 70.0
    assert summarize(cases, 2)["average_under_60_seconds"] is False
    assert summarize(cases, 6)["average_under_60_seconds"] is None


def test_contract_verification_requires_matching_association_and_source(tmp_path):
    import hashlib
    from examples.integrations.handoff_timing_benchmark import LiveServices

    source_file = tmp_path / "contract.yaml"
    source_file.write_text("kind: DataContract\n")
    digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
    provenance = {"product_id": "product-uuid", "contract_id": "contract-uuid"}
    items = [
        {"origin": "OpenMetadata product contract", "provenance": dict(provenance)},
        {
            "origin": "SDK-preserved ODCS source",
            "sha256": digest,
            "provenance": dict(provenance),
        },
    ]
    service = LiveServices(None, None, None, None)
    service.metadata = SimpleNamespace(
        discover_context=lambda **kwargs: {"contracts": items, "errors": []}
    )
    result = service.verify_contract("product-uuid", source_file)
    assert result["preserved_source_integrity"] == "matched"
    assert "not established" in result["platform_schema_validation"]
    items[1]["provenance"]["product_id"] = "wrong-product"
    with pytest.raises(ValueError, match="could not be verified"):
        service.verify_contract("product-uuid", source_file)
    items[1]["provenance"]["product_id"] = "product-uuid"
    items[1]["sha256"] = "wrong"
    with pytest.raises(ValueError, match="could not be verified"):
        service.verify_contract("product-uuid", source_file)


@pytest.mark.parametrize("phase", ["contract_blocked", "contract_unverified"])
def test_contract_failure_reports_existing_product_without_jira(
    tmp_path, monkeypatch, phase
):
    monkeypatch.setenv("JIRA_PROJECT", "TEST")
    monkeypatch.setenv("JIRA_ISSUE_TYPE_ID", "10")
    service = FakeServices(failure=phase)
    record = run_case(
        source(tmp_path), tmp_path / "case", "sdk_perf_abc_1", service, clock=Clock()
    )
    assert record["status"] == "failed"
    assert record["marketplace_product_id"] == "product-uuid"
    assert "product already exists" in record["next_step"]
    assert "deliver_jira_handover" not in service.calls


def test_marketplace_review_reports_name_mismatch_before_create(tmp_path):
    from examples.integrations.handoff_timing_benchmark import LiveServices

    product = tmp_path / "product.yaml"
    product.write_text("synthetic")
    review = SimpleNamespace(
        executable=True, product_id="expected", product_name="Different"
    )
    service = LiveServices(None, None, None, "Banking")
    service.metadata = SimpleNamespace(review_create=lambda *args, **kwargs: review)
    with pytest.raises(ValueError, match="product name does not match"):
        service.review_marketplace(
            product, {"product_id": "expected", "product_name": "Expected"}
        )
