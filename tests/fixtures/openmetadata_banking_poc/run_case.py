"""Review or explicitly create the six persistent banking PoC products via CLI."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parent
PRODUCTS = (
    "campaign-eligibility",
    "customer-lifetime-value",
    "customer-vulnerability-profile",
    "financial-crime-risk-profile",
    "payment-delinquency-forecast",
    "product-holdings",
)


def cli(*arguments):
    """Run the SDK CLI and parse its JSON result."""
    process = subprocess.run(
        [sys.executable, "-m", "open_data_products.cli", *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(process.stdout)
    except ValueError:
        raise RuntimeError(
            process.stderr.strip() or "SDK command returned invalid JSON"
        ) from None
    return process.returncode, payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument(
        "--owner",
        action="append",
        default=[],
        help="Existing user:NAME or team:FQN; repeatable",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Existing classification tag FQN; repeatable",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Create products permanently; none are deleted",
    )
    parser.add_argument(
        "--compare-existing",
        action="store_true",
        help="Compare existing products without creating them",
    )
    parser.add_argument(
        "--comparison-output", help="Save the comparison report as a new JSON file"
    )
    parser.add_argument(
        "--results-output", help="Save creation results to a new JSON file"
    )
    args = parser.parse_args()
    if args.execute and args.compare_existing:
        raise RuntimeError("--execute and --compare-existing cannot be combined")
    common = ("--config", args.config)
    if args.compare_existing:
        reports = []
        for name in PRODUCTS:
            source = ROOT / "products" / ("odps_product_" + name + ".yaml")
            status, candidates = cli(
                "integrations",
                "products",
                "recover-create",
                args.profile,
                *common,
                "--source",
                str(source),
                "--domain",
                args.domain,
                "--json",
            )
            if (
                status
                or not candidates.get("complete")
                or len(candidates.get("candidates", [])) != 1
            ):
                raise RuntimeError("Product lookup was missing or ambiguous: " + name)
            product_id = candidates["candidates"][0]["id"]
            status, report = cli(
                "integrations",
                "products",
                "compare",
                args.profile,
                *common,
                "--source",
                str(source),
                "--id",
                product_id,
                "--domain",
                args.domain,
                "--json",
            )
            if status:
                raise RuntimeError("Source comparison failed for " + name)
            reports.append(report)
        rendered = json.dumps(reports, indent=2) + "\n"
        if args.comparison_output:
            with Path(args.comparison_output).open("x", encoding="utf-8") as handle:
                handle.write(rendered)
        else:
            print(rendered, end="")
        return
    if args.comparison_output:
        raise RuntimeError("--comparison-output requires --compare-existing")
    reviews = {}
    for name in PRODUCTS:
        source = ROOT / "products" / ("odps_product_" + name + ".yaml")
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
        original = yaml.safe_load(
            (ROOT / "sources" / (name + ".md"))
            .read_text(encoding="utf-8")
            .split("---", 2)[1]
        )
        details = document["product"]["details"]["en"]
        if (
            details["productID"] != name
            or details["name"] != original["product_name"]
            or details["visibility"] != "private"
            or details["status"] != "draft"
            or document["version"] != "4.1"
        ):
            raise RuntimeError("Draft identity or safety fields differ for " + name)
        command = (
            "integrations",
            "products",
            "create",
            args.profile,
            *common,
            "--source",
            str(source),
            "--domain",
            args.domain,
            *(argument for owner in args.owner for argument in ("--owner", owner)),
            *(argument for tag in args.tag for argument in ("--tag", tag)),
            "--json",
        )
        status, review = cli(*command)
        if status or not review.get("executable"):
            raise RuntimeError(
                "Create review failed for " + name + ": " + json.dumps(review)
            )
        status, candidates = cli(
            "integrations",
            "products",
            "recover-create",
            args.profile,
            *common,
            "--source",
            str(source),
            "--domain",
            args.domain,
            "--json",
        )
        if status or not candidates.get("complete") or candidates.get("candidates"):
            raise RuntimeError(
                "Existing or uncertain candidates for "
                + name
                + ": "
                + json.dumps(candidates)
            )
        source_sha256 = hashlib.sha256(
            source.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        reviews[name] = (source, command, review["review_sha256"], source_sha256)
    print("All six drafts validated and no existing candidates were found.", flush=True)
    if not args.execute:
        return
    records = []
    result_file = (
        Path(args.results_output)
        if args.results_output
        else ROOT / "live-results.local.json"
    )
    if result_file.exists():
        raise RuntimeError(
            "Local results already exist; inspect them before another creation run"
        )
    for name in PRODUCTS:
        source, command, digest, source_sha256 = reviews[name]
        status, candidates = cli(
            "integrations",
            "products",
            "recover-create",
            args.profile,
            *common,
            "--source",
            str(source),
            "--domain",
            args.domain,
            "--json",
        )
        if status or not candidates.get("complete") or candidates.get("candidates"):
            raise RuntimeError(
                "Existing or uncertain candidates before creation: " + name
            )
        records.append({"source_product_id": name, "status": "create_attempt_pending"})
        result_file.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        status, result = cli(*command, "--execute", "--reviewed-sha256", digest)
        records[-1]["result"] = result
        records[-1]["status"] = "create_returned"
        result_file.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        print("Created", name, "status:", result.get("status"), flush=True)
        if status or result.get("status") != "created":
            raise RuntimeError(
                "Creation needs inspection; see local results before retrying: " + name
            )
        platform_id = result["product_id"]
        status, native = cli(
            "integrations",
            "products",
            "get",
            args.profile,
            *common,
            "--id",
            platform_id,
            "--format",
            "native",
            "--json",
        )
        if (
            status
            or native.get("data", {}).get("name") != name
            or native["data"].get("visibility") != "PRIVATE"
        ):
            raise RuntimeError("Native retrieval did not verify " + name)
        status, comparison = cli(
            "integrations",
            "products",
            "compare",
            args.profile,
            *common,
            "--source",
            str(source),
            "--id",
            platform_id,
            "--domain",
            args.domain,
            "--json",
        )
        if status:
            raise RuntimeError("Source comparison failed for " + name)
        if comparison.get("source_sha256") != source_sha256:
            raise RuntimeError(
                "Source changed after review; comparison is not bound to the reviewed draft: "
                + name
            )
        records[-1]["comparison"] = comparison
        result_file.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        status, listing = cli(
            "integrations",
            "products",
            "recover-create",
            args.profile,
            *common,
            "--source",
            str(source),
            "--domain",
            args.domain,
            "--json",
        )
        if status or not any(
            item.get("id") == platform_id for item in listing.get("candidates", [])
        ):
            raise RuntimeError("Listing did not verify " + name)
        deadline = time.monotonic() + 45
        while True:
            status, found = cli(
                "integrations",
                "products",
                "search",
                args.profile,
                *common,
                "--query",
                name,
                "--limit",
                "100",
                "--json",
            )
            if status:
                raise RuntimeError("Search failed after creating " + name)
            references = found.get("catalog", {}).get("productReferences", [])
            if any(item.get("id") == platform_id for item in references):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Product not found in search before timeout: " + name
                )
            time.sleep(1)
        records[-1]["verified"] = ["native", "listing", "search"]
        result_file.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        print("Verified retrieval, listing and search:", name, flush=True)


if __name__ == "__main__":
    main()
