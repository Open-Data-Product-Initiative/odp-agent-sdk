"""Review and upload fictional catalog samples to the synthetic banking tables."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote

from examples.integrations.synthetic_banking_plan import TABLES
from examples.integrations.synthetic_banking_seed import (
    UnknownOutcome,
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

ROWS = {
    "customers": [
        ["CUST-001", "retail"],
        ["CUST-002", "small_business"],
        ["CUST-003", "retail"],
    ],
    "accounts": [
        ["ACCT-001", "CUST-001", "active"],
        ["ACCT-002", "CUST-002", "active"],
        ["ACCT-003", "CUST-003", "suspended"],
    ],
    "transactions": [
        ["TXN-001", "ACCT-001", "2026-10-01", 125.50],
        ["TXN-002", "ACCT-002", "2026-10-03", 980.00],
        ["TXN-003", "ACCT-003", "2026-10-05", -45.00],
    ],
    "product_holdings": [
        ["HOLD-001", "CUST-001", "ACCT-001", "current_account"],
        ["HOLD-002", "CUST-002", "ACCT-002", "business_account"],
        ["HOLD-003", "CUST-003", "ACCT-003", "current_account"],
    ],
    "customer_consent": [
        ["CONS-001", "CUST-001", "marketing", "granted"],
        ["CONS-002", "CUST-002", "marketing", "denied"],
        ["CONS-003", "CUST-003", "service", "granted"],
    ],
    "customer_risk_signals": [
        ["SIG-001", "CUST-001", "none"],
        ["SIG-002", "CUST-002", "unusual_activity"],
        ["SIG-003", "CUST-003", "payment_difficulty"],
    ],
    "payment_obligations": [
        ["OBL-001", "ACCT-001", "2026-11-01", "paid"],
        ["OBL-002", "ACCT-002", "2026-11-05", "pending"],
        ["OBL-003", "ACCT-003", "2026-10-15", "overdue"],
    ],
}


def _destination(adapter):
    return hashlib.sha256(adapter.profile.base_url.encode()).hexdigest()


def _sample(adapter, identifier):
    table = adapter._json("tables/" + quote(identifier, safe="") + "/sampleData")
    if table.get("id") != identifier:
        raise IntegrationError("Sample response did not identify the requested table")
    return table.get("sampleData")


def review(adapter, seed_path, split_path):
    """Inspect both manifests, permissions, table schemas, and existing samples."""
    adapter.require_write_access()
    if adapter._json("system/version").get("version") != "2.1.0":
        raise IntegrationError("Expected OpenMetadata 2.1.0")
    manifests = [json.loads(Path(p).read_text()) for p in (seed_path, split_path)]
    if any(
        m.get("status") != "created"
        or m.get("destination_sha256") != _destination(adapter)
        for m in manifests
    ):
        raise IntegrationError(
            "Seed manifests are incomplete or refer to another destination"
        )
    operations = []
    ids = set()
    for m in manifests:
        tables = [x for x in m["created"] if x.get("kind") == "table"]
        if sorted(x["fqn"].rsplit(".", 1)[-1] for x in tables) != sorted(TABLES):
            raise IntegrationError(
                "Manifest does not contain exactly the seven expected tables"
            )
        for item in sorted(tables, key=lambda x: x["fqn"]):
            identifier, fqn = item["id"], item["fqn"]
            name = fqn.rsplit(".", 1)[-1]
            if not fqn.startswith("sdk_synthetic_") or identifier in ids:
                raise IntegrationError("Unexpected or repeated table in manifests")
            ids.add(identifier)
            table = adapter._json(
                "tables/" + quote(identifier, safe="") + "?fields=domains"
            )
            if table.get("id") != identifier or table.get("fullyQualifiedName") != fqn:
                raise IntegrationError("Table identity changed: " + fqn)
            columns = table.get("columns", [])
            if [(c.get("name"), c.get("dataType")) for c in columns] != [
                (c[0], c[1]) for c in TABLES[name]
            ]:
                raise IntegrationError("Table schema changed: " + fqn)
            if not any(
                d.get("fullyQualifiedName", d.get("name")) == "Banking"
                for d in table.get("domains", [])
            ):
                raise IntegrationError("Table is outside the Banking domain: " + fqn)
            perms = adapter._json(
                "permissions/table/" + quote(identifier, safe="")
            ).get("permissions", [])
            if not all(
                any(
                    p.get("operation") == op and p.get("access") == "allow"
                    for p in perms
                )
                for op in ("ViewSampleData", "EditSampleData")
            ):
                raise IntegrationError("Sample permissions unavailable: " + fqn)
            if _sample(adapter, identifier) is not None:
                raise IntegrationError(
                    "Existing sample data will not be overwritten: " + fqn
                )
            operations.append(
                {
                    "id": identifier,
                    "fqn": fqn,
                    "version": table.get("version"),
                    "payload": {
                        "columns": [c[0] for c in TABLES[name]],
                        "rows": ROWS[name],
                    },
                }
            )
    payload = {
        "format": "synthetic-banking-samples-v1",
        "destination_sha256": _destination(adapter),
        "operations": operations,
        "warnings": [
            "Fictional catalog sample rows only; no physical tables or data-source connection.",
            "Source and curated samples are identical; sample writes are not atomic and concurrent changes can race the absence check.",
        ],
    }
    return {"review_sha256": _digest(payload), **payload}


def execute(adapter, seed_path, split_path, reviewed_sha256, manifest_path):
    """Apply exactly the current reviewed samples and journal partial outcomes."""
    current = review(adapter, seed_path, split_path)
    if current["review_sha256"] != reviewed_sha256:
        raise IntegrationError("Review changed; inspect and approve the new review")
    path = Path(manifest_path)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    journal = {
        "format": current["format"],
        "destination_sha256": current["destination_sha256"],
        "review_sha256": reviewed_sha256,
        "status": "in_progress",
        "created": [],
        "pending": None,
    }
    _save(path, journal)
    try:
        for op in current["operations"]:
            if _sample(adapter, op["id"]) is not None:
                raise IntegrationError("Sample appeared after review: " + op["fqn"])
            journal["pending"] = {
                "id": op["id"],
                "fqn": op["fqn"],
                "sample_sha256": _digest(op["payload"]),
            }
            _save(path, journal)
            _request_write(
                adapter,
                "PUT",
                "tables/" + quote(op["id"], safe="") + "/sampleData",
                op["payload"],
            )
            journal["created"].append(journal["pending"])
            journal["pending"] = None
            _save(path, journal)
            actual = _sample(adapter, op["id"])
            if (
                actual is None
                or actual.get("columns") != op["payload"]["columns"]
                or actual.get("rows") != op["payload"]["rows"]
            ):
                raise IntegrationError("Sample readback differs: " + op["fqn"])
        journal["status"] = "created"
    except Exception as exc:
        journal["status"] = "unknown" if isinstance(exc, UnknownOutcome) else "partial"
        journal["error"] = str(exc)
        _save(path, journal)
        raise
    _save(path, journal)
    return journal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("review", "execute"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--connection", default="openmetadata")
    parser.add_argument("--env-file")
    parser.add_argument("--seed-manifest", required=True)
    parser.add_argument("--split-manifest", required=True)
    parser.add_argument("--sample-manifest")
    parser.add_argument("--reviewed-sha256")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    profile = load_integration_config(args.config).select(args.connection)
    load_referenced_env(profile, args.env_file)
    with OpenMetadataAdapter(profile) as adapter:
        if args.action == "review":
            result = review(adapter, args.seed_manifest, args.split_manifest)
        else:
            if not args.confirm or not args.sample_manifest or not args.reviewed_sha256:
                raise IntegrationError(
                    "Execution requires --confirm, --sample-manifest and --reviewed-sha256"
                )
            result = execute(
                adapter,
                args.seed_manifest,
                args.split_manifest,
                args.reviewed_sha256,
                args.sample_manifest,
            )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
