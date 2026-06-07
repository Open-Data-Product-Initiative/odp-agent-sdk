"""Portfolio workspace rendering and explanation helpers."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from . import __version__
from ._io import load_mapping
from .odpc import load_catalog
from .odpc.catalog import text_value
from .odpg import load_graph

DEFAULT_PORTFOLIO_HTML = "index.html"


def render_portfolio(
    workspace: Union[str, Path],
    *,
    output_path: Optional[Union[str, Path]] = None,
) -> Dict[str, object]:
    """Render a portfolio workspace as one static HTML page."""
    root = Path(workspace)
    data = load_portfolio_workspace(root)
    html_text = render_portfolio_html(data)
    output = (
        Path(output_path) if output_path is not None else root / DEFAULT_PORTFOLIO_HTML
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    existed = output.exists()
    previous = output.read_text(encoding="utf-8") if existed else None
    output.write_text(html_text, encoding="utf-8")
    changed_key = (
        "unchanged" if previous == html_text else "updated" if existed else "created"
    )
    result: Dict[str, object] = {
        "spec": "portfolio",
        "kind": "PortfolioRender",
        "workspace": str(root),
        "html": str(output),
        "created": [],
        "updated": [],
        "unchanged": [],
        "warnings": data["warnings"],
        "valid": True,
    }
    result[changed_key] = [str(output)]
    return result


def explain_portfolio(workspace: Union[str, Path]) -> Dict[str, object]:
    """Return a JSON-ready summary of a portfolio workspace."""
    root = Path(workspace)
    data = load_portfolio_workspace(root)
    catalog = data["catalog"].get("catalog", {})
    graph = data["graph"].get("graph", {})
    return {
        "spec": "portfolio",
        "kind": "PortfolioExplain",
        "workspace": str(root),
        "html": str(root / DEFAULT_PORTFOLIO_HTML),
        "businessObjectiveCount": _count(catalog, "businessObjectives"),
        "useCaseCount": _count(catalog, "useCases"),
        "signalCount": _count(catalog, "signals"),
        "productReferenceCount": _count(catalog, "productReferences"),
        "productSpecCount": len(data["products"]),
        "graphNodeCount": _count(graph, "nodes"),
        "graphEdgeCount": _count(graph, "edges"),
        "versionCount": len(data["versions"]),
        "warnings": data["warnings"],
        "valid": True,
    }


def load_portfolio_workspace(workspace: Union[str, Path]) -> Dict[str, Any]:
    """Load portfolio map, catalog, product specs, graph, and version metadata."""
    root = Path(workspace)
    catalog_path = root / "odpc" / "catalog.yaml"
    graph_path = root / "odpg" / "graph.yaml"
    portfolio_path = root / "portfolio.yaml"
    warnings: List[str] = []
    portfolio = _load_optional_mapping(portfolio_path)
    catalog = load_catalog(catalog_path) if catalog_path.exists() else _empty_catalog()
    graph = load_graph(graph_path) if graph_path.exists() else _empty_graph()
    products = _load_product_specs(root)
    versions = _portfolio_versions(root, portfolio)
    return {
        "workspace": root,
        "portfolio": portfolio,
        "catalog": catalog,
        "catalog_path": catalog_path,
        "graph": graph,
        "graph_path": graph_path,
        "products": products,
        "versions": versions,
        "warnings": warnings,
    }


def render_portfolio_html(data: Dict[str, Any]) -> str:
    """Render portfolio workspace data to static HTML."""
    portfolio = data["portfolio"]
    catalog_root = data["catalog"].get("catalog", {})
    metadata = (
        catalog_root.get("metadata", {}) if isinstance(catalog_root, dict) else {}
    )
    title = _text(
        metadata.get("name"),
        _text(portfolio.get("metadata", {}).get("name"), "Portfolio"),
    )
    business_objectives = _list(catalog_root, "businessObjectives")
    use_cases = _list(catalog_root, "useCases")
    signals = _list(catalog_root, "signals")
    product_references = _list(catalog_root, "productReferences")
    graph = data["graph"].get("graph", {})

    html_parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_escape(title)}</title>",
        "<style>",
        _portfolio_css(),
        "</style>",
        "</head>",
        "<body>",
        "<main>",
        '<header class="odp-header">',
        f"<h1>{_escape(title)}</h1>",
        f'<p class="odp-muted">{_escape(_text(metadata.get("description"), "Generated Open Data Products portfolio."))}</p>',
        "</header>",
        _render_nav(),
        _render_overview(catalog_root, graph, data["products"], data["versions"]),
        _render_artifact_section(
            "objectives", "Business Objectives", business_objectives
        ),
        _render_artifact_section("use-cases", "Use Cases", use_cases),
        _render_artifact_section("signals", "Signals", signals),
        _render_products(product_references, data["products"]),
        _render_graph(graph),
        _render_about(data),
        "</main>",
        "</body>",
        "</html>",
    ]
    return "\n".join(html_parts) + "\n"


def _load_optional_mapping(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return load_mapping(path, root_name="Portfolio")


def _empty_catalog() -> Dict[str, Any]:
    return {"catalog": {"metadata": {"name": {"en": "Portfolio"}}}}


def _empty_graph() -> Dict[str, Any]:
    return {"graph": {"metadata": {}, "nodes": [], "edges": []}}


def _load_product_specs(root: Path) -> Dict[str, Dict[str, Any]]:
    products: Dict[str, Dict[str, Any]] = {}
    product_dir = root / "odps" / "products"
    for path in sorted(
        [
            *product_dir.glob("*.yaml"),
            *product_dir.glob("*.yml"),
            *product_dir.glob("*.json"),
        ]
    ):
        try:
            document = load_mapping(path, root_name="ODPS product")
        except ValueError:
            continue
        details = _product_details(document)
        product_id = _text(details.get("productID") or details.get("id"), path.stem)
        products[product_id] = {"path": path, "document": document}
    return products


def _portfolio_versions(root: Path, portfolio: Dict[str, Any]) -> List[Dict[str, str]]:
    versions = []
    metadata_versions = portfolio.get("versions")
    if isinstance(metadata_versions, list):
        for item in metadata_versions:
            if not isinstance(item, dict):
                continue
            version_id = str(item.get("id") or item.get("version") or "")
            html_path = str(item.get("html") or f"versions/{version_id}/index.html")
            if version_id:
                versions.append(
                    {
                        "id": version_id,
                        "type": str(
                            item.get("type") or item.get("runType") or "snapshot"
                        ),
                        "summary": str(item.get("summary") or ""),
                        "html": html_path,
                    }
                )
    if versions:
        return versions
    versions_root = root / "versions"
    if versions_root.exists():
        for path in sorted(versions_root.glob("*/index.html")):
            version_id = path.parent.name
            versions.append(
                {
                    "id": version_id,
                    "type": "snapshot",
                    "summary": "",
                    "html": path.relative_to(root).as_posix(),
                }
            )
    return versions


def _render_nav() -> str:
    links = [
        ("overview", "Overview"),
        ("objectives", "Business Objectives"),
        ("use-cases", "Use Cases"),
        ("products", "Products"),
        ("signals", "Signals"),
        ("graph", "Graph"),
        ("about", "About"),
    ]
    items = "".join(f'<a href="#{anchor}">{label}</a>' for anchor, label in links)
    return f'<nav class="odp-tabs">{items}</nav>'


def _render_overview(
    catalog: Dict[str, Any],
    graph: Dict[str, Any],
    products: Dict[str, Dict[str, Any]],
    versions: List[Dict[str, str]],
) -> str:
    counts = [
        ("Business Objectives", _count(catalog, "businessObjectives")),
        ("Use Cases", _count(catalog, "useCases")),
        ("Signals", _count(catalog, "signals")),
        ("Products", _count(catalog, "productReferences")),
        ("ODPS Specs", len(products)),
        ("Graph Nodes", _count(graph, "nodes")),
        ("Graph Edges", _count(graph, "edges")),
    ]
    cards = "".join(
        f"<li><strong>{count}</strong><span>{_escape(label)}</span></li>"
        for label, count in counts
    )
    version_html = _render_versions(versions)
    return (
        '<section id="overview" class="odp-section">'
        "<h2>Overview</h2>"
        f'<ul class="odp-summary">{cards}</ul>'
        f"{version_html}"
        "</section>"
    )


def _render_versions(versions: List[Dict[str, str]]) -> str:
    if not versions:
        return ""
    items = "".join(
        "<li>"
        f'<a href="{_escape_attr(version["html"])}">{_escape(version["id"])}</a>'
        f'<span>{_escape(version["type"])}</span>'
        f'<span>{_escape(version["summary"])}</span>'
        "</li>"
        for version in versions
    )
    return f'<section class="odp-version-switcher"><h3>Versions</h3><ul>{items}</ul></section>'


def _render_artifact_section(
    anchor: str, title: str, items: List[Dict[str, Any]]
) -> str:
    cards = (
        "".join(_render_artifact_card(item) for item in items) or "<p>No entries.</p>"
    )
    return (
        f'<section id="{anchor}" class="odp-section"><h2>{title}</h2>{cards}</section>'
    )


def _render_artifact_card(item: Dict[str, Any]) -> str:
    name = _text(item.get("name"), _text(item.get("id"), "(unnamed)"))
    details = [
        ("ID", item.get("id")),
        ("Status", item.get("status")),
        ("Priority", item.get("priority")),
        ("Confidence", item.get("confidence")),
        ("Type", item.get("type")),
    ]
    return (
        '<article class="odp-card">'
        f"<h3>{_escape(name)}</h3>"
        f'<p>{_escape(_text(item.get("description")))}</p>'
        f"{_render_facts(details)}"
        "</article>"
    )


def _render_products(
    references: List[Dict[str, Any]],
    products: Dict[str, Dict[str, Any]],
) -> str:
    cards = []
    for reference in references:
        product_info = _resolve_product(reference, products)
        cards.append(_render_product_card(reference, product_info))
    content = "".join(cards) or "<p>No entries.</p>"
    return f'<section id="products" class="odp-section"><h2>Products</h2>{content}</section>'


def _render_product_card(
    reference: Dict[str, Any],
    product_info: Optional[Dict[str, Any]],
) -> str:
    product_id = _text(reference.get("productID") or reference.get("id"))
    name = _text(reference.get("name"), product_id or "(unnamed)")
    details = [
        ("Product ID", product_id),
        ("Version", reference.get("productVersion")),
        ("Status", reference.get("status")),
        ("Visibility", reference.get("visibility")),
        ("Type", reference.get("type")),
    ]
    product_model = reference.get("productModel")
    raw_ref = ""
    if isinstance(product_model, dict):
        raw_ref = _text(product_model.get("$ref") or product_model.get("ref"))
    product_detail_html = ""
    if product_info is not None:
        product_detail_html = _render_product_detail(product_info)
    return (
        '<article class="odp-card">'
        f"<h3>{_escape(name)}</h3>"
        f'<p>{_escape(_text(reference.get("description")))}</p>'
        f"{_render_facts(details)}"
        f'<p class="odp-muted">Raw ODPS YAML: {_escape(raw_ref)}</p>'
        f"{product_detail_html}"
        "</article>"
    )


def _resolve_product(
    reference: Dict[str, Any],
    products: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    product_id = _text(reference.get("productID") or reference.get("id"))
    if product_id in products:
        return products[product_id]
    product_model = reference.get("productModel")
    if isinstance(product_model, dict):
        ref = _text(product_model.get("$ref") or product_model.get("ref"))
        for product in products.values():
            path = product["path"]
            if isinstance(path, Path) and path.name == Path(ref).name:
                return product
    return None


def _render_product_detail(product_info: Dict[str, Any]) -> str:
    document = product_info["document"]
    path = product_info["path"]
    details = _product_details(document)
    product = document.get("product", {}) if isinstance(document, dict) else {}
    facts = [
        ("Name", details.get("name")),
        ("Product ID", details.get("productID")),
        ("Status", details.get("status")),
        ("Visibility", details.get("visibility")),
        ("Type", details.get("type")),
    ]
    sections = [
        _render_named_collection("Pricing", _pricing_items(product)),
        _render_named_collection("SLA", _declarative_items(product.get("SLA"))),
        _render_named_collection(
            "Data Quality", _declarative_items(product.get("dataQuality"))
        ),
    ]
    return (
        '<details class="odp-detail" open>'
        "<summary>Open details</summary>"
        f'<p>{_escape(_text(details.get("description")))}</p>'
        f"{_render_facts(facts)}"
        f"{''.join(sections)}"
        f'<p class="odp-muted">Raw artifact: {_escape(str(path))}</p>'
        "</details>"
    )


def _render_graph(graph: Dict[str, Any]) -> str:
    nodes = _list(graph, "nodes")
    edges = _list(graph, "edges")
    node_items = "".join(
        f'<li><strong>{_escape(_text(node.get("id")))}</strong> {_escape(_text(node.get("type")))}</li>'
        for node in nodes
    )
    edge_items = "".join(
        "<li>"
        f'{_escape(_text(edge.get("source")))} '
        f'{_escape(_text(edge.get("type")))} '
        f'{_escape(_text(edge.get("target")))}'
        "</li>"
        for edge in edges
    )
    return (
        '<section id="graph" class="odp-section">'
        "<h2>Graph</h2>"
        f"<p>{len(nodes)} nodes, {len(edges)} edges.</p>"
        f'<div class="odp-grid"><div><h3>Nodes</h3><ul>{node_items}</ul></div>'
        f"<div><h3>Edges</h3><ul>{edge_items}</ul></div></div>"
        "</section>"
    )


def _render_about(data: Dict[str, Any]) -> str:
    portfolio = data["portfolio"]
    metadata = portfolio.get("metadata", {}) if isinstance(portfolio, dict) else {}
    sources = portfolio.get("sources", {}) if isinstance(portfolio, dict) else {}
    source_items = []
    if isinstance(sources, dict):
        for key, value in sorted(sources.items()):
            count = value.get("count") if isinstance(value, dict) else value
            source_items.append(f"<li>{_escape(str(key))}: {_escape(str(count))}</li>")
    return (
        '<section id="about" class="odp-section">'
        "<h2>About</h2>"
        "<p>This portfolio was generated with the Open Data Products SDK and "
        "is grounded in the OpenDataProducts.org standards family: ODPC for "
        "catalog objects, ODPS for product specifications, ODPG for graph "
        "relationships, and ODPV for shared vocabulary where used.</p>"
        f"<p>SDK version: {_escape(_text(metadata.get('sdkVersion'), __version__))}</p>"
        f"<p>Generation timestamp: {_escape(_text(metadata.get('generatedAt'), '(not set)'))}</p>"
        f'<ul>{"".join(source_items)}</ul>'
        "</section>"
    )


def _product_details(document: Dict[str, Any]) -> Dict[str, Any]:
    product = document.get("product")
    if not isinstance(product, dict):
        return {}
    details = product.get("details")
    if isinstance(details, dict):
        english = details.get("en")
        if isinstance(english, dict):
            return english
    return product


def _pricing_items(product: Any) -> List[Dict[str, Any]]:
    if not isinstance(product, dict):
        return []
    pricing = product.get("pricingPlans")
    if not isinstance(pricing, dict):
        return []
    declarative = pricing.get("declarative")
    if isinstance(declarative, dict):
        english = declarative.get("en")
        if isinstance(english, list):
            return [item for item in english if isinstance(item, dict)]
    return []


def _declarative_items(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    declarative = value.get("declarative")
    if isinstance(declarative, list):
        return [item for item in declarative if isinstance(item, dict)]
    return []


def _render_named_collection(title: str, items: List[Dict[str, Any]]) -> str:
    if not items:
        return ""
    rendered = []
    for item in items:
        facts = [(str(key), value) for key, value in item.items()]
        rendered.append(f"<li>{_render_facts(facts)}</li>")
    return f"<h4>{_escape(title)}</h4><ul>{''.join(rendered)}</ul>"


def _render_facts(facts: Iterable[Tuple[str, Any]]) -> str:
    pairs = []
    for label, value in facts:
        text = _text(value)
        if text:
            pairs.append(f"<dt>{_escape(label)}</dt><dd>{_escape(text)}</dd>")
    if not pairs:
        return ""
    return f'<dl class="odp-facts">{"".join(pairs)}</dl>'


def _list(mapping: Any, key: str) -> List[Dict[str, Any]]:
    if not isinstance(mapping, dict):
        return []
    value = mapping.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _count(mapping: Any, key: str) -> int:
    return len(_list(mapping, key))


def _text(value: Any, fallback: str = "") -> str:
    return text_value(value, fallback)


def _escape(value: str) -> str:
    return html.escape(value)


def _escape_attr(value: str) -> str:
    return html.escape(value, quote=True)


def _portfolio_css() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f7f8f5;
  --panel: #ffffff;
  --text: #18201a;
  --muted: #5e6b60;
  --line: #d9dfd6;
  --accent: #006d1d;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
main {
  width: min(1180px, calc(100% - 32px));
  margin: 0 auto;
  padding: 32px 0 56px;
}
a { color: var(--accent); }
.odp-header {
  padding: 24px 0;
  border-bottom: 1px solid var(--line);
}
.odp-header h1 {
  margin: 0 0 8px;
  font-size: clamp(2rem, 5vw, 4rem);
  line-height: 1;
  letter-spacing: 0;
}
.odp-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px 0;
  border-bottom: 1px solid var(--line);
}
.odp-tabs a {
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  text-decoration: none;
}
.odp-section { padding: 24px 0; }
.odp-section h2 { margin: 0 0 12px; font-size: 1.35rem; }
.odp-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  padding: 0;
  list-style: none;
}
.odp-summary li,
.odp-card {
  margin: 12px 0;
  padding: 16px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.odp-summary strong {
  display: block;
  font-size: 2rem;
  line-height: 1;
}
.odp-card h3 { margin: 0; font-size: 1.1rem; }
.odp-facts {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 12px;
  margin: 12px 0 0;
}
.odp-facts dt {
  color: var(--muted);
  font-weight: 700;
}
.odp-facts dd { margin: 0; }
.odp-muted { color: var(--muted); }
.odp-detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.odp-version-switcher ul,
.odp-grid ul {
  padding-left: 20px;
}
.odp-version-switcher li {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 6px 0;
}
.odp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}
"""
