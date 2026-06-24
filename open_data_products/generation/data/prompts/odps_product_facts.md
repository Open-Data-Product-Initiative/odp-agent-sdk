# Extract ODPS Product Facts

Return evidence facts as valid YAML from the source documents.

Output rules:

- Return valid YAML only.
- Do not include Markdown fences or explanatory prose.
- Extract facts that are supported by the source text.
- Do not draft missing ODPS components in this step.
- Keep source-backed facts separate from SDK fallback defaults. Do not list a
  fallback as a product fact unless the source text supports it.
- Use `evidenceGaps` for important missing details.

Required shape:

```yaml
product:
  productID: stable-product-id
  name: Product Name
  valueProposition: Short value statement when supported
  description: Short description when supported
  visibility: null
  status: null
  type: null
signals:
  - Useful source clue
inferredDefaults:
  visibilityWhenMissing: public
  statusWhenMissing: draft
  typeWhenMissing: dataset
evidenceGaps:
  - Missing pricing terms
```

Contrast examples:

```yaml
# Unsupported visibility stays null, not public.
product:
  productID: airport-operations-performance
  name: Airport Operations Performance
  visibility: null
  status: null
  type: null
inferredDefaults:
  visibilityWhenMissing: public
  statusWhenMissing: draft
  typeWhenMissing: dataset
evidenceGaps:
  - Source does not state visibility, lifecycle status, or product type.
```

```yaml
# Supported visibility is copied as a fact.
product:
  productID: airport-operations-performance
  name: Airport Operations Performance
  visibility: internal
  status: production
  type: dataset
evidenceGaps: []
```

Source documents:

```text
{source_documents}
```
