# Open Data Products Python SDK 0.8.0 Release Notes

This feature release adds an experimental OpenMetadata integration to the SDK
and its CLI. Existing public APIs and Python 3.8 support are retained from
Python 3.8.1 onward. The
integration was tested against one OpenMetadata **2.1.0** deployment; support
for other versions has not been established.

## From business documents to OpenMetadata products

- Generate ODPS product drafts from Markdown or Word business documents using
  an existing configured LLM provider. Select ODPS `4.1` explicitly for
  OpenMetadata creation; the default generation target is 4.2. The SDK does
  not convert existing documents between versions.
- Select a named YAML connection, discover products and domains, retrieve native
  metadata or ODPS export, and compare the retrieved product with its reviewed
  ODPS source. Comparisons include validation, provenance, timestamps and
  field-level differences. CLI list and search return ODPC 1.0 catalogs, and
  full catalogs can be exported as YAML or JSON. This changes the earlier CLI
  list and search JSON shape; native Python listing and search APIs remain.
- Copy a bundled connection template into a user-owned file with
  `open-data-products config integrations --copy-to connections.yaml`. Quoted
  multiword domain FQNs are preserved in product operations.
- Use `open-data-products openmetadata products` to review and create a file or
  folder of ODPS documents, and to list, search, retrieve, compare, update or
  delete products. Guided creation checks for possible duplicates, skips
  ineligible files, and requests one terminal confirmation. Retrieval, update,
  delete and comparison identify the target by UUID. Scripted writes retain the explicit
  review digest and execution mechanism.
- Create domains, select product domains, and assign existing OpenMetadata
  users, teams and classification tags. Unless an owner is specified, creation
  uses the account associated with the configured token. Owner and tag
  assignment after product creation is a separate operation and may fail after
  the product has been created.

## Contracts and source fidelity

- Import ODCS 3.1 contracts for existing products or from inline or linked
  contracts in supported ODPS sources. On the tested deployment, the SDK
  imports a schema-free native projection and retains the complete source
  contract and its version in contract metadata for SDK retrieval.
  OpenMetadata does not validate that preserved schema as its native product
  contract schema; native ODCS export does not reconstruct the preserved source.
- The tested ODPS exports contain a numeric `updated` timestamp that fails SDK
  ODPS validation. Retrieval exposes findings; an explicit option can derive a
  UTC date while keeping the original and recording the loss of precision.
  Invalid exports can only be saved when strict validation is disabled.
- ODPC catalog `productVersion` is the OpenMetadata entity metadata revision,
  explicitly labelled as such; it is not an independently verified product
  release version. The catalog's model reference points to the native platform
  API, not to a claim of valid ODPS export.

## Boundaries and verification

- Only mapped fields are imported into OpenMetadata; review and comparison
  reports identify omissions and unverified values. A validated metadata
  record does not prove that data, business claims, controls or contracts are
  verified or approved.
- Writes require a write-enabled connection and platform permission. A review
  digest binds execution to the reviewed input; interrupted or ambiguous
  outcomes are reported without automatic retries. Permanent product deletion
  is recursive. Revision checks request a platform precondition, whose
  enforcement depends on the deployment.
- Connection configuration references a token in the process environment,
  like the OpenAI provider's `OPENAI_API_KEY`; the SDK does not automatically
  load `.env` files. Tokens and local connection files must stay out of Git.
- Live tests are opt-in. The six fictional banking briefs and their reviewed
  drafts are retained as fixtures; the persistent banking workflow deliberately
  does not delete its products.

See the [OpenMetadata integration guide](docs/integrations/openmetadata.md)
and [changelog](CHANGELOG.md) for command examples and details. Previous release
notes are retained in [0.7.0 release notes](docs/releases/0.7.0.md).
