# Extract ODPS Product Facts

Return evidence facts as valid YAML from the source documents.

Output rules:

- Return valid YAML only.
- Do not include Markdown fences or explanatory prose.
- Extract facts that are supported by the source text.
- Do not draft missing ODPS components in this step.
- Use `evidenceGaps` for important missing details.

Required shape:

```yaml
product:
  productID: stable-product-id
  name: Product Name
  valueProposition: Short value statement when supported
  description: Short description when supported
  visibility: public
  status: draft
  type: dataset
signals:
  - Useful source clue
evidenceGaps:
  - Missing pricing terms
```

Source documents:

```text
{source_documents}
```
