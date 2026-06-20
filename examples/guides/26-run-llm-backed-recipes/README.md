# Lecture 26: Run LLM-Backed Recipes

LLM-backed recipes can generate or infer new artifacts. They require explicit
permission and review approval before execution.

## Before You Run This

The hosted examples use the `claude` provider from:

```text
examples/recipes/config/generation.config.yaml
```

Set the provider key in your shell before executing hosted workflows:

```bash
export ANTHROPIC_API_KEY="your-key"
```

Use a temporary copy so generated artifacts do not modify the repository:

```bash
repo="$(pwd)"
tmpdir="$(mktemp -d)"
cp -R "$repo/examples/recipes" "$tmpdir/recipes"
cd "$tmpdir/recipes"
```

## 1. Dry-Run First

Dry-run the graph build recipe:

```bash
open-data-products recipe run \
  workflows/odpg-build.yaml \
  --config config/recipes.config.yaml \
  --dry-run \
  --json
```

If the key is missing, provider readiness reports `missing-env`.

## 2. Execute With Both Gates

Run the graph build recipe only after review:

```bash
open-data-products recipe run \
  workflows/odpg-build.yaml \
  --config config/recipes.config.yaml \
  --execute \
  --allow-llm \
  --approve-review \
  --json
```

`--allow-llm` permits provider calls. `--approve-review` records that a
review-needed plan was approved before execution.

## 3. Inspect Graph Artifacts

```bash
sed -n '1,220p' workspace/odpg/graph.yaml
sed -n '1,80p' workspace/odpg/graph.toon
sed -n '1,80p' workspace/odpg/graph.gcf
```

The YAML is the canonical ODPG graph. TOON and GCF are compact context sidecars
for review, prompts, and agents.

## 4. Other LLM-Backed Recipe Commands

The implemented provider-backed recipe commands are:

- `generate`
- `odpg.build`
- `portfolio.build`
- `portfolio.refresh`
- `portfolio.localize`

Always dry-run first.

## What You Learned

- LLM-backed recipes require explicit execution gates.
- Provider readiness is visible before execution.
- Graph builds can write YAML, TOON, and GCF artifacts.

## Next Lesson

Continue to [Lecture 27: Portfolio Recipes End To End](../27-portfolio-recipes-end-to-end/).
