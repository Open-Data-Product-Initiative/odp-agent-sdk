"""Portfolio generation, synchronization, and localization workflows."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import yaml

from . import __version__
from ._io import load_mapping
from ._portfolio_models import (
    PortfolioBuildClient,
    PortfolioBuildRequest,
    PortfolioBuildResult,
    PortfolioLocalizationClient,
    PortfolioSourceLanes,
)
from ._portfolio_normalization import (
    _normalize_enum,
    normalize_generated_odps_product as _normalize_generated_odps_product,
)
from ._portfolio_prompting import (
    chunk_localization_strings as _chunk_localization_strings,
    parse_executive_summary,
    parse_portfolio_localization,
    parse_portfolio_plan,
    render_executive_summary_repair_prompt as _render_executive_summary_repair_prompt,
    render_portfolio_executive_summary_prompt,
    render_portfolio_localization_prompt as _render_portfolio_localization_prompt,
    render_portfolio_localization_repair_prompt as _render_portfolio_localization_repair_prompt,
    render_portfolio_plan_repair_prompt as _render_portfolio_plan_repair_prompt,
)
from ._portfolio_rendering import (
    DEFAULT_PORTFOLIO_HTML,
    PORTFOLIO_ICON_ASSET_DIR,
    EXECUTIVE_SUMMARY_CARD_ICONS,
    EXECUTIVE_SUMMARY_SWOT_BUCKETS,
    _html_text_items,
    _i18n_html_translations,
    _load_portfolio_i18n,
    _localization_qa,
    _localized_html_filename,
    _merge_languages,
    _normalize_language_tag,
    _normalize_product_spec_files,
    _parse_language_tags,
    _portfolio_validation_results,
    _prune_i18n_html_translations,
    _translate_html_text,
    _valid_portfolio,
    load_portfolio_workspace,
    render_portfolio,
    render_portfolio_html,
)
from ._portfolio_values import (
    as_list as _list,
    count as _count,
    path_id as _path_id,
    text as _text,
    title_from_text as _title_from_text,
)
from ._portfolio_workspace import (
    empty_catalog as _empty_catalog,
    empty_graph as _empty_graph,
    load_optional_mapping as _load_optional_mapping,
    load_product_specs as _load_product_specs,
    portfolio_versions as _portfolio_versions,
    product_details as _product_details,
    write_text as _write_text,
    write_yaml as _write_yaml,
)
from .generation.models import PortfolioPrivacySettings, PortfolioSourceBudget
from .odpc import load_catalog
from .odpg import build_graph, load_graph
from . import portfolio_budget as _portfolio_budget
from . import portfolio_privacy as _portfolio_privacy
from .portfolio_sources import (
    SOURCE_WARNING_KEY,
    changed_source_lanes as _changed_source_lanes,
    collect_source_lanes as _collect_source_lanes,
    resolve_source_lane_paths as _resolve_source_lane_paths,
    source_change_warnings as _source_change_warnings,
    source_changes as _source_changes,
    source_extraction_warnings as _source_extraction_warnings,
    source_hashes_by_lane as _source_hashes_by_lane,
)

DEFAULT_EXECUTIVE_SUMMARY = "executive-summary.yaml"
EXECUTIVE_SUMMARY_SCHEMA = (
    "https://opendataproducts.org/sdk/portfolio-executive-summary/v1"
)
PORTFOLIO_SOURCE_CHUNK_CHARS = _portfolio_budget.PORTFOLIO_SOURCE_CHUNK_CHARS
PORTFOLIO_SOURCE_PROMPT_CHARS = _portfolio_budget.PORTFOLIO_SOURCE_PROMPT_CHARS
PORTFOLIO_PROMPT_OVERHEAD_RESERVE_CHARS = (
    _portfolio_budget.PORTFOLIO_PROMPT_OVERHEAD_RESERVE_CHARS
)
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


class PortfolioPipeline:
    """Public application API for portfolio builds."""

    _PROCESSING_MODES = {"lane-by-lane", "bundled"}

    def build(self, request: PortfolioBuildRequest) -> PortfolioBuildResult:
        """Build a portfolio workspace from a typed application request."""
        if request.processing_mode not in self._PROCESSING_MODES:
            allowed = ", ".join(sorted(self._PROCESSING_MODES))
            raise ValueError(
                f"Unsupported portfolio processing mode: "
                f"{request.processing_mode}. Expected one of: {allowed}"
            )
        lanes = request.normalized_source_lanes()
        payload = _build_portfolio_mapping(
            request.workspace,
            **lanes.to_build_kwargs(),
            title=request.title,
            client=request.client,
            model=request.model,
            run_kind=request.run_kind,
            process_all_sources=request.process_all_sources,
            context_format=request.context_format,
            source_budget=request.source_budget,
            source_privacy=request.privacy,
        )
        return PortfolioBuildResult.from_mapping(payload, model=request.model)


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
    result = PortfolioPipeline().build(
        PortfolioBuildRequest(
            workspace=workspace,
            source_lanes=PortfolioSourceLanes(
                objectives=objectives,
                use_cases=use_cases,
                signals=signals,
                products=products,
            ),
            title=title,
            client=client,
            model=model,
            run_kind=run_kind,
            process_all_sources=process_all_sources,
            context_format=context_format,
            source_budget=source_budget,
            privacy=source_privacy,
        )
    )
    return result.to_dict()


def _build_portfolio_mapping(
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
    """Build a portfolio workspace and return the legacy mapping payload."""
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
    lane_generation_warnings: List[str] = []
    written: List[Tuple[Path, str]] = []
    if _has_processable_sources(reduced_process_lanes):
        if client is None:
            raise ValueError("A model client is required to build a portfolio.")
        guarded_client = _prompt_budget_guarded_client(
            client,
            max_prompt_chars=source_budget_settings.max_prompt_chars,
            report=prompt_budget_report,
        )
        lane_phases, lane_generation_warnings = _generate_portfolio_lane_fragments(
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
    warnings.extend(lane_generation_warnings)
    warnings.extend(extraction_warnings)
    warnings.extend(_source_change_warnings(source_changes))
    warnings.extend(str(item) for item in source_budget_report.get("warnings", []))
    warnings.extend(str(item) for item in source_privacy_report.get("warnings", []))
    if warnings:
        plan["warnings"] = list(dict.fromkeys(warnings))

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
            "version": str(odps_product.get("version") or "4.2"),
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
) -> Tuple[List[str], List[str]]:
    from .generation import generate_local_artifacts_for_kind

    fragments_dir = root / "odpc" / "fragments"
    lane_specs = (
        ("objectives", "objective", "objective"),
        ("useCases", "use-case", "useCase"),
        ("signals", "signal", "signal"),
        ("products", "product-reference", "productReference"),
    )
    phases: List[str] = []
    warnings: List[str] = []
    for lane_name, artifact_kind, phase in lane_specs:
        for source in lanes.get(lane_name, []):
            source_path = source.get("path")
            if not source_path:
                continue
            generation_source = _write_reduced_generation_source(
                root, lane_name, source
            )
            try:
                reference_artifacts = generate_local_artifacts_for_kind(
                    artifact_kind,
                    generation_source,
                    fragments_dir,
                    model=model,
                    client=client,
                )
            except Exception as exc:
                if lane_name == "products":
                    fallback_id = _write_fallback_product_artifacts(
                        root, source, generation_error=str(exc)
                    )
                    phases.extend(
                        [
                            "productReference",
                            "odpsProductFacts",
                            "odpsProductMinimal",
                            "odpsProductComponents",
                            "odpsProductAssemble",
                        ]
                    )
                    warnings.append(
                        "Created fallback product reference for "
                        f"{Path(str(source_path)).name} as {fallback_id} after "
                        f"generation failed: {_compact_warning(str(exc))}"
                    )
                    continue
                warnings.append(
                    "Skipped "
                    f"{phase} generation for {Path(str(source_path)).name}: "
                    f"{_compact_warning(str(exc))}"
                )
                continue
            phases.append(phase)
            if lane_name == "products":
                try:
                    odps_artifacts = generate_local_artifacts_for_kind(
                        "odps-product",
                        generation_source,
                        root / "odps" / "products",
                        model=model,
                        client=client,
                        profile="complete-draft",
                        include_components=("dataAccess", "license"),
                    )
                except Exception as exc:
                    warnings.append(
                        "Skipped ODPS product generation for "
                        f"{Path(str(source_path)).name}: {_compact_warning(str(exc))}"
                    )
                    continue
                _normalize_generated_odps_artifacts(odps_artifacts)
                _align_generated_odps_products_to_reference(
                    odps_artifacts, reference_artifacts
                )
                phases.extend(
                    [
                        "odpsProductFacts",
                        "odpsProductMinimal",
                        "odpsProductComponents",
                        "odpsProductAssemble",
                    ]
                )
    return phases, warnings


def _normalize_generated_odps_artifacts(artifacts: List[Any]) -> None:
    """Write newly generated ODPS artifacts as normalized v4.2 documents."""
    for artifact in artifacts:
        output_path = getattr(artifact, "output_path", None)
        if not isinstance(output_path, Path):
            continue
        try:
            document = load_mapping(output_path, root_name="ODPS product")
        except ValueError:
            continue
        _normalize_generated_odps_product(document)
        _write_yaml(output_path, document)


def _write_fallback_product_artifacts(
    root: Path, source: Dict[str, str], *, generation_error: str
) -> str:
    title = _fallback_title_from_source(source, fallback="Generated Data Product")
    product_id = _slug_id(title)
    description = _fallback_description_from_source(source, title=title)
    reference = {
        "id": product_id,
        "productID": product_id,
        "productVersion": "0.1.0",
        "name": {"en": title},
        "description": {"en": description},
        "visibility": "private",
        "status": "draft",
        "type": "dataset",
        "tags": ["fallback-generated", "needs-review"],
        "productModel": {
            "standard": "ODPS",
            "version": "4.2",
            "format": "yaml",
            "$ref": f"../odps/products/{product_id}.yaml",
        },
        "x-generation": {
            "fallback": True,
            "sourcePath": source.get("path", ""),
            "reason": _compact_warning(generation_error),
        },
    }
    product = {
        "schema": "https://opendataproducts.org/v4.2/schema/odps.json",
        "version": "4.2",
        "product": {
            "details": {
                "en": {
                    "productID": product_id,
                    "name": title,
                    "description": description,
                    "visibility": "private",
                    "status": "draft",
                    "type": "dataset",
                    "valueProposition": description,
                }
            }
        },
    }
    _write_yaml(
        root / "odpc" / "fragments" / f"product_reference_{product_id}.yaml",
        {"productReference": reference},
    )
    _write_yaml(root / "odps" / "products" / f"{product_id}.yaml", product)
    return product_id


def _fallback_title_from_source(source: Dict[str, str], *, fallback: str) -> str:
    text = str(source.get("text") or "").strip()
    for line in text.splitlines():
        stripped = line.strip().strip("|").strip()
        if not stripped:
            continue
        if stripped.lower().startswith("lane:"):
            continue
        if stripped.startswith("#"):
            candidate = stripped.lstrip("#").strip()
        elif "|" in line:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            candidate = cells[0] if cells else ""
        else:
            candidate = stripped
        if candidate and not set(candidate) <= {"-", ":"}:
            return candidate[:80]
    return fallback


def _fallback_description_from_source(source: Dict[str, str], *, title: str) -> str:
    text = str(source.get("text") or "").strip()
    lines = [
        line.strip().strip("|").strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    for line in lines:
        if line.lower().startswith(("purpose", "the ", "provide ", "required ")):
            return line[:240]
    return f"{title} product draft generated from source material."


def _slug_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "generated-product"


def _compact_warning(message: str, *, limit: int = 180) -> str:
    compact = " ".join(message.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def _align_generated_odps_products_to_reference(
    artifacts: List[Any], reference_artifacts: List[Any]
) -> None:
    """Make generated ODPS specs use the ProductReference productID."""
    reference_product_id = _first_product_reference_id(reference_artifacts)
    for artifact in artifacts:
        output_path = getattr(artifact, "output_path", None)
        if not isinstance(output_path, Path) or not output_path.exists():
            continue
        try:
            document = load_mapping(output_path, root_name="ODPS product")
        except ValueError:
            continue
        details = _product_details(document)
        product_id = reference_product_id or _text(
            details.get("productID") or details.get("id")
        )
        if not product_id:
            continue
        _set_odps_product_id(document, product_id)
        target = output_path.with_name(f"{_path_id(product_id)}.yaml")
        target.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        if target != output_path:
            output_path.unlink()


def _first_product_reference_id(reference_artifacts: List[Any]) -> str:
    for artifact in reference_artifacts:
        output_path = getattr(artifact, "output_path", None)
        if not isinstance(output_path, Path) or not output_path.exists():
            continue
        try:
            document = load_mapping(output_path, root_name="ODPC product reference")
        except ValueError:
            continue
        reference = document.get("productReference")
        if not isinstance(reference, dict):
            continue
        product_id = _text(reference.get("productID") or reference.get("id"))
        if product_id:
            return product_id
    return ""


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


def _write_i18n(path: Path, document: Dict[str, Any]) -> Tuple[Path, str]:
    return _write_yaml(path, document, allow_unicode=True)


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
        _normalize_generated_odps_product(product.get("odpsProduct"))

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
        product_path = product_info.get("path")
        if _merge_product_reference_details(
            reference,
            details,
            document=document,
            product_path=product_path if isinstance(product_path, Path) else None,
        ):
            writes.append(
                _write_yaml(
                    _product_reference_fragment_path(root, reference),
                    {"productReference": reference},
                )
            )
    return writes


def _product_reference_fragment_path(root: Path, reference: Dict[str, Any]) -> Path:
    """Return the existing fragment path for one logical product reference."""
    fragments_dir = root / "odpc" / "fragments"
    reference_id = _fragment_identity(reference)
    if reference_id:
        for path in _fragment_paths(fragments_dir):
            document = load_mapping(path, root_name="ODPC fragment")
            candidate = document.get("productReference")
            if (
                isinstance(candidate, dict)
                and _fragment_identity(candidate) == reference_id
            ):
                return path
    return fragments_dir / f"product_reference_{_file_id(reference)}.yaml"


def _merge_product_reference_details(
    reference: Dict[str, Any],
    details: Dict[str, Any],
    *,
    document: Dict[str, Any],
    product_path: Optional[Path],
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
    if product_path is not None:
        expected_model = {
            "standard": "ODPS",
            "version": _text(document.get("version"), "4.2"),
            "format": "yaml",
            "$ref": "../odps/products/{0}".format(product_path.name),
        }
        if reference.get("productModel") != expected_model:
            reference["productModel"] = expected_model
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
    selected: Dict[str, Dict[str, Tuple[int, str, Dict[str, Any]]]] = {
        key: {} for key in collections
    }
    anonymous: Dict[str, List[Dict[str, Any]]] = {key: [] for key in collections}
    for path in _fragment_paths(fragments_dir):
        document = load_mapping(path, root_name="ODPC fragment")
        for source_key, target_key in keys.items():
            value = document.get(source_key)
            if isinstance(value, dict):
                identity = _fragment_identity(value)
                if not identity:
                    anonymous[target_key].append(value)
                    continue
                candidate = (path.stat().st_mtime_ns, str(path), value)
                existing = selected[target_key].get(identity)
                if existing is None or candidate[:2] > existing[:2]:
                    selected[target_key][identity] = candidate
    for target_key in collections:
        collections[target_key] = [
            candidate[2]
            for candidate in sorted(
                selected[target_key].values(), key=lambda candidate: candidate[1]
            )
        ] + anonymous[target_key]
    return collections


def _fragment_paths(fragments_dir: Path) -> List[Path]:
    """Return supported fragment paths in stable order."""
    return sorted(
        [
            *fragments_dir.glob("*.yaml"),
            *fragments_dir.glob("*.yml"),
            *fragments_dir.glob("*.json"),
        ]
    )


def _fragment_identity(value: Dict[str, Any]) -> str:
    """Return a logical identity shared by equivalent fragment files."""
    return _text(value.get("id") or value.get("productID"))


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


def _file_id(item: Dict[str, Any]) -> str:
    return _path_id(_text(item.get("id") or item.get("productID"), "item"))
