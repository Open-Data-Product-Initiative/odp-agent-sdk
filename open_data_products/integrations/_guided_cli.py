"""Interactive shortcuts built on reviewed platform integration operations."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from uuid import UUID
from typing import Dict, Optional, Tuple

import yaml

from ..odpc.catalog import iter_catalog_input_files
from .adapter import open_integration
from .config import ConnectionProfile, IntegrationError
from .create import UnknownCreateOutcome
from .openmetadata import PlatformError

SETTINGS = Path(".open-data-products/integrations.yaml")


def add_guided_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Add optional short commands alongside the established integrations tree."""
    connect = subparsers.add_parser(
        "connect",
        help="Select a platform connection for this workspace",
        description="Select a named profile from the connection configuration for guided OpenMetadata commands.",
        epilog="Example: open-data-products connect openmetadata --config connections.yaml",
    )
    connect.add_argument("connection", nargs="?", help="Connection profile name")
    connect.add_argument("--config", help="Connection configuration YAML")
    connect.add_argument("--json", action="store_true", help="Emit structured JSON")
    products = subparsers.add_parser(
        "openmetadata",
        aliases=["products"],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Work with products in OpenMetadata (products is a compatibility alias)",
        description="Discover catalog evidence or review product operations using an OpenMetadata connection.",
        epilog=(
            'Examples:\n  open-data-products openmetadata products search "campaign"\n'
            '  open-data-products openmetadata products create ./products --domain "Banking"\n\n'
            "Next steps:\n  Use open-data-products openmetadata COMMAND --help for options and examples."
        ),
    )
    actions = products.add_subparsers(dest="guided_action", required=True)
    from .cli import add_integrations_parser

    add_integrations_parser(actions)
    _add_product_actions(actions)
    discover = actions.add_parser(
        "discover",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Discover read-only catalog evidence",
        description="Retrieve available product and catalog evidence without modifying OpenMetadata.",
        epilog='Examples:\n  open-data-products openmetadata discover --id PRODUCT_UUID --json\n  open-data-products openmetadata discover --query "customer accounts" --json',
    )
    discover.add_argument("--config", help="Override connection configuration")
    discover.add_argument("--connection", help="Override connection profile")
    discover.add_argument("--id", help="Explicit product UUID")
    discover.add_argument("--query", help="Catalog search query")
    discover.add_argument(
        "--limit", type=int, default=20, help="Candidate limit, 1 to 100 (default: 20)"
    )
    discover.add_argument("--json", action="store_true", help="Emit structured JSON")
    nested = actions.add_parser("products", help="Manage OpenMetadata data products")
    _add_product_actions(
        nested.add_subparsers(dest="guided_action", required=True), mutations=True
    )


def _add_product_actions(
    actions: argparse._SubParsersAction, *, mutations: bool = False
) -> None:
    names = ("list", "search", "get", "compare", "create", "export") + (
        ("update", "delete") if mutations else ()
    )
    for name in names:
        p = actions.add_parser(
            name,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            help={
                "list": "List products",
                "search": "Search products",
                "get": "Retrieve a product",
                "compare": "Compare source with a product",
                "create": "Review and create products in OpenMetadata interactively",
                "export": "Export OpenMetadata products as an ODPC catalog",
                "update": "Review and update a product by UUID",
                "delete": "Review and permanently delete a product by UUID",
            }[name],
        )
        p.add_argument("--config", help="Override connection configuration")
        p.add_argument("--connection", help="Override connection profile")
        p.add_argument("--json", action="store_true", help="Emit structured JSON")
        if name == "search":
            p.add_argument("query", help="Product search query")
            p.add_argument(
                "--offset",
                type=int,
                default=0,
                help="Search result offset (default: 0)",
            )
            p.add_argument(
                "--limit",
                type=int,
                default=20,
                help="Maximum search results (default: 20)",
            )
        if name in ("get", "compare"):
            p.add_argument(
                "product",
                nargs="?",
                help="Product UUID (positional compatibility form)",
            )
            p.add_argument(
                "--id", help="OpenMetadata product UUID; names are not accepted"
            )
        if name == "get":
            p.add_argument(
                "--format",
                choices=("native", "odps"),
                default="native",
                help="Response format (default: native)",
            )
        if name == "compare":
            p.add_argument("--source", required=True, help="Local ODPS file to compare")
            p.add_argument(
                "--domain", help="Expected destination domain; inferred when unique"
            )
        if name == "create":
            p.description = (
                "Review one ODPS 4.1 file or folder, then confirm creation in the selected\n"
                "writable OpenMetadata 2.1.0 connection. Non-interactive and --json runs\n"
                "only review; use openmetadata api products create for scripted execution.\n"
                "Creating metadata does not verify marketplace UI visibility."
            )
            p.epilog = 'Example:\n  open-data-products openmetadata products create products/ --domain "Retail Banking"'
            p.add_argument("source", help="ODPS YAML/JSON file or folder")
            p.add_argument(
                "--domain",
                required=True,
                help="Existing destination domain fully qualified name; quote the value",
            )
            p.add_argument(
                "--owner",
                action="append",
                dest="owners",
                help="Existing user:NAME or team:FQN; repeatable",
            )
            p.add_argument(
                "--tag",
                action="append",
                dest="tags",
                help="Existing classification tag FQN; repeatable",
            )
        if name == "export":
            p.add_argument(
                "--output",
                required=True,
                help="New ODPC .yaml, .yml or .json file (never overwritten)",
            )
        if name in ("update", "delete"):
            p.add_argument(
                "--id",
                required=True,
                help="OpenMetadata product UUID (names are not accepted)",
            )
            p.add_argument(
                "--execute",
                action="store_true",
                help="Execute a previously reviewed operation",
            )
            p.add_argument("--reviewed-sha256", help="Digest from a previous review")
        if name == "update":
            p.add_argument(
                "--input", "-i", help="ODPS YAML or JSON file to review for this update"
            )
            p.add_argument("--title", help="New display title")
            p.add_argument("--description", help="New description")
            p.add_argument(
                "--domain", help="Replace domains with this FQN; quote multiword values"
            )
            p.add_argument(
                "--owner",
                action="append",
                dest="owners",
                help="Add an existing user:NAME or team:FQN; repeatable",
            )
            p.add_argument(
                "--tag",
                action="append",
                dest="tags",
                help="Add an existing classification tag FQN; repeatable",
            )
        if name == "delete":
            p.add_argument(
                "--confirm-permanent",
                action="store_true",
                help="Confirm permanent recursive deletion for scripted execution",
            )


def _settings() -> Dict[str, str]:
    if not SETTINGS.exists():
        return {}
    try:
        data = yaml.safe_load(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise IntegrationError("Cannot read workspace integration selection") from None
    if (
        not isinstance(data, dict)
        or set(data) != {"config", "connection"}
        or not all(
            isinstance(data.get(x), str) and data[x] for x in ("config", "connection")
        )
    ):
        raise IntegrationError("Invalid workspace integration selection")
    return data


def _select(
    config_path: Optional[str] = None, connection: Optional[str] = None
) -> Tuple[str, ConnectionProfile]:
    settings = {} if config_path else _settings()
    path = config_path or settings.get("config") or "connections.yaml"
    target = Path(path).expanduser()
    if not target.is_file():
        raise IntegrationError(
            "Connection configuration is required. Run 'open-data-products config setup' or supply an existing --config."
        )
    from .config import _UniqueLoader
    from .._guided_handoff import _resolve_discovery_profile

    try:
        root = yaml.load(target.read_text(encoding="utf-8"), Loader=_UniqueLoader)
        default = root.get("default_connection") if isinstance(root, dict) else None
    except (OSError, UnicodeError, yaml.YAMLError):
        raise IntegrationError("Cannot read connection configuration") from None
    name = (
        connection or (None if config_path else settings.get("connection")) or default
    )
    if not name:
        raise IntegrationError("Select an OpenMetadata connection by name")
    return str(target.resolve()), _resolve_discovery_profile(str(target), name)


def _emit(value, structured=False):  # type: ignore[no-untyped-def]
    if structured:
        print(json.dumps(value, indent=2))
    elif isinstance(value, list):
        for item in value:
            print(
                f"{item.get('displayName') or item.get('name') or item.get('id')}\t{item.get('id', '')}"
            )
        if not value:
            print("No products found.")
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False))


def _interactive(args: argparse.Namespace) -> bool:
    return not args.json and sys.stdin.isatty() and sys.stdout.isatty()


def _product_uuid(args: argparse.Namespace) -> str:
    """Require a UUID without resolving names through a platform listing."""
    if args.id and args.product:
        raise IntegrationError(
            "Provide the product UUID once, using --id or the positional argument"
        )
    try:
        return str(UUID(args.id or args.product))
    except (ValueError, TypeError, AttributeError):
        raise IntegrationError(
            "A valid product UUID is required; names are not accepted"
        ) from None


def _create(adapter, args):  # type: ignore[no-untyped-def]
    interactive = _interactive(args)
    source = Path(args.source)
    if source.is_file():
        files = [source] if source.suffix.lower() in (".yaml", ".yml", ".json") else []
    elif source.is_dir():
        files = iter_catalog_input_files(source, recursive=True)
    else:
        raise IntegrationError("Source file or folder does not exist")
    if not files:
        raise IntegrationError("No YAML or JSON product files found")
    entries = []
    for path in files:
        entry = {"file": str(path), "domain": args.domain, "status": "skipped"}
        try:
            text = path.read_text(encoding="utf-8")
            review = adapter.review_create(
                text,
                domain=args.domain,
                source_path=str(path),
                owners=args.owners,
                tags=args.tags,
            )
            entry["review"] = review.to_dict()
            if not review.executable:
                entry["reason"] = (
                    "Invalid, incompatible or read-only; inspect review findings"
                )
            else:
                candidates = adapter.find_create_candidates(
                    text, domain=args.domain, source_path=str(path)
                )
                entry["candidates"] = candidates
                if not candidates.get("complete") or candidates.get("candidates"):
                    entry["reason"] = (
                        "Possible duplicates or incomplete duplicate check"
                    )
                else:
                    entry["status"] = "eligible"
                    entry["_source"] = text
                    entry["_digest"] = review.review_sha256
        except (IntegrationError, OSError, UnicodeError, ValueError) as exc:
            if isinstance(exc, (PlatformError, OSError, UnicodeError)):
                entry["status"] = "failed"
            entry["reason"] = (
                str(exc)
                if isinstance(exc, IntegrationError)
                else "Unable to read or review source"
            )
        entries.append(entry)
    identifiers = {}
    for entry in entries:
        review = entry.get("review")
        if isinstance(review, dict) and review.get("product_id"):
            ident = review["product_id"]
            identifiers[ident] = identifiers.get(ident, 0) + 1
    for entry in entries:
        review = entry.get("review")
        if (
            isinstance(review, dict)
            and identifiers.get(review.get("product_id"), 0) > 1
        ):
            entry["status"] = "skipped"
            entry["reason"] = "Multiple source files have the same product identifier"
    if not interactive:
        report = {
            "connection": adapter.profile.name,
            "domain": args.domain,
            "status": "review_only",
            "message": "Creation requires an interactive terminal. For automation use openmetadata api products create with --reviewed-sha256 and --execute.",
            "products": [
                {k: v for k, v in entry.items() if not k.startswith("_")}
                for entry in entries
            ],
        }
        _emit(report, args.json)
        return 1
    print(
        f"Platform: {adapter.profile.platform}; connection: {adapter.profile.name}; destination domain: {args.domain}"
    )
    print(
        "Duplicate checks are permission-limited and cannot prevent concurrent creates."
    )
    for entry in entries:
        shown = {k: v for k, v in entry.items() if not k.startswith("_")}
        if isinstance(shown.get("review"), dict):
            shown["review"] = {
                k: v for k, v in shown["review"].items() if k != "review_sha256"
            }
        print(json.dumps(shown, indent=2, ensure_ascii=False))
    eligible = [entry for entry in entries if entry["status"] == "eligible"]
    if not eligible:
        print("No eligible products to create.")
        return 1
    try:
        confirmation = (
            input(f"Create {len(eligible)} eligible product(s)? [y/N] ").strip().lower()
        )
    except EOFError:
        confirmation = ""
    if confirmation not in ("y", "yes"):
        for entry in eligible:
            entry["status"] = "skipped"
            entry["reason"] = "Not confirmed"
    else:
        for entry in eligible:
            try:
                path = Path(entry["file"])
                current = path.read_text(encoding="utf-8")
                if current != entry["_source"]:
                    entry["status"] = "skipped"
                    entry["reason"] = "Source changed after review"
                    continue
                candidates = adapter.find_create_candidates(
                    current, domain=args.domain, source_path=str(path)
                )
                if not candidates.get("complete") or candidates.get("candidates"):
                    entry["status"] = "skipped"
                    entry["reason"] = (
                        "Possible duplicates or incomplete duplicate check before creation"
                    )
                    continue
                result = adapter.create_product(
                    current,
                    domain=args.domain,
                    source_path=str(path),
                    owners=args.owners,
                    tags=args.tags,
                    reviewed_sha256=entry["_digest"],
                )
                entry["result"] = result.to_dict()
                entry["status"] = "created" if result.status == "created" else "failed"
                if result.status != "created":
                    entry["reason"] = (
                        "Product may exist; inspect the returned outcome before retrying"
                    )
            except UnknownCreateOutcome as exc:
                entry["status"] = "uncertain"
                entry["reason"] = str(exc)
            except (IntegrationError, OSError, UnicodeError, ValueError) as exc:
                entry["status"] = "failed"
                entry["reason"] = (
                    str(exc)
                    if isinstance(exc, IntegrationError)
                    else "Unable to read or execute source"
                )
    print("Results:")
    for entry in entries:
        if isinstance(entry.get("review"), dict):
            entry["review"] = {
                k: v for k, v in entry["review"].items() if k != "review_sha256"
            }
        print(
            json.dumps(
                {k: v for k, v in entry.items() if not k.startswith("_")},
                ensure_ascii=False,
            )
        )
    return 0 if all(e["status"] == "created" for e in entries) else 1


def _mutate(adapter, args):  # type: ignore[no-untyped-def]
    try:
        product_id = str(UUID(args.id))
    except (ValueError, TypeError, AttributeError):
        raise IntegrationError(
            "A valid product UUID is required; names are not accepted"
        ) from None
    is_delete = args.guided_action == "delete"
    input_source = None
    if not is_delete and args.input:
        from .update import _read_update_source

        input_source = _read_update_source(args.input)
    kwargs = (
        {}
        if is_delete
        else {
            "title": args.title,
            "description": args.description,
            "domain": args.domain,
            "owners": args.owners,
            "tags": args.tags,
        }
    )
    if input_source is not None:
        kwargs["source_yaml"] = input_source
    if args.execute:
        if not args.reviewed_sha256:
            raise IntegrationError(
                "Execution requires --reviewed-sha256 from a prior review"
            )
        if is_delete and not args.confirm_permanent:
            raise IntegrationError("Deletion requires --confirm-permanent")
        digest = args.reviewed_sha256
    else:
        review = (
            adapter.review_delete(product_id)
            if is_delete
            else adapter.review_update(product_id, **kwargs)
        )
        result = review.to_dict()
        if _interactive(args):
            result.pop("review_sha256", None)
        _emit(result, args.json)
        if not _interactive(args):
            return 0
        if not review.write_enabled:
            raise IntegrationError("The connection is configured read-only")
        question = (
            "Permanently and recursively delete this product? [y/N] "
            if is_delete
            else "Apply these product changes? [y/N] "
        )
        try:
            confirm = input(question).strip().lower()
        except EOFError:
            confirm = ""
        if confirm not in ("y", "yes"):
            print("Cancelled; no changes made.")
            return 1
        digest = review.review_sha256
        if input_source is not None and _read_update_source(args.input) != input_source:
            raise IntegrationError("ODPS input changed after review; review again")
    if is_delete:
        result = adapter.delete_product(
            product_id, reviewed_sha256=digest, confirm_permanent=True
        )
        _emit(result.to_dict(), args.json)
        return 0 if result.verification == "not_found_by_id" else 1
    result = adapter.update_product(product_id, reviewed_sha256=digest, **kwargs)
    _emit(result.to_dict(), args.json)
    return 0 if all(value == "matched" for value in result.comparison.values()) else 1


def handle_guided(args):  # type: ignore[no-untyped-def]
    """Execute a short integration command using existing adapter services."""
    try:
        path, profile = _select(args.config, args.connection)
        if args.command == "openmetadata" and profile.platform != "openmetadata":
            raise IntegrationError(
                "The selected connection is not an OpenMetadata connection"
            )
        with open_integration(profile) as adapter:
            if args.command == "connect":
                result = adapter.check_connection()
                if result.get("status") != "connected":
                    raise IntegrationError("Connection check did not succeed")
                SETTINGS.parent.mkdir(parents=True, exist_ok=True)
                SETTINGS.write_text(
                    yaml.safe_dump(
                        {"config": path, "connection": profile.name}, sort_keys=True
                    ),
                    encoding="utf-8",
                )
                _emit(
                    {
                        "connection": profile.name,
                        "platform": profile.platform,
                        "config": path,
                        "status": result.get("status"),
                    },
                    args.json,
                )
                return 0
            required = {
                "discover": ("discover_context",),
                "list": ("list_products_odpc",),
                "search": ("search_products_odpc",),
                "get": ("get_product",),
                "compare": ("get_product", "compare_product"),
                "create": ("review_create", "find_create_candidates", "create_product"),
                "export": ("list_products_odpc",),
                "update": ("review_update", "update_product"),
                "delete": ("review_delete", "delete_product"),
            }[args.guided_action]
            if args.guided_action == "get" and args.format == "odps":
                required += ("export_odps",)
            if any(not callable(getattr(adapter, method, None)) for method in required):
                raise IntegrationError(
                    "The selected platform does not support this operation"
                )
            if args.guided_action == "discover":
                _emit(
                    adapter.discover_context(
                        product_id=args.id, query=args.query, limit=args.limit
                    ),
                    args.json,
                )
                return 0
            if args.guided_action == "list":
                _emit(adapter.list_products_odpc(), args.json)
                return 0
            if args.guided_action == "export":
                from .cli import _save_output_set

                target = Path(args.output)
                suffix = target.suffix.lower()
                if suffix not in (".yaml", ".yml", ".json"):
                    raise IntegrationError(
                        "ODPC output must use a .yaml, .yml or .json extension"
                    )
                document = adapter.list_products_odpc()
                rendered = (
                    json.dumps(document, indent=2, ensure_ascii=False) + "\n"
                    if suffix == ".json"
                    else yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
                )
                _save_output_set([(target, rendered)])
                _emit(
                    {
                        "status": "exported",
                        "output": str(target),
                        "format": "json" if suffix == ".json" else "yaml",
                        "products": len(document["catalog"]["productReferences"]),
                    },
                    args.json,
                )
                return 0
            if args.guided_action == "search":
                _emit(
                    adapter.search_products_odpc(
                        args.query, offset=args.offset, limit=args.limit
                    ),
                    args.json,
                )
                return 0
            if args.guided_action == "create":
                return _create(adapter, args)
            if args.guided_action in ("update", "delete"):
                return _mutate(adapter, args)
            if args.guided_action == "get":
                product_id = _product_uuid(args)
                result = (
                    adapter.get_product(
                        product_id, include_domains=True, include_owners_tags=True
                    )
                    if args.format == "native"
                    else adapter.export_odps(product_id)
                )
                payload = {
                    "data": result.data,
                    "provenance": asdict(result.provenance),
                    "validation": (
                        asdict(result.validation) if result.validation else None
                    ),
                }
                _emit(payload, args.json)
                return 0 if result.validation is None or result.validation.valid else 1
            product_id = _product_uuid(args)
            domain = args.domain
            if not domain:
                result = adapter.get_product(product_id, include_domains=True)
                refs = (
                    result.data.get("domains")
                    if isinstance(result.data, dict)
                    else None
                )
                if (
                    not isinstance(refs, list)
                    or len(refs) != 1
                    or not isinstance(refs[0], dict)
                    or not refs[0].get("fullyQualifiedName")
                ):
                    raise IntegrationError(
                        "Product domain is missing or ambiguous; specify --domain"
                    )
                domain = refs[0]["fullyQualifiedName"]
            result = adapter.compare_product(
                Path(args.source).read_text(encoding="utf-8"),
                product_id=product_id,
                domain=domain,
            )
            _emit(result.to_dict(), args.json)
            return 0 if result.source_validation.valid else 1
    except (IntegrationError, OSError, UnicodeError) as exc:
        message = (
            str(exc)
            if isinstance(exc, IntegrationError)
            else "Unable to read or write a local file"
        )
        if getattr(args, "json", False):
            print(json.dumps({"error": message}))
        else:
            print(message, file=sys.stderr)
        return 1
