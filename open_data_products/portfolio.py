"""Portfolio workspace rendering and explanation helpers."""

from __future__ import annotations

import html
import hashlib
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
from .generation.models import PortfolioPrivacySettings, PortfolioSourceBudget
from .odpc import load_catalog
from .odpc.catalog import text_value
from .odpg import build_graph, build_graph_explorer_html, load_graph
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
from . import portfolio_budget as _portfolio_budget
from . import portfolio_privacy as _portfolio_privacy
from .portfolio_sources import (
    SOURCE_WARNING_KEY,
    changed_source_lanes as _changed_source_lanes,
    collect_source_files as _collect_source_files,
    collect_source_lanes as _collect_source_lanes,
    resolve_source_lane_paths as _resolve_source_lane_paths,
    source_change_warnings as _source_change_warnings,
    source_changes as _source_changes,
    source_extraction_warnings as _source_extraction_warnings,
    source_hashes as _source_hashes,
    source_hashes_by_lane as _source_hashes_by_lane,
)

DEFAULT_PORTFOLIO_HTML = "index.html"
DEFAULT_EXECUTIVE_SUMMARY = "executive-summary.yaml"
EXECUTIVE_SUMMARY_SCHEMA = (
    "https://opendataproducts.org/sdk/portfolio-executive-summary/v1"
)
PORTFOLIO_ICON_ASSET_DIR = Path("assets") / "executive_summary_icons"
PORTFOLIO_LOCALIZATION_BATCH_CHARS = 3500
PORTFOLIO_LOCALIZATION_BATCH_ITEMS = 50
PORTFOLIO_SOURCE_CHUNK_CHARS = _portfolio_budget.PORTFOLIO_SOURCE_CHUNK_CHARS
PORTFOLIO_SOURCE_PROMPT_CHARS = _portfolio_budget.PORTFOLIO_SOURCE_PROMPT_CHARS
PORTFOLIO_PROMPT_OVERHEAD_RESERVE_CHARS = (
    _portfolio_budget.PORTFOLIO_PROMPT_OVERHEAD_RESERVE_CHARS
)
PORTFOLIO_PRIVACY_DISABLED_WARNING = (
    _portfolio_privacy.PORTFOLIO_PRIVACY_DISABLED_WARNING
)
PortfolioBuildClient = Callable[[str, str], str]
PortfolioLocalizationClient = Callable[[str, str], str]
_chunk_source_text = _portfolio_budget.chunk_source_text
_estimated_word_count = _portfolio_budget.estimated_word_count
_int_value = _portfolio_budget.int_value
_prompt_budget_guarded_client = _portfolio_budget.prompt_budget_guarded_client
_reduce_source_lanes_for_prompt = _portfolio_budget.reduce_source_lanes_for_prompt
_split_long_text = _portfolio_budget.split_long_text
_apply_source_privacy = _portfolio_privacy.apply_source_privacy
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
EXECUTIVE_SUMMARY_CONFIDENCE_VALUES = {"high", "medium", "low"}
EXECUTIVE_SUMMARY_SWOT_BUCKETS = (
    "strengths",
    "weaknesses",
    "opportunities",
    "threats",
)
EXECUTIVE_SUMMARY_CARD_ICONS = {
    "primary-focus": "priority_1_trophy.png",
    "secondary-focus": "priority_2_growth.png",
    "risk-focus": "risk_warning.png",
    "readiness-focus": "readiness_clipboard.png",
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
    context_format: str = "markdown",
    source_budget: Optional[PortfolioSourceBudget] = None,
    source_privacy: Optional[PortfolioPrivacySettings] = None,
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
    source_budget_settings = source_budget or PortfolioSourceBudget(
        max_source_chars=PORTFOLIO_SOURCE_CHUNK_CHARS,
        max_prompt_chars=PORTFOLIO_SOURCE_PROMPT_CHARS,
    )
    privacy_settings = source_privacy or PortfolioPrivacySettings()
    private_process_lanes, source_privacy_report = _apply_source_privacy(
        process_lanes,
        privacy_settings=privacy_settings,
    )
    reduced_process_lanes, source_budget_report = _reduce_source_lanes_for_prompt(
        private_process_lanes,
        max_source_chars=source_budget_settings.max_source_chars,
        max_prompt_chars=source_budget_settings.max_prompt_chars,
        prompt_overhead_chars=PORTFOLIO_PROMPT_OVERHEAD_RESERVE_CHARS,
    )
    prompt_budget_report: Dict[str, object] = {
        "method": "final-prompt-char-gate",
        "maxPromptChars": source_budget_settings.max_prompt_chars,
        "checkedPromptCount": 0,
        "maxObservedPromptChars": 0,
    }
    workspace_title = _resolve_workspace_title(title, previous_state)
    llm_call_count = 0
    llm_phases: List[str] = []
    written: List[Tuple[Path, str]] = []
    if _has_processable_sources(reduced_process_lanes):
        if client is None:
            raise ValueError("A model client is required to build a portfolio.")
        guarded_client = _prompt_budget_guarded_client(
            client,
            max_prompt_chars=source_budget_settings.max_prompt_chars,
            report=prompt_budget_report,
        )
        lane_phases = _generate_portfolio_lane_fragments(
            root,
            reduced_process_lanes,
            guarded_client,
            model,
        )
        llm_call_count += len(lane_phases)
        llm_phases.extend(lane_phases)
        catalog = _catalog_from_fragments(root)
        catalog = _apply_catalog_title(catalog, workspace_title)
        product_specs = _load_product_specs(root)
        written.extend(_sync_product_references_from_odps(root, catalog, product_specs))
        written.append(_write_yaml(root / "odpc" / "catalog.yaml", catalog))
        graph = build_graph(
            root / "odpc" / "fragments",
            output_path=root / "odpg" / "graph.yaml",
            client=guarded_client,
            model=model,
        )
        llm_call_count += 1
        llm_phases.append("graph")
        written.append(_write_yaml(root / "odpg" / "graph.yaml", graph))
        plan = _plan_from_workspace(root)
    else:
        plan = _plan_from_workspace(root)
    if has_previous_sources:
        plan = _ensure_changed_signal_source_coverage(plan, lanes, source_changes)
    plan = _reconcile_plan_identity(plan, previous_state)
    plan = _normalize_portfolio_plan(plan)
    plan = _apply_workspace_title(plan, workspace_title)
    if _has_processable_sources(reduced_process_lanes):
        if client is None:
            raise ValueError("A model client is required to build a portfolio.")
        guarded_client = _prompt_budget_guarded_client(
            client,
            max_prompt_chars=source_budget_settings.max_prompt_chars,
            report=prompt_budget_report,
        )
        summary_prompt = render_portfolio_executive_summary_prompt(plan)
        llm_call_count += 1
        llm_phases.append("executiveSummary")
        raw_summary = guarded_client(summary_prompt, model)
        executive_summary, repaired = _parse_executive_summary_with_repair(
            raw_summary, guarded_client, model
        )
        if repaired:
            llm_call_count += 1
            llm_phases.append("executiveSummaryRepair")
        plan["executiveSummary"] = executive_summary
    extraction_warnings = _source_extraction_warnings(lanes)
    warnings = [str(item) for item in plan.get("warnings", []) if item]
    warnings.extend(extraction_warnings)
    warnings.extend(_source_change_warnings(source_changes))
    warnings.extend(str(item) for item in source_budget_report.get("warnings", []))
    warnings.extend(str(item) for item in source_privacy_report.get("warnings", []))

    created: List[str] = []
    updated: List[str] = []
    unchanged: List[str] = []
    written.extend(
        _write_portfolio_metadata_artifacts(
            root,
            plan,
            lanes,
            lane_paths=lane_paths,
            title=workspace_title,
            model=model,
            context_format=context_format,
        )
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
    source_counts = {
        name: len(files) for name, files in lanes.items() if name != SOURCE_WARNING_KEY
    }
    processed_source_counts = {
        name: len(files)
        for name, files in process_lanes.items()
        if name != SOURCE_WARNING_KEY
    }
    result: Dict[str, object] = {
        "spec": "portfolio",
        "kind": run_kind,
        "workspace": str(root),
        "html": str(root / DEFAULT_PORTFOLIO_HTML),
        "snapshot": str(snapshot) if snapshot is not None else None,
        "sourceCounts": source_counts,
        "processedSourceCounts": processed_source_counts,
        "contextFormat": context_format,
        "sourceBudget": source_budget_report,
        "sourcePrivacy": source_privacy_report,
        "promptBudget": prompt_budget_report,
        "sourceExtraction": {
            "warnings": extraction_warnings,
            "skippedSourceCount": len(extraction_warnings),
        },
        "llmCallCount": llm_call_count,
        "llmPhases": llm_phases,
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
    context_format: str = "markdown",
    source_budget: Optional[PortfolioSourceBudget] = None,
    source_privacy: Optional[PortfolioPrivacySettings] = None,
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
        context_format=context_format,
        source_budget=source_budget,
        source_privacy=source_privacy,
    )


def inspect_portfolio_intake(
    *,
    objectives: Optional[Union[str, Path]] = None,
    use_cases: Optional[Union[str, Path]] = None,
    signals: Optional[Union[str, Path]] = None,
    products: Optional[Union[str, Path]] = None,
    source_budget: Optional[PortfolioSourceBudget] = None,
    source_privacy: Optional[PortfolioPrivacySettings] = None,
) -> Dict[str, object]:
    """Inspect portfolio source intake without calling an LLM."""
    lanes = _collect_source_lanes(
        objectives=Path(objectives) if objectives is not None else None,
        use_cases=Path(use_cases) if use_cases is not None else None,
        signals=Path(signals) if signals is not None else None,
        products=Path(products) if products is not None else None,
    )
    source_budget_settings = source_budget or PortfolioSourceBudget(
        max_source_chars=PORTFOLIO_SOURCE_CHUNK_CHARS,
        max_prompt_chars=PORTFOLIO_SOURCE_PROMPT_CHARS,
    )
    privacy_settings = source_privacy or PortfolioPrivacySettings()
    private_lanes, source_privacy_report = _apply_source_privacy(
        lanes,
        privacy_settings=privacy_settings,
    )
    reduced_lanes, source_budget_report = _reduce_source_lanes_for_prompt(
        private_lanes,
        max_source_chars=source_budget_settings.max_source_chars,
        max_prompt_chars=source_budget_settings.max_prompt_chars,
        prompt_overhead_chars=PORTFOLIO_PROMPT_OVERHEAD_RESERVE_CHARS,
    )
    reduced_by_id = {
        str(source.get("sourceId")): source
        for files in reduced_lanes.values()
        for source in files
        if source.get("sourceId")
    }
    sources = []
    for lane_name, files in private_lanes.items():
        if lane_name == SOURCE_WARNING_KEY:
            continue
        for source in files:
            source_id = str(source.get("sourceId", ""))
            reduced = reduced_by_id.get(source_id, {})
            extracted_chars = len(str(source.get("text", "")))
            included_chars = len(str(reduced.get("text", "")))
            chunk_count = _int_value(reduced.get("chunkCount"), default=1)
            included_chunk_count = _int_value(
                reduced.get("includedChunkCount"), default=1
            )
            omitted_chunk_count = _int_value(
                reduced.get("omittedChunkCount"), default=0
            )
            status = "included"
            if omitted_chunk_count:
                status = "reduced"
            if extracted_chars == 0:
                status = "empty"
            sources.append(
                {
                    "lane": lane_name,
                    "path": source.get("path", ""),
                    "sourceId": source_id,
                    "sourceType": source.get("sourceType", ""),
                    "detectionMethod": source.get("detectionMethod", ""),
                    "sourceUnit": source.get("sourceUnit", ""),
                    "sourceUnitId": source.get("sourceUnitId", ""),
                    "preview": str(source.get("text", ""))[:500],
                    "extractedChars": extracted_chars,
                    "estimatedWords": _estimated_word_count(
                        str(source.get("text", ""))
                    ),
                    "includedChars": included_chars,
                    "omittedChars": max(extracted_chars - included_chars, 0),
                    "chunkCount": chunk_count,
                    "includedChunkCount": included_chunk_count,
                    "omittedChunkCount": omitted_chunk_count,
                    "status": status,
                }
            )

    source_counts = {
        name: len(files) for name, files in lanes.items() if name != SOURCE_WARNING_KEY
    }
    warnings = _source_extraction_warnings(lanes)
    warnings.extend(str(item) for item in source_budget_report.get("warnings", []))
    warnings.extend(str(item) for item in source_privacy_report.get("warnings", []))
    skipped_sources = [
        {
            "lane": source.get("lane", ""),
            "path": source.get("path", ""),
            "sourceId": source.get("sourceId", ""),
            "sourceType": source.get("sourceType", ""),
            "detectionMethod": source.get("detectionMethod", ""),
            "warning": source.get("warning", ""),
            "status": "skipped",
        }
        for source in lanes.get(SOURCE_WARNING_KEY, [])
    ]
    return {
        "spec": "portfolio",
        "kind": "PortfolioIntake",
        "llmCallCount": 0,
        "sourceCounts": source_counts,
        "sourceBudget": source_budget_report,
        "sourcePrivacy": source_privacy_report,
        "sourceExtraction": {
            "warnings": _source_extraction_warnings(lanes),
            "skippedSourceCount": len(skipped_sources),
            "skippedSources": skipped_sources,
        },
        "sources": sources,
        "warnings": warnings,
    }


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
    localization_qa = _localization_qa(source_strings, translations, target_languages)
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
        "localizationQa": localization_qa,
        "valid": _valid_portfolio(validation_results),
    }


def render_portfolio_build_prompt(lanes: Dict[str, List[Dict[str, str]]]) -> str:
    """Render the internal portfolio build prompt from source lane content."""
    reduced_lanes, _budget = _reduce_source_lanes_for_prompt(lanes)
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
        "- Do not emit executiveSummary in this phase. The SDK generates Executive Summary in a separate phase from normalized artifacts.",
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
    for lane_name, files in reduced_lanes.items():
        sections.append(f"\n# Source lane: {lane_name}")
        if not files:
            sections.append("(no files)")
            continue
        for source in files:
            sections.append(f"\n## {source['path']}\n{source['text']}")
    return "\n".join(sections)


def render_portfolio_executive_summary_prompt(plan: Dict[str, Any]) -> str:
    """Render the Executive Summary prompt from normalized portfolio artifacts."""
    context = deepcopy(plan)
    context.pop("executiveSummary", None)
    return "\n".join(
        [
            "# Create Portfolio Executive Summary",
            "Create one PortfolioExecutiveSummary YAML document from the normalized portfolio evidence.",
            "Return only YAML. Do not include markdown fences, prose, or comments.",
            "",
            "Use this exact top-level shape:",
            "schema: https://opendataproducts.org/sdk/portfolio-executive-summary/v1",
            "kind: PortfolioExecutiveSummary",
            "portfolioPosition:",
            "  headline: Retention is the clearest first funding decision; partner expansion is a second path to validate.",
            "  narrative: Short business-facing narrative grounded in the portfolio evidence.",
            "priorityBriefing:",
            "  recommendation: Fund the strongest validated workflow first. Validate the next growth path. Strengthen weak evidence before final prioritization.",
            "  primaryFocus:",
            "    label: Priority 1",
            "    title: 'Focus first: strongest workflow validation'",
            "    dashboardTitle: Retention validation",
            "    message: One sentence explaining why this is the clearest funding candidate.",
            "    dashboardMessage: Retention is the strongest first funding candidate.",
            "    action: One sentence stating what leadership should fund or validate first.",
            "    dashboardAction: Fund validation first.",
            "    rationaleTitle: Why this is first",
            "    rationale:",
            "      - Strongest objective, use case, and product alignment",
            "    confidence: high",
            "    evidenceType: direct",
            "    evidence:",
            "      - type: businessObjective",
            "        label: Business-facing evidence label",
            "        id: OBJ-STABLE-ID",
            "  secondaryFocus:",
            "    label: Priority 2",
            "    title: 'Validate next: second growth path'",
            "    dashboardTitle: Partner expansion",
            "    message: One sentence explaining why this remains in discussion but is not first.",
            "    dashboardMessage: Partner expansion is promising but not yet first priority.",
            "    action: One sentence stating what leadership should validate next.",
            "    dashboardAction: Validate the business case next.",
            "    rationaleTitle: Why this is second",
            "    rationale:",
            "      - Has objective and use case alignment",
            "    confidence: medium",
            "    evidenceType: inferred",
            "    evidence:",
            "      - type: useCase",
            "        label: Business-facing evidence label",
            "        id: UC-STABLE-ID",
            "  blocker:",
            "    label: Risk",
            "    title: 'Do not ignore: main prioritization risk'",
            "    dashboardTitle: Signal coverage",
            "    message: One sentence explaining what could distort the funding decision.",
            "    dashboardMessage: Thin signal coverage may overstate prioritization confidence.",
            "    action: One sentence stating what to strengthen before final prioritization.",
            "    dashboardAction: Improve coverage before final prioritization.",
            "    rationaleTitle: Why this matters",
            "    rationale:",
            "      - Weak evidence can distort funding decisions",
            "    confidence: low",
            "    evidenceType: inferred",
            "    evidence:",
            "      - type: signal",
            "        label: Business-facing evidence label",
            "        id: SIG-STABLE-ID",
            "  readinessCheck:",
            "    label: Readiness",
            "    title: 'Before build starts: commercial readiness review'",
            "    dashboardTitle: Commercial review",
            "    message: One sentence explaining what still needs human review.",
            "    dashboardMessage: The product still needs business readiness review.",
            "    action: One sentence stating the readiness review leadership should require.",
            "    dashboardAction: Confirm readiness before build.",
            "    checklist:",
            "      - Business owner confirmed",
            "      - Value model reviewed",
            "      - Delivery owner assigned",
            "      - Operating model clear",
            "      - Production readiness reviewed",
            "    confidence: medium",
            "    evidenceType: inferred",
            "    evidence:",
            "      - type: productReference",
            "        label: Business-facing evidence label",
            "        id: PR-STABLE-ID",
            "leadershipDecisions:",
            "  - id: DECIDE-STABLE-ID",
            "    question: Leadership decision question grounded in evidence.",
            "    decisionType: invest",
            "    urgency: medium",
            "    evidenceRefs:",
            "      - type: businessObjective",
            "        id: OBJ-STABLE-ID",
            "evidenceGaps:",
            "  - id: GAP-STABLE-ID",
            "    statement: Missing evidence needed before a leadership decision.",
            "    evidenceRefs:",
            "      - type: productReference",
            "        id: PR-STABLE-ID",
            "confidenceNotes:",
            "  - Priority items marked as inferred need human review before business action.",
            "",
            "Rules:",
            "- Use only IDs and facts present in the normalized portfolio evidence below.",
            "- Do not invent revenue, cost, customer, compliance, or risk claims.",
            "- Keep dashboardTitle, dashboardMessage, and dashboardAction compact.",
            "- Make priorityBriefing decision-support material, not an approved strategy.",
            "- Every priorityBriefing evidence item must include type, label, and id.",
            "- Prefer direct evidence only when objective, use case, and product alignment is explicit.",
            "",
            "Normalized portfolio evidence:",
            yaml.safe_dump(context, sort_keys=False, allow_unicode=True),
        ]
    )


def _parse_portfolio_plan_with_repair(
    raw_output: str,
    client: PortfolioBuildClient,
    model: str,
) -> Tuple[Dict[str, Any], bool]:
    try:
        return parse_portfolio_plan(raw_output), False
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
        return plan, True


def _parse_executive_summary_with_repair(
    raw_output: str,
    client: PortfolioBuildClient,
    model: str,
) -> Tuple[Dict[str, Any], bool]:
    try:
        return parse_executive_summary(raw_output), False
    except ValueError as original_error:
        repair_prompt = _render_executive_summary_repair_prompt(
            raw_output, str(original_error)
        )
        repaired_output = client(repair_prompt, model)
        try:
            summary = parse_executive_summary(repaired_output)
        except ValueError as repair_error:
            raise ValueError(
                f"{original_error}\nRepair attempt also failed: {repair_error}"
            ) from repair_error
        notes = summary.setdefault("confidenceNotes", [])
        if isinstance(notes, list):
            notes.append("Executive Summary YAML required syntax repair.")
        return summary, True


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


def _render_executive_summary_repair_prompt(raw_output: str, parser_error: str) -> str:
    return "\n".join(
        [
            "# Repair Portfolio Executive Summary YAML",
            "Repair one PortfolioExecutiveSummary YAML document.",
            "Return only YAML. Do not include markdown fences, prose, or comments.",
            "Preserve the generated facts, evidence IDs, and leadership wording.",
            "Fix only YAML syntax, indentation, incomplete keys, and malformed mappings.",
            "Do not add unsupported facts. If a broken value cannot be recovered,",
            "drop that broken field and preserve the rest of the summary.",
            "",
            "Parser error:",
            parser_error,
            "",
            "Malformed executive summary YAML:",
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


def parse_executive_summary(raw_output: str) -> Dict[str, Any]:
    """Parse a model-generated portfolio executive summary YAML mapping."""
    text = _extract_yaml_text(raw_output)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Executive Summary YAML could not be parsed: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Executive Summary must contain a YAML object at the root")
    if data.get("executiveSummary") and isinstance(data.get("executiveSummary"), dict):
        data = data["executiveSummary"]
    data.setdefault("kind", "PortfolioExecutiveSummary")
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
    model: Optional[str] = None,
) -> List[Tuple[Path, str]]:
    written: List[Tuple[Path, str]] = []
    written.append(_write_yaml(root / "portfolio.yaml", _portfolio_map(plan, lanes)))
    executive_summary = _executive_summary_document(plan, title=title, model=model)
    if executive_summary is not None:
        written.append(_write_yaml(root / DEFAULT_EXECUTIVE_SUMMARY, executive_summary))
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


def _write_portfolio_metadata_artifacts(
    root: Path,
    plan: Dict[str, Any],
    lanes: Dict[str, List[Dict[str, str]]],
    lane_paths: Optional[Dict[str, str]] = None,
    title: Optional[str] = None,
    model: Optional[str] = None,
    context_format: str = "markdown",
) -> List[Tuple[Path, str]]:
    written: List[Tuple[Path, str]] = []
    written.append(_write_yaml(root / "portfolio.yaml", _portfolio_map(plan, lanes)))
    executive_summary = _executive_summary_document(plan, title=title, model=model)
    if executive_summary is not None:
        written.append(_write_yaml(root / DEFAULT_EXECUTIVE_SUMMARY, executive_summary))
    written.append(
        _write_yaml(
            root / "portfolio-state.yaml",
            _portfolio_state(plan, lanes, lane_paths or {}, title, context_format),
        )
    )
    return written


def _generate_portfolio_lane_fragments(
    root: Path,
    lanes: Dict[str, List[Dict[str, str]]],
    client: PortfolioBuildClient,
    model: str,
) -> List[str]:
    from .generation import generate_local_artifacts_for_kind

    fragments_dir = root / "odpc" / "fragments"
    lane_specs = (
        ("objectives", "objective", "objective"),
        ("useCases", "use-case", "useCase"),
        ("signals", "signal", "signal"),
        ("products", "product-reference", "productReference"),
    )
    phases: List[str] = []
    for lane_name, artifact_kind, phase in lane_specs:
        for source in lanes.get(lane_name, []):
            source_path = source.get("path")
            if not source_path:
                continue
            generation_source = _write_reduced_generation_source(
                root, lane_name, source
            )
            generate_local_artifacts_for_kind(
                artifact_kind,
                generation_source,
                fragments_dir,
                model=model,
                client=client,
            )
            phases.append(phase)
    return phases


def _write_reduced_generation_source(
    root: Path,
    lane_name: str,
    source: Dict[str, str],
) -> Path:
    source_id = source.get("sourceId") or source.get("path") or "source"
    text = source.get("text", "")
    digest = hashlib.sha256((source_id + "\n" + text).encode("utf-8")).hexdigest()
    safe_lane = re.sub(r"[^A-Za-z0-9_-]+", "-", lane_name).strip("-") or "lane"
    original_name = Path(source.get("path", "source")).stem or "source"
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", original_name).strip("-") or "source"
    output = (
        root
        / ".portfolio-sources"
        / "reduced"
        / f"{safe_lane}-{safe_name}-{digest[:16]}.md"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            f"Original source path: {source.get('path', '')}",
            f"Source ID: {source_id}",
            f"Source type: {source.get('sourceType', '')}",
            f"Chunks included: {source.get('includedChunkCount', '1')} of {source.get('chunkCount', '1')}",
            f"Chunks omitted: {source.get('omittedChunkCount', '0')}",
            "",
            text.strip(),
        ]
    ).strip()
    output.write_text(content + "\n", encoding="utf-8")
    return output


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


def _executive_summary_document(
    plan: Dict[str, Any],
    *,
    title: Optional[str],
    model: Optional[str],
) -> Optional[Dict[str, Any]]:
    summary = plan.get("executiveSummary")
    if not isinstance(summary, dict):
        return None
    metadata = (
        summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    )
    plan_metadata = (
        plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    )
    workspace_title = title or _text(plan_metadata.get("name"))
    document: Dict[str, Any] = {
        "schema": summary.get("schema") or EXECUTIVE_SUMMARY_SCHEMA,
        "kind": summary.get("kind") or "PortfolioExecutiveSummary",
        "metadata": {
            "generatedAt": metadata.get("generatedAt")
            or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generatedBy": metadata.get("generatedBy") or "open-data-products",
            "sdkVersion": metadata.get("sdkVersion") or __version__,
        },
    }
    if model:
        document["metadata"]["model"] = model
    elif metadata.get("model"):
        document["metadata"]["model"] = metadata["model"]
    if workspace_title:
        document["metadata"]["workspaceTitle"] = workspace_title
    for key in (
        "portfolioPosition",
        "priorityBriefing",
        "swot",
        "leadershipDecisions",
        "evidenceGaps",
        "confidenceNotes",
        "leadershipSummary",
    ):
        value = summary.get(key)
        if value is not None:
            document[key] = value
    return document


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
    portfolio = {
        "metadata": {
            "id": metadata.get("id", "generated-portfolio"),
            "name": metadata.get("name", "Generated Portfolio"),
            "description": metadata.get(
                "description", "Generated from portfolio source lanes."
            ),
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sdkVersion": __version__,
        },
        "sources": {
            name: {"count": len(files)}
            for name, files in lanes.items()
            if name != SOURCE_WARNING_KEY
        },
        "warnings": [str(item) for item in plan.get("warnings", []) if item],
    }
    if isinstance(plan.get("executiveSummary"), dict):
        portfolio["artifacts"] = {"executiveSummary": DEFAULT_EXECUTIVE_SUMMARY}
    return portfolio


def _portfolio_state(
    plan: Dict[str, Any],
    lanes: Dict[str, List[Dict[str, str]]],
    lane_paths: Dict[str, str],
    title: Optional[str],
    context_format: str = "markdown",
) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "version": 1,
        "contextFormat": context_format,
        "sourceLanePaths": dict(lane_paths),
        "sources": {
            name: [
                {
                    "sourceId": source["sourceId"],
                    "path": source["path"],
                    "sha256": source["sha256"],
                }
                for source in files
            ]
            for name, files in lanes.items()
            if name != SOURCE_WARNING_KEY
        },
        "identityRegistry": _identity_registry(plan),
    }
    if title:
        state["title"] = title
    return state


def _has_processable_sources(lanes: Dict[str, List[Dict[str, str]]]) -> bool:
    """Return whether any real source lane has files to process."""
    return any(files for name, files in lanes.items() if name != SOURCE_WARNING_KEY)


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


def _apply_catalog_title(
    catalog: Dict[str, Any], title: Optional[str]
) -> Dict[str, Any]:
    if not title:
        return catalog
    catalog_root = catalog.setdefault("catalog", {})
    if not isinstance(catalog_root, dict):
        return catalog
    metadata = catalog_root.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        catalog_root["metadata"] = metadata
    metadata["name"] = {"en": title}
    return catalog


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
    executive_summary = delta.get("executiveSummary")
    if isinstance(executive_summary, dict):
        merged["executiveSummary"] = executive_summary
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


def _filter_delta_plan_by_changed_lanes(
    delta: Dict[str, Any],
    process_lanes: Dict[str, List[Dict[str, str]]],
    existing: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(delta, dict):
        return {}
    filtered: Dict[str, Any] = {}
    for key in ("metadata", "warnings", "executiveSummary"):
        value = delta.get(key)
        if value is not None:
            filtered[key] = value

    lane_collections = (
        ("objectives", "businessObjectives"),
        ("useCases", "useCases"),
        ("signals", "signals"),
        ("products", "products"),
    )
    accepted_ids: Set[str] = set()
    for lane, collection in lane_collections:
        if process_lanes.get(lane):
            items = _list(delta, collection)
            if items:
                filtered[collection] = items
                accepted_ids.update(_plan_item_ids(collection, items))

    existing_ids = _plan_ids(existing)
    discarded_ids = _plan_ids(delta) - accepted_ids
    graph_edges = []
    for edge in _list(delta, "graphEdges"):
        source = _text(edge.get("source") or edge.get("from"))
        target = _text(edge.get("target") or edge.get("to"))
        if not ({source, target} & accepted_ids):
            continue
        if ({source, target} & discarded_ids) - accepted_ids:
            continue
        if (
            source in accepted_ids | existing_ids
            and target in accepted_ids | existing_ids
        ):
            graph_edges.append(edge)
    if graph_edges:
        filtered["graphEdges"] = graph_edges
    return filtered


def _plan_ids(plan: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for collection in ("businessObjectives", "useCases", "signals", "products"):
        ids.update(_plan_item_ids(collection, _list(plan, collection)))
    return ids


def _plan_item_ids(collection: str, items: List[Dict[str, Any]]) -> Set[str]:
    ids: Set[str] = set()
    for item in items:
        if collection == "products":
            reference = item.get("productReference")
            if isinstance(reference, dict):
                for key in ("id", "productID"):
                    item_id = _text(reference.get(key))
                    if item_id:
                        ids.add(item_id)
            continue
        item_id = _text(item.get("id"))
        if item_id:
            ids.add(item_id)
    return ids


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
    counts = {
        "businessObjectives": len(_list(plan, "businessObjectives")),
        "useCases": len(_list(plan, "useCases")),
        "signals": len(_list(plan, "signals")),
        "productReferences": len(_list(plan, "products")),
        "odpsProducts": sum(
            1
            for product in _list(plan, "products")
            if isinstance(product.get("odpsProduct"), dict)
        ),
        "graphEdges": len(_list(plan, "graphEdges")),
    }
    counts.update(_executive_summary_counts(plan.get("executiveSummary")))
    return counts


def _workspace_artifact_counts(data: Dict[str, Any]) -> Dict[str, int]:
    catalog = data["catalog"].get("catalog", {})
    graph = data["graph"].get("graph", {})
    counts = {
        "businessObjectives": _count(catalog, "businessObjectives"),
        "useCases": _count(catalog, "useCases"),
        "signals": _count(catalog, "signals"),
        "productReferences": _count(catalog, "productReferences"),
        "odpsProducts": len(data["products"]),
        "graphNodes": _count(graph, "nodes"),
        "graphEdges": _count(graph, "edges"),
    }
    counts.update(_executive_summary_counts(data.get("executive_summary")))
    return counts


def _executive_summary_counts(value: Any) -> Dict[str, int]:
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
    catalog_path = root / "odpc" / "catalog.yaml"
    graph_path = root / "odpg" / "graph.yaml"
    portfolio_path = root / "portfolio.yaml"
    executive_summary_path = root / DEFAULT_EXECUTIVE_SUMMARY
    i18n = _load_portfolio_i18n(root)
    warnings: List[str] = []
    portfolio = _load_optional_mapping(portfolio_path)
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
