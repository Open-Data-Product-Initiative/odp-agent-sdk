# Merge ODPS Product Facts

Merge ODPS product fact chunks into one consolidated fact packet.

Output rules:

- Return valid YAML only.
- Do not include Markdown fences or explanatory prose.
- Preserve source-backed facts from all chunks.
- Remove duplicates and contradictions when one fact clearly supersedes another.
- Keep source-backed facts separate from SDK fallback defaults. Do not promote a
  fallback into `product` unless a fact chunk contains source evidence for it.
- Keep uncertainty in `evidenceGaps`.
- Do not draft ODPS components in this step.

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

Fact chunks:

```yaml
{fact_chunks}
```

Source chunk excerpts:

```text
{source_documents}
```
