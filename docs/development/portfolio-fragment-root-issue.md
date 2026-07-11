# Portfolio Fragment Root Compatibility Issue

This issue note records a portfolio build defect observed from an external
application that uses `open_data_products.portfolio.build_portfolio(...)`.

## Summary

LLM-backed portfolio generation can produce ODPC fragment files with plural
collection roots such as `businessObjectives`. The portfolio catalog assembly
path currently collects singular fragment roots such as `businessObjective`.
When those shapes do not match, generated objectives can be dropped from
`odpc/catalog.yaml` and from the rendered portfolio page even though source
files were processed.

## Observed Behavior

A portfolio version was created from four source files. One lane contained
business objective material. The generated workspace reported the source files,
but the rendered portfolio showed no Business Objectives.

The generated objective fragment used this shape:

```yaml
businessObjectives:
  - id: support-operations-performance-product
    name:
      en: Support Operations Performance Product
    description:
      en: Create a data product providing support leaders with a consistent view
        of support operations performance.
    status: active
```

The resulting `odpc/catalog.yaml` did not include the objective under:

```yaml
catalog:
  businessObjectives:
```

The rendered HTML therefore showed an empty Business Objectives section.

## Root Cause

`open_data_products.portfolio._fragment_collections(...)` accepts singular
fragment roots:

```python
keys = {
    "businessObjective": "businessObjectives",
    "useCase": "useCases",
    "signal": "signals",
    "productReference": "productReferences",
}
```

It ignores plural list roots such as:

```yaml
businessObjectives:
  - id: support-operations-performance-product
```

The SDK has an internal compatibility gap if one path writes plural-root
generated fragments and another path only collects singular-root fragments.

## Expected Behavior

SDK-generated portfolio fragments should round-trip into the final catalog,
graph context, and rendered portfolio page.

The SDK should either:

1. always write one singular-root fragment per generated object, for example:

   ```yaml
   businessObjective:
     id: support-operations-performance-product
   ```

2. or make fragment collection tolerant of plural list roots, for example:

   ```yaml
   businessObjectives:
     - id: support-operations-performance-product
   ```

The robust fix is to do both: normalize generated artifacts to singular-root
files where possible, and keep the collector tolerant of plural roots for
backward compatibility.

## Suggested Collector Fix

Extend `_fragment_collections(...)` to support singular object roots and plural
list roots:

```python
singular_keys = {
    "businessObjective": "businessObjectives",
    "useCase": "useCases",
    "signal": "signals",
    "productReference": "productReferences",
}

plural_keys = {
    "businessObjectives": "businessObjectives",
    "useCases": "useCases",
    "signals": "signals",
    "productReferences": "productReferences",
}

for source_key, target_key in singular_keys.items():
    value = document.get(source_key)
    if isinstance(value, dict):
        collections[target_key].append(value)

for source_key, target_key in plural_keys.items():
    value = document.get(source_key)
    if isinstance(value, list):
        collections[target_key].extend(
            item for item in value if isinstance(item, dict)
        )
```

If generated plural-root fragments are kept on disk, de-duplicate by stable
object identifier (`id`, then `productID`) before writing the assembled catalog.

## Regression Test

Add a regression in `tests/test_portfolio.py` with a workspace containing:

```text
odpc/
  fragments/
    odpc_objectives.yaml
```

`odpc/fragments/odpc_objectives.yaml`:

```yaml
businessObjectives:
  - id: support-operations-performance-product
    name:
      en: Support Operations Performance Product
```

The test should assert that `_catalog_from_fragments(root)` or
`render_portfolio(root)` includes one `catalog.businessObjectives` item and
that the rendered HTML contains `Support Operations Performance Product`.

Also add equivalent tests for `useCases`, `signals`, and `productReferences`
if plural-root fragments can be produced for those lanes.

## Impact

Without this fix, valid generated source evidence can be silently dropped from
the final catalog and HTML while source counts still look correct. That makes a
portfolio misleading: users see that files were included but do not see the
generated objective content in the portfolio.
