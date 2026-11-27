# Synthetic business-to-marketplace-to-Jira timing benchmark

This development harness measures a complete, sequential workflow from each
fictional Markdown business brief through fresh LLM generation, OpenMetadata
product creation and search verification, metadata discovery, OpenSpec/ODPS/ODCS
validation, ODCS contract association and discovery readback, Jira creation and
attachment hash readback. It does not reuse generated
ODPS drafts, packages or existing products. Each case receives a unique synthetic
product identity. The source brief is copied and its test-only identity is changed;
the original file is not modified. A fictional-test label is added to the generated
ODPS description before the reviewed OpenMetadata write.

Use only a test installation and explicitly fictional input. Configure the existing
`generation.config.yaml`, `.env` and named `connections.yaml` entries, with a writable
OpenMetadata 2.1.0 profile, an existing test domain and a Jira test project and issue
type. The SDK's OpenSpec CLI and datacontract-cli validation tools must be available.
Credentials are resolved by the SDK from the environment and are never written into
reports. See the handover and OpenMetadata guides for configuration.

Preview one case or all Markdown documents in a directory without running a model or
creating external data:

```sh
python3 -m examples.integrations.handoff_timing_benchmark \
  --input tests/fixtures/openmetadata_banking_poc/sources/product-holdings.md \
  --output /tmp/odp-benchmark-example --domain Banking
```

To run the six synthetic banking briefs sequentially, add `--execute` and use an
unused output directory:

```sh
python3 -m examples.integrations.handoff_timing_benchmark \
  --input tests/fixtures/openmetadata_banking_poc/sources/ \
  --output /tmp/odp-benchmark-six --domain Banking --execute
```

Execution creates one new OpenMetadata product, associates the generated ODCS
draft with it, and creates one Jira issue for each successful case. Product and
contract creation are separate writes; a failure can leave the product in place.
The ODCS schema is integrity-checked as preserved source, not validated by
OpenMetadata. Results remain in those systems; the harness never deletes them. It uses the
SDK's review digests, rejects changed inputs and duplicate candidates, and records
local journals. On an incomplete or uncertain write, it stops and requires inspection
before another run. Do not blindly retry an uncertain create.

The output directory contains a plan, per-case reviews and results, source hashes,
contract reviews and verification, catalog snapshots and Jira journals, plus `benchmark-results.json` and
`benchmark-results.md`. The initial catalog snapshot is captured before the generated
contract exists and can report its lookup as unavailable. The subsequent
`contract_verification` result records the post-import discovery and source hash. Each case records distinct wall-clock phase timings, total
elapsed time, product and issue IDs, structural validation and readback outcomes.
The total includes preflight, MCP startup, model calls, OpenMetadata requests and
indexing waits, package construction, validation, Jira attachment upload and hash
verification, and process cleanup. Programmatic digest-bound reviews are authorized
by the explicit synthetic benchmark execution; human review waiting time is not
measured. Results are not production throughput or an approval of generated content.

The average uses only fully successful cases. A pass/fail against 60 seconds is
reported only if every planned case completes successfully; failed, unknown and
unrun cases cannot be treated as zero-duration successes. Listing and search are
verified for the configured account. The SDK does not import ODPS lifecycle status,
so marketplace UI publication and availability to other users are not established
by the benchmark.
