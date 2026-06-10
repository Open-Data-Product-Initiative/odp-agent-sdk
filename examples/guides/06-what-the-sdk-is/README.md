# Lecture 6: What the Open Data Products SDK Is

The Open Data Products SDK is the practical layer on top of the
OpenDataProducts.org standards family. It gives you command-line and Python
tools for working with ODPS data products, ODPC catalogs, ODPG graphs, and ODPV
vocabulary terms.

## 1. The Mental Model

The standards define what good data product artifacts look like. The SDK helps
you create, check, explain, connect, and render those artifacts.

Use the SDK when you need to:

- validate YAML files before sharing them
- explain a standards file in human-readable form
- use controlled vocabulary terms consistently
- generate standards-aligned YAML from source material
- collect ODPC fragments into catalogs
- build ODPG relationship graphs
- create portfolio workspaces for humans and AI agents

## 2. CLI and Python Usage

Most course lessons use the CLI:

```bash
open-data-products --help
```

The same package can also be used from Python when you want to embed SDK
behavior in scripts, notebooks, or automation.

## 3. Standards-Aware YAML

The SDK works with YAML because YAML is easy for people to review and easy for
AI agents to read. A product, catalog, graph, or vocabulary-backed workflow can
be stored in files, versioned in Git, and passed into automation.

## 4. Where The Course Goes Next

The next lessons move from basic SDK commands to LLM-assisted generation,
fragments, graphs, catalogs, and finally a portfolio builder that combines the
pieces into one repeatable workflow.

## What You Learned

- The SDK is the practical tool layer for ODPS, ODPC, ODPG, and ODPV.
- The CLI is the main learning surface in this course.
- YAML artifacts are useful for both human review and AI-agent workflows.
- Portfolio workflows build on the smaller SDK commands.

## Next Lesson

Continue to [Lecture 7: Installing and running the SDK](../07-installing-and-running-sdk/).
