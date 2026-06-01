# Generate ODPS Product YAML

Create one full ODPS OpenDataProduct YAML document from the source document.

Output rules:

- Return valid YAML only.
- Return exactly one OpenDataProduct document.
- Do not include Markdown fences or explanatory prose.
- Do not return an ODPC `productReference` fragment.
- Do not return a catalog, graph, use case, objective, or signal.
- Use stable machine-readable identifiers.
- Use `dataset` as the product type unless the source document explicitly names another delivery type.
- Use `public` visibility and `draft` status only when the source document does not provide better values.
- Keep the document minimal when the source lacks detail; do not invent access URLs, owner names, pricing, or governance details.

Required shape:

```yaml
schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  productID: airport-operations-performance
  name: Airport Operations Performance
  visibility: public
  status: draft
  type: dataset
```

Source documents:

```text
{source_documents}
```
