# Lecture 15: Working with ODPC Catalogs

ODPC catalogs collect product references, use cases, business objectives, and
signals into one structured portfolio artifact. A catalog is easier to review
than isolated fragments and can feed portfolio views, graph workflows, and
agent-ready automation.

The SDK can help you work with catalogs in several ways:

- build an ODPC catalog from fragment files
- validate catalog YAML
- summarize catalog contents
- render a browser-viewable catalog HTML file
- search bundled ODPC object guidance while reviewing catalog structure

This lesson focuses on three practical tasks: building a catalog from
fragments, checking the generated catalog, and searching ODPC guidance while
reviewing catalog structure.

## 1. Prepare Folders

```bash
mkdir -p odps-sdk-guides/15-odpc-catalog/fragments
mkdir -p odps-sdk-guides/15-odpc-catalog/output
```

## 2. Add Fragment Files

From the repository root, copy the sample fragment files from this lesson
folder:

```bash
cp examples/guides/15-working-with-odpc-catalogs/fragments/*.yaml \
  odps-sdk-guides/15-odpc-catalog/fragments/

cd odps-sdk-guides/15-odpc-catalog
```

You can also use the fragments generated in Lecture 13.

Expected fragment types:

- `product_reference_*.yaml`
- `use_case_*.yaml`
- `business_objective_*.yaml`
- `signal_*.yaml`

## 3. Build And Render The ODPC Catalog

```bash
open-data-products odpc-build fragments/ \
  --output output/catalog.yaml \
  --html output/catalog.html
```

The command collects the fragment folder into one ODPC catalog document and can
also render a browser-openable HTML review page.

Open `output/catalog.html` in a browser to review the catalog visually.

## 4. Validate And Summarize The Catalog

```bash
open-data-products validate output/catalog.yaml
open-data-products odpc-summary output/catalog.yaml
```

Validation checks that the catalog is standards-shaped. Summary output gives a
quick terminal view of the catalog contents.

## 5. Search ODPC Guidance

```bash
open-data-products odpc-search "business operational analytical policy user needs" \
  --limit 5
```

This searches bundled ODPC object guidance, not the generated catalog file. It
is especially useful for agents and helper scripts that need to choose whether
source material should become a `UseCase`, `BusinessObjective`, `Signal`, or
`ProductReference`. Humans can also use it as a quick terminal reference while
reviewing catalog structure. It is similar to ODPV search: ODPV search helps
choose standard vocabulary terms, while ODPC search helps choose catalog object
types. This example returns the `UseCase` guidance record because those terms
describe when a use case object is the right ODPC object to use.

## What You Learned

- ODPC catalogs collect related portfolio objects into one artifact.
- The SDK can build, validate, summarize, render, and support review of ODPC
  catalog structures.
- `odpc-search` helps you find bundled ODPC object guidance while reviewing
  catalog structure.
- Catalogs are easier to review than isolated fragments.
- The same catalog can support browser review, graph building, portfolio views,
  and AI-agent workflows.

## Next Lesson

Continue to
[Lecture 16: From commands to portfolio builder](../16-from-commands-to-portfolio-builder/).
