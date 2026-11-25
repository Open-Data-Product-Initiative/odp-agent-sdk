# Persistent OpenMetadata banking PoC

The six fictional business briefs are preserved unchanged in `sources/`. The
`products/` files are SDK-generated ODPS 4.1 drafts, with descriptions enriched
from the source overview, business need and purpose. The documents describe a
proposed proof of concept, not a production contract. They contain metadata,
not customer records.

From the repository root, with a local Ollama server and `qwen2.5:latest`:

```sh
python3 -m open_data_products.cli generate \
  --provider ollama --model qwen2.5:latest \
  --input tests/fixtures/openmetadata_banking_poc/sources \
  --kind odps-product --profile minimal --odps-version 4.1 \
  --prompts tests/fixtures/openmetadata_banking_poc/prompts \
  --output tests/fixtures/openmetadata_banking_poc/products --json
python3 tests/fixtures/openmetadata_banking_poc/enrich_descriptions.py
python3 -m pytest tests/test_openmetadata_banking_poc.py -q
```

Generation does not overwrite existing drafts unless `--overwrite` is passed;
review new output before replacing the stored drafts. Model output can vary.
The explicit `--odps-version 4.1` option requests a newly generated 4.1 document
because the OpenMetadata create adapter accepts 4.1. The local prompt adds
banking-specific requirements such as private visibility; it is not needed to
select the version. No ODPS version conversion is performed.

Inspect reviews and check for existing products (no writes):

```sh
python3 tests/fixtures/openmetadata_banking_poc/run_case.py \
  --config examples/integrations/connections.yaml \
  --profile openmetadata --domain SDKIntegrationTest
```

Add `--execute` only when persistent creation is intended. The runner checks
every product ID for existing candidates, executes reviewed SDK CLI creates,
and checks native retrieval, listing and search. It never deletes products.
The authenticated OpenMetadata account is assigned as owner by default; use
repeatable `--owner user:NAME` or `--owner team:FQN` to choose other owners,
and repeatable `--tag CLASSIFICATION.TAG` to assign existing tags.
Results are recorded in ignored `live-results.local.json`; if a create has an
unknown outcome or verification fails, inspect the target and that file before
retrying. Candidate lookup is permission-limited and does not eliminate races.
Use `--results-output PATH` to record a separate run without replacing an earlier
result file. Protect the chosen file, since it contains marketplace metadata.
The optional `ODPS_BANKING_POC_PERSISTENT_TEST=1` pytest case also creates
persistent products and intentionally performs no cleanup; it refuses known
existing candidates. Use only an explicitly selected write profile and domain.

To verify the existing six products again without creating or deleting them:

```sh
ODPS_BANKING_POC_VERIFY_TEST=1 \
ODPS_INTEGRATION_CONFIG=examples/integrations/connections.yaml \
ODPS_INTEGRATION_READ_PROFILE=openmetadata \
ODPS_INTEGRATION_TEST_DOMAIN=SDKIntegrationTest \
python3 -m pytest tests/test_openmetadata_banking_poc.py::test_live_verify_existing_banking_product -q
```

To compare the saved ODPS drafts with the six existing marketplace products
without writing to OpenMetadata:

```sh
python3 tests/fixtures/openmetadata_banking_poc/run_case.py \
  --config examples/integrations/connections.yaml \
  --profile openmetadata --domain SDKIntegrationTest \
  --compare-existing --comparison-output banking-comparison.json
```

The report includes source validation, native and export provenance and
validation, timestamps, and field-level findings. It writes a new local JSON
file and never overwrites an existing one. Reported source and platform values
may contain business metadata; keep the report appropriately protected.

OpenMetadata imports only a subset of ODPS. The original briefs retain the
proposed ownership, restrictions, quality, service and relationship context;
creation does not establish that those controls or relationships exist in
OpenMetadata, that a product is approved, or that data is available.
