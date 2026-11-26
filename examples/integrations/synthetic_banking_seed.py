"""Review and seed isolated synthetic banking metadata in OpenMetadata 2.1.0."""

from __future__ import annotations

import argparse
import hashlib
from http.client import HTTPException
import json
import os
import tempfile
from pathlib import Path
from typing import Optional
from urllib import error, request
from urllib.parse import quote

import yaml

from examples.integrations.synthetic_banking_plan import (
    FIXTURES,
    LINKS,
    build_plan,
    inspect_target,
)
from open_data_products.integrations.config import (
    IntegrationError,
    load_integration_config,
)
from open_data_products.integrations.openmetadata import (
    OpenMetadataAdapter,
    PlatformError,
)

DOMAIN = "SDKIntegrationTest"
SERVICE = "sdk_synthetic_banking"
DATABASE = SERVICE + ".synthetic_bank"
SCHEMA = DATABASE + ".sdk_test"
LABEL = "Synthetic banking SDK test metadata; no physical data or production claims."


class UnknownOutcome(IntegrationError):
    """A write may have reached the server and must not be retried blindly."""


def _digest(obj):
    return hashlib.sha256(
        json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def operations(plan, *, table_domain=False):
    """Return deterministic creates and lineage instructions for the preview."""
    ops = [
        {
            "kind": "service",
            "path": "services/databaseServices",
            "fqn": SERVICE,
            "payload": {
                "name": SERVICE,
                "serviceType": "CustomDatabase",
                "description": LABEL,
            },
        },
        {
            "kind": "database",
            "path": "databases",
            "fqn": DATABASE,
            "payload": {
                "name": "synthetic_bank",
                "service": SERVICE,
                "description": LABEL,
            },
        },
        {
            "kind": "databaseSchema",
            "path": "databaseSchemas",
            "fqn": SCHEMA,
            "payload": {"name": "sdk_test", "database": DATABASE, "description": LABEL},
        },
    ]
    for item in plan["product_candidates"]:
        slug = item["product"]
        product_name = "sdk_synthetic_" + slug.replace("-", "_")
        source = yaml.safe_load(
            (FIXTURES / "products" / ("odps_product_" + slug + ".yaml")).read_text(
                encoding="utf-8"
            )
        )
        detail = source["product"]["details"]["en"]
        ops.append(
            {
                "kind": "dataProduct",
                "path": "dataProducts",
                "fqn": product_name,
                "payload": {
                    "name": product_name,
                    "displayName": "Synthetic test: " + detail["name"],
                    "description": LABEL + "\n\n" + detail.get("description", ""),
                    "domains": [DOMAIN],
                    "dataProductType": "DATASET",
                    "visibility": "PRIVATE",
                },
            }
        )
    for table in plan["tables"]:
        associated = [
            "sdk_synthetic_" + slug.replace("-", "_")
            for slug, assets in LINKS.items()
            if table["name"] in assets
        ]
        ops.append(
            {
                "kind": "table",
                "path": "tables",
                "fqn": SCHEMA + "." + table["name"],
                "payload": {
                    "name": table["name"],
                    "databaseSchema": SCHEMA,
                    "description": table["description"],
                    "columns": table["columns"],
                    "dataProducts": associated,
                    **({"domains": [DOMAIN]} if table_domain else {}),
                },
            }
        )
    for source, target in plan["proposed_lineage"]:
        ops.append(
            {
                "kind": "lineage",
                "source": SCHEMA + "." + source,
                "target": SCHEMA + "." + target,
            }
        )
    contract = {
        "apiVersion": "v3.1.0",
        "kind": "DataContract",
        "id": "sdk_synthetic_holdings_contract",
        "name": "sdk_synthetic_holdings_contract",
        "version": "0.1.0",
        "status": "draft",
        "description": {"purpose": LABEL},
        "schema": [
            {
                "name": "product_holdings",
                "properties": [
                    {
                        "name": "holding_id",
                        "logicalType": "string",
                        "required": True,
                        "unique": True,
                    },
                    {"name": "customer_id", "logicalType": "string", "required": True},
                    {"name": "account_id", "logicalType": "string", "required": True},
                ],
            }
        ],
    }
    ops.append(
        {
            "kind": "contract",
            "product": "sdk_synthetic_product_holdings",
            "source": yaml.safe_dump(contract, sort_keys=False),
        }
    )
    return ops


def review(plan, adapter):
    """Check target permissions, names and the complete candidate write set."""
    report = inspect_target(plan, adapter)
    if report["server_version"] != "2.1.0":
        raise IntegrationError("Only OpenMetadata 2.1.0 is supported by this seed")
    if (
        adapter.profile.read_only
        or report["conflicts"]
        or report["errors"]
        or any(v != "allow" for v in report["permissions"].values())
    ):
        raise IntegrationError(
            "Seed blocked: connection, permissions, conflicts or inspection errors require review"
        )
    adapter._json("domains/name/" + quote(DOMAIN, safe=""))
    for resource in ("table", "dataProduct"):
        permissions = adapter._json("permissions/" + resource).get("permissions", [])
        if not any(
            isinstance(entry, dict)
            and entry.get("operation") == "EditAll"
            and entry.get("access") == "allow"
            for entry in permissions
        ):
            raise IntegrationError("Seed requires EditAll permission for " + resource)
    ops = operations(plan)
    for op in ops:
        if op["kind"] != "dataProduct":
            continue
        try:
            adapter._json("dataProducts/name/" + quote(op["fqn"], safe=""))
        except PlatformError as exc:
            if exc.status == 404:
                continue
            raise
        raise IntegrationError("Synthetic product already exists: " + op["fqn"])
    payload = {
        "plan": plan,
        "operations": ops,
        "server_version": report["server_version"],
        "permissions": report["permissions"],
        "domain": DOMAIN,
        "warnings": [
            "Metadata only; no physical data source or connection test.",
            "Metadata-only service acceptance is unverified; failure stops the run.",
            "Schema-bearing ODCS is preserved separately; OpenMetadata does not validate its schema.",
            "Quality expectations are draft contract requirements; no quality test execution is implied.",
            "Lineage and product association behavior require read-back verification.",
        ],
    }
    return {"review_sha256": _digest(payload), **payload}


def _request_write(adapter, method, path, payload=None):
    """Issue a single bounded write and classify uncertain responses."""
    base = adapter.profile.base_url
    url = base + ("/v1/" if base.endswith("/api") else "/api/v1/") + path
    token = adapter.profile.token()
    data = json.dumps(payload).encode() if payload is not None else None
    req = request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with adapter._opener.open(
            req, timeout=adapter.profile.timeout_seconds
        ) as response:
            raw = response.read(5 * 1024 * 1024 + 1)
            if len(raw) > 5 * 1024 * 1024:
                raise UnknownOutcome(
                    "Response too large; inspect remote state before retry"
                )
            if not raw:
                return {}
            try:
                value = json.loads(raw.decode("utf-8"))
            except (UnicodeError, ValueError):
                raise UnknownOutcome(
                    "Unreadable write result; inspect remote state before retry"
                ) from None
            if not isinstance(value, dict):
                raise UnknownOutcome(
                    "Unexpected write result; inspect remote state before retry"
                )
            return value
    except error.HTTPError as exc:
        status = exc.code
        raw = exc.read(8192)
        exc.close()
        if status == 408 or status >= 500 or 300 <= status < 400:
            raise UnknownOutcome(
                "Write outcome unknown; inspect remote state before retry"
            ) from None
        try:
            parsed = json.loads(raw.decode("utf-8"))
            detail = str(parsed.get("message", "")) if isinstance(parsed, dict) else ""
        except (UnicodeError, ValueError):
            detail = ""
        detail = detail.replace(token, "[redacted]")[:500]
        raise PlatformError(
            "Write returned HTTP " + str(status) + (": " + detail if detail else ""),
            status,
        ) from None
    except (error.URLError, TimeoutError, OSError, HTTPException):
        raise UnknownOutcome(
            "Write outcome unknown; inspect remote state before retry"
        ) from None


def _save(path, manifest):
    """Persist progress without storing credentials or source-system records."""
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def execute(plan, adapter, *, reviewed_sha256, manifest_path):
    """Execute the reviewed sequence once, recording progress before each write."""
    adapter.require_write_access()
    current = review(plan, adapter)
    if reviewed_sha256 != current["review_sha256"]:
        raise IntegrationError("Seed review changed; preview again")
    path = Path(manifest_path)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    manifest = {
        "format": "synthetic-banking-seed-v1",
        "destination_sha256": plan["destination_sha256"],
        "review_sha256": reviewed_sha256,
        "status": "in_progress",
        "created": [],
        "pending": None,
        "quality_expectations": plan["proposed_quality_expectations"],
    }
    _save(path, manifest)
    created = {}
    for op in current["operations"]:
        manifest["pending"] = {k: v for k, v in op.items() if k != "source"}
        _save(path, manifest)
        try:
            if op["kind"] == "lineage":
                source, target = created[op["source"]], created[op["target"]]
                edge = {
                    "fromEntity": {"id": source, "type": "table"},
                    "toEntity": {"id": target, "type": "table"},
                    "description": LABEL,
                }
                _request_write(adapter, "PUT", "lineage", {"edge": edge})
                record = {"kind": "lineage", "source_id": source, "target_id": target}
            elif op["kind"] == "contract":
                product_id = created[op["product"]]
                draft = adapter.review_contract_import(
                    op["source"], product_id=product_id
                )
                if not draft.executable:
                    raise IntegrationError(
                        "Synthetic contract import is not executable"
                    )
                result = adapter.import_contract(
                    op["source"],
                    product_id=product_id,
                    reviewed_sha256=draft.review_sha256,
                )
                record = {
                    "kind": "contract",
                    "id": result.contract_id,
                    "product_id": product_id,
                    "status": result.status,
                }
                if result.status != "created":
                    manifest["created"].append(record)
                    _save(path, manifest)
                    raise UnknownOutcome(
                        "Contract exists but preservation or verification is unconfirmed; inspect before retry"
                    )
            else:
                response = _request_write(adapter, "POST", op["path"], op["payload"])
                entity_id = response.get("id")
                if not isinstance(entity_id, str) or not entity_id:
                    raise UnknownOutcome(
                        "Create response lacked an ID; inspect remote state before retry"
                    )
                record = {
                    "kind": op["kind"],
                    "id": entity_id,
                    "fqn": op["fqn"],
                    "path": op["path"],
                }
                created[op["fqn"]] = entity_id
            manifest["created"].append(record)
            manifest["pending"] = None
            _save(path, manifest)
        except (IntegrationError, OSError, ValueError, KeyError) as exc:
            manifest["status"] = (
                "unknown"
                if isinstance(exc, UnknownOutcome)
                or "unknown" in type(exc).__name__.lower()
                else "partial"
            )
            manifest["error"] = str(exc)
            _save(path, manifest)
            return manifest
    manifest["status"] = "created"
    _save(path, manifest)
    return manifest


def review_cleanup(adapter, manifest_path):
    """Review only confirmed entities recorded by this seed, without recursion."""
    from uuid import UUID

    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (
        manifest.get("format") != "synthetic-banking-seed-v1"
        or manifest.get("destination_sha256")
        != hashlib.sha256(adapter.profile.base_url.encode()).hexdigest()
    ):
        raise IntegrationError("Manifest does not belong to this destination")
    if manifest.get("status") not in ("created", "partial"):
        raise IntegrationError(
            "Uncertain or ongoing seed outcome must be investigated before cleanup"
        )
    items = manifest.get("created")
    if not isinstance(items, list):
        raise IntegrationError("Invalid seed manifest")
    allowed = {
        "service": "services/databaseServices",
        "database": "databases",
        "databaseSchema": "databaseSchemas",
        "table": "tables",
        "dataProduct": "dataProducts",
    }
    table_ids = {item.get("id") for item in items if item.get("kind") == "table"}
    product_ids = {
        item.get("id") for item in items if item.get("kind") == "dataProduct"
    }
    expected_edges = {
        (item.get("source_id"), item.get("target_id"))
        for item in items
        if item.get("kind") == "lineage"
    }
    targets = []
    for item in reversed(items):
        kind = item.get("kind")
        if kind == "lineage":
            source, target = item.get("source_id"), item.get("target_id")
            if source not in table_ids or target not in table_ids:
                raise IntegrationError("Lineage is not confined to created tables")
            targets.append(
                {
                    "kind": kind,
                    "path": "lineage/table/"
                    + str(UUID(source))
                    + "/table/"
                    + str(UUID(target)),
                }
            )
        elif kind == "contract":
            if item.get("product_id") not in product_ids:
                raise IntegrationError("Contract is not attached to a created product")
            contract_id = str(UUID(item["id"]))
            data = adapter._json("dataContracts/" + contract_id + "?fields=entity")
            if (
                data.get("id") != contract_id
                or not isinstance(data.get("entity"), dict)
                or data["entity"].get("id") != item["product_id"]
            ):
                raise IntegrationError("Contract identity or association changed")
            targets.append(
                {
                    "kind": kind,
                    "path": "dataContracts/"
                    + contract_id
                    + "?recursive=false&hardDelete=false",
                    "revision": data.get("version"),
                }
            )
        elif kind in allowed:
            identifier = str(UUID(item["id"]))
            fqn = item.get("fqn", "")
            if item.get("path") != allowed[kind] or not (
                fqn == SERVICE
                or fqn.startswith(SERVICE + ".")
                or (kind == "dataProduct" and fqn.startswith("sdk_synthetic_"))
            ):
                raise IntegrationError("Entity is outside the synthetic seed namespace")
            data = adapter._json(
                allowed[kind]
                + "/"
                + identifier
                + ("?fields=dataProducts" if kind == "table" else "")
            )
            if kind == "table":
                references = data.get("dataProducts") or []
                if not isinstance(references, list) or any(
                    not isinstance(ref, dict) or ref.get("id") not in product_ids
                    for ref in references
                ):
                    raise IntegrationError(
                        "Table has an unrecorded product relationship; inspect before cleanup"
                    )
                graph = adapter._json(
                    "lineage/table/" + identifier + "?upstreamDepth=1&downstreamDepth=1"
                )
                actual_edges = {
                    (edge.get("fromEntity"), edge.get("toEntity"))
                    for direction in ("upstreamEdges", "downstreamEdges")
                    for edge in graph.get(direction, [])
                    if isinstance(edge, dict)
                }
                relevant_edges = {edge for edge in expected_edges if identifier in edge}
                if actual_edges != relevant_edges:
                    raise IntegrationError(
                        "Table has unrecorded or missing lineage; clean dependent split metadata first"
                    )
            if (
                data.get("id") != identifier
                or data.get("fullyQualifiedName") != fqn
                or "Synthetic" not in str(data.get("description", ""))
            ):
                raise IntegrationError(
                    "Synthetic entity identity changed; manual inspection required"
                )
            targets.append(
                {
                    "kind": kind,
                    "path": allowed[kind]
                    + "/"
                    + identifier
                    + "?recursive=false&hardDelete=false",
                    "revision": data.get("version"),
                }
            )
        else:
            raise IntegrationError("Unknown manifest record; cleanup refused")
    result = {
        "destination_sha256": manifest["destination_sha256"],
        "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "targets": targets,
        "warning": "Soft deletion only; no recursive deletion. Recheck immediately before execution; no atomic concurrency protection.",
    }
    return {**result, "review_sha256": _digest(result)}


def execute_cleanup(adapter, manifest_path, *, reviewed_sha256, confirm):
    """Soft-delete only the individually reviewed seed entities and edges."""
    adapter.require_write_access()
    if confirm is not True:
        raise IntegrationError("Cleanup requires explicit confirmation")
    review_result = review_cleanup(adapter, manifest_path)
    if review_result["review_sha256"] != reviewed_sha256:
        raise IntegrationError("Cleanup review changed")
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["cleanup"] = {"status": "in_progress", "completed": [], "pending": None}
    _save(path, manifest)
    for target in review_result["targets"]:
        manifest["cleanup"]["pending"] = target
        _save(path, manifest)
        try:
            _request_write(adapter, "DELETE", target["path"])
        except (IntegrationError, OSError) as exc:
            manifest["cleanup"]["status"] = (
                "unknown" if isinstance(exc, UnknownOutcome) else "partial"
            )
            manifest["cleanup"]["error"] = str(exc)
            _save(path, manifest)
            return manifest["cleanup"]
        manifest["cleanup"]["completed"].append(target)
        manifest["cleanup"]["pending"] = None
        _save(path, manifest)
    manifest["cleanup"]["status"] = "completed"
    manifest["status"] = "cleaned"
    _save(path, manifest)
    return manifest["cleanup"]


def review_resume(plan, adapter, manifest_path, original_review_path):
    """Review only the remaining operations after the confirmed VARCHAR rejection."""
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    original = json.loads(Path(original_review_path).read_text(encoding="utf-8"))
    original_payload = {k: v for k, v in original.items() if k != "review_sha256"}
    if original.get("review_sha256") != _digest(original_payload) or manifest.get(
        "review_sha256"
    ) != original.get("review_sha256"):
        raise IntegrationError("Original review or manifest digest does not match")
    if (
        manifest.get("format") != "synthetic-banking-seed-v1"
        or manifest.get("status") != "partial"
        or not str(manifest.get("error", "")).startswith("HTTP 400:")
    ):
        raise IntegrationError(
            "Only the confirmed HTTP 400 partial state can be reviewed for resumption"
        )
    if (
        plan["destination_sha256"] != manifest.get("destination_sha256")
        or hashlib.sha256(adapter.profile.base_url.encode()).hexdigest()
        != plan["destination_sha256"]
    ):
        raise IntegrationError("Destination changed")
    old_ops = original["operations"]
    new_ops = operations(plan)
    normalized = json.loads(json.dumps(new_ops))
    for item in normalized:
        if item["kind"] == "table":
            for column in item["payload"]["columns"]:
                if column.get("dataType") == "VARCHAR":
                    if column.get("dataLength") != 255:
                        raise IntegrationError("Unexpected change to VARCHAR length")
                    column.pop("dataLength")
    if (
        normalized != old_ops
        or original["plan"]["product_candidates"] != plan["product_candidates"]
    ):
        raise IntegrationError("Seed changed beyond the reviewed VARCHAR correction")
    created = manifest.get("created", [])
    if (
        len(created) != 9
        or manifest.get("pending") != old_ops[9]
        or old_ops[9].get("kind") != "table"
    ):
        raise IntegrationError("Manifest does not match the expected partial seed")
    if (
        adapter.profile.read_only
        or adapter._json("system/version").get("version") != "2.1.0"
    ):
        raise IntegrationError("A writable OpenMetadata 2.1.0 connection is required")
    for resource, required in (
        ("table", ("Create", "EditAll")),
        ("dataProduct", ("EditAll",)),
        ("dataContract", ("Create",)),
    ):
        entries = adapter._json("permissions/" + resource).get("permissions", [])
        for operation in required:
            if not any(
                isinstance(entry, dict)
                and entry.get("operation") == operation
                and entry.get("access") == "allow"
                for entry in entries
            ):
                raise IntegrationError(
                    "Required " + resource + " permission is unavailable: " + operation
                )
    prior = []
    for record, expected in zip(created, old_ops[:9]):
        if any(record.get(key) != expected.get(key) for key in ("kind", "fqn", "path")):
            raise IntegrationError(
                "Created manifest entry does not match original review"
            )
        data = adapter._json(record["path"] + "/" + quote(record["id"], safe=""))
        if (
            data.get("id") != record["id"]
            or data.get("fullyQualifiedName") != record["fqn"]
            or "Synthetic" not in str(data.get("description", ""))
        ):
            raise IntegrationError(
                "Previously created entity identity or label changed"
            )
        prior.append(
            {"id": record["id"], "fqn": record["fqn"], "version": data.get("version")}
        )
    for item in new_ops[9:]:
        if item["kind"] != "table":
            continue
        try:
            adapter._json("tables/name/" + quote(item["fqn"], safe=""))
        except PlatformError as exc:
            if exc.status == 404:
                continue
            raise
        raise IntegrationError("A planned table already exists: " + item["fqn"])
    product_id = next(
        item["id"]
        for item in created
        if item.get("fqn") == "sdk_synthetic_product_holdings"
    )
    try:
        adapter.get_contract_for_product(product_id)
    except PlatformError as exc:
        if exc.status != 404:
            raise
    else:
        raise IntegrationError("Synthetic product already has a contract")
    payload = {
        "destination_sha256": plan["destination_sha256"],
        "manifest_sha256": hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
        "original_review_sha256": original["review_sha256"],
        "existing": prior,
        "remaining_operations": new_ops[9:],
        "change": "Set dataLength to 255 for VARCHAR columns; no other operation is changed.",
        "warnings": [
            "Existing metadata is reused by ID, never overwritten or deleted.",
            "No physical data or sample rows are created.",
            "Schema-bearing ODCS is preserved separately; native product-schema validation is not claimed.",
        ],
    }
    return {"review_sha256": _digest(payload), **payload}


def resume(plan, adapter, *, manifest_path, original_review_path, reviewed_sha256):
    """Resume the reviewed remaining seed operations exactly once."""
    adapter.require_write_access()
    reviewed = review_resume(plan, adapter, manifest_path, original_review_path)
    if reviewed["review_sha256"] != reviewed_sha256:
        raise IntegrationError("Resume review changed; review again")
    return _execute_resume(adapter, manifest_path, reviewed, reviewed_sha256)


def _execute_resume(adapter, manifest_path, reviewed, reviewed_sha256):
    """Apply a freshly reviewed remaining operation set once."""
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    created = {item["fqn"]: item["id"] for item in manifest["created"] if "fqn" in item}
    manifest["status"] = "in_progress"
    manifest["resume_review_sha256"] = reviewed_sha256
    manifest.pop("error", None)
    _save(path, manifest)
    for op in reviewed["remaining_operations"]:
        manifest["pending"] = {k: v for k, v in op.items() if k != "source"}
        _save(path, manifest)
        try:
            if op["kind"] == "lineage":
                source, target = created[op["source"]], created[op["target"]]
                edge = {
                    "fromEntity": {"id": source, "type": "table"},
                    "toEntity": {"id": target, "type": "table"},
                    "description": LABEL,
                }
                _request_write(adapter, "PUT", "lineage", {"edge": edge})
                record = {"kind": "lineage", "source_id": source, "target_id": target}
            elif op["kind"] == "contract":
                product_id = created[op["product"]]
                draft = adapter.review_contract_import(
                    op["source"], product_id=product_id
                )
                if not draft.executable:
                    raise IntegrationError(
                        "Synthetic contract import is not executable"
                    )
                result = adapter.import_contract(
                    op["source"],
                    product_id=product_id,
                    reviewed_sha256=draft.review_sha256,
                )
                record = {
                    "kind": "contract",
                    "id": result.contract_id,
                    "product_id": product_id,
                    "status": result.status,
                }
                if result.status != "created":
                    manifest["created"].append(record)
                    _save(path, manifest)
                    raise UnknownOutcome(
                        "Contract exists but preservation or verification is unconfirmed"
                    )
            else:
                response = _request_write(adapter, "POST", op["path"], op["payload"])
                entity_id = response.get("id")
                if not isinstance(entity_id, str) or not entity_id:
                    raise UnknownOutcome(
                        "Create response lacked an ID; inspect remote state before retry"
                    )
                record = {
                    "kind": op["kind"],
                    "id": entity_id,
                    "fqn": op["fqn"],
                    "path": op["path"],
                }
                created[op["fqn"]] = entity_id
            manifest["created"].append(record)
            manifest["pending"] = None
            _save(path, manifest)
        except (IntegrationError, OSError, ValueError, KeyError) as exc:
            manifest["status"] = (
                "unknown"
                if isinstance(exc, UnknownOutcome)
                or "unknown" in type(exc).__name__.lower()
                else "partial"
            )
            manifest["error"] = str(exc)
            _save(path, manifest)
            return manifest
    manifest["status"] = "created"
    _save(path, manifest)
    return manifest


def review_domain_resume(
    plan, adapter, manifest_path, original_review_path, previous_review_path
):
    """Review the domain-only correction after the confirmed domain-rule rejection."""
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    original = json.loads(Path(original_review_path).read_text(encoding="utf-8"))
    previous = json.loads(Path(previous_review_path).read_text(encoding="utf-8"))
    for item in (original, previous):
        if item.get("review_sha256") != _digest(
            {k: v for k, v in item.items() if k != "review_sha256"}
        ):
            raise IntegrationError("A prior review digest does not match its content")
    if (
        manifest.get("format") != "synthetic-banking-seed-v1"
        or manifest.get("status") != "partial"
        or "Data Product Domain Validation" not in str(manifest.get("error", ""))
    ):
        raise IntegrationError(
            "Only the confirmed domain-rule partial state can be resumed"
        )
    if (
        manifest.get("review_sha256") != original["review_sha256"]
        or manifest.get("resume_review_sha256") != previous["review_sha256"]
        or previous.get("original_review_sha256") != original["review_sha256"]
    ):
        raise IntegrationError("Prior reviews do not match the seed manifest")
    if (
        plan["destination_sha256"] != manifest.get("destination_sha256")
        or hashlib.sha256(adapter.profile.base_url.encode()).hexdigest()
        != plan["destination_sha256"]
    ):
        raise IntegrationError("Destination changed")
    created = manifest.get("created", [])
    previous_ops = previous.get("remaining_operations", [])
    if (
        len(created) != 9
        or not previous_ops
        or manifest.get("pending") != previous_ops[0]
        or previous_ops[0].get("kind") != "table"
    ):
        raise IntegrationError("Manifest does not match the expected partial seed")
    new_ops = operations(plan, table_domain=True)
    normalized = json.loads(json.dumps(new_ops[9:]))
    for op in normalized:
        if op["kind"] == "table":
            if op["payload"].get("domains") != [DOMAIN]:
                raise IntegrationError("Unexpected table domain")
            del op["payload"]["domains"]
    if (
        normalized != previous_ops
        or original["plan"]["product_candidates"] != plan["product_candidates"]
    ):
        raise IntegrationError(
            "Seed changed beyond the reviewed table-domain correction"
        )
    if (
        adapter.profile.read_only
        or adapter._json("system/version").get("version") != "2.1.0"
    ):
        raise IntegrationError("A writable OpenMetadata 2.1.0 connection is required")
    adapter._json("domains/name/" + quote(DOMAIN, safe=""))
    for resource, required in (
        ("table", ("Create", "EditAll", "EditDomains")),
        ("dataProduct", ("EditAll",)),
        ("dataContract", ("Create",)),
    ):
        entries = adapter._json("permissions/" + resource).get("permissions", [])
        for operation in required:
            if not any(
                isinstance(entry, dict)
                and entry.get("operation") == operation
                and entry.get("access") == "allow"
                for entry in entries
            ):
                raise IntegrationError(
                    "Required " + resource + " permission is unavailable: " + operation
                )
    prior = []
    old_ops = original["operations"]
    for record, expected, previously in zip(created, old_ops[:9], previous["existing"]):
        if any(
            record.get(key) != expected.get(key) for key in ("kind", "fqn", "path")
        ) or record["id"] != previously.get("id"):
            raise IntegrationError(
                "Previously created entity differs from prior review"
            )
        data = adapter._json(record["path"] + "/" + quote(record["id"], safe=""))
        if (
            data.get("id") != record["id"]
            or data.get("fullyQualifiedName") != record["fqn"]
            or "Synthetic" not in str(data.get("description", ""))
        ):
            raise IntegrationError(
                "Previously created entity identity or label changed"
            )
        prior.append(
            {"id": record["id"], "fqn": record["fqn"], "version": data.get("version")}
        )
    for op in new_ops[9:]:
        if op["kind"] != "table":
            continue
        try:
            adapter._json("tables/name/" + quote(op["fqn"], safe=""))
        except PlatformError as exc:
            if exc.status == 404:
                continue
            raise
        raise IntegrationError("A planned table already exists: " + op["fqn"])
    product_id = next(
        item["id"]
        for item in created
        if item.get("fqn") == "sdk_synthetic_product_holdings"
    )
    try:
        adapter.get_contract_for_product(product_id)
    except PlatformError as exc:
        if exc.status != 404:
            raise
    else:
        raise IntegrationError("Synthetic product already has a contract")
    payload = {
        "destination_sha256": plan["destination_sha256"],
        "manifest_sha256": hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
        "previous_review_sha256": previous["review_sha256"],
        "existing": prior,
        "remaining_operations": new_ops[9:],
        "change": "Set the table domain to SDKIntegrationTest; no other remaining operation changes.",
        "warnings": [
            "Existing synthetic metadata is reused by ID without overwrite or deletion.",
            "No physical data or sample rows are created.",
            "The preserved ODCS schema is not validated natively by OpenMetadata.",
        ],
    }
    return {"review_sha256": _digest(payload), **payload}


def resume_domain(
    plan,
    adapter,
    *,
    manifest_path,
    original_review_path,
    previous_review_path,
    reviewed_sha256,
):
    """Resume exactly the reviewed domain correction."""
    adapter.require_write_access()
    reviewed = review_domain_resume(
        plan, adapter, manifest_path, original_review_path, previous_review_path
    )
    if reviewed["review_sha256"] != reviewed_sha256:
        raise IntegrationError("Domain resume review changed; review again")
    return _execute_resume(adapter, manifest_path, reviewed, reviewed_sha256)


def load_referenced_env(profile, env_file):
    """Read only the configured token from a local dotenv file without shell evaluation."""
    if (
        profile.token_source != "env"
        or not env_file
        or os.environ.get(profile.token_env)
    ):
        return
    for line in Path(env_file).read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        if "=" not in entry or entry.split("=", 1)[0].strip() != profile.token_env:
            continue
        value = entry.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
            value = value[1:-1]
        if not value or "\n" in value or "\r" in value:
            raise IntegrationError("Configured credential is empty or invalid")
        os.environ[profile.token_env] = value
        return
    raise IntegrationError(
        "Configured credential is absent from the selected environment file"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "review",
            "execute",
            "resume-review",
            "resume",
            "domain-resume-review",
            "domain-resume",
            "cleanup-review",
            "cleanup-execute",
        ),
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--connection", default="openmetadata")
    parser.add_argument(
        "--env-file", help="Local dotenv file containing the configured credential"
    )
    parser.add_argument("--manifest")
    parser.add_argument(
        "--original-review", help="Original reviewed seed JSON for a supported resume"
    )
    parser.add_argument("--previous-review", help="Prior VARCHAR resume review JSON")
    parser.add_argument("--reviewed-sha256")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    profile = load_integration_config(args.config).select(args.connection)
    load_referenced_env(profile, args.env_file)
    with OpenMetadataAdapter(profile) as adapter:
        if args.action == "review":
            result = review(build_plan(args.config, args.connection), adapter)
        elif args.action == "execute":
            if not args.confirm or not args.reviewed_sha256 or not args.manifest:
                raise IntegrationError(
                    "Execution requires --confirm, --reviewed-sha256 and --manifest"
                )
            result = execute(
                build_plan(args.config, args.connection),
                adapter,
                reviewed_sha256=args.reviewed_sha256,
                manifest_path=args.manifest,
            )
        elif args.action in ("resume-review", "resume"):
            if not args.manifest or not args.original_review:
                raise IntegrationError(
                    "Resume requires --manifest and --original-review"
                )
            plan = build_plan(args.config, args.connection)
            if args.action == "resume-review":
                result = review_resume(
                    plan, adapter, args.manifest, args.original_review
                )
            else:
                if not args.confirm or not args.reviewed_sha256:
                    raise IntegrationError(
                        "Resume requires --confirm and --reviewed-sha256"
                    )
                result = resume(
                    plan,
                    adapter,
                    manifest_path=args.manifest,
                    original_review_path=args.original_review,
                    reviewed_sha256=args.reviewed_sha256,
                )
        elif args.action in ("domain-resume-review", "domain-resume"):
            if (
                not args.manifest
                or not args.original_review
                or not args.previous_review
            ):
                raise IntegrationError(
                    "Domain resume requires manifest and both prior reviews"
                )
            plan = build_plan(args.config, args.connection)
            if args.action == "domain-resume-review":
                result = review_domain_resume(
                    plan,
                    adapter,
                    args.manifest,
                    args.original_review,
                    args.previous_review,
                )
            else:
                if not args.confirm or not args.reviewed_sha256:
                    raise IntegrationError(
                        "Domain resume requires --confirm and --reviewed-sha256"
                    )
                result = resume_domain(
                    plan,
                    adapter,
                    manifest_path=args.manifest,
                    original_review_path=args.original_review,
                    previous_review_path=args.previous_review,
                    reviewed_sha256=args.reviewed_sha256,
                )
        elif args.action == "cleanup-review":
            if not args.manifest:
                raise IntegrationError("Cleanup requires --manifest")
            result = review_cleanup(adapter, args.manifest)
        else:
            if not args.confirm or not args.reviewed_sha256 or not args.manifest:
                raise IntegrationError(
                    "Cleanup execution requires --confirm, --reviewed-sha256 and --manifest"
                )
            result = execute_cleanup(
                adapter,
                args.manifest,
                reviewed_sha256=args.reviewed_sha256,
                confirm=True,
            )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") not in ("unknown", "partial") else 1


if __name__ == "__main__":
    raise SystemExit(main())
