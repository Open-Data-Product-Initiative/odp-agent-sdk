# SDK Input Documents Expansion Plan

This note records the portfolio source-document intake plan and the implemented
base behavior. The SDK has expanded from text-oriented source lanes to common
business document inputs such as PowerPoint decks, text PDFs, Word documents,
spreadsheets, saved emails, and pasted business notes.

The immediate driver is the Maysano / SDK adoption motion: a customer may have
useful material for a data product portfolio, but that material is often in
PowerPoint, PDF, screenshots, Excel, Word, Outlook email, Confluence, Jira,
catalog exports, Teams transcripts, or meeting notes rather than clean
Markdown files.

## Current Boundary

The SDK currently supports `open-data-products generate` from text-like source
files and portfolio workflows from mixed source-lane documents.

Observed CLI behavior:

- `open-data-products generate` accepts a Markdown/text source file or folder.
- `open-data-products portfolio build` accepts source lanes for objectives,
  use cases, signals, and products.
- `open-data-products portfolio intake --json` inspects portfolio source
  extraction, warning-only files, privacy masking, and prompt budget metadata
  without making an LLM call.

Portfolio source lanes accept:

```text
.md, .txt, .yaml, .yml, .json, .eml, .docx, .pptx, .pdf, .csv, .xlsx
```

Outlook `.msg` files and image files (`.png`, `.jpg`, `.jpeg`) are detected in
portfolio lanes but skipped with warnings. Scanned or image-only PDFs also warn
because OCR and vision extraction are not enabled in the base SDK.

## Goal

Add an internal document extraction layer that lets existing SDK source
folders contain common business artifacts. Users should be able to drop files
into the same `objectives`, `use-cases`, `signals`, and `products` folders
they already use, and the SDK should detect supported file types, extract
usable text, and feed the existing generation and portfolio workflows.

The goal is not to make the SDK a general enterprise document management
system. The goal is to help users bring real business material into ODPS,
portfolio, catalog, graph, and contract workflows with less manual preparation.

## Non-Goals

- Do not store original customer documents in generated portfolio workspaces by
  default.
- Do not extract or process hidden sensitive content unless explicitly enabled.
- Do not make document ingestion part of the safe read-only MCP surface before
  the security and file-handling model is clear.
- Do not add a separate required ingestion command as the main user workflow.
  Source folders remain the user-facing contract.
- Do not promise perfect automatic classification from arbitrary files. The
  lane folder still provides the primary classification signal.

## Proposed Model

Keep the source folders as the workflow. The user does not run a separate
ingestion command first.

Example:

```bash
open-data-products portfolio build \
  --objectives sources/objectives/ \
  --use-cases sources/use-cases/ \
  --signals sources/signals/ \
  --products sources/products/ \
  --output portfolio/
```

Those folders may contain a mixed set of supported source files:

```text
sources/
  objectives/
    strategy-priorities.pptx
    quarterly-objectives.md
  use-cases/
    customer-service-workshop.docx
    sales-followup.eml
    outlook-request.msg
  signals/
    kpi-notes.xlsx
  products/
    product-whiteboard.jpg
    product-ideas.txt
```

The SDK source scanner detects each supported file type from metadata and
content signatures, extracts normalized text internally, preserves source
metadata in JSON-compatible source records, and passes compact Markdown or
plain text into the existing portfolio or generation prompt flow. File
extensions are useful hints, but they should not be the only source of truth.

The lane is determined by the folder where the file is placed. A PowerPoint
deck in `sources/objectives/` is treated as objective source material; the same
deck in `sources/products/` is treated as product source material. This keeps
classification transparent and avoids hidden automatic business decisions.

Direct `generate --input some-file.pptx --kind odps-product` can be supported
later by reusing the same internal source loader, but the first priority should
be lane-folder support for portfolio workflows.

## File Type Detection

The SDK should not rely only on file extensions. Extensions are easy to rename
or lose during exports, and some formats share container types. Detection
should combine multiple signals and record how the decision was made.

Recommended detection order:

1. **Explicit metadata**
   If the user provides a sidecar metadata file or lane manifest, trust it only
   after the parser can verify the content is compatible.

2. **Content signatures**
   Inspect magic bytes and container signatures, such as `%PDF` for PDF,
   ZIP-based Office containers for `.pptx`, `.docx`, and `.xlsx`, image
   headers for PNG/JPEG, RFC 822-style headers for `.eml`, and OLE Compound
   File signatures for Outlook `.msg`.

3. **Container inspection**
   For ZIP-based Office files, inspect internal paths such as
   `ppt/presentation.xml`, `word/document.xml`, and `xl/workbook.xml` to
   distinguish PowerPoint, Word, and Excel.

4. **Parser probe**
   Attempt a lightweight parse with the candidate extractor. A file should not
   be treated as supported unless the relevant parser can read the expected
   structure.

5. **Extension fallback**
   Use the file extension only as a final hint when content-based detection is
   inconclusive.

6. **Unknown**
   If the SDK cannot identify the file type confidently, skip the file with a
   clear warning instead of sending raw bytes or malformed text to an LLM.

The source record should include both the detected type and the evidence used:

```python
{
    "source_path": "sources/objectives/strategy-priorities",
    "declared_type": None,
    "detected_type": "pptx",
    "detection_method": "ooxml-container",
    "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "confidence": "high",
    "sha256": "...",
    "warnings": [],
}
```

Optional sidecar metadata can help when source files are ambiguous:

```yaml
---
sourceFile: strategy-priorities
sourceType: pptx
lane: objectives
title: Strategy priorities
notes: Customer supplied a deck export without file extension.
---
```

The sidecar should help routing and reporting, but it should not bypass parser
validation.

## Supported Inputs

### Implemented Portfolio Lane Inputs

Portfolio lane intake currently supports:

- `.md`
- `.txt`
- `.yaml`
- `.yml`
- `.json`
- `.docx`
- `.eml`
- `.pptx`
- `.pdf` with embedded text
- `.xlsx`
- `.csv`

Email is included because many data product ideas start as client-provider
exchanges: a customer asks for data, a provider responds with feasibility or
constraints, and the useful product shape emerges through the thread.

PowerPoint support extracts:

- slide title
- visible text boxes
- bullet text
- table text
- slide number and deck filename as metadata

PowerPoint decks remain one business source record. The extractor preserves
slide boundaries inside that record with `Slide 1:` markers, but it does not
split one deck into multiple lane sources by default. The lane folder
communicates the deck's business role: one deck can be one signal, one product
need, one objective input, or similar.

PowerPoint support should not extract speaker notes by default in v1 and should
not attempt to interpret images in v1. Speaker-note extraction and OCR can be
later optional capabilities.

Word support is conservative. It extracts:

- headings
- paragraphs
- bullet and numbered lists
- table text
- document filename as metadata

Word support should not extract comments, tracked changes, embedded files,
headers, footers, or images by default in v1. The goal is to capture useful
business text from requirements, proposals, meeting notes, and workshop
summaries, not to reproduce the full Word document.

Teams and meeting transcripts are supported when they are already text
documents, such as `.txt`, `.docx`, or pasted Markdown. The SDK does not process
audio or video recordings. Transcript handling should focus on speaker turns,
decisions, questions, requirements, candidate use cases, and follow-up actions.

Email support should be oriented toward saved business requests, stakeholder
needs, meeting follow-ups, decision notes, and product ideas. The extractor
should create one normalized source record per message or thread, with minimal
metadata and the sanitized message body.

`.eml` is handled with Python standard library email parsing. Outlook `.msg`
is handled through the optional `open-data-products[email]` extra. Without the
extra, or when parsing fails, the command skips the affected file, adds a clear
warning to the normal command log and `--json` output, and continues processing
the remaining lane sources. It must not silently skip Outlook files.

Email extraction should not include attachments by default. Attachments can be
listed in the extraction report and processed separately only when explicitly
enabled.

PDF support should be conservative. It should first support text PDFs where
embedded text can be extracted deterministically. If pages appear image-only or
scanned, the extractor should report that OCR or vision support is required.

Excel and CSV support should be oriented toward notes, inventory lists,
catalogs, KPI lists, and product/request tables. The extractor should create
row summaries instead of dumping large sheets wholesale.

### Warning-Only Image Inputs

The SDK detects:

- `.png`
- `.jpg`
- `.jpeg`
- scanned/image-only `.pdf`

Screenshots and image PDFs should be treated as a different extraction class
from text documents. They require OCR or a vision-capable model to produce
usable text. The SDK should not silently pass image bytes into ordinary text
generation prompts.

Implemented first behavior:

1. Detect image files in lane folders.
2. Return a clear warning if OCR/vision support is not enabled.
3. When enabled later, extract visible text into normalized source records.
4. Preserve source metadata, image dimensions, and extraction method.
5. Warn that OCR and vision extraction can miss, distort, or over-interpret
   visual content.

Future image extraction should focus on screenshots of slides, whiteboards,
tables, product notes, dashboards, or catalog pages. It should not attempt to
interpret complex charts beyond extracting visible labels and text without
explicit user control.

### Phase 4: Enterprise Exports

Add optional import adapters for:

- Confluence page exports
- Jira issues or CSV exports
- Outlook mailbox exports or selected email folders
- catalog exports
- OpenMetadata extracts
- data contract folders

These should be explicit adapters, not generic "read anything" behavior.

## Internal Extraction Contract

The extraction layer should create normalized source records in memory and, for
debuggability, include extraction details in the existing command report and
default `--json` output. Source records are JSON-compatible tracking records;
they are not the final prompt format. Prompt assembly should render those
records into compact Markdown or plain text blocks only. Do not use HTML as the
normalized extraction format or as the v1 prompt format. Raw Office, Outlook,
SharePoint, or web-exported HTML is especially out of scope because it tends to
carry style, layout, and boilerplate noise. It should not require writing a
separate prepared source tree before portfolio generation can run.

Internal source record shape:

```python
{
    "source_path": "sources/objectives/strategy-deck.pptx",
    "declared_type": "pptx",
    "detected_type": "pptx",
    "detection_method": "ooxml-container",
    "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "source_unit": "slide",
    "source_unit_id": "3",
    "lane": "objectives",
    "title": "Improve customer retention",
    "content": "...normalized plain text or Markdown...",
    "content_format": "markdown",
    "content_sha256": "...",
    "estimated_tokens": 620,
    "truncated": false,
    "sha256": "...",
    "warnings": [],
}
```

For screenshot extraction, source records should include extraction method
metadata:

```python
{
    "source_path": "sources/products/product-whiteboard.jpg",
    "declared_type": "jpg",
    "detected_type": "jpeg",
    "detection_method": "image-header",
    "mime_type": "image/jpeg",
    "source_unit": "image",
    "source_unit_id": "1",
    "lane": "products",
    "title": "product-whiteboard",
    "content": "...OCR or vision extracted text...",
    "content_format": "plain",
    "extraction_method": "ocr",
    "sha256": "...",
    "warnings": ["review extracted text for OCR errors"],
}
```

When debug output is enabled, the SDK can write extracted Markdown sidecars for
review:

```text
portfolio/
  reports/
    source-extraction.json
    extracted/
      objectives.strategy-deck.slide-001.md
      objectives.strategy-deck.slide-002.md
      use-cases.sales-followup.email-001.md
```

Sidecars are for review and troubleshooting. They are not the primary workflow
contract.

Prompt rendering should keep source boundaries explicit without wrapping long
business text in JSON or HTML. A prompt block can use Markdown headings,
bullets, short tables, and source labels, for example:

```markdown
## Lane: use-cases
### Source: sales-followup.eml
Type: email
Unit: message 1

Customer asked for weekly retention reporting by segment.

- Need: churn visibility
- Constraint: CRM export is delayed by one day
```

JSON remains the format for source records, state, reports, chunk metadata,
warning lists, and deterministic tests. Markdown or plain text remains the v1
default format sent to the LLM.

Packed context formats such as GCF or TOON can be added as optional prompt
rendering formats after the source loader and reduction gate are working.
Expose the prompt/context format in the portfolio API and CLI, defaulting to
Markdown/plain text for v1. It should be selected through an explicit setting
such as:

```python
prepare_prompt_sources(
    lanes,
    max_prompt_tokens=12000,
    context_format="markdown",  # later: "gcf" or "toon"
)
```

Packed formats must only be applied after extraction, optional obfuscation,
chunking, and required reduction. They are not canonical storage formats and
must not hide omitted evidence. Reports still need to show source counts, chunk
counts, omitted chunks, estimated prompt size, reduction method, selected
context format, and warnings.

For email extraction, frontmatter should avoid exposing unnecessary personal
data by default if sidecars are written:

```yaml
---
sourceFile: stakeholder-request.eml
sourceType: eml
sourceUnit: message
sourceUnitId: "1"
subject: Improve retention reporting
sentDate: "2026-06-20"
attachments: 2
attachmentsExtracted: false
classification: unclassified
confidence: unreviewed
---
```

The body should contain the selected message text. Quoted reply chains and
signatures should be trimmed when practical, but the report should warn when
the extractor cannot confidently separate current message text from history.

## Source Size And LLM Context Control

Document support should not mean that the SDK sends all extracted text into one
LLM prompt. Long Word documents, Teams transcripts, slide decks, and email
threads can exceed model context limits, increase cost, and dilute the useful
business signal.

The v1 source loader should therefore separate extraction from prompt assembly:

1. Extract supported documents into JSON-compatible normalized source records.
2. Estimate size for each source record before LLM use.
3. Split long records into deterministic chunks with stable source unit IDs.
4. Preserve source path, lane, unit type, unit ID, and checksum for each chunk.
5. Apply a reduction step before generation when the combined lane input is too
   large.
6. Report when content was chunked, summarized, skipped, or truncated.

Recommended v1 behavior:

- Never silently truncate extracted text before an LLM call.
- Prefer deterministic chunking over arbitrary prompt truncation.
- Use deterministic reduction only in v1. Do not add an LLM summarization or
  reduction pass until the deterministic budget gate, report fields, and tests
  are stable.
- Keep chunk boundaries aligned with natural structure where possible: slide,
  heading section, transcript speaker turn, email message, paragraph, or table
  row group.
- Run lane-level reduction before product generation when a lane contains more
  text than the configured context budget.
- Keep the original extracted content available in the debug/report output when
  reporting is enabled, but send only reduced lane briefs into the LLM-backed
  generation step. Render those briefs as Markdown/plain text by default, with
  packed formats such as GCF or TOON available later as explicit post-reduction
  prompt formats.
- Include token or character estimates, chunk counts, and reduction warnings in
  `--json` output.

The reduced lane brief should be explicit about what it contains:

```text
Lane: use-cases
Sources reviewed: 8
Chunks reviewed: 34
Content omitted from prompt: 12 chunks over context budget
Reduction method: deterministic chunk summaries
```

This keeps the SDK usable with real customer material while avoiding the false
promise that any amount of raw business text can be pushed into a single model
request.

## Personal Data Obfuscation

The SDK should include a best-effort function for obfuscating clear personal
data before extracted content is used in LLM-backed workflows. This should be
framed as privacy risk reduction, not as guaranteed anonymization or compliance.

Recommended v1 helper:

```python
from open_data_products import obfuscate_personal_data
```

The helper should take text and return both the obfuscated text and an audit
summary:

```python
{
    "text": "Customer [PERSON_1] from [ORG_1] asked [EMAIL_1] about retention reporting.",
    "replacements": [
        {"type": "person", "placeholder": "[PERSON_1]", "confidence": "medium"},
        {"type": "organization", "placeholder": "[ORG_1]", "confidence": "medium"},
        {"type": "email", "placeholder": "[EMAIL_1]", "confidence": "high"},
    ],
    "warnings": ["obfuscation is best effort; review before external LLM use"],
}
```

V1 should prioritize clear, high-confidence identifiers:

- email addresses
- phone numbers
- obvious personal names when detected with reasonable confidence
- organization names when they appear in common email or meeting contexts
- postal addresses when detected with reasonable confidence
- URLs that contain personal or customer-specific identifiers

Recommended behavior:

- Enable obfuscation automatically for document intake before LLM-backed
  portfolio generation by default. Keep the helper available as
  `obfuscate_personal_data`.
- Add a `generation.config.yaml` setting that controls this behavior, for
  example:

  ```yaml
  portfolio:
    privacy:
      obfuscatePersonalData: true
  ```

  The default should be `true` for LLM-backed portfolio document intake. Setting
  it to `false` should send extracted content without this best-effort masking
  and should add a warning to the normal command log and `--json` output.
- Run obfuscation after extraction and before chunking/reduction so placeholder
  IDs remain stable across chunks.
- Preserve placeholder consistency within one command run, so the same detected
  email or name maps to the same placeholder.
- Do not write the reverse mapping to normal output or sidecar files by
  default.
- Include counts and warning messages in `--json` output and extraction
  reports.
- Never claim that the output is anonymous. Use wording such as "clear personal
  data obfuscated where detected."

This gives users a practical safer-default path for emails, transcripts, Word
documents, and PowerPoint decks while keeping responsibility for final review
visible.

## Lane Model

Classification should start from folders, not an automatic classifier.

The existing portfolio lane arguments remain authoritative:

- `--objectives sources/objectives/`
- `--use-cases sources/use-cases/`
- `--signals sources/signals/`
- `--products sources/products/`

Recommended v1 behavior:

1. If the user places files under a lane folder, preserve that lane.
2. If a direct `generate --input` path is used, infer only from the requested
   `--kind`.
3. Do not move files between lanes automatically.
4. Report file-level extraction warnings in the command output.
5. Add optional LLM-assisted lane suggestions later, but keep them advisory.

This avoids pretending the SDK can reliably infer business intent from every
document.

## Safety And Privacy

Document extraction increases data exposure risk. The plan should keep the
first version conservative.

- Do not process binary documents from remote URLs.
- Do not trust file extensions alone. Detect type from content signatures,
  parser probes, and optional metadata before choosing an extractor.
- Do not send extracted content to an LLM unless the user explicitly runs an
  LLM-backed command.
- Do not include images, embedded files, comments, track changes, hidden slides,
  or speaker notes by default.
- Do not process image files, screenshots, or scanned PDFs silently as text.
  Require OCR or vision support to be available and report the extraction
  method.
- For screenshots, warn users to review extracted text because OCR and vision
  models may miss or misread visual details.
- For PowerPoint, make speaker-note extraction opt-in.
- For email, extract message body and minimal metadata by default. Do not
  extract attachments, full recipient lists, or complete reply chains unless
  explicitly enabled.
- Obfuscate clear personal data automatically before LLM-backed document
  intake, but do not rely on it as a complete privacy guarantee.
- Always include extraction warnings and source-extraction summary fields in
  the normal `--json` output. Do not add a separate source-extraction report
  flag in v1.

Potential warning text:

> Review extracted content before using it with hosted LLM providers. Do not
> include personal data, credentials, confidential contracts, regulated records,
> or raw customer data unless your environment and provider policy allow it.

## Implementation Approach

### New Module Boundary

Add a new module:

```text
open_data_products/source_documents/
  __init__.py
  documents.py
  extractors.py
```

Possible public helpers:

```python
from open_data_products import (
    load_source_documents,
)
```

Keep extractors small and format-specific. Avoid adding document parsing logic
inside `portfolio.py` or `generation/__init__.py`.

`portfolio.py` and `generation/__init__.py` should call one shared source
loading API. That API should return normalized text records regardless of
whether the original source was Markdown, PowerPoint, email, PDF, Word, or a
spreadsheet.

### Dependencies

PowerPoint and Word extraction likely need optional dependencies:

- `python-pptx` for `.pptx`
- `python-docx` for `.docx`

Email extraction includes standard email files and optional Outlook messages:

- `email` from the Python standard library for `.eml`
- `extract-msg` through `open-data-products[email]` for Outlook `.msg`

PDF and spreadsheet support use lightweight built-in extraction today. Optional
dependencies can improve fidelity later:

- existing standard library `csv` for `.csv`
- optional `pypdf` or equivalent for richer text PDF extraction
- optional `openpyxl` for richer `.xlsx` extraction
- optional `Pillow` for basic image inspection
- `pytesseract` or equivalent OCR tooling for local screenshot text extraction
- optional hosted/local vision-model support for image descriptions, if the
  user explicitly enables a provider

Suggested extras:

```text
open-data-products[documents]
open-data-products[pptx]
open-data-products[email]
open-data-products[images]
```

The base SDK should remain lightweight. If optional dependencies are missing,
portfolio lane processing should add clear install-guidance warnings to the
normal command log and `--json` output, skip only the affected source files, and
continue processing the remaining supported lane sources.

## Tests

Add focused tests before implementation:

- portfolio lane scanning accepts `.pptx` files in lane folders.
- a PowerPoint file without a `.pptx` extension is detected from its Office
  container metadata.
- a renamed file with a misleading extension is rejected or warned when parser
  validation contradicts the extension.
- detection reports include detected type, detection method, MIME type when
  available, checksum, and warnings.
- `generate --input file.pptx --kind odps-product` returns a clear
  "not supported yet" message in v1; document intake is portfolio-lane-first.
- `.pptx` extraction creates one source record per deck, while preserving slide
  boundaries inside the extracted text.
- extraction skips hidden slides unless explicitly enabled.
- speaker notes are not extracted by default.
- `.docx` extraction writes headings, paragraphs, list items, and table text.
- `.docx` extraction does not include comments, tracked changes, embedded
  files, headers, footers, or images by default.
- unsupported file suffixes produce a clear error or warning.
- `.eml` extraction writes message body text and minimal metadata.
- `.msg` extraction uses `open-data-products[email]`; missing optional support
  or parse failures are reported in the normal log and `--json` output while
  remaining lane sources continue processing.
- email attachments are not extracted by default.
- email extraction warns when quoted history cannot be confidently trimmed.
- `.png`, `.jpg`, and `.jpeg` files in lane folders produce a clear warning
  when image extraction support is not installed or enabled.
- screenshot extraction records the extraction method and review warnings.
- text PDF extraction works without OCR when embedded text exists.
- image-only PDF extraction reports that OCR/vision support is required.
- `.docx` extraction creates records per heading section when headings are
  available and falls back to deterministic paragraph chunks.
- extraction reports are included in the default `--json` payload without a
  separate report flag.
- obfuscation runs automatically before LLM-backed portfolio generation unless
  disabled in config.
- deterministic reduction runs before every LLM-backed document-intake prompt,
  and no LLM call is made if the prompt still exceeds the configured budget.
- portfolio CLI/API exposes the prompt context format setting, defaulting to
  Markdown/plain text while allowing later GCF or TOON values.
- long `.docx`, transcript, deck, and email inputs are split into deterministic
  chunks before LLM-backed generation.
- prompt assembly fails clearly or reduces input when extracted lane content
  exceeds the configured context budget.
- no extracted text is silently truncated before an LLM call.
- reports include estimated size, chunk count, reduction method, omitted chunk
  count, and warnings when large inputs are reduced.
- `obfuscate_personal_data` masks clear email addresses, phone numbers, and
  other high-confidence identifiers with stable placeholders.
- obfuscation reports replacement counts, confidence, and warnings without
  writing a reverse mapping by default.
- obfuscation runs automatically before chunking/reduction for LLM-backed
  portfolio document intake unless disabled in config, so placeholders stay
  stable across chunks.
- extracted Markdown contains source metadata.
- lane folder inputs preserve lane assignment.
- extraction reports are deterministic and JSON-serializable.
- portfolio build can consume mixed source folders containing `.md`, `.txt`,
  `.docx`, `.pptx`, `.eml`, `.msg`, `.pdf`, `.csv`, `.xlsx`, and warning-only
  `.png`, `.jpg`, and `.jpeg` files.

Test fixtures should use small generated files under `tmp_path`, not real
customer documents.

## Documentation Updates

If implemented, update:

- `README.md` capability table.
- `docs/user/commands.md`.
- `docs/user/generation.md`.
- `docs/development/generation.md`.
- `docs/development/portfolio.md`.
- Maysano / SDK analysis wording so it can say which document formats are
  directly supported in source folders and which still require pre-processing.

## Implemented Sequence And Remaining Roadmap

### Step 1: Shared Source Loader

Created one shared source loading API used by portfolio workflows. It preserves
current behavior for `.md`, `.txt`, `.yaml`, `.yml`, and `.json` and adds
portfolio-lane document formats.

The source loader includes file type detection from content signatures,
container inspection, and extension fallback before format-specific extraction
runs.

### Step 2: PowerPoint In Lane Folders

Built a minimal `.pptx` extractor that turns visible slide text into one
normalized source record per deck. Preserve slide boundaries inside the record,
but do not split the deck into multiple lane sources by default. No OCR, no
images, no hidden slides, no speaker notes by default. Lane assignment comes
from the folder passed to `--objectives`, `--use-cases`, `--signals`, or
`--products`.

### Step 3: Word Documents In Lane Folders

Built a conservative `.docx` extractor that turns headings, paragraphs, lists,
and table text into normalized source records. Do not extract comments, tracked
changes, embedded files, headers, footers, or images by default. Lane assignment
comes from the folder passed to `--objectives`, `--use-cases`, `--signals`, or
`--products`.

This is part of v1 because customer-provided requirements, proposals, workshop
notes, and meeting summaries are often stored in Word documents.

### Step 4: Text Meeting Transcripts In Lane Folders

Supported transcript text when it is already available as `.txt`, `.docx`, or
Markdown. Extract speaker turns, decisions, questions, requirements, candidate
use cases, and follow-up actions when those cues are visible in the text. Do
not support audio or video ingestion.

This is part of v1 because Teams transcripts can capture the same early
customer-provider product discovery material as email threads and workshop
documents, without requiring media processing.

### Step 5: Email Threads And Outlook Message Warnings In Lane Folders

Built `.eml` extraction and Outlook `.msg` warning handling into the same source
loader. `.eml` extraction records subject, sent date, minimal message metadata,
and the selected message body. It does not extract attachments, full recipient
lists, or complete reply chains by default.

This is part of v1 because email is often the first place where client needs,
provider constraints, candidate data products, and follow-up questions appear.
Outlook `.msg` is detected and, when `open-data-products[email]` is installed,
extracted as message evidence. Without the extra or when parsing fails, it is
skipped with guidance so customer files are visible in reports instead of being
silently ignored.

### Step 6: Report Extraction Details

Added default `--json` fields that show which source files were extracted, which
units were skipped, and which warnings require review. Do not add a separate
source-extraction report flag in v1.

Example:

```bash
open-data-products portfolio build \
  --objectives sources/objectives/ \
  --use-cases sources/use-cases/ \
  --signals sources/signals/ \
  --products sources/products/ \
  --output portfolio/
```

### Step 7: Add Source Size And Context Control

Added deterministic chunking, source size estimates, and lane-level reduction
before any LLM-backed generation step. Long Word documents, Teams transcripts,
slide decks, and email threads should never be silently truncated. The command
should report chunk counts, omitted content, reduction method, and warnings.
Use deterministic reduction only in v1. GCF and TOON renderers can be evaluated
later, but only after extraction, obfuscation, chunking, and deterministic
reduction.

### Step 8: Add Personal Data Obfuscation

Added `obfuscate_personal_data` and run it automatically for LLM-backed portfolio
document intake by default. Add a `portfolio.privacy.obfuscatePersonalData`
setting in `generation.config.yaml` so the behavior can be switched off for
local-only or controlled environments. The function should mask clear personal
data with stable placeholders, report what was replaced, and warn that the
result is not guaranteed anonymization. Run it after extraction and before
chunking/reduction.

### Step 9: Add More Formats

Added text `.pdf`, `.xlsx`, and `.csv` support to portfolio lanes. `.msg`
extraction is available through the optional `open-data-products[email]` extra.

### Step 10: Add Screenshots And Image PDFs

Added `.png`, `.jpg`, `.jpeg`, and image-only PDF detection with clear warnings.
Add OCR or vision-model extraction later only behind explicit optional
dependencies and config.

### Step 11: Optional LLM-Assisted Classification

Add an opt-in classifier that suggests lanes for unstructured folders or mixed
document sets. Do not make it silently move files without review in v1. For the
core workflow, folder placement remains the classification mechanism.

## Open Questions

- Should sidecar metadata be one file per source, such as `deck.meta.yaml`, or
  one lane-level manifest, such as `sources/objectives/sources.yaml`?
- Should MIME detection use an optional `python-magic` dependency, standard
  library signatures, or a small built-in detector for the supported formats?
- Should speaker notes be opt-in per file, per command, or per config?
- Should email reply-chain trimming be enabled by default, or should the SDK
  preserve the full visible body and warn the user to review it?
- Which optional Outlook `.msg` parser is acceptable for license, maintenance,
  and cross-platform reliability?
- Should `.msg` extraction live in a general documents extra, a separate email
  extra, or both through a meta-extra?
- Should screenshot support rely first on local OCR, hosted vision models, or
  both?
- Should image extraction be disabled by default even when optional
  dependencies are installed?
- Should scanned PDFs be treated as PDF inputs, image inputs, or both depending
  on whether embedded text is present?
- Should Maysano own richer document upload and review while the SDK keeps
  folder-based extraction in the CLI/API?
- How much automatic classification is acceptable before review becomes
  mandatory?
- What default context budget should v1 use for each LLM-backed generation
  workflow?
- Which personal data types should v1 obfuscate deterministically without
  creating too many false positives?
- Should reverse mappings ever be written to disk, or should they stay
  in-memory only for one command run?

## Other Possible Inputs

Beyond PowerPoint, email, PDF, screenshots, Word, and spreadsheets, the same
source-folder model could later support:

- HTML exports from Confluence, SharePoint, Notion, or internal portals.
- Jira, Azure DevOps, or GitHub issue exports.
- CSV/JSON exports from data catalogs.
- OpenMetadata extracts.
- Data contract folders.
- Markdown exports from meeting tools.
- Non-text transcript formats from Teams, Zoom, or Google Meet that require a
  dedicated parser beyond `.txt`, `.docx`, or Markdown.
- Whiteboard exports from Miro, FigJam, or similar tools.
- Web archive exports, if processed locally and explicitly.
- ZIP bundles that contain a supported set of files, if the archive is scanned
  safely and file limits are enforced.

These should be added as explicit adapters with clear extraction reports. The
SDK should avoid a generic "read anything" mode that hides uncertainty from the
user.

## Recommendation

Do not add a separate required ingestion command for the main workflow.

The first useful version lets users drop Word `.docx` files, `.eml` email
files, Teams transcript text, PowerPoint `.pptx` files, text PDFs, CSV files,
and spreadsheets into existing portfolio source folders and have the SDK detect
and extract the useful text internally. Outlook `.msg` files are detected and
reported with install guidance instead of silently ignored. That is enough to
support the Maysano prospect-meeting story while preserving the simple user
model: put source material in the right lane folder, then run the normal SDK
workflow.

Screenshots, PNG/JPG files, and scanned PDFs should be planned, but they should
not be the first implementation target unless the onboarding workflow depends
on them. They add OCR/vision accuracy and privacy risks that are larger than
text-based PowerPoint, email, Word, and text PDF extraction.
