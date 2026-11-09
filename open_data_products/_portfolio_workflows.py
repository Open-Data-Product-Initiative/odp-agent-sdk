"""Portfolio generation, synchronization, and localization workflows."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

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
from ._portfolio_plan import (
    _artifact_counts,
    _apply_catalog_title,
    _catalog_document,
    _catalog_from_fragments,
    _ensure_changed_signal_source_coverage,
    _file_id,
    _graph_document,
    _identity_registry,
    _normalize_portfolio_plan,
    _plan_from_workspace,
    _plan_from_catalog,
    _reconcile_plan_identity,
    _string_list,
    _set_odps_product_id,
    _sync_product_references_from_odps,
    _workspace_artifact_counts,
)
from ._portfolio_normalization import (
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
    _html_text_items,
    _i18n_html_translations,
    _load_portfolio_i18n,
    _localization_qa,
    _localized_html_filename,
    _merge_languages,
    _normalize_language_tag,
    _parse_language_tags,
    _portfolio_validation_results,
    _prune_i18n_html_translations,
    _translate_html_text,
    _valid_portfolio,
    load_portfolio_workspace,
    render_portfolio,
    render_portfolio_html,
)
from ._portfolio_html import _normalize_product_spec_files
from ._portfolio_values import (
    as_list as _list,
    path_id as _path_id,
    text as _text,
)
from ._portfolio_workspace import (
    load_optional_mapping as _load_optional_mapping,
    load_product_specs as _load_product_specs,
    portfolio_versions as _portfolio_versions,
    product_details as _product_details,
    write_text as _write_text,
    write_yaml as _write_yaml,
)
from .generation.models import PortfolioPrivacySettings, PortfolioSourceBudget
from .odpg import build_graph
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
