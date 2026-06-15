# Lecture 22: Wrap-up and Next Steps

You have completed the course path from SDK basics to a connected, reviewable,
agent-ready data product portfolio workflow.

## 1. What You Can Do Now

You can now use the Open Data Products SDK to:

- install and run the CLI
- validate and explain standards files
- use ODPV vocabulary helpers
- configure local and online LLM providers
- generate full ODPS product drafts
- generate ODPC fragments
- build and inspect ODPG graph relationships
- build ODPC catalogs
- create, refresh, sync, localize, render, and review a portfolio workspace
- inspect both browser output and machine-readable YAML artifacts

## 2. How The Pieces Fit

The individual SDK commands give you precise control over one artifact or one
step. The portfolio builder combines those capabilities into a repeatable
workflow for real portfolio work.

ODPS describes data products. ODPC organizes portfolio catalog objects. ODPG
describes relationships. ODPV keeps language consistent.

Together they create a practical pattern: business intent and source material
can become human-reviewable HTML and agent-ready YAML.

## 3. Portfolio As A Workflow

You can now treat the portfolio as a workflow, not only as a set of files. That
is important because real portfolio work is repeated: source material changes,
reviewers ask for updates, regional stakeholders need localized pages, and
agents need clean YAML artifacts.

The portfolio command group gives you a repeatable sequence:

```bash
open-data-products portfolio build \
  --objectives source_docs/objectives/ \
  --use-cases source_docs/use-cases/ \
  --signals source_docs/signals/ \
  --products source_docs/products/ \
  --output portfolio/

open-data-products portfolio refresh portfolio/
open-data-products portfolio sync portfolio/
open-data-products portfolio localize portfolio/ \
  --languages "fi,sv" \
  --provider claude \
  --model claude-sonnet-4-5
open-data-products portfolio render portfolio/
open-data-products portfolio explain portfolio/
```

This matters because the SDK keeps the workflow grounded in artifacts:

- source lanes keep business objectives, use cases, signals, and product briefs
  organized;
- ODPC catalogs describe the portfolio structure;
- ODPS product YAML keeps data product details machine-readable;
- ODPG graphs describe relationships between portfolio objects;
- HTML gives people a reviewable browser view;
- localization creates regional review pages without changing canonical YAML;
- version snapshots support governance and change review over time.

In other words, the portfolio workflow turns scattered source material into a
repeatable operating model: build, review, update, localize, validate, explain,
and keep improving.

## 4. Coming Next: ODPR Workflow Recipes

The next layer is ODPR: workflow recipes for repeatable SDK runs. Where the
portfolio command group gives you a built-in workflow, ODPR is intended to let
teams define their own workflows on top of the SDK.

An ODPR-style recipe could define:

- the ordered SDK steps to run;
- which provider or model to use for each step;
- input and output folders;
- validation gates;
- context formats such as YAML, TOON, or GCF;
- review and localization policy.

For example, a future recipe could capture a release review workflow:

```yaml
recipes:
  release-portfolio-review:
    description: Refresh, localize, render, and explain the release portfolio.
    provider: claude
    steps:
      - command: portfolio.refresh
        workspace: portfolio/
      - command: portfolio.localize
        workspace: portfolio/
        languages: fi,sv
      - command: portfolio.render
        workspace: portfolio/
      - command: portfolio.explain
        workspace: portfolio/
```

The value is simple: instead of copying command sequences between terminals,
notebooks, CI jobs, and team documents, a project can name the workflow and run
it consistently. ODPR is the direction for making those repeatable workflows
explicit, portable, and easier for both humans and AI agents to follow.

## 5. Apply This With Your Own Material

Start with source material from a real data product or portfolio idea:

- business objectives
- use cases
- market, operational, customer, quality, or usage signals
- product briefs, emails, transcripts, or governance notes

Put those files into the four source lanes:

```text
odp-portfolio-workspace/source_docs/objectives/
odp-portfolio-workspace/source_docs/use-cases/
odp-portfolio-workspace/source_docs/signals/
odp-portfolio-workspace/source_docs/products/
```

Run `portfolio build` from inside `odp-portfolio-workspace` to create the
`portfolio/` workspace output. Review `portfolio/index.html` with people, then
inspect the YAML files with agents, scripts, validation commands, or version
control.

Then keep the portfolio alive by refreshing sources, syncing edited YAML, and
using version snapshots during review. When the audience changes, localize the
HTML pages without changing the canonical YAML artifacts.

## 6. Reference Material

Use these references when you want to go deeper:

- [SDK README](../../../README.md)
- [SDK API reference](../../../docs/user/API.md)
- [SDK command guide](../../../docs/user/commands.md)
- [Generation guide](../../../docs/user/generation.md)
- [Portfolio development notes](../../../docs/development/portfolio.md)
- [ODPS product specification](https://opendataproducts.org/v4.1/)
- [ODPC catalog specification](https://opendataproducts.org/odpc-v1.0/)
- [ODPG graph specification](https://opendataproducts.org/odpg-v1.0/)
- [ODPV vocabulary specification](https://opendataproducts.org/odpv-v1.0/)

## Thank You

Thank you for taking the course. If you apply these ideas in your own work,
consider sharing your experience, lessons learned, and examples in a blog post
or on LinkedIn. Your notes can help other data, analytics, and AI practitioners
understand how open data product standards can work in real projects.

You can also connect with me on
[LinkedIn](https://ae.linkedin.com/in/jarkkomoilanen) for further discussion.
