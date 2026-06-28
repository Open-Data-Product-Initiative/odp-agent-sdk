# Release Summary: 0.3.3

## Portfolio Refresh Fixes

- Fixed a major normal `portfolio refresh` delta bug so changed source files
  are detected from saved `path + sha256` source state, and model output from a
  changed lane cannot duplicate unchanged objectives, use cases, signals, or
  products.
- Added a real fullscreen graph workspace control for generated portfolio HTML
  so crowded graph views can be explored with the canvas, inspector, filters,
  and legend expanded beyond the normal tab area.

## Portfolio Executive Summary

- Added a machine-readable `executive-summary.yaml` artifact and a new
  Executive Summary tab for generated portfolio workspaces. The tab renders a
  leadership decision dashboard with a recommendation banner, Priority 1,
  Priority 2, Risk, and Readiness cards, confidence/evidence badges, collapsed
  details, and local PNG icon badges.
- Split LLM-backed portfolio generation into explicit phases: `portfolio` for
  normalized artifacts and `executiveSummary` for leadership decision support.
  Build and refresh JSON reports now include `llmCallCount` and `llmPhases`,
  including repair phases when malformed YAML needs a repair call.
- Kept `portfolio render` and `portfolio sync` deterministic: they load and
  validate an existing `executive-summary.yaml`, render an honest missing state
  when absent, and never call a model.
