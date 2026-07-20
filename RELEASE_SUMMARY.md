# Release Summary: 0.3.5

## Portfolio Build Fixes

- Kept portfolio builds moving when one product source fails by creating
  fallback ProductReference and ODPS draft artifacts with review warnings.
- Persisted portfolio build warnings into `portfolio.yaml` so generated
  workspaces keep the same warning context shown in JSON reports and HTML.
- Improved ProductReference-to-ODPS product matching for generated product ID
  suffix variants, reducing false "No linked ODPS detail" states in portfolio
  product cards.
- Prevented localization from translating identifier-like text such as generated
  product IDs.

## Portfolio Product Generation

- Extended product source lane handling so portfolio builds generate linked ODPS
  product YAML drafts alongside ODPC ProductReference fragments.
- Added staged ODPS product generation phases for product facts, minimal product
  YAML, component drafting, and assembly.
- Aligned generated ODPS product IDs and output filenames with the matching ODPC
  ProductReference.

## Portfolio HTML UX

- Added a generated portfolio spacing system with reusable `--space-*` CSS
  tokens for page, section, card, tab, modal, footer, and executive summary
  layout spacing.
- Refined generated portfolio HTML so related content reads as tighter groups,
  sibling cards and panels have more consistent separation, and mobile stacked
  layouts preserve clearer visual hierarchy.
- Reworked generated ODPS product detail modals into a marketplace-style
  product card view with a clear metadata header and compact Pricing, Data
  Quality, SLA, and Licensing sections instead of repeated linked-component
  blocks inside every pricing plan.

## Generation Prompt Hardening

- Tightened ProductReference generation rules so ODPS-only fields such as
  `SLA`, `dataQuality`, `license`, `pricing`, `accessLimits`, and
  `refreshCadence` are not invented in ODPC ProductReference fragments.
- Directed operational notes that must stay on a ProductReference into `x-*`
  extension fields instead of unsupported core fields.

## Internal Refactor And Docs

- Split deterministic portfolio source budgeting helpers into
  `open_data_products.portfolio_budget`.
- Split portfolio source privacy handling into
  `open_data_products.portfolio_privacy`.
- Added developer notes for portfolio spacing, testing strategy, fragment-root
  compatibility, and future AI-assisted data product delivery planning.
