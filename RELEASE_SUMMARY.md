# Open Data Products Python SDK 0.9.0 Release Notes

This feature release prepares a reviewable coding-assistant handover from a
business brief, optionally enriches it with metadata evidence and delivers it
to Jira Cloud. The generated material is a draft; it is not business approval,
a validated production contract or an implemented data product.

## Prepare and deliver a handover

- `handover prepare --input` accepts a Markdown, text or Word document or a folder.
  It uses the configured LLM provider to create an ODPS draft and an OpenSpec
  implementation planning package. Folder results can be returned as JSON.
- The package contains business intent, source references, open decisions and
  draft proposal, specification, design and tasks. Supporting artifacts include
  an enriched ODPS draft, field-level source mappings, a separate ODCS draft and,
  where evidence permits, an output schema. Unmapped attributes and uncertain
  rules remain visible for review.
- `jira deliver --input` reviews an issue and its package attachments before
  creating them. The reusable Jira Cloud adapter also accepts general issue
  requests. An unknown create outcome must be investigated before retrying.
- Local preparation requires neither Jira nor a metadata platform. Optional
  discovery uses the named connection supplied through `--discovery`; the SDK
  currently implements OpenMetadata discovery, not DataHub or other platforms.

## Evidence, limits and validation

- OpenMetadata discovery retrieves available candidate schemas, lineage and
  product contracts through bounded read-only requests. The discovery snapshot
  is limited to 1 MiB, and catalog evidence sent to the provider to 256 KiB.
  Searches are lexical and bounded; candidates can be missed or be irrelevant.
- Preserved ODCS content is integrity checked when accessible. This does not
  mean OpenMetadata validated that preserved schema. ODPS-to-ODCS alignment is
  not assessed when either independent dataset schema is missing.
- The SDK checks source size and selected suspicious input patterns, displays
  provider input for review, and treats source and catalog text as untrusted.
  Screening is not a malware scanner or a complete prompt-injection defense.
- `handover validate --input` uses an optional installed OpenSpec CLI. It reports
  the CLI version and distinguishes structural passes, failures, deliberately
  incomplete preparation packages and checks not performed. OpenSpec CLI 2.2.0
  was tested with freshly generated packages in an isolated project; custom
  target schemas and other CLI versions remain unverified. The CLI is not
  required to install the SDK or generate a package.
- The guided commands read `.env` from the working directory when present.
  Provider and Jira credentials use environment variables; OpenMetadata also
  supports Keychain references. Connection YAML stores references, not secrets.
  Jira and metadata access require their own configured permissions.
- The optional `contracts` extra installs `datacontract-cli` on Python 3.8–3.12.
  On Python 3.13 and later use a compatible separate environment and expose its
  `datacontract` executable on `PATH` for external contract validation.

## Verification and limitations

The release test suite uses mocks and opt-in live checks for external services.
One synthetic Product Holdings handover was generated with OpenAI, enriched with
read-only OpenMetadata 2.1.0 evidence, validated with OpenSpec CLI 2.2.0 and
datacontract-cli 1.2.11, and delivered to Jira Cloud. The linked synthetic
product's preserved contract was integrity checked, not schema validated by
OpenMetadata. ODPS-to-ODCS alignment could not be assessed without an independent
ODPS dataset schema. The result retained unresolved fields and decisions. An
earlier model response was rejected by discovery-concept validation; its exact
cause was not captured. Other models, deployments, versions, permissions and
catalog completeness require separate verification. Candidate mappings and
generated business claims require human and domain review before implementation
or use.

See the [handover guide](docs/integrations/handoff.md),
[OpenMetadata guide](docs/integrations/openmetadata.md) and [changelog](CHANGELOG.md).
Previous release notes are retained for [0.8.0](docs/releases/0.8.0.md) and
[0.7.0](docs/releases/0.7.0.md).
