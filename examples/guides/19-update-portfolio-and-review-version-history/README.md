# Lecture 19: Update the Portfolio and Review Version History

A portfolio is a living artifact. Source material changes, new signals appear,
and product drafts improve over time. This lesson is about maintaining that
portfolio without losing control of the previous version.

The important idea is that `refresh` and `sync` have different purposes:

```text
source_docs/ changed        -> refresh proposes the next portfolio version
generated YAML edited by you -> sync rebuilds outputs from controlled edits
```

When you add raw source material, the LLM may infer more than one change. A new
signal can create a new signal fragment, update graph relationships, affect use
case links, or suggest changed product details. Treat the refreshed portfolio as
a proposed next version that you review before accepting.

Continue from the same workspace folder you created in Lecture 18:

```text
/content/odp-portfolio-workspace
```

All commands in this lesson assume the current folder contains both
`source_docs/` and `portfolio/`.

## 1. Add Or Change Source Material

Add a new file to one saved source lane. In Colab, run this in a shell cell
from `/content/odp-portfolio-workspace`:

```bash
%%bash
cat > source_docs/signals/support-pressure-signal.txt <<'TXT'
Support operations note from April 19, 2026 at 10:15.

Priority accounts with unresolved tickets are waiting longer for first response.
Customer success teams want this signal linked to retention review workflows.
TXT
```

## 2. Refresh Changed Sources

```bash
!open-data-products portfolio refresh portfolio/ \
  --provider claude \
  --model claude-sonnet-4-5
```

Refresh snapshots the current workspace, sends changed or new source files to
the LLM, and merges the generated result into the existing portfolio. Existing
catalog objects, product drafts, and graph links are carried forward unless the
refresh produces an object or edge with the same stable identity. New evidence
can still add objects or relationships, so treat refresh as a proposed next
version and review the diff before accepting it.

After refresh, inspect the changed workspace:

```bash
!find portfolio/odpc/fragments -maxdepth 1 -type f | sort
!open-data-products portfolio explain portfolio/
```

If you use Git, this is also the right moment to compare the refreshed YAML
with the previous version:

```bash
!git diff -- portfolio
```

In Colab, if you are not using Git, rely on the `portfolio/versions/` snapshots
created by the SDK and the generated HTML version links.

## 3. Force Full Reprocessing

```bash
!open-data-products portfolio refresh portfolio/ \
  --all-sources \
  --provider claude \
  --model claude-sonnet-4-5
```

Use `--all-sources` when the full evidence set should be reprocessed.

This can change more of the portfolio than a normal refresh. Use it when you
want the current model and prompts to reconsider the whole evidence set, not
only changed source files.

## 4. Sync Edited YAML Without An LLM

```bash
!open-data-products portfolio sync portfolio/
```

Use sync after directly editing ODPC fragments, ODPS products, or graph YAML.
This does not interpret raw source material again. It is the safer maintenance
path when you already know the exact YAML change you want.

## 5. Review Version History

```bash
!find portfolio/versions -maxdepth 2 -type f | sort
```

Successful builds and refreshes snapshot previous portfolio outputs. The latest
`index.html` includes links to available versions so reviewers can compare
current and previous portfolio pages.

One caveat: version snapshots are not automatically localized. Localization
creates translated pages for the active portfolio workspace, not for every older
snapshot under `portfolio/versions/`. If translated review evidence matters,
localize the portfolio when that version is current and preserve the zipped
localized package.

For portfolio maintenance, keep this habit:

```text
refresh -> compare -> decide what to keep
sync    -> rebuild after deliberate YAML edits
```

## What You Learned

- Refresh processes changed and new source documents by default.
- Refresh may create new or changed portfolio objects because it interprets
  new evidence.
- `--all-sources` forces full reprocessing and can change more of the
  portfolio.
- `portfolio sync` rebuilds outputs from edited YAML without asking an LLM to
  reinterpret raw source material.
- Version snapshots support review, comparison, and governance over time.
- Localized pages are generated for the current portfolio workspace; older
  snapshots are not translated automatically.

## Next Lesson

Continue to
[Lecture 20: How to localize a portfolio](../20-how-to-localize-portfolio/).
