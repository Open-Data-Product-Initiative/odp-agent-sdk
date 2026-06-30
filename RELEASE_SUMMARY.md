# Release Summary: 0.3.4

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

## Portfolio Source Document Intake

- Added mixed document intake for portfolio source lanes so objectives, use
  cases, signals, and products can be built from business source folders that
  contain `.md`, `.txt`, `.yaml`, `.yml`, `.json`, `.eml`, `.docx`, `.pptx`,
  text `.pdf`, `.csv`, and `.xlsx` files.
- Added content-first file type detection for portfolio intake, including
  RFC822 email headers, OLE `.msg` signatures, PDF headers, PNG/JPEG headers,
  CSV sniffing, and OOXML container inspection for Word, PowerPoint, and Excel.
  Extensions are now fallback hints rather than the only signal.
- Kept one user-supplied business file as one portfolio source record: a
  PowerPoint deck remains one deck source, a Word or PDF file remains one
  document source, a spreadsheet remains one workbook source, and a CSV remains
  one table source.
- Added deterministic extractors for visible PowerPoint slide text, Word
  document text, `.eml` message bodies, embedded PDF text, CSV row summaries,
  and workbook sheet summaries.
- Added optional Outlook `.msg` extraction through the
  `open-data-products[email]` extra. Without the extra, or when parsing fails,
  `.msg` files remain warning-only skipped sources with clear guidance.
- Added warning-only handling for image files (`.png`, `.jpg`, `.jpeg`) and
  image-only PDFs. These inputs are detected and reported, but the base SDK does
  not silently OCR images.

## Portfolio Intake Controls

- Added `open-data-products portfolio intake --json` so users can inspect
  source extraction, skipped inputs, lane counts, prompt budget metadata, and
  privacy masking without making an LLM call.
- Made deterministic source reduction required before LLM-backed portfolio
  calls. Reports now include the configured source budget, estimated sizes,
  chunk counts, omitted chunk counts, and budget warnings.
- Added `portfolio.sourceBudget.maxSourceChars` and
  `portfolio.sourceBudget.maxPromptChars` config settings, with default config
  comments explaining how extracted text limits relate to original document
  sizes.
- Added default-on best-effort personal data masking for LLM-backed portfolio
  intake, exposed through `obfuscate_personal_data` and controlled by
  `portfolio.privacy.obfuscatePersonalData`.
- Exposed source extraction, source budget, and source privacy metadata in
  portfolio JSON reports so generated portfolio artifacts can be traced back to
  the reduced and masked source context used for LLM calls.

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
