# DCAT Catalog Intelligence

The SDK can inspect a supplied W3C DCAT catalog before an organisation adopts
ODPS. It inventories source metadata, reports evidence-bounded reuse and
metadata gaps, and can generate selected ODPS 4.2 drafts.

DCAT 3 is the principal vocabulary. DCAT-AP 3.0.1 is the primary European
application-profile target. Parsing DCAT terms from an older DCAT-AP or national
extension is useful compatibility, not a DCAT-AP 3.0.1 conformance claim.

## Analyze a catalog

```bash
open-data-products portfolio discover-dcat ./catalogs \
  --output ./catalog-intelligence.html --json
```

Inputs may be a local RDF/XML, Turtle, JSON-LD, N-Triples, or N3 file; a
directory containing those files; a local file URI; or one public HTTP(S)
document. Retrieval is bounded, uses a timeout, rejects credential-bearing URLs,
does not crawl linked resources, and rejects remote JSON-LD contexts.

The structured result preserves source facts separately from inferences and
proposals. It includes Catalog, Dataset, DatasetSeries, Distribution, DataService,
and CatalogRecord inventory entries; language-tagged titles/descriptions;
publisher, themes, keywords, distributions, service endpoints, and declared
relationships. A distribution is not treated as an independent dataset.

The self-contained HTML report has an overview, searchable catalog explorer,
evidence-labelled findings, and product opportunities. It is intentionally a
decision-support report rather than a graph application.

## Generate selected product drafts

```bash
open-data-products product wrap-dcat \
  --input ./catalog.ttl \
  --resource https://catalog.example/datasets/air-quality \
  --output ./air-quality.yaml --json
```

The source resource must be explicitly selected. A Dataset, DatasetSeries, or
DataService can be selected; the command never converts a whole catalog by
default. For more than one selected resource, repeat `--resource` and provide an
output directory:

```bash
open-data-products product wrap-dcat --input ./catalog.ttl \
  --resource https://catalog.example/datasets/air-quality \
  --resource https://catalog.example/datasets/water-quality \
  --output ./drafts/
```

Drafts are private and have status `draft`. The converter maps only schema-valid
ODPS 4.2 fields: identifier/title/description, keywords, themes, and explicit
credential-free HTTP(S) access endpoints. `dcat:accessURL` is kept distinct from
`dcat:downloadURL`; a URL alone does not establish authentication, availability,
or service guarantees. DCAT does not supply a data contract, so the converter
does not invent one.

Each result contains a mapping report: mapped fields, source values not
represented, defaults, missing business context, warnings, ODPS validation, and
the draft ODPV DCAT profile boundary. It does not treat the DCAT publisher as an
approved product owner or claim DCAT/ODPS semantic equivalence.

## Optional AI enrichment

```bash
open-data-products product wrap-dcat --input ./catalog.ttl \
  --resource https://catalog.example/datasets/air-quality \
  --output ./air-quality.yaml --enrich --config generation.config.yaml
```

`--enrich` proposes a business description and discovery tags. `--enrich
--full-draft` also returns wider business proposals in the conversion report.
Every generated field is marked `proposed` and requires review; generated wording
never becomes a source fact, approval, ownership assertion, demand signal, or
operational commitment.

## Python and MCP

```python
from open_data_products import discover_dcat_catalog, wrap_dcat_resource

catalog = discover_dcat_catalog("catalog.ttl")
draft = wrap_dcat_resource(
    "catalog.ttl", "https://catalog.example/datasets/air-quality"
)
assert draft.validation.valid
```

MCP exposes `discover_dcat_catalog` as a safe inspection tool and
`wrap_dcat_resource` as a state-changing artifact-writing tool. The latter takes
an explicit `source`, `resource`, and `output` and redacts local paths in its
response.

## Operational catalog snapshots

Use `scripts/acquire_dcat_samples.py` to create bounded, reproducible samples
from the European Data Portal, Germany GovData, Finland Avoindata.fi, or
Switzerland opendata.swiss. It records selected IRIs, hashes, source URL,
retrieval time, declared profile, and reuse/license hints. It never retrieves
dataset contents. Do not commit third-party snapshots until their redistribution
rights have been reviewed; CI uses local synthetic fixtures and never requires
network access.
