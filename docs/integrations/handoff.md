# Data product preparation handoff

For a short business starting point, use the [data product idea one-pager](../user/business-one-pager.md).

For development timing tests from a synthetic business brief through OpenMetadata and Jira, see the [end-to-end timing benchmark](../../examples/integrations/HANDOFF_TIMING_BENCHMARK.md).

## MCP tools

The SDK MCP server exposes reviewed, per-document handover and Jira operations.
Configure the generation provider and named Jira connection as for the guided
CLI. MCP clients should render the supplied source files for the user to review;
preview responses contain source filenames, hashes, provider origin and bounded
catalog summaries rather than full document bodies.

1. Call `preview_business_handover` with `business_document` and a new `output`
   directory. After review, call `create_business_odps_draft` with the same
   arguments and `reviewed_sha256`. The tool stages the reviewed source and
   generates a local ODPS draft.
2. Call `preview_implementation_handover` with the staged business document,
   ODPS draft, a **new** package `output` directory and a `change_name`. An
   optional `context_file` supplies a JSON metadata snapshot; `asset_id` selects
   an optional catalog asset. The snapshot's safe platform origin, when
   recorded, is included automatically. Review the inputs and provider, then call
   `create_implementation_handover` with the same arguments and returned digest.
   The result identifies the OpenSpec change and ZIP relative to the chosen
   output directory. The package includes a separate ODCS draft.
3. Call `review_jira_handover` with that change, project, issue type and exactly
   one package delivery method (`package_attachment`, `package_url` or
   `shared_filesystem`). Supply the business document as an attachment or an
   accessible HTTPS reference. The preview states access assumptions and binds
   the issue and attachments to a digest. After review, call
   `deliver_jira_handover` with the same inputs, digest and a new `journal_file`.

`review_jira_issue` and `create_jira_issue` provide the same reviewed Jira
workflow for general issues without any handover dependencies. Create calls
use an exclusive local journal before contacting Jira. Existing journals block
retries; inspect Jira after a failed or unknown outcome. A partial attachment
upload is returned as an MCP error with the issue key and journal status so the
client can investigate. These create tools are classified as state-changing.

MCP package generation accepts existing metadata snapshots; it does not run
automatic catalog discovery itself. The SDK remains usable without Jira or a
metadata platform. Output schemas, contracts and plans are drafts requiring
domain review; structural validation is not approval.

## Guided flow

After installing the SDK, run setup from the project directory where you want
to keep the configuration. To configure a provider, OpenMetadata, Jira, or all
three, run:

```sh
open-data-products config setup
open-data-products config show
```

Setup requires an interactive terminal. It reviews the selected settings and
files before saving. It first shows the existing local configuration and
suggests a next command after saving. Credentials are entered without echo and stored in the
local `.env`; connection and generation YAML files contain references to their
environment variables. Existing unrelated values are retained, but editing
YAML rewrites its comments and formatting. Selected connection profiles can be
replaced, as shown during review. Existing process environment variables take
precedence over `.env`; keep `.env` out of version control.

Status reports local configuration and credential presence without printing
secrets, with commands for missing credentials or other next steps. `--json`
provides machine-readable output including `next_steps`. To perform read-only
OpenMetadata and Jira connection checks, use:

```sh
open-data-products config status --test
```

These checks do not test the LLM provider, marketplace visibility, Jira project
permissions or write permissions. Setup can select a built-in or existing
configured provider, or add a custom provider using a supported SDK provider
type and model. Custom remote provider URLs must use HTTPS; HTTP is allowed
for localhost. Generation, guided handover and platform CLI commands load the
local `.env` automatically; other workflows may require variables to be
exported in the shell. Existing user-owned generation and connection
configurations also satisfy setup; no separate setup marker is required.

To add or select LLM providers later, run:

```sh
open-data-products config llm add
open-data-products config llm list
open-data-products config llm use --name company
```

Adding a provider does not select it automatically. The `use` command changes
the active provider after review. The `list --json` form is machine-readable.

To manage named platform connections, use:

```sh
open-data-products config connections list
open-data-products config connections add
open-data-products config connections edit --name openmetadata
```

The add and edit commands review changes before saving. They currently support
OpenMetadata and Jira Cloud; listing also identifies unsupported platform types.
An existing name is never replaced by `add`. Use `config show --json` for one
view of the active provider and connections without credential values; endpoint
origins are shown without URL paths or query strings.

To set or replace a credential without putting its value in a command or shell
history, run the following and enter the value at the hidden prompt:

```sh
open-data-products config credentials set --name OPENAI_API_KEY
```

Use the environment-variable name shown in `config show` for other providers
and connections. The local `.env` is updated only after review; an existing
process environment variable takes precedence. Jira project and issue type
settings are shared by guided Jira delivery across Jira connections.

To test the configured LLM, OpenMetadata and Jira connections together, run:

```sh
open-data-products config test
```

The LLM test sends the fixed prompt `Reply with OK.` and may incur provider
costs. It does not send business documents. OpenMetadata and Jira checks are
read-only, and do not establish write permissions, marketplace visibility or
Jira project permissions. Only configured, supported connections are tested.

From the project directory, prepare the handoff in one interactive command:

```sh
open-data-products handover prepare --input business-brief.md
```

To prepare multiple business documents, supply a folder instead:

```sh
open-data-products handover prepare --input path/to/business-briefs/
```

The folder is scanned at its top level for `.md`, `.txt` and `.docx` files.
Each file is treated as a separate business idea and gets its own provider
reviews and package. Other entries, including subfolders and symbolic links, are
reported and skipped. Failures are reported per file and do not prevent later
files from being processed; the command returns a nonzero status if any failed.
Discovery is planned separately for each brief; it does not reuse one search
term across the folder.

For a machine-readable result, use `--json` and redirect standard output:

```sh
open-data-products handover prepare --input path/to/business-briefs/ --json > results.json
```

Reviews and prompts still appear on standard error and require an interactive
terminal. `results.json` contains a `documents` array with each source and
status (`prepared`, `declined`, or `failed`), a `workspace` path for prepared
packages, and an error for failures. Paths are interpreted from the working
directory used for preparation. `skipped` lists unsupported folder entries.
The command exits nonzero if a document fails; inspect the JSON for partial
results. Input or configuration errors before processing can exit without JSON.
Use each prepared `workspace` with `jira deliver`; delivery remains separately
reviewed and interactive.

The command prints each prepared workspace and its exact second command. Run it
when you are ready to review Jira delivery for that package:

```sh
open-data-products jira deliver --input path/to/prepared-workspace
```

Both commands automatically read `.env` in the current directory when present,
without executing shell code; existing environment variables take precedence.
Preparation uses the local `generation.config.yaml` when present. Configure the
provider, model and credential environment variable there; the credential itself
belongs in `.env` or the environment. Without that file the existing SDK
generation defaults apply. `--config`, `--provider`, `--model` and `--env-file`
remain optional overrides.

For example, a project-local `generation.config.yaml` can select OpenAI
without putting credentials in configuration:

```yaml
provider: openai
providers:
  openai:
    type: openai
    model: gpt-5.2
    apiKeyEnv: OPENAI_API_KEY
```

Store the API key in the environment or in the local `.env` file as
`OPENAI_API_KEY=...`. Treat `.env` as a secret and do not commit it. Other
providers and models use the existing [generation configuration](../user/generation.md#llm-setup).
Validate a configuration with `open-data-products config generation --config
generation.config.yaml --check`.

Preparation rejects documents larger than 20 MiB or with more than 1,000,000
characters in the generation context or extracted text. Word document XML is
also limited to 10 MiB uncompressed. These checks run before provider review
or generation; documents are not silently truncated. For a folder, an oversized
file is reported as failed and the other files continue. The character limit
is not a guarantee that every provider or model can accept the resulting prompt.
The guided flow accepts `.md`, `.txt` and `.docx`, rejects control and invisible
formatting characters in extracted text, and rejects encrypted Word archives,
macros and embedded active content. A narrow check also stops selected explicit patterns for instruction override,
role spoofing, credential disclosure and command execution. It names the category
in its error without repeating the suspicious content. This can flag legitimate
discussion and will miss paraphrased, encoded, multilingual and other attacks.
These checks happen before provider configuration, review and generation.
The SDK does not execute document contents.
Source text is untrusted: generation prompts and assistant instructions tell the
model not to obey instructions inside source material. These checks are not a
malware scanner or a guarantee against prompt injection. Review source material
and generated artifacts before sharing or acting on them. Word attachments may
contain other content not inspected by the SDK; scan untrusted files with your
organization's security tools before opening or distributing them.

In guided preparation, an unsupported `public` visibility in the generated
ODPS is replaced with a conservative `private` draft default. The default is
recorded in `supporting/generation-defaults.yaml` and requires review; it is
not an approved access classification. An explicitly labelled `visibility:
public` source value is preserved for review.

Preparation displays the business content before the first provider call and
shows the generated ODPS and provider evidence before the second. Each call
requires confirmation. It stores a copy of the business document in the local
workspace with the package, ZIP and previews. No Jira connection is needed for
preparation.

Delivery uses the named `jira` connection in `connections.yaml` and the
`JIRA_PROJECT` and `JIRA_ISSUE_TYPE_ID` environment variables. Set these and the
Jira credential variables in `.env` or the environment; the issue type must be
its numeric ID, and the issue type and project must be accessible to the account. The connection
references credential environment variables; do not put their values in YAML.
Delivery previews the Jira issue and attachments and creates the issue only
after confirmation. The reviewed digest binds the issue and attachments. If
creation has an unknown outcome, inspect Jira before attempting another
delivery. The workspace records the preview and result. The business document,
enriched ODPS and ODCS draft are delivered alongside the package;
the original ODPS draft is not delivered. Use `--connections` and `--connection`
to override the Jira profile, and `--fields` for a JSON object containing
required custom fields.

Every implementation-draft handoff includes a separate ODCS 3.1 draft. When no
output attributes can be established, the draft contains only its draft metadata
and an explanation that the schema and contract terms remain open; it does not
invent fields or rules. Output schema alignment is then not assessed, and the
coding assistant must investigate it. Jira delivery stops before creating an
issue if the ODCS draft is missing or its required draft identity is invalid.
This check does not replace full ODCS validation. An issue may still be created
before an attachment upload fails: inspect the reported partial result in Jira
before recovery, and do not assume the contract was delivered.

Select a metadata discovery target per preparation run using its connection name
in the YAML configuration:

```sh
open-data-products handover prepare --input business-briefs/ --discovery openmetadata --json > results.json
```

Without `--discovery`, preparation runs without metadata discovery. The default
configuration is `connections.yaml`; use `--connections` if the connection is
configured elsewhere. The target must advertise the read-only metadata discovery
capability. OpenMetadata is currently implemented; another platform such as
DataHub needs an implemented and registered adapter and configuration support.
The connection name is a YAML key, which can be different from the platform type.

When a snapshot is supplied, the package includes
`supporting/metadata-discovery.yaml`: a platform-neutral summary of the target,
selected product and assets, available search queries and retrieval times,
contract provenance, and incomplete or unavailable resources. It references
`catalog-evidence.yaml` and asks the coding assistant to confirm live access.
These are supporting artifacts, not native OpenSpec files. For SDK discovery,
the configured HTTP(S) **origin** is included automatically and is covered by
the handover review digest. Credentials, query strings, fragments and
reverse-proxy paths are not included. A supplied snapshot can record the
credential-free origin as `discovery_target.platform_url`; if it lacks one,
the package reports that the address is unavailable instead of guessing. The
origin does not establish that the assistant has access, and the snapshot may
contain other sensitive information. Review it before sharing.

For each brief, the SDK sends the already reviewed text to the configured
provider to propose up to three concepts, each with an exact source quotation.
When the brief has an explicit `product_name` in YAML front matter, the SDK
includes that name within the same three-concept budget. It is a search phrase,
not an automatic product match.
Search phrases may include proposed synonyms. The user reviews the concepts
before the SDK sends them to the selected metadata platform. The model's reasons
are proposals, not evidence.

Discovery executes up to three quoted phrase searches, four results per search,
and inspects their available metadata and one-hop lineage. It displays possible
product matches and allows the user to select at most one product for its linked
assets and available contract content. It never guesses a product match.
Candidates, schemas, lineage, incomplete requests and source-backed query
provenance are preserved in the local evidence snapshot. The provider review
shows the candidate asset columns it will receive; the full snapshot is kept in
the package for the coding assistant. The user confirms before it is sent.

An automatic discovery budget gate checks the combined snapshot before it is
saved or used for handover generation. It allows at most 1 MiB for the snapshot
and 256 KiB for the serialized asset evidence and column citations sent to the
provider. Existing limits also apply: at most 20 assets, 200 columns per asset
and 1,000 columns total. The gate records byte counts, counts, incompleteness,
errors and truncation notes in `discovery-budget.json` locally and in the
package's `supporting/` directory. If a budget is exceeded the affected document
fails with a clear error before the evidence is saved or sent; folder processing
continues for other documents. There is no new human approval step at the gate.
Byte limits do not enforce the model's token or full prompt limits. Current
candidate and column truncation follows discovery order, not relevance ranking.
Search is bounded and lexical, not semantic, and proposed synonyms can be wrong
or miss relevant assets. One live synthetic Product Holdings test used OpenAI,
OpenMetadata 2.1.0 and Jira Cloud; it retained unresolved fields and catalog
search limits. One earlier model concept response was rejected and its exact
cause was not captured. These observations do not verify other inputs or deployments. The
model assesses candidate fields against requirements during generation; these
remain proposals rather than verified mappings. If discovery is disabled,
the user declines discovery, or the service is unavailable, preparation can
continue without catalog evidence. These guided commands require an interactive
terminal. For scripting or more control, use the individual commands below.

The independent OpenMetadata command space also provides read-only discovery:

```sh
open-data-products openmetadata discover --id PRODUCT_UUID --json
```

The default CLI handoff produces an **implementation draft**, not an approved
plan or implemented product. It includes an OpenSpec proposal, specification,
design and tasks, an enriched ODPS draft and evidence-linked open questions.
The provider proposes business-requested output attributes and candidate mappings
across the supplied catalog assets. `supporting/field-mapping.yaml` distinguishes
business quotations, catalog observations, model proposals and decisions. The
output schema and separate ODCS 3.1 draft retain unresolved fields without asserting
unknown types. When candidate column names match the output field and all source types agree,
a compatible output type is proposed for a non-derived field. Such types and mappings remain unverified and
the field descriptions point to open decisions. Derived field types are not inferred
from input types. No target repository or source connection
is inspected by generation. `--preparation-only` retains the initial workflow.

## Validate with the OpenSpec CLI

Install OpenSpec separately if you want the SDK to run its structural check.
The SDK itself does not install the CLI or require it for generation. Follow
[OpenSpec's official installation guide](https://github.com/Fission-AI/OpenSpec/blob/main/docs/installation.md).
For example, with a compatible Node.js installation, the version used in the
SDK's CLI integration tests can be installed with:

```sh
npm install -g @fission-ai/openspec@2.2.0
openspec --version
```

Then validate either the prepared workspace or its generated change directory:

```sh
open-data-products handover validate --input handoffs/data-product-WORKSPACE --json
```

The SDK detects `openspec` on `PATH`, reports its version, and runs OpenSpec
`status` and strict `validate` in an isolated temporary project using the SDK's
default `spec-driven` schema. It does not initialize, inspect or modify the
target repository or its OpenSpec configuration. Only native planning artifacts
are staged; SDK supporting evidence remains in the package. The subprocess uses
a limited environment and disables OpenSpec telemetry. Results are printed only;
the SDK does not modify the package or write the result back to its manifest.

- `passed` (exit 0): CLI validation passed and planning artifacts are present.
- `failed` (exit 1): validation failed or an implementation draft lacks required
  planning artifacts. Inspect `issues` and `reason`.
- `incomplete` (exit 2): a preparation-only package has its intentionally missing
  specs, design and tasks; strict CLI validation did not pass. This is not a pass
  or an independent validation of the proposal.
- `not_performed` (exit 2): the CLI is missing or could not complete the check.
  Install it using the linked guide and retry; no validation pass is reported.

OpenSpec CLI 2.2.0 was tested against fresh SDK-generated preparation-only and
implementation-draft packages. The tests also reject a broken implementation
specification. Other CLI versions and target repository custom schemas remain
unverified. Structural validation does not establish business approval, source
correctness or implementation readiness. A coding assistant must inspect the
target repository and its actual OpenSpec schema before using the package.

The generated OpenSpec `spec-driven` layout is based on upstream source revision
`f1cd852f4edce22b8df9548a4df889172ca8ff25`. OpenSpec CLI 2.2.0 previously strictly
validated an implementation draft produced by a mocked provider in an isolated
project. This historical check does not establish compatibility of every newly
generated package, other CLI versions or custom schemas, or the semantic
correctness of model output. The CLI is not bundled with the SDK. Previously,
in an isolated temporary project, the CLI recognized
the synthetic Product Holdings draft and its proposal, and reported planning as
incomplete. Its full change validation failed because the draft contains no
specification delta yet. This is expected for the initial package and is not a
successful full validation; other CLI versions and custom schemas have not been
tested. In a separate synthetic banking handoff, a coding assistant completed
the proposal, specifications, design and tasks in an isolated project; that
completed change passed OpenSpec CLI 2.2.0 strict validation. Its proposed ODCS
3.1.0 draft also passed the SDK's contract check using datacontract-cli 1.2.11.
These checks do not approve the plan or establish that a data product exists.
The preparation-only output contains `.openspec.yaml`, a draft `proposal.md`,
`preparation.md`, and SDK-owned `supporting/` evidence. It does not create empty
specifications, design, tasks, output schema, or ODCS contract. The assistant
must inspect the target's OpenSpec schema and configuration before using the
change there. Supporting files are not required native OpenSpec artifacts.
The implementation-draft generator refuses an output directory containing a
Git repository marker or OpenSpec configuration; generate separately and
inspect the target workflow before any explicit import into a repository.

## Generate locally

The existing generation configuration selects the provider and model. Preview
prints the full business and ODPS text and candidate asset metadata that will be
sent to the provider, so protect its output. The original ODPS is not included
in the implementation package; its digest is retained for traceability. Review
the package before sharing it. The rest of the context snapshot is
not sent to the provider. Review the preview and use its digest for generation:

```sh
open-data-products handoff brief.md product.yaml --output handoffs \
  --change customer-view --config generation.config.yaml \
  --context context.json --asset-id ASSET_ID
open-data-products handoff brief.md product.yaml --output handoffs \
  --change customer-view --config generation.config.yaml \
  --context context.json --asset-id ASSET_ID --execute \
  --reviewed-sha256 REVIEW_DIGEST
```

The same context and asset selection must be supplied at execution. Asset IDs
are explicit; catalog matches remain unverified candidates. The preview
binds the entire snapshot and all submitted assets to the review digest. Evidence
is limited to 20 assets, 200 columns per asset and 1,000 columns total. Unsupported
types and unresolved mappings remain visible as untyped ODCS properties.
Different output and source column names are kept as unresolved candidate mappings
until a human confirms equivalence. A proposed transformation without an exact
supporting business excerpt or cited column description is omitted and flagged.
Column descriptions are capped at 2,000 characters, with truncated
column names recorded in the provider preview. The provider can cite numbered
source excerpts; the SDK resolves those identifiers back to exact source text.
Recognized sample-data fields are omitted from the package's catalog evidence
and never sent in the asset evidence. The local `catalog-context.json` retains
the original discovery response, including preserved contract content; protect
it accordingly. Contract content in the package can still be sensitive.
`supporting/product-enriched.odps.yaml`, `output-schema.yaml`,
`odcs-draft.yaml`, `field-mapping.yaml`, `evidence.yaml` and `catalog-evidence.yaml` are SDK supporting
artifacts, not native OpenSpec files. The original ODPS remains unchanged; an
existing contract reference is preserved and the new draft is not linked over
it. For ODPS 4.1 and 4.2 with no existing contract, the enriched draft references
the adjacent ODCS file. The provider's exact quotations are checked, but a
matching quote does not prove a proposed interpretation is correct. An ODPS
implementation package includes `requirements-traceability.yaml` (bounded
source-statement inventory and tentative links), `open-decisions.yaml`,
`contract-constraints.yaml`, and `validation-status.yaml`. A linked quotation
is only partial candidate coverage, not proof that a requirement is correctly
specified, approved, or implemented. Unmatched statements require review; the
inventory can contain context as well as requirements. Open decisions may have
only lexical candidate links and never assign an invented owner. A suggested
role is included only when the source explicitly names that role; responsibility
remains unconfirmed. Generated scenarios preserve source wording or identify
missing acceptance criteria; narrowly recognized explicit source actions and
their `when`/`if` triggers can form candidate scenarios. Model-proposed failure
mechanisms remain in evidence for review and are not treated as verified. Preserved ODCS
constraints are reported with their provenance and unresolved applicability,
never copied automatically. Validation results distinguish structural checks,
proposal consistency, alignment, and semantic review. Source excerpts may be
sensitive and should be reviewed before sharing the package. An ODPS
data-quality proposal uses a `default` declarative profile. The generator only
creates a structured quality dimension for an exact source excerpt with one
unambiguous integer percentage target and a recognized dimension. Other quality
expectations remain quoted draft text; conflicting targets are left unresolved.
Existing data-quality profiles are preserved. Generated objectives are proposals,
not verified measurements or approved promises. A new SLA uses a `default`
declarative profile and records exact service-source excerpts. The generator
proposes `uptime` from an unambiguous availability percentage target and
`updateFrequency` from an explicit daily publication expectation. The mapping,
scope and measurement need confirmation; acknowledgement and recovery are kept
as source text rather than silently assigned SLA dimensions. Conflicting targets
remain unresolved, and existing SLA profiles are preserved. Other ODPS
enrichment proposals are omitted and flagged when they introduce numeric details
absent from its cited excerpt. Core intent, requirements, scenarios or tasks
with numeric details absent from their primary citation receive additional exact
source excerpts when available; details absent from that source are rejected.
If the same number appears in multiple source excerpts, the generator reports
the candidates as ambiguous instead of selecting one. Matching numbers or
excerpts do not prove semantic support and require human
review.
Omit both `--context` and `--asset-id` to generate locally without OpenMetadata;
unmapped requested attributes remain in the output proposal and ODCS schema without
an invented type. Simple identifier-shaped list items under output,
attribute, field or measure headings are retained as unresolved when the provider
omits them. Other document formats still require human completeness review.
ODPS-to-ODCS alignment is not assessed, and does not pass, when either independent
schema is missing; an ODPS reference to ODCS is not an independent dataset schema.
Malformed responses or unsupported citations for core intent, requirements or
tasks stop generation with an error. Optional ODPS enrichment with an unsupported
citation is omitted and reported in the package findings.

`--business-product-id` checks an explicitly supplied identifier against the
ODPS product ID. `--business-reference` and `--product-reference` record source
references but do not verify access. Full extracted business text is excluded
unless `--include-full-business` is selected. Evidence contains selected
quotations that may still be sensitive. Generated statements are model
suggestions, even where a quotation matches a source, and require review.
Python callers can use `preview_implementation_handoff` and
`generate_implementation_handoff`; `preview_handoff` and `generate_handoff`
continue to provide the preparation-only flow.
If no ODPS draft exists yet, first use the existing `generate --kind
odps-product` workflow and review its output; the handoff does not silently
create or convert the input product.

## Optional OpenMetadata context

```sh
open-data-products integrations discover metadata --config metadata.yaml \
  --id PRODUCT_UUID --query 'customer' --limit 20 --json > context.json
# Add --context context.json and, after review, --asset-id ASSET_ID to handoff.
```

A product ID or user search query is required; both may be supplied. Discovery
uses read-only requests, a single bounded search page, bounded candidate reads,
one-hop lineage, and product-contract lookup. It collects available column
names, types and descriptions without requesting sample rows. It includes the
product contract response and, when accessible and safe to include, the SDK-preserved ODCS
source in `supporting/catalog-evidence.yaml`, each with connection, product and
contract provenance, retrieval time, byte size and SHA-256. Each is limited to
1 MiB; unavailable, oversized or integrity-failed content is reported as an
incomplete resource. The preserved source is integrity checked only: neither its
schema nor its completeness is claimed to have been validated by OpenMetadata.
If the product contract lookup returns HTTP 404, discovery reports that no
contract was returned without assuming whether it is absent, inaccessible or
unsupported. It does not repeat that request for preserved ODCS content; the
snapshot instead states that the source could not be checked. Confirm the
selected product and investigate the installation when needed.
Recognized sample-data fields are removed from structured evidence. If a
preserved ODCS source contains those fields, or cannot be parsed for inspection,
the package withholds its YAML and retains the original source hash and a
withholding notice. Other contract content may still be sensitive; review the
snapshot before sharing it.
The overall snapshot is marked incomplete. Matches require independent review;
not every asset type, lineage or quality endpoint is covered.
In the configured OpenMetadata 2.1.0 synthetic test environment, product and
catalog discovery returned linked assets, table columns, lineage and contract
information. Search also reported inaccessible or unsupported candidates and
the snapshots remain incomplete. This is evidence for that test deployment,
not verification of other deployments or every supported resource type.

## Jira Cloud

Create a separate named Jira connection configuration (credentials are only
resolved from environment variables):

```yaml
version: 1
default_connection: jira
connections:
  jira:
    platform: jira_cloud
    base_url: https://example.atlassian.net
    read_only: false
    auth:
      type: basic_env
      email_env: JIRA_EMAIL
      token_env: JIRA_API_TOKEN
    http:
      timeout_seconds: 30
```

For any general issue, provide a JSON file with `project`, `issue_type_id`,
`summary`, `description` (Markdown), and optional `fields` for required custom
fields. Preview with `open-data-products jira --config jira.yaml --connection
jira --request issue.json`. Pass `--execute --reviewed-sha256 REVIEW_DIGEST` to
create after review. The adapter reads required field metadata, converts supported
headings, paragraphs, lists and links to Atlassian Document Format, and performs
an advisory duplicate search. A search is not atomic duplicate protection.
Timeout or uncertain creation requires searching Jira before a manual retry.

For handoff delivery, replace `--request` with `--handoff CHANGE_DIRECTORY`,
`--project` and `--issue-type-id`, and choose exactly one package delivery method:

- `--package-url https://...` for an HTTPS reference.
- `--package-attachment handoff.zip` for an explicitly selected ZIP whose
  entries match the change directory exactly. Use paths relative to the change
  directory inside the ZIP; both compressed and uncompressed sizes are capped
  at 10 MiB.
- `--shared-filesystem /absolute/path` when the assistant shares that filesystem.

`--business-url` is an optional HTTPS source reference. `--product-url` is
available for preparation-only packages; implementation delivery rejects
original ODPS source URLs and attachments. For an implementation package, only the enriched
ODPS draft is delivered; the original ODPS source digest remains in the evidence.
With ZIP delivery, the SDK also selects `product-enriched.odps.yaml` as a distinct Jira
attachment and identifies it as the generated draft deliverable. It is part of
the reviewed attachment list and counts toward the five-attachment limit.
Use `--attachment FILE` to select additional files explicitly, such as the full
business document. The task identifies a selected source attachment when its digest matches the original
source, and asks the assistant to verify access; the SDK cannot verify the remote assistant's
permissions. Supply required custom fields as a JSON object with `--fields`.
To provide the ODCS as a standalone Jira attachment as well as inside the ZIP,
explicitly select `--attachment CHANGE_DIRECTORY/supporting/odcs-draft.yaml`.

The review binds the selected delivery method, task, destination, package and
source digests, plus the selected attachment filenames, sizes and digests. The
package digest is SHA-256 of a UTF-8 compact JSON list of `[relative_path,
file_sha256]` pairs sorted by path. It describes the local change files; an
HTTPS or shared-filesystem destination must be independently checked against it.
The issue labels this as the content-manifest digest. For a ZIP attachment, it
also includes the separate SHA-256 of the ZIP file bytes; the two hashes are
different and serve different verification steps.
Confirm HTTPS and filesystem access with the assistant. A confirmed issue key
is returned along with attachment failures, which can have an unknown remote
outcome and require manual inspection before retrying. Uploads are limited to
five files of at most 10 MiB each. Live Jira behavior remains unverified; the
OpenSpec and OpenMetadata checks have the limited scope described above.
