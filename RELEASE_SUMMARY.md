# Open Data Products Python SDK 0.3.6 Release Notes

## Portfolio API

- Added a public application-grade Portfolio pipeline API:
  `PortfolioSourceLanes`, `PortfolioBuildRequest`, `PortfolioBuildResult`, and
  `PortfolioPipeline`.
- Added canonical source-lane handling with aliases such as `use-cases`,
  `use_cases`, and `useCases`, so embedded applications can use stable SDK lane
  IDs while keeping their own display labels.
- Added a typed `PortfolioBuildResult` that preserves mapping-style access and
  `to_dict()` compatibility for existing callers.
- Kept `build_portfolio()` as the legacy dict-returning facade while delegating
  through the public pipeline path.
- Preserved both lane-by-lane portfolio generation and explicit bundled
  processing mode, with lane-by-lane as the safer embedded-application default.

## Validation

- Added tests for typed Portfolio pipeline usage, source-lane aliases, bundled
  mode compatibility, and root-package public exports.
- Verified the package with the full pytest suite, import check, manifest JSON
  rendering, Black formatting check, and diff whitespace check.
