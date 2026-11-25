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
- Include description or valueProposition only when supported by the source.
- Keep the document minimal. Do not invent `SLA`, `dataQuality`,
  `pricingPlans`, `license`, `dataAccess`, `dataHolder`, `contract`,
  `paymentGateways`, or `productStrategy`.

Required shape:

```yaml
schema: https://opendataproducts.org/v4.2/schema/odps.json
version: "4.2"
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

For this fictional restricted-access banking PoC, use private visibility. Use the source front matter product_id and product_name exactly. Use draft status. Include a concise description based on the source overview and state that the product is a fictional proposed PoC. Never invent ownership, quality or service commitments.
