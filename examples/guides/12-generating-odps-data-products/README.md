# Lecture 12: Generating ODPS Data Products from Business Requirements

This lesson turns business requirement text, transcripts, emails, and briefs
into full ODPS product YAML drafts. This is full data product generation, not
fragment generation yet.

## 1. Prepare folders

```bash
mkdir -p odps-sdk-guides/12-odps-products/source_docs
mkdir -p odps-sdk-guides/12-odps-products/products
```

## 2. Add Source Documents

From the repository root, copy the sample files from this lesson folder:

```bash
cp examples/guides/12-generating-odps-data-products/source_docs/* \
  odps-sdk-guides/12-odps-products/source_docs/

cd odps-sdk-guides/12-odps-products
```

You can also write your own business requirement notes into the same shape.
Each Markdown or text file becomes one ODPS product draft.

## 3. Generate minimal ODPS products

```bash
open-data-products generate \
  --provider claude \
  --input source_docs/ \
  --kind odps-product \
  --profile minimal \
  --output products/
```

The default `minimal` profile is evidence-only. It creates valid ODPS product
YAML from source-backed facts and avoids drafting optional business components.

## 4. Generate complete draft products

```bash
open-data-products generate \
  --provider claude \
  --input source_docs/ \
  --kind odps-product \
  --profile complete-draft \
  --output products/
```

The `complete-draft` profile drafts `SLA`, `dataQuality`, and `pricingPlans`
when the source does not provide enough detail. Add `--json` when you want a
structured report with `review_notes`, `drafted_components`, and
`evidence_gaps`.

## 5. Force specific ODPS components

```bash
open-data-products generate \
  --provider claude \
  --input source_docs/ \
  --kind odps-product \
  --profile minimal \
  --include-components SLA,dataQuality,pricingPlans,dataAccess,license \
  --output products/
```

Supported component names are `contract`, `SLA`, `dataQuality`,
`pricingPlans`, `license`, `dataAccess`, `dataHolder`, `paymentGateways`, and
`productStrategy`.

## 6. Chunk long transcripts

```bash
open-data-products generate \
  --provider claude \
  --input source_docs/ \
  --kind odps-product \
  --profile minimal \
  --max-source-chars 40000 \
  --output products/
```

When a source file is longer than `--max-source-chars`, the SDK extracts facts
from chunks, merges those facts, and then generates ODPS from the merged facts.

## 7. Validate generated products

```bash
ls products/

for product_file in products/*.yaml; do
  open-data-products validate "$product_file"
done
```

## What You Learned

- `--kind odps-product` processes every source file in a folder.
- `--profile minimal` stays evidence-only.
- `--profile complete-draft` drafts key review-needed components.
- `--include-components` forces specific ODPS product components.
- `--max-source-chars` chunks long transcript or email files before ODPS
  generation.
- Generated ODPS YAML should be reviewed by a human and validated after
  generation.

## Next Lesson

Continue to
[Lecture 13: Working with generation and fragments](../13-working-with-generation-and-fragments/).
