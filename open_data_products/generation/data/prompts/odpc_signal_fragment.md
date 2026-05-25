# Generate ODPC Signal Fragments

Create ODPC signal YAML fragments from the source documents.

Output rules:

- Return valid YAML only.
- Start the response with `signals:` as the first characters.
- Do not include analysis, reasoning, notes, or sentences before the YAML.
- Return exactly one YAML document with a top-level `signals` list.
- Do not use YAML document separators such as `---`.
- Allowed enum values are strict. Replace any source wording such as
  "moderate" with `medium`.
- Generate all signal fragments supported by the source documents, not a full
  catalog.
- Each item must follow the ODPC Signal shape with `id`, `name.en`,
  `description.en`, `type`, `source.origin`, `source.method`, and `observedAt`.
- Use nested language strings, for example `name: {en: "Signal name"}` and
  `description: {en: "Signal description"}`.
- Do not use dotted keys such as `name.en` or `description.en`.
- Do not use unsupported keys such as `linkedObjectives` or `linkedUseCases`.
- The `id` must describe the same signal as `name.en`. For example, a Security
  Queue Surge Signal must use an id such as `security-queue-surge-signal`, not
  an unrelated connection or passenger id.
- Derive each signal `id` by lowercasing `name.en` and replacing spaces with
  hyphens. Do not derive the signal `id` from an affected use case, objective,
  product, or domain.
- Generate at most one signal for each source document that describes a signal.
- Preserve the source signal name when it is present.
- `impact` must be an object. Use `impact.affectedDomains` for related use
  cases, objectives, domains, or affected operational areas.
- For `strength`, `confidence`, `impact.valuePotential`, and `impact.urgency`,
  use only `low`, `medium`, `high`, or `critical` where the field allows it. Do not use `moderate`.
- Put evidence text under `evidence.summary.en` or `evidence.examples`.
- Put the recommended action under `recommendedAction.en`.
- `source.origin` must be one of `internal`, `external`, or `mixed`. Put the
  system or evidence text in `source.system`, `source.method`, or
  `source.reference`.
- Use `type: operational` when the source describes airport operations events.
- Use ISO date-time strings for `observedAt`; when only a date is provided, use
  midnight UTC for that date.
- Do not include use cases, objectives, or products in this output.
- Capture the signal name, observation date, source, strength, confidence,
  evidence, recommended action, and linked objectives or use cases when they are
  present in the source documents.
- Preserve dates, percentages, and time windows exactly as stated.
- Do not include Markdown fences or explanatory prose.

Example shape:

```yaml
signals:
  - id: turnaround-delay-spike-signal
    name:
      en: Turnaround Delay Spike Signal
    description:
      en: Turnaround delays increased for Terminal 2 departures.
    type: operational
    source:
      origin: internal
      method: ground operations event log
      system: airport operations control
    observedAt: "2026-05-20T00:00:00Z"
    strength: high
    confidence: medium
    opportunity:
      en: Review high-risk departures and coordinate with handling agents.
    impact:
      valuePotential: high
      urgency: high
      affectedDomains:
        - Flight Delay Risk Monitoring
        - Reduce Departure Delay Minutes
    evidence:
      summary:
        en: Turnaround delays increased by 18 percent.
    recommendedAction:
      en: Review high-risk departures and coordinate with handling agents.
```

Source documents:

```text
{source_documents}
```
