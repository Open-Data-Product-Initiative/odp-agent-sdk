"""CLI bindings for platform integration operations."""

from dataclasses import asdict
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Dict, List, Tuple
from uuid import UUID

from .config import IntegrationError, load_integration_config
from .openmetadata import OpenMetadataAdapter, normalize_openmetadata_updated_dates


def add_integrations_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the integrations command tree."""
    parser = subparsers.add_parser(
        "integrations", help="Use platform connection profiles"
    )
    commands = parser.add_subparsers(dest="integration_command", required=True)
    profiles = commands.add_parser("list", help="List configured connection names")
    profiles.add_argument("--config", required=True)
    profiles.add_argument("--json", action="store_true")
    check = commands.add_parser("check", help="Check read connectivity")
    check.add_argument("connection")
    check.add_argument("--config", required=True)
    check.add_argument("--json", action="store_true")
    discovery = commands.add_parser(
        "discover", help="Discover bounded read-only context"
    )
    discovery.add_argument("connection")
    discovery.add_argument("--config", required=True)
    discovery.add_argument("--id")
    discovery.add_argument("--query")
    discovery.add_argument("--limit", type=int, default=20)
    discovery.add_argument("--json", action="store_true")
    domains = commands.add_parser("domains", help="List available OpenMetadata domains")
    domains.add_argument("connection")
    domains.add_argument("--config", required=True)
    domains.add_argument("--limit", type=int, default=100)
    domains.add_argument("--after")
    domains.add_argument("--json", action="store_true")
    domain_create = commands.add_parser(
        "domain-create", help="Review or create an OpenMetadata domain"
    )
    domain_create.add_argument("connection")
    domain_create.add_argument("--config", required=True)
    domain_create.add_argument("--name", required=True)
    domain_create.add_argument("--description", required=True)
    domain_create.add_argument(
        "--type",
        required=True,
        choices=("Source-aligned", "Consumer-aligned", "Aggregate"),
    )
    domain_create.add_argument("--display-name")
    domain_create.add_argument("--parent", help="Parent domain FQN for a subdomain")
    domain_create.add_argument("--execute", action="store_true")
    domain_create.add_argument("--reviewed-sha256")
    domain_create.add_argument("--json", action="store_true")
    products = commands.add_parser(
        "products", help="Read, create, update or delete platform products"
    )
    actions = products.add_subparsers(dest="integration_action", required=True)
    listing = actions.add_parser("list", help="List one page of products")
    listing.add_argument("connection")
    listing.add_argument("--config", required=True)
    listing.add_argument("--limit", type=int, default=100)
    listing.add_argument("--after")
    listing.add_argument("--json", action="store_true")
    search = actions.add_parser("search", help="Search platform data products")
    search.add_argument("connection")
    search.add_argument("--config", required=True)
    search.add_argument("--query", required=True, help="OpenMetadata search query")
    search.add_argument("--offset", type=int, default=0)
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--json", action="store_true")
    compare = actions.add_parser(
        "compare", help="Compare source ODPS with a retrieved product"
    )
    compare.add_argument("connection")
    compare.add_argument("--config", required=True)
    compare.add_argument("--id", required=True, help="Platform product ID")
    compare.add_argument("--source", required=True, help="Reviewed ODPS YAML")
    compare.add_argument(
        "--domain", required=True, help="Intended destination domain FQN"
    )
    compare.add_argument("--language", default="en")
    compare.add_argument(
        "--output", help="Save the comparison JSON without overwriting"
    )
    compare.add_argument("--json", action="store_true")
    get = actions.add_parser("get", help="Retrieve a product")
    get.add_argument("connection")
    get.add_argument("--config", required=True)
    get.add_argument("--id", required=True)
    get.add_argument("--format", choices=("odps", "native"), default="odps")
    get.add_argument(
        "--include-extensions",
        action="store_true",
        help="Include native custom properties",
    )
    get.add_argument(
        "--include-domains",
        action="store_true",
        help="Include native domain references",
    )
    get.add_argument("--output", help="Write the retrieved document; never overwrites")
    get.add_argument("--provenance", help="Write a separate provenance JSON file")
    get.add_argument(
        "--normalize-updated-timestamps",
        action="store_true",
        help="Derive UTC dates from OpenMetadata millisecond timestamps; save the original and provenance",
    )
    get.add_argument(
        "--strict",
        choices=("true", "false"),
        default="true",
        help="Block invalid ODPS when true (default); allow it with findings when false",
    )
    get.add_argument("--json", action="store_true")
    create = actions.add_parser(
        "create", help="Review or explicitly create an ODPS product"
    )
    create.add_argument("connection")
    create.add_argument("--config", required=True)
    create.add_argument("--source", required=True, help="Local ODPS YAML source")
    create.add_argument(
        "--domain",
        required=True,
        help="Destination OpenMetadata domain FQN; quote multiword values",
    )
    create.add_argument("--language", default="en")
    create.add_argument(
        "--owner",
        action="append",
        dest="owners",
        help="Add an existing user:NAME or team:FQN; repeatable",
    )
    create.add_argument(
        "--no-owner",
        action="store_true",
        help="Do not assign the authenticated user by default",
    )
    create.add_argument(
        "--tag",
        action="append",
        dest="tags",
        help="Add an existing classification tag FQN; repeatable",
    )
    create.add_argument(
        "--execute", action="store_true", help="Execute a reviewed creation"
    )
    create.add_argument(
        "--reviewed-sha256", help="Digest from a previous create review"
    )
    create.add_argument("--json", action="store_true")
    recover = actions.add_parser(
        "recover-create",
        help="Find possible outcomes of an uncertain create (read-only)",
    )
    recover.add_argument("connection")
    recover.add_argument("--config", required=True)
    recover.add_argument("--source", required=True)
    recover.add_argument("--domain", required=True)
    recover.add_argument("--language", default="en")
    recover.add_argument("--max-pages", type=int, default=10)
    recover.add_argument("--json", action="store_true")
    contract = actions.add_parser(
        "contract-import", help="Review or import an ODCS contract for a data product"
    )
    contract.add_argument("connection")
    contract.add_argument("--config", required=True)
    contract.add_argument("--id", required=True, help="Target data product UUID")
    contract.add_argument("--source", required=True, help="Local ODCS YAML document")
    contract.add_argument(
        "--object-name", help="Explicit schema object name for multi-object contracts"
    )
    contract.add_argument("--execute", action="store_true")
    contract.add_argument("--reviewed-sha256")
    contract.add_argument("--json", action="store_true")
    contract_get = actions.add_parser(
        "contract-get", help="Retrieve a data product's effective contract"
    )
    contract_get.add_argument("connection")
    contract_get.add_argument("--config", required=True)
    contract_get.add_argument("--id", required=True, help="Target data product UUID")
    contract_get.add_argument("--json", action="store_true")
    contract_source = actions.add_parser(
        "contract-source", help="Save the original SDK-preserved ODCS contract"
    )
    contract_source.add_argument("connection")
    contract_source.add_argument("--config", required=True)
    contract_source.add_argument("--id", required=True)
    contract_source.add_argument("--output", required=True)
    contract_source.add_argument("--json", action="store_true")
    delete = actions.add_parser("delete", help="Review or permanently delete a product")
    delete.add_argument("connection")
    delete.add_argument("--config", required=True)
    delete.add_argument("--id", required=True, help="Platform product UUID")
    delete.add_argument(
        "--execute", action="store_true", help="Execute a reviewed deletion"
    )
    delete.add_argument(
        "--reviewed-sha256", help="Digest from a previous deletion review"
    )
    delete.add_argument(
        "--confirm-permanent",
        action="store_true",
        help="Acknowledge permanent, recursive deletion",
    )
    delete.add_argument("--json", action="store_true")
    update = actions.add_parser(
        "update", help="Review or update a product's title, description or domain"
    )
    update.add_argument("connection")
    update.add_argument("--config", required=True)
    update.add_argument("--id", required=True, help="Platform product UUID")
    update.add_argument("--title")
    update.add_argument(
        "--input", "-i", help="ODPS YAML or JSON file to review for this update"
    )
    update.add_argument("--description")
    update.add_argument(
        "--owner",
        action="append",
        dest="owners",
        help="Add an existing user:NAME or team:FQN; repeatable",
    )
    update.add_argument(
        "--tag",
        action="append",
        dest="tags",
        help="Add an existing classification tag FQN; repeatable",
    )
    update.add_argument(
        "--domain", help="Replace existing domains with this domain FQN"
    )
    update.add_argument("--execute", action="store_true")
    update.add_argument(
        "--reviewed-sha256", help="Digest from a previous update review"
    )
    update.add_argument("--json", action="store_true")


def _save_output_set(files: List[Tuple[Path, str]]) -> None:
    """Stage output files and roll back files created by a failed save."""
    staged = []
    published = []
    remaining = []
    failed = False
    interrupted = False
    try:
        for target, data in files:
            fd, name = tempfile.mkstemp(prefix=".odps-", dir=str(target.parent))
            staged.append(Path(name))
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
        for (target, _), temporary in zip(files, staged):
            stat = temporary.stat()
            os.link(str(temporary), str(target))
            published.append((target, stat.st_dev, stat.st_ino))
    except (OSError, UnicodeError, KeyboardInterrupt) as exc:
        failed = True
        interrupted = isinstance(exc, KeyboardInterrupt)
        for target, device, inode in reversed(published):
            try:
                stat = target.stat()
                if (stat.st_dev, stat.st_ino) == (device, inode):
                    target.unlink()
                else:
                    remaining.append(target.name)
            except FileNotFoundError:
                pass
            except OSError:
                remaining.append(target.name)
    finally:
        for temporary in staged:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                remaining.append(temporary.name)
    if interrupted and not remaining:
        raise KeyboardInterrupt
    if failed or remaining:
        suffix = (
            "; files requiring inspection: " + ", ".join(remaining) if remaining else ""
        )
        message = (
            "Unable to save the complete output set"
            if failed
            else "Output was saved but temporary files could not be removed"
        )
        raise IntegrationError(message + suffix) from None


def handle_integrations(args: argparse.Namespace) -> int:
    """Execute an integration command and return its exit status."""
    try:
        config = load_integration_config(args.config)
        if args.integration_command == "list":
            profiles = [
                {"name": p.name, "platform": p.platform, "read_only": p.read_only}
                for p in config.connections.values()
            ]
            print(
                json.dumps(profiles, indent=2)
                if args.json
                else "\n".join(
                    p.name + "\t" + p.platform for p in config.connections.values()
                )
            )
            return 0
        payload: Dict[str, object]
        with OpenMetadataAdapter(config.select(args.connection)) as adapter:
            if args.integration_command == "check":
                payload = dict(adapter.check_connection())
            elif args.integration_command == "discover":
                payload = adapter.discover_context(
                    product_id=args.id, query=args.query, limit=args.limit
                )
            elif args.integration_command == "domains":
                page = adapter.list_domains(limit=args.limit, after=args.after)
                payload = {
                    "domains": page.products,
                    "after": page.after,
                    "provenance": asdict(page.provenance),
                }
            elif args.integration_command == "domain-create":
                kwargs = {
                    "name": args.name,
                    "description": args.description,
                    "domain_type": args.type,
                    "display_name": args.display_name,
                    "parent": args.parent,
                }
                if args.execute:
                    if not args.reviewed_sha256:
                        raise IntegrationError(
                            "Execution requires --reviewed-sha256 from a prior review"
                        )
                    domain_result = adapter.create_domain(
                        **kwargs, reviewed_sha256=args.reviewed_sha256
                    )
                    print(json.dumps(domain_result.to_dict(), indent=2))
                    return 0 if domain_result.status == "created" else 1
                domain_review = adapter.review_domain_create(**kwargs)
                print(json.dumps(domain_review.to_dict(), indent=2))
                return 0
            elif args.integration_action == "list":
                payload = adapter.list_products_odpc(
                    page_size=args.limit, after=args.after
                )
            elif args.integration_action == "search":
                payload = adapter.search_products_odpc(
                    args.query, offset=args.offset, limit=args.limit
                )
            elif args.integration_action == "compare":
                try:
                    product_id = str(UUID(args.id))
                except (ValueError, TypeError, AttributeError):
                    raise IntegrationError(
                        "A valid product UUID is required; names are not accepted"
                    ) from None
                source = Path(args.source).read_text(encoding="utf-8")
                comparison = adapter.compare_product(
                    source,
                    product_id=product_id,
                    domain=args.domain,
                    language=args.language,
                )
                payload = comparison.to_dict()
                if args.output:
                    _save_output_set(
                        [(Path(args.output), json.dumps(payload, indent=2) + "\n")]
                    )
                print(json.dumps(payload, indent=2))
                return 0 if comparison.source_validation.valid else 1
            elif args.integration_action == "create":
                source = Path(args.source).read_text(encoding="utf-8")
                if args.no_owner and args.owners:
                    raise IntegrationError("--no-owner cannot be combined with --owner")
                selected_owners = [] if args.no_owner else args.owners
                if args.execute:
                    if not args.reviewed_sha256:
                        raise IntegrationError(
                            "Execution requires --reviewed-sha256 from a prior review"
                        )
                    creation_result = adapter.create_product(
                        source,
                        domain=args.domain,
                        language=args.language,
                        reviewed_sha256=args.reviewed_sha256,
                        source_path=args.source,
                        owners=selected_owners,
                        tags=args.tags,
                    )
                    print(json.dumps(creation_result.to_dict(), indent=2))
                    return 0 if creation_result.status == "created" else 1
                review = adapter.review_create(
                    source,
                    domain=args.domain,
                    language=args.language,
                    source_path=args.source,
                    owners=selected_owners,
                    tags=args.tags,
                )
                print(json.dumps(review.to_dict(), indent=2))
                return 0 if review.compatible else 1
            elif args.integration_action == "recover-create":
                source = Path(args.source).read_text(encoding="utf-8")
                recovery_result = adapter.find_create_candidates(
                    source,
                    domain=args.domain,
                    language=args.language,
                    max_pages=args.max_pages,
                    source_path=args.source,
                )
                print(json.dumps(recovery_result, indent=2))
                return 0 if recovery_result["complete"] else 1
            elif args.integration_action == "contract-import":
                source = Path(args.source).read_text(encoding="utf-8")
                if args.execute:
                    if not args.reviewed_sha256:
                        raise IntegrationError(
                            "Execution requires --reviewed-sha256 from a prior review"
                        )
                    import_result = adapter.import_contract(
                        source,
                        product_id=args.id,
                        object_name=args.object_name,
                        reviewed_sha256=args.reviewed_sha256,
                    )
                    print(json.dumps(import_result.to_dict(), indent=2))
                    return 0 if import_result.status == "created" else 1
                contract_review = adapter.review_contract_import(
                    source, product_id=args.id, object_name=args.object_name
                )
                print(json.dumps(contract_review.to_dict(), indent=2))
                report = contract_review.validation.get("odcsImportReport")
                return (
                    0
                    if contract_review.validation.get("valid") is True
                    and isinstance(report, dict)
                    and report.get("canImport") is True
                    else 1
                )
            elif args.integration_action == "contract-get":
                payload = adapter.get_contract_for_product(args.id)
            elif args.integration_action == "contract-source":
                source_result = adapter.get_preserved_contract_source(args.id)
                _save_output_set([(Path(args.output), source_result["yaml"])])
                payload = {
                    key: value for key, value in source_result.items() if key != "yaml"
                }
                payload["saved"] = True
            elif args.integration_action == "delete":
                if args.execute:
                    if not args.reviewed_sha256:
                        raise IntegrationError(
                            "Execution requires --reviewed-sha256 from a prior review"
                        )
                    deletion_result = adapter.delete_product(
                        args.id,
                        reviewed_sha256=args.reviewed_sha256,
                        confirm_permanent=args.confirm_permanent,
                    )
                    print(json.dumps(deletion_result.to_dict(), indent=2))
                    return 0 if deletion_result.verification == "not_found_by_id" else 1
                delete_review = adapter.review_delete(args.id)
                print(json.dumps(delete_review.to_dict(), indent=2))
                return 0
            elif args.integration_action == "update":
                source_yaml = None
                if args.input:
                    from .update import _read_update_source

                    source_yaml = _read_update_source(args.input)
                if args.execute:
                    if not args.reviewed_sha256:
                        raise IntegrationError(
                            "Execution requires --reviewed-sha256 from a prior review"
                        )
                    update_result = adapter.update_product(
                        args.id,
                        title=args.title,
                        description=args.description,
                        domain=args.domain,
                        owners=args.owners,
                        tags=args.tags,
                        source_yaml=source_yaml,
                        reviewed_sha256=args.reviewed_sha256,
                    )
                    print(json.dumps(update_result.to_dict(), indent=2))
                    return (
                        0
                        if all(
                            value == "matched"
                            for value in update_result.comparison.values()
                        )
                        else 1
                    )
                update_review = adapter.review_update(
                    args.id,
                    title=args.title,
                    description=args.description,
                    domain=args.domain,
                    owners=args.owners,
                    tags=args.tags,
                    source_yaml=source_yaml,
                )
                print(json.dumps(update_review.to_dict(), indent=2))
                return 0
            else:
                try:
                    product_id = str(UUID(args.id))
                except (ValueError, TypeError, AttributeError):
                    raise IntegrationError(
                        "A valid product UUID is required; names are not accepted"
                    ) from None
                if args.include_extensions and args.format != "native":
                    raise IntegrationError(
                        "--include-extensions requires native format"
                    )
                if args.include_domains and args.format != "native":
                    raise IntegrationError("--include-domains requires native format")
                if args.provenance and not args.output:
                    raise IntegrationError("--provenance requires --output")
                if args.normalize_updated_timestamps and (
                    args.format != "odps" or not args.output or not args.provenance
                ):
                    raise IntegrationError(
                        "Timestamp normalization requires ODPS format, --output and --provenance"
                    )
                result = (
                    adapter.export_odps(product_id)
                    if args.format == "odps"
                    else adapter.get_product(
                        product_id,
                        include_extensions=args.include_extensions,
                        include_domains=args.include_domains,
                    )
                )
                normalized = (
                    normalize_openmetadata_updated_dates(result.data)
                    if args.normalize_updated_timestamps
                    and isinstance(result.data, str)
                    else None
                )
                validation_result = (
                    normalized.validation if normalized else result.validation
                )
                validation = (
                    validation_result.to_dict()
                    if validation_result is not None
                    else None
                )
                valid = validation is None or validation["valid"]
                strict = args.strict == "true"
                warnings = list(result.warnings)
                if not valid and not strict:
                    warnings.append("Validation failed; strict mode is disabled")
                payload = {
                    "provenance": asdict(result.provenance),
                    "validation": validation,
                    "warnings": warnings,
                    "saved": False,
                    "strict": strict,
                }
                if normalized:
                    payload["timestamp_normalizations"] = [
                        asdict(change) for change in normalized.changes
                    ]
                    warnings.append(
                        "Derived UTC dates lose time precision; the original export and timestamps are retained"
                    )
                if args.output and (valid or not strict):
                    findings_path = (
                        args.output + ".validation.json" if not valid else None
                    )
                    original_path = (
                        args.output + ".original.yaml" if normalized else None
                    )
                    paths = [
                        Path(p)
                        for p in (
                            args.output,
                            args.provenance,
                            findings_path,
                            original_path,
                        )
                        if p
                    ]
                    if len({str(p.resolve()) for p in paths}) != len(paths) or any(
                        p.exists() for p in paths
                    ):
                        raise IntegrationError(
                            "Output paths must be distinct and must not already exist"
                        )
                    body = (
                        normalized.normalized_yaml
                        if normalized
                        else (
                            result.data
                            if isinstance(result.data, str)
                            else json.dumps(result.data, indent=2) + "\n"
                        )
                    )
                    files = []
                    if original_path and normalized:
                        files.append((Path(original_path), normalized.original_yaml))
                    if findings_path:
                        files.append(
                            (
                                Path(findings_path),
                                json.dumps(validation, indent=2) + "\n",
                            )
                        )
                    files.append((Path(args.output), body))
                    if args.provenance:
                        provenance = asdict(result.provenance)
                        if normalized:
                            provenance["timestamp_normalizations"] = [
                                asdict(change) for change in normalized.changes
                            ]
                        files.append(
                            (
                                Path(args.provenance),
                                json.dumps(provenance, indent=2) + "\n",
                            )
                        )
                    _save_output_set(files)
                    payload["saved"] = True
                elif args.output and not valid:
                    payload["message"] = (
                        "Validation failed; strict mode blocked saving the document"
                    )
                if not args.output and args.format == "native":
                    payload["data"] = result.data
                elif not args.output and args.format == "odps":
                    payload["message"] = "Use --output to save the ODPS document"
                print(json.dumps(payload, indent=2))
                return 0 if valid or not strict else 1
        print(json.dumps(payload, indent=2))
        return 0
    except (IntegrationError, OSError, UnicodeError) as exc:
        # File and network exceptions can include sensitive paths or response content.
        message = (
            str(exc)
            if isinstance(exc, IntegrationError)
            else "Unable to read or write a local file"
        )
        print(message, file=sys.stderr)
        return 1
