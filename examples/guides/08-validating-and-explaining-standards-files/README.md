# Lecture 8: Validating and Explaining Standards Files

The SDK is not only for generation. It also helps you check standards files,
explain their structure, and detect missing fields before those files are used
in a real project.

## 1. Create A Lesson Folder

```bash
mkdir -p odps-sdk-guides/08-validate-and-explain
cd odps-sdk-guides/08-validate-and-explain
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

## 3. Validate The File

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

## 5. Explain The File

```bash
open-data-products explain product.yaml
```

Use explanation when you want a quick human-readable view of what a standards
file contains.

## 6. Create A Schema-Invalid File

```bash
cat > invalid-product.yaml <<'YAML'
schema: https://opendataproducts.org/v4.0/schema/odps.json
version: "4.0"
product:
  name: Missing Product ID Example
  visibility: public
  status: draft
  type: dataset
  description: This YAML is syntactically valid but is missing a required productID.
  valueProposition: Shows how validation catches missing standards fields.
YAML
```

Run validation again:

```bash
open-data-products validate invalid-product.yaml --json
```

The command should report a validation error instead of a YAML parsing error.
That distinction matters: the file is readable YAML, but it does not satisfy
the ODPS schema.

## What You Learned

- `open-data-products validate` detects the document type.
- The SDK validates ODPS 4.x product files.
- `open-data-products explain` gives a human-readable summary.
- Missing required fields are caught before the file reaches a catalog,
  graph, portfolio, or automation workflow.
- Human-readable output is useful while learning.
- JSON output is better for automation.

## Next Lesson

Continue to
[Lecture 9: Use the ODPV vocabulary helpers](../09-use-odpv-vocabulary-helpers/).
