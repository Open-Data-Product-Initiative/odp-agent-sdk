# Lecture 17: What the Portfolio Builder Creates

Before running the portfolio builder, it helps to know the shape of the inputs
and the workspace it will create. This lesson is the map for the hands-on build
in Lecture 18.

Data product work is often fragmented. Ideas live in slides. Requirements live
in spreadsheets. Governance notes live in documents. Technical details live in
repositories. Catalog entries live elsewhere.

The portfolio builder connects this scattered intent into structured portfolio
artifacts.

## 1. Input Map

Portfolio build starts from source lanes. Each lane can contain Markdown or
text files:

- `source_docs/objectives/`: business goals, outcomes, KPIs, or strategic
  intent
- `source_docs/use-cases/`: decisions, workflows, user needs, or business
  processes that need data
- `source_docs/signals/`: market, operational, customer, quality, or usage
  evidence
- `source_docs/products/`: product briefs, transcripts, emails, or technical
  notes that describe possible data products

The separated lanes help the builder understand what kind of portfolio object
each source document should become.

## 2. Output Map

A successful build creates a portfolio workspace. In the next lesson, you will
inspect files like these:

```text
portfolio/
  index.html
  portfolio.yaml
  odpc/
    catalog.yaml
    fragments/
  odpg/
    graph.yaml
  odps/
    products/
  versions/
```

The generated ODPC fragments capture portfolio objects. The ODPC catalog
collects those objects. The ODPG graph captures relationships. The ODPS product
files describe generated data product drafts.

## 3. Human And Agent Outputs

The portfolio builder creates outputs for two audiences:

- `index.html` is for people who need to review the portfolio in a browser.
- YAML files are for AI agents, validation, automation, version control, and
  later refreshes.

This is why the builder matters: human reviewers can inspect one portfolio
page, while agents and scripts can read the same underlying structured
artifacts.

## 4. Path To The Next Lesson

In Lecture 18, you will create the source lanes, add sample source files, run
`portfolio build`, inspect the generated workspace, and open `index.html` in a
browser.

## What You Learned

- Portfolio build starts from four source lanes: objectives, use cases,
  signals, and products.
- The generated workspace contains HTML for humans and YAML for agents and
  automation.
- The workspace connects ODPC fragments, an ODPC catalog, an ODPG graph, ODPS
  product drafts, and versioned portfolio outputs.

## Next Lesson

Continue to
[Lecture 18: Build the first portfolio in Colab](../18-build-first-portfolio-in-colab/).
