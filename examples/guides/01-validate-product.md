# Guide 1: Validate an ODPS Product

This is the first useful SDK workflow: validate a product YAML file and get a
machine-readable result.

## 1. Create a lesson folder

```bash
mkdir -p odp-course/01-validate
cd odp-course/01-validate
```

## 2. Create `product.yaml`

```bash
cat > product.yaml <<'YAML'
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: "4.0"
product:
  name: Airport Operations Performance
  productID: airport-operations-performance
  visibility: public
  status: production
  type: dataset
  description: Operational data product for monitoring airport turnaround and departure performance.
  valueProposition: Helps operations teams reduce delays and coordinate airport resources.
YAML
```

## 3. Validate the file

```bash
open-data-products validate product.yaml
```

Expected result:

```text
Validation successful!
```

## 4. Get JSON output

```bash
open-data-products validate product.yaml --json
```

Use `--json` when the result is consumed by CI, scripts, or another tool.

## What You Learned

- `open-data-products validate` detects the document type.
- The SDK validates ODPS 4.x product files.
- Human-readable output is useful while learning.
- JSON output is better for automation.
