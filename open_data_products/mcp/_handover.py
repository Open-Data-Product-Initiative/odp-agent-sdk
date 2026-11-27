"""Reviewed MCP handover and Jira workflows."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, replace
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

from .._guided_handoff import (
    _check_business_file,
    _conservative_visibility,
    _default_env_file,
    _load_env_file,
    _screen_instructions,
)
from .._handoff_implementation import (
    _citation_index,
    generate_implementation_handoff,
    preview_implementation_handoff,
)
from ..generation import (
    MAX_ODPS_SOURCE_CHARS,
    create_generation_client,
    generate_local_artifacts_for_kind,
    resolve_generation_settings,
)
from ..generation.prompts import load_source_documents as load_generation_source
from ..handoff import _discovery_package_context, handoff_jira_request
from ..integrations.jira import JiraCloudAdapter, JiraIssueRequest, load_jira_connection
from ..source_documents.documents import load_source_documents
from ._response import json_envelope


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def _settings(args):
    _load_env_file(_default_env_file(args.get("env_file")))
    config = args.get("config") or (
        "generation.config.yaml" if Path("generation.config.yaml").is_file() else None
    )
    return resolve_generation_settings(
        config_path=config, provider=args.get("provider"), model=args.get("model")
    )


def _provider_origin(url):
    if not url:
        return None
    parts = urlsplit(url)
    if not parts.scheme or not parts.hostname:
        return None
    host = parts.hostname
    if ":" in host:
        host = "[" + host + "]"
    return parts.scheme + "://" + host + (":" + str(parts.port) if parts.port else "")


def _bounded_source(path):
    with path.open("rb") as handle:
        data = handle.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("Source exceeds the 20 MiB file size limit")
    return data


def _business(path):
    path = Path(path).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError("Business document must be a regular file")
    if path.suffix.lower() not in {".md", ".txt", ".docx"}:
        raise ValueError("Business documents must be .md, .txt or .docx files")
    data = _bounded_source(path)
    with tempfile.TemporaryDirectory(prefix="odp-mcp-intake-") as temporary:
        staged = Path(temporary) / ("business" + path.suffix.lower())
        staged.write_bytes(data)
        _check_business_file(staged)
        generated = load_generation_source(staged)
        records = load_source_documents(staged)
    text = "\n\n".join(record.get("text", "") for record in records)
    if not text.strip():
        raise ValueError("Business document has no readable text")
    for value in (generated, text):
        if len(value) > MAX_ODPS_SOURCE_CHARS:
            raise ValueError("Business document exceeds the generation character limit")
        if any(
            unicodedata.category(c) in {"Cc", "Cf"} and c not in "\n\r\t" for c in value
        ):
            raise ValueError(
                "Business document contains unsupported control characters"
            )
        _screen_instructions(value)
    if hashlib.sha256(_bounded_source(path)).digest() != hashlib.sha256(data).digest():
        raise ValueError("Business document changed during extraction")
    return path, data


def _workspace(args):
    path = Path(args["output"]).expanduser().absolute()
    if path.is_symlink() or path.exists():
        raise ValueError("Output workspace already exists; refusing to overwrite")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("Output parent must be an existing directory")
    return path


def _business_review(args):
    path, data = _business(args["business_document"])
    settings = _settings(args)
    output = _workspace(args)
    source_hash = hashlib.sha256(data).hexdigest()
    from .._organization import load_organization

    organization = load_organization()
    review = {
        "organization": organization,
        "source_name": path.name,
        "source_sha256": source_hash,
        "source_bytes": len(data),
        "provider": settings.provider,
        "provider_type": settings.provider_type,
        "model": settings.model,
        "base_url": settings.base_url,
        "settings": asdict(settings),
        "output": str(output),
    }
    return path, data, settings, output, review, _digest(review)


def preview_business_handover(args):
    path, data, settings, output, review, digest = _business_review(args)
    review.pop("output")
    review.pop("base_url")
    review.pop("settings")
    organization = review.pop("organization")
    review["organization_default_fields"] = (
        sorted(organization["dataHolder"]) if organization else []
    )
    review["provider_origin"] = _provider_origin(settings.base_url)
    review.update(
        reviewed_sha256=digest,
        source_review="Review the supplied document before approving the provider request. Its content will be sent to the selected provider; this response does not contain the full document.",
    )
    return json_envelope(review)


def create_business_odps_draft(args):
    path, data, settings, output, review, digest = _business_review(args)
    if digest != args["reviewed_sha256"]:
        raise ValueError("Business source, provider or output changed since review")
    output.mkdir(mode=0o700)
    staged = output / ("business-brief" + path.suffix.lower())
    with staged.open("xb") as handle:
        handle.write(data)
    artifacts = generate_local_artifacts_for_kind(
        "odps-product",
        staged,
        output / "odps",
        model=settings.model,
        client=create_generation_client(settings),
        profile="minimal",
        odps_version="4.1",
        organization=review["organization"] or {},
    )
    if len(artifacts) != 1 or not artifacts[0].valid_yaml:
        raise ValueError("ODPS generation did not produce one valid draft")
    artifact = Path(artifacts[0].output_path)
    if artifact.parent.resolve() != (output / "odps").resolve():
        raise ValueError("Generated ODPS is outside the workspace")
    defaults = _conservative_visibility(artifact, artifacts[0])
    (output / "odps-generation-review.json").write_text(
        json.dumps(
            {
                "source_sha256": review["source_sha256"],
                "conservative_defaults": defaults,
                "review_notes": getattr(artifacts[0], "review_notes", []),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return json_envelope(
        {
            "status": "draft",
            "workspace_id": output.name,
            "business_document": staged.name,
            "odps_draft": "odps/" + artifact.name,
            "source_sha256": review["source_sha256"],
            "conservative_defaults": defaults,
            "review_notes": getattr(artifacts[0], "review_notes", []),
            "next_step": "Review the ODPS draft and use preview_implementation_handover.",
        }
    )


def _context(args):
    if not args.get("context_file"):
        return None
    path = Path(args["context_file"]).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError("Context snapshot must be a regular file")
    with path.open("rb") as handle:
        raw = handle.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Context snapshot exceeds 1 MiB")
    context = json.loads(raw)
    if not isinstance(context, dict):
        raise ValueError("Context snapshot must be an object")
    return context


def _implementation_review(args):
    business, data = _business(args["business_document"])
    product = Path(args["product"]).expanduser()
    if product.is_symlink() or not product.is_file():
        raise ValueError("ODPS draft must be a regular file")
    product_data = _bounded_source(product)
    settings = _settings(args)
    context = _context(args)
    output = _workspace(args)
    change = args["change_name"]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", change):
        raise ValueError("Change name must be kebab-case")
    with tempfile.TemporaryDirectory(prefix="odp-mcp-review-") as temporary:
        staged_business = Path(temporary) / ("business" + business.suffix.lower())
        staged_product = Path(temporary) / ("product" + product.suffix.lower())
        staged_business.write_bytes(data)
        staged_product.write_bytes(product_data)
        preview = preview_implementation_handoff(
            staged_business,
            staged_product,
            settings,
            context_snapshot=context,
            asset_id=args.get("asset_id"),
            business_product_id=args.get("business_product_id"),
        )
    preview = replace(
        preview,
        base=replace(preview.base, business_path=business, product_path=product),
    )
    if _bounded_source(business) != data or _bounded_source(product) != product_data:
        raise ValueError("Handover source changed during review")
    if context is not None:
        snapshot_size = len(json.dumps(context, indent=2, ensure_ascii=False).encode())
        columns = {
            key: value
            for key, value in _citation_index(preview.base, preview.assets).items()
            if key.startswith("C")
        }
        prompt_size = len(
            json.dumps(preview.assets, ensure_ascii=False, sort_keys=True).encode()
        ) + len(json.dumps(columns, ensure_ascii=False, sort_keys=True).encode())
        if snapshot_size > 1024 * 1024 or prompt_size > 256 * 1024:
            raise ValueError("Metadata evidence exceeds the discovery budget")
    review = {
        "input_digest": preview.digest,
        "business_sha256": hashlib.sha256(data).hexdigest(),
        "odps_sha256": hashlib.sha256(product_data).hexdigest(),
        "output": str(output),
        "change_name": change,
        "include_full_business": bool(args.get("include_full_business", False)),
    }
    return preview, settings, output, review, _digest(review)


def preview_implementation_handover(args):
    preview, settings, output, review, digest = _implementation_review(args)
    return json_envelope(
        {
            "mode": "implementation-draft",
            "provider": settings.provider,
            "provider_type": settings.provider_type,
            "provider_origin": _provider_origin(settings.base_url),
            "model": settings.model,
            "business_document": preview.base.business_path.name,
            "business_sha256": review["business_sha256"],
            "odps_document": preview.base.product_path.name,
            "odps_sha256": review["odps_sha256"],
            "catalog_assets": [
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "column_count": len(a.get("columns", [])),
                }
                for a in preview.assets
            ],
            "reviewed_sha256": digest,
            "source_review": "Review the supplied business document, ODPS and optional catalog snapshot before approving. The provider receives business and ODPS text and selected catalog columns; this response does not include full documents.",
            "include_full_business": review["include_full_business"],
            "discovery_target": (
                _discovery_package_context(preview.context).get("discovery_target")
                if preview.context is not None
                else None
            ),
        }
    )


def create_implementation_handover(args):
    preview, settings, output, review, digest = _implementation_review(args)
    if digest != args["reviewed_sha256"]:
        raise ValueError("Handover inputs, provider or output changed since review")
    with tempfile.TemporaryDirectory(prefix="odp-mcp-sources-") as temporary:
        staged_business = Path(temporary) / (
            "business" + preview.base.business_path.suffix
        )
        staged_product = Path(temporary) / (
            "product" + preview.base.product_path.suffix
        )
        staged_business.write_bytes(_bounded_source(preview.base.business_path))
        staged_product.write_bytes(_bounded_source(preview.base.product_path))
        if (
            hashlib.sha256(staged_business.read_bytes()).hexdigest()
            != review["business_sha256"]
            or hashlib.sha256(staged_product.read_bytes()).hexdigest()
            != review["odps_sha256"]
        ):
            raise ValueError("Handover sources changed during staging")
        staged_preview = preview_implementation_handoff(
            staged_business,
            staged_product,
            settings,
            context_snapshot=preview.context,
            asset_id=preview.asset_id,
            business_product_id=preview.base.business_product_id,
        )
        if staged_preview.digest != preview.digest:
            raise ValueError("Handover sources changed during staging")
        root = generate_implementation_handoff(
            staged_preview,
            output,
            args["change_name"],
            settings,
            reviewed_sha256=staged_preview.digest,
            include_full_business=review["include_full_business"],
        )
    archive = output / "handoff.zip"
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as zipped:
        for file in sorted(root.rglob("*")):
            if file.is_symlink():
                raise ValueError("Handoff package cannot contain symlinks")
            if file.is_file():
                zipped.write(file, file.relative_to(root).as_posix())
    return json_envelope(
        {
            "status": "draft",
            "workspace_id": output.name,
            "change": "openspec/changes/" + args["change_name"],
            "package": "handoff.zip",
            "odcs_draft": "supporting/odcs-draft.yaml",
            "next_step": "Review the draft and use review_jira_handover before delivery.",
        }
    )


def _jira(args):
    _load_env_file(_default_env_file(args.get("env_file")))
    return JiraCloudAdapter(
        load_jira_connection(
            args.get("connections", "connections.yaml"), args.get("connection", "jira")
        )
    )


def _general_issue(args):
    return JiraIssueRequest(
        args["project"],
        args["issue_type_id"],
        args["summary"],
        args["description"],
        args.get("fields") or {},
        tuple(args.get("attachments") or ()),
    )


def _handover_issue(args):
    issue = handoff_jira_request(
        args["change"],
        project=args["project"],
        issue_type_id=args["issue_type_id"],
        package_attachment=args.get("package_attachment"),
        package_url=args.get("package_url"),
        shared_filesystem=args.get("shared_filesystem"),
        business_url=args.get("business_url"),
        product_url=args.get("product_url"),
        fields=args.get("fields") or {},
        attachments=tuple(args.get("attachments") or ()),
    )
    if "Business document: not supplied;" in issue.description:
        raise ValueError(
            "Provide an accessible business source URL or attachment before Jira delivery"
        )
    return issue


def _review(adapter, issue, *, handover_args=None):
    value = adapter.review_issue(issue)
    result = {
        "destination": value["destination"],
        "destination_url": adapter.connection.base_url,
        "project": value["project"],
        "issue_type_id": value["issue_type_id"],
        "summary": value["summary"],
        "reviewed_sha256": value["reviewed_sha256"],
        "attachments": value["attachments"],
        "possible_duplicate_keys": [x.get("key") for x in value["possible_duplicates"]],
        "duplicate_warning": value["duplicate_warning"],
        "review_note": "Review the supplied issue text or handover package and accessibility before approval. The digest binds destination, issue content and attachments.",
    }
    if handover_args is not None:
        method = (
            "attachment"
            if handover_args.get("package_attachment")
            else (
                "shared_filesystem"
                if handover_args.get("shared_filesystem")
                else "https"
            )
        )
        result["delivery_access"] = {
            "package_method": method,
            "business_source": (
                "https" if handover_args.get("business_url") else "attachment"
            ),
            "assumption": "The coding assistant must be able to access the selected package and source; shared filesystems must actually be shared.",
        }
    return json_envelope(result)


def review_jira_issue(args):
    return _review(_jira(args), _general_issue(args))


def review_jira_handover(args):
    return _review(_jira(args), _handover_issue(args), handover_args=args)


def _create(adapter, issue, args):
    journal = Path(args["journal_file"]).expanduser()
    if (
        journal.is_symlink()
        or not journal.parent.is_dir()
        or journal.parent.is_symlink()
    ):
        raise ValueError(
            "Journal parent must be an existing directory; symlinks are not allowed"
        )
    try:
        fd = os.open(str(journal), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError(
            "Execution journal already exists; inspect Jira before retrying"
        ) from None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:

        def record(value):
            handle.seek(0)
            handle.truncate()
            json.dump(value, handle)
            handle.flush()
            os.fsync(handle.fileno())

        record({"status": "pending", "reviewed_sha256": args["reviewed_sha256"]})
        try:
            result = adapter.create_issue(
                issue, reviewed_sha256=args["reviewed_sha256"]
            )
        except Exception:
            record(
                {
                    "status": "unknown_or_failed",
                    "next_step": "Inspect Jira before retrying.",
                }
            )
            raise
        status = "partial" if result.get("attachment_failures") else "created"
        result["status"] = status
        record({"status": status, "result": result})
    if status == "partial":
        result["warning"] = (
            "Some attachments failed or have unknown outcomes; inspect Jira before retrying."
        )
    envelope = json_envelope(result)
    if status == "partial":
        envelope["isError"] = True
    return envelope


def create_jira_issue(args):
    return _create(_jira(args), _general_issue(args), args)


def deliver_jira_handover(args):
    return _create(_jira(args), _handover_issue(args), args)


def _guard(handler):
    def invoke(args):
        try:
            return handler(args)
        except Exception as exc:
            message = str(exc)
            for key in (
                "business_document",
                "product",
                "output",
                "context_file",
                "config",
                "env_file",
                "connections",
                "change",
                "package_attachment",
                "journal_file",
                "attachments",
            ):
                value = args.get(key)
                paths = value if isinstance(value, list) else [value]
                for item in paths:
                    if isinstance(item, str) and item:
                        for candidate in (
                            item,
                            str(Path(item).expanduser().absolute()),
                        ):
                            if len(candidate) > 2:
                                message = message.replace(candidate, "<local-path>")
            for name, value in os.environ.items():
                if (
                    re.search(r"(?:TOKEN|SECRET|PASSWORD|API_KEY)", name, re.I)
                    and len(value) >= 8
                ):
                    message = message.replace(value, "<redacted>")
            result = json_envelope({"error": type(exc).__name__, "message": message})
            result["isError"] = True
            return result

    return invoke


def tool_definitions(object_schema):
    """Return MCP definitions with explicit review and write classifications."""
    string = {"type": "string"}
    config = {"config": string, "env_file": string, "provider": string, "model": string}
    business = {"business_document": string, "output": string, **config}
    implementation = {
        **business,
        "product": string,
        "change_name": string,
        "context_file": string,
        "asset_id": string,
        "business_product_id": string,
        "include_full_business": {"type": "boolean"},
    }
    common = {
        "connections": string,
        "connection": string,
        "env_file": string,
        "project": string,
        "issue_type_id": string,
        "fields": {"type": "object"},
        "attachments": {"type": "array", "items": string},
    }
    issue = {**common, "summary": string, "description": string}
    handover = {
        **common,
        "change": string,
        "package_attachment": string,
        "package_url": string,
        "shared_filesystem": string,
        "business_url": string,
        "product_url": string,
    }
    reviewed = {"reviewed_sha256": string}
    journal = {"journal_file": string}
    definitions = [
        (
            "preview_business_handover",
            "Review the business source and provider before drafting ODPS.",
            "safe",
            business,
            ["business_document", "output"],
            preview_business_handover,
        ),
        (
            "create_business_odps_draft",
            "Generate a local ODPS draft after business-source review.",
            "state-changing",
            {**business, **reviewed},
            ["business_document", "output", "reviewed_sha256"],
            create_business_odps_draft,
        ),
        (
            "preview_implementation_handover",
            "Review business, ODPS, provider and catalog evidence before generation.",
            "safe",
            implementation,
            ["business_document", "product", "output", "change_name"],
            preview_implementation_handover,
        ),
        (
            "create_implementation_handover",
            "Generate a local OpenSpec handover and ODCS draft after review.",
            "state-changing",
            {**implementation, **reviewed},
            [
                "business_document",
                "product",
                "output",
                "change_name",
                "reviewed_sha256",
            ],
            create_implementation_handover,
        ),
        (
            "review_jira_issue",
            "Review a general Jira Cloud issue before creation.",
            "safe",
            issue,
            ["project", "issue_type_id", "summary", "description"],
            review_jira_issue,
        ),
        (
            "create_jira_issue",
            "Create a reviewed general Jira issue once and record its outcome.",
            "state-changing",
            {**issue, **reviewed, **journal},
            [
                "project",
                "issue_type_id",
                "summary",
                "description",
                "reviewed_sha256",
                "journal_file",
            ],
            create_jira_issue,
        ),
        (
            "review_jira_handover",
            "Review Jira delivery of a handover and its accessible sources.",
            "safe",
            handover,
            ["change", "project", "issue_type_id"],
            review_jira_handover,
        ),
        (
            "deliver_jira_handover",
            "Deliver a reviewed handover to Jira once and record its outcome.",
            "state-changing",
            {**handover, **reviewed, **journal},
            ["change", "project", "issue_type_id", "reviewed_sha256", "journal_file"],
            deliver_jira_handover,
        ),
    ]
    descriptions = {
        "business_document": "Business document path. Review it before authorizing provider use.",
        "output": "New local output directory. The parent must exist and the directory must not.",
        "config": "Optional generation configuration path.",
        "env_file": "Optional environment file path; defaults to .env when present.",
        "provider": "Optional configured generation provider override.",
        "model": "Optional generation model override.",
        "product": "ODPS draft document path.",
        "change_name": "Kebab-case OpenSpec change name.",
        "context_file": "Optional JSON metadata evidence snapshot, limited to 1 MiB.",
        "asset_id": "Optional selected catalog asset identifier.",
        "business_product_id": "Optional explicit business product identifier.",
        "include_full_business": "Explicitly include the full business text in the package.",
        "connections": "Named connection configuration path; defaults to connections.yaml.",
        "connection": "Jira connection name; defaults to jira.",
        "project": "Jira project key or ID.",
        "issue_type_id": "Jira issue type ID.",
        "fields": "Jira custom fields; core issue fields cannot be overridden.",
        "attachments": "Explicit local file attachments; review hashes and accessibility.",
        "summary": "General issue summary.",
        "description": "General issue description in Markdown.",
        "change": "Generated OpenSpec change directory.",
        "package_attachment": "Package ZIP; choose exactly one package delivery method.",
        "package_url": "Accessible HTTPS package reference.",
        "shared_filesystem": "Package reference on a filesystem shared with the assistant.",
        "business_url": "Accessible HTTPS business source reference.",
        "product_url": "Accessible HTTPS ODPS source reference where supported.",
        "reviewed_sha256": "Exact digest returned by the corresponding review tool.",
        "journal_file": "New local execution journal; inspect Jira before retrying any existing journal.",
    }
    return [
        {
            "name": name,
            "description": description,
            "class": category,
            "inputSchema": object_schema(
                {
                    key: {**value, "description": descriptions[key]}
                    for key, value in properties.items()
                },
                required,
            ),
            "handler": _guard(handler),
        }
        for name, description, category, properties, required, handler in definitions
    ]
