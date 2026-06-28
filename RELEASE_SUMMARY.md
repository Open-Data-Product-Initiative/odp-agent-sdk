# Release Summary: 0.3.3

## Source-To-Fragment Generation

- Changed selected-kind source generation so each matching source document is
  processed in its own LLM call and emits at most one YAML artifact for the
  selected kind.
- Updated objective, use case, signal, and product-reference prompts to make
  the one-source-document-to-one-fragment contract explicit.
- Clarified the bundled source document guidance so folder generation means
  repeating the selected prompt over each source file, not combining the whole
  folder into one prompt.

## Staged Portfolio Build

- Reworked LLM-backed `portfolio build` and `portfolio refresh` source-lane
  handling to follow the fragment workflow: generate lane fragments first,
  build the ODPC catalog from fragments, infer ODPG graph edges from compact
  fragment context, then generate the Executive Summary from normalized
  portfolio evidence.
- Build and refresh JSON reports now expose staged `llmPhases` such as
  `objective`, `useCase`, `signal`, `productReference`, `graph`, and
  `executiveSummary` instead of a single raw-source `portfolio` phase.
- Kept the later portfolio assembly deterministic where possible: generated
  fragments remain the handoff surface, graph linking runs after fragments
  exist, and `portfolio sync` continues to rebuild from YAML artifacts.

## Workflow Boundary

- Kept product-reference fragments separate from full ODPS product drafts. The
  portfolio product lane now creates ODPC `ProductReference` fragments; full
  ODPS product YAML generation remains part of the dedicated generation
  workflow.

## SDK Activity Logging

- Added default-on CLI activity logging so SDK command runs leave one
  fixed-format evidence line in the resolved workspace log at
  `.open-data-products/activity.log`.
- Used Python standard-library logging with rotating file handling, avoiding a
  new third-party logging dependency.
- Logged CLI outcomes with `[SUCCESS]`, `[WARNING]`, or `[FAILED]`
  classification, canonical command ids, exit codes, duration, and redacted
  structured details.
- Added explicit `[INFO]` `llm.invoke` lines for LLM-backed CLI workflows so
  the log shows when a provider/model was invoked.
