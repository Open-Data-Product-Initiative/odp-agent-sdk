# Open Data Products Python SDK

[![PyPI version](https://img.shields.io/pypi/v/open-data-products.svg)](https://pypi.org/project/open-data-products/)
[![Python Support](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://github.com/Open-Data-Product-Initiative/odps-python)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/open-data-products?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/open-data-products)

`open-data-products` is a Python SDK and CLI for the
[OpenDataProducts.org](https://opendataproducts.org/) standards family:
ODPS, ODPC, ODPG, ODPV, and ODPR.

Use it to create and validate data product specifications from business needs,
build catalogs and graphs, and explore portfolio inputs. Connect to OpenMetadata
to discover evidence and manage product metadata, or prepare a coding-assistant
handover and deliver it to Jira. The SDK also supports LLM-assisted generation,
a local MCP server, and a standards-aware API for AI agents.

## Install

```bash
pip install open-data-products
```

Optional extras:

```bash
# Outlook .msg intake support
pip install "open-data-products[email]"

# Data Contract CLI integration
pip install "open-data-products[contracts]"

# Embedded llama.cpp generation support
pip install "open-data-products[llama-cpp]"

# Development tools
pip install "open-data-products[dev]"
```

Python 3.8.1 or newer is required.

The experimental [OpenMetadata integration](docs/integrations/openmetadata.md)
supports product discovery, ODPS export, reviewed creation and updates, domain
management, and contract attachment. It was tested against one OpenMetadata
2.1.0 deployment. Other versions and their export behavior require verification.

## What It Provides

| Area | Capabilities |
|------|--------------|
| Cross-spec API | Detect, load, validate, explain, summarize, and resolve references across ODPS, ODPC, ODPG, and ODPV documents |
| CLI | Run validation, generation, catalog, graph, vocabulary, portfolio, OKF, contract, resource, manifest, and MCP workflows through `open-data-products` |
| Portfolio workflows | Build, refresh, sync, render, localize, explain, and inspect portfolio workspaces from objectives, use cases, signals, and product source lanes |
| Document intake | Read Markdown, text, YAML, JSON, EML, MSG with the `email` extra, DOCX, PPTX, PDF, CSV, and XLSX source files for portfolio workflows |
| Agent surfaces | Run a stdio MCP server with reviewed handover and Jira tools, and generate an ARWS-compatible agent manifest |
| LLM generation | Generate ODPC fragments, ODPG graphs, and ODPS product YAML from source notes using local or hosted providers |
| OpenMetadata | Connect, review and create products, manage domains, compare retrieved metadata, and attach ODCS contracts |
| Coding-assistant handover | Prepare OpenSpec planning drafts, enriched ODPS and a separate ODCS draft from business documents, with optional metadata discovery |
| Jira Cloud | Review and deliver handover packages, or create general issues through a reusable Jira adapter |
| Data Contracts | Wrap ODCS 3.0/3.1/3.2 contracts into conservative ODPS 4.2 drafts, resolve ODPS contract references, validate external contracts through optional `datacontract-cli`, extract schemas, check alignment, and generate reports |
| DCAT Catalog Intelligence | Inspect supplied DCAT RDF with evidence-bounded findings, render an offline report, and convert explicitly selected resources to private ODPS 4.2 drafts |
| DPROD interoperability | Validate explicit OMG DPROD 1.0 Beta 2 products offline, create ODPS 4.2 drafts, and export deterministic DPROD RDF with loss reports |

## Quick CLI Examples

Most commands print human-readable output by default. Add `--json` for CI,
scripts, MCP clients, and agents.

Run the SDK through Python:

```bash
# Validate and inspect standards documents
python3 -m open_data_products.cli validate examples/product.yaml
python3 -m open_data_products.cli explain examples/product.yaml --json
python3 -m open_data_products.cli refs examples/product.yaml --json
python3 -m open_data_products.cli summary examples/product.yaml

# Discover bundled schemas, prompts, vocabulary records, and guidance
python3 -m open_data_products.cli resources --json
python3 -m open_data_products.cli resources --id generation.prompt.system --json

# Agent surfaces
python3 -m open_data_products.cli manifest --json
python3 -m open_data_products.cli serve
```

After installation, the console script provides the same commands:

```bash
open-data-products validate examples/product.yaml
open-data-products explain examples/product.yaml --json
```

Prepare a coding-assistant handover from one business document or a folder:

The handover and Jira commands require SDK 0.9.0 or later. Check the installed
version with `open-data-products --version`.

```bash
open-data-products handover prepare --input business-briefs/ --json > results.json
# Add --discovery CONNECTION_NAME for optional metadata discovery.
open-data-products jira deliver --input handoffs/data-product-WORKSPACE
```

Use the workspace returned in `results.json`. Preparation and Jira delivery are
separately reviewed; the resulting OpenSpec and data product artifacts are
unapproved drafts. See the [handover guide](docs/integrations/handoff.md) for
provider, discovery and Jira setup, evidence limits and review requirements.

Create OpenMetadata products from reviewed ODPS 4.1 documents:

```bash
# Copy the bundled example into your project, then edit its endpoint.
open-data-products config integrations --copy-to connections.yaml
# Set OPENMETADATA_TOKEN in the environment, then select the connection.
open-data-products connect openmetadata --config connections.yaml

# Create new 4.1 drafts from business documents using a configured provider.
open-data-products generate --input business-brief.md --kind odps-product \
  --odps-version 4.1 --output products/

# Review the folder and confirm creation in OpenMetadata.
open-data-products openmetadata products create ./products --domain "Retail Banking"
open-data-products openmetadata products list
open-data-products openmetadata products search "campaign"
open-data-products openmetadata products export --output catalog.yaml

# Review changes to an existing product by UUID.
open-data-products openmetadata products update --id PRODUCT_UUID \
  --input product.yaml
```

The connection file references an environment variable, like `OPENAI_API_KEY`;
the standalone platform commands do not automatically load `.env`. Guided
handover preparation and Jira delivery do read `.env` from the working directory
when present. The platform command requires a
write-enabled profile and appropriate platform permissions. It checks for
possible duplicates and reports fields that might not be imported; generated
metadata is not evidence of approval. See the [integration guide](docs/integrations/openmetadata.md)
for setup, comparison, update and deletion, contract limitations, and JSON
automation.

Replace `Retail Banking` with the domain's exact OpenMetadata fully qualified
name (FQN); quote values with spaces. The FQN may differ from the display name.
For updates, the input product ID must match the OpenMetadata product name.
The review shows which source fields are applied; currently the file supplies
the title and description, while other ODPS fields are not applied.

OpenMetadata list, search and catalog export produce validated ODPC 1.0
catalogs. The catalog's `productVersion` records the OpenMetadata metadata
revision and labels its origin; it is not an independently verified product
release version.

Wrap an ODCS contract without changing its source:

```bash
open-data-products product wrap-contract --input contracts/orders.yaml \
  --output products/orders.yaml --json
```

The resulting ODPS document is a private draft with reported defaults and
missing business evidence. It uses the original contract as an external
reference unless `--inline-contract` is selected.

Choose the draft depth with optional enrichment:

```bash
# Minimal technical wrapper
open-data-products product wrap-contract --input contracts/orders.yaml --output products/orders.yaml

# Business description and discovery tags
open-data-products product wrap-contract --input contracts/orders.yaml --output products/orders.yaml --enrich

# Rich ODPS draft
open-data-products product wrap-contract --input contracts/orders.yaml --output products/orders.yaml --enrich --full-draft
```

See [Data Contract workflows](docs/user/data-contracts.md) for the generated
fields and provider configuration.

Inspect a DCAT catalog, then convert only a selected resource:

```bash
open-data-products portfolio discover-dcat ./catalogs --output catalog-intelligence.html
open-data-products product wrap-dcat --input catalog.ttl \
  --resource https://catalog.example/datasets/air-quality --output air-quality.yaml
```

See [DCAT Catalog Intelligence](docs/user/dcat-catalog-intelligence.md) for
format support, evidence boundaries, conversion mapping, and optional AI proposals.

Validate an explicit DPROD Beta 2 product, create an ODPS draft, or export an
ODPS definition as DPROD Turtle and JSON-LD:

```bash
open-data-products dprod-validate product.ttl --json
open-data-products product wrap-dprod --input product.ttl --resource https://example.test/products/air --output air.yaml
open-data-products product export-dprod --input air.yaml --output air
```

See [DPROD interoperability](docs/user/dprod-interoperability.md) for the
normative namespace, offline SHACL profile, mapping constraints, and loss
boundaries.

Discover technical portfolio evidence from a contract repository without
declaring any contract to be an approved data product:

    open-data-products portfolio discover-contracts contracts/ \
      --output portfolio-discovery/ --json

The command writes a normalized contract inventory, a source-linked Data
Contract Intelligence artifact, review-only typed opportunities, and a static
HTML report. The report separates standalone product candidates, multi-contract
boundary proposals, and rationalisation opportunities; it also lists contracts
without a current opportunity signal. Duplicate and schema-overlap findings are
technical evidence, not approved product boundaries.

Without `--json`, the command prints the same inventory, interface analysis,
priority evidence, typed opportunities, and no-current-signal contracts as the
HTML report. Use `--json` for the same information in structured form.

Portfolio source intake can be inspected without calling an LLM:

```bash
python3 -m open_data_products.cli portfolio intake \
  --objectives sources/objectives/ \
  --use-cases sources/use-cases/ \
  --signals sources/signals/ \
  --products sources/products/ \
  --config generation.config.yaml \
  --json
```

Portfolio build uses the same source lanes and prompt budget controls:

```bash
python3 -m open_data_products.cli portfolio build \
  --objectives sources/objectives/ \
  --use-cases sources/use-cases/ \
  --signals sources/signals/ \
  --products sources/products/ \
  --output generated/portfolio/
```

## LLM Generation

Generation defaults to local Ollama-compatible settings, and can also use
embedded llama.cpp, OpenAI-compatible local servers, NVIDIA NIM, Claude, and
hosted providers configured in `generation.config.yaml`.

```bash
open-data-products config generation --copy-to generation.config.yaml
open-data-products config generation --config generation.config.yaml --check

open-data-products generate \
  --config generation.config.yaml \
  --input source_docs/products/ \
  --kind product-reference \
  --output generated/
```

## Documentation

The full SDK guide that used to live in this README is now here:

- [Full SDK guide](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/docs/user/full-sdk-guide.md)

Focused user guides:

- [Command guide](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/docs/user/commands.md)
- [Portfolio intake guide](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/docs/user/portfolio-intake.md)
- [LLM generation](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/docs/user/generation.md)
- [Agent surface](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/docs/user/agent-surface.md)
- [Recipe workflows](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/docs/user/recipe-workflows.md)
- [Data Contract workflows](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/docs/user/data-contracts.md)
- [DCAT Catalog Intelligence](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/docs/user/dcat-catalog-intelligence.md)
- [API reference](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/docs/user/API.md)

Project references:

- [Documentation index](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/docs/README.md)
- [Examples](https://github.com/Open-Data-Product-Initiative/odps-python/tree/main/examples)
- [Agent handoff](https://github.com/Open-Data-Product-Initiative/odps-python/blob/main/llms.txt)

## Development

```bash
git clone https://github.com/Open-Data-Product-Initiative/odps-python
cd odps-python
pip install -e ".[dev]"
pytest -q
```

Before publishing a package, verify the PyPI description renders:

```bash
python3 -m build
python3 -m twine check dist/*
```

## Acknowledgments

Thanks to the Open Data Product Initiative community, Chris Howard / Kitard for
the original `odps-python` foundation, devlouie for the MCP layer and agent
surface, the OpenMetadata platform, and the Data Contract CLI project for the
optional contract execution engine.

## License

Apache License 2.0. See `LICENSE` for details.
