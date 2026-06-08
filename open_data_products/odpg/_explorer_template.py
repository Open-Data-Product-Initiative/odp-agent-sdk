"""HTML/CSS/JS template for the ODPG graph explorer.

Extracted from the upstream ``generate_graph_explorer.py`` script to keep the
Python graph module focused on graph logic. The string is interpolated via
f-string so the call site stays readable; do not switch to ``str.format``
(CSS braces would all need escaping).
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List


def render_explorer(
    *,
    graph_title: str,
    graph_meta: str,
    relationship_types: List[str],
    node_types: List[str],
    confidence_levels: List[str],
    vis_nodes: List[Dict[str, Any]],
    vis_edges: List[Dict[str, Any]],
    legend_edges_html: str,
    odpg_supported_ordered_json: str,
    odpg_descriptions_json: str,
) -> str:
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ODPG Graph Explorer — {html.escape(graph_title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
  <style>
    :root {{
      --topbar-bg: #005316;
      --topbar-fg: #f8fafc;
      --topbar-muted: #fff;
      --canvas-bg: #ffffff;
      --border: #e2e8f0;
      --inspector-bg: #f8fafc;
      --accent: #2563eb;
    }}

    * {{ box-sizing: border-box; }}

    html {{
      height: 100%;
    }}

    body {{
      margin: 0;
      font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
      background: #eef2f7;
      color: #0f172a;
      height: 100%;
      max-height: 100dvh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}

    html:fullscreen {{
      width: 100%;
      height: 100%;
      background: #eef2f7;
    }}

    html:fullscreen body {{
      max-height: none;
      height: 100%;
    }}

    .topbar {{
      flex-shrink: 0;
      display: grid;
      grid-template-columns: minmax(160px, 1fr) minmax(0, 2.2fr) minmax(160px, 1fr);
      align-items: center;
      gap: 12px;
      padding: 10px 20px;
      background: var(--topbar-bg);
      color: var(--topbar-fg);
      border-bottom: 1px solid #003d10;
      min-height: 52px;
    }}

    .topbar-brand {{
      font-weight: 700;
      font-size: 14px;
      letter-spacing: 0.02em;
      color: var(--topbar-fg);
    }}

    .topbar-center {{
      display: grid;
      gap: 6px;
      text-align: center;
      min-width: 0;
    }}

    .topbar-graph-heading {{
      min-width: 0;
    }}

    .topbar-search {{
      position: relative;
      min-width: 220px;
      max-width: 460px;
      width: 100%;
      justify-self: center;
    }}

    .topbar-search input {{
      width: 100%;
      height: 36px;
      border: 1px solid rgba(255, 255, 255, 0.32);
      border-radius: 8px;
      padding: 0 12px 0 36px;
      background: rgba(255, 255, 255, 0.12);
      color: #ffffff;
      font-size: 13px;
      outline: none;
    }}

    .topbar-search input::placeholder {{
      color: rgba(255, 255, 255, 0.76);
    }}

    .topbar-search input:focus {{
      background: #ffffff;
      color: #0f172a;
      border-color: #bfdbfe;
      box-shadow: 0 0 0 3px rgba(191, 219, 254, 0.22);
    }}

    .topbar-search svg {{
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      color: rgba(255, 255, 255, 0.82);
      pointer-events: none;
    }}

    .topbar-search:focus-within svg {{
      color: #64748b;
    }}

    .search-results {{
      position: absolute;
      top: calc(100% + 8px);
      left: 0;
      right: 0;
      z-index: 20;
      display: none;
      max-height: 280px;
      overflow-y: auto;
      padding: 6px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #ffffff;
      box-shadow: 0 12px 30px rgba(15, 23, 42, 0.18);
    }}

    .search-result {{
      display: grid;
      grid-template-columns: 10px 1fr;
      gap: 9px;
      align-items: center;
      width: 100%;
      padding: 8px;
      border: none;
      border-radius: 6px;
      background: transparent;
      color: #0f172a;
      text-align: left;
      cursor: pointer;
    }}

    .search-result:hover,
    .search-result.is-active {{
      background: #f1f5f9;
    }}

    .search-result-dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
    }}

    .search-result strong {{
      display: block;
      font-size: 12px;
      line-height: 1.25;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .search-result span {{
      display: block;
      margin-top: 2px;
      font-size: 11px;
      color: #64748b;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    .topbar-graph-title {{
      display: block;
      font-size: 17px;
      font-weight: 600;
      line-height: 1.25;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .topbar-graph-meta {{
      display: block;
      font-size: 12px;
      color: var(--topbar-muted);
      margin-top: 2px;
    }}

    .topbar-actions {{
      display: flex;
      justify-content: flex-end;
      gap: 6px;
    }}

    .icon-btn {{
      width: 36px;
      height: 36px;
      border: none;
      border-radius: 8px;
      background: transparent;
      color: var(--topbar-muted);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }}

    .icon-btn:hover {{
      background: rgba(148, 163, 184, 0.15);
      color: var(--topbar-fg);
    }}

    .workspace {{
      flex: 1 1 auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}

    .workspace-main {{
      flex: 1 1 auto;
      min-height: 0;
      display: grid;
      grid-template-columns: 1fr minmax(280px, 380px);
      grid-template-rows: 1fr;
      overflow: hidden;
    }}

    .canvas-col {{
      display: flex;
      flex-direction: column;
      background: var(--canvas-bg);
      min-height: 0;
      min-width: 0;
      overflow: hidden;
    }}

    .canvas-graph-area {{
      position: relative;
      flex: 1 1 auto;
      min-height: 120px;
      min-width: 0;
    }}

    #graph {{
      width: 100%;
      height: 100%;
      min-height: 0;
    }}

    .vis-tooltip,
    div.vis-network-tooltip {{
      white-space: pre-line !important;
    }}

    .minimap {{
      position: absolute;
      top: 12px;
      left: 12px;
      width: 200px;
      height: 132px;
      z-index: 5;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
      overflow: hidden;
    }}

    .graph-tools {{
      position: absolute;
      top: 50%;
      left: 12px;
      transform: translateY(-50%);
      z-index: 6;
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 6px;
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 10px;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
    }}

    .graph-tools button {{
      width: 34px;
      height: 34px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #fff;
      font-size: 18px;
      line-height: 1;
      cursor: pointer;
      color: #334155;
    }}

    .graph-tools button:hover {{
      background: #f1f5f9;
    }}

    .graph-tools button.is-locked {{
      background: #e0f2fe;
      border-color: #7dd3fc;
      color: #0369a1;
    }}

    .graph-legend {{
      flex-shrink: 0;
      width: 100%;
      background: #f8fafc;
      border-top: 1px solid var(--border);
      padding: 10px 18px 12px;
      overflow-x: auto;
      overflow-y: visible;
    }}

    .graph-legend-inner {{
      display: grid;
      grid-template-columns: 1fr auto 1.15fr;
      gap: 0 20px;
      align-items: stretch;
      max-width: 100%;
    }}

    .graph-legend-divider {{
      width: 1px;
      background: #e2e8f0;
      margin: 4px 0;
    }}

    .graph-legend-title {{
      margin: 0 0 10px;
      font-size: 11px;
      font-weight: 700;
      color: #475569;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .graph-legend-node-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px 14px;
    }}

    .graph-legend-edge-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px 12px;
    }}

    @media (max-width: 1100px) {{
      .graph-legend-node-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .graph-legend-edge-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}

    .legend-node-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      font-weight: 500;
      color: #1e293b;
      white-space: nowrap;
    }}

    .legend-node-dot {{
      width: 13px;
      height: 13px;
      border-radius: 50%;
      flex-shrink: 0;
      box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.18);
    }}

    .legend-edge-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 11px;
      font-weight: 600;
      color: #334155;
      letter-spacing: 0.02em;
    }}

    .legend-edge-item svg {{
      flex-shrink: 0;
    }}

    .odpg-footer {{
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      gap: 14px;
      padding: 12px 20px 14px;
      border-top: 1px solid rgba(255, 255, 255, 0.18);
      background: linear-gradient(180deg, #0a6b22 0%, var(--topbar-bg) 100%);
      color: #ecfdf5;
      font-size: 12px;
      line-height: 1.45;
    }}

    .odpg-footer-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }}

    .odpg-footer-brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      font-weight: 600;
      color: #f0fdf4;
      font-size: 24px;
    }}

    .odpg-footer-mark {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border-radius: 8px;
      background: rgba(0, 0, 0, 0.25);
      color: #ffffff;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.04em;
      flex-shrink: 0;
    }}

    .odpg-footer-link {{
      color: #bbf7d0;
      font-weight: 700;
      text-decoration: none;
      white-space: nowrap;
    }}

    .odpg-footer-link:hover {{
      text-decoration: underline;
      color: #ffffff;
    }}

    .odpg-footer-resources {{
      display: flex;
      flex-direction: row;
      flex-wrap: nowrap;
      align-items: center;
      gap: 8px 14px;
      min-width: 0;
      width: 100%;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }}

    .odpg-footer-resources h3 {{
      margin: 0;
      flex-shrink: 0;
      font-size: 11px;
      font-weight: 700;
      color: #bbf7d0;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      white-space: nowrap;
    }}

    .odpg-footer-resources a {{
      flex-shrink: 0;
      white-space: nowrap;
      color: #ffffff;
      font-weight: 600;
      text-decoration: underline;
      text-underline-offset: 2px;
    }}

    .odpg-footer-resources a:hover {{
      color: #fef08a;
    }}

    @media (max-width: 760px) {{
      .odpg-footer-top {{
        align-items: flex-start;
        flex-direction: column;
        gap: 8px;
      }}
    }}

    .inspector {{
      border-left: 1px solid var(--border);
      background: var(--inspector-bg);
      display: flex;
      flex-direction: column;
      min-height: 0;
      min-width: 0;
    }}

    .inspector-tabs {{
      display: flex;
      border-bottom: 1px solid var(--border);
      background: #fff;
    }}

    .inspector-tabs button {{
      flex: 1;
      padding: 12px 10px;
      border: none;
      background: transparent;
      font-size: 13px;
      font-weight: 600;
      color: #64748b;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      margin-bottom: -1px;
    }}

    .inspector-tabs button.is-active {{
      color: var(--accent);
      border-bottom-color: var(--accent);
      background: #f8fafc;
    }}

    .filter-panel {{
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      gap: 12px;
      max-height: min(44vh, 430px);
      overflow-y: auto;
      padding: 14px 16px;
      border-top: 1px solid var(--border);
      background: #ffffff;
    }}

    .filter-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}

    .filter-head h2 {{
      margin: 0;
      font-size: 13px;
      font-weight: 800;
      color: #334155;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}

    .filter-actions {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
    }}

    .filter-reset {{
      border: 1px solid var(--border);
      border-radius: 7px;
      background: #f8fafc;
      color: #334155;
      cursor: pointer;
      font-size: 12px;
      font-weight: 700;
      padding: 6px 9px;
    }}

    .filter-reset:hover {{
      background: #eef2f7;
    }}

    .filter-status {{
      margin: -5px 0 0;
      font-size: 12px;
      color: #64748b;
    }}

    .filter-group h3 {{
      margin: 0 0 8px;
      font-size: 11px;
      font-weight: 800;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    .filter-options {{
      display: grid;
      gap: 6px;
    }}

    .filter-option {{
      display: grid;
      grid-template-columns: 16px 12px minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
      min-height: 28px;
      padding: 4px 6px;
      border-radius: 6px;
      color: #1e293b;
      cursor: pointer;
      font-size: 12px;
      user-select: none;
    }}

    .filter-option:hover {{
      background: #f8fafc;
    }}

    .filter-option.is-muted {{
      opacity: 0.45;
    }}

    .filter-option input {{
      width: 14px;
      height: 14px;
      margin: 0;
      accent-color: var(--accent);
      cursor: pointer;
    }}

    .filter-swatch {{
      width: 11px;
      height: 11px;
      border-radius: 999px;
      box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.18);
    }}

    .filter-label {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 600;
    }}

    .filter-count {{
      color: #64748b;
      font-size: 11px;
      font-weight: 700;
    }}

    .inspector-panel {{
      flex: 1;
      overflow-y: auto;
      padding: 16px 18px 20px;
    }}

    .inspector-panel.is-hidden {{
      display: none;
    }}

    .panel-placeholder {{
      color: #64748b;
      font-size: 14px;
      line-height: 1.5;
    }}

    .panel-head {{
      display: flex;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 18px;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--border);
    }}

    .type-dot {{
      width: 40px;
      height: 40px;
      border-radius: 999px;
      flex-shrink: 0;
      border: 2px solid rgba(255, 255, 255, 0.95);
      box-shadow: 0 2px 6px rgba(15, 23, 42, 0.12);
    }}

    .panel-head h2 {{
      margin: 0;
      font-size: 15px;
      font-weight: 700;
      line-height: 1.3;
    }}

    .panel-head .sub {{
      margin: 4px 0 0;
      font-size: 12px;
      color: #64748b;
      font-weight: 500;
    }}

    .field {{
      margin-bottom: 14px;
    }}

    .field label {{
      display: block;
      font-size: 11px;
      font-weight: 700;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}

    .field span, .field p {{
      display: block;
      margin-top: 5px;
      font-size: 13px;
      color: #0f172a;
      word-break: break-word;
      line-height: 1.45;
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-brand"><img src="https://github.com/Open-Data-Product-Initiative/odpg-v1.0/blob/main/source/images/odpg-white.png?raw=true" alt="ODPG Logo" width="100"></div>
    <div class="topbar-center">
      <div class="topbar-graph-heading">
        <span class="topbar-graph-title">{html.escape(graph_title)}</span>
        <span class="topbar-graph-meta">{html.escape(graph_meta)}</span>
      </div>
      <div class="topbar-search">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
        <input id="node-search" type="search" placeholder="Search nodes in {html.escape(graph_title)}" autocomplete="off" aria-label="Search graph nodes">
        <div id="search-results" class="search-results" role="listbox" aria-label="Node search results"></div>
      </div>
    </div>
    <div class="topbar-actions">
      <button type="button" class="icon-btn" title="Fit graph" id="btn-fit-top">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
      </button>
      <button type="button" class="icon-btn" title="Fullscreen" id="btn-fullscreen">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>
      </button>
      <button type="button" class="icon-btn" title="About">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
      </button>
    </div>
  </header>

  <div class="workspace">
    <div class="workspace-main">
    <div class="canvas-col">
      <div class="canvas-graph-area">
      <nav class="graph-tools" aria-label="Zoom and layout">
        <button type="button" id="btn-zoom-in" title="Zoom in">+</button>
        <button type="button" id="btn-zoom-out" title="Zoom out">−</button>
        <button type="button" id="btn-fit" title="Fit view">⊙</button>
        <button type="button" id="btn-physics" title="Toggle physics (layout)">◎</button>
      </nav>
      <div id="minimap" class="minimap" aria-label="Overview map"></div>
      <div id="graph"></div>
      </div>
    </div>

    <aside class="inspector">
      <div class="inspector-tabs" role="tablist">
        <button type="button" id="tab-node" class="is-active" role="tab" aria-selected="true">Node details</button>
        <button type="button" id="tab-edge" role="tab" aria-selected="false">Edge details</button>
      </div>
      <div id="panel-node" class="inspector-panel" role="tabpanel">
        <p class="panel-placeholder" id="node-placeholder">Select a node on the graph to see ID, type, reference, and description.</p>
        <div id="node-detail" style="display:none"></div>
      </div>
      <div id="panel-edge" class="inspector-panel is-hidden" role="tabpanel">
        <p class="panel-placeholder" id="edge-placeholder">Select an edge to see relationship type and confidence.</p>
        <div id="edge-detail" style="display:none"></div>
      </div>
      <section class="filter-panel" aria-label="Graph filters">
        <div class="filter-head">
          <h2>Filters</h2>
          <div class="filter-actions">
            <button type="button" id="btn-toggle-filters" class="filter-reset">Deselect all</button>
            <button type="button" id="btn-reset-filters" class="filter-reset">Reset</button>
          </div>
        </div>
        <p id="filter-status" class="filter-status"></p>
        <div class="filter-group">
          <h3>Node types</h3>
          <div id="filter-node-types" class="filter-options"></div>
        </div>
        <div class="filter-group">
          <h3>Relationship types</h3>
          <div id="filter-edge-types" class="filter-options"></div>
        </div>
        <div class="filter-group">
          <h3>Confidence</h3>
          <div id="filter-confidence" class="filter-options"></div>
        </div>
      </section>
    </aside>
    </div>

    <div class="graph-legend" role="region" aria-label="Graph legend">
        <div class="graph-legend-inner">
          <div class="graph-legend-col">
            <h3 class="graph-legend-title">Node Types</h3>
            <div class="graph-legend-node-grid">
              <div class="legend-node-item"><span class="legend-node-dot" style="background:#16a34a"></span>UseCase</div>
              <div class="legend-node-item"><span class="legend-node-dot" style="background:#0284c7"></span>DataProduct</div>
              <div class="legend-node-item"><span class="legend-node-dot" style="background:#7c3aed"></span>API</div>
              <div class="legend-node-item"><span class="legend-node-dot" style="background:#ea580c"></span>BusinessObjective</div>
              <div class="legend-node-item"><span class="legend-node-dot" style="background:#0891b2"></span>Signal</div>
              <div class="legend-node-item"><span class="legend-node-dot" style="background:#0d9488"></span>KPI</div>
              <div class="legend-node-item"><span class="legend-node-dot" style="background:#db2777"></span>Policy</div>
              <div class="legend-node-item"><span class="legend-node-dot" style="background:#0e7490"></span>Agent</div>
              <div class="legend-node-item"><span class="legend-node-dot" style="background:#fb923c"></span>StrategicOpportunity</div>
            </div>
          </div>
          <div class="graph-legend-divider" aria-hidden="true"></div>
          <div class="graph-legend-col">
            <h3 class="graph-legend-title">Relationship Types</h3>
            <div class="graph-legend-edge-grid">
{legend_edges_html}
            </div>
          </div>
        </div>
      </div>

      <footer class="odpg-footer">
        <div class="odpg-footer-top">
          <div class="odpg-footer-brand">
            <span>Open Data Product Graphs Explorer</span>
          </div>
          <a class="odpg-footer-link" href="https://opendataproducts.org/odpg-v1.0" target="_blank" rel="noopener noreferrer">
            opendataproducts.org/odpg-v1.0
          </a>
        </div>
        <nav class="odpg-footer-resources" aria-label="ODPG 1.0 specification, schemas, and contribution">
          <h3>Specification &amp; schemas</h3>
          <a href="https://github.com/Open-Data-Product-Initiative/odpg-v1.0" target="_blank" rel="noopener noreferrer" title="Official source repository for the ODPG 1.0 specification">Open Data Product Graphs 1.0 on GitHub</a>
          <a href="https://opendataproducts.org/odpg-v1.0/schema/graph.yaml" target="_blank" rel="noopener noreferrer" title="Machine-readable schema definition in YAML format">ODPG YAML Schema</a>
          <a href="https://opendataproducts.org/odpg-v1.0/schema/graph.json" target="_blank" rel="noopener noreferrer" title="Machine-readable schema definition in JSON format">ODPG JSON Schema</a>
          <a href="https://github.com/Open-Data-Product-Initiative/odpg-v1.0/issues" target="_blank" rel="noopener noreferrer" title="Submit issues or suggestions to the specification maintainers">Raise an issue in GitHub</a>
        </nav>
      </footer>
  </div>

  <script>
    (function () {{
    function escHtml(s) {{
      return String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
    }}

    const TYPE_COLORS = {{
      UseCase: "#16a34a",
      BusinessObjective: "#ea580c",
      StrategicOpportunity: "#f97316",
      DataProduct: "#0284c7",
      Agent: "#0e7490",
      API: "#7c3aed",
      Policy: "#db2777",
      Signal: "#0891b2",
      KPI: "#0d9488"
    }};

    const NODE_TYPES = {json.dumps(node_types, ensure_ascii=False)};
    const RELATIONSHIP_TYPES = {json.dumps(relationship_types)};
    const CONFIDENCE_LEVELS = {json.dumps(confidence_levels, ensure_ascii=False)};
    const ODPG_SUPPORTED_EDGE_TYPES_ORDERED = {odpg_supported_ordered_json};
    const ODPG_EDGE_TYPE_DESCRIPTIONS = {odpg_descriptions_json};

    if (typeof vis === "undefined") {{
      document.getElementById("graph").innerHTML =
        "<p style=\\"padding:24px;font-family:sans-serif;line-height:1.5\\">" +
        "The graph library did not load (network or CDN blocked). " +
        "Serve this folder over HTTP or allow scripts from cdn.jsdelivr.net, then reload." +
        "</p>";
      return;
    }}

    const nodes = new vis.DataSet({json.dumps(vis_nodes, indent=2, ensure_ascii=False)});
    const edges = new vis.DataSet({json.dumps(vis_edges, indent=2, ensure_ascii=False)});

    const container = document.getElementById("graph");
    const data = {{ nodes: nodes, edges: edges }};

    const groupCard = (border) => ({{
      color: {{
        background: "#ffffff",
        border: border,
        highlight: {{ background: "#ffffff", border: border }},
        hover: {{ background: "#ffffff", border: border }}
      }}
    }});

    const options = {{
      autoResize: true,
      nodes: {{
        shape: "box",
        margin: 16,
        borderWidth: 2,
        shadow: {{
          enabled: true,
          color: "rgba(15,23,42,0.1)",
          size: 10,
          x: 0,
          y: 3
        }},
        font: {{
          size: 13,
          face: "Segoe UI,system-ui,sans-serif",
          color: "#0f172a"
        }},
        shapeProperties: {{ borderRadius: 12 }}
      }},
      edges: {{
        width: 1.25,
        smooth: {{ type: "dynamic" }},
        color: {{ inherit: false }},
        font: {{
          size: 10,
          align: "middle",
          face: "Segoe UI,system-ui,sans-serif",
          color: "#334155",
          strokeWidth: 0,
          background: "rgba(255,255,255,0.92)"
        }}
      }},
      groups: {{
        DataProduct: groupCard("#0284c7"),
        UseCase: groupCard("#16a34a"),
        BusinessObjective: groupCard("#ea580c"),
        Signal: groupCard("#0891b2"),
        KPI: groupCard("#0d9488"),
        Policy: groupCard("#db2777"),
        API: groupCard("#7c3aed"),
        Agent: groupCard("#0e7490"),
        StrategicOpportunity: groupCard("#f97316")
      }},
      physics: {{
        enabled: true,
        stabilization: {{ iterations: 280, updateInterval: 25, fit: true }},
        barnesHut: {{
          gravitationalConstant: -3400,
          centralGravity: 0.11,
          springLength: 280,
          springConstant: 0.032,
          damping: 0.58,
          avoidOverlap: 0.42
        }}
      }},
      interaction: {{
        hover: true,
        dragNodes: true,
        dragView: true,
        zoomView: true,
        multiselect: false,
        navigationButtons: false,
        keyboard: true
      }}
    }};

    const network = new vis.Network(container, data, options);
    let minimapNetwork = null;
    let physicsUserOn = false;
    let selectedFocusNodeId = null;

    const activeNodeTypes = new Set(NODE_TYPES);
    const activeEdgeTypes = new Set(RELATIONSHIP_TYPES);
    const activeConfidenceLevels = new Set(CONFIDENCE_LEVELS);

    function valueCounts(items, key) {{
      return items.reduce(function (acc, item) {{
        const value = String(item[key] || "");
        if (value) acc[value] = (acc[value] || 0) + 1;
        return acc;
      }}, {{}});
    }}

    const nodeTypeCounts = valueCounts(nodes.get(), "type");
    const edgeTypeCounts = valueCounts(edges.get(), "type");
    const confidenceCounts = valueCounts(edges.get(), "confidence");

    function rgba(hex, alpha) {{
      const clean = String(hex || "#64748b").replace("#", "");
      const bigint = parseInt(clean.length === 3
        ? clean.split("").map(function (ch) {{ return ch + ch; }}).join("")
        : clean, 16);
      const r = (bigint >> 16) & 255;
      const g = (bigint >> 8) & 255;
      const b = bigint & 255;
      return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
    }}

    function nodeVisual(node, state) {{
      const border = TYPE_COLORS[node.type] || "#64748b";
      if (state === "muted") {{
        return {{
          id: node.id,
          color: {{
            background: "rgba(248,250,252,0.48)",
            border: rgba(border, 0.24),
            highlight: {{ background: "rgba(248,250,252,0.58)", border: rgba(border, 0.42) }},
            hover: {{ background: "rgba(248,250,252,0.58)", border: rgba(border, 0.42) }}
          }},
          font: {{ color: "rgba(100,116,139,0.42)" }},
          shadow: false,
          borderWidth: 1
        }};
      }}
      if (state === "selected") {{
        return {{
          id: node.id,
          color: {{
            background: "#ffffff",
            border: "#0f172a",
            highlight: {{ background: "#ffffff", border: "#0f172a" }},
            hover: {{ background: "#ffffff", border: "#0f172a" }}
          }},
          font: {{ color: "#0f172a" }},
          shadow: {{ enabled: true, color: "rgba(15,23,42,0.18)", size: 16, x: 0, y: 4 }},
          borderWidth: 3
        }};
      }}
      return {{
        id: node.id,
        color: {{
          background: "#ffffff",
          border: border,
          highlight: {{ background: "#ffffff", border: border }},
          hover: {{ background: "#ffffff", border: border }}
        }},
        font: {{ color: "#0f172a" }},
        shadow: {{ enabled: true, color: "rgba(15,23,42,0.1)", size: 10, x: 0, y: 3 }},
        borderWidth: 2
      }};
    }}

    function edgeVisual(edge, state) {{
      const color = edgeColor(edge.type);
      if (state === "muted") {{
        return {{
          id: edge.id,
          color: {{
            color: rgba(color, 0.16),
            highlight: rgba(color, 0.24),
            hover: rgba(color, 0.24),
            inherit: false
          }},
          font: {{ color: "rgba(100,116,139,0.28)", background: "rgba(255,255,255,0.55)" }},
          width: 0.75
        }};
      }}
      if (state === "selected") {{
        return {{
          id: edge.id,
          color: {{ color: color, highlight: color, hover: color, inherit: false }},
          font: {{ color: "#0f172a", background: "rgba(255,255,255,0.96)" }},
          width: 2.25
        }};
      }}
      return {{
        id: edge.id,
        color: {{ color: color, highlight: color, hover: color, inherit: false }},
        font: {{ color: "#334155", background: "rgba(255,255,255,0.92)" }},
        width: 1.25
      }};
    }}

    function clearSelectionHighlight() {{
      selectedFocusNodeId = null;
      nodes.update(nodes.get().map(function (node) {{
        return nodeVisual(node, "normal");
      }}));
      edges.update(edges.get().map(function (edge) {{
        return edgeVisual(edge, "normal");
      }}));
    }}

    function applySelectionHighlight(nodeId) {{
      const selected = nodes.get(nodeId);
      if (!selected || selected.hidden) {{
        clearSelectionHighlight();
        return;
      }}
      selectedFocusNodeId = nodeId;
      const visibleIncidentEdges = edges.get().filter(function (edge) {{
        return !edge.hidden && (edge.from === nodeId || edge.to === nodeId);
      }});
      const focusNodeIds = new Set([nodeId]);
      visibleIncidentEdges.forEach(function (edge) {{
        focusNodeIds.add(edge.from);
        focusNodeIds.add(edge.to);
      }});
      nodes.update(nodes.get().map(function (node) {{
        if (node.hidden) return nodeVisual(node, "normal");
        if (node.id === nodeId) return nodeVisual(node, "selected");
        return nodeVisual(node, focusNodeIds.has(node.id) ? "normal" : "muted");
      }}));
      const focusEdgeIds = new Set(visibleIncidentEdges.map(function (edge) {{ return edge.id; }}));
      edges.update(edges.get().map(function (edge) {{
        if (edge.hidden) return edgeVisual(edge, "normal");
        return edgeVisual(edge, focusEdgeIds.has(edge.id) ? "selected" : "muted");
      }}));
    }}

    function renderFilterGroup(containerId, values, activeSet, counts, colorFor, onChange) {{
      const root = document.getElementById(containerId);
      root.innerHTML = "";
      values.forEach(function (value) {{
        const label = document.createElement("label");
        label.className = "filter-option";
        label.title = value;
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = activeSet.has(value);
        checkbox.addEventListener("change", function () {{
          if (checkbox.checked) {{
            activeSet.add(value);
            label.classList.remove("is-muted");
          }} else {{
            activeSet.delete(value);
            label.classList.add("is-muted");
          }}
          onChange();
        }});
        const swatch = document.createElement("span");
        swatch.className = "filter-swatch";
        swatch.style.background = colorFor(value);
        const text = document.createElement("span");
        text.className = "filter-label";
        text.textContent = value;
        const count = document.createElement("span");
        count.className = "filter-count";
        count.textContent = counts[value] || 0;
        label.appendChild(checkbox);
        label.appendChild(swatch);
        label.appendChild(text);
        label.appendChild(count);
        if (!checkbox.checked) label.classList.add("is-muted");
        root.appendChild(label);
      }});
    }}

    function passesNodeFilters(node) {{
      return activeNodeTypes.has(node.type);
    }}

    function passesEdgeFilters(edge, hiddenNodeIds) {{
      return activeEdgeTypes.has(edge.type) &&
        activeConfidenceLevels.has(String(edge.confidence || "")) &&
        !hiddenNodeIds.has(edge.from) &&
        !hiddenNodeIds.has(edge.to);
    }}

    function updateFilterStatus(visibleNodeCount, visibleEdgeCount) {{
      document.getElementById("filter-status").textContent =
        visibleNodeCount + " of " + nodes.length + " nodes · " +
        visibleEdgeCount + " of " + edges.length + " relationships visible";
    }}

    function allFiltersSelected() {{
      return activeNodeTypes.size === NODE_TYPES.length &&
        activeEdgeTypes.size === RELATIONSHIP_TYPES.length &&
        activeConfidenceLevels.size === CONFIDENCE_LEVELS.length;
    }}

    function updateFilterToggleButton() {{
      const btn = document.getElementById("btn-toggle-filters");
      if (btn) btn.textContent = allFiltersSelected() ? "Deselect all" : "Select all";
    }}

    function setAllFilters(selected) {{
      activeNodeTypes.clear();
      activeEdgeTypes.clear();
      activeConfidenceLevels.clear();
      if (selected) {{
        NODE_TYPES.forEach(function (value) {{ activeNodeTypes.add(value); }});
        RELATIONSHIP_TYPES.forEach(function (value) {{ activeEdgeTypes.add(value); }});
        CONFIDENCE_LEVELS.forEach(function (value) {{ activeConfidenceLevels.add(value); }});
      }}
      document.querySelectorAll(".filter-option").forEach(function (label) {{
        label.classList.toggle("is-muted", !selected);
        const cb = label.querySelector("input");
        if (cb) cb.checked = selected;
      }});
      updateFilterToggleButton();
    }}

    function applyFilters() {{
      const hiddenNodeIds = new Set();
      const nodeUpdates = nodes.get().map(function (node) {{
        const hidden = !passesNodeFilters(node);
        if (hidden) hiddenNodeIds.add(node.id);
        return {{ id: node.id, hidden: hidden }};
      }});
      nodes.update(nodeUpdates);

      let visibleEdgeCount = 0;
      const edgeUpdates = edges.get().map(function (edge) {{
        const hidden = !passesEdgeFilters(edge, hiddenNodeIds);
        if (!hidden) visibleEdgeCount += 1;
        return {{ id: edge.id, hidden: hidden }};
      }});
      edges.update(edgeUpdates);
      updateFilterStatus(nodes.length - hiddenNodeIds.size, visibleEdgeCount);
      if (selectedFocusNodeId) applySelectionHighlight(selectedFocusNodeId);
      updateFilterToggleButton();
      renderSearchResults();
      if (minimapNetwork) minimapNetwork.fit({{ animation: false }});
    }}

    renderFilterGroup(
      "filter-node-types",
      NODE_TYPES,
      activeNodeTypes,
      nodeTypeCounts,
      function (value) {{ return TYPE_COLORS[value] || "#64748b"; }},
      applyFilters
    );
    renderFilterGroup(
      "filter-edge-types",
      RELATIONSHIP_TYPES,
      activeEdgeTypes,
      edgeTypeCounts,
      function (value) {{ return edgeColor(value); }},
      applyFilters
    );
    renderFilterGroup(
      "filter-confidence",
      CONFIDENCE_LEVELS,
      activeConfidenceLevels,
      confidenceCounts,
      function (value) {{
        const lo = String(value).toLowerCase();
        if (lo === "high") return "#16a34a";
        if (lo === "medium") return "#f59e0b";
        if (lo === "low") return "#ef4444";
        return "#64748b";
      }},
      applyFilters
    );

    document.getElementById("btn-toggle-filters").addEventListener("click", function () {{
      setAllFilters(!allFiltersSelected());
      applyFilters();
    }});

    document.getElementById("btn-reset-filters").addEventListener("click", function () {{
      setAllFilters(true);
      applyFilters();
      network.fit({{ animation: true }});
    }});

    function edgeColor(value) {{
      const raw = String(value || "").toLowerCase();
      const colors = {{
        uses: "#16a34a",
        supports: "#ea580c",
        contributesto: "#0284c7",
        measures: "#0d9488",
        tracks: "#14b8a6",
        dependson: "#6366f1",
        produces: "#059669",
        consumes: "#a855f7",
        governedby: "#db2777",
        ownedby: "#ca8a04",
        alignswith: "#f97316",
        alignwith: "#f97316",
        relatedto: "#64748b",
        impacts: "#dc2626",
        derivedfrom: "#78716c",
        exposes: "#7c3aed",
        monitors: "#0891b2",
        identifies: "#475569"
      }};
      return colors[raw] || "#94a3b8";
    }}

    const searchInput = document.getElementById("node-search");
    const searchResults = document.getElementById("search-results");
    let activeSearchIndex = -1;
    let currentSearchMatches = [];

    function searchableNodeText(node) {{
      return [node.id, node.type, node.ref, node.displayName].join(" ").toLowerCase();
    }}

    function visibleSearchMatches() {{
      const q = searchInput.value.trim().toLowerCase();
      if (!q) return [];
      return nodes.get().filter(function (node) {{
        return !node.hidden && searchableNodeText(node).indexOf(q) !== -1;
      }}).slice(0, 20);
    }}

    function focusNode(nodeId) {{
      const node = nodes.get(nodeId);
      if (!node || node.hidden) return;
      network.selectNodes([nodeId]);
      applySelectionHighlight(nodeId);
      network.focus(nodeId, {{ scale: 1.35, animation: true }});
      showNodePanel(node);
    }}

    function renderSearchResults(nextActiveIndex) {{
      if (!searchInput) return;
      currentSearchMatches = visibleSearchMatches();
      if (currentSearchMatches.length) {{
        activeSearchIndex = typeof nextActiveIndex === "number"
          ? Math.max(0, Math.min(nextActiveIndex, currentSearchMatches.length - 1))
          : Math.max(0, activeSearchIndex);
      }} else {{
        activeSearchIndex = -1;
      }}
      searchResults.innerHTML = "";
      if (!searchInput.value.trim()) {{
        searchResults.style.display = "none";
        return;
      }}
      if (!currentSearchMatches.length) {{
        const empty = document.createElement("div");
        empty.className = "search-result";
        empty.innerHTML = '<span class="search-result-dot" style="background:#cbd5e1"></span><div><strong>No visible nodes found</strong><span>Try changing filters or using another term.</span></div>';
        searchResults.appendChild(empty);
        searchResults.style.display = "block";
        return;
      }}
      currentSearchMatches.forEach(function (node, index) {{
        const item = document.createElement("button");
        item.type = "button";
        item.className = "search-result" + (index === activeSearchIndex ? " is-active" : "");
        item.setAttribute("role", "option");
        item.innerHTML =
          '<span class="search-result-dot" style="background:' + (TYPE_COLORS[node.type] || "#64748b") + '"></span>' +
          "<div><strong>" + escHtml(node.id) + "</strong><span>" + escHtml(node.type + " · " + (node.displayName || node.ref || "")) + "</span></div>";
        item.addEventListener("click", function () {{
          focusNode(node.id);
          searchInput.value = "";
          searchResults.style.display = "none";
        }});
        searchResults.appendChild(item);
      }});
      searchResults.style.display = "block";
    }}

    searchInput.addEventListener("input", function () {{
      activeSearchIndex = -1;
      renderSearchResults();
    }});
    searchInput.addEventListener("keydown", function (event) {{
      if (!currentSearchMatches.length && event.key !== "Escape") return;
      if (event.key === "ArrowDown") {{
        event.preventDefault();
        activeSearchIndex = Math.min(activeSearchIndex + 1, currentSearchMatches.length - 1);
        renderSearchResults(activeSearchIndex);
      }} else if (event.key === "ArrowUp") {{
        event.preventDefault();
        activeSearchIndex = Math.max(activeSearchIndex - 1, 0);
        renderSearchResults(activeSearchIndex);
      }} else if (event.key === "Enter") {{
        event.preventDefault();
        if (currentSearchMatches[activeSearchIndex]) {{
          focusNode(currentSearchMatches[activeSearchIndex].id);
          searchInput.value = "";
          searchResults.style.display = "none";
        }}
      }} else if (event.key === "Escape") {{
        searchInput.value = "";
        searchResults.style.display = "none";
      }}
    }});

    document.addEventListener("click", function (event) {{
      if (!searchResults.contains(event.target) && event.target !== searchInput) {{
        searchResults.style.display = "none";
      }}
    }});

    applyFilters();

    document.addEventListener("fullscreenchange", function () {{
      window.requestAnimationFrame(function () {{
        network.redraw();
        if (minimapNetwork) minimapNetwork.redraw();
      }});
    }});

    function persistAllNodePositions() {{
      network.stopSimulation();
      const ids = nodes.getIds();
      if (!ids.length) return;
      const pos = network.getPositions(ids);
      const upd = ids.map(function (id) {{
        const pt = pos[id];
        if (!pt) return null;
        return {{ id: id, x: pt.x, y: pt.y, fixed: false }};
      }}).filter(Boolean);
      if (upd.length) nodes.update(upd);
    }}

    function persistNodePositions(ids) {{
      if (!ids || !ids.length) return;
      const pos = network.getPositions(ids);
      const upd = ids.map(function (id) {{
        const pt = pos[id];
        if (!pt) return null;
        return {{ id: id, x: pt.x, y: pt.y, fixed: false }};
      }}).filter(Boolean);
      if (upd.length) nodes.update(upd);
    }}

    function disablePhysicsAfterLayout() {{
      network.stopSimulation();
      network.setOptions({{ physics: {{ enabled: false }} }});
      physicsUserOn = false;
      document.getElementById("btn-physics").classList.add("is-locked");
      persistAllNodePositions();
      if (!minimapNetwork) {{
        minimapNetwork = new vis.Network(document.getElementById("minimap"), data, {{
          autoResize: false,
          width: "200px",
          height: "132px",
          nodes: options.nodes,
          edges: Object.assign({{}}, options.edges, {{ smooth: {{ type: "continuous" }} }}),
          groups: options.groups,
          physics: false,
          interaction: {{ zoomView: true, dragView: true, dragNodes: false, selectable: true }}
        }});
        minimapNetwork.fit({{ animation: false }});
      }} else {{
        minimapNetwork.fit({{ animation: false }});
      }}
    }}

    let layoutDone = false;
    function onLayoutStable() {{
      if (layoutDone) return;
      layoutDone = true;
      disablePhysicsAfterLayout();
    }}
    network.once("stabilizationIterationsDone", onLayoutStable);
    network.once("stabilized", function () {{
      setTimeout(function () {{
        if (!layoutDone) onLayoutStable();
      }}, 300);
    }});

    network.on("dragStart", function () {{
      if (!physicsUserOn) network.stopSimulation();
    }});

    network.on("dragEnd", function (p) {{
      if (!p.nodes || !p.nodes.length) return;
      network.stopSimulation();
      window.setTimeout(function () {{
        if (physicsUserOn) {{
          persistNodePositions(p.nodes);
        }} else {{
          persistAllNodePositions();
        }}
      }}, 0);
    }});

    document.getElementById("btn-zoom-in").addEventListener("click", function () {{
      const s = network.getScale();
      network.moveTo({{ scale: s * 1.25, animation: true }});
    }});
    document.getElementById("btn-zoom-out").addEventListener("click", function () {{
      const s = network.getScale();
      network.moveTo({{ scale: s * 0.8, animation: true }});
    }});
    document.getElementById("btn-fit").addEventListener("click", function () {{
      network.fit({{ animation: true }});
      if (minimapNetwork) minimapNetwork.fit({{ animation: false }});
    }});
    document.getElementById("btn-fit-top").addEventListener("click", function () {{
      network.fit({{ animation: true }});
    }});

    document.getElementById("btn-physics").addEventListener("click", function () {{
      const btn = document.getElementById("btn-physics");
      physicsUserOn = !physicsUserOn;
      network.setOptions({{ physics: {{ enabled: physicsUserOn }} }});
      if (physicsUserOn) {{
        nodes.update(nodes.get().map(function (n) {{
          return {{ id: n.id, fixed: false }};
        }}));
        btn.classList.remove("is-locked");
      }} else {{
        network.stopSimulation();
        network.setOptions({{ physics: {{ enabled: false }} }});
        btn.classList.add("is-locked");
        persistAllNodePositions();
      }}
    }});

    document.getElementById("btn-fullscreen").addEventListener("click", function () {{
      const el = document.documentElement;
      if (!document.fullscreenElement) {{
        if (el.requestFullscreen) el.requestFullscreen();
      }} else if (document.exitFullscreen) {{
        document.exitFullscreen();
      }}
    }});

    const tabNode = document.getElementById("tab-node");
    const tabEdge = document.getElementById("tab-edge");
    const panelNode = document.getElementById("panel-node");
    const panelEdge = document.getElementById("panel-edge");

    tabNode.addEventListener("click", function () {{
      tabNode.classList.add("is-active");
      tabEdge.classList.remove("is-active");
      tabNode.setAttribute("aria-selected", "true");
      tabEdge.setAttribute("aria-selected", "false");
      panelNode.classList.remove("is-hidden");
      panelEdge.classList.add("is-hidden");
    }});
    tabEdge.addEventListener("click", function () {{
      tabEdge.classList.add("is-active");
      tabNode.classList.remove("is-active");
      tabEdge.setAttribute("aria-selected", "true");
      tabNode.setAttribute("aria-selected", "false");
      panelEdge.classList.remove("is-hidden");
      panelNode.classList.add("is-hidden");
    }});

    function showNodePanel(node) {{
      document.getElementById("node-placeholder").style.display = "none";
      const wrap = document.getElementById("node-detail");
      wrap.style.display = "block";
      const dot = TYPE_COLORS[node.type] || "#64748b";
      const desc = escHtml(node.displayName || node.type);
      wrap.innerHTML =
        '<div class="panel-head">' +
          '<span class="type-dot" style="background:' + dot + '"></span>' +
          "<div><h2>" + escHtml(node.id) + '</h2><p class="sub">' + desc + "</p></div>" +
        "</div>" +
        '<div class="field"><label>ID</label><span>' + escHtml(node.id) + "</span></div>" +
        '<div class="field"><label>Type</label><span>' + escHtml(node.type) + "</span></div>" +
        '<div class="field"><label>Reference</label><span>' + escHtml(node.ref) + "</span></div>" +
        '<div class="field"><label>Description</label><p>' + desc + "</p></div>";
      tabNode.click();
    }}

    function showEdgePanel(edge) {{
      document.getElementById("edge-placeholder").style.display = "none";
      const wrap = document.getElementById("edge-detail");
      wrap.style.display = "block";
      const lines = String(edge.label || "").split("\\n");
      const rawTypeKey = (lines[0] || "").trim();
      const typeLine = escHtml(rawTypeKey);
      const confLine = escHtml(lines[1] || "(" + edge.confidence + ")");
      const odpgDesc = ODPG_EDGE_TYPE_DESCRIPTIONS[(rawTypeKey || "").toLowerCase()] || "";
      const descHtml = odpgDesc
        ? '<div class="field"><label>ODPG definition</label><p>' + escHtml(odpgDesc) + "</p></div>"
        : "";
      wrap.innerHTML =
        '<div class="panel-head"><div><h2>Relationship</h2><p class="sub">' + typeLine + " " + confLine + "</p></div></div>" +
        '<div class="field"><label>From</label><span>' + escHtml(edge.from) + "</span></div>" +
        '<div class="field"><label>To</label><span>' + escHtml(edge.to) + "</span></div>" +
        '<div class="field"><label>Type</label><span>' + typeLine + "</span></div>" +
        '<div class="field"><label>Confidence</label><span>' + escHtml(edge.confidence) + "</span></div>" +
        descHtml;
      tabEdge.click();
    }}

    network.on("selectNode", function (params) {{
      if (!params.nodes.length) return;
      const node = nodes.get(params.nodes[0]);
      applySelectionHighlight(node.id);
      showNodePanel(node);
    }});

    network.on("selectEdge", function (params) {{
      if (!params.edges.length) return;
      const edge = edges.get(params.edges[0]);
      showEdgePanel(edge);
    }});

    network.on("deselectNode", function () {{
      if (network.getSelectedNodes().length === 0 && network.getSelectedEdges().length === 0) {{
        clearSelectionHighlight();
        document.getElementById("node-placeholder").style.display = "";
        document.getElementById("node-detail").style.display = "none";
      }}
    }});

    network.on("deselectEdge", function () {{
      if (network.getSelectedEdges().length === 0 && network.getSelectedNodes().length === 0) {{
        clearSelectionHighlight();
        document.getElementById("edge-placeholder").style.display = "";
        document.getElementById("edge-detail").style.display = "none";
      }}
    }});
    }})();
  </script>
</body>
</html>
"""
