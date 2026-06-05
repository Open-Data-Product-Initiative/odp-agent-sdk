# Assemble ODPS Product YAML

Assemble one valid ODPS OpenDataProduct YAML document from the minimal ODPS
document and drafted component YAML.

Output rules:

- Return valid YAML only.
- Return exactly one OpenDataProduct document.
- Keep the existing `schema`, `version`, and required `product` fields.
- Add drafted components directly under `product`.
- Preserve component object/array shapes. Do not collapse components to scalar
  strings.
- Keep `SLA` and `dataQuality` dimensions limited to the ODPS dimension names
  shown in the drafted components. Do not add invented nested rule, monitoring,
  scope, or support fields while assembling.
- Preserve ODPS schema component shapes: `SLA.declarative` and
  `dataQuality.declarative` are arrays. Do not create `profiles` under either
  component.
- Preserve pricing plan references to named packages with `paymentGateway`,
  `dataQuality`, `SLA`, and `access` objects. Do not create pricing `$ref`
  values ending in numeric indexes such as `/0`; use named endings such as
  `default`, `premium`, or `API`.
- Do not include `reviewNotes`, `evidenceGaps`, or `draftedComponents` in the
  final ODPS YAML document.
- Do not include Markdown fences or explanatory prose.

Minimal ODPS document:

```yaml
{minimal_odps}
```

Drafted components:

```yaml
{component_draft}
```

Extracted facts:

```yaml
{product_facts}
```

Source documents:

```text
{source_documents}
```
