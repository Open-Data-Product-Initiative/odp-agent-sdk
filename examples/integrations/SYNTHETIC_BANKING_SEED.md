# Synthetic banking metadata seed

This workflow creates OpenMetadata entities only. It does not create physical
infrastructure, ingest data, upload sample rows, or verify a database connection.
It uses the six unchanged banking briefs and ODPS drafts under
`tests/fixtures/openmetadata_banking_poc/`. Its synthetic service and entity names
are stable. The existing `SDKIntegrationTest` domain is referenced, never deleted.

Review against OpenMetadata 2.1.0 with a configured SDK connection. The optional
`--env-file` reads only the environment variable referenced by the connection;
it does not execute the file as shell code or print the credential.

```sh
python3 -m examples.integrations.synthetic_banking_seed review \
  --config examples/integrations/connections.yaml --env-file .env
```

The preview includes exact create payloads, a schema-bearing synthetic ODCS
source, proposed lineage, permissions, a destination-bound digest, and warnings.
The server must accept metadata-only `CustomDatabase` services; the existence of
a service does not verify a physical connection. Existing names or denied or
unknown permissions block the review. This is a non-atomic conflict check; POST
creation does not overwrite existing entities.

After explicitly reviewing and approving the preview:

```sh
python3 -m examples.integrations.synthetic_banking_seed execute \
  --config examples/integrations/connections.yaml --env-file .env \
  --reviewed-sha256 REVIEW_DIGEST --confirm --manifest "$HOME/.local/share/open-data-products/synthetic-banking/seed-manifest.json"
```

The manifest path must not already exist. It records each confirmed ID and
relationship and the operation pending before each request. An unknown outcome
stops the run; inspect the platform and manifest before any retry. The preserved
ODCS source is not validated by OpenMetadata as a native product schema. Its
required and unique fields are draft quality expectations, not executed tests.

Cleanup is an independent operation requiring another review and confirmation:

```sh
python3 -m examples.integrations.synthetic_banking_seed cleanup-review \
  --config examples/integrations/connections.yaml --env-file .env \
  --manifest "$HOME/.local/share/open-data-products/synthetic-banking/seed-manifest.json"
python3 -m examples.integrations.synthetic_banking_seed cleanup-execute \
  --config examples/integrations/connections.yaml --env-file .env \
  --manifest "$HOME/.local/share/open-data-products/synthetic-banking/seed-manifest.json" --reviewed-sha256 CLEANUP_DIGEST --confirm
```

Cleanup examines only confirmed manifest records, checks their identity and
namespace, removes recorded lineage individually, and uses non-recursive soft
entity deletion. It refuses unknown or ongoing seed outcomes. There is no atomic
revision precondition for all cleanup operations, so examine dependencies and
perform cleanup promptly after review. The manifest is local and should be
protected from editing; preserve it for verification and recovery.

## Resume the reviewed VARCHAR correction

OpenMetadata 2.1.0 rejected the first table because `VARCHAR` columns require
`dataLength`. The supported resume path applies only to that confirmed HTTP 400
state: it checks the original review and manifest, verifies the nine recorded
entities by ID, checks that planned tables and the contract are absent, and
permits only the addition of `dataLength: 255` to VARCHAR columns. Unknown
outcomes cannot use this resume path.

```sh
python3 -m examples.integrations.synthetic_banking_seed resume-review \
  --config examples/integrations/connections.yaml --env-file .env \
  --manifest "$HOME/.local/share/open-data-products/synthetic-banking/seed-manifest.json" \
  --original-review /tmp/odps-banking-seed-review.json
# After an explicit review and confirmation:
python3 -m examples.integrations.synthetic_banking_seed resume \
  --config examples/integrations/connections.yaml --env-file .env \
  --manifest "$HOME/.local/share/open-data-products/synthetic-banking/seed-manifest.json" \
  --original-review /tmp/odps-banking-seed-review.json \
  --reviewed-sha256 RESUME_DIGEST --confirm
```

## Resume the reviewed domain correction

A second confirmed HTTP 400 showed that the installation requires table and
product domains to match. `domain-resume-review` is limited to this recorded
partial state. It verifies both preceding reviews and all recorded entity IDs,
and allows only `domains: [SDKIntegrationTest]` on the seven table requests.
Execute `domain-resume` only after reviewing the new digest and giving explicit
confirmation. Supply `--manifest`, `--original-review`, `--previous-review`,
`--reviewed-sha256`, and `--confirm` as appropriate.

## Move the synthetic catalog to Banking

The `synthetic_banking_domain` workflow operates only on the sixteen service,
database, schema, table and product IDs recorded in a completed seed manifest.
Review validates that the synthetic hierarchy has no unrecorded children, that
all twenty product–asset links belong to the seed, and that the three recorded
lineage edges and preserved contract still exist. It uses the server's
`dryRun: true` domain bulk API and includes its warnings in the digest-bound
review. The server warns that moving the tables may remove product links.

```sh
python3 -m examples.integrations.synthetic_banking_domain review \
  --config examples/integrations/connections.yaml --env-file .env \
  --seed-manifest "$HOME/.local/share/open-data-products/synthetic-banking/seed-manifest.json"
```

After explicit approval, execute with `--reviewed-sha256`, `--confirm`, and a new
`--migration-manifest` path. The workflow rechecks the review, moves the sixteen
entities to Banking, restores any missing original synthetic product links, and
verifies domains, links, lineage and the preserved contract digest. The move is
not atomic: partial or unknown outcomes stop the workflow and require inspection
of its journal. It never automatically retries an unknown write.

## Split source and curated metadata

The `synthetic_banking_split` workflow keeps the original seven table IDs and
product links in the existing service, designating that service as curated
analytics. It creates three metadata-only source services for customer and
consent, core banking, and payments, with seven source table definitions copied
from the curated column metadata. Seven new source-to-curated lineage edges are
test descriptions; they do not represent verified pipelines or physical data.
All new entities belong to Banking.

```sh
python3 -m examples.integrations.synthetic_banking_split review \
  --config examples/integrations/connections.yaml --env-file .env \
  --seed-manifest "$HOME/.local/share/open-data-products/synthetic-banking/seed-manifest.json"
```

The review checks the existing graph, permissions, names and revisions and
shows every source payload and lineage edge. It also proposes a guarded change
to the existing service description so its curated role is visible. After
explicit approval, run `execute` with a new `--split-manifest` path, the
`--reviewed-sha256` value and `--confirm`. It stops on partial or unknown
outcomes, records confirmed IDs, and verifies source schemas, lineage and the
original product links and contract.

`cleanup-review` and `cleanup-execute` use the same seed manifest and the split
manifest. Cleanup affects only the split-created source entities and lineage;
it restores the curated service description only when still unchanged. It
refuses unrecorded children, product links or lineage and uses non-recursive
soft deletion. Review and confirm cleanup independently. Clean the split first:
the original seed cleanup refuses the added source lineage until it is removed.
