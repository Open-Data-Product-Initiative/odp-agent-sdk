# Platform integrations: OpenMetadata

The first adapter provides connection checks, ODPC catalog listing, search and
export, native product retrieval, ODPS YAML export, and experimental reviewed
creation and permanent deletion.
On 2026-11-25, the
deployment owner reported a successful connection check and product-list request
from their own shell. A direct version request returned OpenMetadata **2.1.0**.
On that deployment, the SDK also listed and retrieved a non-sensitive test
product and obtained an ODPS 4.1 YAML export. The export failed SDK validation:
required product detail fields were missing or invalid, and `updated` was a
number rather than a string. This is evidence for that product, not a claim
about all exports or OpenMetadata versions. A successful empty list
does not establish that the export endpoint exists or that products are absent
for every identity. Imported metadata is source-declared, not approval or an
independent verification of business facts.

## Configuration

### Workspace shortcuts

Choose a connection once per working directory. This checks connectivity and
stores the config path and profile name in the ignored
`.open-data-products/integrations.yaml`; no credential is stored there.

```sh
open-data-products config integrations --copy-to connections.yaml
# Edit the copied file's base_url and set OPENMETADATA_TOKEN in your environment.
open-data-products connect openmetadata --config connections.yaml
open-data-products openmetadata products list
open-data-products openmetadata products search "campaign"
open-data-products openmetadata products export --output catalog.yaml
open-data-products openmetadata products get --id PRODUCT_UUID
open-data-products openmetadata products compare --id PRODUCT_UUID --source product.yaml
open-data-products openmetadata products create product.yaml --domain "Retail Banking"
open-data-products openmetadata products create ./products --domain "Retail Banking"
open-data-products openmetadata products update --id PRODUCT_UUID --input product.yaml
open-data-products openmetadata products delete --id PRODUCT_UUID
```

`--config` and `--connection` override the saved selection. Supplying a
different `--config` without `--connection` uses that config's default.
The `openmetadata` command requires the selected connection to be an
OpenMetadata connection. Earlier `openmetadata create` and `products create`
shortcuts remain available for compatibility.
Retrieval and comparison require a product UUID; names cannot identify their
targets. List and search catalogs include UUIDs. A comparison infers the domain only
when the retrieved product has exactly one; use `--domain` otherwise.

Guided creation discovers `.yaml`, `.yml`, and `.json` files recursively in
sorted order. It reviews all files and performs a duplicate check, then asks
once before creating eligible products. Invalid files, duplicates, and
incomplete duplicate checks are skipped. Duplicate detection depends on
platform visibility and cannot prevent concurrent creations. The SDK rereads
each file, rechecks for duplicates, and uses the source-bound review digest
for each execution. A failed or uncertain write is reported without a retry;
inspect the destination before trying again. The created records remain in the
platform. `--owner` and `--tag` may be repeated for explicit assignments.

The short creation command never writes without a terminal confirmation.
With `--json`, or when there is no interactive terminal, it returns a structured
or readable review-only report and a nonzero status. Scripts must use the
existing `integrations products create` review and `--execute
--reviewed-sha256` commands for explicit execution. Other short commands accept
`--json` for structured output. CLI product list and search now return ODPC
catalogs, including in the existing integration commands; this changes their
earlier native JSON result shape. The Python adapter's `list_products` and
`search_products` methods continue to return native paginated results.

The update command accepts `--input` with an ODPS YAML or JSON file, as well as
`--title`, `--description`, `--domain`, `--owner` and `--tag`. The input's
English `productID` must match the target's OpenMetadata name. The SDK validates
the document, maps its English name to the title and its description (or value
proposition when no description is present) to the description, and lists the
other source fields that will not be applied. Contracts and other ODPS fields
are not updated by this operation. Explicit title and description options
override the corresponding source values. The review digest binds the source
file and target revision; changed inputs require a new review. `--owner` and `--tag`
add to existing assignments, while `--domain` replaces the existing domains.
For example:

```sh
open-data-products openmetadata products update --id PRODUCT_UUID \
  --title "New title" --description "New description" \
  --domain "Retail Banking" --owner user:USERNAME --tag Classification.ExistingTag
```

Use the domain's exact `fullyQualifiedName` from `integrations domains`. Quote
multiword values; an OpenMetadata display name may differ from its FQN. Domain
changes may affect associated assets and relationships, as noted in the review.
The owner and tag must already exist in OpenMetadata.

Update and delete require `--id` with a product UUID; names cannot identify
their targets. In an interactive terminal they show a fresh review and ask
for confirmation. Deletion is permanent and recursive. In non-interactive
use the commands return a review without writing. For scripted execution,
repeat the command with `--execute --reviewed-sha256 REVIEW_SHA256`; deletion
also requires `--confirm-permanent`. The existing review, revision checks and
write-enabled connection requirements remain in force.

### ODPC catalog list, search and export

Both CLI list and search return a validated ODPC 1.0 `Catalog` whose
`productReferences` represent OpenMetadata products. The `export` command
saves the full listing as a new `.yaml`, `.yml`, or `.json` file and does not
overwrite an existing file:

```sh
open-data-products openmetadata products export --output catalog.yaml
open-data-products validate catalog.yaml --json
```

The adapter exposes `list_products_odpc()` and `search_products_odpc()` for
Python callers. The catalog points to native OpenMetadata product API records;
it is not an assertion that OpenMetadata exported a valid ODPS document. The
OpenMetadata metadata revision is mapped to ODPC `productVersion` by design and
marked with `x-productVersion-source`. It is not independently verified as a
product release version. OpenMetadata names and descriptions are not
language-tagged; they are mapped to the schema's required `en` field without
translation and labelled by `x-language-mapping`. Missing descriptions use an
explicitly labelled placeholder.

Listing follows all pages, subject to the adapter's page limit, and rejects
incomplete pagination. Search returns one page; `--offset` and `--limit`
select pages, with the total, next offset and index-lag warnings recorded in
`catalog.metadata.x-source`. Each result is retrieved by UUID to map its
current native metadata. Neither listing nor search is an atomic snapshot.
Catalog validation establishes schema conformance, not business approval or
the validity of the underlying data or contract.

Use `open-data-products config integrations --copy-to connections.yaml` to copy
the packaged example to a user-owned file. Edit that copy; do not edit the
installed template. Replace the base URL with the deployment URL, retaining any deployment path
prefix. Both a root URL and a URL ending in `/api` are accepted. A plain HTTP
URL requires `http.allow_insecure_http: true`; bearer tokens sent over HTTP are
not encrypted. TLS verification is on by default. For a private CA set
`http.ca_bundle` to its PEM file; disabling `verify_tls` is for development
only. Never commit a private URL, token, or customer metadata. Named profiles
can use different URLs and credentials. No network requests or credential
resolution occur when the configuration is loaded. The recommended configuration
references `OPENMETADATA_TOKEN` in the process environment, exactly as the
generation provider references `OPENAI_API_KEY`. The SDK does not load `.env`
files automatically.

For local use, copy `.env.example` to `.env`, replace the placeholder in a
private editor, and keep `.env` out of version control. On POSIX systems,
restrict access with `chmod 600 .env`. Then load the simple `KEY=value` file
into each shell session before running the SDK:

```sh
set -a
. ./.env
set +a
```

On Windows PowerShell, for a file containing simple unquoted `KEY=value` lines:

```powershell
Get-Content .env | Where-Object { $_ -match '^[A-Za-z_][A-Za-z0-9_]*=' } | ForEach-Object {
  $name, $value = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($name, $value, 'Process')
}
```

Alternatively, configure environment variables through the process launcher,
container, or deployment environment. The SDK does not need macOS Keychain;
existing Keychain references remain supported for compatibility.

Replace or revoke a token through OpenMetadata, update `.env` or the process
environment, and reload it or restart the process. Give tokens the platform privileges needed for
the intended operations. Exact role requirements remain unverified for
the target deployment. An SDK connection check only tests list access; it does
not establish write access. 401 and 403 are reported separately.

```sh
open-data-products integrations list --config ~/connections.yaml
open-data-products integrations check openmetadata --config ~/connections.yaml
open-data-products integrations domains openmetadata --config ~/connections.yaml --json
open-data-products integrations products list openmetadata --config ~/connections.yaml --json
open-data-products integrations products search openmetadata --config ~/connections.yaml --query "customer" --limit 20 --json
open-data-products integrations products get openmetadata --config ~/connections.yaml --id PRODUCT_ID --format native --output native.json
open-data-products integrations products get openmetadata --config ~/connections.yaml --id PRODUCT_ID --format native --include-domains --json
open-data-products integrations products get openmetadata --config ~/connections.yaml --id PRODUCT_ID --output product.yaml --provenance product.provenance.json
open-data-products validate product.yaml
```

The product list command retrieves all pages into one ODPC catalog; domain
listing returns one page and an `after` cursor. Results can be filtered by
platform permissions. Product search uses OpenMetadata's
`data_product_search_index` and its native query-string syntax. Its ODPC
catalog includes the total, whether it is exact or a lower bound, and the
next offset in `catalog.metadata.x-source`. Offsets plus page size are
limited to 10,000. Search results depend on the platform index and may lag
behind creation or updates. A search timeout or failed search shard is
reported as an error, not an empty result.
Native retrieval is explicit (`--format native`); no response body is logged.
ODPS export preserves the document's source version and runs existing local
validation. Strict mode defaults to true: invalid documents are not saved,
validation findings are shown, and the command exits nonzero. Set `--strict false`
to allow invalid output; the command writes a `.validation.json` findings file,
reports the failed validation as a warning, and exits successfully.
Outputs do not overwrite existing files. Multi-file saves are staged first;
if publication fails, the SDK attempts to remove files it created and reports
files requiring inspection if cleanup fails. Abrupt process or system failure
can still leave partial output. The optional provenance file contains
only the profile name, platform, ID, source format, time, and available FQN and
revision; it contains no credential or base URL.

### Workaround for numeric `updated` values

OpenMetadata 2.1.0 returned millisecond timestamps in `updated` for the test
product. ODPS 4.1 and 4.2 require a date string. To explicitly create a
derived document, pass `--normalize-updated-timestamps` with an output and a
provenance path:

```sh
open-data-products integrations products get openmetadata --config ~/connections.yaml \
  --id PRODUCT_ID --output product.yaml --provenance product.provenance.json \
  --normalize-updated-timestamps --strict false
```

The SDK interprets supported integers as Unix milliseconds and derives the UTC
calendar date. It writes the unchanged source to `product.yaml.original.yaml`
and records each original number, derived date, and field path in provenance.
The derived document loses time-of-day precision. It is validated separately;
other findings still apply, and `--strict false` is needed to save it if those
findings remain. No fields are invented and nothing is written to the platform.
Out-of-range and ambiguous seconds values are rejected instead of guessed.

Python callers can use `normalize_openmetadata_updated_dates(result.data)` and
inspect the returned original, normalized YAML, changes, and validation result.

Python use:

```python
import yaml
from open_data_products import load_integration_config, open_integration

config = load_integration_config("/path/to/connections.yaml")
with open_integration(config.select("openmetadata")) as adapter:
    page = adapter.list_products()
    result = adapter.export_odps("PRODUCT_ID")
    if result.validation.valid:
        document = yaml.safe_load(result.data)  # Pass to existing SDK interfaces.
```

The candidate export uses `GET /api/v1/dataProducts/{id}/odps/yaml`.
A 404 can indicate a missing product or endpoint and is not interpreted as a
version diagnosis. There is no automatic fallback to native mapping, version
conversion, publication, or background synchronization. Connection and
response errors are sanitized; response bodies and authorization headers are
not logged. Requests refuse redirects, use a bounded response size, and retry
selected transient failures for safe reads only. Use explicit timeouts and keep
local credentials and retrieved metadata under appropriate access controls.
Interrupted or truncated write responses have an unknown outcome: inspect the
destination before deciding whether to retry. The SDK does not retry writes.

## Experimental reviewed creation

The create implementation targets the OpenMetadata 2.1.0 ODPS 4.1 YAML API;
SDK creation has been tested on one live 2.1.0 deployment. Other server versions
and ODPS 4.2 input are blocked; no version conversion is performed. Create uses
POST only, never the upsert or update endpoints. Review resolves the authenticated owner through OpenMetadata by default; a linked remote contract is also fetched during review. It reports validation findings, field omissions and mapping
limits, the selected domain, and a digest bound to the source, profile, server
address, language and destination. It does not establish platform permission.

Generate a new ODPS 4.1 draft for this adapter with the explicit generation
option (the default generation prompt targets 4.2):

```sh
open-data-products generate --kind odps-product --odps-version 4.1 \
  --input business-brief.md --output products/ --json
```

The Python generation methods accept `odps_version="4.1"` or `"4.2"`. The
model is asked to generate the selected version, and the SDK checks the
document's declared version and schema before marking the draft valid. It does
not relabel or convert a document generated for another version. Check the
generated document and validation findings before creation.

Use the `openmetadata` connection profile with `read_only: false` and a token with the
platform's create privilege. The SDK checks the profile before writing:
Find the domain's `fullyQualifiedName` with `integrations domains`, then pass
that exact value as `--domain` for both review and execution. The domain is
bound to the review digest, and the SDK requests domain references on readback.
If the target domain is absent or cannot be verified, the creation result and
CLI status report the mismatch or uncertainty along with the product ID.

```sh
open-data-products integrations products create openmetadata \
  --config ~/connections.yaml --source product.yaml --domain YOUR_DOMAIN

# Use review_sha256 from the review, without changing the source or target.
open-data-products integrations products create openmetadata \
  --config ~/connections.yaml --source product.yaml --domain YOUR_DOMAIN \
  --execute --reviewed-sha256 REVIEW_SHA256
```

Python callers can choose the domain through the same reviewed workflow:

```python
from pathlib import Path
from open_data_products import load_integration_config, open_integration

source = Path("product.yaml").read_text(encoding="utf-8")
profile = load_integration_config("connections.yaml").select("openmetadata")
with open_integration(profile) as adapter:
    review = adapter.review_create(source, domain="YOUR_DOMAIN")
    # Inspect the review before explicitly creating the product.
    if review.executable:
        result = adapter.create_product(
            source, domain="YOUR_DOMAIN", reviewed_sha256=review.review_sha256
        )
        print(result.comparison["domain"])
```

If the ODPS 4.1 document contains one ODCS 3.1.0 contract under
`product.contract.spec`, or links to one with `$ref` or `contractURL`, the SDK
includes the resolved contract content in the review digest. A relative `$ref`
is resolved relative to the ODPS source file; Python callers should pass that
file as `source_path=` to both `review_create` and `create_product`.

OpenMetadata's ODPS import does not import the contract itself. The SDK creates
and verifies the product first, then validates and imports the contract as a
second operation. This is not atomic: if the contract step fails, the product
remains and the result reports its ID and contract outcome. Inspect both before
retrying. The platform can validate the contract against the product only after
the product exists. The source and resolved contract are rechecked against the
review digest; changes block the write. Ambiguous or unsupported references are
blocked rather than silently omitted.

Invalid ODPS documents are blocked for creation. The `--strict false` retrieval
option does not relax this write boundary. OpenMetadata's import maps only a
subset of ODPS and does not import ODPS lifecycle status. Unsupported paths are
listed in the review; retain the original file as evidence. The digest binds
execution to that review but is not an approval or permission mechanism.
Creation also rejects duplicate YAML keys, aliases and documents nested more
than 64 levels, to avoid ambiguous interpretation by the SDK and server.

After a successful response, the SDK retrieves the product and compares its
name, product identifier, selected domain, supplied description and the tested `dataset` and
`private` values. Other type and visibility values, tags and priority are marked
unverified when supplied, pending mapping tests. A mismatch or failed readback returns a nonzero CLI status and the
created product ID; inspect it instead of retrying creation. A timeout,
unreadable or ambiguous response, or server error may leave
the outcome unknown: inspect the destination before retrying. The SDK does not
retry creates. Publication and approval are not implemented. A
validated document is not evidence of business approval.

## Owners and tags

When creating a product without `--owner`, the SDK resolves the authenticated
OpenMetadata account through `users/loggedInUser` and assigns that account as
owner. This can be a service account or bot. The resolved identity is included
in the creation review and checked again before assignment. Use `--no-owner`
to create without this default; Python callers can pass `owners=[]`. If the
current account cannot be resolved, creation is blocked. An explicit `--owner`
replaces this default selection.

Creation and update commands accept repeatable `--owner user:NAME` or
`--owner team:FQN` and `--tag CLASSIFICATION.TAG` options. Use existing active
OpenMetadata users, teams, and classification tags; the SDK resolves them by
identity and binds them to the review. On update the requested values are added
to existing owners and tags. During an update, omit an option to leave that
assignment unchanged.

```sh
open-data-products integrations products create openmetadata \
  --config ~/connections.yaml --source product.yaml --domain Banking \
  --owner user:jarkko --tag PII.NonSensitive --json
# After inspecting the review, repeat the same arguments with:
#   --execute --reviewed-sha256 REVIEW_DIGEST

open-data-products integrations products update openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID \
  --owner user:jarkko --tag PII.NonSensitive --json
# Repeat the reviewed command with --execute --reviewed-sha256 REVIEW_DIGEST.
```

Creation assigns owners and tags in a separate update after the product is
created and verified. This is not atomic. If that update fails or cannot be
verified, the result includes the product ID and assignment outcome; inspect
the product before retrying. A tag such as `PII.NonSensitive` is an example,
not a determination about the data. OpenMetadata's revision precondition
enforcement should be verified on the deployment.

## Create a domain

OpenMetadata 2.1.0 requires a name, description, and domain type. Available
types are `Source-aligned`, `Consumer-aligned`, and `Aggregate`. Optionally
provide `--display-name` and a parent domain FQN with `--parent` to create a
subdomain. Use a write-enabled profile:

```sh
open-data-products integrations domain-create openmetadata \
  --config ~/connections.yaml --name Retail --description "Retail data" \
  --type Aggregate

open-data-products integrations domain-create openmetadata \
  --config ~/connections.yaml --name Retail --description "Retail data" \
  --type Aggregate --execute --reviewed-sha256 REVIEW_SHA256
```

The first call performs a local review; the second checks the digest, sends one
POST, and retrieves the created domain. Inspect the ID and result before retrying
an uncertain outcome. This operation does not create or alter a data product.
The same workflow is available as `adapter.review_domain_create(...)` and
`adapter.create_domain(...)` in Python.

For an unknown create outcome, use the same source and domain in a read-only
candidate lookup:

```sh
open-data-products integrations products recover-create openmetadata \
  --config ~/connections.yaml --source product.yaml --domain YOUR_DOMAIN --json
```

The lookup compares the reviewed product identifier with paginated native
results. A candidate or an empty result cannot prove what happened: permissions,
concurrent changes and missing domain metadata may hide or confuse matches.
`complete: false` means the page limit was reached; the CLI exits nonzero.
The command does not retry, update or delete anything.

## Compare a source with a marketplace product

Compare the reviewed source YAML with a retrieved product without writing to
OpenMetadata:

```sh
open-data-products integrations products compare openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID --source product.yaml \
  --domain YOUR_DOMAIN --output comparison.json --json
```

The output includes the source SHA-256 and validation findings, product ID,
requested and observed domain, platform update timestamp, retrieval time and
revision, and the retrieved ODPS export's timestamp and validation findings.
Each field is marked `preserved`, `normalized`, `changed`, `omitted`, or
`unverified`, with its evidence source. Enum case differences are recorded as
normalization; numeric export timestamps can only be matched to a source date
at UTC day precision. An omission from the ODPS export is not proof that a value
is absent from other OpenMetadata metadata. If export is unavailable, affected
fields are unverified. Invalid exports can still be compared as retrieved
evidence; their validation findings remain visible. The command returns nonzero
for an invalid source or a failed comparison, not simply for a reported
difference. It does not confirm data, controls, business claims or approval.

## Reviewed product updates

An explicit review and subsequent execution can update the native display name
and description. OpenMetadata assigns the metadata revision when the entity
changes; retrieve it as `provenance.revision`. This revision is not an ODPS
product release version and cannot be set directly through this operation.

```sh
open-data-products integrations products update openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID --title "Revised title" \
  --description "Revised description"

open-data-products integrations products update openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID --title "Revised title" \
  --description "Revised description" \
  --execute --reviewed-sha256 REVIEW_SHA256
```

The review retrieves the baseline and displays the changes; execution checks
the baseline again and sends a version-based `If-Match` with a JSON Patch. The
server can enforce that condition. A stale-revision probe on the tested 2.1.0
deployment was rejected; enforcement must still be verified per deployment.
The result compares all requested fields against a fresh read.
Timeouts or ambiguous responses are unknown outcomes and are not retried.

To replace a product's existing domain assignments with one domain, use its
domain FQN and review the consequences before executing:

```sh
open-data-products integrations products update openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID --domain Retail

open-data-products integrations products update openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID --domain Retail \
  --execute --reviewed-sha256 REVIEW_SHA256
```

The review shows the current and proposed domains, resolves the target domain
identity, and binds the product snapshot and target to its digest. Execution
rechecks both, requests revision protection, and verifies the domain afterward.
OpenMetadata may migrate associated assets and detach conflicting relationships
when a domain changes; inspect dependencies before executing. This operation
replaces all current product domains with the selected one. The Python methods
`review_update` and `update_product` accept `domain=` as well.
The [OpenMetadata 2.1.0 implementation](https://github.com/open-metadata/OpenMetadata/blob/2.1.0/openmetadata-service/src/main/java/org/openmetadata/service/jdbi3/DataProductRepository.java)
contains the domain-change handling.

## Attach an ODCS contract to an existing product

Review and explicitly import a single ODCS 3.1.0 YAML document against the
target product UUID:

```sh
open-data-products integrations products contract-import openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID --source contract.yaml

open-data-products integrations products contract-import openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID --source contract.yaml \
  --execute --reviewed-sha256 REVIEW_SHA256

open-data-products integrations products contract-get openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID --json
```

The review checks the product and absence of an existing contract, then calls
OpenMetadata's non-writing ODCS validation endpoint and returns its import
findings. Full local ODCS schema validation is not bundled; the SDK performs
basic metadata and unambiguous-YAML checks. This create-only operation blocks if the product
already has a contract; it does not merge or replace existing contracts. It
rechecks the product and absence before one POST, with no atomic absence
precondition, and reads back the contract and association. The source should be
retained because platform mapping can omit fields.

On the tested OpenMetadata 2.1.0 deployment, platform validation rejects native
schema validation for a `dataProduct` target and does not retain the ODCS
contract version as the native revision. The SDK's workaround imports a
schema-free projection as the product's native contract, then preserves the
complete source YAML, source version and SHA-256 in that contract's
`odcsPreservedFields.odpsSdkSource` metadata. It verifies that metadata after
writing. No deployment-wide custom property is required. The full schema is
preserved as source metadata; OpenMetadata does not validate it as the product's
native contract schema. The platform's native ODCS export does not reconstruct
this SDK-preserved source or its original version. Retrieve the exact preserved
source through the SDK:

```sh
open-data-products integrations products contract-source openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID --output original-contract.yaml
```

Direct and linked YAML inputs retain their exact text. An inline ODPS contract
is serialized as a standalone YAML document, preserving its values rather than
the surrounding document's original formatting or comments.

The review displays both the source and projected platform validation reports.
Only source validation failures caused by the product schema restriction are
eligible for the workaround; other blocking findings still block import. All
ODCS schema objects are preserved, including when none is selected for native
mapping. The SDK checks only basic ODCS metadata locally; preservation is not
full ODCS schema validation or business approval. Source YAML is stored in
OpenMetadata, so it should not contain credentials. The source and native
contract can diverge after later edits; the retrieved source is the preserved
imported document, not a live reconstruction of the native contract. The
source is limited to 1 MiB. Python callers can use `review_contract_import`,
`import_contract`, and `get_preserved_contract_source`.
See the [OpenMetadata 2.1.0 ODCS import endpoint](https://github.com/open-metadata/OpenMetadata/blob/2.1.0/openmetadata-service/src/main/java/org/openmetadata/service/resources/data/DataContractResource.java)
for the platform contract.

The opt-in live SDK round-trip test creates and retrieves a product, checks
it appears in listing and search, checks a non-matching query, updates
its title and description, verifies the new values and platform revision, and
probes whether the server rejects a stale revision, and permanently deletes
that test product with a final absence check. If a server accepts the probe,
the test reports that atomic protection is unavailable.
An earlier test also populated a `productVersion` custom property; the SDK no
longer depends on that property for this workflow.

## Experimental permanent deletion

OpenMetadata 2.1.0's data-product deletion endpoint is **permanent and
recursive**, including when `hardDelete=false` is supplied. The 2.1.0 server
implementation passes both `recursive=true` and `hardDelete=true`; the product
cannot be restored through that endpoint, and child entities may be deleted.
Inspect dependencies before using it. This SDK operation has been tested on a
disposable product in one OpenMetadata 2.1.0 deployment and is restricted to
that server version. It does not offer a recoverable or non-recursive mode.

Review the target using its platform UUID and a write-enabled profile:

```sh
open-data-products integrations products delete openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID

# After reviewing the target, consequences and review_sha256:
open-data-products integrations products delete openmetadata \
  --config ~/connections.yaml --id PRODUCT_UUID --execute \
  --reviewed-sha256 REVIEW_SHA256 --confirm-permanent
```

Review reads the server version and current product without deleting it. The
digest binds the target snapshot, profile and server. Execution re-reads the
snapshot and blocks if it changed. This is not an atomic revision check; a
change can occur between the final read and deletion. The platform still makes
the authorization decision. The SDK sends the DELETE once and checks whether
the product can be read afterward. The CLI returns nonzero when absence cannot
be verified. An ambiguous response or timeout is an
unknown outcome: inspect the destination before retrying. It never automatically
deletes the test product or other entities.

## Extending

First-party adapters implement `PlatformAdapter`: capabilities, a safe
connection check, and close. Register each explicitly in `open_integration`.
Operations must preserve native identity and provenance, make unsupported
capabilities explicit, and invoke `require_write_access` before any future
mutation. A write-enabled profile does not grant platform permission. The
adapter should return typed, sanitized errors and never infer permission from
connectivity. Third-party plugin discovery is not implemented.

## Opt-in live checks

Set `ODPS_INTEGRATION_CONFIG` to the private YAML path and the referenced token
in the same environment. Run `python -m pytest tests/test_integrations_live.py`.
The optional `ODPS_INTEGRATION_PRODUCT_ID` enables a separate export test.
The round-trip write test requires `ODPS_INTEGRATION_WRITE_TEST=1`,
`ODPS_INTEGRATION_WRITE_PROFILE`, and `ODPS_INTEGRATION_TEST_DOMAIN`. It creates
a uniquely named non-sensitive product and permanently deletes that same
product after the test, including after an assertion failure where cleanup can
still be performed. It verifies the target before deletion and reports the ID
for manual investigation if the outcome is uncertain. It requires create,
update and delete privileges; it never registers a property. Without opt-in,
write tests are skipped. Record the deployment version and outcomes before
making compatibility claims.

The additional document-to-marketplace test uses a locally running Ollama model
to generate a specification from each synthetic Markdown and Word `.docx`
brief. It validates the specification, reviews and creates a private product,
checks the returned fields, listing and search, then permanently deletes the
test product. The listing and search checks use the configured identity; they
do not establish publication, approval or visibility to other users. Run it
with the same write configuration and domain plus:

```sh
export ODPS_INTEGRATION_DOCUMENT_TEST=1
export ODPS_INTEGRATION_WRITE_TEST=1
export ODPS_INTEGRATION_OLLAMA_MODEL=qwen2.5:latest
python -m pytest tests/test_integrations_live.py::test_live_business_document_to_marketplace -q -s
```

The test requests ODPS 4.1 with `odps_version="4.1"` because the OpenMetadata
create adapter accepts 4.1; the standard generation prompt targets 4.2. It
does not convert versions or establish that arbitrary generated documents are
ready for use. Review generated drafts and their source before creating a real
product. The cleanup has the same uncertain-outcome limitations as other
reviewed deletes.
