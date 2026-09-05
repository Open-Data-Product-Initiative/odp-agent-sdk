# Studio-Derived SDK Improvement Plan

## Purpose

Studio has become the best stress test for the SDK because it uses the SDK as a processing engine inside a product workflow, not as a one-off CLI. The useful signal is where Studio had to build app-owned wrappers around SDK behavior to make generation reliable, configurable, observable, and recoverable.

This plan captures SDK improvements that would make the same integration easier for Studio and for other applications embedding the SDK.

## Current Studio Usage

Studio calls the SDK through an app-owned boundary in `app/sdk/` and `app/services/sdk_adapter.py`. It does not shell out to the SDK CLI.

The current integration uses two generation modes:

- `render-only`: package and render already prepared SDK artifacts.
- `llm`: call SDK generation with a config file, currently `config/sdk-generation.config.yaml`, pointed at LiteLLM through an OpenAI-compatible provider profile.

Studio separates runtime ownership across three surfaces:

- `config/sdk-generation.config.yaml`: SDK-compatible provider adapter, portfolio source budgets, and privacy settings.
- `data/admin/ai-runtime.yaml`: Studio workload routing policy.
- `config/litellm.config.yaml`: LiteLLM provider/model registry, aliases, provider keys, retries, cooldowns, and fallbacks.

Studio maps portfolio source lanes to SDK generation inputs:

- `objectives`
- `use-cases`
- `signals`
- `products`

Studio also routes SDK-related workloads explicitly:

- `sdk_portfolio_build`
- `sdk_repair`
- `sdk_localization`

## What Studio Had To Build Around The SDK

Studio created a compatibility module because it needs SDK helpers that are not all stable public application APIs. The wrapper imports public functions such as `build_portfolio`, `render_portfolio`, `localize_portfolio`, and `generate_local_artifacts_for_kind`, but it also depends on private portfolio helpers for source collection, prompt-budget reduction, metadata writing, graph/catalog assembly, and executive-summary repair.

Studio created its own lane pipeline because the bundled portfolio build was not
reliable enough for Studio's product workflow. Studio processes input documents
as separate lane runs for objectives, product references, ODPS product details,
signals, and use cases, then assembles catalog, graph, plan, summary, rendered
pages, and localized pages. The public SDK API should treat lane-by-lane
processing as the recommended embedded-application contract, while still
supporting one-shot bundled generation for simpler or lower-control use cases.

Studio added recovery behavior around SDK output:

- recover partial workspaces after generation errors;
- normalize plural ODPC fragments;
- retry product generation with smaller source excerpts;
- create fallback product references when generation fails;
- repair missing workspace contract files;
- repair missing ODPS product details from product references;
- create a node-only graph when relationship generation fails;
- retry or deterministically fallback executive summaries when YAML parsing fails.

Studio added product-facing progress events around SDK work. The SDK call is presented as stages such as extracting content, connecting relationships, and creating language versions. Without this, a long generation run is too opaque for an application UI.

Studio added preflight checks before generation:

- missing source files;
- missing output languages;
- render-only mode used with raw source documents;
- missing provider settings;
- missing API-key environment variable;
- empty files;
- unsupported files;
- empty source lanes;
- source content exceeding configured prompt budget.

Studio surfaced SDK source and prompt budgets in the Admin UI because they are operational settings, not just static developer config.

## Improvement Themes

### 1. Publish An API-First Portfolio Pipeline Contract

Add the stable public API surface before changing diagnostics, progress, or
recovery behavior. The first useful slice is a public Studio-like build path
that processes each source lane independently, then assembles the portfolio
workspace through SDK-owned code. Existing `build_portfolio()` behavior should
be preserved as a compatibility facade, not treated as the target embedded-app
default.

Target shape:

```python
from pathlib import Path

from open_data_products.portfolio import (
    PortfolioBuildRequest,
    PortfolioPipeline,
    PortfolioSourceLanes,
)

source_lanes = PortfolioSourceLanes(
    objectives=Path("sources/objectives"),
    use_cases=Path("sources/use-cases"),
    signals=Path("sources/signals"),
    products=Path("sources/products"),
)

result = PortfolioPipeline().build(
    PortfolioBuildRequest(
        workspace=workspace,
        source_lanes=source_lanes,
        title=title,
        description=description,
        languages=["en", "fi"],
        client=client,
        model=model,
        source_budget=source_budget,
        privacy=privacy,
        progress=progress_callback,
    )
)
```

The SDK should own the standard lane model, per-lane processing contract, and
assembly orchestration so apps do not need to import private helpers or
duplicate sequencing.

Acceptance criteria:

- The SDK owns canonical lane IDs, accepted aliases, and lane validation.
- Apps can use display labels independently from SDK lane IDs.
- `PortfolioBuildRequest`, `PortfolioSourceLanes`, `PortfolioBuildResult`, and
  `PortfolioPipeline` are public imports from `open_data_products`.
- `PortfolioPipeline.build(...)` processes lanes as separate units before
  assembly by default; it also preserves an explicit bundled generation option
  for callers that want to provide all lanes and documents in one shot.
- Studio can remove direct imports of underscored SDK helpers.
- The public API returns structured phase, warning, artifact, source-budget, privacy, and recovery data.
- The monolithic `build_portfolio()` remains as a compatibility facade over the same internal pipeline.

### 2. Provide A Typed Result Object

Replace loosely shaped dict results with a typed result object while preserving dict compatibility for existing callers.

Target fields:

- `valid`
- `workspace`
- `artifacts`
- `warnings`
- `recoveries`
- `phases`
- `source_budget`
- `source_privacy`
- `render`
- `localization`
- `sdk_version`
- `model`
- `provider`

Acceptance criteria:

- Apps do not need to inspect ad hoc keys such as `partial_generation`, `normalization`, `workspace_repair`, or `odps_product_repair`.
- The result can be serialized to JSON for manifests and UI logs.
- Existing callers of `build_portfolio()` still receive compatible mappings during a deprecation period.

### 3. Make Generation Diagnostics First-Class

Expose a public preflight API that apps can call before generation.

Target shape:

```python
from open_data_products.generation import preflight_portfolio_generation

findings = preflight_portfolio_generation(
    source_lanes=source_lanes,
    settings=settings,
    languages=languages,
)
```

The SDK should report machine-readable findings with stable codes, severity, user-facing message, and affected source paths.

Acceptance criteria:

- Studio can replace its app-local generation preflight checks with SDK findings plus Studio-specific checks.
- Findings include prompt-budget estimates before the run.
- Findings distinguish unsupported file type, empty input, missing provider credentials, render-only mismatch, and no processable source.

### 4. Make Recovery A Supported SDK Feature

Move common recovery behavior into the SDK:

- partial workspace detection;
- retry with reduced source excerpts;
- product-reference fallback;
- ODPS detail repair from product references;
- catalog rebuild from fragments;
- graph fallback from catalog nodes;
- executive-summary retry and deterministic fallback.

Acceptance criteria:

- Recovery decisions are represented in `PortfolioBuildResult.recoveries`.
- Apps can choose recovery policy: `strict`, `recover`, or `recover_with_fallbacks`.
- Warnings remain reviewable and do not silently hide weak generated output.

### 5. Stabilize Runtime Configuration Composition

Studio's current three-file setup is correct for ownership, but awkward to operate. The SDK should make it easier to compose an SDK-compatible generation config from application runtime policy.

Do not make the SDK own Studio workload routing. Instead, provide a composition helper that accepts an application-selected provider/model alias and SDK-owned generation settings.

Target shape:

```python
settings = resolve_generation_settings(
    sdk_config_path,
    overrides={
        "provider": "litellm",
        "model": "studio-generation",
    },
)
```

Acceptance criteria:

- Apps can inject workload-selected provider/model values without writing temporary YAML.
- SDK config validation ignores or rejects app-only sections with clear diagnostics instead of obscure errors.
- LiteLLM/OpenAI-compatible gateways remain ordinary provider profiles, not special cases.

### 6. Improve Progress And Observability Contracts

Define stable SDK progress events for embedded apps.

Proposed event fields:

- `stage`
- `phase`
- `status`
- `message`
- `current`
- `total`
- `artifact_kind`
- `source_path`
- `warning_code`

Acceptance criteria:

- Studio can display SDK progress without translating internal events.
- Event names are documented and tested.
- Long-running steps emit enough detail for UI progress and logs.

## Phased Plan

### Phase 1: API Surface Without Behavior Change

- Add `PortfolioSourceLanes`, `PortfolioBuildRequest`, and `PortfolioBuildResult`.
- Add `PortfolioPipeline.build(...)` as the public application API.
- Freeze canonical lane IDs and accepted aliases before exposing them publicly.
- Implement `PortfolioPipeline.build(...)` as lane-by-lane processing followed
  by SDK-owned assembly, matching Studio's actual integration path.
- Promote the private helpers Studio uses into internal SDK services behind the public `PortfolioPipeline`.
- Keep `build_portfolio()` behavior stable.
- Keep `build_portfolio()` mapping compatibility during the deprecation period,
  with `build_portfolio()` delegating to the public pipeline where practical.
- Add tests that run the Studio-like lane workflow through public imports only.
- Add a regression test proving the API supports lane-by-lane generation without
  requiring the bundled option Studio found unreliable.
- Add a compatibility test proving callers can still provide all lanes and
  documents in one bundled run.
- Add export tests for the new public API in `open_data_products.__init__`.

### Phase 2: Diagnostics And Progress

- Add generation preflight findings with stable codes.
- Add progress event schema and callbacks to `PortfolioPipeline`.
- Update CLI output to use the same diagnostics where practical.
- Add fixtures for empty files, unsupported files, missing API keys, and prompt-budget overflow.

### Phase 3: Recovery Policy

- Add explicit recovery policies.
- Move partial workspace, graph fallback, summary fallback, and product retry behavior into SDK-owned code.
- Return structured recoveries and warnings.
- Separate deterministic recoveries from LLM-generated repairs in the result.
- Keep `strict` as the default recovery policy.
- Add tests for each recovery path.

### Phase 4: Runtime Config Composition

- Clarify whether existing `resolve_generation_settings(...)` keyword overrides are sufficient or whether a dict-based composition helper is needed.
- Add clear validation errors for app-only config sections.
- Document LiteLLM gateway configuration as one OpenAI-compatible provider profile pattern.
- Provide an example that mirrors Studio's workload-selected `studio-generation` alias without copying Studio's routing files.

### Phase 5: Studio Migration

- Update Studio to call the new public SDK APIs.
- Remove direct imports of underscored SDK helpers from Studio.
- Delete duplicated recovery and preflight code where SDK behavior is sufficient.
- Keep Studio-owned routing, Admin UI, tenancy, review workflow, delivery integrations, and source upload policy in Studio.

## Non-Goals

- Do not move Studio workload routing into the SDK.
- Do not make LiteLLM a required SDK dependency.
- Do not hide weak generated output behind silent repair.
- Do not turn OKF into a fifth Open Data Products standard; keep it as an external Markdown/frontmatter context bundle format.
- Do not remove the existing CLI or `build_portfolio()` entry points without a compatibility period.

## Immediate Next Step

Start with Phase 1 in the actual SDK implementation repository. The strongest
first test is: Studio can run its current lane-oriented build path using only
public SDK imports, with canonical source-lane aliases and a dict-compatible
result for existing `build_portfolio()` callers. The test should prove each lane
can be processed as a separate unit before portfolio assembly, because that is
the path Studio used in practice. A secondary compatibility test should prove
that bundled all-lane input remains available.
