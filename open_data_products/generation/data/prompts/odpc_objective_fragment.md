# Generate ODPC Business Objective Fragments

Create ODPC business objective YAML fragments from the source documents.

Output rules:

- Return valid YAML only.
- Return exactly one YAML document with a top-level `businessObjectives` list.
- The document root must be a mapping. Do not start the YAML with
  `- businessObjectives:`.
- Do not use YAML document separators such as `---`.
- Generate exactly one business objective fragment for this source document,
  not a full catalog.
- Each item must follow the ODPC BusinessObjective shape with `id`, nested
  `name: {en: ...}`, and nested `description: {en: ...}`.
- Do not use dotted keys such as `name.en` or `description.en`.
- Use optional ODPC fields such as `owner`, `kpis`, `timeframe`, `status`, and
  `priority` only when supported by the source text.
- Do not include use cases, signals, or products in this output.
- Do not use `linkedUseCases`, `dataProducts`, or other relationship fields in
  this output. Those relationships belong in ODPG graph YAML.
- Capture the objective name, priority, owner, timeframe, target, metrics, and
  linked use cases when they are present in the source documents.
- Preserve numeric targets exactly as stated.
- Do not include Markdown fences or explanatory prose.

Schema-valid example shape:

```yaml
businessObjectives:
  - id: reduce-departure-delay-minutes
    name:
      en: Reduce Departure Delay Minutes
    description:
      en: Reduce average departure delay minutes by 12 percent during the 2026 Q3 summer peak.
    owner:
      role: Head of Airport Operations
    expectedOutcomes:
      - en: Improve passenger satisfaction, stand availability, and airline partner service levels.
    kpis:
      - id: average-departure-delay-minutes
        name:
          en: Average Departure Delay Minutes
        unit: minutes
        target:
          value: 12
          date: "2026-09-30"
    timeframe:
      startDate: "2026-07-01"
      endDate: "2026-09-30"
    status: active
    priority: high
```

Source documents:

```text
{source_documents}
```
