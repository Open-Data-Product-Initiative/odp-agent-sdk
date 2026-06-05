# Guide 10: Generate ODPS Products from Transcripts and Email

This guide turns unstructured source files into full ODPS product YAML. Each
Markdown or text file becomes one data product.

## 1. Prepare folders

```bash
mkdir -p odps-sdk-guides/10-odps-products/source_docs
mkdir -p odps-sdk-guides/10-odps-products/products
cd odps-sdk-guides/10-odps-products
```

## 2. Add source documents

```bash
cat > source_docs/customer-retention-meeting.txt <<'TXT'
Meeting transcript:

Maya from retention analytics says the team needs a reusable customer analytics
data product for churn prevention. It should combine account profile, product
usage, purchase history, support tickets, campaign contacts, and churn risk
signals. The primary users are retention managers and lifecycle marketing
analysts. The product should support weekly churn review and next-best-action
campaign planning.
TXT

cat > source_docs/support-operations-email.md <<'MD'
# Support operations data product email

The service operations team wants a data product for support ticket backlog,
response time, escalation pressure, sentiment, and team capacity. The product is
used by support leads to prioritize escalations and improve response quality.
MD
```

## 3. Generate minimal ODPS products

```bash
open-data-products generate \
  --provider claude \
  --input source_docs/ \
  --kind odps-product \
  --profile minimal \
  --output products/ \
  --json
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
  --output products/ \
  --json
```

The `complete-draft` profile drafts `SLA`, `dataQuality`, and `pricingPlans`
when the source does not provide enough detail. Review the JSON response for
`review_notes`, `drafted_components`, and `evidence_gaps`.

## 5. Force specific ODPS components

```bash
open-data-products generate \
  --provider claude \
  --input source_docs/ \
  --kind odps-product \
  --profile minimal \
  --include-components SLA,dataQuality,pricingPlans,dataAccess,license \
  --output products/ \
  --json
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
  --output products/ \
  --json
```

When a source file is longer than `--max-source-chars`, the SDK extracts facts
from chunks, merges those facts, and then generates ODPS from the merged facts.

## 7. Validate generated products

```bash
open-data-products validate products/odps_product_customer-retention.yaml --json
```

## What You Learned

- `--kind odps-product` processes every source file in a folder.
- `--profile minimal` stays evidence-only.
- `--profile complete-draft` drafts key review-needed components.
- `--include-components` forces specific ODPS product components.
- `--max-source-chars` chunks long transcript or email files before ODPS
  generation.
