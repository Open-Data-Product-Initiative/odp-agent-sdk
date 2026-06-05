# Generate Minimal ODPS Product YAML

Create one full ODPS OpenDataProduct YAML document from extracted facts and
source documents.

Output rules:

- Return valid YAML only.
- Return exactly one OpenDataProduct document.
- Do not include Markdown fences or explanatory prose.
- Do not return an ODPC `productReference` fragment.
- Use stable machine-readable identifiers.
- Use `dataset` as the product type unless facts explicitly name another valid
  ODPS product type.
- Use `public` visibility and `draft` status only when the facts do not provide
  better values.
- Keep the document minimal. Do not invent `SLA`, `dataQuality`,
  `pricingPlans`, `license`, `dataAccess`, `dataHolder`, `contract`,
  `paymentGateways`, or `productStrategy`.

Required shape:

```yaml
schema: https://opendataproducts.org/v4.1/schema/odps.json
version: "4.1"
product:
  details:
    en:
      productID: airport-operations-performance
      name: Airport Operations Performance
      visibility: public
      status: draft
      type: dataset
```

Extracted facts:

```yaml
{product_facts}
```

Source documents:

```text
{source_documents}
```
