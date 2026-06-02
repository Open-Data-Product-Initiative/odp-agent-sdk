# Infer ODPG Edges from ODPC Fragments

Infer directional ODPG graph edges between nodes derived from ODPC fragments.

Output rules:

- Return valid YAML only.
- Return exactly one YAML document.
- Return only an `edges` object.
- Do not use YAML document separators such as `---`.
- Do not include Markdown fences or explanatory prose.
- Do not create nodes.
- Do not invent node ids.
- Every edge `from` and `to` value must exactly match one provided node id.
- Every edge must use `from`, `to`, `type`, and `confidence`.
- Use `confidence: high`, `confidence: medium`, or `confidence: low`.
- Prefer ODPG relationship types such as `dependsOn`, `supports`, `measures`,
  `contributesTo`, `impacts`, `uses`, and `relatedTo` when they accurately
  describe the fragment content.
- Generate only relationships supported by the ODPC fragment content.
- If no relationship is supported by the content, return `edges: []`.

Schema-valid output shape:

```yaml
edges:
  - from: retention-use-case
    to: customer-analytics-product
    type: dependsOn
    confidence: high
```

Available nodes:

```text
{nodes}
```

ODPC fragment context:

```text
{odpc_fragments}
```
