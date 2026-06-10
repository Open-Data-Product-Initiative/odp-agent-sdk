# Lecture 21: Wrap-up and Next Steps

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

## 3. Apply This With Your Own Material

Start with source material from a real data product or portfolio idea:

- business objectives
- use cases
- market, operational, customer, quality, or usage signals
- product briefs, emails, transcripts, or governance notes

Put those files into the four source lanes:

```text
source_docs/objectives/
source_docs/use-cases/
source_docs/signals/
source_docs/products/
```

Run `portfolio build` to create the first workspace. Review `index.html` with
people, then inspect the YAML files with agents, scripts, validation commands,
or version control.

Then keep the portfolio alive by refreshing sources, syncing edited YAML, and
using version snapshots during review. When the audience changes, localize the
HTML pages without changing the canonical YAML artifacts.

## 4. Reference Material

Use these references when you want to go deeper:

- [SDK README](../../../README.md)
- [SDK API reference](../../../docs/API.md)
- [SDK command guide](../../../docs/commands.md)
- [Generation guide](../../../docs/generation.md)
- [Portfolio development notes](../../../docs/portfolio-development.md)
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
