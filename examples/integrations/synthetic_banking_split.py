"""Review a metadata-only split into source services and a curated layer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib import error, request
from urllib.parse import quote, urlencode
from http.client import HTTPException
from uuid import UUID

from examples.integrations.synthetic_banking_domain import inspect_catalog
from examples.integrations.synthetic_banking_seed import (
    LABEL,
    UnknownOutcome,
    _digest,
    _request_write,
    _save,
    load_referenced_env,
)
from open_data_products.integrations import (
    IntegrationError,
    OpenMetadataAdapter,
    PlatformError,
    load_integration_config,
)

DOMAIN = "Banking"
ROLES = {
    "sdk_synthetic_customer_consent": (
        "Customer and consent",
        ("customers", "customer_consent", "customer_risk_signals"),
    ),
    "sdk_synthetic_core_banking": ("Core banking", ("accounts", "product_holdings")),
    "sdk_synthetic_payments": ("Payments", ("transactions", "payment_obligations")),
}
CURATED_DESCRIPTION = (
    "Synthetic curated analytics metadata for SDK discovery tests. "
    "No physical database, source connection, or customer data is represented."
)


def review_split(adapter, seed_manifest):
    """Review exact synthetic source creates, lineage and curated designation."""
    if (
        adapter.profile.read_only
        or adapter._json("system/version").get("version") != "2.1.0"
    ):
        raise IntegrationError("A writable OpenMetadata 2.1.0 profile is required")
    baseline = inspect_catalog(
        adapter, seed_manifest, expected_domain=DOMAIN, require_links=True
    )
    target = adapter._json("domains/name/Banking")
    if target.get("fullyQualifiedName") != DOMAIN:
        raise IntegrationError("Banking domain identity changed")
    for resource, required in (
        ("databaseService", ("Create",)),
        ("database", ("Create",)),
        ("databaseSchema", ("Create",)),
        ("table", ("Create", "EditAll")),
    ):
        entries = adapter._json("permissions/" + resource).get("permissions", [])
        if any(
            not any(
                isinstance(e, dict)
                and e.get("operation") == operation
                and e.get("access") == "allow"
                for e in entries
            )
            for operation in required
        ):
            raise IntegrationError("Required permission unavailable for " + resource)
    curated = next(x for x in baseline["entities"] if x["kind"] == "service")
    permissions = adapter._json(
        "permissions/databaseService/" + quote(curated["id"], safe="")
    ).get("permissions", [])
    if not any(
        x.get("operation") in ("EditDescription", "EditAll")
        and x.get("access") == "allow"
        for x in permissions
        if isinstance(x, dict)
    ):
        raise IntegrationError(
            "Curated service description edit permission unavailable"
        )
    old_service = adapter._json(
        "services/databaseServices/" + quote(curated["id"], safe="")
    )
    if (
        old_service.get("id") != curated["id"]
        or old_service.get("version") != curated["version"]
        or isinstance(old_service.get("version"), bool)
        or not isinstance(old_service.get("version"), (int, float))
    ):
        raise IntegrationError("Curated service changed or its revision is unavailable")
    original_tables = {
        x["fqn"].rsplit(".", 1)[-1]: x
        for x in baseline["entities"]
        if x["kind"] == "table"
    }
    ops = []
    for service, (title, names) in ROLES.items():
        database = service + ".synthetic_bank"
        schema = database + ".source"
        desc = (
            "Synthetic "
            + title
            + " source metadata for SDK tests; no real connection or records."
        )
        ops.extend(
            [
                {
                    "kind": "service",
                    "path": "services/databaseServices",
                    "fqn": service,
                    "payload": {
                        "name": service,
                        "serviceType": "CustomDatabase",
                        "description": desc,
                        "domains": [DOMAIN],
                    },
                },
                {
                    "kind": "database",
                    "path": "databases",
                    "fqn": database,
                    "payload": {
                        "name": "synthetic_bank",
                        "service": service,
                        "description": desc,
                        "domains": [DOMAIN],
                    },
                },
                {
                    "kind": "databaseSchema",
                    "path": "databaseSchemas",
                    "fqn": schema,
                    "payload": {
                        "name": "source",
                        "database": database,
                        "description": desc,
                        "domains": [DOMAIN],
                    },
                },
            ]
        )
        for name in names:
            original = original_tables[name]
            table = adapter._json(
                "tables/"
                + quote(original["id"], safe="")
                + "?"
                + urlencode({"fields": "domains,dataProducts"})
            )
            if (
                table.get("version") != original["version"]
                or table.get("id") != original["id"]
            ):
                raise IntegrationError("Curated table changed during review")
            columns = table.get("columns")
            if not isinstance(columns, list) or not columns:
                raise IntegrationError("Curated table columns unavailable: " + name)
            safe_columns = [
                {
                    k: col[k]
                    for k in (
                        "name",
                        "dataType",
                        "dataLength",
                        "precision",
                        "scale",
                        "description",
                    )
                    if k in col
                }
                for col in columns
                if isinstance(col, dict)
            ]
            if len(safe_columns) != len(columns) or any(
                not c.get("name") or not c.get("dataType") for c in safe_columns
            ):
                raise IntegrationError("Curated column metadata is incomplete")
            ops.append(
                {
                    "kind": "table",
                    "path": "tables",
                    "fqn": schema + "." + name,
                    "payload": {
                        "name": name,
                        "databaseSchema": schema,
                        "description": desc,
                        "columns": safe_columns,
                        "domains": [DOMAIN],
                    },
                    "curated_target_id": original["id"],
                }
            )
    for op in ops:
        try:
            adapter._json(op["path"] + "/name/" + quote(op["fqn"], safe=""))
        except PlatformError as exc:
            if exc.status == 404:
                continue
            raise
        raise IntegrationError("Proposed source entity already exists: " + op["fqn"])
    edges = [
        {"source_fqn": op["fqn"], "target_id": op["curated_target_id"]}
        for op in ops
        if op["kind"] == "table"
    ]
    patch = {
        "id": curated["id"],
        "fqn": curated["fqn"],
        "version": old_service.get("version"),
        "before": old_service.get("description"),
        "after": CURATED_DESCRIPTION,
    }
    payload = {
        "destination_sha256": baseline["destination_sha256"],
        "seed_manifest_sha256": baseline["seed_manifest_sha256"],
        "target_domain": DOMAIN,
        "baseline": baseline,
        "creates": ops,
        "source_to_curated_lineage": edges,
        "curated_service_description": patch,
        "warnings": [
            "New source metadata duplicates the existing column definitions; old tables remain as curated metadata.",
            "Lineage is synthetic documentation, not proof of a running pipeline.",
            "The workflow changes no existing product or table links and creates no physical data or connections.",
            "New service connection acceptance and API outcomes are checked at execution; unknown writes stop the run.",
            "The curated description patch uses If-Match; enforcement and concurrent edits are rechecked but cannot be assumed atomic.",
        ],
    }
    return {"review_sha256": _digest(payload), **payload}


def _patch_service(adapter, service_id, revision, description):
    """Patch one reviewed description once with an optimistic revision guard."""
    base = adapter.profile.base_url
    url = (
        base
        + ("/v1/" if base.endswith("/api") else "/api/v1/")
        + "services/databaseServices/"
        + quote(service_id, safe="")
    )
    token = adapter.profile.token()
    body = json.dumps(
        [{"op": "add", "path": "/description", "value": description}]
    ).encode()
    req = request.Request(
        url,
        method="PATCH",
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json-patch+json",
            "Accept": "application/json",
            "If-Match": 'W/"' + str(revision) + '"',
        },
    )
    try:
        with adapter._opener.open(
            req, timeout=adapter.profile.timeout_seconds
        ) as response:
            if response.status not in (200, 204):
                raise UnknownOutcome(
                    "Service update outcome unknown; inspect before retry"
                )
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code == 408 or code >= 500 or 300 <= code < 400:
            raise UnknownOutcome(
                "Service update outcome unknown; inspect before retry"
            ) from None
        raise PlatformError("Service update returned HTTP " + str(code), code) from None
    except (error.URLError, TimeoutError, OSError, HTTPException):
        raise UnknownOutcome(
            "Service update outcome unknown; inspect before retry"
        ) from None


def execute_split(adapter, seed_manifest, *, reviewed_sha256, manifest_path):
    """Apply the reviewed metadata changes once and journal every remote write."""
    adapter.require_write_access()
    review = review_split(adapter, seed_manifest)
    if review["review_sha256"] != reviewed_sha256:
        raise IntegrationError("Split review changed; review again")
    path = Path(manifest_path)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    journal = {
        "format": "synthetic-banking-split-v1",
        "destination_sha256": review["destination_sha256"],
        "seed_manifest_sha256": review["seed_manifest_sha256"],
        "review_sha256": reviewed_sha256,
        "status": "in_progress",
        "created": [],
        "description_change": None,
        "pending": None,
    }
    _save(path, journal)
    try:
        created = {}
        for op in review["creates"]:
            journal["pending"] = {"kind": op["kind"], "fqn": op["fqn"]}
            _save(path, journal)
            response = _request_write(adapter, "POST", op["path"], op["payload"])
            identifier = response.get("id")
            try:
                identifier = str(UUID(identifier))
            except (ValueError, TypeError, AttributeError):
                raise UnknownOutcome(
                    "Create returned no usable ID; inspect before retry"
                ) from None
            record = {
                "kind": op["kind"],
                "path": op["path"],
                "fqn": op["fqn"],
                "id": identifier,
            }
            journal["created"].append(record)
            created[op["fqn"]] = identifier
            journal["pending"] = None
            _save(path, journal)
        for edge in review["source_to_curated_lineage"]:
            source_id = created[edge["source_fqn"]]
            target_id = edge["target_id"]
            journal["pending"] = {
                "kind": "lineage",
                "source_id": source_id,
                "target_id": target_id,
            }
            _save(path, journal)
            _request_write(
                adapter,
                "PUT",
                "lineage",
                {
                    "edge": {
                        "fromEntity": {"id": source_id, "type": "table"},
                        "toEntity": {"id": target_id, "type": "table"},
                        "description": "Synthetic source-to-curated test lineage; no running pipeline is asserted.",
                    }
                },
            )
            journal["created"].append(
                {"kind": "lineage", "source_id": source_id, "target_id": target_id}
            )
            journal["pending"] = None
            _save(path, journal)
        patch = review["curated_service_description"]
        current = adapter._json(
            "services/databaseServices/" + quote(patch["id"], safe="")
        )
        if (
            current.get("version") != patch["version"]
            or current.get("description") != patch["before"]
        ):
            raise IntegrationError(
                "Curated service changed; description update blocked"
            )
        journal["pending"] = {"kind": "curated_description", "id": patch["id"]}
        _save(path, journal)
        _patch_service(adapter, patch["id"], patch["version"], patch["after"])
        journal["description_change"] = patch
        journal["pending"] = None
        _save(path, journal)
        verified_service = adapter._json(
            "services/databaseServices/" + quote(patch["id"], safe="")
        )
        if verified_service.get("description") != patch["after"]:
            raise IntegrationError("Curated service description was not verified")
        for op in review["creates"]:
            data = adapter._json(
                op["path"]
                + "/"
                + quote(created[op["fqn"]], safe="")
                + "?"
                + urlencode({"fields": "domains"})
            )
            domains = data.get("domains") or []
            if (
                data.get("id") != created[op["fqn"]]
                or data.get("fullyQualifiedName") != op["fqn"]
                or not any(
                    isinstance(x, dict)
                    and (
                        x.get("name") == DOMAIN or x.get("fullyQualifiedName") == DOMAIN
                    )
                    for x in domains
                )
            ):
                raise IntegrationError(
                    "Created entity identity or domain was not verified: " + op["fqn"]
                )
            if op["kind"] == "table":
                actual = data.get("columns")
                if not isinstance(actual, list) or [
                    (c.get("name"), c.get("dataType")) for c in actual
                ] != [(c["name"], c["dataType"]) for c in op["payload"]["columns"]]:
                    raise IntegrationError(
                        "Source table schema was not verified: " + op["fqn"]
                    )
        for edge in review["source_to_curated_lineage"]:
            source_id = created[edge["source_fqn"]]
            graph = adapter._json(
                "lineage/table/"
                + quote(source_id, safe="")
                + "?upstreamDepth=1&downstreamDepth=1"
            )
            if not any(
                isinstance(row, dict)
                and row.get("fromEntity") == source_id
                and row.get("toEntity") == edge["target_id"]
                for row in graph.get("downstreamEdges", [])
            ):
                raise IntegrationError(
                    "Source-to-curated lineage was not verified: " + edge["source_fqn"]
                )
        after = inspect_catalog(
            adapter, seed_manifest, expected_domain=DOMAIN, require_links=True
        )
        if (
            after["links"] != review["baseline"]["links"]
            or after["lineage"] != review["baseline"]["lineage"]
            or after["preserved_contract_sha256"]
            != review["baseline"]["preserved_contract_sha256"]
        ):
            raise IntegrationError(
                "Existing product links, lineage or contract changed"
            )
        journal["verification"] = {
            "new_services": 3,
            "new_databases": 3,
            "new_schemas": 3,
            "new_tables": 7,
            "new_lineage": 7,
            "existing_product_links": sum(len(x["asset_ids"]) for x in after["links"]),
            "existing_lineage": len(after["lineage"]),
            "contract_sha256": after["preserved_contract_sha256"],
        }
        journal["status"] = "created"
    except (IntegrationError, OSError, ValueError, KeyError) as exc:
        journal["status"] = (
            "unknown"
            if isinstance(exc, (UnknownOutcome, OSError))
            or "unknown" in type(exc).__name__.lower()
            else "partial"
        )
        journal["error"] = str(exc)
    _save(path, journal)
    return journal


def review_split_cleanup(adapter, seed_manifest, split_manifest):
    """Review only split-created metadata and its recorded description change."""
    seed_path, split_path = Path(seed_manifest), Path(split_manifest)
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    journal = json.loads(split_path.read_text(encoding="utf-8"))
    if (
        journal.get("format") != "synthetic-banking-split-v1"
        or journal.get("status") not in ("created", "partial")
        or journal.get("cleanup")
        or journal.get("destination_sha256")
        != hashlib.sha256(adapter.profile.base_url.encode()).hexdigest()
        or journal.get("seed_manifest_sha256")
        != hashlib.sha256(seed_path.read_bytes()).hexdigest()
    ):
        raise IntegrationError(
            "Split manifest is uncertain, modified, already in cleanup, or belongs to another target"
        )
    created = journal.get("created")
    if not isinstance(created, list):
        raise IntegrationError("Invalid split manifest")
    paths = {
        "service": "services/databaseServices",
        "database": "databases",
        "databaseSchema": "databaseSchemas",
        "table": "tables",
    }
    allowed = {}
    for service, (_, names) in ROLES.items():
        database, schema = (
            service + ".synthetic_bank",
            service + ".synthetic_bank.source",
        )
        allowed[service] = ("service", paths["service"])
        allowed[database] = ("database", paths["database"])
        allowed[schema] = ("databaseSchema", paths["databaseSchema"])
        for name in names:
            allowed[schema + "." + name] = ("table", paths["table"])
    curated_tables = {
        x["id"] for x in seed.get("created", []) if x.get("kind") == "table"
    }
    source_tables = {x.get("id") for x in created if x.get("kind") == "table"}
    if len(source_tables) != sum(x.get("kind") == "table" for x in created):
        raise IntegrationError("Duplicate source table IDs in split manifest")
    edges = [
        (x.get("source_id"), x.get("target_id"))
        for x in created
        if x.get("kind") == "lineage"
    ]
    if len(set(edges)) != len(edges) or any(
        a not in source_tables or b not in curated_tables for a, b in edges
    ):
        raise IntegrationError(
            "Lineage is not confined to recorded source and curated tables"
        )
    targets = []
    change = journal.get("description_change")
    if change:
        curated_service = next(
            (x for x in seed.get("created", []) if x.get("kind") == "service"), None
        )
        if (
            not curated_service
            or change.get("id") != curated_service.get("id")
            or change.get("after") != CURATED_DESCRIPTION
        ):
            raise IntegrationError("Curated service description record is invalid")
        current = adapter._json(
            "services/databaseServices/" + quote(change["id"], safe="")
        )
        if (
            current.get("id") != change["id"]
            or current.get("description") != change["after"]
        ):
            raise IntegrationError(
                "Curated service description changed; cleanup blocked"
            )
        targets.append(
            {
                "kind": "restore_description",
                "id": change["id"],
                "version": current.get("version"),
                "description": change.get("before"),
            }
        )
    for record in reversed(created):
        kind = record.get("kind")
        if kind == "lineage":
            source, target = str(UUID(record["source_id"])), str(
                UUID(record["target_id"])
            )
            graph = adapter._json(
                "lineage/table/"
                + quote(source, safe="")
                + "?upstreamDepth=1&downstreamDepth=1"
            )
            if not any(
                isinstance(e, dict)
                and e.get("fromEntity") == source
                and e.get("toEntity") == target
                for e in graph.get("downstreamEdges", [])
            ):
                raise IntegrationError("Recorded source lineage is unavailable")
            targets.append(
                {
                    "kind": "lineage",
                    "path": "lineage/table/" + source + "/table/" + target,
                }
            )
            continue
        fqn, identifier = record.get("fqn"), str(UUID(record.get("id")))
        if fqn not in allowed or (kind, record.get("path")) != allowed[fqn]:
            raise IntegrationError(
                "Split entity is outside the reviewed synthetic namespace"
            )
        fields = "domains,dataProducts" if kind == "table" else "domains"
        entity = adapter._json(
            record["path"] + "/" + identifier + "?" + urlencode({"fields": fields})
        )
        if (
            entity.get("id") != identifier
            or entity.get("fullyQualifiedName") != fqn
            or "Synthetic" not in str(entity.get("description", ""))
        ):
            raise IntegrationError("Split entity identity or synthetic label changed")
        if kind == "table":
            if entity.get("dataProducts"):
                raise IntegrationError(
                    "Source table has product links; cleanup requires manual inspection"
                )
            graph = adapter._json(
                "lineage/table/" + identifier + "?upstreamDepth=1&downstreamDepth=1"
            )
            actual_edges = {
                (x.get("fromEntity"), x.get("toEntity"))
                for key in ("upstreamEdges", "downstreamEdges")
                for x in graph.get(key, [])
                if isinstance(x, dict)
            }
            expected_edges = {(a, b) for a, b in edges if a == identifier}
            if actual_edges != expected_edges:
                raise IntegrationError("Source table has unrecorded or missing lineage")
        targets.append(
            {
                "kind": kind,
                "path": record["path"]
                + "/"
                + identifier
                + "?recursive=false&hardDelete=false",
                "version": entity.get("version"),
            }
        )
    # Non-recursive deletion is still refused if unrecorded children appeared.
    for service in ROLES:
        filters = [
            ("databases", {"service": service}, "database", service + "."),
            (
                "databaseSchemas",
                {"database": service + ".synthetic_bank"},
                "databaseSchema",
                service + ".",
            ),
            (
                "tables",
                {"databaseSchema": service + ".synthetic_bank.source"},
                "table",
                service + ".",
            ),
        ]
        for endpoint, query, kind, prefix in filters:
            parent_kind = {
                "databases": "service",
                "databaseSchemas": "database",
                "tables": "databaseSchema",
            }[endpoint]
            if not any(
                x.get("kind") == parent_kind
                and str(x.get("fqn", "")).startswith(
                    prefix if parent_kind != "service" else service
                )
                for x in created
            ):
                continue
            expected = {
                x["id"]
                for x in created
                if x.get("kind") == kind and str(x.get("fqn", "")).startswith(prefix)
            }
            result = adapter._json(endpoint + "?" + urlencode({**query, "limit": 100}))
            rows, paging = result.get("data"), result.get("paging")
            if (
                not isinstance(rows, list)
                or not isinstance(paging, dict)
                or paging.get("after")
                or paging.get("total") != len(rows)
                or {x.get("id") for x in rows if isinstance(x, dict)} != expected
            ):
                raise IntegrationError("Unrecorded children prevent split cleanup")
    payload = {
        "destination_sha256": journal["destination_sha256"],
        "split_manifest_sha256": hashlib.sha256(split_path.read_bytes()).hexdigest(),
        "seed_manifest_sha256": journal["seed_manifest_sha256"],
        "targets": targets,
        "warnings": [
            "Only recorded source entities and lineage are removed, using non-recursive soft deletes.",
            "The existing curated service description is restored only if unchanged.",
            "No atomic server-wide lock exists; changes after review may still race.",
        ],
    }
    return {"review_sha256": _digest(payload), **payload}


def execute_split_cleanup(
    adapter, seed_manifest, split_manifest, *, reviewed_sha256, confirm
):
    """Apply separately confirmed cleanup without deleting curated products or tables."""
    adapter.require_write_access()
    if confirm is not True:
        raise IntegrationError("Split cleanup requires explicit confirmation")
    reviewed = review_split_cleanup(adapter, seed_manifest, split_manifest)
    if reviewed["review_sha256"] != reviewed_sha256:
        raise IntegrationError("Split cleanup review changed")
    path = Path(split_manifest)
    journal = json.loads(path.read_text(encoding="utf-8"))
    journal["cleanup"] = {"status": "in_progress", "completed": [], "pending": None}
    _save(path, journal)
    for target in reviewed["targets"]:
        journal["cleanup"]["pending"] = target
        _save(path, journal)
        try:
            if target["kind"] == "restore_description":
                _patch_service(
                    adapter, target["id"], target["version"], target["description"]
                )
            else:
                _request_write(adapter, "DELETE", target["path"])
        except (IntegrationError, OSError) as exc:
            journal["cleanup"]["status"] = (
                "unknown"
                if isinstance(exc, UnknownOutcome) or isinstance(exc, OSError)
                else "partial"
            )
            journal["cleanup"]["error"] = str(exc)
            _save(path, journal)
            return journal["cleanup"]
        journal["cleanup"]["completed"].append(target)
        journal["cleanup"]["pending"] = None
        _save(path, journal)
    journal["cleanup"]["status"] = "completed"
    journal["status"] = "cleaned"
    _save(path, journal)
    return journal["cleanup"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("review", "execute", "cleanup-review", "cleanup-execute")
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--connection", default="openmetadata")
    parser.add_argument("--env-file")
    parser.add_argument("--seed-manifest", required=True)
    parser.add_argument("--split-manifest")
    parser.add_argument("--reviewed-sha256")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    profile = load_integration_config(args.config).select(args.connection)
    load_referenced_env(profile, args.env_file)
    with OpenMetadataAdapter(profile) as adapter:
        if args.action == "review":
            result = review_split(adapter, args.seed_manifest)
        elif args.action == "execute":
            if not args.split_manifest or not args.reviewed_sha256 or not args.confirm:
                raise IntegrationError(
                    "Split execution requires --split-manifest, --reviewed-sha256 and --confirm"
                )
            result = execute_split(
                adapter,
                args.seed_manifest,
                reviewed_sha256=args.reviewed_sha256,
                manifest_path=args.split_manifest,
            )
        elif args.action == "cleanup-review":
            if not args.split_manifest:
                raise IntegrationError("Split cleanup requires --split-manifest")
            result = review_split_cleanup(
                adapter, args.seed_manifest, args.split_manifest
            )
        else:
            if not args.split_manifest or not args.reviewed_sha256 or not args.confirm:
                raise IntegrationError(
                    "Split cleanup execution requires --split-manifest, --reviewed-sha256 and --confirm"
                )
            result = execute_split_cleanup(
                adapter,
                args.seed_manifest,
                args.split_manifest,
                reviewed_sha256=args.reviewed_sha256,
                confirm=True,
            )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") not in ("partial", "unknown") else 1


if __name__ == "__main__":
    raise SystemExit(main())
