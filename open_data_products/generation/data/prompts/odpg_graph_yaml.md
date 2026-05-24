# Generate ODPG Graph YAML

Create ODPG graph YAML that connects the generated fragments.

Output rules:

- Return valid YAML only.
- Return exactly one YAML document.
- Do not use YAML document separators such as `---`.
- Return a full ODPG graph document with `schema`, `version`, `kind: Graph`,
  and `graph`.
- Use `schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml` and
  `version: "1.0"`.
- Include `graph.metadata.id`, `graph.metadata.name.en`, and
  `graph.metadata.description.en`.
- Generate graph nodes for all data products, use cases, business objectives,
  and signals when they are supported by the source documents.
- Every node must use `id`, `type`, and `$ref`. Do not use `label` instead of
  `type`.
- Use `$ref` values that point to the generated artifact files:
  `product_reference_<id>.yaml`, `use_case_<id>.yaml`,
  `business_objective_<id>.yaml`, and `signal_<id>.yaml`.
- Do not leave `$ref` empty.
- Generate edges only for relationships supported by the source documents.
- Every edge must use `from`, `to`, `type`, and `confidence`. Do not use
  `source`, `target`, or `label` instead of ODPG edge fields.
- Before returning YAML, check that every edge `from` and `to` value appears in `graph.nodes`.
- Use stable node identifiers that match the generated fragment identifiers.
- Prefer ODPG relationship types such as `dependsOn`, `supports`, `measures`,
  `impacts`, `contributesTo`, `uses`, and `relatedTo` when they accurately
  describe the source material.
- Use `confidence: high`, `confidence: medium`, or `confidence: low`.
- Do not include Markdown fences or explanatory prose.

Schema-valid example shape:

```yaml
schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: "1.0"
kind: Graph
graph:
  metadata:
    id: airports-flights-generation-graph
    name:
      en: Airports and Flights Generation Graph
    description:
      en: Relationships between generated airport data products, use cases, objectives, and signals.
  nodes:
    - id: airport-operations-performance
      type: DataProduct
      $ref: product_reference_airport-operations-performance.yaml
    - id: flight-delay-risk-monitoring
      type: UseCase
      $ref: use_case_flight-delay-risk-monitoring.yaml
  edges:
    - from: flight-delay-risk-monitoring
      to: airport-operations-performance
      type: dependsOn
      confidence: high
```

Source documents:

```text
{source_documents}
```
