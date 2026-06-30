# SDK Workflow Recipes Plan

This plan describes proposed SDK workflow recipes: reusable, cookbook-style
ways to run Open Data Products SDK tasks. It is not implemented yet.

These notes also preserve the working ODPR blog draft content after removing
the standalone draft from the repository. ODPR is the proposed Data Product
Recipe Specification: a lightweight workflow contract around ODPS, ODPC, ODPG,
and ODPV artifacts.

## Idea

Provider presets solve the lower-level question of how the SDK connects to a
model runtime. That runtime can be local or online. SDK workflow recipes would
solve the higher-level question of how a team runs repeatable SDK workflows in
development, production, or mixed operating modes.

The analogy is CI/CD pipelines. A pipeline is more than one command or one
runtime setting. It is a named recipe that says which steps run, which
environment they target, what inputs and outputs they use, and which checks or
policies apply. SDK workflow recipes would bring that same pattern to
LLM-backed ODP work.

The short framing is: portable SDK workflow automation with pluggable LLM
execution. The workflow should remain stable while the model runtime can change
by environment, task, or deployment stage.

The reason for considering ODPR is simple: data product delivery is still too
manual. Even with schemas and SDK commands, teams often rely on copied commands,
notebooks, local scripts, prompt chains, CI jobs, and personal habits. One
person knows how to generate fragments, another knows validation, another knows
portfolio refresh, graph build, localization, rendering, or review packaging.
That can work for experiments, but it does not work well for portfolio-scale
operations.

The analogy is the shift from manual software release habits to CI/CD. ODPR
should bring the same explicit workflow thinking to data product delivery, but
as a small, portable, declarative recipe format rather than a heavy
orchestration system.

## SDK Concept Layer

Workflow recipes would add another layer to the SDK concept:

```text
Standards layer
  ODPS, ODPC, ODPG, ODPV schemas, vocabularies, examples

SDK capability layer
  validate, explain, build catalogs, build graphs, generate fragments,
  portfolio workflows

LLM provider layer
  Ollama, llama.cpp server, embedded llama-cpp-python, LM Studio, vLLM,
  OpenAI, OpenRouter, Groq, Claude

Recipe layer
  repeatable SDK workflows with pluggable local and online LLM execution

Automation layer
  CI/CD, release checks, portfolio refreshes, localization, agent review
```

This recipe layer would make the SDK feel less like a collection of commands
and more like an automation platform for Open Data Product work. It also fits
AI Agent First usage: agents do not only need tools, they need repeatable,
inspectable workflows that describe inputs, execution policy, checks, and
outputs.

The existing provider layer should stay focused on runtime wiring:

```yaml
providers:
  ollama-gemma3n:
    type: ollama
    model: gemma3n:e4b
    baseUrl: http://localhost:11434

  lmstudio-gemma4-12b:
    type: openai-chat
    model: google/gemma-4-12b
    baseUrl: http://localhost:1234/v1

  llamacpp-local:
    type: openai-chat
    model: local-model
    baseUrl: http://127.0.0.1:8080/v1

  llamacpp-embedded:
    type: llama-cpp
    model: local-gguf
    modelPath: models/qwen2.5-7b-instruct-q4_k_m.gguf
    contextWindow: 8192
    gpuLayers: -1

  openai:
    type: openai
    model: gpt-4.1-mini
    baseUrl: https://api.openai.com/v1
    apiKeyEnv: OPENAI_API_KEY

  claude:
    type: anthropic
    model: claude-sonnet-4-5
    baseUrl: https://api.anthropic.com/v1
    apiKeyEnv: ANTHROPIC_API_KEY
```

A future recipe layer could define project-owned workflow policy in recipe
files. V1 should use one recipe per file and inline step definitions:

```yaml
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-DEV-001
    name:
      en: Dev Fragment Draft
    description:
      en: Generate draft ODPC signal fragments locally for fast iteration.
  version: "1.0.0"
  type: development
  execution:
    providerRef: llamacpp-local
  steps:
    - id: draft-signals
      command: generate
      with:
        kind: signal
        input: source_docs/signals/
        output: generated/fragments/
```

CI/CD automation can use the same shape:

```yaml
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-RELEASE-001
    name:
      en: Release Portfolio Review
    description:
      en: Refresh, localize, render, and explain the release portfolio.
  version: "1.0.0"
  type: release
  execution:
    providerRef: claude
  runPolicy:
    timeoutSeconds: 900
  steps:
    - id: refresh
      command: portfolio.refresh
      with:
        workspace: portfolio/
    - id: localize
      command: portfolio.localize
      with:
        workspace: portfolio/
        languages:
          - fi
          - sv
    - id: render
      command: portfolio.render
      with:
        workspace: portfolio/
    - id: explain
      command: portfolio.explain
      with:
        workspace: portfolio/
```

CI or release automation could then run:

```bash
open-data-products recipe run recipes/ci-validate-generated-fragments.yaml
open-data-products recipe run recipes/release-portfolio-review.yaml
```

The recipe files above are examples. The important design point is that a recipe
can express environment, task intent, provider choices, context preferences,
inputs, outputs, and validation steps together. Development recipes can favor
local models for privacy, speed, and cost control. Production recipes can favor
online providers for reliability, scale, support, and stronger model quality.
Hybrid recipes can deliberately mix both.

## Added Value

This is a step up in abstraction, similar to the portfolio command group. The
portfolio workflow lets users think in tasks such as build, refresh, sync,
render, localize, and explain instead of manually assembling every ODPC, ODPS,
and ODPG artifact. SDK workflow recipes would do the same for LLM-backed
execution by turning common task sequences into named, reusable runbooks.

The added value is:

- project teams can standardize repeatable SDK runs instead of copying command
  sequences between terminals, notebooks, and CI jobs;
- each recipe can document which local or hosted model is used for each step
  without repeating flags in every command;
- development can default to local models while production uses online providers
  or a deliberate mix of local and online providers;
- llama.cpp can be treated as a first-class local runtime in two forms:
  through the existing OpenAI-compatible `openai-chat` provider shape for a
  separately managed server, or through the embedded `llama-cpp`
  provider for in-process GGUF inference;
- embedded llama.cpp support can give Python SDK users a more direct local path:
  install an optional SDK extra, point the config at a model file, and run the
  same recipe without separately starting Ollama, LM Studio, or a llama.cpp
  server;
- keeping embedded llama.cpp behind an optional extra preserves the lightweight
  base SDK install for validation, catalog, graph, MCP, and hosted-provider
  workflows while making local GGUF inference officially supported;
- fast local models can be used for draft fragments while stronger or slower
  models can be reserved for graph inference, portfolio review, or localization;
- online models can be reserved for production workflows, high-value review
  steps, multilingual localization, or cases where quality and operational
  reliability matter more than local execution;
- compact context choices such as GCF or TOON can become workflow policy instead
  of command-by-command habit;
- portfolio localization can carry workflow-specific runtime settings such as
  longer timeouts or smaller chunks;
- validation, rendering, and review steps can be encoded next to generation
  steps, similar to a CI/CD pipeline;
- agents can inspect the config and understand both available runtimes and the
  intended SDK task policy before running tools.

## Standards Family Relationship

The OpenDataProducts.org standards family follows a separation of concerns:

- ODPS defines the product.
- ODPC defines catalogs and reusable portfolio objects.
- ODPG defines relationships and graphs.
- ODPV defines shared vocabulary and terms.
- ODPR would define repeatable workflows for data product delivery.

ODPR should not define the product, catalog, graph, or vocabulary model. It
should define the workflow contract around those artifacts: how work should run,
which steps are included, what inputs and outputs are expected, which validation
gates apply, and when review is required.

## Business, Developer, And Agent Value

For business users, ODPR is about repeatability. A data product portfolio does
not become valuable because one expert runs the right commands on one machine.
It becomes valuable when many teams can create, review, refresh, and improve
data products consistently.

A data office could define a standard portfolio review workflow. A platform
team could define a release workflow. A governance team could require
validation and approval gates. A localization team could define multilingual
publishing steps. A government entity or enterprise unit could adapt the same
recipe shape to its own operating model.

For developers, ODPR gives data product work a CI/CD-style workflow format.
Instead of running separate SDK commands manually, a team can define a recipe
once and run it repeatedly across local development, CI, release automation, or
agentic execution.

For AI agents, ODPR should remove guesswork. An agent should be able to inspect
a declared workflow and understand which workflows are available, which steps
are allowed, which inputs are expected, which outputs should be produced, which
context format should be used, which provider reference applies, and whether
human review is required.

## User-Owned Workflows

Workflow ownership should move toward users. Without recipes, SDK users depend
on workflows that SDK developers decide to implement or document. The SDK can
provide commands such as `generate`, `validate`, `build`, `refresh`, `render`,
`localize`, and `explain`, but the sequence is still fixed by the tool, the
documentation, or the person running it.

With ODPR-style recipes, a company can define its own production release
workflow, a government organization can define its own portfolio review
workflow, a vendor can define its own marketplace publishing workflow, and a
data office can define mandatory validation and review gates.

The SDK becomes the runtime. ODPR becomes the workflow contract.

## Development To Production Flow

SDK workflow recipes would make the development lifecycle explicit. A team
could build and iterate locally:

```bash
open-data-products recipe run recipes/dev-fragment-draft.yaml
open-data-products recipe run recipes/dev-portfolio-build.yaml
```

Then use production recipes for release, review, localization, or automated
portfolio updates:

```bash
open-data-products recipe run recipes/prod-fragment-generation.yaml
open-data-products recipe run recipes/prod-portfolio-localization.yaml
```

Hybrid flows should also be first-class. For example, graph edge inference can
use a local Gemma or Qwen model with compact GCF context, while final portfolio
review or localization uses Claude, OpenAI, OpenRouter, or another online
provider. The SDK should not force one runtime strategy across every task.

Today, a portfolio review flow can already be run as separate commands:

```bash
open-data-products portfolio refresh portfolio/
open-data-products portfolio localize portfolio/ \
  --languages "fi,sv" \
  --provider claude \
  --model claude-sonnet-4-5
open-data-products portfolio render portfolio/
open-data-products portfolio explain portfolio/
```

A future recipe runner would let the same workflow be named and reused:

```bash
open-data-products recipe run recipes/dev-fragment-draft.yaml
open-data-products recipe run recipes/ci-validate-generated-fragments.yaml
open-data-products recipe run recipes/release-portfolio-review.yaml
```

Those `recipe` commands are planned SDK support, not part of the current SDK CLI
yet. The direction is that the workflow becomes stable and inspectable while
execution can happen locally, in CI, in release automation, or through an AI
agent.

## Cookbook Shape

Recipes should be readable as documentation and executable as configuration.
Each recipe should answer:

- what workflow is being run;
- which commands or SDK operations are included;
- which provider is used by default;
- which steps override that provider;
- which inputs, outputs, and context formats are expected;
- which validation or review steps prove the run is useful.

The SDK could ship starter recipes while allowing projects to copy, edit, and
own their own cookbook. This would make SDK adoption feel closer to using CI/CD
pipeline templates: start with a working recipe, then adapt it to the team's
runtime, governance, and release process.

## ODPR Recipe Shape

A minimal recipe should be easy to read:

```yaml
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-CI-001
    name:
      en: Validate Generated Catalog
    description:
      en: Validate a generated ODPC catalog during CI.
  version: "1.0.0"
  type: ci
  steps:
    - id: validate-catalog
      command: validate
      with:
        document: generated/catalog.yaml
```

A richer release recipe could include inputs, outputs, context format,
execution mode, steps, gates, and human review:

```yaml
schema: https://opendataproducts.org/odpr-v1.0/schema/odpr.yaml
version: "1.0"
kind: Recipe
recipe:
  metadata:
    id: RCP-RELEASE-001
    name:
      en: Release Portfolio Review
    description:
      en: Refresh, localize, render, and explain a data product portfolio.
  version: "1.0.0"
  type: release
  inputs:
    - id: portfolio
      path: portfolio/
      description: Portfolio workspace to refresh and review.
  outputs:
    - id: rendered-portfolio
      path: portfolio/index.html
    - id: localized-finnish
      path: portfolio/index.fi.html
    - id: localized-swedish
      path: portfolio/index.sv.html
  context:
    format: gcf
    fallback:
      - toon
      - yaml
  execution:
    mode: hosted
    providerRef: production-quality
  runPolicy:
    timeoutSeconds: 900
  steps:
    - id: refresh-portfolio
      command: portfolio.refresh
      with:
        workspace: portfolio/
    - id: localize-portfolio
      command: portfolio.localize
      with:
        workspace: portfolio/
        languages:
          - fi
          - sv
    - id: render-portfolio
      command: portfolio.render
      with:
        workspace: portfolio/
    - id: explain-portfolio
      command: portfolio.explain
      with:
        workspace: portfolio/
  gates:
    - id: human-review
      type: review
      required: true
      mode: report-only
  review:
    required: true
    mode: human
    instructions: Review localized pages and generated reports before publishing.
```

The first ODPR version should stay small. It should cover recipe identity,
recipe type, inputs, outputs, steps, context format, execution mode, provider
reference, validation gates, review requirements, and run policy. It should not
define every model provider, become a CI/CD engine, replace SDK commands, or
replace workflow tools. It should define a portable workflow contract that tools
can run, inspect, validate, and explain.

## Inline Steps First

The first ODPR version should keep recipe steps fully inline. Reusable step YAML
fragments are attractive, but they add a second schema, versioning rules, lookup
paths, merge semantics, and another failure mode before the core recipe runner is
proven. V1 should optimize for inspectability: one recipe file should be enough
to understand the workflow, dry-run it, and review the resolved SDK commands.

The v1 step shape should be explicit:

```yaml
steps:
  - id: build-catalog
    command: odpc.build
    with:
      input: generated/fragments/
      output: generated/catalog.yaml

  - id: localize-fi-sv
    command: portfolio.localize
    with:
      workspace: generated/portfolio/
      languages:
        - fi
        - sv
    providerRef: claude
```

V1 should reserve room for future reuse without implementing it. The schema can
reserve `uses` as a future field, but v1 validation should reject it with a clear
message such as: reusable step fragments are planned for a later version; expand
the step inline for now.

```yaml
# Future v2 extension, not v1.
steps:
  - id: localize-fi-sv
    uses: steps/portfolio-localize.yaml
    with:
      workspace: generated/portfolio/
      languages:
        - fi
        - sv
```

This gives the project a compatibility path without making the first runner a
template engine. If real recipes later show enough duplication to justify reuse,
the v2 design can add a `RecipeStep` schema, `stepPaths`, merge rules, and
dry-run output that shows both the fragment source and final SDK command.

## V1 Execution Decisions

The first recipe implementation should make a few simplifying decisions:

- recipes are invoked by file path, not by recipe id;
- `recipes.defaultRecipe` can provide the path to use when a recipe path is
  omitted;
- `recipes.paths` can help locate starter files and validate config, but v1
  should not scan those paths to resolve arbitrary recipe ids;
- step options for SDK command flags live under `with`;
- recipe-level and step-level provider choices use `providerRef`;
- `providerRef` and `model` are execution fields, not `with` fields;
- `validate` targets one concrete document in v1;
- folder or glob validation should be a later `validate.each` step;
- gates are report-only in v1 and are written into dry-run and run manifests;
- v1 should not include `recipe approve` or persistent approval records.

These decisions keep the first runner file-based, inspectable, and close to the
existing SDK CLI surface.

## SDK Implementation Direction

The ODP Agent SDK is the first implementation target for ODPR-style workflow
recipes. The goal is to let SDK users define, validate, inspect, and run
declarative workflow recipes instead of relying only on built-in command
sequences.

A future SDK command set could look like this:

```bash
open-data-products recipe validate recipes/release-portfolio-review.yaml
open-data-products recipe explain recipes/release-portfolio-review.yaml
open-data-products recipe run recipes/release-portfolio-review.yaml --dry-run
open-data-products recipe run recipes/release-portfolio-review.yaml --json
```

These commands are not available in the current SDK yet. Today, the same work is
done with existing commands such as:

```bash
open-data-products generate --input source_docs/ --kind signal --output generated/
open-data-products odpc-build generated/ --output catalog.yaml --gcf catalog.gcf
open-data-products odpg-build generated/ --output graph.yaml --gcf graph.gcf
open-data-products portfolio refresh portfolio/
open-data-products portfolio localize portfolio/ --languages "fi,sv"
open-data-products portfolio render portfolio/
open-data-products portfolio explain portfolio/
```

The standard defines the portable recipe shape. The SDK turns that shape into
executable workflows.

## Planned Recipe Command Contract

The recipe command group should be small and explicit. It should not hide the
underlying SDK commands. Its job is to validate the recipe contract, resolve
provider and path policy, show the execution plan, and then run the same SDK
operations a user could run manually.

### `recipe validate`

```bash
open-data-products recipe validate recipes/release-portfolio-review.yaml
open-data-products recipe validate recipes/release-portfolio-review.yaml --json
open-data-products recipe validate --config recipes.config.yaml
```

What it should do:

- parse the recipe YAML;
- validate required fields such as `kind`, `recipe.metadata.id`,
  `recipe.version`, `type`, and `steps`;
- verify that each `steps[].command` is a supported step command;
- verify that required `with` fields exist for each step;
- check input paths when the path is concrete and local;
- report missing provider references without calling the provider;
- reject v2-only fields such as `steps[].uses` with a clear error;
- report planned output paths and write scope;
- return non-zero for schema errors, unsupported commands, missing required
  options, or invalid provider references.

It should not write generated artifacts or call an LLM.

### `recipe explain`

```bash
open-data-products recipe explain recipes/release-portfolio-review.yaml
open-data-products recipe explain recipes/release-portfolio-review.yaml --json
open-data-products recipe explain --config recipes.config.yaml
```

What it should do:

- print a human-readable summary of the recipe;
- list steps in execution order;
- show which steps are deterministic and which steps call a model;
- show resolved inputs, outputs, provider references, context format, gates,
  and review policy;
- show the recipe path used, including when it came from `recipes.defaultRecipe`;
- show equivalent SDK commands with placeholders resolved where possible.

It should not write generated artifacts or call an LLM.

### `recipe run`

```bash
open-data-products recipe run recipes/release-portfolio-review.yaml
open-data-products recipe run recipes/release-portfolio-review.yaml --dry-run
open-data-products recipe run recipes/release-portfolio-review.yaml --json
open-data-products recipe run recipes/release-portfolio-review.yaml \
  --execute \
  --provider-ref claude \
  --model claude-sonnet-4-5
open-data-products recipe run --config recipes.config.yaml --dry-run
```

What it should do:

- run validation before execution;
- resolve recipe-level and step-level options into executable SDK commands;
- support `--dry-run` to emit the resolved plan without writes or LLM calls;
- require `--execute` for state-changing execution;
- support `--json` for CI, agents, and the future GUI;
- support provider/model overrides for compatible LLM-backed steps through
  `--provider-ref` and `--model`;
- write a run manifest containing the recipe id, SDK version, run id,
  timestamps, resolved action parameters, status per step, outputs, warnings,
  and gates;
- stop on hard failures unless a recipe explicitly marks a step as optional;
- return non-zero when a required step fails.

In v1, required gates should not block execution because the runner has no
approval command or approval-record format yet. Required gates should be recorded
as `review-needed` in the dry-run plan and run manifest.

The runner should classify each step before execution:

- `deterministic`: no provider needed, repeatable from files and options;
- `llm-backed`: calls a configured provider and model;
- `review`: requires human or external approval before continuing;
- `report`: reads artifacts and produces summaries, diagnostics, or manifests.

## Agent Contract

AI agents should be able to discover, inspect, dry-run, execute, recover, and
report recipe workflows without guessing from prose. V1 should keep that path
small: find a recipe file, validate it, dry-run it as JSON, then execute it only
when explicitly requested.

ODPR v1 should stay centered on the authored `Recipe` contract. See
[ODPR Agent Runtime Structures](odpr-agent-runtime-structures.md) for the
simpler boundary: recipe files are ODPR documents, while dry-run plans,
inspection results, run manifests, and provider readiness are SDK response
formats until they prove useful enough to standardize.

### Agent Happy Path

The agent path should be one predictable sequence:

```bash
open-data-products recipe list --config recipes.config.yaml --json
open-data-products recipe validate recipes/release-portfolio-review.yaml --json
open-data-products recipe run recipes/release-portfolio-review.yaml --dry-run --json
open-data-products recipe run recipes/release-portfolio-review.yaml --execute --json
```

`recipe list --json` should read `recipes.paths` from `recipes.config.yaml` and
return recipe files that can be parsed enough to expose metadata. It should not
execute steps, call providers, or write files.

`recipe validate --json` should tell the agent whether the authored `Recipe`
document is structurally usable.

`recipe run --dry-run --json` should be the main planning surface. It should
return a stable SDK response with at least:

```yaml
mode: dry-run
recipe:
  path: recipes/release-portfolio-review.yaml
  id: RCP-RELEASE-001
  version: "1.0.0"
  type: release
canRun: false
blockingReasons: []
warnings: []
config:
  recipeConfig: recipes.config.yaml
  generationConfig: generation.config.yaml
providers:
  - ref: claude
    model: claude-sonnet-4-5
    readiness: ready
    missingEnv: []
steps:
  - id: localize
    command: portfolio.localize
    classification: llm-backed
    resolved:
      action: portfolio.localize
      parameters:
        workspace: generated/portfolio/
        languages:
          - fi
          - sv
        providerRef: claude
        model: claude-sonnet-4-5
    inputs:
      - path: generated/portfolio/
        exists: true
    plannedWrites:
      - path: generated/portfolio/index.fi.html
        allowed: true
    review:
      status: review-needed
```

The dry-run response should be authoritative for agents:

- `mode` must state the SDK invocation mode, such as `dry-run` or `execute`;
- `canRun: true` means no blocking schema, provider, input, or write-scope issue
  was found;
- `blockingReasons` must use structured error codes;
- `resolved.parameters` must use structured values, not shell strings or argv
  arrays;
- `plannedWrites` must include explicit and derived outputs;
- `review.status: review-needed` must be visible before execution;
- provider readiness must be checked without making model-completion calls.

`recipe run --execute --json` should write files only after the same validation,
provider, and write-scope checks pass.

The same `Recipe` document should be used for validation, dry-run, execution,
and resume. Invocation mode belongs to the SDK command and SDK JSON response,
not to the ODPR recipe body. `recipe.execution.mode` means provider/runtime
class such as `local`, `hosted`, `hybrid`, or `none`.

### Error Codes

JSON responses should use stable machine-readable error codes:

- `schema_error`
- `unsupported_step`
- `unsupported_field`
- `missing_input`
- `missing_output`
- `missing_provider`
- `missing_model`
- `missing_env`
- `provider_unreachable`
- `optional_dependency_missing`
- `write_scope_violation`
- `review_needed`
- `validation_failed`
- `model_call_failed`
- `step_failed`
- `manifest_write_failed`

Each error should include `code`, `message`, `path`, `stepId` when applicable,
and `blocking: true|false`.

### Agent-Safe Execution

Agents should default to non-writing behavior. In v1:

- `recipe run` should behave like a dry-run unless `--execute` is present;
- `--execute` should still run validation and write-scope checks first;
- if a required report-only gate is present, execution should finish with
  `review-needed` status and a non-zero exit code unless
  `--allow-review-needed` is passed;
- agents should use `--json` for all recipe commands and treat non-JSON output
  as human-facing only.

### Provider Readiness

Agent planning should distinguish provider configuration from provider use.
Dry-run and inspect commands should check:

- provider reference exists in the selected generation config;
- model is selected from the step, recipe, recipe config, generation config, or
  SDK defaults;
- required API key environment variables are present without printing values;
- local provider URLs are syntactically valid;
- optional local dependencies such as embedded llama.cpp are importable when the
  selected provider type requires them.

Network reachability checks should be optional and bounded by a short timeout.
No dry-run or inspect command should submit source content to a model.

### Recovery

Agents need a recovery path after interruption, but v1 should not become a
workflow engine. The minimal recovery feature is reading a previous manifest and
showing what would be rerun:

```bash
open-data-products recipe run recipes/release-portfolio-review.yaml \
  --resume .odp/runs/<run-id>/manifest.json \
  --dry-run \
  --json
```

Recovery behavior should be conservative:

- failed, skipped, and review-needed steps should be listed before resuming;
- v1 should not skip or rerun steps automatically without `--execute`;
- a resumed execution should write a new manifest linked to the previous run id.

### Redaction

Every agent-facing JSON surface, manifest, stdout line, stderr line, and log file
should redact:

- API keys and environment variable values;
- authorization headers and bearer tokens;
- provider URLs containing credentials;
- prompt bodies when the command is only inspecting or dry-running;
- generated document bodies unless a command explicitly asks for an artifact
  preview.

The manifest should keep references, hashes, paths, warnings, and summaries, not
full source documents or generated bodies.

### Agent Manifest Integration

The SDK agent manifest should advertise recipe capabilities once implemented.
It should expose recipe discovery, validation, dry-run, execution, safety class,
and supported step commands without requiring agents to scrape help text.

## Planned Step Command Catalog

The first implementation should support a limited catalog of step commands. A
step command is the stable recipe name. The runner translates it into an SDK CLI
call or equivalent Python API call.

### `generate`

Purpose: turn Markdown or text source files into ODPC fragments, ODPG graph
drafts, or ODPS product drafts through configured LLM prompts.

Equivalent SDK command:

```bash
open-data-products generate \
  --input source_docs/ \
  --kind signal \
  --output generated/fragments/ \
  --config generation.config.yaml \
  --provider openai \
  --model gpt-4.1-mini \
  --json
```

Required recipe fields:

- `with.input`: Markdown/text source file or folder.
- `with.kind`: one of `product-reference`, `odps-product`, `use-case`,
  `objective`, `signal`, or `graph`.
- `with.output`: output folder for generated YAML artifacts.

Optional step execution fields:

- `providerRef`: optional step-level provider reference for this LLM-backed
  step.
- `model`: optional step-level model override.

Optional recipe fields:

- `with.config`: generation config YAML path.
- `with.prompts`: prompt template folder override.
- `with.profile`: `minimal` or `complete-draft` for `odps-product`.
- `with.includeComponents`: comma-separated or list form for ODPS product
  components such as `SLA`, `dataQuality`, `pricingPlans`, or `dataAccess`.
- `with.maxSourceChars`: source chunk limit for ODPS product fact extraction.
- `with.ollamaUrl`: local Ollama base URL.
- `with.json`: emit JSON from the underlying command.

Outputs:

- selected YAML artifacts under `with.output`;
- JSON command result when requested;
- validation warnings for generated artifacts.

Notes:

- `generate` is LLM-backed.
- For selected kinds, each source document should produce its own selected
  artifact instead of being collapsed into one output.
- `odps-product` outputs are generated product drafts, not ODPC fragments.

### `odpc.build`

Purpose: build one ODPC catalog from ODPC fragments, nested ODPC catalogs, or
ODPS product files.

Equivalent SDK command:

```bash
open-data-products odpc-build generated/fragments/ \
  --output generated/catalog.yaml \
  --html generated/catalog.html \
  --toon generated/catalog.toon \
  --gcf generated/catalog.gcf \
  --json
```

Required recipe fields:

- `with.input`: folder containing ODPC objects, ODPC catalogs, or ODPS product
  files.
- `with.output`: output catalog YAML path.

Optional recipe fields:

- `with.html`: standalone browser-viewable HTML catalog path.
- `with.toon`: TOON catalog context sidecar path.
- `with.gcf`: GCF catalog context sidecar path.
- `with.id`: catalog metadata id override.
- `with.name`: catalog `metadata.name.en` override.
- `with.description`: catalog `metadata.description.en` override.
- `with.recursive`: `false` maps to `--no-recursive`.
- `with.validate`: `false` maps to `--no-validate`.
- `with.json`: emit JSON from the underlying command.

Outputs:

- ODPC catalog YAML;
- optional HTML catalog;
- optional TOON and GCF context files.

Notes:

- `odpc.build` is deterministic.
- It should not accept provider or model options.

### `odpg.build`

Purpose: build one ODPG graph from ODPC fragments and infer graph edges with a
configured provider.

Equivalent SDK command:

```bash
open-data-products odpg-build generated/fragments/ \
  --output generated/graph.yaml \
  --toon generated/graph.toon \
  --gcf generated/graph.gcf \
  --context-graph portfolio/graph.yaml \
  --config generation.config.yaml \
  --provider lmstudio \
  --model google/gemma-4-12b \
  --json
```

Required recipe fields:

- `with.input`: folder containing ODPC product reference, use case, objective,
  or signal fragments.
- `with.output`: output graph YAML path.

Optional recipe fields:

- `with.toon`: TOON graph context sidecar path.
- `with.gcf`: GCF graph context sidecar path.
- `with.contextGraph`: existing graph YAML used as prior edge-inference
  context; sibling `.gcf` or `.toon` files should be preferred when present.
- `with.id`: graph metadata id override.
- `with.name`: graph `metadata.name.en` override.
- `with.description`: graph `metadata.description.en` override.
- `with.recursive`: `false` maps to `--no-recursive`.
- `with.validate`: `false` maps to `--no-validate`.
- `with.config`: generation config YAML path for edge inference.
- `with.prompts`: prompt template folder override.
- `with.ollamaUrl`: local Ollama base URL.
- `with.json`: emit JSON from the underlying command.

Optional step execution fields:

- `providerRef`: optional step-level provider reference for edge inference.
- `model`: optional step-level model override.

Outputs:

- ODPG graph YAML;
- optional TOON and GCF graph context files.

Notes:

- `odpg.build` is LLM-backed because edge inference uses a provider.
- Recipe dry-runs should report the context graph and compact context sidecars
  selected for edge inference.

### `odpg.render`

Purpose: render a standalone browser-viewable ODPG graph explorer from graph
YAML.

Equivalent SDK command:

```bash
open-data-products odpg-generate generated/graph.yaml \
  --output generated/graph-explorer.html \
  --json
```

Required recipe fields:

- `with.graph`: ODPG graph YAML path.
- `with.output`: output HTML file path.

Optional recipe fields:

- `with.json`: emit JSON from the underlying command.

Outputs:

- standalone graph explorer HTML file.

Notes:

- `odpg.render` is deterministic.
- The step name should be `odpg.render` in recipes even though the current CLI
  subcommand is `odpg-generate`; recipe names should describe workflow intent,
  not legacy command naming.

### `portfolio.build`

Purpose: build or rerun a portfolio workspace from source lanes covering
objectives, use cases, signals, and products.

Equivalent SDK command:

```bash
open-data-products portfolio build \
  --objectives sources/objectives/ \
  --use-cases sources/use-cases/ \
  --signals sources/signals/ \
  --products sources/products/ \
  --output generated/portfolio/ \
  --title "Public Data Product Portfolio" \
  --config generation.config.yaml \
  --provider openai \
  --model gpt-4.1-mini \
  --strict-validation \
  --json
```

Required recipe fields:

- at least one source lane: `with.objectives`, `with.useCases`,
  `with.signals`, or `with.products`;
- `with.output` for a new workspace, or `with.workspace` for a rerun of an
  existing workspace.

Optional recipe fields:

- `with.title`: human-controlled workspace title.
- `with.config`: generation config YAML path.
- `with.prompts`: reserved for portfolio prompt folder overrides.
- `with.ollamaUrl`: local Ollama base URL.
- `with.strictValidation`: fail when generated artifacts fail schema
  validation.
- `with.json`: emit JSON from the underlying command.

Optional step execution fields:

- `providerRef`: optional step-level provider reference.
- `model`: optional step-level model override.

Outputs:

- portfolio workspace directory;
- generated ODPC, ODPS, and ODPG artifacts managed by the workspace;
- rendered `index.html` unless a later implementation separates rendering.

Notes:

- `portfolio.build` is LLM-backed.
- Recipes should treat portfolio workspaces as the higher-level orchestration
  path, not as a wrapper around only `generate`.

### `portfolio.refresh`

Purpose: refresh an existing portfolio workspace from saved source lanes or
explicit source overrides.

Equivalent SDK command:

```bash
open-data-products portfolio refresh generated/portfolio/ \
  --all-sources \
  --provider claude \
  --model claude-sonnet-4-5 \
  --strict-validation \
  --json
```

Required recipe fields:

- `with.workspace`: portfolio workspace path.

Optional recipe fields:

- `with.objectives`, `with.useCases`, `with.signals`, `with.products`: source
  overrides.
- `with.title`: human-controlled workspace title.
- `with.config`: generation config YAML path.
- `with.allSources`: process all saved source documents instead of only new or
  changed files.
- `with.prompts`: reserved for portfolio prompt folder overrides.
- `with.ollamaUrl`: local Ollama base URL.
- `with.strictValidation`: fail when generated artifacts fail schema
  validation.
- `with.json`: emit JSON from the underlying command.

Optional step execution fields:

- `providerRef`: optional step-level provider reference.
- `model`: optional step-level model override.

Outputs:

- updated portfolio workspace artifacts;
- updated rendered page and reports.

Notes:

- `portfolio.refresh` is LLM-backed.
- By default it should keep identity and workspace state from the existing
  portfolio.

### `portfolio.sync`

Purpose: sync edited YAML artifacts inside a portfolio workspace without
calling an LLM.

Equivalent SDK command:

```bash
open-data-products portfolio sync generated/portfolio/ \
  --strict-validation \
  --json
```

Required recipe fields:

- `with.workspace`: portfolio workspace path.

Optional recipe fields:

- `with.strictValidation`: fail when synced artifacts fail schema validation.
- `with.json`: emit JSON from the underlying command.

Outputs:

- synchronized workspace indexes, reports, and browser artifacts.

Notes:

- `portfolio.sync` is deterministic.
- It is the right step after human edits to generated YAML.

### `portfolio.localize`

Purpose: localize portfolio HTML pages without changing canonical YAML
artifacts.

Equivalent SDK command:

```bash
open-data-products portfolio localize generated/portfolio/ \
  --languages "fi,sv,ar" \
  --default-language en \
  --config generation.config.yaml \
  --provider claude \
  --model claude-sonnet-4-5 \
  --strict-validation \
  --json
```

Required recipe fields:

- `with.workspace`: portfolio workspace path.
- `with.languages`: BCP 47 language tags as a list or comma-separated string.

Optional recipe fields:

- `with.defaultLanguage`: default portfolio language; defaults to `en`.
- `with.config`: generation config YAML path.
- `with.prompts`: reserved for portfolio prompt folder overrides.
- `with.ollamaUrl`: local Ollama base URL.
- `with.strictValidation`: fail when localized artifacts fail schema
  validation.
- `with.json`: emit JSON from the underlying command.

Optional step execution fields:

- `providerRef`: optional step-level provider reference.
- `model`: optional step-level model override.

Outputs:

- localized HTML pages such as `index.fi.html` and `index.sv.html`;
- localization metadata and warnings in command output.

Notes:

- `portfolio.localize` is LLM-backed.
- It should not mutate canonical ODPS, ODPC, or ODPG YAML artifacts.
- Recipes may set longer `runPolicy.timeoutSeconds` for this step because
  localization often has larger text volume than validation or rendering.

### `portfolio.render`

Purpose: render one static browser-viewable portfolio page from the workspace.

Equivalent SDK command:

```bash
open-data-products portfolio render generated/portfolio/ \
  --output generated/portfolio/index.html \
  --strict-validation \
  --json
```

Required recipe fields:

- `with.workspace`: portfolio workspace path.

Optional recipe fields:

- `with.output`: optional HTML output path; defaults to
  `<workspace>/index.html`.
- `with.strictValidation`: fail when rendered artifacts fail schema validation.
- `with.json`: emit JSON from the underlying command.

Outputs:

- static portfolio HTML page.

Notes:

- `portfolio.render` is deterministic.

### `portfolio.explain`

Purpose: summarize a portfolio workspace for humans, scripts, agents, and
review gates.

Equivalent SDK command:

```bash
open-data-products portfolio explain generated/portfolio/ --json
```

Required recipe fields:

- `with.workspace`: portfolio workspace path.

Optional recipe fields:

- `with.json`: emit JSON from the underlying command.

Outputs:

- workspace summary, artifact counts, warnings, and browser entry point.

Notes:

- `portfolio.explain` is a report step.
- It is a good final step before a review gate.

### `validate`

Purpose: validate one ODPS, ODPC, or ODPG document.

Equivalent SDK command:

```bash
open-data-products validate generated/catalog.yaml --json
```

Required recipe fields:

- `with.document`: artifact path to validate.

Optional recipe fields:

- `with.json`: emit JSON from the underlying command.

Outputs:

- validation status, errors, and warnings.

Notes:

- `validate` is deterministic.
- A later recipe runner can add `validate.each` or glob support, but the first
  version should keep validation targets explicit.

### `explain`

Purpose: produce an agent-readable explanation of one ODPS, ODPC, or ODPG
document.

Equivalent SDK command:

```bash
open-data-products explain generated/graph.yaml --json
```

Required recipe fields:

- `with.document`: artifact path to explain.

Optional recipe fields:

- `with.json`: emit JSON from the underlying command.

Outputs:

- document summary, references, relationships, and warnings.

Notes:

- `explain` is a report step.
- It should be used for review packaging, not as a substitute for validation.

## Recipe Expansion Examples

The runner should be able to show exact command expansion during `recipe
explain` and `recipe run --dry-run`.

### Fragment Draft Recipe

Recipe step:

```yaml
- id: draft-signals
  command: generate
  providerRef: ollama
  model: qwen2.5
  with:
    input: source_docs/signals/
    kind: signal
    output: generated/fragments/
```

Dry-run expansion:

```bash
open-data-products generate \
  --input source_docs/signals/ \
  --kind signal \
  --output generated/fragments/ \
  --provider ollama \
  --model qwen2.5
```

### Catalog And Graph Build Recipe

Recipe steps:

```yaml
- id: build-catalog
  command: odpc.build
  with:
    input: generated/fragments/
    output: generated/catalog.yaml
    html: generated/catalog.html
    gcf: generated/catalog.gcf
- id: build-graph
  command: odpg.build
  providerRef: lmstudio
  model: google/gemma-4-12b
  with:
    input: generated/fragments/
    output: generated/graph.yaml
    gcf: generated/graph.gcf
- id: render-graph
  command: odpg.render
  with:
    graph: generated/graph.yaml
    output: generated/graph-explorer.html
```

Dry-run expansion:

```bash
open-data-products odpc-build generated/fragments/ \
  --output generated/catalog.yaml \
  --html generated/catalog.html \
  --gcf generated/catalog.gcf
open-data-products odpg-build generated/fragments/ \
  --output generated/graph.yaml \
  --gcf generated/graph.gcf \
  --provider lmstudio \
  --model google/gemma-4-12b
open-data-products odpg-generate generated/graph.yaml \
  --output generated/graph-explorer.html
```

### Portfolio Localization Recipe

Recipe steps:

```yaml
- id: refresh
  command: portfolio.refresh
  with:
    workspace: generated/portfolio/
    allSources: true
- id: localize
  command: portfolio.localize
  providerRef: claude
  model: claude-sonnet-4-5
  with:
    workspace: generated/portfolio/
    languages:
      - fi
      - sv
- id: render
  command: portfolio.render
  with:
    workspace: generated/portfolio/
- id: summarize
  command: portfolio.explain
  with:
    workspace: generated/portfolio/
    json: true
```

Dry-run expansion:

```bash
open-data-products portfolio refresh generated/portfolio/ --all-sources
open-data-products portfolio localize generated/portfolio/ \
  --languages "fi,sv" \
  --provider claude \
  --model claude-sonnet-4-5
open-data-products portfolio render generated/portfolio/
open-data-products portfolio explain generated/portfolio/ --json
```

## Step Option Rules

The recipe runner should keep option handling boring and predictable:

- convert camelCase recipe keys to the current CLI option names, for example
  `includeComponents` to `--include-components` and `strictValidation` to
  `--strict-validation`;
- omit boolean flags when the value is false, except inverse flags such as
  `recursive: false` mapping to `--no-recursive` and `validate: false` mapping
  to `--no-validate`;
- join list-valued language fields as comma-separated strings for CLI
  execution;
- pass `--json` only when the step or run requests machine-readable output;
- reject `providerRef` and `model` fields on deterministic commands;
- require a provider-capable command before applying recipe-level provider
  defaults or top-level CLI provider overrides;
- keep `--dry-run` at the recipe runner level instead of forwarding it to SDK
  commands that do not support it today.

## Recipe Runner Config

Recipes should have their own runner config because workflow execution policy is
separate from LLM provider wiring. The existing generation config should remain
the source for model access, provider endpoints, API key environment variables,
prompt folders, and local runtime settings. A recipe runner config should define
how recipes are discovered, planned, written, reported, and gated.

The file could be named `recipes.config.yaml`:

```yaml
version: "1.0"

recipes:
  paths:
    - recipes/
    - .odp/recipes/
  defaultRecipe: recipes/release-portfolio-review.yaml

providers:
  generationConfig: generation.config.yaml
  defaultProviderRef: local-draft

execution:
  manifestDir: .odp/runs/
  allowWrites:
    - generated/
    - portfolio/
  requireReviewFor:
    - production
    - release
  stopOnWarning: false

outputs:
  defaultJson: false
  keepRunLogs: true
  reportName: recipe-run.json

gui:
  exposeDryRunPlan: true
  exposeRunManifest: true
  allowStateChangingRuns: false
```

The config should answer project-level runner questions:

- where recipe files are searched;
- which recipe is the default when a command omits a recipe path;
- which generation config file resolves provider references;
- which provider reference is the default for LLM-backed recipe steps;
- where run manifests and logs are written;
- which output roots are allowed for state-changing steps;
- which recipe types require human review;
- whether warnings stop execution;
- whether JSON output is the project default;
- which dry-run and run-manifest details the future GUI may expose.

It should not duplicate provider definitions:

```yaml
# Keep this in generation.config.yaml, not recipes.config.yaml.
providers:
  claude:
    type: anthropic
    model: claude-sonnet-4-5
    apiKeyEnv: ANTHROPIC_API_KEY
```

Instead, recipes and recipe runner config should reference provider names:

```yaml
# recipes.config.yaml
providers:
  generationConfig: generation.config.yaml
  defaultProviderRef: claude

# release-portfolio-review.yaml
recipe:
  execution:
    providerRef: claude
  steps:
    - id: localize
      command: portfolio.localize
      with:
        workspace: generated/portfolio/
        languages:
          - fi
          - sv
```

This keeps provider maintenance in one place while still letting recipes define
workflow-specific policy. It also keeps a production recipe from silently
changing model endpoints just because the team changed runner defaults.

The first SDK support could mirror the current generation config commands:

```bash
open-data-products config recipes --copy-to recipes.config.yaml
open-data-products config recipes --check recipes.config.yaml
open-data-products config recipes --print
open-data-products recipe validate recipes/release-portfolio-review.yaml \
  --config recipes.config.yaml
open-data-products recipe run recipes/release-portfolio-review.yaml \
  --config recipes.config.yaml \
  --dry-run
```

When a recipe path is omitted, `recipe validate`, `recipe explain`, and
`recipe run` should use `recipes.defaultRecipe` from the selected
`recipes.config.yaml`. V1 should not resolve arbitrary recipe ids by scanning
`recipes.paths`; that can be added later if users need a registry-like
experience.

`config recipes --check` should validate the runner config shape, verify that
configured recipe search paths are usable when present, verify that
`providers.generationConfig` points to a valid generation config when set, and
verify that `allowWrites` entries are project-relative directories. It should
not call model providers.

### Write Scope

`allowWrites` should be treated as a safety boundary, not as documentation.
Before any state-changing step runs, the runner should resolve all planned
outputs and generated run files to normalized project-relative paths.

V1 write-scope rules should be:

- reject absolute output paths unless a future explicit unsafe flag is added;
- reject `..` path traversal after normalization;
- reject writes outside configured `allowWrites` roots;
- create parent directories only inside allowed roots;
- treat `execution.manifestDir` as an allowed internal write root;
- reject symlink escapes when the platform can resolve them;
- include every planned write path in dry-run output before execution.

These checks should run for explicit outputs, derived outputs such as
`<workspace>/index.html`, run manifests, logs, and reports.

### Run Manifest

The run manifest is the evidence contract for CI, agents, and the future GUI.
V1 should keep it small.

The manifest should include at least:

- SDK version, run id, start time, completion time, status, and exit code;
- recipe path, recipe id, recipe version, and recipe type;
- recipe config path and generation config path when used;
- resolved provider reference and model per LLM-backed step, with secrets
  redacted;
- resolved SDK command arguments for each step;
- step status: `pending`, `running`, `passed`, `warned`, `failed`, `skipped`,
  or `review-needed`;
- generated artifact references and review gate status.

The manifest should reference generated artifacts by path and metadata. It
should not embed full generated document bodies.

## Precedence

Recipes should stay user-controlled. A likely precedence order is:

1. Explicit CLI provider and model overrides.
2. Step-level provider settings inside a selected recipe.
3. Recipe-level provider settings.
4. Recipe runner config defaults from `recipes.config.yaml`.
5. Generation config provider defaults from `generation.config.yaml`.
6. SDK defaults.

This keeps recipes helpful without making them a model whitelist.
