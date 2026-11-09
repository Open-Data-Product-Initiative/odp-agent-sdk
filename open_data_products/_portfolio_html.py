"""HTML composition for Portfolio workspaces."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from . import __version__
from ._io import load_mapping
from ._portfolio_assets import portfolio_css, portfolio_js
from ._portfolio_normalization import normalize_odps_product as _normalize_odps_product
from ._portfolio_values import (
    as_list as _list,
    change_list_count as _change_list_count,
    count as _count,
    escape as _escape,
    escape_attr as _escape_attr,
    path_id as _path_id,
    text as _text,
    title_from_text as _title_from_text,
)
from ._portfolio_workspace import (
    product_details as _product_details,
    product_spec_paths as _product_spec_paths,
    write_yaml as _write_yaml,
)
from .odpg import build_graph_explorer_html

PORTFOLIO_ICON_ASSET_DIR = Path("assets") / "executive_summary_icons"
EXECUTIVE_SUMMARY_CARD_ICONS = {
    "primary-focus": "priority_1_trophy.png",
    "secondary-focus": "priority_2_growth.png",
    "risk-focus": "risk_warning.png",
    "readiness-focus": "readiness_clipboard.png",
}
RTL_LANGUAGE_SUBTAGS = {
    "ar",
    "ckb",
    "dv",
    "fa",
    "he",
    "ps",
    "sd",
    "ur",
    "yi",
}


def _string_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _html_direction(language: str) -> str:
    primary = language.split("-", 1)[0].lower()
    return "rtl" if primary in RTL_LANGUAGE_SUBTAGS else "ltr"


def _localized_html_filename(language: str, default_language: str) -> str:
    return "index.html" if language == default_language else f"index.{language}.html"


def render_portfolio_html(data: Dict[str, Any]) -> str:
    """Render portfolio workspace data to static HTML."""
    portfolio = data["portfolio"]
    language = _text(data.get("language"), "en")
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
    description = _text(
        metadata.get("description"), "Generated Open Data Products portfolio."
    )
    direction = _html_direction(language)

    html_parts = [
        "<!doctype html>",
        f'<html lang="{_escape_attr(language)}" dir="{direction}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_escape(title)}</title>",
        "<style>",
        portfolio_css(),
        "</style>",
        "</head>",
        "<body>",
        '<header class="topbar">',
        '<div class="topbar-inner">',
        '<a class="brand" href="#overview" aria-label="Data products portfolio">Data Products Portfolio</a>',
        _render_language_selector(data, language),
        "</div>",
        "</header>",
        '<section class="hero">',
        '<div class="wrap">',
        '<p class="eyebrow">AI Agent First Portfolio Workspace</p>',
        f"<h1>{_escape(title)}</h1>",
        f'<p class="lead">{_escape(description)}</p>',
        "</div>",
        "</section>",
        '<main class="wrap">',
        _render_tab_inputs(),
        _render_tab_nav(),
        '<div class="panels">',
        _render_overview(
            catalog_root,
            graph,
            data["products"],
            data["versions"],
            data["warnings"],
        ),
        _render_executive_summary(
            data.get("executive_summary"),
            _catalog_label_map(catalog_root),
        ),
        _render_artifact_panel(
            "objectives",
            "Objectives",
            "Business Objectives",
            "Business-Led Starting Point",
            "Objectives make the portfolio business-led before products become the center of gravity.",
            business_objectives,
            show_id=False,
        ),
        _render_artifact_panel(
            "use-cases",
            "Use Cases",
            "Use Cases",
            "Operational Demand",
            "Use cases are the practical starting points for deciding which data products should exist.",
            use_cases,
        ),
        _render_products(product_references, data["products"]),
        _render_artifact_panel(
            "signals",
            "Signals",
            "Signals",
            "Market And Portfolio Signals",
            "Signals explain why a product or use case matters now, and how confident the evidence is.",
            signals,
            card_class=" signal",
        ),
        _render_graph(data["graph"], _catalog_label_map(catalog_root)),
        _render_about(data),
        "</div>",
        "</main>",
        _render_footer(data),
        portfolio_js(),
        "</body>",
        "</html>",
    ]
    return "\n".join(html_parts) + "\n"


def _render_tab_inputs() -> str:
    tabs = (
        "overview",
        "executive-summary",
        "objectives",
        "use-cases",
        "products",
        "signals",
        "graph",
        "about",
    )
    inputs = []
    for index, tab in enumerate(tabs):
        checked = " checked" if index == 0 else ""
        inputs.append(
            f'<input class="tab-radio" type="radio" name="portfolio-tab" id="tab-{tab}"{checked}>'
        )
    return "".join(inputs)


def _render_language_selector(data: Dict[str, Any], current_language: str) -> str:
    i18n = data.get("i18n")
    if not isinstance(i18n, dict):
        return ""
    default_language = _text(i18n.get("defaultLanguage"), "en")
    languages = _string_list(i18n.get("languages"))
    if len(languages) < 2:
        return ""
    links = []
    for language in languages:
        href = _localized_html_filename(language, default_language)
        current = ' aria-current="true"' if language == current_language else ""
        links.append(f'<a href="{_escape_attr(href)}"{current}>{_escape(language)}</a>')
    return (
        '<nav class="language-selector" aria-label="Portfolio language selector">'
        f"<span>{_escape(current_language)}</span>"
        f'<div>{"".join(links)}</div>'
        "</nav>"
    )


def _render_tab_nav() -> str:
    tabs = [
        ("overview", "Overview"),
        ("executive-summary", "Executive Summary"),
        ("objectives", "Objectives"),
        ("use-cases", "Use Cases"),
        ("products", "Products"),
        ("signals", "Signals"),
        ("graph", "Graph"),
        ("about", "About"),
    ]
    labels = "".join(
        f'<label for="tab-{tab}">{_escape(label)}</label>' for tab, label in tabs
    )
    return f'<nav class="tabs" aria-label="Portfolio tabs">{labels}</nav>'


def _render_overview(
    catalog: Dict[str, Any],
    graph: Dict[str, Any],
    products: Dict[str, Dict[str, Any]],
    versions: List[Dict[str, Any]],
    warnings: List[str],
) -> str:
    counts = [
        ("Objective", _count(catalog, "businessObjectives")),
        ("Use Cases", _count(catalog, "useCases")),
        ("Signal", _count(catalog, "signals")),
        ("Product", _count(catalog, "productReferences")),
        ("Graph Nodes", _count(graph, "nodes")),
        ("Graph Edges", _count(graph, "edges")),
    ]
    metrics = "".join(
        f'<article class="metric"><strong>{count}</strong><span>{_escape(label)}</span></article>'
        for label, count in counts
    )
    return (
        '<section class="tab-panel overview-panel" id="overview">'
        '<div class="section-head"><div>'
        '<p class="eyebrow">Portfolio Overview</p>'
        "<h2>Generated workspace summary</h2>"
        "</div></div>"
        f'<section class="summary" aria-label="Portfolio summary">{metrics}</section>'
        f"{_render_recommended_actions(catalog, graph, products, warnings)}"
        f"{_render_portfolio_changes(versions)}"
        f"{_render_versions(versions)}"
        "</section>"
    )


def _render_executive_summary(
    summary: Any,
    labels: Dict[str, str],
) -> str:
    if not isinstance(summary, dict) or not summary:
        return (
            '<section class="tab-panel executive-summary-panel" id="executive-summary">'
            '<div class="section-head"><div>'
            '<p class="eyebrow">Leadership Decision Support</p>'
            "<h2>Executive Summary</h2>"
            "</div></div>"
            '<article class="action-card executive-empty">'
            "<p>Executive summary has not been generated for this workspace yet. "
            "Run a LLM-backed portfolio build or refresh to create "
            "executive-summary.yaml.</p>"
            "</article>"
            "</section>"
        )
    position = summary.get("portfolioPosition")
    position = position if isinstance(position, dict) else {}
    headline = _text(position.get("headline"), "Current portfolio position")
    narrative = _text(position.get("narrative"))
    priority_briefing = _render_priority_briefing(summary, labels)
    decisions = _render_executive_list(
        "Leadership decisions",
        _list(summary, "leadershipDecisions"),
        labels,
        primary_key="question",
    )
    evidence_gaps = _render_executive_list(
        "Evidence gaps",
        _list(summary, "evidenceGaps"),
        labels,
        primary_key="statement",
    )
    notes = "".join(
        f"<li>{_escape(_text(note))}</li>"
        for note in _string_list(summary.get("confidenceNotes"))
    )
    notes_html = (
        '<section class="executive-list"><h3>Confidence notes</h3>'
        f"<ul>{notes}</ul></section>"
        if notes
        else ""
    )
    return (
        '<section class="tab-panel executive-summary-panel" id="executive-summary">'
        '<div class="section-head"><div>'
        '<p class="eyebrow">Leadership Decision Support</p>'
        "<h2>Executive Summary</h2>"
        "</div><p>Business-facing analysis grounded in portfolio evidence.</p></div>"
        '<article class="executive-dashboard-intro">'
        f"<h3>{_escape(headline)}</h3>"
        f"<p>{_escape(narrative)}</p>"
        "</article>"
        f"{priority_briefing}"
        f"{decisions}{evidence_gaps}{notes_html}"
        "</section>"
    )


def _render_priority_briefing(summary: Dict[str, Any], labels: Dict[str, str]) -> str:
    briefing = _priority_briefing(summary)
    recommendation = _text(briefing.get("recommendation"))
    recommendation_html = (
        '<article class="leadership-recommendation">'
        '<span class="recommendation-label">Recommended decision</span>'
        f"<p>{_escape(recommendation)}</p>"
        "</article>"
        if recommendation
        else ""
    )
    primary = _render_priority_card(
        briefing.get("primaryFocus"),
        labels,
        class_name="primary-focus",
        default_label="Priority 1",
        default_rationale_title="Why this is first",
    )
    secondary = _render_priority_card(
        briefing.get("secondaryFocus"),
        labels,
        class_name="secondary-focus",
        default_label="Priority 2",
        default_rationale_title="Why this is second",
    )
    blocker = _render_priority_card(
        briefing.get("blocker"),
        labels,
        class_name="risk-focus",
        default_label="Risk",
        default_rationale_title="Why this matters",
    )
    readiness = _render_priority_card(
        briefing.get("readinessCheck"),
        labels,
        class_name="readiness-focus",
        default_label="Readiness check",
        default_rationale_title="Checklist",
    )
    return (
        f"{recommendation_html}"
        f'<div class="decision-card-grid">{primary}{secondary}{blocker}{readiness}</div>'
    )


def _priority_briefing(summary: Dict[str, Any]) -> Dict[str, Any]:
    briefing = summary.get("priorityBriefing")
    if isinstance(briefing, dict) and briefing:
        return briefing
    return _priority_briefing_from_swot(summary)


def _priority_briefing_from_swot(summary: Dict[str, Any]) -> Dict[str, Any]:
    swot = summary.get("swot") if isinstance(summary.get("swot"), dict) else {}
    leadership = (
        summary.get("leadershipSummary")
        if isinstance(summary.get("leadershipSummary"), dict)
        else {}
    )
    strengths = _list(swot, "strengths")
    opportunities = _list(swot, "opportunities")
    threats = _list(swot, "threats")
    weaknesses = _list(swot, "weaknesses")
    return {
        "recommendation": _fallback_recommendation(leadership),
        "primaryFocus": _priority_item_from_swot(
            strengths[:1],
            label="Priority 1",
            title="Focus first: strongest validated workflow",
            rationale_title="Why this is first",
        ),
        "secondaryFocus": _priority_item_from_swot(
            opportunities[:1],
            label="Priority 2",
            title="Validate next: second growth path",
            rationale_title="Why this is second",
        ),
        "blocker": _priority_item_from_swot(
            threats[:1],
            label="Risk",
            title="Do not ignore: main prioritization risk",
            rationale_title="Why this matters",
        ),
        "readinessCheck": _priority_item_from_swot(
            weaknesses[:1],
            label="Readiness check",
            title="Before build starts: commercial readiness review",
            rationale_title="Checklist",
        ),
    }


def _fallback_recommendation(leadership: Dict[str, Any]) -> str:
    first = _text(leadership.get("recommendedFirstMove"))
    second = _text(leadership.get("secondGrowthPath"))
    risk = _text(leadership.get("mainRisk"))
    parts = []
    if first:
        parts.append(first)
    if second:
        parts.append(second)
    if risk:
        parts.append(risk)
    return ". ".join(parts)


def _priority_item_from_swot(
    items: List[Dict[str, Any]],
    *,
    label: str,
    title: str,
    rationale_title: str,
) -> Dict[str, Any]:
    item = items[0] if items else {}
    return {
        "label": label,
        "title": title,
        "message": _text(item.get("statement")),
        "action": _text(item.get("decisionImplication")),
        "rationaleTitle": rationale_title,
        "rationale": [],
        "confidence": item.get("confidence"),
        "evidenceType": "inferred" if item.get("inference") is True else "direct",
        "evidenceRefs": _list(item, "evidenceRefs"),
    }


def _render_priority_card(
    value: Any,
    labels: Dict[str, str],
    *,
    class_name: str,
    default_label: str,
    default_rationale_title: str,
) -> str:
    if not isinstance(value, dict):
        return ""
    title = _dashboard_card_title(value, class_name)
    message = _dashboard_card_message(value, class_name)
    action = _dashboard_card_action(value, class_name)
    if not title and not message and not action:
        return ""
    label = _dashboard_card_label(value, class_name, default_label)
    return (
        f'<article class="decision-card {class_name}">'
        f'<input class="decision-details-toggle" id="decision-details-{_escape(class_name)}" type="checkbox">'
        '<div class="decision-card-head">'
        f"{_render_decision_card_icon(class_name)}"
        "<div>"
        f'<span class="priority-label">{_escape(label)}</span>'
        f"<h3>{_escape(title)}</h3>"
        "</div>"
        "</div>"
        f'<p class="decision-insight">{_escape(message)}</p>'
        f"{_render_priority_action(action)}"
        '<div class="decision-card-footer">'
        f"{_render_priority_meta(value)}"
        f"{_render_priority_details_trigger(class_name)}"
        "</div>"
        f"{_render_priority_details_dropdown(value, labels, default_rationale_title)}"
        "</article>"
    )


def _render_decision_card_icon(class_name: str) -> str:
    filename = EXECUTIVE_SUMMARY_CARD_ICONS.get(class_name, "")
    if not filename:
        return '<span class="decision-card-icon" aria-hidden="true"></span>'
    src = Path(PORTFOLIO_ICON_ASSET_DIR) / filename
    return (
        '<span class="decision-card-icon" aria-hidden="true">'
        f'<img src="{_escape(src.as_posix())}" alt="" loading="lazy">'
        "</span>"
    )


def _dashboard_card_title(item: Dict[str, Any], class_name: str) -> str:
    title = _text(item.get("dashboardTitle") or item.get("shortTitle"))
    if title:
        return title
    defaults = {
        "primary-focus": "Retention validation",
        "secondary-focus": "Partner expansion",
        "risk-focus": "Signal coverage",
        "readiness-focus": "Commercial review",
    }
    return defaults.get(class_name, _text(item.get("title")))


def _dashboard_card_message(item: Dict[str, Any], class_name: str) -> str:
    message = _text(item.get("dashboardMessage") or item.get("shortMessage"))
    if message:
        return message
    defaults = {
        "primary-focus": "Retention is the strongest first funding candidate.",
        "secondary-focus": "Partner expansion is promising but not yet first priority.",
        "risk-focus": "Thin signal coverage may overstate prioritization confidence.",
        "readiness-focus": "The product still needs business readiness review.",
    }
    return defaults.get(class_name, _text(item.get("message")))


def _dashboard_card_action(item: Dict[str, Any], class_name: str) -> str:
    action = _text(item.get("dashboardAction") or item.get("shortAction"))
    if action:
        return action
    defaults = {
        "primary-focus": "Fund validation first.",
        "secondary-focus": "Validate the business case next.",
        "risk-focus": "Improve coverage before final prioritization.",
        "readiness-focus": "Confirm readiness before build.",
    }
    return defaults.get(class_name, _text(item.get("action")))


def _dashboard_card_label(
    item: Dict[str, Any],
    class_name: str,
    default_label: str,
) -> str:
    label = _text(item.get("label"), default_label)
    if class_name == "readiness-focus":
        return "Readiness"
    return label


def _render_priority_action(action: str) -> str:
    if not action:
        return ""
    return (
        '<div class="priority-action">'
        "<span>Action:</span>"
        f"<p>{_escape(action)}</p>"
        "</div>"
    )


def _render_priority_meta(item: Dict[str, Any]) -> str:
    confidence = _confidence_label(item.get("confidence"))
    evidence_type = _priority_evidence_type(item)
    confidence_key = confidence.lower()
    evidence_key = evidence_type.lower()
    return (
        '<div class="priority-meta">'
        f'<span class="metadata-badge confidence-badge confidence-{_escape(confidence_key)}">'
        '<span class="status-dot" aria-hidden="true"></span>'
        f"{_escape(confidence)}"
        "</span>"
        f'<span class="metadata-badge evidence-badge evidence-{_escape(evidence_key)}">'
        '<span class="evidence-icon" aria-hidden="true"></span>'
        f"{_escape(evidence_type)}"
        "</span>"
        "</div>"
    )


def _priority_evidence_type(item: Dict[str, Any]) -> str:
    evidence_type = _text(item.get("evidenceType")).lower()
    if evidence_type == "direct":
        return "Direct"
    if evidence_type == "inferred":
        return "Inferred"
    return _evidence_type(item)


def _render_priority_evidence(
    item: Dict[str, Any],
    labels: Dict[str, str],
) -> str:
    evidence = _priority_evidence_items(item, labels)
    refs = _priority_technical_refs(item)
    if not evidence:
        return ""
    rendered = "".join(
        f"<li>{_escape(ref_type)}: {_escape(label)}</li>"
        for ref_type, label in evidence
    )
    return (
        '<div class="business-evidence priority-evidence"><h4>Evidence</h4>'
        f"<ul>{rendered}</ul></div>"
        f"{_render_technical_evidence(refs)}"
    )


def _render_priority_details_trigger(class_name: str) -> str:
    return (
        f'<label class="decision-details-trigger" for="decision-details-{_escape(class_name)}">'
        '<span class="decision-details-label-closed">Show more</span>'
        '<span class="decision-details-label-open">Show less</span>'
        "</label>"
    )


def _render_priority_details_dropdown(
    item: Dict[str, Any],
    labels: Dict[str, str],
    default_rationale_title: str,
) -> str:
    rationale_title = _text(item.get("rationaleTitle"), default_rationale_title)
    rationale = _string_list(item.get("checklist")) or _string_list(
        item.get("rationale")
    )
    sections = []
    if rationale:
        rendered = "".join(f"<li>{_escape(text)}</li>" for text in rationale)
        sections.append(f"<h4>{_escape(rationale_title)}</h4><ul>{rendered}</ul>")
    evidence = _priority_evidence_items(item, labels)
    if evidence:
        rendered = "".join(
            f"<li>{_escape(ref_type)}: {_escape(label)}</li>"
            for ref_type, label in evidence
        )
        sections.append(f"<h4>Evidence</h4><ul>{rendered}</ul>")
    technical_refs = _priority_technical_refs(item)
    if technical_refs:
        rendered = "".join(
            "<li>"
            f"{_escape(_text(ref.get('type'), 'reference'))}: "
            f"{_escape(_text(ref.get('id'), '(missing)'))}"
            "</li>"
            for ref in technical_refs
        )
        sections.append(f"<h4>Technical evidence</h4><ul>{rendered}</ul>")
    if not sections:
        return ""
    return f'<div class="decision-details-dropdown">{"".join(sections)}</div>'


def _priority_evidence_items(
    item: Dict[str, Any],
    labels: Dict[str, str],
) -> List[Tuple[str, str]]:
    evidence = item.get("evidence")
    if isinstance(evidence, list):
        items = []
        for ref in evidence:
            if not isinstance(ref, dict):
                continue
            ref_type = _business_evidence_type(_text(ref.get("type")))
            label = _text(ref.get("label"))
            ref_id = _text(ref.get("id"))
            items.append((ref_type, label or labels.get(ref_id, ref_id)))
        return items
    refs = _list(item, "evidenceRefs")
    return [
        (
            _business_evidence_type(_text(ref.get("type"))),
            labels.get(_text(ref.get("id")), _text(ref.get("id"))),
        )
        for ref in refs
    ]


def _priority_technical_refs(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence = item.get("evidence")
    if isinstance(evidence, list):
        return [ref for ref in evidence if isinstance(ref, dict)]
    return _list(item, "evidenceRefs")


def _render_swot_bucket(
    bucket: str,
    items: List[Dict[str, Any]],
    labels: Dict[str, str],
) -> str:
    title = _swot_leadership_label(bucket)
    if not items:
        body = "<p>No entries.</p>"
    else:
        body = "".join(_render_swot_item(item, labels, bucket=bucket) for item in items)
    return f'<section class="swot-card"><h3>{_escape(title)}</h3>{body}</section>'


def _render_leadership_summary_bar(summary: Dict[str, Any]) -> str:
    value = summary.get("leadershipSummary")
    if not isinstance(value, dict):
        return ""
    items = [
        ("Recommended first move", value.get("recommendedFirstMove")),
        ("Second growth path", value.get("secondGrowthPath")),
        ("Main risk", value.get("mainRisk")),
    ]
    cards = []
    for label, text in items:
        rendered = _text(text)
        if rendered:
            cards.append(
                '<article class="leadership-summary-point">'
                f"<span>{_escape(label)}</span>"
                f"<strong>{_escape(rendered)}</strong>"
                "</article>"
            )
    if not cards:
        return ""
    return f'<section class="leadership-summary-bar">{"".join(cards)}</section>'


def _render_swot_item(
    item: Dict[str, Any],
    labels: Dict[str, str],
    *,
    bucket: str,
) -> str:
    statement = _text(item.get("statement"))
    implication = _text(
        item.get("decisionImplication"),
        _default_decision_implication(bucket),
    )
    confidence = _confidence_label(item.get("confidence"))
    evidence_type = _evidence_type(item)
    basis = _confidence_basis(item)
    refs = _list(item, "evidenceRefs")
    return (
        '<article class="executive-item swot-item">'
        f'<p class="swot-finding">{_escape(statement)}</p>'
        '<div class="decision-implication">'
        "<span>Decision implication</span>"
        f"<p>{_escape(implication)}</p>"
        "</div>"
        '<div class="executive-meta">'
        f"<div><span>Confidence</span><strong>{_escape(confidence)}</strong></div>"
        f"<div><span>Evidence type</span><strong>{_escape(evidence_type)}</strong></div>"
        f"<div><span>Basis</span><strong>{_escape(basis)}</strong></div>"
        "</div>"
        f"{_render_business_evidence(refs, labels)}"
        f"{_render_technical_evidence(refs)}"
        "</article>"
    )


def _render_executive_list(
    title: str,
    items: List[Dict[str, Any]],
    labels: Dict[str, str],
    *,
    primary_key: str,
) -> str:
    if not items:
        return ""
    body = "".join(
        _render_executive_item(item, labels, primary_key=primary_key) for item in items
    )
    return f'<section class="executive-list"><h3>{_escape(title)}</h3>{body}</section>'


def _render_executive_item(
    item: Dict[str, Any],
    labels: Dict[str, str],
    *,
    primary_key: str = "statement",
) -> str:
    statement = _text(item.get(primary_key), _text(item.get("statement")))
    facts = [
        ("Confidence", item.get("confidence")),
        ("Urgency", item.get("urgency")),
        ("Decision", item.get("decisionType")),
        ("Inference", "yes" if item.get("inference") is True else None),
    ]
    return (
        '<article class="executive-item">'
        f"<p>{_escape(statement)}</p>"
        f"{_render_facts(facts)}"
        f"{_render_evidence_refs(_list(item, 'evidenceRefs'), labels)}"
        "</article>"
    )


def _swot_leadership_label(bucket: str) -> str:
    labels = {
        "strengths": "What is working",
        "weaknesses": "What needs attention",
        "opportunities": "Where to invest next",
        "threats": "What could block progress",
    }
    return labels.get(bucket, _title_from_text(bucket))


def _default_decision_implication(bucket: str) -> str:
    defaults = {
        "strengths": "Use this as a candidate for first delivery funding.",
        "weaknesses": "Resolve this before moving into delivery.",
        "opportunities": "Validate this before assigning delivery capacity.",
        "threats": "Reduce this risk before final prioritization.",
    }
    return defaults.get(bucket, "Review this before making a portfolio decision.")


def _confidence_label(value: Any) -> str:
    confidence = _text(value, "medium").lower()
    if confidence == "high":
        return "High"
    if confidence == "low":
        return "Low"
    return "Medium"


def _evidence_type(item: Dict[str, Any]) -> str:
    return "Inferred" if item.get("inference") is True else "Direct"


def _confidence_basis(item: Dict[str, Any]) -> str:
    confidence = _text(item.get("confidence"), "medium").lower()
    if confidence == "high" and item.get("inference") is not True:
        return "Direct portfolio alignment"
    refs = _list(item, "evidenceRefs")
    types = [_business_evidence_type(_text(ref.get("type"))) for ref in refs]
    if confidence == "low":
        if any(label == "Signal" for label in types):
            return "Thin signal coverage"
        return "Limited portfolio evidence"
    unique = []
    for label in types:
        plural = _basis_plural(label)
        if plural and plural not in unique:
            unique.append(plural)
    if unique:
        return f"Inferred from {_join_human_list(unique)}"
    return "Inferred from portfolio evidence"


def _basis_plural(label: str) -> str:
    mapping = {
        "Objective": "objectives",
        "Use case": "use cases",
        "Candidate product": "product references",
        "Signal": "signals",
    }
    return mapping.get(label, "")


def _join_human_list(items: List[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _render_business_evidence(
    refs: List[Dict[str, Any]],
    labels: Dict[str, str],
) -> str:
    if not refs:
        return (
            '<div class="business-evidence"><h4>Evidence</h4>'
            "<p>No evidence references.</p></div>"
        )
    items = []
    for ref in refs:
        ref_type = _business_evidence_type(_text(ref.get("type")))
        ref_id = _text(ref.get("id"))
        label = labels.get(ref_id, ref_id or "(missing)")
        items.append(f"<li>{_escape(ref_type)}: {_escape(label)}</li>")
    return (
        '<div class="business-evidence"><h4>Evidence</h4>'
        f"<ul>{''.join(items)}</ul></div>"
    )


def _business_evidence_type(value: str) -> str:
    labels = {
        "businessObjective": "Objective",
        "useCase": "Use case",
        "productReference": "Candidate product",
        "signal": "Signal",
        "graph": "Portfolio evidence",
        "graphEdge": "Portfolio evidence",
    }
    return labels.get(value, _display_label(value) if value else "Portfolio evidence")


def _render_technical_evidence(refs: List[Dict[str, Any]]) -> str:
    if not refs:
        return ""
    items = []
    for ref in refs:
        ref_type = _text(ref.get("type"), "reference")
        ref_id = _text(ref.get("id"), "(missing)")
        items.append(f"<li>{_escape(ref_type)}: {_escape(ref_id)}</li>")
    return (
        '<details class="technical-evidence">'
        "<summary>Technical evidence</summary>"
        f"<ul>{''.join(items)}</ul>"
        "</details>"
    )


def _render_evidence_refs(
    refs: List[Dict[str, Any]],
    labels: Dict[str, str],
) -> str:
    if not refs:
        return '<div class="evidence-refs"><span class="chip warning">No evidence refs</span></div>'
    chips = []
    for ref in refs:
        ref_type = _text(ref.get("type"), "reference")
        ref_id = _text(ref.get("id"), "(missing)")
        label = labels.get(ref_id, ref_id)
        chips.append(
            '<span class="chip evidence-ref">'
            f"{_escape(ref_type)}: {_escape(label)}"
            f" <small>{_escape(ref_id)}</small>"
            "</span>"
        )
    return f'<div class="evidence-refs">{"".join(chips)}</div>'


def _render_portfolio_changes(versions: List[Dict[str, Any]]) -> str:
    latest = _latest_version(versions)
    if latest is None:
        body = (
            '<article class="action-card overview-card changes-card">'
            "<p>No version snapshots exist yet. A change summary will appear "
            "after the first build, refresh, or sync snapshot is created.</p>"
            "</article>"
        )
    else:
        report = latest.get("report") if isinstance(latest.get("report"), dict) else {}
        change_items = _latest_change_items(report)
        validation = _change_validation_label(report)
        list_html = "".join(f"<li>{_escape(item)}</li>" for item in change_items)
        body = (
            '<article class="action-card overview-card changes-card">'
            '<div class="chip-row"><span class="chip">Latest portfolio snapshot</span></div>'
            f"<p>{_escape(_text(latest.get('summary'), 'Latest portfolio snapshot.'))}</p>"
            f"{_render_facts([('Version', latest.get('id')), ('Run', report.get('kind') or latest.get('type')), ('Validation', validation)])}"
            f'<ul class="change-story-list">{list_html}</ul>'
            "</article>"
        )
    return (
        '<section class="overview-section" aria-label="What changed since last version">'
        '<div class="section-head"><div>'
        '<p class="eyebrow">Latest delta</p>'
        "<h2>What changed since last version</h2>"
        "</div></div>"
        f'<div class="overview-card-grid">{body}</div>'
        "</section>"
    )


def _latest_version(versions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not versions:
        return None
    return max(versions, key=lambda version: _text(version.get("id")))


def _change_validation_label(report: Dict[str, Any]) -> str:
    if "valid" not in report:
        return "Not recorded"
    return "Valid" if bool(report.get("valid")) else "Validation needs review"


def _latest_change_items(report: Dict[str, Any]) -> List[str]:
    items = []
    for label, key in (
        ("artifact was created", "created"),
        ("artifact was updated", "updated"),
        ("artifact was removed", "removed"),
    ):
        count = _change_list_count(report.get(key))
        if count:
            items.append(_plural_sentence(count, label))
    items.extend(_source_change_items(report.get("sourceChanges")))
    if report.get("valid") is True:
        items.append("Generated artifacts validated successfully.")
    elif report.get("valid") is False:
        items.append("Validation needs review before production use.")
    if not items:
        items.append("No material portfolio changes were recorded.")
    return items


def _plural_sentence(count: int, singular: str) -> str:
    if count == 1:
        return f"1 {singular}."
    return f"{count} {singular.replace(' was ', 's were ')}."


def _source_change_items(value: Any) -> List[str]:
    if not isinstance(value, dict):
        return []
    items = []
    lane_labels = {
        "objectives": "Business objective",
        "useCases": "Use case",
        "signals": "Signal",
        "products": "Product",
    }
    for lane, changes in sorted(value.items()):
        if not isinstance(changes, dict):
            continue
        label = lane_labels.get(str(lane), _title_from_text(str(lane)))
        if _change_list_count(changes.get("created")):
            items.append(f"New {label.lower()} source evidence was added.")
        if _change_list_count(changes.get("updated")):
            items.append(f"{label} source evidence was updated.")
        if _change_list_count(changes.get("removed")):
            items.append(f"{label} source evidence was removed.")
    return items


def _render_recommended_actions(
    catalog: Dict[str, Any],
    graph: Dict[str, Any],
    products: Dict[str, Dict[str, Any]],
    warnings: List[str],
) -> str:
    actions = []
    if warnings:
        actions.append(
            (
                "Review",
                "Review portfolio warnings",
                f"{len(warnings)} warning item(s) need human review.",
                "tab-overview",
                "Review Overview",
            )
        )
    product_refs = _list(catalog, "productReferences")
    if product_refs and len(products) < len(product_refs):
        actions.append(
            (
                "Resolve",
                "Link missing ODPS specs",
                "Some product references do not have matching ODPS product details.",
                "tab-products",
                "Open Products",
            )
        )
    if product_refs:
        actions.append(
            (
                "Complete",
                "Expand product evidence",
                "Review commercial, SLA, and data quality evidence for generated products.",
                "tab-products",
                "Open Products",
            )
        )
    if _count(graph, "nodes"):
        actions.append(
            (
                "Validate",
                "Check graph coverage",
                "Review whether every objective and signal has a useful relationship path.",
                "tab-graph",
                "Open Graph",
            )
        )
    if not actions:
        actions.append(
            (
                "Review",
                "Inspect generated artifacts",
                "Open each artifact tab and confirm the generated portfolio is ready to maintain.",
                "tab-products",
                "Open Products",
            )
        )
    cards = "".join(
        '<article class="action-card">'
        f'<span class="chip">{_escape(kind)}</span>'
        f"<strong>{_escape(title)}</strong>"
        f"<p>{_escape(description)}</p>"
        f'<label class="action-link" for="{_escape_attr(target)}">{_escape(label)}</label>'
        "</article>"
        for kind, title, description, target, label in actions[:3]
    )
    return (
        '<section aria-label="Recommended next actions">'
        '<div class="section-head"><div>'
        '<p class="eyebrow">Operational Guidance</p>'
        "<h2>Recommended next actions</h2>"
        "</div></div>"
        f'<div class="actions-grid">{cards}</div>'
        "</section>"
    )


def _render_versions(versions: List[Dict[str, Any]]) -> str:
    recent = versions[:5]
    recent_items = [
        '<li class="version-row"><strong>Current</strong><span>latest</span></li>'
    ]
    for version in recent:
        html_path = _escape_attr(version["html"])
        recent_items.append(
            '<li class="version-row">'
            f'<a href="{html_path}">{_escape(version["id"])}</a>'
            f'<a class="version-action" href="{html_path}">Open</a>'
            "</li>"
        )
    if not versions:
        recent_items.append(
            '<li class="version-row"><span>No snapshots yet</span></li>'
        )
    rows = "".join(
        "<tr>"
        f"<td>{_escape(version['id'])}</td>"
        f"<td>{_escape(version['type'])}</td>"
        f"<td>{_escape(version['summary'])}</td>"
        f'<td><a class="version-action" href="{_escape_attr(version["html"])}">Open</a></td>'
        "</tr>"
        for version in versions
    )
    history = ""
    if versions:
        history = (
            '<details class="version-history">'
            f"<summary>Show all {len(versions)} versions</summary>"
            '<table class="version-table"><thead>'
            "<tr><th>Version</th><th>Run</th><th>Summary</th><th></th></tr>"
            f"</thead><tbody>{rows}</tbody></table></details>"
        )
    return (
        '<section class="overview-section" aria-label="Portfolio versions">'
        '<div class="section-head"><div>'
        '<p class="eyebrow">Version history</p>'
        "<h2>Portfolio versions</h2>"
        "</div></div>"
        '<div class="overview-card-grid">'
        '<article class="action-card overview-card versions-card">'
        "<p>Latest page is always this index.html; previous snapshots open from "
        "version folders.</p>"
        f'<ul class="version-list">{"".join(recent_items)}</ul>'
        f"{history}"
        "</article>"
        "</div>"
        "</section>"
    )


def _render_artifact_panel(
    tab: str,
    label: str,
    title: str,
    eyebrow: str,
    description: str,
    items: List[Dict[str, Any]],
    *,
    card_class: str = "",
    show_id: bool = True,
) -> str:
    cards = "".join(
        _render_artifact_card(item, card_class=card_class, show_id=show_id)
        for item in items
    )
    if not cards:
        cards = "<p>No entries.</p>"
    return (
        f'<section class="tab-panel {tab}-panel" id="{tab}">'
        '<div class="section-head"><div>'
        f'<p class="eyebrow">{_escape(eyebrow)}</p>'
        f"<h2>{_escape(title)}</h2>"
        f"</div><p>{_escape(description)}</p></div>"
        f'<div class="grid">{cards}</div>'
        "</section>"
    )


def _render_artifact_card(
    item: Dict[str, Any], *, card_class: str = "", show_id: bool = True
) -> str:
    name = _text(item.get("name"), _text(item.get("id"), "(unnamed)"))
    details = [
        ("Status", item.get("status")),
        ("Priority", item.get("priority")),
        ("Confidence", item.get("confidence")),
        ("Type", item.get("type")),
    ]
    if show_id:
        details.insert(0, ("ID", item.get("id")))
    return (
        f'<article class="card{card_class}">'
        '<div class="chip-row"><span class="chip odpc">ODPC</span></div>'
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
    modals = []
    for reference in references:
        product_info = _resolve_product(reference, products)
        modal_id = _product_modal_id(reference, product_info)
        cards.append(_render_product_card(reference, product_info, modal_id))
        if product_info is not None:
            modals.append(_render_product_modal(reference, product_info, modal_id))
    content = "".join(cards) or "<p>No entries.</p>"
    return (
        '<section class="tab-panel products-panel" id="products">'
        '<div class="section-head"><div>'
        '<p class="eyebrow">Product Reference + ODPS Detail</p>'
        "<h2>Products</h2>"
        "</div><p>Product cards start from ODPC references and open into "
        "detailed ODPS product specifications.</p></div>"
        f'<div class="product-grid">{content}</div>'
        f"{''.join(modals)}"
        "</section>"
    )


def _render_product_card(
    reference: Dict[str, Any],
    product_info: Optional[Dict[str, Any]],
    modal_id: str,
) -> str:
    product_id = _text(reference.get("productID") or reference.get("id"))
    name = _text(reference.get("name"), product_id or "(unnamed)")
    product = (
        product_info.get("document", {}).get("product", {})
        if isinstance(product_info, dict)
        else {}
    )
    pricing_count = len(_pricing_items(product))
    sla_count = len(_declarative_items(product.get("SLA")))
    quality_count = len(_declarative_items(product.get("dataQuality")))
    details = [
        ("Product ID", product_id),
        ("Status", reference.get("status")),
        ("Visibility", reference.get("visibility")),
        ("Type", reference.get("type")),
    ]
    counters = [
        ("Pricing", pricing_count),
        ("SLA", sla_count),
        ("DQ", quality_count),
    ]
    tags = _string_list(reference.get("tags"))
    generation = reference.get("x-generation")
    fallback_generation = isinstance(generation, dict) and bool(
        generation.get("fallback")
    )
    generation_reason = (
        _text(generation.get("reason")) if isinstance(generation, dict) else ""
    )
    review_chips = []
    if fallback_generation:
        review_chips.append('<span class="chip warning">Needs review</span>')
    if "fallback-generated" in tags:
        review_chips.append('<span class="chip warning">Fallback generated</span>')
    review_html = (
        f'<div class="product-review-chips">{"".join(review_chips)}</div>'
        if review_chips
        else ""
    )
    reason_html = (
        '<p class="product-review-note">'
        f"Fallback reason: {_escape(generation_reason)}"
        "</p>"
        if fallback_generation and generation_reason
        else ""
    )
    counter_html = "".join(
        f"<span><strong>{count}</strong>{_escape(label)}</span>"
        for label, count in counters
        if count
    )
    button = (
        '<button class="product-detail-button" type="button" '
        f'data-modal-target="{_escape_attr(modal_id)}">Details</button>'
        if product_info is not None
        else '<span class="odp-muted">No linked ODPS detail</span>'
    )
    return (
        '<article class="card product product-card">'
        '<div class="chip-row"><span class="chip odps">ODPS</span>'
        '<span class="chip odpc">ODPC Reference</span></div>'
        f"<h3>{_escape(name)}</h3>"
        f'<p class="product-card-description">{_escape(_text(reference.get("description")))}</p>'
        f"{review_html}"
        f"{reason_html}"
        f"{_render_facts(details)}"
        f'<div class="product-card-counters">{counter_html}</div>'
        f'<div class="product-card-actions">{button}</div>'
        "</article>"
    )


def _product_modal_id(
    reference: Dict[str, Any],
    product_info: Optional[Dict[str, Any]],
) -> str:
    if product_info is not None:
        details = _product_details(product_info["document"])
        product_id = _text(details.get("productID"))
        if product_id:
            return f"product-modal-{_path_id(product_id)}"
    product_id = _text(reference.get("productID") or reference.get("id"), "product")
    return f"product-modal-{_path_id(product_id)}"


def _render_product_modal(
    reference: Dict[str, Any],
    product_info: Dict[str, Any],
    modal_id: str,
) -> str:
    details = _product_details(product_info["document"])
    name = _text(details.get("name"), _text(reference.get("name"), "Product"))
    return (
        f'<div class="product-modal" id="{_escape_attr(modal_id)}" '
        'aria-hidden="true" role="dialog" aria-modal="true" '
        f'aria-label="{_escape_attr(name)} details">'
        '<div class="product-modal-backdrop" data-modal-close></div>'
        '<div class="product-modal-panel" role="document">'
        '<div class="product-modal-header">'
        f'<div><p class="eyebrow">ODPS Product Detail</p><h3>{_escape(name)}</h3></div>'
        '<button class="product-modal-close" type="button" '
        'data-modal-close aria-label="Close product details">Close</button>'
        "</div>"
        f"{_render_product_detail(product_info)}"
        "</div>"
        "</div>"
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
    reference_keys = _product_reference_match_keys(reference)
    for product in products.values():
        product_keys = _product_spec_match_keys(product)
        if reference_keys & product_keys:
            return product
    return None


def _product_reference_match_keys(reference: Dict[str, Any]) -> Set[str]:
    keys: Set[str] = set()
    for value in (reference.get("productID"), reference.get("id")):
        keys.update(_product_slug_variants(_text(value)))
    product_model = reference.get("productModel")
    if isinstance(product_model, dict):
        ref = _text(product_model.get("$ref") or product_model.get("ref"))
        if ref:
            keys.update(_product_slug_variants(Path(ref).stem))
    return keys


def _product_spec_match_keys(product_info: Dict[str, Any]) -> Set[str]:
    keys: Set[str] = set()
    document = product_info.get("document")
    details = _product_details(document) if isinstance(document, dict) else {}
    for value in (details.get("productID"), details.get("id")):
        keys.update(_product_slug_variants(_text(value)))
    path = product_info.get("path")
    if isinstance(path, Path):
        keys.update(_product_slug_variants(path.stem))
    return keys


def _product_slug_variants(value: str) -> Set[str]:
    slug = _path_id(value).lower()
    if not slug:
        return set()
    variants = {slug}
    for suffix in ("-odps-product", "-data-product", "-product"):
        if slug.endswith(suffix):
            variants.add(slug[: -len(suffix)])
    return {variant for variant in variants if variant}


def _render_product_detail(product_info: Dict[str, Any]) -> str:
    document = product_info["document"]
    path = product_info["path"]
    details = _product_details(document)
    product = document.get("product", {}) if isinstance(document, dict) else {}
    facts = [
        ("Product ID", details.get("productID")),
        ("Status", details.get("status")),
        ("Visibility", details.get("visibility")),
        ("Type", details.get("type")),
    ]
    pricing_items = _pricing_items(product)
    product_model_path = _escape(str(path))
    description = _text(details.get("description"))
    description_html = (
        f'<p class="product-detail-description">{_escape(description)}</p>'
        if description
        else ""
    )
    sections = [
        _render_pricing_section(pricing_items, product),
        _render_market_profile_section(
            "Data Quality", _declarative_items(product.get("dataQuality"))
        ),
        _render_market_profile_section("SLA", _declarative_items(product.get("SLA"))),
        _render_license_section(product.get("license")),
    ]
    return (
        '<div class="odp-detail product-detail-layout">'
        '<section class="product-detail-hero">'
        f"{description_html}"
        f'<div class="product-detail-meta">{_render_facts(facts)}</div>'
        "</section>"
        f'<div class="product-marketplace-segments">{"".join(sections)}</div>'
        f'<p class="odp-muted">Raw artifact: {product_model_path}</p>'
        "</div>"
    )


def _render_graph(graph: Dict[str, Any], labels: Dict[str, str]) -> str:
    explorer_html = _portfolio_graph_explorer_html(graph, labels)
    return (
        '<section class="tab-panel graph-panel" id="graph">'
        '<div class="section-head"><div>'
        '<p class="eyebrow">ODPG Graph View</p>'
        "<h2>Graph explorer</h2>"
        "</div></div>"
        '<iframe class="graph-explorer-frame" title="ODPG graph explorer" '
        f'srcdoc="{_escape_attr(explorer_html)}"></iframe>'
        "</section>"
    )


def _portfolio_graph_explorer_html(
    graph: Dict[str, Any],
    labels: Dict[str, str],
) -> str:
    html_text = build_graph_explorer_html(_graph_for_explorer(graph, labels))
    html_text = _remove_html_block(
        html_text, '<footer class="odpg-footer">', "</footer>"
    )
    html_text = html_text.replace(
        "</style>",
        ".topbar{display:none!important;}</style>",
        1,
    )
    html_text = html_text.replace("max-height: 100dvh;", "max-height: none;")
    return html_text


def _graph_for_explorer(
    graph: Dict[str, Any],
    labels: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    document = deepcopy(graph)
    payload = document.get("graph") if isinstance(document, dict) else None
    if not isinstance(payload, dict):
        payload = document if isinstance(document, dict) else {}
    label_map = labels or {}
    for node in _list(payload, "nodes"):
        node_id = _text(node.get("id"))
        label = label_map.get(node_id)
        if label:
            node["label"] = {"en": label}
    normalized_edges = []
    for edge in _list(payload, "edges"):
        item = dict(edge)
        if "from" not in item and item.get("source"):
            item["from"] = item["source"]
        if "to" not in item and item.get("target"):
            item["to"] = item["target"]
        normalized_edges.append(item)
    payload["edges"] = normalized_edges
    return document


def _catalog_label_map(catalog: Dict[str, Any]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for collection in (
        "businessObjectives",
        "useCases",
        "signals",
        "productReferences",
    ):
        for item in _list(catalog, collection):
            item_id = _text(item.get("id"))
            label = _text(item.get("name"))
            if item_id and label:
                labels[item_id] = label
    return labels


def _remove_html_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        return text
    end = text.find(end_marker, start)
    if end == -1:
        return text
    return text[:start] + text[end + len(end_marker) :]


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
        '<section class="tab-panel about-panel" id="about">'
        '<article class="about-card">'
        '<div class="chip-row"><span class="chip">SDK '
        f"{_escape(_text(metadata.get('sdkVersion'), __version__))}</span>"
        '<span class="chip">ODPC</span><span class="chip">ODPS</span>'
        '<span class="chip">ODPG</span><span class="chip">ODPV</span></div>'
        "<h2>About this portfolio</h2>"
        "<p>This portfolio was generated with the Open Data Products SDK and "
        "is grounded in the OpenDataProducts.org standards family: ODPC for "
        "catalog objects, ODPS for product specifications, ODPG for graph "
        "relationships, and ODPV for shared vocabulary where used.</p>"
        "<p>Generated ODPS products are drafts. They are intended to give teams "
        "a quick start from source material such as text files, emails, briefs, "
        "and transcripts. Human review and acceptance are required before any "
        "generated product specification is treated as production-ready.</p>"
        f"<p>Generation timestamp: {_escape(_text(metadata.get('generatedAt'), '(not set)'))}</p>"
        f'<ul>{"".join(source_items)}</ul>'
        "</article></section>"
    )


def _render_footer(data: Dict[str, Any]) -> str:
    versions = data.get("versions")
    has_versions = isinstance(versions, list) and bool(versions)
    latest_version = _latest_version(versions if isinstance(versions, list) else [])
    version_link = _escape_attr(
        _text(latest_version.get("html"))
        if isinstance(latest_version, dict)
        else "#overview"
    )
    version_action = (
        f'<a href="{version_link}">Compare previous snapshot</a>'
        if has_versions
        else "<span>No previous snapshots yet</span>"
    )
    return (
        '<footer class="footer">'
        '<div class="wrap footer-inner">'
        '<p class="footer-status">Draft portfolio generated with the Data Products '
        "SDK. Human review is required before product specs are treated as "
        "production-ready.</p>"
        '<div class="footer-columns">'
        '<section class="footer-column">'
        "<h2>Review status</h2>"
        "<ul>"
        "<li>Draft portfolio</li>"
        "<li>Human acceptance required</li>"
        f"<li>{'Latest snapshot available' if has_versions else 'No version snapshot yet'}</li>"
        "</ul>"
        "</section>"
        '<nav class="footer-column" aria-label="Portfolio next actions">'
        "<h2>Next actions</h2>"
        "<ul>"
        '<li><a href="#executive-summary">Review executive decisions</a></li>'
        '<li><a href="#executive-summary">Resolve evidence gaps</a></li>'
        '<li><a href="#products">Approve product specs</a></li>'
        f"<li>{version_action}</li>"
        "</ul>"
        "</nav>"
        '<nav class="footer-column" aria-label="Portfolio evidence links">'
        "<h2>Evidence</h2>"
        "<ul>"
        '<li><a href="#about">Source summary</a></li>'
        '<li><a href="#overview">Portfolio versions</a></li>'
        '<li><a href="#graph">Graph view</a></li>'
        '<li><a href="#objectives">Catalog objects</a></li>'
        "</ul>"
        "</nav>"
        '<nav class="footer-column" aria-label="Portfolio artifact links">'
        "<h2>Artifacts</h2>"
        "<ul>"
        '<li><a href="odpc/catalog.yaml">Catalog YAML</a></li>'
        '<li><a href="odpg/graph.yaml">Graph YAML</a></li>'
        '<li><a href="#products">Product specs</a></li>'
        '<li><a href="#overview">Back to top</a></li>'
        "</ul>"
        "</nav>"
        "</div>"
        "</div>"
        "</footer>"
    )


def _normalize_product_spec_files(root: Path) -> List[Tuple[Path, str]]:
    written: List[Tuple[Path, str]] = []
    for path in _product_spec_paths(root):
        try:
            document = load_mapping(path, root_name="ODPS product")
        except ValueError:
            continue
        _normalize_odps_product(document)
        written.append(_write_yaml(path, document))
    return written


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
    if isinstance(declarative, dict):
        items = []
        for name, item in declarative.items():
            if isinstance(item, dict):
                named_item = dict(item)
                named_item.setdefault("profile", name)
                items.append(named_item)
        return items
    if isinstance(declarative, list):
        return [item for item in declarative if isinstance(item, dict)]
    return []


def _render_pricing_section(
    items: List[Dict[str, Any]], product: Dict[str, Any]
) -> str:
    cards = []
    for item in items:
        name = _text(item.get("name"), "Pricing plan")
        description = _text(item.get("description"))
        price = _text(item.get("price"), "0")
        currency = _text(item.get("priceCurrency"))
        amount = " ".join(part for part in (price, currency) if part)
        plan_facts = [
            ("Price", amount),
            ("Billing", item.get("billingDuration")),
            ("Unit", item.get("unit")),
            ("Access", _named_ref_label(item.get("access"), product.get("dataAccess"))),
        ]
        description_html = f"<p>{_escape(description)}</p>" if description else ""
        cards.append(
            '<article class="market-plan-card">'
            f"<h5>{_escape(name)}</h5>"
            f"{description_html}"
            f"{_render_facts(plan_facts)}"
            f"{_render_component_refs(item)}"
            "</article>"
        )
    content = (
        "".join(cards)
        if cards
        else '<p class="odp-muted">No pricing plans are defined yet.</p>'
    )
    return (
        '<section class="market-segment">'
        "<h4>Pricing</h4>"
        f'<div class="market-plan-list">{content}</div>'
        "</section>"
    )


def _render_market_profile_section(title: str, items: List[Dict[str, Any]]) -> str:
    cards = []
    for item in items:
        profile = _text(item.get("profile"), "default")
        name = _text(item.get("name"), _title_from_text(profile))
        description = _text(item.get("description"))
        description_html = f"<p>{_escape(description)}</p>" if description else ""
        cards.append(
            '<article class="market-profile-card">'
            f"<h5>{_escape(name)}</h5>"
            f'<span class="profile-chip">{_escape(profile)}</span>'
            f"{description_html}"
            f"{_render_dimension_summary(_profile_dimensions(item))}"
            "</article>"
        )
    content = (
        "".join(cards)
        if cards
        else f'<p class="odp-muted">No {title.lower()} profile is defined yet.</p>'
    )
    return (
        '<section class="market-segment">'
        f"<h4>{_escape(title)}</h4>"
        f'<div class="market-profile-list">{content}</div>'
        "</section>"
    )


def _render_license_section(value: Any) -> str:
    if not isinstance(value, dict):
        content = '<p class="odp-muted">No licensing terms are defined yet.</p>'
    else:
        scope = value.get("scope") if isinstance(value.get("scope"), dict) else {}
        facts = [
            ("Type", value.get("type")),
            ("Scope", scope.get("definition") if isinstance(scope, dict) else None),
            (
                "Restrictions",
                (
                    _short_text(scope.get("restrictions"))
                    if isinstance(scope, dict)
                    else None
                ),
            ),
        ]
        content = (
            _render_facts(facts)
            or '<p class="odp-muted">No licensing terms are defined yet.</p>'
        )
    return (
        '<section class="market-segment">'
        "<h4>Licensing</h4>"
        f'<div class="market-license-card">{content}</div>'
        "</section>"
    )


def _profile_dimensions(item: Dict[str, Any]) -> Any:
    dimensions = item.get("dimensions")
    if isinstance(dimensions, list):
        return dimensions
    if item.get("dimension") is not None or item.get("objective") is not None:
        return [item]
    return []


def _short_text(value: Any, limit: int = 180) -> str:
    text = _text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def _named_ref_label(reference: Any, value: Any) -> str:
    item = _resolve_named_ref(reference, value)
    if item is None:
        return _title_from_text(_profile_key_from_ref(_component_ref(reference)))
    return _text(
        item.get("name"),
        _title_from_text(_profile_key_from_ref(_component_ref(reference))),
    )


def _resolve_named_ref(reference: Any, value: Any) -> Optional[Dict[str, Any]]:
    profile_key = _profile_key_from_ref(_component_ref(reference))
    if not profile_key:
        return None
    if isinstance(value, dict):
        named = value.get(profile_key)
        if isinstance(named, dict):
            return named
        for key, item in value.items():
            if _path_id(str(key)) == _path_id(profile_key) and isinstance(item, dict):
                return item
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and _path_id(_text(item.get("name"))) == _path_id(
                profile_key
            ):
                return item
    return None


def _component_ref(value: Any) -> str:
    if isinstance(value, dict):
        return _text(value.get("$ref") or value.get("ref"))
    return _text(value)


def _profile_key_from_ref(ref: str) -> str:
    if not ref:
        return ""
    return ref.rstrip("/").split("/")[-1]


def _render_component_refs(item: Dict[str, Any]) -> str:
    refs = []
    for label, key in (
        ("Payment", "paymentGateway"),
        ("Data Quality", "dataQuality"),
        ("SLA", "SLA"),
        ("Access", "access"),
    ):
        value = item.get(key)
        if isinstance(value, dict):
            ref = _text(value.get("$ref") or value.get("ref"))
            if ref:
                profile = _profile_key_from_ref(ref)
                ref_label = _title_from_text(profile) if profile else ref
                refs.append(
                    f"<li><strong>{_escape(label)}</strong> {_escape(ref_label)}</li>"
                )
    if not refs:
        return ""
    return f'<ul class="component-refs">{"".join(refs)}</ul>'


def _render_dimension_summary(value: Any, limit: int = 3) -> str:
    if not isinstance(value, list):
        return ""
    items = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            continue
        label = _dimension_label(item)
        objective = _text(item.get("objective"))
        unit = _text(item.get("unit"))
        metric = " ".join(part for part in (objective, unit) if part and part != "null")
        metric_html = (
            f'<span class="dimension-metric">{_escape(metric)}</span>' if metric else ""
        )
        items.append(
            '<li class="dimension-summary-item">'
            f"<span>{_escape(label)}</span>{metric_html}"
            "</li>"
        )
    if not items:
        return ""
    if len(value) > limit:
        remaining = len(value) - limit
        items.append(
            '<li class="dimension-summary-item muted">'
            f"<span>+{remaining} more checks</span>"
            "</li>"
        )
    return f'<ul class="dimension-summary-list">{"".join(items)}</ul>'


def _dimension_label(item: Dict[str, Any]) -> str:
    for key in ("displayTitle", "displaytitle", "name", "dimension"):
        value = _text(item.get(key))
        if value:
            return value
    return "Dimension"


def _render_facts(facts: Iterable[Tuple[str, Any]]) -> str:
    pairs = []
    for label, value in facts:
        text = _text(value)
        if text:
            pairs.append(
                f"<dt>{_escape(_display_label(label))}</dt><dd>{_escape(text)}</dd>"
            )
    if not pairs:
        return ""
    return f'<dl class="odp-facts">{"".join(pairs)}</dl>'


def _display_label(value: str) -> str:
    if value == "$ref":
        return "Reference"
    if " " in value:
        return value
    words: List[str] = []
    current = []
    for index, char in enumerate(value):
        previous = value[index - 1] if index else ""
        next_char = value[index + 1] if index + 1 < len(value) else ""
        boundary = (
            index > 0
            and char.isupper()
            and (
                previous.islower()
                or previous.isdigit()
                or (previous.isupper() and next_char.islower())
            )
        )
        if boundary and current:
            words.append("".join(current))
            current = [char]
        else:
            current.append(char)
    if current:
        words.append("".join(current))
    return " ".join(word[:1].upper() + word[1:] for word in words)
