# Portfolio Intake Guide

Portfolio intake is the SDK step that reads source documents before a
portfolio build or refresh sends evidence to an LLM. Use it when you want to
check what the SDK can extract, what it will skip, how much content will fit in
the prompt budget, and whether personal data masking is active.

The intake command never calls an LLM:

```bash
open-data-products portfolio intake \
  --objectives sources/objectives/ \
  --use-cases sources/use-cases/ \
  --signals sources/signals/ \
  --products sources/products/ \
  --config generation.config.yaml \
  --json
```

The four source lanes map to portfolio concepts:

- `--objectives`: business objectives
- `--use-cases`: use cases
- `--signals`: market, operational, risk, quality, usage, or other signals
- `--products`: existing or candidate data products

Use the same source folders for `portfolio build` and `portfolio refresh`.
`portfolio intake --json` is the dry-run view of those source folders.

## Supported Inputs

Portfolio source lanes accept:

- Text: `.md`, `.txt`, `.yaml`, `.yml`, `.json`
- Email: `.eml`
- Outlook email: `.msg` when installed with `open-data-products[email]`
- Office documents: `.docx`, `.pptx`, `.xlsx`
- PDF: `.pdf`
- Tables: `.csv`

The SDK also detects but skips:

- Outlook `.msg` files when `open-data-products[email]` is not installed, or
  when the message cannot be parsed
- Image files: `.png`, `.jpg`, `.jpeg`
- Image-only or scanned PDFs when embedded text is not available

File type detection is content-first where possible. For example, a PDF named
`notes.docx` is treated as a PDF if the PDF header is present. OOXML containers
are inspected instead of blindly trusting `.docx`, `.pptx`, or `.xlsx`
extensions. Extensions are used as fallback when no stronger signature is
available.

## What The JSON Means

The JSON report contains the main fields users usually need:

- `llmCallCount`: always `0` for intake.
- `sourceCounts`: included source counts by lane.
- `sources`: included source records with lane, path, type, detection method,
  source unit, character counts, chunk counts, status, and a short preview.
- `sourceExtraction.warnings`: extraction, decoding, and skipped-file warnings.
- `sourceExtraction.skippedSourceCount`: number of skipped source files.
- `sourceExtraction.skippedSources`: skipped file records with path, lane,
  source type, detection method, status, and warning.
- `sourceBudget`: deterministic prompt-reduction metadata.
- `sourcePrivacy`: personal data masking metadata.
- `warnings`: combined warnings from extraction, budget reduction, and privacy
  masking.

A source `status` can be:

- `included`: extracted content fits the configured intake budget.
- `reduced`: extracted content was chunked and some chunks were omitted from
  the LLM prompt budget.
- `empty`: the file was readable but produced no text content.
- `skipped`: the file appears under `sourceExtraction.skippedSources`, not
  `sources`.

## Budget And Reduction Behavior

Long-input reduction is required before LLM-backed portfolio calls. Intake uses
the same deterministic budget settings and reports the result before any LLM is
involved.

Default budget settings live in `generation.config.yaml`:

```yaml
portfolio:
  sourceBudget:
    maxSourceChars: 2000
    maxPromptChars: 32000
  privacy:
    obfuscatePersonalData: true
```

`maxSourceChars` controls chunk size. `maxPromptChars` controls the final
prompt budget. The SDK reserves space for prompt instructions, then includes
source chunks up to the remaining source budget. Omitted chunks are counted and
reported. Omission is not a crash and not silent truncation; it is visible in
`sourceBudget.omittedChunkCount`, per-source `omittedChunkCount`, and
`warnings`.

Important budget fields:

- `sourceBudget.method`: currently `deterministic-chunk-budget`.
- `sourceBudget.estimatedInputChars`: total extracted characters before
  reduction.
- `sourceBudget.includedChars`: characters kept for prompt construction.
- `sourceBudget.omittedChars`: extracted characters not included.
- `sourceBudget.chunkCount`: total chunks created.
- `sourceBudget.includedChunkCount`: chunks kept.
- `sourceBudget.omittedChunkCount`: chunks omitted.
- `sourceBudget.reducedSourceCount`: number of sources with omitted chunks.

If a file appears to be missing content in the generated portfolio, run
`portfolio intake --json` first and check whether that source has
`status: reduced` and a non-zero `omittedChunkCount`.

## Privacy Behavior

By default, portfolio intake applies best-effort personal data masking before
source reduction. This is the same privacy stage used by LLM-backed build and
refresh.

The JSON report includes:

- `sourcePrivacy.enabled`
- `sourcePrivacy.method`
- `sourcePrivacy.sourceCount`
- `sourcePrivacy.replacementCounts`
- `sourcePrivacy.replacements`
- `sourcePrivacy.warnings`

Repeated values are mapped to stable placeholders within one command run, such
as `[EMAIL_1]` or `[PHONE_1]`. The masking is best effort and should be
reviewed before external LLM use.

To disable masking for a controlled local-only workflow:

```yaml
portfolio:
  privacy:
    obfuscatePersonalData: false
```

Then rerun intake with `--config generation.config.yaml` and confirm
`sourcePrivacy.enabled` is `false`.

## Edge Cases Covered

The SDK test fixtures cover these intake behaviors:

- Mixed file types across all four portfolio lanes.
- Content-first detection for renamed PDF, OOXML, email, image, and MSG files.
- `.pptx` files treated as one portfolio source, even though the deck may
  contain multiple visible slides.
- `.docx` and `.xlsx` extraction from OOXML containers.
- Embedded-text PDF extraction.
- Image-only PDFs skipped with OCR or vision guidance.
- Image files skipped with OCR or vision guidance.
- Outlook `.msg` files extracted when the `email` extra is installed, or
  skipped with install or parse guidance when extraction is unavailable.
- Corrupt Office, workbook, presentation, and PDF-like files skipped with
  warnings instead of crashing the whole command.
- Empty files and whitespace-only files represented as empty or zero-content
  records.
- UTF-8 BOM cleanup.
- Latin-1 text and CSV decoding fallback with a warning.
- Control-character cleanup before prompt rendering.
- Multilingual text preservation.
- Semicolon and quoted-newline CSV handling.
- Hidden XLSX sheets skipped by default.
- DOCX header and footer text not extracted by default.
- PPTX hidden slide and image-only slide content not extracted by default.
- Email plain text selected deterministically from multipart messages.
- Email attachments not extracted by default.
- Duplicate content in different lanes preserving lane assignment and source
  paths.
- Nested folders scanned recursively and deterministically.
- Long DOCX, long email, long transcript, and many-small-file budget behavior.
- No LLM calls during intake.

These tests are intentionally conservative. If content requires OCR, vision,
comments, speaker notes, hidden slides, hidden sheets, or embedded attachment
extraction, the base SDK will not extract it silently. Outlook MSG parsing is
optional and requires installing the email extra.

## Debugging Checklist

Start with the dry run:

```bash
open-data-products portfolio intake \
  --objectives sources/objectives/ \
  --use-cases sources/use-cases/ \
  --signals sources/signals/ \
  --products sources/products/ \
  --config generation.config.yaml \
  --json
```

Then check these points.

1. Confirm the file is in a lane folder.

   If a file is outside the folder passed to `--objectives`, `--use-cases`,
   `--signals`, or `--products`, it is not part of intake.

2. Check `sourceCounts`.

   If the lane count is lower than expected, check
   `sourceExtraction.skippedSources` and `sourceExtraction.warnings`.

3. Check `sourceExtraction.skippedSources`.

   A skipped file should include the lane, path, detected source type,
   detection method, and warning. Common causes are missing optional Outlook
   support, image files, image-only PDFs, corrupt Office containers, or a
   misleading Office extension that is not a readable OOXML document.

4. Check `detectionMethod`.

   Useful values include `extension`, `pdf-header`, `ooxml-container`,
   `rfc822-headers`, `ole-compound-header`, `png-header`, `jpeg-header`, and
   `csv-sniffer`. If detection differs from the extension, the content
   signature won.

5. Check `status`.

   `empty` means the SDK could read the file but found no extractable text.
   `reduced` means text was extracted but not all chunks fit the configured
   prompt budget.

6. Check `preview`.

   If preview has the expected text, extraction worked. If preview is empty for
   a valid file, the file may contain only unsupported content such as images,
   hidden slides, hidden sheets, comments, or attachments.

7. Check `sourceBudget`.

   If `omittedChunkCount` is greater than zero, the input was larger than the
   configured prompt budget. Increase `portfolio.sourceBudget.maxPromptChars`
   only if your LLM and workflow can safely handle the larger prompt.

8. Check `sourcePrivacy`.

   If content looks masked, verify `sourcePrivacy.enabled` and
   `replacementCounts`. Masking happens before chunking and reduction.

9. Re-run with one lane or one file.

   Each lane option can point at a folder or a single file. To isolate a
   problem, run intake with only the suspicious file:

   ```bash
   open-data-products portfolio intake \
     --signals sources/signals/problem-file.pdf \
     --json
   ```

10. Compare build behavior to intake.

   If `portfolio build` output seems wrong, first check whether intake shows
   the expected extracted source records. If intake already skipped, reduced,
   or masked the content, the LLM never saw the original full text.

11. Install optional Outlook support when needed.

   `.msg` files require the email extra:

   ```bash
   python3 -m pip install "open-data-products[email]"
   ```

   Then rerun `portfolio intake --json` and check that the message appears in
   `sources` with `sourceType: msg`.

## Common Symptoms

The command fails because a source folder does not exist.

: The lane path is wrong. Source lane paths must exist. Fix the path or remove
  the lane flag.

A `.msg` file is skipped.

: Install `open-data-products[email]` if the warning says MSG extraction is not
  enabled. If the extra is already installed, the warning usually means the MSG
  file could not be parsed.

A scanned PDF has no text.

: This is expected unless the PDF contains embedded text. OCR or vision
  extraction is not enabled by default.

A `.docx`, `.pptx`, or `.xlsx` file is skipped as an Office source.

: The extension exists, but the file is not a readable OOXML document of that
  type. The file may be corrupt, password-protected, or mislabeled.

A PDF named `.docx` is extracted as PDF.

: This is expected. Content signatures take precedence over file extensions.

Hidden spreadsheet data is missing.

: Hidden XLSX sheets are skipped by default. Move the data to a visible sheet
  if it should be part of portfolio evidence.

PowerPoint speaker notes or hidden slides are missing.

: They are not extracted by default. Intake uses visible slide XML text as the
  default deck evidence.

Email attachments are missing.

: Attachments are not extracted by default. Put attachment content into a
  supported source lane file if it should be included.

The generated portfolio misses the end of a long document.

: Check per-source `omittedChunkCount` and the aggregate
  `sourceBudget.omittedChunkCount`. The source was processed, but the omitted
  chunks were over budget and were not sent to the LLM.

Personal emails or phone numbers look replaced.

: This is expected when privacy masking is enabled. Check
  `sourcePrivacy.replacementCounts`.
