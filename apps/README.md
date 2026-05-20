# Sample Apps

Small runnable Python applications built on top of the Open Data Products SDK.
They are examples for local testing and experimentation, not package entry
points.

## ODP Document Inspector CLI

Inspect any ODPS, ODPC, ODPG, or ODPV YAML/JSON document:

```bash
python apps/document_inspector/cli.py examples/demo_product.yaml
python apps/document_inspector/cli.py examples/demo_product.yaml --json
```

The app reports detected spec and kind, validation status, a compact
explanation, discovered references, and bundled SDK resources.

## ODPV Vocabulary Finder CLI

Search bundled ODPV vocabulary terms with natural-language queries:

```bash
python apps/vocabulary_finder/cli.py "customer churn reusable data offering"
python apps/vocabulary_finder/cli.py "governance policy risk" --limit 5 --json
```

The app reports matching term IDs, sections, scores, URIs, definitions,
matched fields, and related terms.

## ODPS Pricing 402 Builder CLI

Build an HTTP 402 payment envelope from an ODPS product with pricing plans:

```bash
python apps/pricing_402_builder/cli.py apps/pricing_402_builder/priced_product.yaml
python apps/pricing_402_builder/cli.py apps/pricing_402_builder/priced_product.yaml --json
```

The app reports the ODPS product ID, whether pricing is available, and the
generated 402 status and payment headers.
