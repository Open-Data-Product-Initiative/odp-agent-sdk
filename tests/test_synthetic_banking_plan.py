"""Check the offline synthetic banking metadata preview."""

import json

from examples.integrations.synthetic_banking_plan import build_plan


def test_preview_is_deterministic_and_contains_no_credentials(tmp_path, monkeypatch):
    config = tmp_path / "connections.yaml"
    config.write_text("""version: 1
default_connection: openmetadata
connections:
  openmetadata:
    platform: openmetadata
    base_url: https://metadata.example.org
    read_only: false
    auth:
      type: bearer_token
      token:
        source: env
        name: SYNTHETIC_TEST_TOKEN
""")
    monkeypatch.setenv("SYNTHETIC_TEST_TOKEN", "test-secret-not-for-output")
    one = build_plan(config)
    two = build_plan(config)
    assert one == two
    assert len(one["product_candidates"]) == 6
    assert len(one["tables"]) == 7
    assert all("synthetic" in table["description"].lower() for table in one["tables"])
    assert "test-secret-not-for-output" not in json.dumps(one)
    assert "only previews" in one["limitations"][0]
    names = {table["name"] for table in one["tables"]}
    assert all(
        set(item["candidate_assets"]) <= names for item in one["product_candidates"]
    )


def test_preflight_reports_conflict_and_denial_without_writes(tmp_path):
    from types import SimpleNamespace
    from open_data_products.integrations.openmetadata import PlatformError
    from examples.integrations.synthetic_banking_plan import inspect_target

    config = tmp_path / "config.yaml"
    config.write_text("""version: 1
default_connection: om
connections:
  om:
    platform: openmetadata
    base_url: https://metadata.example.org
    auth:
      type: bearer_token
      token: {source: env, name: TOKEN}
""")
    plan = build_plan(config, "om")

    class Fake:
        profile = SimpleNamespace(base_url="https://metadata.example.org")

        def _json(self, path):
            if path == "system/version":
                return {"version": "2.1.0"}
            if path == "permissions/table":
                return {"permissions": [{"operation": "Create", "access": "deny"}]}
            if path.startswith("permissions/"):
                return {"permissions": [{"operation": "Create", "access": "allow"}]}
            if path == "services/databaseServices/name/sdk_synthetic_banking":
                return {"id": "existing"}
            raise PlatformError("Missing", 404)

    report = inspect_target(plan, Fake())
    assert report["permissions"]["table"] == "deny"
    assert report["conflicts"][0]["id"] == "existing"
    assert report["write_ready"] is False
