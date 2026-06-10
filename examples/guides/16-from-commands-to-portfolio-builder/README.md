# Lecture 16: From Commands to Portfolio Builder

You have already used fine-grained SDK capabilities: validation, explanation,
vocabulary helpers, generation, fragments, graphs, and catalogs. The portfolio
builder is the higher-level workflow that packages those parts into one guided
business process.

The shift matters because real portfolio work rarely starts as clean YAML. It
often starts as higher-level intent, source material, customer transcripts,
business notes, product briefs, and signals. The portfolio builder turns that
material into a structured portfolio that is easier for business users to
review, easier for technical teams to refresh, and easier for AI agents to reuse
through machine-readable YAML artifacts.

The builder does not replace the individual SDK commands. The isolated commands
remain the control surface for precise work. The portfolio builder is the
business-facing workflow for producing a complete portfolio result.

## 1. Isolated Commands Give You Control

Individual SDK commands are useful when you want control over one step:

- generate one business objective
- generate one use case
- generate one product reference
- generate one signal
- validate one YAML file
- build one ODPC catalog
- build one ODPG graph
- render HTML output

These commands are still valid when you need to inspect one artifact type,
debug one step, or control exactly what gets generated.

## 2. Portfolio Builder Connects The Parts

The portfolio builder creates the whole data product portfolio in one guided
flow. It connects:

- business objectives
- use cases
- signals
- product references
- catalog structure
- graph-ready artifacts
- HTML review output
- versioned portfolio outputs

You give higher-level intent, source material, or a customer transcript.
The builder creates a connected workspace that is easier to review, refresh,
compare, and reuse.

## 3. When To Use Each Approach

Use isolated commands when you are debugging one artifact, demonstrating one
object type, or need fine-grained control.

Use the portfolio builder when you want an end-to-end portfolio result, business
users need to understand the output, AI agents need machine-readable YAML
artifacts, and the workflow should be repeatable, refreshable, and comparable
over time.

## 4. Inspect The Portfolio Workflow

Check the portfolio command group:

```bash
open-data-products portfolio --help
```

You should see commands for building, refreshing, syncing, localizing,
rendering, and explaining a portfolio workspace.

Now create the source-lane structure used by the builder:

```bash
mkdir -p odps-sdk-guides/16-portfolio-workflow/source_docs/objectives
mkdir -p odps-sdk-guides/16-portfolio-workflow/source_docs/use-cases
mkdir -p odps-sdk-guides/16-portfolio-workflow/source_docs/signals
mkdir -p odps-sdk-guides/16-portfolio-workflow/source_docs/products
mkdir -p odps-sdk-guides/16-portfolio-workflow/portfolio
cd odps-sdk-guides/16-portfolio-workflow
```

These lanes match the higher-level intent the portfolio builder expects:
objectives, use cases, signals, and product source material.

## What You Learned

- Isolated commands give you fine-grained control.
- The portfolio builder packages SDK capabilities into an applied business
  workflow.
- Use isolated commands when you need precise control over one step.
- Use the portfolio builder when you need an end-to-end portfolio result.
- The portfolio command group gives you build, refresh, sync, localize, render,
  and explain workflows.
- Portfolio source lanes separate objectives, use cases, signals, and products.
- Both approaches are useful in real projects.

## Next Lesson

Continue to
[Lecture 17: What the portfolio builder creates](../17-what-the-portfolio-builder-creates/).
