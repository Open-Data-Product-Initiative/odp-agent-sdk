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

A future recipe layer could define project-owned workflow policy:

```yaml
recipes:
  dev-fragment-draft:
    description: Generate draft ODPC fragments locally for fast iteration.
    provider: llamacpp-local
    steps:
      - command: generate
        kind: signal
        input: source_docs/signals/
        output: generated/fragments/

  dev-portfolio-build:
    description: Build a reviewable portfolio workspace with local models.
    provider: lmstudio-gemma4-12b
    steps:
      - command: portfolio.build
        workspace: portfolio/
      - command: portfolio.render
        workspace: portfolio/

  prod-fragment-generation:
    description: Generate release-candidate fragments with an online provider.
    provider: openai
    steps:
      - command: generate
        kind: signal
        input: source_docs/signals/
        output: generated/fragments/
      - command: validate
        input: generated/fragments/

  prod-portfolio-localization:
    description: Localize portfolio pages with production-grade model quality.
    provider: claude
    timeoutSeconds: 900
    steps:
      - command: portfolio.localize
        workspace: portfolio/
        languages: fi,sv,ar

  hybrid-graph-review:
    description: Infer graph edges locally, then review the portfolio online.
    contextFormat: gcf
    steps:
      - command: odpg.build
        provider: lmstudio-gemma4-12b
        contextFormat: gcf
      - command: portfolio.explain
        provider: claude
```

CI/CD automation can use the same shape:

```yaml
recipes:
  ci-validate-generated-fragments:
    description: Generate and validate draft fragments during CI.
    provider: ollama-gemma3n
    steps:
      - command: generate
        kind: signal
        input: source_docs/signals/
        output: generated/fragments/
      - command: validate
        input: generated/fragments/

  release-portfolio-review:
    description: Refresh, localize, and explain the release portfolio.
    provider: claude
    steps:
      - command: portfolio.refresh
        workspace: portfolio/
      - command: portfolio.localize
        workspace: portfolio/
        languages: fi,sv
      - command: portfolio.explain
        workspace: portfolio/
```

CI or release automation could then run:

```bash
open-data-products recipe run ci-validate-generated-fragments
open-data-products recipe run release-portfolio-review
```

The recipe names above are examples. The important design point is that a recipe
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
open-data-products recipe run dev-fragment-draft
open-data-products recipe run dev-portfolio-build
```

Then use production recipes for release, review, localization, or automated
portfolio updates:

```bash
open-data-products recipe run prod-fragment-generation
open-data-products recipe run prod-portfolio-localization
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
open-data-products recipe run dev-fragment-draft
open-data-products recipe run ci-validate-generated-fragments
open-data-products recipe run release-portfolio-review
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
      en: Validate Generated Fragments
    description:
      en: Validate generated data product fragments during CI.
  version: "1.0.0"
  type: ci
  steps:
    - id: validate-fragments
      command: validate
      with:
        input: generated/fragments/
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

## SDK Implementation Direction

The ODP Agent SDK is the first implementation target for ODPR-style workflow
recipes. The goal is to let SDK users define, validate, inspect, and run
declarative workflow recipes instead of relying only on built-in command
sequences.

A future SDK command set could look like this:

```bash
open-data-products recipe validate release-portfolio-review.yaml
open-data-products recipe explain release-portfolio-review.yaml
open-data-products recipe run release-portfolio-review.yaml --dry-run
open-data-products recipe run release-portfolio-review.yaml --json
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

## Precedence

Recipes should stay user-controlled. A likely precedence order is:

1. Explicit CLI provider and model overrides.
2. Step-level provider settings inside a selected recipe.
3. Recipe-level provider settings.
4. Top-level config defaults.
5. SDK defaults.

This keeps recipes helpful without making them a model whitelist.
