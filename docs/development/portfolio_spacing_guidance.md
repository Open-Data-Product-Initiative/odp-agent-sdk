# Portfolio HTML Spacing Improvement Plan

This plan describes how to improve spacing in the generated portfolio
`index.html` UI. The goal is not to redesign the portfolio. The goal is to make
the existing experience feel more intentional, easier to scan, and more stable
across desktop and mobile layouts by replacing one-off spacing with a small
system.

The main implementation target is `open_data_products/portfolio.py`, especially
`_portfolio_css()` and the HTML helpers that emit repeated portfolio groups.
Keep generated HTML static and browser-openable. Do not add runtime dependencies
or a build step.

## Problem

Generated portfolio pages currently mix many raw spacing values such as `5px`,
`7px`, `13px`, `18px`, `22px`, `26px`, and `28px`. Many are harmless in
isolation, but together they make the UI feel uneven:

- section spacing, card spacing, and text spacing do not always communicate
  hierarchy;
- executive summary cards use different gaps than other cards without a clear
  scale;
- mobile stacking can visually merge separate groups;
- repeated components such as cards, chips, facts, lists, actions, and panels
  have similar roles but inconsistent padding and gaps;
- tests currently assert some exact CSS values, so spacing work needs deliberate
  regression updates.

## Design Principle

Spacing is structure.

Use spacing to show what belongs together and what should be read separately.
Do not tune gaps one component at a time unless the component has a distinct
layout need.

The hierarchy should be:

- inline elements: smallest spacing;
- related text inside one component: tight spacing;
- component internals: smaller than the space between sibling components;
- related cards and panels: medium spacing;
- tab sections and major topic changes: larger spacing;
- hero and page breaks: largest spacing.

## Scope

In scope:

- spacing tokens in generated portfolio CSS;
- page wrapper, hero, tabs, tab panels, section headers, cards, panels, metrics,
  action cards, executive summary dashboard, SWOT and executive lists, product
  cards, product modals, graph layout, about card, footer, chips, facts, and
  repeated list rows;
- mobile and tablet spacing adjustments;
- tests that pin generated HTML/CSS behavior.

Out of scope:

- changing portfolio data generation;
- changing tab names or artifact structure;
- changing localization behavior except preserving translated output;
- replacing the visual language, colors, typography, shadows, or icon assets;
- refactoring `portfolio.py` into new modules. If renderer extraction is needed,
  do it as a separate task after this spacing cleanup.

## Spacing Scale

Add the spacing scale to the generated portfolio `:root` block and use it for
layout spacing.

| Token | Value | Primary Use |
|---|---:|---|
| `--space-1` | 4px | icon-to-label gaps, tiny inline offsets |
| `--space-2` | 8px | labels to values, chips, tight grouped text |
| `--space-3` | 12px | compact metadata and list row gaps |
| `--space-4` | 16px | normal text blocks, compact card internals |
| `--space-6` | 24px | standard card padding and sibling card gaps |
| `--space-8` | 32px | subsection gaps and large card padding |
| `--space-12` | 48px | major section spacing |
| `--space-16` | 64px | page-level spacing |
| `--space-24` | 96px | hero or strong page breaks |

Use `0`, `1px`, border radii, stroke widths, font sizes, line heights, icon
sizes, and media dimensions as normal values. The spacing token rule is for
`gap`, `padding`, `margin`, `inset`, and positional spacing.

Avoid adding extra spacing tokens until a repeated need appears in at least two
component families.

## Target Defaults

Use these defaults unless a component has a clear reason to differ:

```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;
  --space-16: 64px;
  --space-24: 96px;
}

.wrap {
  width: min(1180px, calc(100% - (var(--space-6) * 2)));
}

.hero .wrap {
  padding-block: var(--space-16) var(--space-12);
}

main.wrap {
  padding-block: var(--space-6) var(--space-16);
}

.tab-panel {
  padding-top: var(--space-8);
}

.section-head {
  gap: var(--space-6);
  margin-bottom: var(--space-6);
}

.grid,
.actions-grid,
.overview-card-grid,
.product-grid,
.decision-card-grid {
  gap: var(--space-6);
}

.card,
.panel,
.action-card,
.decision-card,
.executive-list,
.executive-empty {
  padding: var(--space-6);
}
```

Desktop exception: executive dashboard intro and large leadership cards may use
`var(--space-8)` padding when they introduce or summarize a major decision
area. Most repeated cards should use `var(--space-6)`.

Mobile adjustment:

```css
@media (max-width: 640px) {
  .wrap {
    width: min(100% - (var(--space-4) * 2), 1180px);
  }

  .hero .wrap {
    padding-block: var(--space-12);
  }

  .card,
  .panel,
  .action-card,
  .decision-card,
  .executive-list,
  .executive-empty {
    padding: var(--space-4);
  }

  .grid,
  .actions-grid,
  .overview-card-grid,
  .product-grid,
  .decision-card-grid {
    gap: var(--space-6);
  }
}
```

Keep stacked cards at least `var(--space-6)` apart on mobile so separate
objects do not visually merge.

## Implementation Phases

### 1. Baseline Audit

Inspect `_portfolio_css()` and generated sample HTML before editing.

- List all raw `gap`, `padding`, `margin`, `inset`, `top`, `right`, `bottom`,
  and `left` spacing values in `open_data_products/portfolio.py`.
- Categorize each value as inline, component internal, sibling component,
  section, page, or layout-specific.
- Identify CSS assertions in `tests/test_portfolio.py` that will need updates.
  Existing examples include executive summary intro padding and decision card
  grid gap assertions.
- Render at least one sample workspace before the change if practical, so visual
  differences can be compared.

### 2. Add Tokens And Page-Level Spacing

Add the spacing tokens to the generated `:root` block.

Then normalize:

- `.wrap`, `.topbar-inner`, and page edge spacing;
- `.hero .wrap`, `h1`, `.lead`, and hero eyebrow spacing;
- `main.wrap`, `.tabs`, `.tabs label`, and `.tab-panel`;
- footer spacing.

This phase should make the page frame consistent before tuning individual
components.

### 3. Normalize Shared Components

Convert repeated component families to tokenized spacing:

- metrics and summary grid;
- `.card`, `.panel`, `.action-card`, `.overview-card`;
- `.chip-row`, `.chip`, `.facts`, row lists, and details blocks;
- `.grid`, `.actions-grid`, `.overview-card-grid`, `.product-grid`;
- graph side panels and graph detail lists.

Rules:

- internal card gaps should usually be `var(--space-2)` to `var(--space-4)`;
- card and panel padding should usually be `var(--space-6)`;
- sibling cards should use `var(--space-6)` or `var(--space-8)`;
- avoid padding larger than sibling card gaps unless the component is a major
  executive or hero surface.

### 4. Normalize Executive Summary Spacing

Treat the Executive Summary tab as a high-value user surface, because it is the
leadership decision view.

Update:

- `.executive-dashboard-intro`;
- `.leadership-recommendation`;
- `.decision-card-grid`;
- `.decision-card` and its header, icon, body, footer, details, badge rows, and
  evidence rows;
- `.swot-grid`, `.swot-card`, `.executive-list`, `.executive-item`, and
  `.business-evidence`.

Preserve existing behavior:

- four decision cards still render in the dashboard;
- technical IDs remain hidden from the visible collapsed card body;
- details remain collapsed by default where they are today;
- missing executive summary state remains honest and does not infer content.

Expected spacing hierarchy:

- recommendation and dashboard intro: `var(--space-6)` to `var(--space-8)`;
- decision card padding: `var(--space-6)`;
- decision card internal gaps: `var(--space-2)` to `var(--space-4)`;
- dashboard card grid gap: `var(--space-6)` or `var(--space-8)`;
- executive lists below the dashboard: separated by at least `var(--space-6)`.

### 5. Product Cards And Modals

Normalize product card and modal spacing without changing the product detail
contract.

Focus on:

- `.product-card`, `.product-card-description`, `.product-card-counters`, and
  `.product-card-actions`;
- modal panel padding and internal component sections;
- pricing table and linked component cards;
- SLA, data quality, access, and payment component cards.

Keep pricing-linked details grouped together. Do not reintroduce separate
unlinked SLA or data quality sections when pricing plans already reference them.

### 6. Responsive Review

Review generated HTML at these widths:

- desktop around 1280px;
- tablet around 900px;
- mobile around 390px.

Check:

- edge padding does not feel cramped;
- section headers do not collide with descriptions;
- stacked cards keep clear separation;
- tabs remain usable when horizontally scrolling;
- modals fit without text touching panel edges;
- graph tab remains readable when the side panel stacks;
- footer columns have enough vertical separation on mobile.

### 7. Test Updates

Update tests after the CSS behavior is intentionally changed.

Recommended tests:

- generated CSS contains all spacing tokens;
- representative layout selectors use spacing tokens instead of old raw values,
  for example `.hero .wrap`, `.tab-panel`, `.grid`, `.card`, and
  `.decision-card-grid`;
- executive summary tests assert tokenized spacing rather than exact old values
  such as `padding: 24px 28px;` or `gap: 28px;`;
- product card/modal tests continue to verify the existing modal contract;
- localization tests continue to verify CSS and JavaScript are preserved.

Avoid snapshotting the whole HTML page. Pin a few high-value selectors and keep
behavioral assertions focused.

## Audit Checklist

Before considering the implementation complete, verify:

- no arbitrary spacing values remain for `gap`, `padding`, `margin`, or `inset`
  unless documented as layout-specific;
- similar cards and panels share the same padding and internal gaps;
- related elements are closer than unrelated groups;
- section spacing is larger than card spacing;
- cards are neither cramped nor hollow;
- mobile stacking preserves the same grouping logic as desktop;
- spacing improvements do not rely on adding more borders, shadows, colors, or
  decorative surfaces;
- generated HTML still opens directly from disk;
- generated HTML still escapes user and model content;
- localized pages still preserve CSS and JavaScript.

## Verification Commands

Run the focused portfolio tests first:

```bash
python -m pytest tests/test_portfolio.py -q
```

Then run the repository pre-completion checks:

```bash
python -m pytest -q
python -c "import open_data_products"
python -m open_data_products.cli manifest --json | python -m json.tool
```

Also verify that `docs/superpowers/` was not recreated.

## Definition Of Done

The spacing refinement is done when the generated portfolio UI reads as a
consistent system before the user reads the text:

- page, section, card, and inline spacing have clear hierarchy;
- repeated portfolio components use reusable spacing tokens;
- executive summary, product cards, modals, graph, and footer all follow the
  same spacing logic;
- desktop, tablet, and mobile layouts preserve grouping and scanability;
- tests document the intended CSS contract without locking the whole page into a
  fragile snapshot.
