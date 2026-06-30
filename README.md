# Open Data Products Python SDK

[![PyPI version](https://badge.fury.io/py/open-data-products.svg)](https://badge.fury.io/py/open-data-products)
[![Python Support](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://github.com/Open-Data-Product-Initiative/odps-python)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

`open-data-products` is a Python SDK and CLI for the
[OpenDataProducts.org](https://opendataproducts.org/) standards family:
ODPS, ODPC, ODPG, ODPV, and ODPR.

Use it to validate data product documents, build catalogs and graphs, inspect
portfolio source intake, run LLM-assisted generation workflows, expose a local
MCP server, and give AI agents a consistent standards-aware API.

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

Python 3.8 or newer is required.

## What It Provides

| Area | Capabilities |
|------|--------------|
| Cross-spec API | Detect, load, validate, explain, summarize, and resolve references across ODPS, ODPC, ODPG, and ODPV documents |
| CLI | Run validation, generation, catalog, graph, vocabulary, portfolio, OKF, contract, resource, manifest, and MCP workflows through `open-data-products` |
| Portfolio workflows | Build, refresh, sync, render, localize, explain, and inspect portfolio workspaces from objectives, use cases, signals, and product source lanes |
| Document intake | Read Markdown, text, YAML, JSON, EML, MSG with the `email` extra, DOCX, PPTX, PDF, CSV, and XLSX source files for portfolio workflows |
| Agent surfaces | Run a safe-class stdio MCP server and generate an ARWS-compatible agent manifest |
| LLM generation | Generate ODPC fragments, ODPG graphs, and ODPS product YAML from source notes using local or hosted providers |
| Data Contracts | Resolve ODPS contract references, validate external contracts through optional `datacontract-cli`, extract schemas, check alignment, and generate reports |

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
surface, and the Data Contract CLI project for the optional contract execution
engine.

## License

Apache License 2.0. See `LICENSE` for details.
