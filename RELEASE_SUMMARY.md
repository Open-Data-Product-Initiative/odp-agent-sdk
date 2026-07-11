# Release Summary: 0.3.4

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
- Added developer guidance for future portfolio spacing work in
  `docs/development/portfolio_spacing_guidance.md`.

## Portfolio Refactor

- Split deterministic portfolio source budgeting helpers into
  `open_data_products.portfolio_budget`.
- Split portfolio source privacy handling into
  `open_data_products.portfolio_privacy`.
- Updated `docs/development/portfolio-refactor-note.md` to document the current
  module boundaries and remaining future extraction candidates.
