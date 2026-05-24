# Generate ODPC Use Case Fragments

Create ODPC use case YAML fragments from the source documents.

Output rules:

- Return valid YAML only.
- Return exactly one YAML document with a top-level `useCases` list.
- The document root must be a mapping. Do not start the YAML with
  `- useCases:`.
- Do not use YAML document separators such as `---`.
- Generate all use case fragments supported by the source documents, not a full
  catalog.
- Each item must follow the ODPC UseCase shape with `id`, nested
  `name: {en: ...}`, and nested `description: {en: ...}`.
- Do not use dotted keys such as `name.en` or `description.en`.
- Use optional ODPC fields such as `stakeholders`, `decision`,
  `expectedOutcome`, `dataNeeds`, `status`, and `priority` only when supported
  by the source text.
- Do not include signals, objectives, or products in this output.
- Capture the use case name, purpose, users, decisions, dependencies, expected
  outcomes, and metrics when they are present in the source documents.
- Link to referenced products by stable identifier when the source documents
  support that relationship.
- Do not include Markdown fences or explanatory prose.

Schema-valid example shape:

```yaml
useCases:
  - id: flight-delay-risk-monitoring
    name:
      en: Flight Delay Risk Monitoring
    description:
      en: Detect departures likely to miss target off-block time.
    domains:
      - airport operations
    stakeholders:
      - duty managers
      - airline station managers
    decision:
      en: Prioritize gate swaps, stand reassignment, staffing, and passenger communication.
    expectedOutcome:
      en: Reduce reaction time by 20 percent during the summer peak period.
    dataNeeds:
      summary:
        en: Flight, gate, stand, baggage, and estimated departure timestamps.
      items:
        - airport-operations-performance
    status: active
    priority: high
    tags:
      - departure-delay
```

Source documents:

```text
{source_documents}
```
