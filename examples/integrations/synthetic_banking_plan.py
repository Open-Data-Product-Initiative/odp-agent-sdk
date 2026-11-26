"""Preview synthetic banking metadata for a future reviewed OpenMetadata seed."""

import argparse
import hashlib
import json
from pathlib import Path

from open_data_products.integrations.config import load_integration_config

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "openmetadata_banking_poc"
PRODUCTS = (
    "campaign-eligibility",
    "customer-lifetime-value",
    "customer-vulnerability-profile",
    "financial-crime-risk-profile",
    "payment-delinquency-forecast",
    "product-holdings",
)
# All identifiers and values describe fictional metadata; there are no rows.
TABLES = {
    "customers": [
        ("customer_id", "VARCHAR", "Synthetic customer identifier"),
        ("customer_segment", "VARCHAR", "Fictional customer segment"),
    ],
    "accounts": [
        ("account_id", "VARCHAR", "Synthetic account identifier"),
        ("customer_id", "VARCHAR", "References customers.customer_id"),
        ("account_status", "VARCHAR", "Synthetic account status"),
    ],
    "transactions": [
        ("transaction_id", "VARCHAR", "Synthetic transaction identifier"),
        ("account_id", "VARCHAR", "References accounts.account_id"),
        ("transaction_date", "DATE", "Fictional transaction date"),
        ("amount", "DECIMAL", "Synthetic transaction amount"),
    ],
    "product_holdings": [
        ("holding_id", "VARCHAR", "Synthetic holding identifier"),
        ("customer_id", "VARCHAR", "References customers.customer_id"),
        ("account_id", "VARCHAR", "References accounts.account_id"),
        ("product_type", "VARCHAR", "Fictional product category"),
    ],
    "customer_consent": [
        ("consent_id", "VARCHAR", "Synthetic consent identifier"),
        ("customer_id", "VARCHAR", "References customers.customer_id"),
        ("purpose", "VARCHAR", "Fictional consent purpose"),
        ("consent_status", "VARCHAR", "Fictional consent status"),
    ],
    "customer_risk_signals": [
        ("signal_id", "VARCHAR", "Synthetic signal identifier"),
        ("customer_id", "VARCHAR", "References customers.customer_id"),
        ("signal_type", "VARCHAR", "Fictional risk or vulnerability signal type"),
    ],
    "payment_obligations": [
        ("obligation_id", "VARCHAR", "Synthetic obligation identifier"),
        ("account_id", "VARCHAR", "References accounts.account_id"),
        ("due_date", "DATE", "Fictional payment due date"),
        ("payment_status", "VARCHAR", "Fictional payment status"),
    ],
}
LINKS = {
    "campaign-eligibility": ["customers", "product_holdings", "customer_consent"],
    "customer-lifetime-value": [
        "customers",
        "accounts",
        "transactions",
        "product_holdings",
    ],
    "customer-vulnerability-profile": [
        "customers",
        "customer_risk_signals",
        "customer_consent",
    ],
    "financial-crime-risk-profile": [
        "customers",
        "accounts",
        "transactions",
        "customer_risk_signals",
    ],
    "payment-delinquency-forecast": ["accounts", "transactions", "payment_obligations"],
    "product-holdings": ["customers", "accounts", "product_holdings"],
}


def build_plan(config_path, connection="openmetadata"):
    """Build a deterministic local preview without contacting OpenMetadata."""
    profile = load_integration_config(config_path).select(connection)
    if profile.platform != "openmetadata":
        raise ValueError("OpenMetadata connection required")
    fixtures = []
    for slug in PRODUCTS:
        source = FIXTURES / "sources" / (slug + ".md")
        product = FIXTURES / "products" / ("odps_product_" + slug + ".yaml")
        fixtures.append(
            {
                "product": slug,
                "business_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "odps_sha256": hashlib.sha256(product.read_bytes()).hexdigest(),
                "candidate_assets": LINKS[slug],
            }
        )
    plan = {
        "format": "synthetic-banking-metadata-preview-v1",
        "connection": profile.name,
        "destination_sha256": hashlib.sha256(profile.base_url.encode()).hexdigest(),
        "service": {
            "name": "sdk_synthetic_banking",
            "serviceType": "CustomDatabase",
            "description": "Synthetic test metadata only; no physical source connection is asserted.",
        },
        "database": "synthetic_bank",
        "schema": "sdk_test",
        "tables": [
            {
                "name": name,
                "description": "Synthetic banking test metadata; no physical table or sample data.",
                "columns": [
                    {
                        "name": n,
                        "dataType": t,
                        "description": d,
                        **({"dataLength": 255} if t == "VARCHAR" else {}),
                    }
                    for n, t, d in columns
                ],
            }
            for name, columns in TABLES.items()
        ],
        "proposed_lineage": [
            ["customers", "product_holdings"],
            ["accounts", "transactions"],
            ["accounts", "payment_obligations"],
        ],
        "product_candidates": fixtures,
        "proposed_contract": {
            "purpose": "Synthetic test contract proposal; not validated or enforced",
            "product_candidate": "product-holdings",
            "schema": [
                {
                    "name": "product_holdings",
                    "properties": [
                        {
                            "name": "holding_id",
                            "logicalType": "string",
                            "description": "Synthetic holding identifier",
                        },
                        {
                            "name": "customer_id",
                            "logicalType": "string",
                            "description": "Synthetic customer reference",
                        },
                        {
                            "name": "account_id",
                            "logicalType": "string",
                            "description": "Synthetic account reference",
                        },
                    ],
                }
            ],
        },
        "proposed_quality_expectations": [
            "Synthetic holding identifiers are present and unique.",
            "Synthetic customer references are present.",
        ],
        "limitations": [
            "This command only previews; execution and cleanup use the separate reviewed seed workflow.",
            "OpenMetadata 2.1.0 request formats, permissions and metadata-only service acceptance must be verified against the target.",
            "Inspect the separately reviewed seed operations for product associations and contract handling.",
        ],
    }
    plan["review_sha256"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return plan


def inspect_target(plan, adapter):
    """Inspect server version, basic permissions and proposed name conflicts."""
    from urllib.parse import quote
    from open_data_products.integrations.openmetadata import PlatformError

    if (
        hashlib.sha256(adapter.profile.base_url.encode()).hexdigest()
        != plan["destination_sha256"]
    ):
        raise ValueError("Preview destination does not match the selected connection")
    version = adapter._json("system/version").get("version")
    permissions = {}
    errors = []
    for resource in (
        "databaseService",
        "database",
        "databaseSchema",
        "table",
        "dataProduct",
        "domain",
        "dataContract",
    ):
        try:
            data = adapter._json("permissions/" + resource)
            entries = data.get("permissions", [])
            permissions[resource] = next(
                (
                    x.get("access")
                    for x in entries
                    if isinstance(x, dict) and x.get("operation") == "Create"
                ),
                "unknown",
            )
        except PlatformError as exc:
            permissions[resource] = "unknown"
            errors.append({"resource": "permissions/" + resource, "status": exc.status})
    service = plan["service"]["name"]
    database = service + "." + plan["database"]
    schema = database + "." + plan["schema"]
    names = [
        ("databaseService", "services/databaseServices", service),
        ("database", "databases", database),
        ("databaseSchema", "databaseSchemas", schema),
    ]
    names.extend(
        ("table", "tables", schema + "." + table["name"]) for table in plan["tables"]
    )
    conflicts = []
    for kind, endpoint, fqn in names:
        try:
            entity = adapter._json(endpoint + "/name/" + quote(fqn, safe=""))
            conflicts.append({"type": kind, "fqn": fqn, "id": entity.get("id")})
        except PlatformError as exc:
            if exc.status != 404:
                errors.append({"resource": kind + ":" + fqn, "status": exc.status})
    return {
        "server_version": version,
        "permissions": permissions,
        "conflicts": conflicts,
        "errors": errors,
        "write_ready": False,
        "reason": "This inspection is read-only; use the separate seed review before execution.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--connection", default="openmetadata")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Read server version, permissions and conflicts",
    )
    args = parser.parse_args()
    plan = build_plan(args.config, args.connection)
    if args.inspect:
        from open_data_products.integrations.openmetadata import OpenMetadataAdapter

        with OpenMetadataAdapter(
            load_integration_config(args.config).select(args.connection)
        ) as adapter:
            plan["target_inspection"] = inspect_target(plan, adapter)
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
