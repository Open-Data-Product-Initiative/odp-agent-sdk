# Generate ODPS Data Product Fragments

Create ODPC product reference YAML fragments from the source documents.

Output rules:

- Return valid YAML only.
- Return exactly one YAML document with a top-level `productReferences` list.
- The document root must be a mapping. Do not start the YAML with `- productReferences:`.
- Do not use YAML document separators such as `---`.
- Generate exactly one data product reference for this source document, not a
  full catalog.
- Only create an item when the source document explicitly describes a data
  product.
- Never create `productReferences` for use cases, business objectives, or
  signals.
- Never use fields named `useCaseID`, `signalID`, or `objectiveID`.
- Every item must have `productID`, `productVersion`, and `productModel.$ref`.
- Use `type: dataset` unless the source document explicitly names another
  product delivery type.
- Each item must follow the ODPC ProductReference shape with `id`, `productID`,
  `productVersion`, nested `name: {en: ...}`, nested `description: {en: ...}`,
  and `productModel`.
- Do not use dotted keys such as `name.en` or `description.en`.
- Use `productModel.standard: ODPS`, `productModel.version: "4.1"`,
  `productModel.format: yaml`, and a stable relative `$ref` for the future ODPS
  product file.
- Use the product name, product identifier, version, status, visibility, owner,
  source systems, fields, and intended users when they are present in the
  source documents.
- Do not invent ProductReference fields such as `accessLimits`,
  `refreshCadence`, `pricing`, `SLA`, `dataQuality`, or `license`. Those belong
  in the linked ODPS product spec, not in ODPC ProductReference.
- If operational notes must be preserved on the reference, use `x-*` extension
  fields only, such as `x-accessLimits` or `x-refreshCadence`.
- Keep field names and identifiers stable and machine-readable.
- Do not include Markdown fences or explanatory prose.
- Do not create unrelated products. Do not include use cases, signals, or
  objectives in this output.

Schema-valid example shape:

```yaml
productReferences:
  - id: airport-operations-performance
    productID: airport-operations-performance
    productVersion: "1.0.0"
    name:
      en: Airport Operations Performance Data Product
    description:
      en: Internal operational analytics for flight, gate, baggage, and turnaround events.
    visibility: internal
    status: production
    type: dataset
    domains:
      - airport operations
    portfolioPriority: high
    owner:
      team: Airport Data Platform Team
    productModel:
      standard: ODPS
      version: "4.1"
      format: yaml
      $ref: products/airport-operations-performance.yaml
```

Source documents:

```text
{source_documents}
```
