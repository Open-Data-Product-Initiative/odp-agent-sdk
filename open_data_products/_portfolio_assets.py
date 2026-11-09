"""Static presentation assets for Portfolio HTML."""

from __future__ import annotations


def portfolio_css() -> str:
    return """
:root {
  color-scheme: light;
  --odps-violet: #6c2a8e;
  --odpc-orange: #f28c28;
  --odpg-green: #2f9b58;
  --odpv-blue: #1f78d1;
  --odp-ink: #1e0a2e;
  --odp-soft: #f7f3fa;
  --odp-line: #e7e1ec;
  --odp-muted: #6d6175;
  --odp-black: #050505;
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
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--odp-ink);
  background: #fff;
  font: 16px/1.55 Poppins, Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
html[dir="rtl"] body {
  direction: rtl;
  text-align: right;
}
a { color: inherit; text-decoration: none; }
.topbar {
  color: #fff;
  background: var(--odp-black);
  border-bottom: 4px solid var(--odps-violet);
}
.topbar-inner,
.wrap {
  width: min(1180px, calc(100% - (var(--space-6) * 2)));
  margin: 0 auto;
}
.topbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-height: 58px;
}
.brand {
  font-weight: 700;
}
.language-selector {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: .82rem;
}
.language-selector span {
  padding: var(--space-1) var(--space-2);
  border: 1px solid rgba(255,255,255,.35);
  border-radius: 8px;
  font-weight: 800;
  text-transform: uppercase;
}
.language-selector div {
  display: flex;
  gap: var(--space-2);
}
.language-selector a {
  color: rgba(255,255,255,.76);
  font-weight: 700;
  text-transform: uppercase;
}
.language-selector a[aria-current="true"] {
  color: #fff;
}
html[dir="rtl"] .topbar-inner,
html[dir="rtl"] .section-head,
html[dir="rtl"] .product-modal-header {
  direction: rtl;
}
html[dir="rtl"] .language-selector div {
  flex-direction: row-reverse;
}
.hero {
  color: #fff;
  background:
    linear-gradient(135deg, rgba(108, 42, 142, .96), rgba(30, 10, 46, .94)),
    var(--odps-violet);
}
.hero .wrap {
  padding-block: var(--space-16) var(--space-12);
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 0 var(--space-3);
  color: var(--odps-violet);
  font-size: .78rem;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.hero .eyebrow { color: rgba(255, 255, 255, .82); }
h1 {
  max-width: 780px;
  margin: 0 0 var(--space-4);
  font-size: clamp(2.25rem, 5vw, 4.55rem);
  line-height: 1.02;
  font-weight: 600;
  letter-spacing: 0;
}
h2 {
  margin: 0;
  font-size: clamp(1.35rem, 2.5vw, 2rem);
  line-height: 1.12;
  font-weight: 600;
}
h3 {
  margin: 0 0 8px;
  font-size: 1.08rem;
  line-height: 1.25;
}
.lead {
  max-width: 760px;
  margin: 0;
  color: rgba(255, 255, 255, .86);
  font-size: clamp(1rem, 2vw, 1.18rem);
}
main {
  padding-block: var(--space-6) var(--space-16);
}
.tab-radio {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}
.tabs {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  padding-block: var(--space-3);
  background: rgba(255, 255, 255, .96);
  border-top: 1px solid var(--odp-line);
  border-bottom: 1px solid var(--odp-line);
  backdrop-filter: blur(10px);
}
.tabs label {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  color: var(--odp-muted);
  background: #fff;
  cursor: pointer;
  font-size: .9rem;
  font-weight: 700;
}
#tab-overview:checked ~ .tabs label[for="tab-overview"],
#tab-executive-summary:checked ~ .tabs label[for="tab-executive-summary"],
#tab-objectives:checked ~ .tabs label[for="tab-objectives"],
#tab-use-cases:checked ~ .tabs label[for="tab-use-cases"],
#tab-products:checked ~ .tabs label[for="tab-products"],
#tab-signals:checked ~ .tabs label[for="tab-signals"],
#tab-graph:checked ~ .tabs label[for="tab-graph"],
#tab-about:checked ~ .tabs label[for="tab-about"] {
  color: #fff;
  border-color: var(--odps-violet);
  background: var(--odps-violet);
}
.tab-panel {
  display: none;
  padding-top: var(--space-8);
}
#tab-overview:checked ~ .panels .overview-panel,
#tab-executive-summary:checked ~ .panels .executive-summary-panel,
#tab-objectives:checked ~ .panels .objectives-panel,
#tab-use-cases:checked ~ .panels .use-cases-panel,
#tab-products:checked ~ .panels .products-panel,
#tab-signals:checked ~ .panels .signals-panel,
#tab-graph:checked ~ .panels .graph-panel,
#tab-about:checked ~ .panels .about-panel {
  display: block;
}
.section-head {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: var(--space-6);
  margin-bottom: var(--space-6);
}
.section-head p {
  max-width: 540px;
  margin: 0;
  color: var(--odp-muted);
}
.summary {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--space-6);
  margin: 0 0 var(--space-8);
}
.metric,
.card,
.panel {
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 16px 42px rgba(15, 23, 42, .09);
}
.metric {
  min-height: 104px;
  padding: var(--space-4);
}
.metric strong {
  display: block;
  font-size: 2.1rem;
  line-height: 1;
}
.metric span {
  display: block;
  margin-top: var(--space-2);
  color: var(--odp-muted);
  font-size: .8rem;
  font-weight: 700;
  text-transform: uppercase;
}
.grid,
.actions-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
}
.executive-dashboard-intro,
.decision-card,
.leadership-recommendation,
.executive-list,
.executive-empty {
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(30, 10, 46, .06);
}
.executive-dashboard-intro {
  padding: var(--space-8);
  margin-bottom: var(--space-6);
}
.leadership-recommendation {
  padding: var(--space-6);
  margin: 0 0 var(--space-8);
  border-color: #c4b5fd;
  border-left: 6px solid #6d28d9;
  background: #f5f3ff;
  box-shadow: 0 18px 44px rgba(88, 28, 135, .12);
}
.recommendation-label,
.priority-label,
.priority-action span {
  display: block;
  color: var(--odp-muted);
  font-size: .76rem;
  font-weight: 800;
  text-transform: uppercase;
}
.leadership-recommendation p {
  margin: var(--space-2) 0 0;
  color: var(--odp-ink);
  font-size: 1.05rem;
  font-weight: 800;
  line-height: 1.35;
}
.executive-dashboard-intro p,
.executive-empty p {
  margin: 0;
  color: var(--odp-muted);
}
.decision-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: var(--space-8);
  margin-bottom: var(--space-6);
}
.decision-card,
.executive-list,
.executive-empty {
  padding: var(--space-6);
}
.decision-card {
  display: flex;
  flex-direction: column;
  min-height: 174px;
  border-top: 6px solid #64748b;
  box-shadow: 0 18px 44px rgba(15, 23, 42, .11);
}
.primary-focus {
  border-color: #bfdbfe;
  border-top-color: #2563eb;
  background: linear-gradient(135deg, #eff6ff 0%, #f8fbff 100%);
}
.secondary-focus {
  border-color: #bfdbfe;
  border-top-color: #3b82f6;
  background: linear-gradient(135deg, #f1f7ff 0%, #fbfdff 100%);
}
.risk-focus {
  border-color: #fed7aa;
  border-top-color: #d97706;
  background: linear-gradient(135deg, #fff7ed 0%, #fffbf5 100%);
}
.readiness-focus {
  border-color: #d8d6e4;
  border-top-color: #6d5f9f;
  background: linear-gradient(135deg, #f7f5fb 0%, #fcfbff 100%);
}
.decision-card-head {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.decision-card-icon {
  flex: 0 0 44px;
  width: 44px;
  height: 44px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: #dbeafe;
  border: 1px solid rgba(37, 99, 235, .18);
  box-shadow: 0 12px 26px rgba(37, 99, 235, .24);
}
.decision-card-icon img {
  width: 30px;
  height: 30px;
  display: block;
  object-fit: contain;
}
.secondary-focus .decision-card-icon {
  background: #eff6ff;
  border-color: rgba(59, 130, 246, .18);
  box-shadow: 0 12px 26px rgba(59, 130, 246, .2);
}
.risk-focus .decision-card-icon {
  background: #ffedd5;
  border-color: rgba(217, 119, 6, .22);
  box-shadow: 0 12px 26px rgba(217, 119, 6, .22);
}
.readiness-focus .decision-card-icon {
  background: #ede9fe;
  border-color: rgba(109, 95, 159, .2);
  box-shadow: 0 12px 26px rgba(109, 95, 159, .2);
}
.decision-card h3 {
  margin: var(--space-1) 0 0;
  font-size: 1.2rem;
}
.decision-insight {
  margin: var(--space-4) 0 0;
  color: var(--odp-muted);
  font-size: .95rem;
  line-height: 1.4;
}
.priority-action {
  display: flex;
  gap: var(--space-2);
  margin: var(--space-4) 0 0;
  padding-top: var(--space-3);
  border-top: 1px solid var(--odp-line);
}
.priority-action p {
  margin: 0;
  color: var(--odp-ink);
  font-size: .92rem;
}
.primary-focus .priority-action span,
.primary-focus .priority-label,
.primary-focus .decision-details-trigger {
  color: #1d4ed8;
}
.secondary-focus .priority-action span,
.secondary-focus .priority-label,
.secondary-focus .decision-details-trigger {
  color: #2563eb;
}
.risk-focus .priority-action span,
.risk-focus .priority-label,
.risk-focus .decision-details-trigger {
  color: #c2410c;
}
.readiness-focus .priority-action span,
.readiness-focus .priority-label,
.readiness-focus .decision-details-trigger {
  color: #5b4f8a;
}
.decision-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-top: auto;
  padding-top: var(--space-4);
}
.priority-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: 0;
}
.metadata-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 26px;
  padding: var(--space-1) var(--space-3);
  border: 1px solid #d7deea;
  border-radius: 7px;
  background: rgba(255, 255, 255, .72);
  color: var(--odp-ink);
  font-size: .82rem;
  font-weight: 800;
  box-shadow: 0 4px 12px rgba(15, 23, 42, .08);
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #64748b;
}
.confidence-high .status-dot {
  background: #059669;
}
.confidence-medium .status-dot {
  background: #f59e0b;
}
.confidence-low .status-dot {
  background: #e11d48;
}
.evidence-badge {
  color: #1d4ed8;
}
.evidence-icon {
  position: relative;
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-radius: 999px;
}
.evidence-direct .evidence-icon::after {
  content: "";
  position: absolute;
  left: 3px;
  top: 3px;
  width: 4px;
  height: 4px;
  border-radius: 999px;
  background: currentColor;
}
.evidence-inferred .evidence-icon {
  border-radius: 2px;
}
.evidence-inferred .evidence-icon::after {
  content: "";
  position: absolute;
  left: 2px;
  right: 2px;
  top: 4px;
  border-top: 2px solid currentColor;
}
.decision-details-toggle {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.decision-details-trigger {
  display: flex;
  justify-content: flex-end;
  cursor: pointer;
  font-size: .86rem;
  font-weight: 800;
}
.decision-details-label-open {
  display: none;
}
.decision-details-toggle:checked ~ .decision-card-footer .decision-details-label-closed {
  display: none;
}
.decision-details-toggle:checked ~ .decision-card-footer .decision-details-label-open {
  display: inline;
}
.decision-details-dropdown {
  display: none;
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--odp-line);
  color: var(--odp-muted);
  font-size: .86rem;
}
.decision-details-toggle:checked ~ .decision-details-dropdown {
  display: block;
}
.decision-details-dropdown h4 {
  margin: var(--space-3) 0 var(--space-2);
  color: var(--odp-ink);
  font-size: .82rem;
}
.decision-details-dropdown ul {
  margin: 0;
  padding-left: var(--space-6);
}
.decision-details-dropdown li {
  margin: var(--space-1) 0;
}
.executive-list {
  margin-top: var(--space-6);
}
.executive-item {
  padding-block: var(--space-4);
  border-top: 1px solid var(--odp-line);
}
.executive-item:first-of-type {
  border-top: 0;
  padding-top: 0;
}
.executive-item p {
  margin: 0 0 var(--space-3);
}
.business-evidence {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--odp-line);
}
.business-evidence h4 {
  margin: 0 0 var(--space-2);
  color: var(--odp-muted);
  font-size: .8rem;
  text-transform: uppercase;
}
.business-evidence ul,
.technical-evidence ul {
  margin: 0;
  padding-left: var(--space-6);
}
.business-evidence li {
  margin: var(--space-1) 0;
}
.priority-evidence {
  color: var(--odp-ink);
}
.technical-evidence {
  margin-top: var(--space-3);
  color: var(--odp-muted);
  font-size: .85rem;
}
.technical-evidence summary {
  cursor: pointer;
  font-weight: 700;
}
.evidence-refs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.evidence-ref small {
  color: var(--odp-muted);
  font-weight: 700;
}
.chip.warning {
  border-color: #d97706;
  color: #92400e;
  background: #fffbeb;
}
.product-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
}
.card {
  position: relative;
  min-height: 216px;
  padding: var(--space-6);
}
.card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  border-radius: 8px 0 0 8px;
  background: var(--odpc-orange);
}
.card.product::before { background: var(--odps-violet); }
.card.signal::before { background: var(--odpv-blue); }
.wide { grid-column: span 2; }
.product-card {
  display: flex;
  flex-direction: column;
  min-height: 280px;
}
.product-card-description {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.product-review-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: var(--space-2) 0;
}
.product-review-note {
  margin: 0 0 var(--space-3);
  color: #92400e;
  font-size: .85rem;
  font-weight: 700;
}
.product-card-counters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: var(--space-4) 0;
}
.product-card-counters span {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: 999px;
  background: var(--odp-soft);
  color: var(--odp-muted);
  font-size: .78rem;
  font-weight: 800;
}
.product-card-counters strong {
  color: var(--odp-ink);
}
.product-card-actions {
  margin-top: auto;
}
.product-detail-button,
.product-modal-close {
  min-height: 36px;
  border: 0;
  border-radius: 8px;
  background: var(--odps-violet);
  color: #fff;
  cursor: pointer;
  font-weight: 800;
}
.product-detail-button {
  width: 100%;
}
.product-modal-close {
  padding-inline: var(--space-4);
}
.product-detail-button:hover,
.product-modal-close:hover {
  background: #4f1f68;
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}
.chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: var(--space-1) var(--space-2);
  border-radius: 999px;
  background: var(--odp-soft);
  color: var(--odp-muted);
  font-size: .74rem;
  font-weight: 700;
  text-transform: uppercase;
}
.chip.odps { color: #fff; background: var(--odps-violet); }
.chip.odpc { color: #fff; background: var(--odpc-orange); }
.chip.odpg { color: #fff; background: var(--odpg-green); }
.chip.odpv { color: #fff; background: var(--odpv-blue); }
.card p,
.panel p,
.action-card p {
  margin: 0 0 var(--space-4);
  color: var(--odp-muted);
}
.odp-facts {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: var(--space-2) var(--space-3);
  margin: 0;
  font-size: .9rem;
}
html[dir="rtl"] .odp-facts {
  grid-template-columns: 1fr max-content;
}
.odp-facts dt {
  color: var(--odp-muted);
  font-weight: 700;
}
.odp-facts dd { margin: 0; }
.component-section {
  margin-top: var(--space-6);
}
.component-section h4 {
  margin: 0 0 var(--space-3);
}
.product-detail-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(240px, 320px);
  gap: 18px;
  align-items: start;
  margin-bottom: 22px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--odp-line);
}
.product-detail-description {
  margin: 0;
  color: var(--odp-ink);
  font-size: 1.02rem;
  line-height: 1.55;
}
.product-detail-meta {
  padding: 14px;
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  background: var(--odp-soft);
}
.product-marketplace-segments {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.market-segment {
  min-width: 0;
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}
.market-segment h4 {
  margin: 0 0 12px;
  font-size: .86rem;
  letter-spacing: .04em;
  text-transform: uppercase;
}
.market-plan-list,
.market-profile-list {
  display: grid;
  gap: 12px;
}
.market-plan-card,
.market-profile-card,
.market-license-card {
  min-width: 0;
}
.market-plan-card + .market-plan-card,
.market-profile-card + .market-profile-card {
  padding-top: 12px;
  border-top: 1px solid var(--odp-line);
}
.market-plan-card h5,
.market-profile-card h5 {
  margin: 0 0 6px;
  font-size: 1rem;
}
.market-plan-card p,
.market-profile-card p {
  margin: 0 0 10px;
  color: var(--odp-muted);
}
.component-refs {
  list-style: none;
  margin: 0;
  padding: 0;
}
.profile-chip {
  display: inline-flex;
  margin-bottom: var(--space-3);
  padding: var(--space-1) var(--space-2);
  border-radius: 999px;
  background: var(--odp-soft);
  color: var(--odp-muted);
  font-size: .72rem;
  font-weight: 800;
  text-transform: uppercase;
}
.dimension-metric,
.dimension-weight {
  display: inline-flex;
  padding: var(--space-1) var(--space-2);
  border-radius: 999px;
  background: #fff;
  color: var(--odp-ink);
  font-size: .78rem;
  font-weight: 800;
  white-space: nowrap;
}
.component-refs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
  color: var(--odp-muted);
  font-size: .82rem;
}
.component-refs li {
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--odp-soft);
}
.dimension-summary-list {
  display: grid;
  gap: 8px;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}
.dimension-summary-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  min-width: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--odp-soft);
  font-size: .88rem;
  font-weight: 700;
}
.dimension-summary-item span:first-child {
  min-width: 0;
  overflow-wrap: anywhere;
}
.dimension-summary-item.muted {
  color: var(--odp-muted);
  font-weight: 700;
}
.modal-open {
  overflow: hidden;
}
.product-modal {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: none;
  padding: var(--space-8);
}
.product-modal[aria-hidden="false"] {
  display: block;
}
.product-modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(5, 5, 5, .64);
}
.product-modal-panel {
  position: relative;
  width: min(1120px, calc(100vw - (var(--space-8) * 2)));
  max-height: calc(100vh - (var(--space-8) * 2));
  margin: 0 auto;
  overflow: auto;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 24px 80px rgba(0, 0, 0, .28);
}
.product-modal-header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-6);
  border-bottom: 1px solid var(--odp-line);
  background: #fff;
}
.product-modal-header h3 {
  margin: 0;
  font-size: 1.45rem;
}
.product-detail-layout {
  margin: 0;
  padding: var(--space-6);
  border-top: 0;
}
.odp-muted { color: var(--odp-muted); }
.odp-detail {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--odp-line);
}
.action-card,
.overview-card {
  border: 1px solid #ded2e8;
  border-radius: 8px;
  background: var(--odp-soft);
  box-shadow: 0 14px 34px rgba(30, 10, 46, .06);
}
.action-card {
  padding: var(--space-6);
}
.action-card strong {
  display: block;
  margin: var(--space-2) 0;
}
.action-link,
.version-action {
  color: var(--odps-violet);
  cursor: pointer;
  font-weight: 700;
}
.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: var(--space-6);
}
.overview-section {
  margin-top: var(--space-8);
}
.overview-card-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-6);
}
.change-story-list {
  display: grid;
  gap: var(--space-2);
  margin: var(--space-4) 0 0;
  padding-left: var(--space-6);
  color: var(--odp-muted);
}
.panel { padding: var(--space-6); }
.version-list {
  margin: 0;
  padding: 0;
}
.version-list li {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  margin: 0 0 var(--space-2);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--odp-line);
  list-style: none;
}
.version-history {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--odp-line);
}
.version-table {
  width: 100%;
  max-width: 100%;
  margin-top: var(--space-3);
  border-collapse: collapse;
  table-layout: fixed;
  font-size: .9rem;
}
.version-table th,
.version-table td {
  padding: var(--space-2);
  border-bottom: 1px solid var(--odp-line);
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.version-table th {
  color: var(--odp-muted);
  font-size: .76rem;
  text-transform: uppercase;
}
.version-table th:nth-child(1),
.version-table td:nth-child(1) {
  width: 48%;
}
.version-table th:nth-child(2),
.version-table td:nth-child(2) {
  width: 24%;
}
.version-table th:nth-child(3),
.version-table td:nth-child(3) {
  display: none;
}
.version-table th:nth-child(4),
.version-table td:nth-child(4) {
  width: 28%;
  text-align: right;
}
.version-row a:first-child,
.version-row strong {
  min-width: 0;
  overflow-wrap: anywhere;
}
.graph-explorer-frame {
  display: block;
  width: 100%;
  height: min(900px, calc(100vh - 180px));
  min-height: 680px;
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  background: #eef2f7;
  box-shadow: 0 12px 32px rgba(30, 10, 46, .06);
}
.about-card {
  padding: var(--space-8);
  border-radius: 8px;
  color: #fff;
  background: var(--odp-ink);
}
.about-card p {
  max-width: 820px;
  color: rgba(255, 255, 255, .82);
}
.about-card .chip {
  color: #fff;
  background: rgba(255, 255, 255, .12);
}
.footer {
  margin-top: var(--space-12);
  padding-block: var(--space-8);
  color: rgba(255, 255, 255, .78);
  background: var(--odp-black);
  border-top: 4px solid var(--odps-violet);
  font-size: .92rem;
}
.footer-inner {
  display: grid;
  gap: var(--space-6);
}
.footer-status {
  margin: 0;
  max-width: 880px;
  color: rgba(255, 255, 255, .88);
}
.footer-columns {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-6);
}
.footer-column h2 {
  margin: 0 0 var(--space-3);
  color: #fff;
  font-size: .82rem;
  letter-spacing: .04em;
  text-transform: uppercase;
}
.footer-column ul {
  display: grid;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}
.footer-column li {
  min-width: 0;
}
.footer-column a {
  color: #fff;
  font-weight: 700;
}
.footer-column span {
  color: rgba(255, 255, 255, .62);
}
@media (max-width: 900px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
  .footer-columns {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .grid,
  .actions-grid,
  .decision-card-grid,
  .product-grid {
    grid-template-columns: 1fr;
  }
  .product-modal {
    padding: var(--space-3);
  }
  .product-modal-panel {
    width: calc(100vw - (var(--space-3) * 2));
    max-height: calc(100vh - (var(--space-3) * 2));
  }
  .product-modal-header {
    align-items: start;
  }
  .product-detail-hero,
  .product-marketplace-segments {
    grid-template-columns: 1fr;
  }
  .wide { grid-column: auto; }
}
@media (max-width: 640px) {
  .wrap,
  .topbar-inner {
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
  .executive-dashboard-intro,
  .about-card {
    padding: var(--space-6);
  }
  .footer-columns {
    grid-template-columns: 1fr;
  }
}
"""


def portfolio_js() -> str:
    return """<script>
(function () {
  var activeModal = null;
  function closeModal() {
    if (!activeModal) return;
    activeModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    activeModal = null;
  }
  function openModal(id) {
    var modal = document.getElementById(id);
    if (!modal) return;
    closeModal();
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    activeModal = modal;
    var closeButton = modal.querySelector("[data-modal-close]");
    if (closeButton) closeButton.focus();
  }
  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-modal-target]");
    if (trigger) {
      openModal(trigger.getAttribute("data-modal-target"));
      return;
    }
    if (event.target.closest("[data-modal-close]")) {
      closeModal();
    }
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeModal();
  });
}());
</script>"""
