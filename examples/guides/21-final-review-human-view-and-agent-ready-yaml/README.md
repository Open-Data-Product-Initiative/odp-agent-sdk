# Lecture 21: Final Review: Human View and Agent-Ready YAML

The portfolio workflow serves two audiences. The HTML view is for humans. The
YAML files are for AI agents, automation, validation, and long-term version
control.

Continue from the same workspace folder you created in Lecture 18:

```text
/content/odp-portfolio-workspace
```

## 1. Human Review

Open:

```text
/content/odp-portfolio-workspace/portfolio/index.html
```

Review the overview, artifact types, products, graph, and about tabs. Product
cards open detailed views with pricing plans, linked access, SLA, data quality,
payment, licensing, and raw artifact references when those sections exist.

If you localized the portfolio in Lecture 20, review those pages from the same
workspace too:

```text
/content/odp-portfolio-workspace/portfolio/index.fi.html
/content/odp-portfolio-workspace/portfolio/index.sv.html
```

## 2. Agent-Ready YAML

Review the generated YAML files:

```bash
!find portfolio -path "*/versions/*" -prune -o -name "*.yaml" -print | sort
```

The important files are:

- `portfolio/portfolio.yaml`
- `portfolio/odpc/catalog.yaml`
- `portfolio/odpc/fragments/*.yaml`
- `portfolio/odpg/graph.yaml`
- `portfolio/odps/products/*.yaml`

## 3. Validate The Artifacts

```bash
!open-data-products validate portfolio/odpc/catalog.yaml
!open-data-products validate portfolio/odpg/graph.yaml
!open-data-products portfolio explain portfolio/
```

Portfolio commands default to warning mode for schema-invalid generated ODPS
drafts so users can still review the browser output. Use `--strict-validation`
when automation should fail on schema errors.

## What You Learned

- HTML supports human portfolio review.
- YAML supports AI agents and automation.
- Final review checks both the browser experience and the generated YAML
  artifacts.
- Catalogs provide structure, graphs provide relationships, and validation
  supports governance.

## Next Lesson

Continue to [Lecture 22: Wrap-up and next steps](../22-wrap-up-and-next-steps/).
