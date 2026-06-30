# Documentation

This folder is organized by audience and purpose.

## User Guides

- [Full SDK guide](user/full-sdk-guide.md): complete overview formerly kept in
  the root README.
- [Command guide](user/commands.md): common CLI workflows and outputs.
- [ODPR recipe quick start](recipes/quick-start.md): create a project-local
  recipe workspace from packaged starters.
- [ODPR recipe agent usage](recipes/agent-usage.md): safe agent flow for
  discovery, explanation, planning, and guarded execution.
- [ODPR RecipeCatalog](recipes/catalog.md): metadata-only recipe discovery,
  starter catalogs, and project catalogs.
- [ODPR recipe examples](recipes/examples.md): example workspace map and
  commands.
- [LLM generation](user/generation.md): source documents, providers, prompts, and generated artifacts.
- [ODPR recipe workflows](user/recipe-workflows.md): recipe files, runner config, provider readiness, dry-run planning, guarded execution, review status, and run manifests.
- [Provider and model matrix](user/provider-model-matrix.md): direct hosted and local provider/model lookup.
- [Embedded llama.cpp](user/llama-cpp.md): local GGUF model setup without a separate server.
- [NVIDIA NIM generation](user/nvidia-nim.md): run generation through a
  local NIM LLM container.
- [Z.ai GLM generation](user/zai-glm.md): run generation through the hosted
  Z.ai GLM OpenAI-compatible API.
- [LLM selection guide](user/llm-selection-guide.md): model choices by SDK workflow.
- [Data Contract workflows](user/data-contracts.md): product contract resolution, validation, alignment, and reports.
- [Agent surface](user/agent-surface.md): MCP server, ARWS manifest, and bundled skills.
- [API reference](user/API.md): Python API, models, validators, and examples.

## Development Notes

- [Development index](development/README.md): contributor-facing internals map.
- [SDK architecture overview](development/sdk-architecture.md): high-level
  package map and contributor onboarding guide.
- [SDK architecture visual overview](development/sdk-architecture.html):
  standalone illustrated HTML page.
- [Generation development](development/generation.md)
- [Portfolio development](development/portfolio.md)
- [ODPS validation development](development/odps-validation.md)
- [ODPC catalog development](development/odpc-catalog.md)
- [ODPG graph development](development/odpg-graph.md)
- [Data Contracts development](development/data-contracts.md)
- [MCP development](development/mcp.md)
- [GCF development](development/gcf.md)
- [TOON development](development/toon.md)

## Planning

- [Maintainability refactor plan](planning/refactor-maintainability.md)
- [Portfolio workflow plan](planning/portfolio-workflow-plan.md)
- [SDK workflow profiles plan](planning/sdk-workflow-profiles-plan.md)
- [SDK workflow recipes GUI plan](planning/sdk-workflow-recipes-gui-plan.md)
- [ODPR RecipeCatalog grouping spec update](planning/odpr-recipe-catalog-grouping-spec-update.md)
- [ODPR recipe quick starts plan](planning/odpr_recipe_quick_starts_plan_final.md)
- [Tooling development model](planning/tooling-development-model.md)
- [Online LLM generation story](planning/online-llm-generation-story.md)

## Reports

- [Functional test report](reports/functional-test-report.md)
- [Capability drift reports](reports/capability-drift/README.md)
