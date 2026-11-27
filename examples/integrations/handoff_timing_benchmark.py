"""Measure a synthetic business-to-marketplace-to-Jira workflow end to end."""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import quote
from urllib.request import Request
from uuid import uuid4

import yaml

from open_data_products._guided_handoff import (
    _brief_search_concepts,
    _catalog_context,
    _discovery_adapter,
    _load_env_file,
    _merge_discovery,
    _resolve_discovery_profile,
)
from open_data_products._openspec_validation import validate_openspec_handover
from open_data_products.agent import validate_document
from open_data_products.contracts.datacontract_cli_adapter import validate_contract
from open_data_products.generation import resolve_generation_settings
from open_data_products.integrations.jira import (
    JiraCloudAdapter,
    JiraIssueRequest,
    load_jira_connection,
)

PHASES = (
    "source_staging",
    "service_preflight",
    "mcp_startup",
    "business_review",
    "odps_generation",
    "synthetic_metadata_label",
    "marketplace_review",
    "marketplace_create",
    "marketplace_verification",
    "discovery_planning",
    "metadata_discovery",
    "handover_review",
    "handover_generation",
    "structural_validation",
    "contract_review",
    "contract_import",
    "contract_verification",
    "jira_review",
    "jira_delivery",
    "jira_verification",
)


def _write_json(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


@contextmanager
def _phase(record, name, clock=time.perf_counter):
    start = clock()
    try:
        yield
    finally:
        record["phase_seconds"][name] = round(clock() - start, 6)


def stage_synthetic_source(source, destination, unique_id):
    """Copy a fictional Markdown brief with a unique test-only identity."""
    if source.is_symlink() or not source.is_file() or source.suffix.lower() != ".md":
        raise ValueError("Benchmark input must be a regular Markdown file")
    raw = source.read_bytes()
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError("Benchmark input exceeds 20 MiB")
    text = raw.decode("utf-8")
    if not re.search(r"\b(?:fictional|synthetic)\b", text, re.I):
        raise ValueError("Benchmark inputs must be explicitly fictional or synthetic")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not match:
        raise ValueError("Synthetic benchmark briefs require YAML front matter")
    front = match.group(1)
    name = re.search(r"(?m)^product_name:[ \t]*(.+?)[ \t]*$", front)
    if not name or len(re.findall(r"(?m)^product_id:", front)) != 1:
        raise ValueError("Brief needs exactly one product_id and product_name")
    original_name = name.group(1).strip().strip("\"'")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,100}", original_name):
        raise ValueError(
            "Synthetic product name must use simple letters, numbers, spaces or hyphens"
        )
    label = "Synthetic benchmark " + original_name + " " + unique_id[-8:]
    front = re.sub(r"(?m)^product_id:.*$", "product_id: " + unique_id, front, count=1)
    front = re.sub(r"(?m)^product_name:.*$", "product_name: " + label, front, count=1)
    content = "---\n" + front + "\n---\n" + text[match.end() :]
    destination.write_text(content, encoding="utf-8")
    return {
        "original_sha256": hashlib.sha256(raw).hexdigest(),
        "staged_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "product_id": unique_id,
        "product_name": label,
    }


def label_synthetic_odps(product_path):
    """Mark the newly generated metadata as fictional without changing its meaning."""
    document = yaml.safe_load(product_path.read_text(encoding="utf-8"))
    try:
        details = document["product"]["details"]["en"]
        description = details["description"]
    except (KeyError, TypeError):
        raise ValueError(
            "Generated ODPS needs a description for the synthetic test label"
        ) from None
    if not isinstance(description, str) or not description.strip():
        raise ValueError(
            "Generated ODPS needs a description for the synthetic test label"
        )
    details["description"] = (
        "Fictional synthetic performance benchmark metadata. " + description
    )
    product_path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


class MCPClient:
    """Use the actual stdio MCP transport for the benchmark."""

    def __init__(self, stderr_path):
        self.stderr = stderr_path.open("x", encoding="utf-8")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "open_data_products.mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
            text=True,
            bufsize=1,
        )
        self.sequence = 0
        self.request("initialize", {})

    def request(self, method, params):
        self.sequence += 1
        self.process.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": self.sequence,
                    "method": method,
                    "params": params,
                }
            )
            + "\n"
        )
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        try:
            message = json.loads(line)
        except ValueError:
            raise RuntimeError(
                "MCP server did not return a JSON-RPC response"
            ) from None
        if message.get("id") != self.sequence or "error" in message:
            raise RuntimeError("MCP server returned an unexpected response")
        return message["result"]

    def call(self, name, arguments):
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        value = json.loads(result["content"][0]["text"])
        if result.get("isError"):
            raise RuntimeError(
                name + " failed: " + str(value.get("message", "unknown error"))
            )
        return value

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.process.stdin:
            self.process.stdin.close()
        if self.process.stdout:
            self.process.stdout.close()
        self.stderr.close()


class LiveServices:
    """Use configured SDK integrations and read back live results."""

    def __init__(self, config, discovery, jira, domain):
        self.config, self.discovery, self.jira_name, self.domain = (
            config,
            discovery,
            jira,
            domain,
        )
        self.metadata = self.jira = self.mcp = None

    def preflight(self):
        _load_env_file(".env" if Path(".env").is_file() else None)
        profile = _resolve_discovery_profile(self.config, self.discovery)
        if profile.platform != "openmetadata" or profile.read_only:
            raise ValueError("A writable OpenMetadata connection is required")
        self.metadata = _discovery_adapter(profile)
        if self.metadata._json("system/version").get("version") != "2.1.0":
            raise ValueError("The synthetic benchmark targets OpenMetadata 2.1.0")
        permissions = self.metadata._json("permissions/dataProduct").get(
            "permissions", []
        )
        if not any(
            p.get("operation") == "Create" and p.get("access") == "allow"
            for p in permissions
            if isinstance(p, dict)
        ):
            raise ValueError(
                "OpenMetadata data product create permission is unavailable"
            )
        self.metadata._json("domains/name/" + quote(self.domain, safe=""))
        self.jira = JiraCloudAdapter(load_jira_connection(self.config, self.jira_name))
        if not os.environ.get("JIRA_PROJECT") or not os.environ.get(
            "JIRA_ISSUE_TYPE_ID"
        ):
            raise ValueError("JIRA_PROJECT and JIRA_ISSUE_TYPE_ID must be configured")
        self.jira.review_issue(
            JiraIssueRequest(
                os.environ["JIRA_PROJECT"],
                os.environ["JIRA_ISSUE_TYPE_ID"],
                "Synthetic benchmark preflight",
                "Preflight only; no issue is created.",
            )
        )
        if not shutil.which("openspec"):
            raise ValueError("OpenSpec CLI is required for the benchmark")
        from open_data_products.contracts.datacontract_cli_adapter import (
            detect_datacontract_cli,
        )

        available = detect_datacontract_cli()
        if not available.python_package and not available.cli_executable:
            raise ValueError("datacontract-cli is required for the benchmark")
        settings = resolve_generation_settings(
            config_path=(
                "generation.config.yaml"
                if Path("generation.config.yaml").is_file()
                else None
            )
        )
        if settings.api_key_env and not os.environ.get(settings.api_key_env):
            raise ValueError("Configured provider credential is unavailable")
        return {
            "provider": settings.provider,
            "model": settings.model,
            "platform": profile.platform,
            "domain": self.domain,
            "human_review": "Preauthorized synthetic benchmark; exact digests and results are recorded. No human review wait is included.",
        }

    def start_mcp(self, case_dir):
        self.mcp = MCPClient(case_dir / "mcp-stderr.log")

    def call(self, name, args):
        return self.mcp.call(name, args)

    def review_marketplace(self, product_path, identity):
        text = product_path.read_text(encoding="utf-8")
        review = self.metadata.review_create(text, domain=self.domain)
        if not review.executable:
            raise ValueError(
                "Generated ODPS is not executable for OpenMetadata creation"
            )
        if review.product_id != identity["product_id"]:
            raise ValueError(
                "Generated ODPS product ID does not match the synthetic source"
            )
        if review.product_name != identity["product_name"]:
            raise ValueError(
                "Generated ODPS product name does not match the synthetic source"
            )
        matches = self.metadata.find_create_candidates(text, domain=self.domain)
        if not matches.get("complete"):
            raise ValueError("OpenMetadata duplicate check did not complete")
        if matches.get("candidates"):
            raise ValueError("A potential matching OpenMetadata product already exists")
        return review.to_dict()

    def create_marketplace(self, product_path, review):
        created = self.metadata.create_product(
            product_path.read_text(encoding="utf-8"),
            domain=self.domain,
            reviewed_sha256=review["review_sha256"],
        )
        return created.to_dict()

    def verify_marketplace(self, product_id, product_name):
        current = self.metadata.get_product(product_id, include_domains=True).data
        if not isinstance(current, dict) or current.get("name") != product_name:
            raise ValueError(
                "Created OpenMetadata product did not match its synthetic ID"
            )
        cursor, seen = None, set()
        for _ in range(20):
            page = self.metadata.list_products(limit=1000, after=cursor)
            if any(
                isinstance(item, dict) and item.get("id") == product_id
                for item in page.products
            ):
                break
            cursor = page.after
            if cursor is None or cursor in seen:
                raise ValueError("Created product is absent from the product listing")
            seen.add(cursor)
        else:
            raise ValueError("Product listing exceeded the page limit")
        deadline = time.monotonic() + 30
        while True:
            search = self.metadata.search_products(product_name, limit=100)
            if any(item.get("id") == product_id for item in search.products):
                break
            if time.monotonic() >= deadline:
                raise ValueError("Product did not become searchable within 30 seconds")
            time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
        return {
            "product_id": product_id,
            "listed": True,
            "searchable": True,
            "visibility": current.get("visibility"),
            "limitation": "Listing and search are verified for the configured account; marketplace UI visibility and lifecycle publication are not verified.",
        }

    def discovery_concepts(self, business_path):
        settings = resolve_generation_settings(
            config_path=(
                "generation.config.yaml"
                if Path("generation.config.yaml").is_file()
                else None
            )
        )
        return _brief_search_concepts(
            business_path.read_text(encoding="utf-8"), settings
        )

    def discover(self, concepts, product_id):
        snapshots = []
        for item in concepts:
            query = '"' + item["phrase"] + '"'
            snapshots.append(
                (
                    query,
                    _catalog_context(self.config, self.discovery, None, query, limit=4),
                )
            )
        snapshots.append(
            (
                "selected product: " + product_id,
                _catalog_context(
                    self.config, self.discovery, product_id, None, limit=4
                ),
            )
        )
        return _merge_discovery(concepts, snapshots)

    def validate(self, change):
        supporting = change / "supporting"
        odps = validate_document(supporting / "product-enriched.odps.yaml")
        odcs = validate_contract(str(supporting / "odcs-draft.yaml"))
        openspec = validate_openspec_handover(change)
        if not odps.valid or not odcs.passed or openspec.get("status") != "passed":
            raise ValueError("Structural validation failed or was not performed")
        return {
            "odps": "passed",
            "odcs": "passed",
            "odcs_tool_version": odcs.tool_version,
            "openspec": openspec,
            "business_approval": "not assessed",
        }

    def review_contract(self, product_id, contract_path):
        source = contract_path.read_text(encoding="utf-8")
        review = self.metadata.review_contract_import(source, product_id=product_id)
        if not review.executable:
            raise ValueError(
                "Generated ODCS draft cannot be imported; inspect the contract review"
            )
        return review.to_dict()

    def import_contract(self, product_id, contract_path, review):
        source = contract_path.read_text(encoding="utf-8")
        result = self.metadata.import_contract(
            source, product_id=product_id, reviewed_sha256=review["review_sha256"]
        )
        return result.to_dict()

    def verify_contract(self, product_id, contract_path):
        expected = hashlib.sha256(contract_path.read_bytes()).hexdigest()
        context = self.metadata.discover_context(product_id=product_id, limit=2)
        evidence = context.get("contracts", [])
        native = [
            item
            for item in evidence
            if item.get("origin") == "OpenMetadata product contract"
        ]
        preserved = [
            item
            for item in evidence
            if item.get("origin") == "SDK-preserved ODCS source"
        ]
        if (
            len(native) != 1
            or len(preserved) != 1
            or preserved[0].get("sha256") != expected
            or native[0].get("provenance", {}).get("product_id") != product_id
            or preserved[0].get("provenance", {}).get("product_id") != product_id
            or not native[0].get("provenance", {}).get("contract_id")
            or native[0].get("provenance", {}).get("contract_id")
            != preserved[0].get("provenance", {}).get("contract_id")
        ):
            raise ValueError(
                "Contract association or preserved ODCS source could not be verified"
            )
        return {
            "contract_id": native[0].get("provenance", {}).get("contract_id"),
            "source_sha256": expected,
            "preserved_source_integrity": "matched",
            "platform_schema_validation": "not established; ODCS schema is preserved separately",
            "discovery_errors": context.get("errors", []),
        }

    def verify_jira(self, issue_key, review):
        issue = self.jira._request(
            "GET",
            "issue/"
            + quote(issue_key, safe="")
            + "?fields=summary,description,attachment",
        )
        attachments = issue.get("fields", {}).get("attachment", [])
        expected = {x["filename"]: x for x in review["attachments"]}
        if {x.get("filename") for x in attachments} != set(expected):
            raise ValueError("Jira attachment names do not match the reviewed delivery")
        credentials = (
            os.environ[self.jira.connection.email_env]
            + ":"
            + os.environ[self.jira.connection.token_env]
        ).encode()
        authorization = "Basic " + base64.b64encode(credentials).decode("ascii")
        for item in attachments:
            url = (
                self.jira.connection.base_url.rstrip("/")
                + "/rest/api/3/attachment/content/"
                + quote(str(item["id"]), safe="")
                + "?redirect=false"
            )
            req = Request(
                url, headers={"Authorization": authorization, "Accept": "*/*"}
            )
            with self.jira._opener.open(
                req, timeout=self.jira.connection.timeout_seconds
            ) as response:
                body = response.read(10 * 1024 * 1024 + 1)
            reference = expected[item["filename"]]
            if (
                len(body) != reference["size"]
                or hashlib.sha256(body).hexdigest() != reference["sha256"]
            ):
                raise ValueError(
                    "Jira attachment content differs from the reviewed delivery"
                )
        return {
            "issue_key": issue_key,
            "attachments_verified": sorted(expected),
            "sha256_verified": True,
        }

    def close(self):
        if self.mcp:
            self.mcp.close()
        if self.metadata:
            self.metadata.close()


def _safe_error(exc):
    value = str(exc)
    for name, secret in os.environ.items():
        if (
            re.search(r"(?:TOKEN|SECRET|PASSWORD|API_KEY)", name, re.I)
            and len(secret) >= 8
        ):
            value = value.replace(secret, "<redacted>")
    return {"type": type(exc).__name__, "message": value[:1000]}


def run_case(source, case_dir, unique_id, service, clock=time.perf_counter):
    """Measure one full case, recording partial results without retrying writes."""
    started = clock()
    record = {
        "source": source.name,
        "case_id": unique_id,
        "status": "running",
        "phase_seconds": {},
        "human_wait_seconds": 0.0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "write_outcome": None,
    }
    case_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    state_path = case_dir / "result.json"
    _write_json(state_path, record)
    active = "initialization"
    try:
        active = "source_staging"
        with _phase(record, active, clock):
            staged_input = case_dir / "input.md"
            identity = stage_synthetic_source(source, staged_input, unique_id)
            record["source_identity"] = identity
        active = "service_preflight"
        with _phase(record, active, clock):
            record["environment"] = service.preflight()
        active = "mcp_startup"
        with _phase(record, active, clock):
            service.start_mcp(case_dir)
        business_args = {
            "business_document": str(staged_input),
            "output": str(case_dir / "business"),
        }
        active = "business_review"
        with _phase(record, active, clock):
            business_review = service.call("preview_business_handover", business_args)
            _write_json(case_dir / "business-review.json", business_review)
        active = "odps_generation"
        with _phase(record, active, clock):
            business = service.call(
                "create_business_odps_draft",
                {
                    **business_args,
                    "reviewed_sha256": business_review["reviewed_sha256"],
                },
            )
        business_path = case_dir / "business" / business["business_document"]
        product_path = case_dir / "business" / business["odps_draft"]
        active = "synthetic_metadata_label"
        with _phase(record, active, clock):
            label_synthetic_odps(product_path)
        active = "marketplace_review"
        with _phase(record, active, clock):
            product_review = service.review_marketplace(product_path, identity)
            _write_json(case_dir / "marketplace-review.json", product_review)
        record["write_outcome"] = "marketplace_create_pending"
        _write_json(state_path, record)
        active = "marketplace_create"
        with _phase(record, active, clock):
            created = service.create_marketplace(product_path, product_review)
            record["marketplace_product_id"] = created["product_id"]
            record["marketplace_create_result"] = created
            if created.get("status") != "created":
                raise RuntimeError(
                    "OpenMetadata creation was not verified; inspect before retrying"
                )
            record["write_outcome"] = "marketplace_created"
            _write_json(state_path, record)
        active = "marketplace_verification"
        with _phase(record, active, clock):
            record["marketplace_verification"] = service.verify_marketplace(
                created["product_id"], identity["product_id"]
            )
        active = "discovery_planning"
        with _phase(record, active, clock):
            concepts = service.discovery_concepts(business_path)
            if not concepts:
                raise ValueError("No catalog search concepts were returned")
        active = "metadata_discovery"
        with _phase(record, active, clock):
            context = service.discover(concepts, created["product_id"])
            context_path = case_dir / "catalog-context.json"
            _write_json(context_path, context)
            record["discovery"] = {
                "asset_count": len(context.get("assets", [])),
                "lineage_count": len(context.get("lineage", [])),
                "contract_count": len(context.get("contracts", [])),
                "error_count": len(context.get("errors", [])),
                "incomplete": bool(context.get("incomplete", True)),
            }
        handover_args = {
            "business_document": str(business_path),
            "product": str(product_path),
            "context_file": str(context_path),
            "output": str(case_dir / "handover"),
            "change_name": "implement-" + unique_id.replace("_", "-"),
        }
        active = "handover_review"
        with _phase(record, active, clock):
            handover_review = service.call(
                "preview_implementation_handover", handover_args
            )
            _write_json(case_dir / "handover-review.json", handover_review)
        active = "handover_generation"
        with _phase(record, active, clock):
            handover = service.call(
                "create_implementation_handover",
                {
                    **handover_args,
                    "reviewed_sha256": handover_review["reviewed_sha256"],
                },
            )
        change = case_dir / "handover" / handover["change"]
        active = "structural_validation"
        with _phase(record, active, clock):
            record["validation"] = service.validate(change)
        contract_path = change / "supporting" / "odcs-draft.yaml"
        active = "contract_review"
        with _phase(record, active, clock):
            contract_review = service.review_contract(
                created["product_id"], contract_path
            )
            _write_json(case_dir / "contract-review.json", contract_review)
        record["write_outcome"] = "contract_import_pending"
        _write_json(state_path, record)
        active = "contract_import"
        with _phase(record, active, clock):
            imported = service.import_contract(
                created["product_id"], contract_path, contract_review
            )
            record["contract_import_result"] = imported
            if imported.get("status") != "created":
                raise RuntimeError(
                    "Contract import was not verified; inspect before retrying"
                )
            record["write_outcome"] = "contract_imported"
            _write_json(state_path, record)
        active = "contract_verification"
        with _phase(record, active, clock):
            record["contract_verification"] = service.verify_contract(
                created["product_id"], contract_path
            )
        issue_args = {
            "connections": service.config,
            "connection": service.jira_name,
            "change": str(change),
            "project": os.environ["JIRA_PROJECT"],
            "issue_type_id": os.environ["JIRA_ISSUE_TYPE_ID"],
            "package_attachment": str(case_dir / "handover" / handover["package"]),
            "attachments": [str(business_path)],
        }
        active = "jira_review"
        with _phase(record, active, clock):
            jira_review = service.call("review_jira_handover", issue_args)
            _write_json(case_dir / "jira-review.json", jira_review)
            if jira_review.get("possible_duplicate_keys"):
                raise ValueError(
                    "Possible duplicate Jira issue found; inspect before creating"
                )
        active = "jira_delivery"
        record["write_outcome"] = "jira_create_pending"
        _write_json(state_path, record)
        with _phase(record, active, clock):
            jira = service.call(
                "deliver_jira_handover",
                {
                    **issue_args,
                    "reviewed_sha256": jira_review["reviewed_sha256"],
                    "journal_file": str(case_dir / "jira-journal.json"),
                },
            )
            record["jira_issue_key"] = jira["key"]
            record["jira_issue_url"] = jira["url"]
            record["write_outcome"] = "jira_created"
            _write_json(state_path, record)
        active = "jira_verification"
        with _phase(record, active, clock):
            record["jira_verification"] = service.verify_jira(jira["key"], jira_review)
        record["status"] = "success"
    except Exception as exc:
        journal = case_dir / "jira-journal.json"
        if record["write_outcome"] == "jira_create_pending" and journal.is_file():
            try:
                partial = json.loads(journal.read_text(encoding="utf-8"))
                if isinstance(partial.get("result"), dict):
                    record["jira_issue_key"] = partial["result"].get("key")
                    record["jira_issue_url"] = partial["result"].get("url")
                    record["jira_journal_status"] = partial.get("status")
            except (OSError, ValueError):
                pass
        record["status"] = (
            "unknown_write_outcome"
            if record["write_outcome"]
            in (
                "marketplace_create_pending",
                "contract_import_pending",
                "jira_create_pending",
            )
            else "failed"
        )
        record["failed_phase"] = active
        record["error"] = _safe_error(exc)
        if record["status"] == "unknown_write_outcome":
            record["next_step"] = (
                "Inspect the target and local journal before retrying; no create is automatically retried."
            )
        elif record.get("write_outcome") in (
            "marketplace_created",
            "contract_imported",
        ):
            record["next_step"] = (
                "The product already exists; inspect its contract and the recorded result before retrying."
            )
    finally:
        try:
            service.close()
        except Exception as exc:
            record["cleanup_warning"] = _safe_error(exc)
        record["total_seconds"] = round(clock() - started, 6)
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        _write_json(state_path, record)
    return record


def summarize(records, planned):
    successful = [r for r in records if r.get("status") == "success"]
    durations = [r["total_seconds"] for r in successful]
    average = sum(durations) / len(durations) if durations else None
    complete = len(records) == planned and len(successful) == planned
    phase_averages = {
        phase: round(
            sum(r["phase_seconds"][phase] for r in successful) / len(successful), 3
        )
        for phase in PHASES
        if successful and all(phase in r.get("phase_seconds", {}) for r in successful)
    }
    return {
        "planned": planned,
        "completed_successfully": len(successful),
        "failed_or_unknown": len(records) - len(successful),
        "not_run": planned - len(records),
        "average_seconds_successful": (
            round(average, 3) if average is not None else None
        ),
        "all_cases_completed": complete,
        "average_under_60_seconds": (average < 60) if complete else None,
        "average_phase_seconds_successful": phase_averages,
        "timing_scope": "Elapsed wall-clock from source staging through verified Jira attachment readback, including discovery, validation, retries of read-only search and cleanup of local process; no human review wait.",
        "marketplace_scope": "Native OpenMetadata product listing and search were checked as the configured account; marketplace UI publication and access by other users were not verified.",
    }


def write_report(output, records, planned):
    summary = summarize(records, planned)
    _write_json(
        output / "benchmark-results.json", {"summary": summary, "cases": records}
    )
    lines = [
        "# Synthetic handover timing benchmark",
        "",
        "This measures wall-clock elapsed time, including live LLM calls, OpenMetadata listing/search, structural validation and verified Jira attachment readback. Reviews were programmatically digest-bound and preauthorized for synthetic test content; no human wait is included.",
        "",
        "| Case | Status | Total seconds | OpenMetadata product | Jira issue |",
        "|---|---|---:|---|---|",
    ]
    for item in records:
        lines.append(
            "| {} | {} | {:.3f} | {} | {} |".format(
                item["source"],
                item["status"],
                item["total_seconds"],
                item.get("marketplace_product_id", "—"),
                item.get("jira_issue_key", "—"),
            )
        )
    lines += [
        "",
        "Successful cases: {} of {}".format(summary["completed_successfully"], planned),
        "Average of completed successful cases: {} seconds".format(
            summary["average_seconds_successful"]
            if summary["average_seconds_successful"] is not None
            else "not available"
        ),
        "All cases under evaluation completed: {}".format(
            summary["all_cases_completed"]
        ),
        "Average below 60 seconds: {}".format(
            summary["average_under_60_seconds"]
            if summary["average_under_60_seconds"] is not None
            else "not assessable because cases failed or were not run"
        ),
        "",
        "OpenMetadata listing and search were checked for the configured account; marketplace UI publication and access by other users were not verified.",
        "The generated ODCS draft is imported and associated after product creation; its preserved schema is not claimed to be validated by OpenMetadata.",
        "",
    ]
    if summary["average_phase_seconds_successful"]:
        lines += [
            "## Average phase durations for successful cases",
            "",
            "| Phase | Average seconds |",
            "|---|---:|",
        ]
        for name, seconds in summary["average_phase_seconds_successful"].items():
            lines.append("| {} | {:.3f} |".format(name, seconds))
        lines.append("")
    lines += [
        "## Discovery and validation",
        "",
        "| Case | Catalog assets | Discovery findings | Structural validation |",
        "|---|---:|---:|---|",
    ]
    for item in records:
        evidence = item.get("discovery", {})
        validation = item.get("validation", {})
        status = (
            "passed"
            if validation.get("odps") == "passed"
            and validation.get("odcs") == "passed"
            and validation.get("openspec", {}).get("status") == "passed"
            else "not passed or not performed"
        )
        lines.append(
            "| {} | {} | {} | {} |".format(
                item["source"],
                evidence.get("asset_count", "—"),
                evidence.get("error_count", "—"),
                status,
            )
        )
    lines += [
        "",
        "Discovery findings are retained in each catalog snapshot. Incomplete evidence and structural validation do not establish business approval or implementation readiness.",
        "",
    ]
    for item in records:
        lines += ["## " + item["source"], "", "| Phase | Seconds |", "|---|---:|"]
        for name, seconds in item["phase_seconds"].items():
            lines.append("| {} | {:.3f} |".format(name, seconds))
        if item.get("error"):
            lines += [
                "",
                "Failure at {}: {}".format(
                    item.get("failed_phase"), item["error"]["message"]
                ),
            ]
        lines.append("")
    (output / "benchmark-results.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Measure synthetic business documents through OpenMetadata and Jira."
    )
    parser.add_argument(
        "--input", required=True, help="Fictional Markdown brief or folder of briefs"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="New local output directory for results and journals",
    )
    parser.add_argument("--connections", default="connections.yaml")
    parser.add_argument("--discovery", default="openmetadata")
    parser.add_argument("--jira", default="jira")
    parser.add_argument(
        "--domain", required=True, help="Existing OpenMetadata test domain FQN"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly run live provider and reviewed platform writes",
    )
    args = parser.parse_args(argv)
    source = Path(args.input).expanduser()
    if source.is_symlink() or not source.exists():
        parser.error("Input must be a regular file or directory")
    files = (
        sorted(
            p
            for p in source.iterdir()
            if p.is_file() and not p.is_symlink() and p.suffix.lower() == ".md"
        )
        if source.is_dir()
        else [source]
    )
    if not files:
        parser.error("No Markdown briefs found")
    output = Path(args.output).expanduser().absolute()
    if output.exists() or not output.parent.is_dir():
        parser.error("Output must be a new directory whose parent exists")
    plan = {
        "documents": [f.name for f in files],
        "count": len(files),
        "domain": args.domain,
        "discovery_connection": args.discovery,
        "jira_connection": args.jira,
        "writes": "One new synthetic OpenMetadata product, an associated ODCS draft contract, and one Jira issue per successful case; no deletion.",
        "measurement": "Sequential end-to-end wall time including SDK review checks, discovery, validation and Jira readback; human approval wait is not included.",
    }
    print(json.dumps(plan, indent=2), flush=True)
    if not args.execute:
        print(
            "Preview only; add --execute to run the live synthetic benchmark.",
            flush=True,
        )
        return 0
    output.mkdir(mode=0o700)
    _write_json(output / "plan.json", plan)
    run_id = uuid4().hex[:12]
    records = []
    for index, source_file in enumerate(files, 1):
        identifier = "sdk-perf-" + run_id + "-" + str(index)
        print(
            "Running {} of {}: {}".format(index, len(files), source_file.name),
            flush=True,
        )
        service = LiveServices(
            str(Path(args.connections).expanduser().absolute()),
            args.discovery,
            args.jira,
            args.domain,
        )
        record = run_case(source_file, output / identifier, identifier, service)
        records.append(record)
        summary = write_report(output, records, len(files))
        print(
            json.dumps(
                {
                    "source": record["source"],
                    "status": record["status"],
                    "total_seconds": record["total_seconds"],
                    "phase_seconds": record["phase_seconds"],
                    "product_id": record.get("marketplace_product_id"),
                    "jira_issue": record.get("jira_issue_key"),
                    "error": record.get("error"),
                },
                indent=2,
            ),
            flush=True,
        )
        if record["status"] != "success":
            print(
                "Stopped after an incomplete case; inspect the result and any destination writes before a new run.",
                flush=True,
            )
            break
    print("Summary:", json.dumps(summary, indent=2), flush=True)
    print("Report:", output / "benchmark-results.md", flush=True)
    return 0 if summary["all_cases_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
