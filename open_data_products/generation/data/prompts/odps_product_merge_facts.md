# Merge ODPS Product Facts

Merge ODPS product fact chunks into one consolidated fact packet.

Output rules:

- Return valid YAML only.
- Do not include Markdown fences or explanatory prose.
- Preserve source-backed facts from all chunks.
- Remove duplicates and contradictions when one fact clearly supersedes another.
- Keep uncertainty in `evidenceGaps`.
- Do not draft ODPS components in this step.

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

Fact chunks:

```yaml
{fact_chunks}
```

Source chunk excerpts:

```text
{source_documents}
```
