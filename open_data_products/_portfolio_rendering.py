"""Portfolio workspace loading, validation, and HTML rendering."""

from __future__ import annotations

import html
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from ._io import load_mapping
from ._portfolio_html import (
    EXECUTIVE_SUMMARY_CARD_ICONS,
    PORTFOLIO_ICON_ASSET_DIR,
    render_portfolio_html,
)
from ._portfolio_values import (
    as_list as _list,
    count as _count,
    text as _text,
)
from ._portfolio_workspace_paths import PortfolioWorkspacePaths
from ._portfolio_workspace import (
    empty_catalog as _empty_catalog,
    empty_graph as _empty_graph,
    load_optional_mapping as _load_optional_mapping,
    load_product_specs as _load_product_specs,
    portfolio_versions as _portfolio_versions,
)
from .odpc import load_catalog
from .odpg import load_graph

DEFAULT_PORTFOLIO_HTML = "index.html"
EXECUTIVE_SUMMARY_CONFIDENCE_VALUES = {"high", "medium", "low"}
EXECUTIVE_SUMMARY_SWOT_BUCKETS = (
    "strengths",
    "weaknesses",
    "opportunities",
    "threats",
)


def _group_written_paths(
    written: Iterable[Tuple[Path, str]],
) -> Tuple[List[str], List[str], List[str]]:
    created: List[str] = []
    updated: List[str] = []
    unchanged: List[str] = []
    for path, state in written:
        if state == "created":
            created.append(str(path))
        elif state == "updated":
            updated.append(str(path))
        else:
            unchanged.append(str(path))
    return created, updated, unchanged


def _string_list(value: Any) -> List[str]:
    """Return nonempty strings from a scalar or sequence."""
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _executive_summary_counts(value: Any) -> Dict[str, int]:
    """Return summary counts for a Portfolio executive summary."""
    if not isinstance(value, dict):
        return {
            "priorityItems": 0,
            "swotItems": 0,
            "leadershipDecisions": 0,
            "evidenceGaps": 0,
        }
    briefing = (
        value.get("priorityBriefing")
        if isinstance(value.get("priorityBriefing"), dict)
        else {}
    )
    priority_count = sum(
        1
        for key in ("primaryFocus", "secondaryFocus", "blocker", "readinessCheck")
        if isinstance(briefing.get(key), dict)
    )
    swot = value.get("swot") if isinstance(value.get("swot"), dict) else {}
    swot_count = sum(
        len(_list(swot, bucket)) for bucket in EXECUTIVE_SUMMARY_SWOT_BUCKETS
    )
    return {
        "priorityItems": priority_count,
        "swotItems": swot_count,
        "leadershipDecisions": len(_list(value, "leadershipDecisions")),
        "evidenceGaps": len(_list(value, "evidenceGaps")),
    }


def _copy_binary_asset(source: Path, target: Path) -> Tuple[Path, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    if existed and target.read_bytes() == source.read_bytes():
        return target, "unchanged"
    shutil.copy2(source, target)
    return target, "updated" if existed else "created"


def _portfolio_icon_source_dir() -> Path:
    packaged = Path(__file__).resolve().parent / "data" / "portfolio"
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parent.parent / "images" / "portfolio"


def _copy_portfolio_icon_assets(output_dir: Path) -> List[Tuple[Path, str]]:
    source_dir = _portfolio_icon_source_dir()
    target_dir = output_dir / PORTFOLIO_ICON_ASSET_DIR
    copied: List[Tuple[Path, str]] = []
    for filename in EXECUTIVE_SUMMARY_CARD_ICONS.values():
        source = source_dir / filename
        if source.exists():
            copied.append(_copy_binary_asset(source, target_dir / filename))
    return copied


def render_portfolio(
    workspace: Union[str, Path],
    *,
    output_path: Optional[Union[str, Path]] = None,
) -> Dict[str, object]:
    """Render a portfolio workspace as one static HTML page."""
    root = Path(workspace)
    data = load_portfolio_workspace(root)
    html_text = render_portfolio_html(data)
    validation_results = _portfolio_validation_results(data)
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
    icon_assets = _copy_portfolio_icon_assets(output.parent)
    created, updated, unchanged = _group_written_paths(icon_assets)
    result: Dict[str, object] = {
        "spec": "portfolio",
        "kind": "PortfolioRender",
        "workspace": str(root),
        "html": str(output),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "warnings": data["warnings"],
        "validationResults": validation_results,
        "valid": _valid_portfolio(validation_results),
    }
    result[changed_key] = [str(output), *result[changed_key]]
    return result


def explain_portfolio(workspace: Union[str, Path]) -> Dict[str, object]:
    """Return a JSON-ready summary of a portfolio workspace."""
    root = Path(workspace)
    data = load_portfolio_workspace(root)
    catalog = data["catalog"].get("catalog", {})
    graph = data["graph"].get("graph", {})
    validation_results = _portfolio_validation_results(data)
    executive_summary_counts = _executive_summary_counts(data.get("executive_summary"))
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
        "hasExecutiveSummary": bool(data.get("executive_summary")),
        "priorityItemCount": executive_summary_counts["priorityItems"],
        "swotItemCount": executive_summary_counts["swotItems"],
        "leadershipDecisionCount": executive_summary_counts["leadershipDecisions"],
        "evidenceGapCount": executive_summary_counts["evidenceGaps"],
        "warnings": data["warnings"],
        "validationResults": validation_results,
        "valid": _valid_portfolio(validation_results),
    }


def load_portfolio_workspace(workspace: Union[str, Path]) -> Dict[str, Any]:
    """Load portfolio map, catalog, product specs, graph, and version metadata."""
    root = Path(workspace)
    paths = PortfolioWorkspacePaths(root)
    catalog_path = paths.catalog
    graph_path = paths.graph
    portfolio_path = paths.portfolio
    executive_summary_path = paths.executive_summary
    i18n = _load_portfolio_i18n(root)
    portfolio = _load_optional_mapping(portfolio_path)
    portfolio_warnings = (
        portfolio.get("warnings") if isinstance(portfolio, dict) else []
    )
    warnings = [
        str(item)
        for item in (portfolio_warnings if isinstance(portfolio_warnings, list) else [])
        if item
    ]
    executive_summary = (
        load_mapping(executive_summary_path, root_name="Portfolio executive summary")
        if executive_summary_path.exists()
        else {}
    )
    catalog = load_catalog(catalog_path) if catalog_path.exists() else _empty_catalog()
    graph = load_graph(graph_path) if graph_path.exists() else _empty_graph()
    products = _load_product_specs(root)
    versions = _portfolio_versions(root, portfolio)
    return {
        "workspace": root,
        "portfolio": portfolio,
        "executive_summary": executive_summary,
        "executive_summary_path": executive_summary_path,
        "catalog": catalog,
        "catalog_path": catalog_path,
        "graph": graph,
        "graph_path": graph_path,
        "products": products,
        "versions": versions,
        "i18n": i18n,
        "language": _text(i18n.get("defaultLanguage"), "en"),
        "warnings": warnings,
    }


def _portfolio_validation_results(data: Dict[str, Any]) -> Dict[str, Any]:
    from .agent import validate_document
    from .odpc import validate_catalog
    from .odpg import validate_graph

    catalog_result = validate_catalog(data["catalog"])
    graph_result = validate_graph(data["graph"])
    product_results = []
    for product in data["products"].values():
        path = product.get("path")
        if isinstance(path, Path):
            try:
                result = validate_document(path)
                product_results.append(result.to_dict())
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                product_results.append(
                    {
                        "valid": False,
                        "spec": "odps",
                        "kind": "OpenDataProduct",
                        "path": str(path),
                        "errors": [str(exc)],
                    }
                )
    return {
        "catalog": {
            "valid": catalog_result.valid,
            "errors": list(catalog_result.errors),
        },
        "graph": graph_result.to_dict(),
        "products": product_results,
        "executiveSummary": _validate_executive_summary(data.get("executive_summary")),
    }


def _valid_portfolio(validation_results: Dict[str, Any]) -> bool:
    catalog = validation_results.get("catalog", {})
    graph = validation_results.get("graph", {})
    products = validation_results.get("products", [])
    executive_summary = validation_results.get("executiveSummary", {})
    return (
        bool(catalog.get("valid"))
        and bool(graph.get("valid"))
        and all(bool(product.get("valid")) for product in products)
        and bool(executive_summary.get("valid", True))
    )


def _validate_executive_summary(value: Any) -> Dict[str, Any]:
    if not value:
        return {
            "valid": True,
            "missing": True,
            "warnings": ["executive-summary.yaml has not been generated."],
            "errors": [],
        }
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(value, dict):
        return {
            "valid": False,
            "missing": False,
            "warnings": [],
            "errors": ["executive summary must be a mapping"],
        }
    for key in ("kind", "portfolioPosition", "priorityBriefing"):
        if key not in value:
            errors.append(f"{key} is required")
    if value.get("kind") and value.get("kind") != "PortfolioExecutiveSummary":
        errors.append("kind must be PortfolioExecutiveSummary")
    position = value.get("portfolioPosition")
    if isinstance(position, dict):
        for key in ("headline", "narrative"):
            if not _text(position.get(key)):
                errors.append(f"portfolioPosition.{key} is required")
    _validate_priority_briefing(value.get("priorityBriefing"), errors)
    swot = value.get("swot")
    if swot is not None:
        if not isinstance(swot, dict):
            errors.append("swot must be a mapping")
        else:
            _validate_legacy_swot(swot, errors)
    for index, item in enumerate(_list(value, "leadershipDecisions")):
        path = f"leadershipDecisions[{index}]"
        for key in ("question", "decisionType", "urgency"):
            if not _text(item.get(key)):
                errors.append(f"{path}.{key} is required")
        for ref_index, reference in enumerate(_list(item, "evidenceRefs")):
            _validate_evidence_ref(
                reference,
                f"{path}.evidenceRefs[{ref_index}]",
                errors,
            )
    for index, item in enumerate(_list(value, "evidenceGaps")):
        path = f"evidenceGaps[{index}]"
        if not _text(item.get("statement")):
            errors.append(f"{path}.statement is required")
        if not _list(item, "evidenceRefs"):
            warnings.append(f"{path}.evidenceRefs is empty")
    return {
        "valid": not errors,
        "missing": False,
        "warnings": warnings,
        "errors": errors,
    }


def _validate_priority_briefing(value: Any, errors: List[str]) -> None:
    if not isinstance(value, dict):
        errors.append("priorityBriefing must be a mapping")
        return
    if not _text(value.get("recommendation")):
        errors.append("priorityBriefing.recommendation is required")
    for key in ("primaryFocus", "secondaryFocus", "blocker", "readinessCheck"):
        path = f"priorityBriefing.{key}"
        item = value.get(key)
        if not isinstance(item, dict):
            errors.append(f"{path} must be a mapping")
            continue
        for required in ("title", "message", "action"):
            if not _text(item.get(required)):
                errors.append(f"{path}.{required} is required")
        confidence = _text(item.get("confidence"))
        if confidence and confidence not in EXECUTIVE_SUMMARY_CONFIDENCE_VALUES:
            errors.append(f"{path}.confidence must be high, medium, or low")
        evidence = item.get("evidence")
        refs = _list(item, "evidenceRefs")
        if isinstance(evidence, list):
            if not evidence:
                errors.append(f"{path}.evidence is required")
            for index, reference in enumerate(evidence):
                _validate_evidence_ref(reference, f"{path}.evidence[{index}]", errors)
        elif refs:
            for index, reference in enumerate(refs):
                _validate_evidence_ref(
                    reference, f"{path}.evidenceRefs[{index}]", errors
                )
        else:
            errors.append(f"{path}.evidence is required")


def _validate_legacy_swot(swot: Dict[str, Any], errors: List[str]) -> None:
    for bucket in EXECUTIVE_SUMMARY_SWOT_BUCKETS:
        for index, item in enumerate(_list(swot, bucket)):
            path = f"swot.{bucket}[{index}]"
            if not _text(item.get("statement")):
                errors.append(f"{path}.statement is required")
            if not _list(item, "evidenceRefs"):
                errors.append(f"{path}.evidenceRefs is required")
            confidence = _text(item.get("confidence"))
            if confidence and confidence not in EXECUTIVE_SUMMARY_CONFIDENCE_VALUES:
                errors.append(f"{path}.confidence must be high, medium, or low")
            for ref_index, reference in enumerate(_list(item, "evidenceRefs")):
                _validate_evidence_ref(
                    reference,
                    f"{path}.evidenceRefs[{ref_index}]",
                    errors,
                )


def _validate_evidence_ref(
    value: Any,
    path: str,
    errors: List[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be a mapping")
        return
    if not _text(value.get("type")):
        errors.append(f"{path}.type is required")
    if not _text(value.get("id")):
        errors.append(f"{path}.id is required")


def _load_portfolio_i18n(root: Path) -> Dict[str, Any]:
    i18n = _load_optional_mapping(root / "portfolio-i18n.yaml")
    if not isinstance(i18n, dict):
        return {}
    default_language = _normalize_language_tag(_text(i18n.get("defaultLanguage"), "en"))
    languages = _merge_languages(
        [default_language], _string_list(i18n.get("languages"))
    )
    i18n["defaultLanguage"] = default_language
    i18n["languages"] = languages
    translations = i18n.get("translations")
    if not isinstance(translations, dict):
        i18n["translations"] = {}
    return i18n


def _parse_language_tags(value: Union[str, Iterable[str]]) -> List[str]:
    raw_values: List[str] = []
    if isinstance(value, str):
        raw_values = [value]
    else:
        raw_values = [str(item) for item in value]
    languages = []
    for raw in raw_values:
        for part in raw.split(","):
            language = _normalize_language_tag(part)
            if language and language not in languages:
                languages.append(language)
    return languages


def _prune_i18n_html_translations(
    i18n: Dict[str, Any], source_strings: Set[str]
) -> None:
    translations = i18n.get("translations")
    if not isinstance(translations, dict):
        return
    for language_translations in translations.values():
        if not isinstance(language_translations, dict):
            continue
        html_translations = language_translations.get("html")
        if not isinstance(html_translations, dict):
            continue
        for key in list(html_translations):
            if str(key) not in source_strings:
                del html_translations[key]


def _localization_qa(
    source_strings: Sequence[str],
    translations: Mapping[str, Any],
    target_languages: Sequence[str],
) -> Dict[str, object]:
    source_set = set(source_strings)
    source_count = len(source_set)
    languages: Dict[str, Dict[str, object]] = {}
    for language in target_languages:
        language_map = translations.get(language)
        if not isinstance(language_map, dict):
            language_map = {}
        html_translations = language_map.get("html")
        if not isinstance(html_translations, dict):
            html_translations = {}
        present_keys = {
            str(key)
            for key, value in html_translations.items()
            if str(key) in source_set and str(value).strip()
        }
        changed_keys = {
            str(key)
            for key, value in html_translations.items()
            if str(key) in source_set
            and str(value).strip()
            and str(value).strip() != str(key)
        }
        unchanged_keys = present_keys - changed_keys
        missing_count = max(source_count - len(present_keys), 0)
        languages[language] = {
            "translationCount": len(html_translations),
            "sourceStringCount": source_count,
            "presentStringCount": len(present_keys),
            "changedStringCount": len(changed_keys),
            "unchangedStringCount": len(unchanged_keys),
            "missingStringCount": missing_count,
            "coverage": _ratio(len(present_keys), source_count),
            "changedCoverage": _ratio(len(changed_keys), source_count),
        }
    return {
        "sourceStringCount": source_count,
        "languages": languages,
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(numerator / denominator, 4)


def _normalize_language_tag(value: str) -> str:
    language = value.strip()
    if not language:
        return ""
    if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", language):
        raise ValueError(f"Invalid BCP 47 language tag: {value}")
    parts = language.split("-")
    normalized = [parts[0].lower()]
    normalized.extend(part.upper() if len(part) == 2 else part for part in parts[1:])
    return "-".join(normalized)


def _merge_languages(*groups: Iterable[str]) -> List[str]:
    languages = []
    for group in groups:
        for item in group:
            language = _normalize_language_tag(str(item))
            if language and language not in languages:
                languages.append(language)
    return languages


def _localized_html_filename(language: str, default_language: str) -> str:
    return (
        DEFAULT_PORTFOLIO_HTML
        if language == default_language
        else f"index.{language}.html"
    )


def _i18n_html_translations(i18n: Any, language: str) -> Dict[str, str]:
    if not isinstance(i18n, dict):
        return {}
    translations = i18n.get("translations")
    if not isinstance(translations, dict):
        return {}
    language_map = translations.get(language)
    if not isinstance(language_map, dict):
        return {}
    html_map = language_map.get("html")
    if not isinstance(html_map, dict):
        return {}
    return {str(key): _text(value) for key, value in html_map.items()}


def _html_text_items(html_text: str) -> List[str]:
    parser = _HTMLTextCollector()
    parser.feed(html_text)
    parser.close()
    return parser.items


def _translate_html_text(html_text: str, translations: Dict[str, str]) -> str:
    parser = _HTMLTextTranslator(translations)
    parser.feed(html_text)
    parser.close()
    return parser.html


class _HTMLTextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: List[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not _translatable_html_text(text):
            return
        if text not in self.items:
            self.items.append(text)


class _HTMLTextTranslator(HTMLParser):
    _RAW_TEXT_TAGS = {"script", "style"}

    def __init__(self, translations: Dict[str, str]) -> None:
        super().__init__(convert_charrefs=True)
        self.translations = translations
        self.parts: List[str] = []
        self._raw_text_tag: Optional[str] = None

    @property
    def html(self) -> str:
        return "".join(self.parts)

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.parts.append(self._tag(tag, attrs))
        normalized_tag = tag.lower()
        if normalized_tag in self._RAW_TEXT_TAGS:
            self._raw_text_tag = normalized_tag

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.parts.append(self._tag(tag, attrs, closed=True))

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        if self._raw_text_tag == tag.lower():
            self._raw_text_tag = None

    def handle_data(self, data: str) -> None:
        if self._raw_text_tag:
            self.parts.append(data)
            return
        text = data.strip()
        if text and text in self.translations:
            leading = data[: len(data) - len(data.lstrip())]
            trailing = data[len(data.rstrip()) :]
            self.parts.append(
                f"{leading}{html.escape(self.translations[text])}{trailing}"
            )
            return
        self.parts.append(html.escape(data))

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def _tag(
        self,
        tag: str,
        attrs: List[Tuple[str, Optional[str]]],
        *,
        closed: bool = False,
    ) -> str:
        rendered = [tag]
        for key, value in attrs:
            if value is None:
                rendered.append(key)
            else:
                rendered.append(f'{key}="{html.escape(value, quote=True)}"')
        suffix = " /" if closed else ""
        return f"<{' '.join(rendered)}{suffix}>"


def _translatable_html_text(text: str) -> bool:
    if not text or len(text) > 900:
        return False
    if _identifier_like_text(text):
        return False
    if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", text):
        return False
    if "/" in text and re.search(r"\.(yaml|yml|json|html)\b", text):
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T[\d:-]+Z", text):
        return False
    return True


def _identifier_like_text(text: str) -> bool:
    return bool(
        re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:[-_.][A-Za-z0-9]+)+", text.strip())
    )
