# Release Summary: 0.3.0

Added the hosted `sakana-fugu` provider preset for Sakana Fugu's
  OpenAI-compatible Responses API, with default model `fugu` and documented
  `fugu-ultra` override examples.
- Tightened `--kind odps-product --profile minimal` so generated products keep
  only mandatory ODPS fields and strip hallucinated optional components unless
  they are requested through `complete-draft`.
- Tightened generation prompts to separate source-backed facts from defaults,
  skip unsupported optional ODPS component drafts, avoid invented signal
  timestamps, and constrain graph nodes to generated fragment context.
- Added compact contrast examples to the most drift-prone generation prompts so
  models see when to emit nulls, skip optional components, return empty signals,
  and avoid graph nodes without generated fragments.
- Added scoped rich examples for `--profile complete-draft` showing the default
  `SLA`, `dataQuality`, and `pricingPlans` component set without implying
  unrelated optional components.
- Added deterministic ODPS output pruning so unsupported root, product, and
  detail fields are removed before validation and writing.