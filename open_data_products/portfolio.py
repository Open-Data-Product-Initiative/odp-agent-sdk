"""Portfolio workspace rendering and explanation helpers."""

from __future__ import annotations

import html
import json
import re
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union

import yaml

from . import __version__
from ._io import load_mapping
from .odpc import load_catalog
from .odpc.catalog import text_value
from .odpg import build_graph_explorer_html, load_graph
from .odps._normalization import (
    ODPS_DATA_QUALITY_DIMENSION_ALIASES,
    ODPS_DATA_QUALITY_DIMENSIONS,
    ODPS_DATA_QUALITY_UNIT_ALIASES,
    ODPS_DATA_QUALITY_UNITS,
    ODPS_SLA_DIMENSION_ALIASES,
    ODPS_SLA_DIMENSIONS,
    ODPS_SLA_UNIT_ALIASES,
    ODPS_SLA_UNITS,
    hours_to_minutes,
)
from .portfolio_sources import (
    changed_source_lanes as _changed_source_lanes,
    collect_source_files as _collect_source_files,
    collect_source_lanes as _collect_source_lanes,
    resolve_source_lane_paths as _resolve_source_lane_paths,
    source_change_warnings as _source_change_warnings,
    source_changes as _source_changes,
    source_hashes as _source_hashes,
    source_hashes_by_lane as _source_hashes_by_lane,
)

DEFAULT_PORTFOLIO_HTML = "index.html"
PORTFOLIO_LOCALIZATION_BATCH_CHARS = 3500
PORTFOLIO_LOCALIZATION_BATCH_ITEMS = 50
PortfolioBuildClient = Callable[[str, str], str]
PortfolioLocalizationClient = Callable[[str, str], str]
ODPC_STATUSES = {"draft", "active", "paused", "completed", "retired"}
ODPC_STATUS_ALIASES = {
    "proposed": "draft",
    "planned": "draft",
    "planning": "draft",
    "development": "active",
    "testing": "active",
    "acceptance": "active",
    "production": "active",
    "sunset": "retired",
    "deprecated": "retired",
    "archived": "retired",
}
ODPS_STATUSES = {
    "announcement",
    "draft",
    "development",
    "testing",
    "acceptance",
    "production",
    "sunset",
    "retired",
}
ODPS_STATUS_ALIASES = {
    "proposed": "draft",
    "planned": "announcement",
    "planning": "announcement",
    "active": "production",
    "completed": "production",
    "paused": "sunset",
    "deprecated": "sunset",
    "archived": "retired",
}
ODPS_VISIBILITIES = {"private", "invitation", "organisation", "dataspace", "public"}
ODPS_VISIBILITY_ALIASES = {
    "internal": "organisation",
    "organization": "organisation",
    "organisation": "organisation",
    "restricted": "invitation",
    "external": "public",
    "open": "public",
}
ODPC_SIGNAL_TYPES = {
    "demand",
    "competitive",
    "market",
    "technology",
    "policy",
    "operational",
    "quality",
    "usage",
    "risk",
    "gap",
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
ODPC_SIGNAL_TYPE_ALIASES = {
    "portfolio": "operational",
    "product": "operational",
    "business": "demand",
    "commercial": "market",
}
ODPG_EDGE_TYPES = {
    "uses",
    "supports",
    "contributesTo",
    "measures",
    "tracks",
    "dependsOn",
    "produces",
    "consumes",
    "governedBy",
    "ownedBy",
    "alignsWith",
    "alignWith",
    "relatedTo",
    "impacts",
    "derivedFrom",
    "exposes",
    "monitors",
    "identifies",
}
ODPG_EDGE_TYPE_ALIASES = {
    "informs": "relatedTo",
    "influences": "impacts",
    "enables": "supports",
    "needs": "uses",
}
ODPS_PRICING_UNITS = {
    "One-time-payment",
    "Pay-per-use",
    "Recurring",
    "Revenue-sharing",
    "Data-volume",
    "Pay-what-you-want",
    "Freemium",
    "Open-data",
    "Value-based",
    "On-request",
    "Trial",
}
ODPS_PRICING_UNIT_ALIASES = {
    "free": "Open-data",
    "open": "Open-data",
    "subscription": "Recurring",
    "monthly": "Recurring",
    "month": "Recurring",
    "usage": "Pay-per-use",
    "request": "Pay-per-use",
}


def build_portfolio(
    workspace: Union[str, Path],
    *,
    objectives: Optional[Union[str, Path]] = None,
    use_cases: Optional[Union[str, Path]] = None,
    signals: Optional[Union[str, Path]] = None,
    products: Optional[Union[str, Path]] = None,
    title: Optional[str] = None,
    client: Optional[PortfolioBuildClient] = None,
    model: str = "qwen2.5",
    run_kind: str = "PortfolioBuild",
    process_all_sources: bool = True,
) -> Dict[str, object]:
    """Build a portfolio workspace from source lanes using an LLM client."""
    root = Path(workspace)
    previous_state = _load_optional_mapping(root / "portfolio-state.yaml")
    snapshot = _snapshot_existing_workspace(root, run_kind)
    lane_paths = _resolve_source_lane_paths(
        previous_state,
        objectives=Path(objectives) if objectives is not None else None,
        use_cases=Path(use_cases) if use_cases is not None else None,
        signals=Path(signals) if signals is not None else None,
        products=Path(products) if products is not None else None,
    )
    lanes = _collect_source_lanes(
        objectives=(
            Path(lane_paths["objectives"]) if "objectives" in lane_paths else None
        ),
        use_cases=Path(lane_paths["useCases"]) if "useCases" in lane_paths else None,
        signals=Path(lane_paths["signals"]) if "signals" in lane_paths else None,
        products=Path(lane_paths["products"]) if "products" in lane_paths else None,
    )
    source_changes = _source_changes(previous_state, lanes)
    has_previous_sources = bool(_source_hashes_by_lane(previous_state))
    process_lanes = (
        lanes
        if process_all_sources or not has_previous_sources
        else _changed_source_lanes(lanes, source_changes)
    )
    if any(process_lanes.values()):
        if client is None:
            raise ValueError("A model client is required to build a portfolio.")
        prompt = render_portfolio_build_prompt(process_lanes)
        raw_plan = client(prompt, model)
        plan = _parse_portfolio_plan_with_repair(raw_plan, client, model)
        plan = _reconcile_plan_identity(plan, previous_state)
        if not process_all_sources and has_previous_sources:
            plan = _merge_portfolio_plans(_plan_from_workspace(root), plan)
    else:
        plan = _plan_from_workspace(root)
    if has_previous_sources:
        plan = _ensure_changed_signal_source_coverage(plan, lanes, source_changes)
    plan = _reconcile_plan_identity(plan, previous_state)
    plan = _normalize_portfolio_plan(plan)
    workspace_title = _resolve_workspace_title(title, previous_state)
    plan = _apply_workspace_title(plan, workspace_title)
    warnings = [str(item) for item in plan.get("warnings", []) if item]
    warnings.extend(_source_change_warnings(source_changes))

    created: List[str] = []
    updated: List[str] = []
    unchanged: List[str] = []
    written = _write_portfolio_artifacts(
        root,
        plan,
        lanes,
        lane_paths=lane_paths,
        title=workspace_title,
    )
    for path, state in written:
        if state == "created":
            created.append(str(path))
        elif state == "updated":
            updated.append(str(path))
        else:
            unchanged.append(str(path))

    render_result = render_portfolio(root)
    validation_results = render_result["validationResults"]
    for path in render_result["created"]:
        created.append(str(path))
    for path in render_result["updated"]:
        updated.append(str(path))
    for path in render_result["unchanged"]:
        unchanged.append(str(path))

    artifact_counts = _artifact_counts(plan)
    source_counts = {name: len(files) for name, files in lanes.items()}
    processed_source_counts = {
        name: len(files) for name, files in process_lanes.items()
    }
    result: Dict[str, object] = {
        "spec": "portfolio",
        "kind": run_kind,
        "workspace": str(root),
        "html": str(root / DEFAULT_PORTFOLIO_HTML),
        "snapshot": str(snapshot) if snapshot is not None else None,
        "sourceCounts": source_counts,
        "processedSourceCounts": processed_source_counts,
        "artifactCounts": artifact_counts,
        "validationResults": validation_results,
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "removed": source_changes["removed"],
        "sourceChanges": source_changes["lanes"],
        "warnings": warnings,
        "unresolvedLinks": [],
        "weakLinks": [],
        "valid": _valid_portfolio(validation_results),
    }
    if snapshot is not None:
        _write_json_report(snapshot / "report.json", result)
        _refresh_portfolio_versions(root)
    return result


def refresh_portfolio(
    workspace: Union[str, Path],
    *,
    objectives: Optional[Union[str, Path]] = None,
    use_cases: Optional[Union[str, Path]] = None,
    signals: Optional[Union[str, Path]] = None,
    products: Optional[Union[str, Path]] = None,
    title: Optional[str] = None,
    client: Optional[PortfolioBuildClient] = None,
    model: str = "qwen2.5",
    all_sources: bool = False,
) -> Dict[str, object]:
    """Refresh an existing portfolio workspace from saved or supplied source lanes."""
    root = Path(workspace)
    state = _load_optional_mapping(root / "portfolio-state.yaml")
    lane_paths = state.get("sourceLanePaths") if isinstance(state, dict) else None
    if not isinstance(lane_paths, dict):
        lane_paths = {}
    return build_portfolio(
        root,
        objectives=objectives or lane_paths.get("objectives"),
        use_cases=use_cases or lane_paths.get("useCases"),
        signals=signals or lane_paths.get("signals"),
        products=products or lane_paths.get("products"),
        title=title,
        client=client,
        model=model,
        run_kind="PortfolioRefresh",
        process_all_sources=all_sources,
    )


def sync_portfolio(workspace: Union[str, Path]) -> Dict[str, object]:
    """Sync edited YAML artifacts into catalog, state, and rendered HTML."""
    root = Path(workspace)
    previous_state = _load_optional_mapping(root / "portfolio-state.yaml")
    snapshot = _snapshot_existing_workspace(root, "PortfolioSync")
    product_writes = _normalize_product_spec_files(root)
    catalog = _catalog_from_fragments(root)
    product_specs = _load_product_specs(root)
    reference_writes = _sync_product_references_from_odps(root, catalog, product_specs)
    written: List[Tuple[Path, str]] = [
        *product_writes,
        *reference_writes,
        _write_yaml(root / "odpc" / "catalog.yaml", catalog),
        _write_yaml(
            root / "portfolio-state.yaml",
            _synced_portfolio_state(previous_state, catalog),
        ),
    ]
    render_result = render_portfolio(root)
    validation_results = render_result["validationResults"]
    created, updated, unchanged = _group_written_paths(written)
    created.extend(str(path) for path in render_result["created"])
    updated.extend(str(path) for path in render_result["updated"])
    unchanged.extend(str(path) for path in render_result["unchanged"])
    data = load_portfolio_workspace(root)
    result: Dict[str, object] = {
        "spec": "portfolio",
        "kind": "PortfolioSync",
        "workspace": str(root),
        "html": str(root / DEFAULT_PORTFOLIO_HTML),
        "snapshot": str(snapshot) if snapshot is not None else None,
        "artifactCounts": _workspace_artifact_counts(data),
        "validationResults": validation_results,
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "warnings": data["warnings"],
        "valid": _valid_portfolio(validation_results),
    }
    if snapshot is not None:
        _write_json_report(snapshot / "report.json", result)
        _refresh_portfolio_versions(root)
    return result


def localize_portfolio(
    workspace: Union[str, Path],
    *,
    languages: Union[str, Iterable[str]],
    client: PortfolioLocalizationClient,
    model: str,
    default_language: str = "en",
) -> Dict[str, object]:
    """Localize portfolio HTML without changing canonical YAML artifacts."""
    root = Path(workspace)
    target_languages = _parse_language_tags(languages)
    default_language = _normalize_language_tag(default_language)
    target_languages = [
        language for language in target_languages if language != default_language
    ]
    if not target_languages:
        raise ValueError("Provide at least one non-default language to localize.")

    i18n = _load_portfolio_i18n(root)
    i18n["defaultLanguage"] = default_language
    i18n["languages"] = _merge_languages(
        [default_language],
        _string_list(i18n.get("languages")),
        target_languages,
    )
    translations = i18n.setdefault("translations", {})
    if not isinstance(translations, dict):
        translations = {}
        i18n["translations"] = translations

    data = load_portfolio_workspace(root)
    data["i18n"] = i18n
    data["language"] = default_language
    source_strings = _html_text_items(render_portfolio_html(data))
    _prune_i18n_html_translations(i18n, set(source_strings))
    warnings: List[str] = list(data["warnings"])

    for language in target_languages:
        language_translations = translations.setdefault(language, {})
        if not isinstance(language_translations, dict):
            language_translations = {}
            translations[language] = language_translations
        html_translations = language_translations.setdefault("html", {})
        if not isinstance(html_translations, dict):
            html_translations = {}
            language_translations["html"] = html_translations
        for chunk in _chunk_localization_strings(source_strings):
            prompt = _render_portfolio_localization_prompt(language, chunk)
            localized, repaired = _parse_portfolio_localization_with_repair(
                client(prompt, model), client, model, language
            )
            if repaired:
                warnings.append(
                    f"Portfolio localization YAML required syntax repair for {language}."
                )
            chunk_strings = set(chunk)
            html_translations.update(
                {
                    key: value
                    for key, value in localized.get("translations", {}).items()
                    if key in chunk_strings
                }
            )

    i18n_path, i18n_state = _write_i18n(root / "portfolio-i18n.yaml", i18n)
    data = load_portfolio_workspace(root)
    html_paths: Dict[str, str] = {}
    written: List[Tuple[Path, str]] = [(i18n_path, i18n_state)]

    for language in [default_language] + target_languages:
        localized_data = dict(data)
        localized_data["language"] = language
        html_text = render_portfolio_html(localized_data)
        if language != default_language:
            html_text = _translate_html_text(
                html_text, _i18n_html_translations(data.get("i18n"), language)
            )
        output = root / _localized_html_filename(language, default_language)
        written.append(_write_text(output, html_text))
        html_paths[language] = str(output)

    created, updated, unchanged = _group_written_paths(written)
    validation_results = _portfolio_validation_results(data)
    return {
        "spec": "portfolio",
        "kind": "PortfolioLocalize",
        "workspace": str(root),
        "defaultLanguage": default_language,
        "languages": target_languages,
        "html": html_paths,
        "i18n": str(root / "portfolio-i18n.yaml"),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "warnings": warnings,
        "validationResults": validation_results,
        "valid": _valid_portfolio(validation_results),
    }


def render_portfolio_build_prompt(lanes: Dict[str, List[Dict[str, str]]]) -> str:
    """Render the internal portfolio build prompt from source lane content."""
    sections = [
        "Create one Open Data Products portfolio plan as YAML.",
        "Return only YAML. Do not include markdown fences, prose, or comments.",
        "",
        "Use this exact top-level shape:",
        "metadata:",
        "  id: generated-portfolio",
        "  name: Portfolio name",
        "  description: Evidence-based portfolio description",
        "businessObjectives:",
        "  - id: OBJ-STABLE-ID",
        "    name:",
        "      en: Objective name",
        "    description:",
        "      en: Objective description grounded in source evidence",
        "    status: proposed",
        "    priority: medium",
        "useCases:",
        "  - id: UC-STABLE-ID",
        "    name:",
        "      en: Use case name",
        "    description:",
        "      en: Use case description grounded in source evidence",
        "    status: proposed",
        "    priority: medium",
        "signals:",
        "  - id: SIG-STABLE-ID",
        "    name:",
        "      en: Signal name",
        "    description:",
        "      en: Signal description grounded in source evidence",
        "    type: market",
        "    confidence: medium",
        "products:",
        "  - productReference:",
        "      id: PR-STABLE-ID",
        "      productID: stable-product-id",
        '      productVersion: "4.1"',
        "      name:",
        "        en: Product name",
        "      description:",
        "        en: Product reference description grounded in source evidence",
        "      status: proposed",
        "      visibility: internal",
        "      type: dataset",
        "    odpsProduct:",
        "      schema: https://opendataproducts.org/v4.1/schema/odps.json",
        '      version: "4.1"',
        "      product:",
        "        details:",
        "          en:",
        "            name: Product name",
        "            productID: stable-product-id",
        "            description: Product specification description grounded in source evidence",
        "            visibility: internal",
        "            status: proposed",
        "            type: dataset",
        "            valueProposition: Business value grounded in source evidence",
        "        productStrategy:",
        "          status: Planned",
        "          objectives:",
        "            - en: Portfolio objective supported by this product.",
        "          contributesToKPI:",
        "            id: KPI-RETENTION",
        "            name: Retention performance",
        "            unit: percentage",
        "            target: 100",
        "          productKPIs:",
        "            - id: KPI-PRODUCT-COVERAGE",
        "              name: Product coverage",
        "              unit: percentage",
        "              target: 95",
        "              calculation: Covered records divided by eligible records.",
        "        dataHolder:",
        "          legalName: Example Data Products Ltd",
        "          contactName: Data Product Owner",
        "          email: data-products@example.com",
        "          businessDomain: Revenue Operations",
        "        dataAccess:",
        "          API:",
        "            name:",
        "              en: API",
        "            description:",
        "              en: Internal access during pilot",
        "            outputPortType: API",
        "            format: JSON",
        "            authenticationMethod: OAuth",
        "        pricingPlans:",
        "          declarative:",
        "            en:",
        "              - name: Internal Starter",
        "                description: Internal use only",
        "                priceCurrency: XXX",
        '                price: "0"',
        "                billingDuration: month",
        "                unit: On-request",
        "                paymentGateway:",
        '                  $ref: "#/product/paymentGateways/default"',
        "                dataQuality:",
        '                  $ref: "#/product/dataQuality/declarative/default"',
        "                SLA:",
        '                  $ref: "#/product/SLA/declarative/default"',
        "                access:",
        '                  $ref: "#/product/dataAccess/API"',
        "              - name: Premium",
        "                description: Higher support and quality package",
        "                priceCurrency: XXX",
        '                price: "0"',
        "                billingDuration: month",
        "                unit: On-request",
        "                paymentGateway:",
        '                  $ref: "#/product/paymentGateways/default"',
        "                dataQuality:",
        '                  $ref: "#/product/dataQuality/declarative/premium"',
        "                SLA:",
        '                  $ref: "#/product/SLA/declarative/premium"',
        "                access:",
        '                  $ref: "#/product/dataAccess/API"',
        "        SLA:",
        "          declarative:",
        "            default:",
        "              name:",
        "                en: The Basic SLA",
        "              description:",
        "                en: The basic SLA package.",
        "              dimensions:",
        "                - dimension: uptime",
        "                  displaytitle:",
        "                    en: Uptime",
        "                  objective: 90",
        "                  unit: percent",
        "                  weight: 50",
        "                - dimension: responseTime",
        "                  objective: 200",
        "                  unit: milliseconds",
        "                  weight: 30",
        "                - dimension: updateFrequency",
        "                  objective: 30",
        "                  unit: minutes",
        "                  weight: 20",
        "            premium:",
        "              name:",
        "                en: The Premium SLA",
        "              description:",
        "                en: The Premium SLA package.",
        "              dimensions:",
        "                - dimension: uptime",
        "                  displaytitle:",
        "                    en: Uptime",
        "                  objective: 99",
        "                  unit: percent",
        "                  weight: 70",
        "                - dimension: responseTime",
        "                  objective: 100",
        "                  unit: milliseconds",
        "                  weight: 20",
        "                - dimension: updateFrequency",
        "                  objective: 5",
        "                  unit: minutes",
        "                  weight: 10",
        "        dataQuality:",
        "          declarative:",
        "            default:",
        "              description: The basic data quality package.",
        "              dimensions:",
        "                - dimension: completeness",
        "                  displayTitle: Completeness",
        "                  objective: 95",
        "                  unit: percentage",
        "                  weight: 50",
        "                  description: Required fields are populated.",
        "            premium:",
        "              description: The premium data quality package.",
        "              dimensions:",
        "                - dimension: completeness",
        "                  displayTitle: Completeness",
        "                  objective: 98",
        "                  unit: percentage",
        "                  weight: 60",
        "                  description: Required fields are populated.",
        "                - dimension: timeliness",
        "                  objective: 95",
        "                  unit: percentage",
        "                  weight: 40",
        "                  description: Records are updated within the expected window.",
        "        paymentGateways:",
        "          default:",
        "            description:",
        "              en: Internal chargeback or manual billing process.",
        "            type: Custom",
        "            version: v1",
        "        license:",
        "          scope:",
        "            definition: Internal use for evidence-supported workflows.",
        "            restrictions: No resale or external redistribution.",
        "            geographicalArea:",
        "              - EU",
        "            permanent: false",
        "            exclusive: false",
        "            rights:",
        "              - Display",
        "              - Distribution",
        "              - Adaptation",
        "          termination:",
        "            noticePeriod: 30",
        "            terminationConditions: Access ends when approved use ends.",
        "          governance:",
        "            ownership: Business owner governs use; data platform governs operations.",
        "            audit: Access and usage are reviewed periodically.",
        "graphEdges:",
        "  - source: UC-STABLE-ID",
        "    target: PR-STABLE-ID",
        "    type: uses",
        "    confidence: medium",
        "warnings:",
        "  - Evidence gap or weak-link note",
        "",
        "Linking rules:",
        "- Generate stable, deterministic IDs from names and concepts.",
        "- productReference.productID must match odpsProduct.product.details.en.productID.",
        '- productModel.$ref must be "../odps/products/<productID>.yaml"; the SDK will add it to productReference.',
        "- Graph edge source and target values must use generated stable IDs from objectives, use cases, signals, or product references.",
        "- Prefer linking use cases to product references when the evidence supports the relationship.",
        "- Do not invent confident facts. If evidence is missing, use warnings and lower confidence.",
        "- Keep all values schema-shaped YAML mappings, not narrative paragraphs at the root.",
        "- Use only facts supported by the source lanes. Draft minimal viable ODPS details when product evidence is sparse.",
        "",
        "ODPS v4.1 product component rules:",
        "- dataAccess must be a named mapping of access method objects, such as dataAccess.API. Use outputPortType with this exact casing.",
        "- pricingPlans.declarative.en must be a list of pricing plan objects with name, priceCurrency, price, billingDuration, and unit.",
        "- SLA must be an object, never a list. Use SLA.declarative as a named mapping such as default and premium.",
        "- Each SLA declarative profile must contain dimensions with dimension, objective, and unit.",
        "- dataQuality must be an object, never a list. Use dataQuality.declarative as a named mapping such as default and premium.",
        "- Allowed dataQuality dimension names are accuracy, completeness, conformity, consistency, coverage, timeliness, validity, and uniqueness.",
        "- Map reconciliation checks to consistency. Keep the reconciliation detail in displayTitle or description, not as dimension: reconciliation.",
        "- Pricing plan references must use named paths such as #/product/SLA/declarative/default, #/product/dataQuality/declarative/default, and #/product/dataAccess/API.",
        "- paymentGateway refs must use named paths such as #/product/paymentGateways/default.",
        "- Never use array-index reference paths such as #/product/SLA/0 or #/product/dataQuality/declarative/0.",
        "- license uses scope, termination, and governance. Do not emit legacy license fields.",
        "- Do not place SLA inside product.details.en. SLA belongs at product.SLA.",
        "- Do not emit pricing. Use pricingPlans.",
        "- Do not emit dataOps. If operational evidence is useful, describe it in warnings or an optional x-* extension.",
        "- x-* extension fields are allowed because they are ODPS extensions, but they must not replace schema fields like SLA, dataQuality, dataAccess, or pricingPlans.",
        "- If evidence is missing for a schema component, emit a minimal pending schema-shaped component and add a warning.",
    ]
    for lane_name, files in lanes.items():
        sections.append(f"\n# Source lane: {lane_name}")
        if not files:
            sections.append("(no files)")
            continue
        for source in files:
            sections.append(f"\n## {source['path']}\n{source['text']}")
    return "\n".join(sections)


def _parse_portfolio_plan_with_repair(
    raw_output: str,
    client: PortfolioBuildClient,
    model: str,
) -> Dict[str, Any]:
    try:
        return parse_portfolio_plan(raw_output)
    except ValueError as original_error:
        repair_prompt = _render_portfolio_plan_repair_prompt(
            raw_output, str(original_error)
        )
        repaired_output = client(repair_prompt, model)
        try:
            plan = parse_portfolio_plan(repaired_output)
        except ValueError as repair_error:
            raise ValueError(
                f"{original_error}\nRepair attempt also failed: {repair_error}"
            ) from repair_error
        warnings = plan.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append("Portfolio plan YAML required syntax repair.")
        return plan


def _render_portfolio_plan_repair_prompt(raw_output: str, parser_error: str) -> str:
    return "\n".join(
        [
            "# Repair Portfolio Plan YAML",
            "Repair one Open Data Products portfolio plan YAML document.",
            "Return only YAML. Do not include markdown fences, prose, or comments.",
            "Preserve the generated facts, IDs, links, warnings, and artifact lists.",
            "Fix only YAML syntax, indentation, incomplete keys, and malformed mappings.",
            "Do not add new unsupported facts. If a broken value cannot be recovered,",
            "drop that broken field and preserve the rest of the artifact.",
            "",
            "Parser error:",
            parser_error,
            "",
            "Malformed portfolio plan YAML:",
            raw_output,
        ]
    )


def parse_portfolio_plan(raw_output: str) -> Dict[str, Any]:
    """Parse a model-generated portfolio plan YAML mapping."""
    text = _extract_yaml_text(raw_output)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(
            "Portfolio plan YAML could not be parsed. The model response may "
            "have been truncated; increase provider maxTokens or rerun the "
            f"command. Parser error: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError("Portfolio plan must contain a YAML object at the root")
    return data


def parse_portfolio_localization(raw_output: str) -> Dict[str, Any]:
    """Parse a model-generated portfolio localization YAML mapping."""
    text = _extract_yaml_text(raw_output)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(
            f"Portfolio localization YAML could not be parsed: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(
            "Portfolio localization must contain a YAML object at the root"
        )
    translations = data.get("translations")
    if not isinstance(translations, dict):
        data["translations"] = {}
        return data
    data["translations"] = {
        str(key): _text(value)
        for key, value in translations.items()
        if isinstance(key, str) and _text(value)
    }
    return data


def _parse_portfolio_localization_with_repair(
    raw_output: str,
    client: PortfolioLocalizationClient,
    model: str,
    language: str,
) -> Tuple[Dict[str, Any], bool]:
    try:
        return parse_portfolio_localization(raw_output), False
    except ValueError as original_error:
        repair_prompt = _render_portfolio_localization_repair_prompt(
            language, raw_output, str(original_error)
        )
        repaired_output = client(repair_prompt, model)
        try:
            return parse_portfolio_localization(repaired_output), True
        except ValueError as repair_error:
            raise ValueError(
                f"{original_error}\nRepair attempt also failed: {repair_error}"
            ) from repair_error


def _render_portfolio_localization_repair_prompt(
    language: str,
    raw_output: str,
    parser_error: str,
) -> str:
    return "\n".join(
        [
            "# Repair Portfolio Localization YAML",
            f"Target language: {language}",
            "Repair one portfolio localization YAML document.",
            "Return only YAML. Do not include markdown fences, prose, or comments.",
            "Preserve the translation keys and translated values.",
            "Fix only YAML syntax, quoting, block scalars, indentation, and malformed mappings.",
            "Use this shape:",
            f"language: {language}",
            "translations:",
            "  Source text: Translated text",
            "",
            "Parser error:",
            parser_error,
            "",
            "Malformed localization YAML:",
            raw_output,
        ]
    )


def _render_portfolio_localization_prompt(
    language: str, source_strings: List[str]
) -> str:
    lines = [
        "# Localize Portfolio HTML",
        f"Target language: {language}",
        "Translate the human-facing strings from one static portfolio HTML page.",
        "Return only YAML. Do not include markdown fences, prose, or comments.",
        "Use this exact shape:",
        f"language: {language}",
        "translations:",
        '  "Source text": "Translated text"',
        "",
        "Rules:",
        "- Do not translate IDs, file paths, URLs, YAML keys, or enum values.",
        "- Keep product IDs, graph node IDs, version IDs, and artifact paths unchanged.",
        "- Preserve numbers and units unless the target language requires normal spacing.",
        "- Keep translations concise enough for the existing static HTML layout.",
        "- Quote translation keys and values, or use block scalars for long values.",
        "- Translation values often contain colons; never emit an unquoted value with a colon.",
        "",
        "Strings:",
    ]
    for text in source_strings:
        lines.append(f"- {yaml.safe_dump(text, allow_unicode=True).strip()}")
    return "\n".join(lines)


def _chunk_localization_strings(
    source_strings: List[str],
    *,
    max_chars: int = PORTFOLIO_LOCALIZATION_BATCH_CHARS,
    max_items: int = PORTFOLIO_LOCALIZATION_BATCH_ITEMS,
) -> List[List[str]]:
    chunks: List[List[str]] = []
    current: List[str] = []
    current_chars = 0
    for text in source_strings:
        item_chars = len(text)
        if current and (
            len(current) >= max_items or current_chars + item_chars > max_chars
        ):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(text)
        current_chars += item_chars
    if current:
        chunks.append(current)
    return chunks


def _resolve_workspace_title(
    title: Optional[str],
    previous_state: Dict[str, Any],
) -> Optional[str]:
    explicit = _text(title)
    if explicit:
        return explicit
    saved = previous_state.get("title") if isinstance(previous_state, dict) else None
    saved_title = _text(saved)
    return saved_title or None


def _apply_workspace_title(
    plan: Dict[str, Any],
    title: Optional[str],
) -> Dict[str, Any]:
    if not title:
        return plan
    titled = deepcopy(plan)
    metadata = titled.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        titled["metadata"] = metadata
    metadata["name"] = title
    return titled


def _write_portfolio_artifacts(
    root: Path,
    plan: Dict[str, Any],
    lanes: Dict[str, List[Dict[str, str]]],
    lane_paths: Optional[Dict[str, str]] = None,
    title: Optional[str] = None,
) -> List[Tuple[Path, str]]:
    written: List[Tuple[Path, str]] = []
    written.append(_write_yaml(root / "portfolio.yaml", _portfolio_map(plan, lanes)))
    written.append(
        _write_yaml(
            root / "portfolio-state.yaml",
            _portfolio_state(plan, lanes, lane_paths or {}, title),
        )
    )

    fragments_dir = root / "odpc" / "fragments"
    catalog = _catalog_document(plan)
    for item in _list(plan, "businessObjectives"):
        written.append(
            _write_yaml(
                fragments_dir / f"business_objective_{_file_id(item)}.yaml",
                {"businessObjective": item},
            )
        )
    for item in _list(plan, "useCases"):
        written.append(
            _write_yaml(
                fragments_dir / f"use_case_{_file_id(item)}.yaml",
                {"useCase": item},
            )
        )
    for item in _list(plan, "signals"):
        written.append(
            _write_yaml(
                fragments_dir / f"signal_{_file_id(item)}.yaml",
                {"signal": item},
            )
        )

    product_specs = []
    product_references = []
    for product in _list(plan, "products"):
        reference = product.get("productReference")
        odps_product = product.get("odpsProduct")
        if not isinstance(reference, dict) or not isinstance(odps_product, dict):
            continue
        product_id = _text(reference.get("productID") or reference.get("id"))
        product_path = Path("odps") / "products" / f"{_path_id(product_id)}.yaml"
        reference = dict(reference)
        reference["productModel"] = {
            "standard": "ODPS",
            "version": str(odps_product.get("version") or "4.1"),
            "format": "yaml",
            "$ref": f"../{product_path.as_posix()}",
        }
        product_references.append(reference)
        product_specs.append(odps_product)
        written.append(
            _write_yaml(
                fragments_dir / f"product_reference_{_file_id(reference)}.yaml",
                {"productReference": reference},
            )
        )
        written.append(_write_yaml(root / product_path, odps_product))

    if product_references:
        catalog["catalog"]["productReferences"] = product_references
    written.append(_write_yaml(root / "odpc" / "catalog.yaml", catalog))
    written.append(_write_yaml(root / "odpg" / "graph.yaml", _graph_document(plan)))
    return written


def _write_yaml(path: Path, document: Dict[str, Any]) -> Tuple[Path, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(document, sort_keys=False, allow_unicode=False)
    existed = path.exists()
    previous = path.read_text(encoding="utf-8") if existed else None
    path.write_text(content, encoding="utf-8")
    state = "unchanged" if previous == content else "updated" if existed else "created"
    return path, state


def _write_i18n(path: Path, document: Dict[str, Any]) -> Tuple[Path, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
    existed = path.exists()
    previous = path.read_text(encoding="utf-8") if existed else None
    path.write_text(content, encoding="utf-8")
    state = "unchanged" if previous == content else "updated" if existed else "created"
    return path, state


def _write_text(path: Path, content: str) -> Tuple[Path, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    previous = path.read_text(encoding="utf-8") if existed else None
    path.write_text(content, encoding="utf-8")
    state = "unchanged" if previous == content else "updated" if existed else "created"
    return path, state


def _group_written_paths(
    written: List[Tuple[Path, str]],
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


def _write_json_report(path: Path, report: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _snapshot_existing_workspace(root: Path, run_kind: str) -> Optional[Path]:
    html_path = root / DEFAULT_PORTFOLIO_HTML
    if not html_path.exists():
        return None
    snapshot_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    snapshot = root / "versions" / snapshot_id
    suffix = 1
    while snapshot.exists():
        snapshot = root / "versions" / f"{snapshot_id}-{suffix}"
        suffix += 1
    snapshot.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html_path, snapshot / DEFAULT_PORTFOLIO_HTML)
    portfolio_path = root / "portfolio.yaml"
    if portfolio_path.exists():
        shutil.copy2(portfolio_path, snapshot / "portfolio.yaml")
    _write_json_report(
        snapshot / "report.json",
        {
            "spec": "portfolio",
            "kind": run_kind,
            "snapshot": str(snapshot),
            "html": str(snapshot / DEFAULT_PORTFOLIO_HTML),
        },
    )
    return snapshot


def _refresh_portfolio_versions(root: Path) -> None:
    portfolio_path = root / "portfolio.yaml"
    portfolio = _load_optional_mapping(portfolio_path)
    versions = _portfolio_versions(root, {})
    if not versions:
        return
    portfolio["versions"] = versions
    _write_yaml(portfolio_path, portfolio)
    render_portfolio(root)


def _portfolio_map(
    plan: Dict[str, Any],
    lanes: Dict[str, List[Dict[str, str]]],
) -> Dict[str, Any]:
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    return {
        "metadata": {
            "id": metadata.get("id", "generated-portfolio"),
            "name": metadata.get("name", "Generated Portfolio"),
            "description": metadata.get(
                "description", "Generated from portfolio source lanes."
            ),
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sdkVersion": __version__,
        },
        "sources": {name: {"count": len(files)} for name, files in lanes.items()},
        "warnings": [str(item) for item in plan.get("warnings", []) if item],
    }


def _portfolio_state(
    plan: Dict[str, Any],
    lanes: Dict[str, List[Dict[str, str]]],
    lane_paths: Dict[str, str],
    title: Optional[str],
) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "version": 1,
        "sourceLanePaths": dict(lane_paths),
        "sources": {
            name: [
                {
                    "path": source["path"],
                    "sha256": source["sha256"],
                }
                for source in files
            ]
            for name, files in lanes.items()
        },
        "identityRegistry": _identity_registry(plan),
    }
    if title:
        state["title"] = title
    return state


def _synced_portfolio_state(
    previous_state: Dict[str, Any],
    catalog: Dict[str, Any],
) -> Dict[str, Any]:
    state = dict(previous_state) if isinstance(previous_state, dict) else {}
    state["version"] = state.get("version", 1)
    state.setdefault("sourceLanePaths", {})
    state.setdefault("sources", {})
    state["identityRegistry"] = _identity_registry(_plan_from_catalog(catalog))
    return state


def _reconcile_plan_identity(
    plan: Dict[str, Any],
    previous_state: Dict[str, Any],
) -> Dict[str, Any]:
    registry = previous_state.get("identityRegistry")
    if not isinstance(registry, dict):
        return plan

    reconciled = deepcopy(plan)
    id_remap: Dict[str, str] = {}
    for collection, registry_key in (
        ("businessObjectives", "businessObjectives"),
        ("useCases", "useCases"),
        ("signals", "signals"),
    ):
        previous_by_fingerprint = _registry_by_fingerprint(registry.get(registry_key))
        for item in _list(reconciled, collection):
            previous = previous_by_fingerprint.get(_artifact_fingerprint(item))
            if not previous:
                continue
            proposed_id = _text(item.get("id"))
            stable_id = _text(previous.get("id"))
            if proposed_id and stable_id and proposed_id != stable_id:
                id_remap[proposed_id] = stable_id
                item["id"] = stable_id

    previous_products = _registry_by_fingerprint(registry.get("products"))
    for product in _list(reconciled, "products"):
        reference = product.get("productReference")
        odps_product = product.get("odpsProduct")
        if not isinstance(reference, dict):
            continue
        previous = previous_products.get(_artifact_fingerprint(reference))
        if not previous:
            continue
        proposed_id = _text(reference.get("id"))
        stable_id = _text(previous.get("id"))
        if proposed_id and stable_id and proposed_id != stable_id:
            id_remap[proposed_id] = stable_id
            reference["id"] = stable_id
        proposed_product_id = _text(reference.get("productID"))
        stable_product_id = _text(previous.get("productID"))
        if proposed_product_id and stable_product_id:
            if proposed_product_id != stable_product_id:
                id_remap[proposed_product_id] = stable_product_id
            reference["productID"] = stable_product_id
            _set_odps_product_id(odps_product, stable_product_id)

    for edge in _list(reconciled, "graphEdges"):
        for key in ("source", "target"):
            value = _text(edge.get(key))
            if value in id_remap:
                edge[key] = id_remap[value]

    return reconciled


def _identity_registry(plan: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    return {
        "businessObjectives": [
            _registry_entry(item, "id") for item in _list(plan, "businessObjectives")
        ],
        "useCases": [_registry_entry(item, "id") for item in _list(plan, "useCases")],
        "signals": [_registry_entry(item, "id") for item in _list(plan, "signals")],
        "products": [_product_registry_entry(item) for item in _list(plan, "products")],
    }


def _registry_entry(item: Dict[str, Any], id_key: str) -> Dict[str, str]:
    return {
        "fingerprint": _artifact_fingerprint(item),
        id_key: _text(item.get(id_key)),
    }


def _product_registry_entry(product: Dict[str, Any]) -> Dict[str, str]:
    reference = product.get("productReference")
    if not isinstance(reference, dict):
        reference = {}
    return {
        "fingerprint": _artifact_fingerprint(reference),
        "id": _text(reference.get("id")),
        "productID": _text(reference.get("productID")),
    }


def _registry_by_fingerprint(value: Any) -> Dict[str, Dict[str, str]]:
    if not isinstance(value, list):
        return {}
    entries = {}
    for item in value:
        if isinstance(item, dict):
            fingerprint = _text(item.get("fingerprint"))
            if fingerprint:
                entries[fingerprint] = {str(key): str(val) for key, val in item.items()}
    return entries


def _artifact_fingerprint(item: Dict[str, Any]) -> str:
    return _normalize_identity_text(_text(item.get("name") or item.get("id")))


def _normalize_identity_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _set_odps_product_id(value: Any, product_id: str) -> None:
    if not isinstance(value, dict):
        return
    product = value.get("product")
    if not isinstance(product, dict):
        return
    details = product.get("details")
    if isinstance(details, dict):
        english = details.get("en")
        if isinstance(english, dict):
            english["productID"] = product_id
            return
    product["productID"] = product_id


def _normalize_portfolio_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deepcopy(plan)
    for item in _list(normalized, "businessObjectives"):
        item["status"] = _normalize_enum(
            item.get("status"), ODPC_STATUSES, ODPC_STATUS_ALIASES, "draft"
        )
    for item in _list(normalized, "useCases"):
        item["status"] = _normalize_enum(
            item.get("status"), ODPC_STATUSES, ODPC_STATUS_ALIASES, "draft"
        )
    for item in _list(normalized, "signals"):
        item["type"] = _normalize_enum(
            item.get("type"), ODPC_SIGNAL_TYPES, ODPC_SIGNAL_TYPE_ALIASES, "operational"
        )
        if not isinstance(item.get("source"), dict):
            item["source"] = {
                "origin": "internal",
                "method": "generated portfolio source lanes",
            }
        if not _text(item.get("observedAt")):
            item["observedAt"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

    for product in _list(normalized, "products"):
        reference = product.get("productReference")
        if isinstance(reference, dict):
            reference["status"] = _normalize_enum(
                reference.get("status"), ODPC_STATUSES, ODPC_STATUS_ALIASES, "draft"
            )
        _normalize_odps_product(product.get("odpsProduct"))

    for edge in _list(normalized, "graphEdges"):
        source = _text(edge.get("source") or edge.get("from"))
        target = _text(edge.get("target") or edge.get("to"))
        edge_type = _normalize_enum(
            edge.get("type"), ODPG_EDGE_TYPES, ODPG_EDGE_TYPE_ALIASES, "relatedTo"
        )
        confidence = _normalize_enum(
            edge.get("confidence"), {"high", "medium", "low"}, {}, "medium"
        )
        edge.clear()
        edge["source"] = source
        edge["target"] = target
        edge["type"] = edge_type
        edge["confidence"] = confidence

    return normalized


def _normalize_odps_product(value: Any) -> None:
    if not isinstance(value, dict):
        return
    product = value.get("product")
    if isinstance(product, dict):
        _normalize_odps_generated_sections(product)
        _normalize_odps_pricing_plans(product)
        _normalize_odps_data_access(product)
        _normalize_odps_license(product.get("license"))
    details = _odps_details_mapping(value)
    if details is None:
        return
    details["status"] = _normalize_enum(
        details.get("status"), ODPS_STATUSES, ODPS_STATUS_ALIASES, "draft"
    )
    details["visibility"] = _normalize_enum(
        details.get("visibility"),
        ODPS_VISIBILITIES,
        ODPS_VISIBILITY_ALIASES,
        "private",
    )


def _odps_details_mapping(value: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    product = value.get("product")
    if not isinstance(product, dict):
        return None
    details = product.get("details")
    if isinstance(details, dict):
        english = details.get("en")
        if isinstance(english, dict):
            return english
    return product if isinstance(product, dict) else None


def _normalize_odps_generated_sections(product: Dict[str, Any]) -> None:
    data_ops = product.pop("dataOps", None)
    if data_ops is not None:
        data_ops = _normalize_loose_data_ops(data_ops)
        if data_ops is not None:
            product["x-dataOps"] = data_ops

    details = product.get("details")
    detail_sla = None
    if isinstance(details, dict):
        english = details.get("en")
        if isinstance(english, dict):
            _normalize_odps_detail_use_cases(english)
            detail_sla = english.pop("SLA", None)

    sla = product.get("SLA")
    if isinstance(sla, list):
        normalized_sla = _normalize_sla_list(sla)
        if isinstance(detail_sla, dict):
            _merge_sla_dimensions(normalized_sla, _sla_from_loose_details(detail_sla))
        if isinstance(data_ops, dict):
            _merge_sla_dimensions(
                normalized_sla, _sla_from_data_ops_update_frequency(data_ops)
            )
        product["SLA"] = normalized_sla
    elif isinstance(sla, dict):
        normalized_sla = _normalize_loose_sla(sla)
        if isinstance(detail_sla, dict):
            _merge_sla_dimensions(normalized_sla, _sla_from_loose_details(detail_sla))
        if isinstance(data_ops, dict):
            _merge_sla_dimensions(
                normalized_sla, _sla_from_data_ops_update_frequency(data_ops)
            )
        product["SLA"] = normalized_sla
    elif isinstance(detail_sla, dict):
        product["SLA"] = _sla_from_loose_details(detail_sla)
        if isinstance(data_ops, dict):
            _merge_sla_dimensions(
                product["SLA"], _sla_from_data_ops_update_frequency(data_ops)
            )
    elif isinstance(data_ops, dict):
        data_ops_sla = _sla_from_data_ops_update_frequency(data_ops)
        if _first_named_profile(data_ops_sla.get("declarative")) is not None:
            product["SLA"] = data_ops_sla

    data_quality = product.get("dataQuality")
    if isinstance(data_quality, list):
        product["dataQuality"] = _normalize_data_quality_list(data_quality)
    elif isinstance(data_quality, dict):
        product["dataQuality"] = _normalize_loose_data_quality(data_quality)


def _normalize_loose_data_ops(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, list):
        merged: Dict[str, Any] = {}
        for item in value:
            if isinstance(item, dict):
                merged.update(item)
        value = merged
    if not isinstance(value, dict):
        return None
    normalized = dict(value)
    for key in ("infrastructure", "format", "dataQuality", "updateFrequency"):
        item = normalized.get(key)
        if isinstance(item, list):
            first = next((entry for entry in item if isinstance(entry, dict)), None)
            if first is not None:
                normalized[key] = first
    return normalized


def _normalize_odps_detail_use_cases(details: Dict[str, Any]) -> None:
    use_cases = details.get("useCases")
    if isinstance(use_cases, str):
        text = use_cases.strip()
        details["useCases"] = (
            [{"useCase": {"useCaseTitle": text, "useCaseDescription": text}}]
            if text
            else []
        )
        return
    if isinstance(use_cases, list):
        normalized = []
        for item in use_cases:
            if isinstance(item, str) and item.strip():
                normalized.append(
                    {
                        "useCase": {
                            "useCaseTitle": item.strip(),
                            "useCaseDescription": item.strip(),
                        }
                    }
                )
            elif isinstance(item, dict):
                normalized.append(item)
        details["useCases"] = normalized


def _normalize_odps_license(license_data: Any) -> None:
    if not isinstance(license_data, dict):
        return
    scope = license_data.get("scope")
    if isinstance(scope, dict):
        _truncate_mapping_strings(
            scope,
            {
                "definition": 512,
                "restrictions": 255,
            },
        )
    termination = license_data.get("termination")
    if isinstance(termination, dict):
        _truncate_mapping_strings(
            termination,
            {
                "terminationConditions": 512,
                "continuityConditions": 512,
            },
        )
    governance = license_data.get("governance")
    if isinstance(governance, dict):
        _truncate_mapping_strings(
            governance,
            {
                "ownership": 512,
                "audit": 512,
                "warranties": 512,
                "damages": 512,
                "confidentiality": 512,
                "applicableLaws": 512,
                "forceMajeure": 512,
            },
        )


def _truncate_mapping_strings(mapping: Dict[str, Any], limits: Dict[str, int]) -> None:
    for key, limit in limits.items():
        value = mapping.get(key)
        if isinstance(value, str) and len(value) > limit:
            mapping[key] = _truncate_text(value, limit)


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3].rstrip() + "..."


def _normalize_loose_sla(sla: Dict[str, Any]) -> Dict[str, Any]:
    declarative = sla.get("declarative")
    if isinstance(declarative, dict):
        normalized = {"declarative": {}}
        for key, profile in declarative.items():
            normalized["declarative"][_path_id(str(key)) or "default"] = (
                _normalize_sla_profile(profile, str(key))
            )
        return normalized
    if isinstance(declarative, list):
        return {"declarative": _named_profiles_from_list(declarative, "default")}
    description = _text(sla.get("description"))
    normalized = _sla_from_loose_details(sla)
    profile = normalized["declarative"]["default"]
    if description:
        profile["description"] = {"en": description}
    return normalized


def _normalize_sla_list(items: List[Any]) -> Dict[str, Any]:
    profiles = [
        profile
        for item in items
        if isinstance(item, dict)
        for profile in [_sla_profile_from_loose_mapping(item)]
        if profile is not None
    ]
    if not profiles:
        profiles = [{"name": {"en": "Default SLA"}, "dimensions": []}]
    return {"declarative": _named_profiles_from_list(profiles, "default")}


def _normalize_sla_profile(value: Any, fallback_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "name": {"en": _title_from_text(_text(value) or fallback_name or "SLA")},
            "dimensions": [],
        }
    if isinstance(value.get("dimensions"), list):
        profile = dict(value)
        profile["dimensions"] = [
            _normalize_sla_dimension(dimension)
            for dimension in value["dimensions"]
            if isinstance(dimension, dict)
        ]
        if not isinstance(profile.get("name"), dict):
            profile["name"] = {
                "en": _text(profile.get("name"), _title_from_text(fallback_name))
            }
        return profile
    profile = _sla_profile_from_loose_mapping(value)
    if profile is None:
        return {"name": {"en": _title_from_text(fallback_name)}, "dimensions": []}
    return profile


def _named_profiles_from_list(
    profiles: List[Dict[str, Any]], first_key: str
) -> Dict[str, Dict[str, Any]]:
    named: Dict[str, Dict[str, Any]] = {}
    for index, profile in enumerate(profiles):
        key = first_key if index == 0 else _profile_key(profile, index)
        while key in named:
            key = f"{key}-{index + 1}"
        named[key] = profile
    return named


def _profile_key(profile: Dict[str, Any], index: int) -> str:
    name = _text(profile.get("id") or profile.get("key"))
    if not name:
        name = _text(profile.get("name"))
    normalized = _path_id(name)
    if normalized in {"", "default-sla", "default-data-quality"}:
        return f"profile-{index + 1}"
    if "premium" in normalized:
        return "premium"
    return normalized or f"profile-{index + 1}"


def _sla_profile_from_loose_mapping(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if isinstance(item.get("dimensions"), list):
        profile = dict(item)
        profile["dimensions"] = [
            _normalize_sla_dimension(dimension)
            for dimension in item["dimensions"]
            if isinstance(dimension, dict)
        ]
        if not isinstance(profile.get("name"), dict):
            profile["name"] = {"en": _text(profile.get("name"), "Default SLA")}
        return profile

    language, content = _language_content(item)
    source = content if isinstance(content, dict) else item
    description = _text(source.get("description"))
    profile: Dict[str, Any] = {
        "name": {"en": _text(source.get("name"), "Default SLA")},
        "dimensions": _sla_dimensions_from_loose_mapping(source),
    }
    if description:
        profile["description"] = {language: description}
    return profile


def _language_content(item: Dict[str, Any]) -> Tuple[str, Any]:
    for key, value in item.items():
        if isinstance(key, str) and len(key) == 2 and isinstance(value, dict):
            return key, value
    return "en", item


def _sla_dimensions_from_loose_mapping(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    dimensions = []
    for key, value in item.items():
        if key in {"name", "description", "dimensions"}:
            continue
        dimension = key
        if key == "availability":
            dimension = "uptime"
        if dimension not in ODPS_SLA_DIMENSIONS:
            continue
        objective = _text(value)
        if objective:
            dimensions.append(
                {
                    "dimension": dimension,
                    "objective": objective,
                    "unit": "null",
                }
            )
    if not dimensions and _text(item.get("objective")):
        dimensions.append(
            {
                "dimension": "updateFrequency",
                "objective": _text(item.get("objective")),
                "unit": "null",
            }
        )
    return dimensions


def _normalize_sla_dimension(dimension: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(dimension)
    raw_dimension = _text(normalized.get("dimension") or normalized.get("name"))
    raw_unit = _text(normalized.get("unit"))
    normalized["dimension"] = _normalize_enum(
        raw_dimension,
        ODPS_SLA_DIMENSIONS,
        ODPS_SLA_DIMENSION_ALIASES,
        "updateFrequency",
    )
    if "objective" not in normalized:
        normalized["objective"] = _text(normalized.get("target"), "pending")
    if raw_unit.casefold() in {"hour", "hours"}:
        normalized["objective"] = hours_to_minutes(normalized.get("objective"))
    if not _text(normalized.get("unit")):
        normalized["unit"] = "null"
    else:
        normalized["unit"] = _normalize_enum(
            normalized.get("unit"), ODPS_SLA_UNITS, ODPS_SLA_UNIT_ALIASES, "null"
        )
    return normalized


def _sla_from_data_ops_update_frequency(data_ops: Dict[str, Any]) -> Dict[str, Any]:
    update_frequency = data_ops.get("updateFrequency")
    if not isinstance(update_frequency, dict):
        return {"declarative": []}
    objective = update_frequency.get("value")
    unit = _normalize_enum(
        update_frequency.get("unit"), ODPS_SLA_UNITS, ODPS_SLA_UNIT_ALIASES, "days"
    )
    if objective is None or objective == "":
        return {"declarative": []}
    return {
        "declarative": {
            "default": {
                "name": {"en": "Default SLA"},
                "dimensions": [
                    {
                        "dimension": "updateFrequency",
                        "objective": objective,
                        "unit": unit,
                    }
                ],
            }
        }
    }


def _merge_sla_dimensions(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    target_profile = _first_named_profile(target.get("declarative"))
    source_profile = _first_named_profile(source.get("declarative"))
    if target_profile is None or source_profile is None:
        return
    target_dimensions = target_profile.setdefault("dimensions", [])
    if not isinstance(target_dimensions, list):
        target_profile["dimensions"] = []
        target_dimensions = target_profile["dimensions"]
    existing = {
        _text(item.get("dimension"))
        for item in target_dimensions
        if isinstance(item, dict)
    }
    for item in source_profile.get("dimensions", []):
        if not isinstance(item, dict):
            continue
        dimension = _text(item.get("dimension"))
        if dimension and dimension not in existing:
            target_dimensions.append(item)
            existing.add(dimension)


def _first_named_profile(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        for profile in value.values():
            if isinstance(profile, dict):
                return profile
    if isinstance(value, list):
        for profile in value:
            if isinstance(profile, dict):
                return profile
    return None


def _normalize_loose_data_quality(data_quality: Dict[str, Any]) -> Dict[str, Any]:
    declarative = data_quality.get("declarative")
    if isinstance(declarative, dict):
        normalized = {"declarative": {}}
        for key, profile in declarative.items():
            if isinstance(profile, dict):
                normalized["declarative"][_path_id(str(key)) or "default"] = (
                    _normalize_data_quality_profile(profile)
                )
        return normalized
    if isinstance(declarative, list):
        return {
            "declarative": _named_profiles_from_list(
                [_normalize_data_quality_profile(item) for item in declarative],
                "default",
            )
        }
    description = _text(data_quality.get("policyDescription"))
    if not description:
        description = _text(data_quality.get("description"))
    return {
        "declarative": {
            "default": {
                "dimensions": [
                    {
                        "dimension": "validity",
                        "objective": 0,
                        "unit": "percentage",
                        "description": description or "Data quality policy pending.",
                    }
                ]
            }
        }
    }


def _normalize_data_quality_list(items: List[Any]) -> Dict[str, Any]:
    profiles = []
    for item in items:
        if not isinstance(item, dict):
            continue
        language, content = _language_content(item)
        source = content if isinstance(content, dict) else item
        description = _text(source.get("description"))
        profiles.append(
            {
                "description": description or "Data quality policy pending.",
                "dimensions": [
                    {
                        "dimension": "validity",
                        "objective": 0,
                        "unit": "percentage",
                        "description": description
                        or f"Data quality policy pending ({language}).",
                    }
                ],
            }
        )
    return {
        "declarative": (
            _named_profiles_from_list(profiles, "default") if profiles else {}
        )
    }


def _normalize_data_quality_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(profile)
    dimensions = normalized.get("dimensions")
    if isinstance(dimensions, list):
        normalized["dimensions"] = [
            dimension
            for dimension in (
                _normalize_data_quality_dimension(dimension)
                for dimension in dimensions
                if isinstance(dimension, dict)
            )
            if dimension
        ]
    return normalized


def _normalize_data_quality_dimension(dimension: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(dimension)
    normalized["dimension"] = _normalize_enum(
        normalized.get("dimension") or normalized.get("name"),
        ODPS_DATA_QUALITY_DIMENSIONS,
        ODPS_DATA_QUALITY_DIMENSION_ALIASES,
        "validity",
    )
    if "objective" in normalized:
        normalized["objective"] = _normalize_integer_value(normalized["objective"])
    if "unit" in normalized:
        normalized["unit"] = _normalize_enum(
            normalized.get("unit"),
            ODPS_DATA_QUALITY_UNITS,
            ODPS_DATA_QUALITY_UNIT_ALIASES,
            "percentage",
        )
    return normalized


def _normalize_integer_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    text = _text(value)
    if text.isdigit():
        return int(text)
    return value


def _sla_from_loose_details(sla: Dict[str, Any]) -> Dict[str, Any]:
    dimensions = []
    update_frequency = _text(sla.get("updateFrequency"))
    if update_frequency:
        dimensions.append(
            {
                "dimension": "updateFrequency",
                "objective": update_frequency,
                "unit": "days",
            }
        )
    for key, value in sla.items():
        if key == "updateFrequency":
            continue
        objective = _text(value)
        if objective and key in ODPS_SLA_DIMENSIONS:
            dimensions.append(
                {"dimension": key, "objective": objective, "unit": "null"}
            )
    return {
        "declarative": {
            "default": {
                "name": {"en": "Default SLA"},
                "dimensions": dimensions,
            }
        }
    }


def _normalize_odps_pricing_plans(product: Dict[str, Any]) -> None:
    legacy_pricing = product.pop("pricing", None)
    if "pricingPlans" not in product and legacy_pricing is not None:
        product["pricingPlans"] = legacy_pricing

    pricing = product.get("pricingPlans")
    if isinstance(pricing, list):
        product["pricingPlans"] = {"declarative": _pricing_language_map(pricing)}
        return
    if not isinstance(pricing, dict):
        return
    plans = pricing.pop("plans", None)
    if isinstance(plans, list):
        declarative = pricing.setdefault("declarative", {})
        if isinstance(declarative, dict):
            existing = declarative.get("en")
            normalized_plans = [
                _normalize_portfolio_pricing_plan(plan)
                for plan in plans
                if isinstance(plan, dict)
            ]
            if isinstance(existing, list):
                declarative["en"] = existing + normalized_plans
            else:
                declarative["en"] = normalized_plans
    declarative = pricing.get("declarative")
    if isinstance(declarative, dict):
        for language, plans_for_language in list(declarative.items()):
            if isinstance(plans_for_language, list):
                declarative[language] = [
                    _normalize_portfolio_pricing_plan(plan)
                    for plan in plans_for_language
                    if isinstance(plan, dict)
                ]


def _normalize_odps_data_access(product: Dict[str, Any]) -> None:
    data_access = product.get("dataAccess")
    if isinstance(data_access, list):
        named_items = [
            (
                _data_access_key(item, None),
                _normalize_odps_data_access_item(item),
            )
            for item in data_access
            if isinstance(item, dict)
        ]
        if named_items:
            product["dataAccess"] = _unique_named_items(named_items)
        return

    if not isinstance(data_access, dict):
        return

    if _looks_like_data_access_method(data_access):
        product["dataAccess"] = {
            _data_access_key(data_access, None): _normalize_odps_data_access_item(
                data_access
            )
        }
        return

    items = []
    for key, value in list(data_access.items()):
        if key == "$ref" or not isinstance(value, dict):
            continue
        method = _normalize_odps_data_access_item(value, method_name=key)
        items.append((_data_access_key(method, key), method))

    if items:
        product["dataAccess"] = _unique_named_items(items)


def _unique_named_items(
    items: List[Tuple[str, Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    named: Dict[str, Dict[str, Any]] = {}
    for index, (key, value) in enumerate(items, start=1):
        candidate = key or f"item{index}"
        while candidate in named:
            candidate = f"{key}-{index}"
        named[candidate] = value
    return named


def _data_access_key(item: Dict[str, Any], fallback: Optional[str]) -> str:
    output_port_type = _text(item.get("outputPortType") or item.get("outputPorttype"))
    name = _text(item.get("name"))
    key = output_port_type or name or _text(fallback) or "API"
    if key.casefold() == "api":
        return "API"
    return _path_id(key)


def _looks_like_data_access_method(value: Dict[str, Any]) -> bool:
    method_keys = {
        "name",
        "description",
        "outputPorttype",
        "outputPortType",
        "format",
        "accessURL",
        "authenticationMethod",
        "specsURL",
        "documentationURL",
        "specification",
        "version",
        "reference",
        "accessInstructions",
    }
    return any(key in value for key in method_keys)


def _normalize_odps_data_access_item(
    item: Dict[str, Any], method_name: Optional[str] = None
) -> Dict[str, Any]:
    normalized = dict(item)
    legacy_output_port_type = normalized.pop("outputPorttype", None)
    output_port_type = normalized.get("outputPortType")
    if output_port_type is None:
        normalized["outputPortType"] = (
            _text(legacy_output_port_type)
            or _infer_output_port_type(method_name)
            or "API"
        )
    elif legacy_output_port_type is not None:
        normalized["outputPortType"] = _text(output_port_type) or _text(
            legacy_output_port_type
        )
    return normalized


def _infer_output_port_type(method_name: Optional[str]) -> Optional[str]:
    if not method_name:
        return None
    lowered = method_name.casefold()
    if "file" in lowered or "download" in lowered:
        return "file"
    if "database" in lowered or "sql" in lowered or "query" in lowered:
        return "database"
    if "stream" in lowered:
        return "stream"
    if "webhook" in lowered:
        return "webhook"
    if "ai" in lowered or "agent" in lowered or "mcp" in lowered:
        return "AI"
    if "api" in lowered:
        return "API"
    return None


def _pricing_language_map(plans: List[Any]) -> Dict[str, List[Dict[str, Any]]]:
    language_map: Dict[str, List[Dict[str, Any]]] = {}
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        language_keys = {
            key: value
            for key, value in plan.items()
            if isinstance(key, str) and isinstance(value, dict) and len(key) == 2
        }
        if language_keys:
            for language, value in language_keys.items():
                language_map.setdefault(language, []).append(
                    _normalize_portfolio_pricing_plan(value)
                )
        else:
            language_map.setdefault("en", []).append(
                _normalize_portfolio_pricing_plan(plan)
            )
    return language_map or {"en": []}


def _normalize_portfolio_pricing_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(plan)
    plan_name = normalized.pop("plan", None)
    if "price" not in normalized and "priceAmount" in normalized:
        normalized["price"] = normalized.pop("priceAmount")
    else:
        normalized.pop("priceAmount", None)
    if "name" not in normalized and "pricingPlanName" in normalized:
        normalized["name"] = normalized.pop("pricingPlanName")
    if "name" not in normalized and plan_name is not None:
        normalized["name"] = plan_name
    elif _text(normalized.get("name")) == "On-request" and plan_name is not None:
        normalized["name"] = plan_name
    if "description" not in normalized and "license" in normalized:
        normalized["description"] = normalized.pop("license")
    for key in ("name", "description"):
        value = normalized.get(key)
        if isinstance(value, dict):
            normalized[key] = _text(value)
    if not _text(normalized.get("name")):
        normalized["name"] = "On-request"
    if not _text(normalized.get("priceCurrency")):
        normalized["priceCurrency"] = "XXX"
    if not _text(normalized.get("price")):
        normalized["price"] = "0"
    if not _text(normalized.get("billingDuration")):
        normalized["billingDuration"] = "month"
    unit = _text(normalized.get("unit"))
    normalized["unit"] = _normalize_enum(
        unit,
        ODPS_PRICING_UNITS,
        ODPS_PRICING_UNIT_ALIASES,
        "On-request",
    )
    normalized["price"] = str(normalized["price"])
    return normalized


def _normalize_enum(
    value: Any,
    allowed: Iterable[str],
    aliases: Dict[str, str],
    default: str,
) -> str:
    text = _text(value)
    if text in allowed:
        return text
    lowered = text.casefold().strip()
    if lowered in aliases:
        return aliases[lowered]
    for candidate in allowed:
        if candidate.casefold() == lowered:
            return candidate
    return default


def _catalog_from_fragments(root: Path) -> Dict[str, Any]:
    existing = _load_optional_mapping(root / "odpc" / "catalog.yaml")
    catalog_root = existing.get("catalog") if isinstance(existing, dict) else {}
    metadata = {}
    if isinstance(catalog_root, dict) and isinstance(
        catalog_root.get("metadata"), dict
    ):
        metadata = catalog_root["metadata"]
    catalog: Dict[str, Any] = {"metadata": metadata or _default_catalog_metadata(root)}
    fragments = _fragment_collections(root / "odpc" / "fragments")
    for key in ("businessObjectives", "useCases", "signals", "productReferences"):
        if fragments[key]:
            catalog[key] = fragments[key]
    return {
        "schema": existing.get(
            "schema", "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml"
        ),
        "version": str(existing.get("version") or "1.0"),
        "kind": existing.get("kind", "Catalog"),
        "catalog": catalog,
    }


def _sync_product_references_from_odps(
    root: Path,
    catalog: Dict[str, Any],
    product_specs: Dict[str, Dict[str, Any]],
) -> List[Tuple[Path, str]]:
    catalog_root = catalog.get("catalog")
    if not isinstance(catalog_root, dict):
        return []
    writes: List[Tuple[Path, str]] = []
    for reference in _list(catalog_root, "productReferences"):
        product_id = _text(reference.get("productID") or reference.get("id"))
        product_info = product_specs.get(product_id)
        if not product_info:
            continue
        document = product_info.get("document")
        if not isinstance(document, dict):
            continue
        details = _product_details(document)
        if _merge_product_reference_details(reference, details):
            writes.append(
                _write_yaml(
                    root
                    / "odpc"
                    / "fragments"
                    / f"product_reference_{_file_id(reference)}.yaml",
                    {"productReference": reference},
                )
            )
    return writes


def _merge_product_reference_details(
    reference: Dict[str, Any],
    details: Dict[str, Any],
) -> bool:
    changed = False
    for source_key, target_key in (
        ("name", "name"),
        ("description", "description"),
        ("valueProposition", "valueProposition"),
    ):
        value = _text(details.get(source_key))
        if value and reference.get(target_key) != {"en": value}:
            reference[target_key] = {"en": value}
            changed = True
    for key in ("status", "type"):
        value = _text(details.get(key))
        if value and reference.get(key) != value:
            reference[key] = value
            changed = True
    visibility = _odpc_product_visibility(details.get("visibility"))
    if visibility and reference.get("visibility") != visibility:
        reference["visibility"] = visibility
        changed = True
    return changed


def _odpc_product_visibility(value: Any) -> str:
    visibility = _text(value)
    if visibility in {"public", "internal", "restricted", "private"}:
        return visibility
    if visibility == "organisation":
        return "internal"
    if visibility == "invitation":
        return "restricted"
    return ""


def _default_catalog_metadata(root: Path) -> Dict[str, Any]:
    portfolio = _load_optional_mapping(root / "portfolio.yaml")
    metadata = portfolio.get("metadata") if isinstance(portfolio, dict) else {}
    name = (
        metadata.get("name", "Portfolio") if isinstance(metadata, dict) else "Portfolio"
    )
    description = (
        metadata.get("description", "Portfolio synced from YAML artifacts.")
        if isinstance(metadata, dict)
        else "Portfolio synced from YAML artifacts."
    )
    return {
        "id": (
            metadata.get("id", "CAT-PORTFOLIO")
            if isinstance(metadata, dict)
            else "CAT-PORTFOLIO"
        ),
        "name": {"en": name},
        "description": {"en": description},
    }


def _fragment_collections(fragments_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    collections: Dict[str, List[Dict[str, Any]]] = {
        "businessObjectives": [],
        "useCases": [],
        "signals": [],
        "productReferences": [],
    }
    if not fragments_dir.exists():
        return collections
    keys = {
        "businessObjective": "businessObjectives",
        "useCase": "useCases",
        "signal": "signals",
        "productReference": "productReferences",
    }
    for path in sorted(
        [
            *fragments_dir.glob("*.yaml"),
            *fragments_dir.glob("*.yml"),
            *fragments_dir.glob("*.json"),
        ]
    ):
        document = load_mapping(path, root_name="ODPC fragment")
        for source_key, target_key in keys.items():
            value = document.get(source_key)
            if isinstance(value, dict):
                collections[target_key].append(value)
    return collections


def _plan_from_catalog(catalog: Dict[str, Any]) -> Dict[str, Any]:
    catalog_root = catalog.get("catalog") if isinstance(catalog, dict) else {}
    if not isinstance(catalog_root, dict):
        catalog_root = {}
    return {
        "businessObjectives": _list(catalog_root, "businessObjectives"),
        "useCases": _list(catalog_root, "useCases"),
        "signals": _list(catalog_root, "signals"),
        "products": [
            {"productReference": item}
            for item in _list(catalog_root, "productReferences")
        ],
    }


def _plan_from_workspace(root: Path) -> Dict[str, Any]:
    catalog_path = root / "odpc" / "catalog.yaml"
    catalog = load_catalog(catalog_path) if catalog_path.exists() else _empty_catalog()
    plan = _plan_from_catalog(catalog)
    product_specs = _load_product_specs(root)
    for product in _list(plan, "products"):
        reference = product.get("productReference")
        if not isinstance(reference, dict):
            continue
        product_id = _text(reference.get("productID") or reference.get("id"))
        product_info = product_specs.get(product_id)
        if isinstance(product_info, dict):
            document = product_info.get("document")
            if isinstance(document, dict):
                product["odpsProduct"] = document

    graph_path = root / "odpg" / "graph.yaml"
    graph = load_graph(graph_path) if graph_path.exists() else _empty_graph()
    graph_payload = graph.get("graph") if isinstance(graph, dict) else {}
    if isinstance(graph_payload, dict):
        edges = []
        for edge in _list(graph_payload, "edges"):
            edges.append(
                {
                    "source": _text(edge.get("source") or edge.get("from")),
                    "target": _text(edge.get("target") or edge.get("to")),
                    "type": _text(edge.get("type"), "relatedTo"),
                    "confidence": _text(edge.get("confidence"), "medium"),
                }
            )
        if edges:
            plan["graphEdges"] = edges
    return plan


def _merge_portfolio_plans(
    existing: Dict[str, Any],
    delta: Dict[str, Any],
) -> Dict[str, Any]:
    merged = deepcopy(existing) if isinstance(existing, dict) else {}
    if not isinstance(delta, dict):
        return merged
    metadata = delta.get("metadata")
    if isinstance(metadata, dict) and not isinstance(merged.get("metadata"), dict):
        merged["metadata"] = metadata
    for collection in ("businessObjectives", "useCases", "signals"):
        merged[collection] = _merge_items_by_id(
            _list(merged, collection), _list(delta, collection)
        )
    merged["products"] = _merge_products(
        _list(merged, "products"), _list(delta, "products")
    )
    merged["graphEdges"] = _merge_graph_edges(
        _list(merged, "graphEdges"), _list(delta, "graphEdges")
    )
    warnings = [
        *_string_list(merged.get("warnings")),
        *_string_list(delta.get("warnings")),
    ]
    if warnings:
        merged["warnings"] = list(dict.fromkeys(warnings))
    return merged


def _merge_items_by_id(
    existing: List[Dict[str, Any]],
    delta: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged = {
        (_text(item.get("id")) or _artifact_fingerprint(item)): item
        for item in existing
    }
    for item in delta:
        key = _text(item.get("id")) or _artifact_fingerprint(item)
        merged[key] = item
    return list(merged.values())


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _merge_products(
    existing: List[Dict[str, Any]],
    delta: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged = {_product_merge_key(item): item for item in existing}
    for item in delta:
        merged[_product_merge_key(item)] = item
    return list(merged.values())


def _product_merge_key(product: Dict[str, Any]) -> str:
    reference = product.get("productReference")
    if isinstance(reference, dict):
        return _text(
            reference.get("productID") or reference.get("id")
        ) or _artifact_fingerprint(reference)
    return _artifact_fingerprint(product)


def _merge_graph_edges(
    existing: List[Dict[str, Any]],
    delta: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged = {_graph_edge_key(item): item for item in existing}
    for item in delta:
        merged[_graph_edge_key(item)] = item
    return list(merged.values())


def _graph_edge_key(edge: Dict[str, Any]) -> str:
    source = _text(edge.get("source") or edge.get("from"))
    target = _text(edge.get("target") or edge.get("to"))
    edge_type = _text(edge.get("type"), "relatedTo")
    return f"{source}|{edge_type}|{target}"


def _ensure_changed_signal_source_coverage(
    plan: Dict[str, Any],
    lanes: Dict[str, List[Dict[str, str]]],
    source_changes: Dict[str, Any],
) -> Dict[str, Any]:
    lane_changes = source_changes.get("lanes")
    if not isinstance(lane_changes, dict):
        return plan
    signal_changes = lane_changes.get("signals")
    if not isinstance(signal_changes, dict):
        return plan
    changed_paths = {
        str(path)
        for key in ("created", "updated")
        for path in signal_changes.get(key, [])
    }
    if not changed_paths:
        return plan

    covered = deepcopy(plan) if isinstance(plan, dict) else {}
    signals = _list(covered, "signals")
    existing_ids = {_text(item.get("id")) for item in signals}
    for source in lanes.get("signals", []):
        if source.get("path") not in changed_paths:
            continue
        if _signal_source_is_represented(signals, source):
            continue
        signal = _draft_signal_from_source(source, existing_ids)
        existing_ids.add(_text(signal.get("id")))
        signals.append(signal)
        warnings = covered.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(
                f"Draft signal created from changed source {source['path']} because the model did not return a separate signal artifact."
            )
    if signals:
        covered["signals"] = signals
    return covered


def _signal_source_is_represented(
    signals: List[Dict[str, Any]],
    source: Dict[str, str],
) -> bool:
    source_key = _normalize_identity_text(Path(source["path"]).stem.replace("-", " "))
    source_title = _normalize_identity_text(_source_signal_title(source))
    source_terms = _meaningful_terms(source.get("text", ""))
    for signal in signals:
        identity = _normalize_identity_text(
            " ".join(
                [
                    _text(signal.get("id")),
                    _text(signal.get("name")),
                    _text(signal.get("description")),
                ]
            )
        )
        if source_key and source_key in identity:
            return True
        if source_title and source_title in identity:
            return True
        if _term_overlap(source_terms, _meaningful_terms(identity)) >= 4:
            return True
    return False


def _draft_signal_from_source(
    source: Dict[str, str],
    existing_ids: set,
) -> Dict[str, Any]:
    title = _source_signal_title(source)
    signal_id = _unique_signal_id(Path(source["path"]).stem, existing_ids)
    return {
        "id": signal_id,
        "name": {"en": title},
        "description": {"en": _source_signal_description(source)},
        "type": "operational",
        "confidence": "medium",
        "source": {
            "origin": "internal",
            "method": "generated from changed signal source",
        },
    }


def _unique_signal_id(stem: str, existing_ids: set) -> str:
    base = f"SIG-{_path_id(stem).upper()}"
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _source_signal_title(source: Dict[str, str]) -> str:
    text = source.get("text", "")
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("#").strip()
        if not line:
            continue
        lowered = line.casefold()
        if lowered.startswith("signal:"):
            line = line.split(":", 1)[1].strip()
        if line:
            return _title_from_text(line)
    return _title_from_text(Path(source["path"]).stem.replace("-", " "))


def _source_signal_description(source: Dict[str, str]) -> str:
    text = source.get("text", "")
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.casefold().startswith("signal:"):
            line = line.split(":", 1)[1].strip()
        if line:
            lines.append(line)
        if len(" ".join(lines)) >= 220:
            break
    description = " ".join(lines).strip()
    return description or f"Draft signal created from {source['path']}."


def _title_from_text(value: str) -> str:
    return " ".join(word.capitalize() for word in value.replace("_", " ").split())


def _meaningful_terms(value: str) -> set:
    stopwords = {
        "and",
        "are",
        "for",
        "from",
        "has",
        "have",
        "inside",
        "into",
        "that",
        "the",
        "this",
        "use",
        "uses",
        "with",
    }
    terms = set()
    current = []
    for char in value.casefold():
        if char.isalnum():
            current.append(char)
        elif current:
            term = "".join(current)
            if len(term) >= 4 and term not in stopwords:
                terms.add(term)
            current = []
    if current:
        term = "".join(current)
        if len(term) >= 4 and term not in stopwords:
            terms.add(term)
    return terms


def _term_overlap(left: set, right: set) -> int:
    return len(left & right)


def _catalog_document(plan: Dict[str, Any]) -> Dict[str, Any]:
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    catalog: Dict[str, Any] = {
        "metadata": {
            "id": metadata.get("id", "CAT-PORTFOLIO"),
            "name": {"en": metadata.get("name", "Generated Portfolio")},
            "description": {
                "en": metadata.get(
                    "description", "Generated from portfolio source lanes."
                )
            },
        }
    }
    collections = (
        ("businessObjectives", "businessObjectives"),
        ("useCases", "useCases"),
        ("signals", "signals"),
    )
    for source_key, target_key in collections:
        items = _list(plan, source_key)
        if items:
            catalog[target_key] = items
    return {
        "schema": "https://opendataproducts.org/odpc-v1.0/schema/odpc.yaml",
        "version": "1.0",
        "kind": "Catalog",
        "catalog": catalog,
    }


def _graph_document(plan: Dict[str, Any]) -> Dict[str, Any]:
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    nodes = []
    nodes.extend(
        _graph_nodes(
            _list(plan, "businessObjectives"),
            "BusinessObjective",
            "business_objective",
        )
    )
    nodes.extend(_graph_nodes(_list(plan, "useCases"), "UseCase", "use_case"))
    nodes.extend(_graph_nodes(_list(plan, "signals"), "Signal", "signal"))
    for product in _list(plan, "products"):
        reference = product.get("productReference")
        if isinstance(reference, dict):
            nodes.append(_graph_node(reference, "DataProduct", "product_reference"))
    return {
        "schema": "https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml",
        "version": "1.0",
        "kind": "Graph",
        "graph": {
            "metadata": {
                "id": f"{metadata.get('id', 'portfolio')}-graph",
                "name": {"en": metadata.get("name", "Generated Portfolio")},
                "description": {
                    "en": metadata.get(
                        "description",
                        "Generated portfolio relationship graph.",
                    )
                },
            },
            "nodes": nodes,
            "edges": [_graph_edge(edge) for edge in _list(plan, "graphEdges")],
        },
    }


def _graph_nodes(
    items: List[Dict[str, Any]],
    node_type: str,
    fragment_prefix: str,
) -> List[Dict[str, Any]]:
    return [_graph_node(item, node_type, fragment_prefix) for item in items]


def _graph_node(
    item: Dict[str, Any],
    node_type: str,
    fragment_prefix: str,
) -> Dict[str, Any]:
    item_id = _text(item.get("id") or item.get("productID"))
    return {
        "id": item_id,
        "type": node_type,
        "$ref": f"../odpc/fragments/{fragment_prefix}_{_path_id(item_id)}.yaml",
    }


def _graph_edge(edge: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "from": _text(edge.get("source") or edge.get("from")),
        "to": _text(edge.get("target") or edge.get("to")),
        "type": _text(edge.get("type"), "relatedTo"),
        "confidence": _text(edge.get("confidence"), "medium"),
    }


def _artifact_counts(plan: Dict[str, Any]) -> Dict[str, int]:
    return {
        "businessObjectives": len(_list(plan, "businessObjectives")),
        "useCases": len(_list(plan, "useCases")),
        "signals": len(_list(plan, "signals")),
        "productReferences": len(_list(plan, "products")),
        "odpsProducts": len(_list(plan, "products")),
        "graphEdges": len(_list(plan, "graphEdges")),
    }


def _workspace_artifact_counts(data: Dict[str, Any]) -> Dict[str, int]:
    catalog = data["catalog"].get("catalog", {})
    graph = data["graph"].get("graph", {})
    return {
        "businessObjectives": _count(catalog, "businessObjectives"),
        "useCases": _count(catalog, "useCases"),
        "signals": _count(catalog, "signals"),
        "productReferences": _count(catalog, "productReferences"),
        "odpsProducts": len(data["products"]),
        "graphNodes": _count(graph, "nodes"),
        "graphEdges": _count(graph, "edges"),
    }


def _extract_yaml_text(raw_output: str) -> str:
    stripped = raw_output.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return ""
    if "```" not in raw_output:
        return raw_output
    parts = raw_output.split("```")
    if len(parts) < 3:
        return raw_output
    candidate = parts[1]
    if candidate.lstrip().startswith(("yaml", "yml")):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
    return candidate


def _file_id(item: Dict[str, Any]) -> str:
    return _path_id(_text(item.get("id") or item.get("productID"), "item"))


def _path_id(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in "._-" else "-" for char in value
    )
    return cleaned.strip("-") or "item"


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
    result: Dict[str, object] = {
        "spec": "portfolio",
        "kind": "PortfolioRender",
        "workspace": str(root),
        "html": str(output),
        "created": [],
        "updated": [],
        "unchanged": [],
        "warnings": data["warnings"],
        "validationResults": validation_results,
        "valid": _valid_portfolio(validation_results),
    }
    result[changed_key] = [str(output)]
    return result


def explain_portfolio(workspace: Union[str, Path]) -> Dict[str, object]:
    """Return a JSON-ready summary of a portfolio workspace."""
    root = Path(workspace)
    data = load_portfolio_workspace(root)
    catalog = data["catalog"].get("catalog", {})
    graph = data["graph"].get("graph", {})
    validation_results = _portfolio_validation_results(data)
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
        "validationResults": validation_results,
        "valid": _valid_portfolio(validation_results),
    }


def load_portfolio_workspace(workspace: Union[str, Path]) -> Dict[str, Any]:
    """Load portfolio map, catalog, product specs, graph, and version metadata."""
    root = Path(workspace)
    catalog_path = root / "odpc" / "catalog.yaml"
    graph_path = root / "odpg" / "graph.yaml"
    portfolio_path = root / "portfolio.yaml"
    i18n = _load_portfolio_i18n(root)
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
    }


def _valid_portfolio(validation_results: Dict[str, Any]) -> bool:
    catalog = validation_results.get("catalog", {})
    graph = validation_results.get("graph", {})
    products = validation_results.get("products", [])
    return (
        bool(catalog.get("valid"))
        and bool(graph.get("valid"))
        and all(bool(product.get("valid")) for product in products)
    )


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


def _html_direction(language: str) -> str:
    primary = language.split("-", 1)[0].lower()
    return "rtl" if primary in RTL_LANGUAGE_SUBTAGS else "ltr"


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
    if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", text):
        return False
    if "/" in text and re.search(r"\.(yaml|yml|json|html)\b", text):
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T[\d:-]+Z", text):
        return False
    return True


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
        _portfolio_css(),
        "</style>",
        "</head>",
        "<body>",
        '<header class="topbar">',
        '<div class="topbar-inner">',
        '<a class="brand" href="#overview" aria-label="Open Data Products portfolio">Open Data Products Portfolio</a>',
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
        _render_artifact_panel(
            "objectives",
            "Objectives",
            "Business Objectives",
            "Business-Led Starting Point",
            "Objectives make the portfolio business-led before products become the center of gravity.",
            business_objectives,
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
        _portfolio_js(),
        "</body>",
        "</html>",
    ]
    return "\n".join(html_parts) + "\n"


def _render_tab_inputs() -> str:
    tabs = (
        "overview",
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


def _change_list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


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
) -> str:
    cards = "".join(
        _render_artifact_card(item, card_class=card_class) for item in items
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


def _render_artifact_card(item: Dict[str, Any], *, card_class: str = "") -> str:
    name = _text(item.get("name"), _text(item.get("id"), "(unnamed)"))
    details = [
        ("ID", item.get("id")),
        ("Status", item.get("status")),
        ("Priority", item.get("priority")),
        ("Confidence", item.get("confidence")),
        ("Type", item.get("type")),
    ]
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
    pricing_items = _pricing_items(product)
    referenced_profiles = _referenced_pricing_profiles(pricing_items)
    sections = [_render_pricing_section(pricing_items, product)]
    if not pricing_items:
        sections.extend(
            [
                _render_declarative_section(
                    "SLA", _declarative_items(product.get("SLA"))
                ),
                _render_declarative_section(
                    "Data Quality", _declarative_items(product.get("dataQuality"))
                ),
            ]
        )
    else:
        sections.extend(
            [
                _render_declarative_section(
                    "Unlinked SLA profiles",
                    _unreferenced_declarative_items(
                        product.get("SLA"), referenced_profiles["SLA"]
                    ),
                ),
                _render_declarative_section(
                    "Unlinked Data Quality profiles",
                    _unreferenced_declarative_items(
                        product.get("dataQuality"), referenced_profiles["dataQuality"]
                    ),
                ),
            ]
        )
    product_model_path = _escape(str(path))
    return (
        '<div class="odp-detail product-detail-layout">'
        f'<p>{_escape(_text(details.get("description")))}</p>'
        f"{_render_facts(facts)}"
        f"{''.join(sections)}"
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
    return (
        '<footer class="footer"><div class="wrap footer-inner">'
        "<p>Generated with the Open Data Products SDK. This static portfolio keeps "
        "catalog artifacts, ODPS product specs, ODPG graph data, version snapshots, "
        "and review guidance together in one browser-openable file. Generated "
        "product specs are drafts until reviewed and accepted by humans.</p>"
        '<nav class="footer-links" aria-label="Portfolio artifact links">'
        '<a href="odpc/catalog.yaml">Catalog YAML</a>'
        '<a href="odpg/graph.yaml">Graph YAML</a>'
        '<a href="#overview">Back to top</a>'
        "</nav></div></footer>"
    )


def _portfolio_js() -> str:
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
    for path in _product_spec_paths(root):
        try:
            document = load_mapping(path, root_name="ODPS product")
        except ValueError:
            continue
        details = _product_details(document)
        product_id = _text(details.get("productID") or details.get("id"), path.stem)
        products[product_id] = {"path": path, "document": document}
    return products


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


def _product_spec_paths(root: Path) -> List[Path]:
    product_dir = root / "odps" / "products"
    return sorted(
        [
            *product_dir.glob("*.yaml"),
            *product_dir.glob("*.yml"),
            *product_dir.glob("*.json"),
        ]
    )


def _portfolio_versions(root: Path, portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
    versions: List[Dict[str, Any]] = []
    metadata_versions = portfolio.get("versions")
    if isinstance(metadata_versions, list):
        for item in metadata_versions:
            if not isinstance(item, dict):
                continue
            version_id = str(item.get("id") or item.get("version") or "")
            html_path = str(item.get("html") or f"versions/{version_id}/index.html")
            if version_id:
                report = _version_report_for_html(root, html_path)
                versions.append(
                    {
                        "id": version_id,
                        "type": str(
                            item.get("type")
                            or item.get("runType")
                            or report.get("kind")
                            or "snapshot"
                        ),
                        "summary": str(
                            item.get("summary") or _version_report_summary(report) or ""
                        ),
                        "html": html_path,
                        "report": report,
                    }
                )
    if versions:
        return versions
    versions_root = root / "versions"
    if versions_root.exists():
        for path in sorted(versions_root.glob("*/index.html")):
            version_id = path.parent.name
            report = _load_version_report(path.parent / "report.json")
            versions.append(
                {
                    "id": version_id,
                    "type": str(report.get("kind") or "snapshot"),
                    "summary": _version_report_summary(report),
                    "html": path.relative_to(root).as_posix(),
                    "report": report,
                }
            )
    return versions


def _version_report_for_html(root: Path, html_path: str) -> Dict[str, Any]:
    path = root / html_path
    return _load_version_report(path.parent / "report.json")


def _load_version_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_mapping(path, root_name="Portfolio version report")
    except ValueError:
        return {}


def _version_report_summary(report: Dict[str, Any]) -> str:
    if not report:
        return ""
    created = _change_list_count(report.get("created"))
    updated = _change_list_count(report.get("updated"))
    removed = _change_list_count(report.get("removed"))
    changes = []
    if created:
        changes.append(f"{created} created")
    if updated:
        changes.append(f"{updated} updated")
    if removed:
        changes.append(f"{removed} removed")
    return ", ".join(changes)


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
    if not items:
        return ""
    rows = []
    for item in items:
        name = _text(item.get("name"), "Pricing plan")
        description = _text(item.get("description"))
        price = _text(item.get("price"), "0")
        currency = _text(item.get("priceCurrency"))
        amount = " ".join(part for part in (price, currency) if part)
        rows.append(
            '<tr class="pricing-plan-row">'
            f"<td><strong>{_escape(name)}</strong>"
            f"{f'<p>{_escape(description)}</p>' if description else ''}</td>"
            f"<td>{_escape(amount)}</td>"
            f"<td>{_escape(_text(item.get('billingDuration')))}</td>"
            f"<td>{_escape(_text(item.get('unit')))}</td>"
            f"<td>{_render_component_refs(item)}</td>"
            "</tr>"
        )
        linked_components = _render_pricing_linked_components(item, product)
        if linked_components:
            rows.append(
                '<tr class="pricing-linked-row">'
                f'<td colspan="5">{linked_components}</td>'
                "</tr>"
            )
    return (
        '<section class="component-section">'
        "<h4>Pricing</h4>"
        '<div class="table-scroll"><table class="pricing-table">'
        "<thead><tr><th>Plan</th><th>Price</th><th>Billing Duration</th>"
        "<th>Unit</th><th>References</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table></div>"
        "</section>"
    )


def _referenced_pricing_profiles(items: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
    references = {"SLA": set(), "dataQuality": set()}
    for item in items:
        for key in references:
            profile = _profile_key_from_ref(_component_ref(item.get(key)))
            if profile:
                references[key].add(profile)
    return references


def _unreferenced_declarative_items(
    value: Any, referenced: Set[str]
) -> List[Dict[str, Any]]:
    return [
        item
        for item in _declarative_items(value)
        if _text(item.get("profile"), "default") not in referenced
    ]


def _render_pricing_linked_components(
    item: Dict[str, Any], product: Dict[str, Any]
) -> str:
    components = [
        _render_pricing_linked_profile(
            "Included SLA", item.get("SLA"), product.get("SLA")
        ),
        _render_pricing_linked_profile(
            "Included Data Quality",
            item.get("dataQuality"),
            product.get("dataQuality"),
        ),
        _render_pricing_linked_access(item.get("access"), product.get("dataAccess")),
        _render_pricing_linked_gateway(
            item.get("paymentGateway"), product.get("paymentGateways")
        ),
    ]
    rendered = [component for component in components if component]
    if not rendered:
        return ""
    return f'<div class="pricing-linked-components">{"".join(rendered)}</div>'


def _render_pricing_linked_profile(title: str, reference: Any, value: Any) -> str:
    profile = _resolve_declarative_ref(reference, value)
    if profile is None:
        return ""
    name = _text(profile.get("name"), _title_from_text(_text(profile.get("profile"))))
    description = _text(profile.get("description"))
    description_html = f"<p>{_escape(description)}</p>" if description else ""
    return (
        '<article class="linked-component-card">'
        f'<p class="linked-component-title">{_escape(title)}</p>'
        f"<h5>{_escape(name)}</h5>"
        f'<span class="profile-chip">{_escape(_text(profile.get("profile"), "default"))}</span>'
        f"{description_html}"
        f"{_render_dimensions(profile.get('dimensions'))}"
        "</article>"
    )


def _render_pricing_linked_access(reference: Any, value: Any) -> str:
    access = _resolve_named_ref(reference, value)
    if access is None:
        return ""
    facts = [
        ("Description", access.get("description")),
        (
            "Output Port Type",
            access.get("outputPortType") or access.get("outputPorttype"),
        ),
        ("Format", access.get("format")),
        ("Authentication", access.get("authenticationMethod")),
    ]
    return (
        '<article class="linked-component-card">'
        '<p class="linked-component-title">Included Access</p>'
        f"<h5>{_escape(_title_from_text(_profile_key_from_ref(_component_ref(reference)) or 'access'))}</h5>"
        f"{_render_facts(facts)}"
        "</article>"
    )


def _render_pricing_linked_gateway(reference: Any, value: Any) -> str:
    gateway = _resolve_named_ref(reference, value)
    if gateway is None:
        return ""
    facts = [
        ("Name", gateway.get("name")),
        ("Type", gateway.get("type")),
        ("Provider", gateway.get("provider")),
        ("Description", gateway.get("description")),
    ]
    return (
        '<article class="linked-component-card">'
        '<p class="linked-component-title">Included Payment</p>'
        f"<h5>{_escape(_title_from_text(_profile_key_from_ref(_component_ref(reference)) or 'payment'))}</h5>"
        f"{_render_facts(facts)}"
        "</article>"
    )


def _resolve_declarative_ref(reference: Any, value: Any) -> Optional[Dict[str, Any]]:
    profile_key = _profile_key_from_ref(_component_ref(reference))
    if not profile_key:
        return None
    for item in _declarative_items(value):
        if _text(item.get("profile"), "default") == profile_key:
            return item
    return None


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


def _render_declarative_section(title: str, items: List[Dict[str, Any]]) -> str:
    if not items:
        return ""
    rendered = []
    for item in items:
        profile = _text(item.get("profile"), "default")
        name = _text(item.get("name"), _title_from_text(profile))
        description = _text(item.get("description"))
        facts = [
            (str(key), value)
            for key, value in item.items()
            if key not in {"name", "description", "dimensions", "profile"}
            and not isinstance(value, (dict, list))
        ]
        description_html = f"<p>{_escape(description)}</p>" if description else ""
        rendered.append(
            '<li class="component-card">'
            f"<h5>{_escape(name)}</h5>"
            f'<span class="profile-chip">{_escape(profile)}</span>'
            f"{description_html}"
            f"{_render_facts(facts)}"
            f"{_render_dimensions(item.get('dimensions'))}"
            "</li>"
        )
    return (
        '<section class="component-section">'
        f"<h4>{_escape(title)}</h4>"
        f'<ul class="component-list">{"".join(rendered)}</ul>'
        "</section>"
    )


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
                refs.append(
                    f"<li><strong>{_escape(label)}</strong> {_escape(ref)}</li>"
                )
    if not refs:
        return ""
    return f'<ul class="component-refs">{"".join(refs)}</ul>'


def _render_dimensions(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    rows = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = _dimension_label(item)
        objective = _text(item.get("objective"))
        unit = _text(item.get("unit"))
        metric = " ".join(part for part in (objective, unit) if part and part != "null")
        weight = _text(item.get("weight"))
        description = _text(item.get("description"))
        meta = []
        if metric:
            meta.append(f'<span class="dimension-metric">{_escape(metric)}</span>')
        if weight:
            meta.append(
                f'<span class="dimension-weight">{_escape(weight)} weight</span>'
            )
        description_html = (
            f'<p class="dimension-description">{_escape(description)}</p>'
            if description
            else ""
        )
        rows.append(
            '<li class="dimension-row">'
            f"<div><strong>{_escape(label)}</strong>{description_html}</div>"
            f'<div class="dimension-meta">{"".join(meta)}</div>'
            "</li>"
        )
    if not rows:
        return ""
    return f'<ul class="dimension-list">{"".join(rows)}</ul>'


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
  --odps-violet: #6c2a8e;
  --odpc-orange: #f28c28;
  --odpg-green: #2f9b58;
  --odpv-blue: #1f78d1;
  --odp-ink: #1e0a2e;
  --odp-soft: #f7f3fa;
  --odp-line: #e7e1ec;
  --odp-muted: #6d6175;
  --odp-black: #050505;
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
  width: min(1180px, calc(100% - 32px));
  margin: 0 auto;
}
.topbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 58px;
}
.brand {
  font-weight: 700;
}
.language-selector {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: .82rem;
}
.language-selector span {
  padding: 4px 8px;
  border: 1px solid rgba(255,255,255,.35);
  border-radius: 8px;
  font-weight: 800;
  text-transform: uppercase;
}
.language-selector div {
  display: flex;
  gap: 8px;
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
  padding: 46px 0 30px;
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 14px;
  color: var(--odps-violet);
  font-size: .78rem;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.hero .eyebrow { color: rgba(255, 255, 255, .82); }
h1 {
  max-width: 780px;
  margin: 0 0 14px;
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
  padding: 26px 0 64px;
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
  gap: 8px;
  overflow-x: auto;
  padding: 12px 0;
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
  padding: 8px 13px;
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  color: var(--odp-muted);
  background: #fff;
  cursor: pointer;
  font-size: .9rem;
  font-weight: 700;
}
#tab-overview:checked ~ .tabs label[for="tab-overview"],
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
  padding-top: 28px;
}
#tab-overview:checked ~ .panels .overview-panel,
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
  gap: 18px;
  margin-bottom: 16px;
}
.section-head p {
  max-width: 540px;
  margin: 0;
  color: var(--odp-muted);
}
.summary {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin: 0 0 26px;
}
.metric,
.card,
.panel {
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(30, 10, 46, .06);
}
.metric {
  min-height: 104px;
  padding: 16px;
}
.metric strong {
  display: block;
  font-size: 2.1rem;
  line-height: 1;
}
.metric span {
  display: block;
  margin-top: 8px;
  color: var(--odp-muted);
  font-size: .8rem;
  font-weight: 700;
  text-transform: uppercase;
}
.grid,
.actions-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.product-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.card {
  position: relative;
  min-height: 216px;
  padding: 18px;
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
.product-card-counters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 14px 0;
}
.product-card-counters span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 8px;
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
  padding: 0 14px;
}
.product-detail-button:hover,
.product-modal-close:hover {
  background: #4f1f68;
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}
.chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 4px 8px;
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
  margin: 0 0 14px;
  color: var(--odp-muted);
}
.odp-facts {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 12px;
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
  margin-top: 18px;
}
.component-section h4 {
  margin: 0 0 10px;
}
.table-scroll {
  max-width: 100%;
  overflow-x: auto;
}
.pricing-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  background: #fff;
  font-size: .88rem;
}
.pricing-table th,
.pricing-table td {
  padding: 10px;
  border-bottom: 1px solid var(--odp-line);
  text-align: left;
  vertical-align: top;
}
.pricing-table th {
  background: var(--odp-soft);
  color: var(--odp-muted);
  font-size: .76rem;
  text-transform: uppercase;
}
.pricing-table tr:last-child td {
  border-bottom: 0;
}
.pricing-table p {
  margin: 4px 0 0;
  font-size: .84rem;
}
.pricing-linked-row td {
  padding: 12px;
  background: #fbf9fc;
}
.pricing-linked-components {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.linked-component-card {
  min-width: 0;
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  background: #fff;
  padding: 12px;
}
.linked-component-title {
  margin: 0 0 6px;
  color: var(--odps-violet);
  font-size: .72rem;
  font-weight: 900;
  letter-spacing: .04em;
  text-transform: uppercase;
}
.linked-component-card h5 {
  margin: 0 0 8px;
  font-size: .98rem;
}
.linked-component-card .odp-facts {
  grid-template-columns: max-content minmax(0, 1fr);
}
.component-list,
.dimension-list,
.component-refs {
  list-style: none;
  margin: 0;
  padding: 0;
}
.component-list {
  display: grid;
  gap: 12px;
}
.component-card {
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  background: #fff;
  padding: 14px;
}
.component-card h5 {
  margin: 0 0 8px;
  font-size: 1rem;
}
.profile-chip {
  display: inline-flex;
  margin-bottom: 10px;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--odp-soft);
  color: var(--odp-muted);
  font-size: .72rem;
  font-weight: 800;
  text-transform: uppercase;
}
.dimension-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}
.dimension-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 10px;
  border: 1px solid var(--odp-line);
  border-radius: 8px;
  background: var(--odp-soft);
}
.dimension-description {
  margin: 4px 0 0;
  font-size: .86rem;
}
.dimension-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}
.dimension-metric,
.dimension-weight {
  display: inline-flex;
  padding: 3px 8px;
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
  gap: 8px;
  margin-top: 12px;
  color: var(--odp-muted);
  font-size: .82rem;
}
.modal-open {
  overflow: hidden;
}
.product-modal {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: none;
  padding: 28px;
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
  width: min(1120px, calc(100vw - 56px));
  max-height: calc(100vh - 56px);
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
  gap: 16px;
  padding: 20px 22px;
  border-bottom: 1px solid var(--odp-line);
  background: #fff;
}
.product-modal-header h3 {
  margin: 0;
  font-size: 1.45rem;
}
.product-detail-layout {
  margin: 0;
  padding: 22px;
  border-top: 0;
}
.odp-muted { color: var(--odp-muted); }
.odp-detail {
  margin-top: 14px;
  padding-top: 12px;
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
  padding: 16px;
}
.action-card strong {
  display: block;
  margin: 6px 0;
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
  gap: 16px;
}
.overview-section {
  margin-top: 28px;
}
.overview-card-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}
.change-story-list {
  display: grid;
  gap: 8px;
  margin: 14px 0 0;
  padding-left: 18px;
  color: var(--odp-muted);
}
.panel { padding: 18px; }
.version-list {
  margin: 0;
  padding: 0;
}
.version-list li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 8px;
  padding: 10px 0;
  border-bottom: 1px solid var(--odp-line);
  list-style: none;
}
.version-history {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--odp-line);
}
.version-table {
  width: 100%;
  max-width: 100%;
  margin-top: 12px;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: .9rem;
}
.version-table th,
.version-table td {
  padding: 9px 6px;
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
  padding: 26px;
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
  margin-top: 42px;
  padding: 24px 0 34px;
  color: rgba(255, 255, 255, .78);
  background: var(--odp-black);
  border-top: 4px solid var(--odps-violet);
  font-size: .92rem;
}
.footer-inner {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: start;
}
.footer p {
  max-width: 760px;
  margin: 0;
}
.footer-links {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
  font-weight: 700;
}
.footer-links a { color: #fff; }
@media (max-width: 900px) {
  .overview-grid,
  .footer-inner {
    grid-template-columns: 1fr;
  }
  .summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .grid,
  .actions-grid,
  .product-grid {
    grid-template-columns: 1fr;
  }
  .product-modal {
    padding: 12px;
  }
  .product-modal-panel {
    width: calc(100vw - 24px);
    max-height: calc(100vh - 24px);
  }
  .product-modal-header {
    align-items: start;
  }
  .dimension-row {
    grid-template-columns: 1fr;
  }
  .dimension-meta {
    justify-content: flex-start;
  }
  .wide { grid-column: auto; }
  .footer-links { justify-content: flex-start; }
}
"""
