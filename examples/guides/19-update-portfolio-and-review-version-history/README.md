# Lecture 19: Update the Portfolio and Review Version History

A portfolio is a living artifact. Source material changes, new signals appear,
and product drafts improve over time. This lesson shows how to refresh a
workspace and review previous versions.

## 1. Add Or Change Source Material

Add a new file to one saved source lane:

```bash
cat > source_docs/signals/support-pressure-signal.txt <<'TXT'
Support operations note from April 19, 2026 at 10:15.

Priority accounts with unresolved tickets are waiting longer for first response.
Customer success teams want this signal linked to retention review workflows.
TXT
```

## 2. Refresh Changed Sources

```bash
open-data-products portfolio refresh portfolio/ \
  --provider claude \
  --model claude-sonnet-4-5
```

Refresh scans saved source lanes and sends changed or new source files to the
LLM. Existing unchanged artifacts are preserved where possible.

## 3. Force Full Reprocessing

```bash
open-data-products portfolio refresh portfolio/ \
  --all-sources \
  --provider claude \
  --model claude-sonnet-4-5
```

Use `--all-sources` when the full evidence set should be reprocessed.

## 4. Sync Edited YAML Without An LLM

```bash
open-data-products portfolio sync portfolio/
```

Use sync after directly editing ODPC fragments, ODPS products, or graph YAML.

## 5. Review Version History

```bash
find portfolio/versions -maxdepth 2 -type f | sort
```

Successful builds and refreshes snapshot previous portfolio outputs. The latest
`index.html` includes links to available versions so reviewers can compare
current and previous portfolio pages.

## 6. Localize The Updated Portfolio

After the portfolio has been refreshed, you can create localized static pages
from the latest workspace:

```bash
open-data-products portfolio localize portfolio/ \
  --languages "fi,sv,ar,vi" \
  --provider claude \
  --model claude-sonnet-4-5
```

Localization translates human-facing HTML strings without changing the
canonical ODPC, ODPS, or ODPG YAML artifacts. The command writes localized pages
such as `index.fi.html`, `index.sv.html`, `index.ar.html`, and `index.vi.html`
beside the main `index.html`.

Confirm that one localized page was written:

```bash
ls portfolio/index.fi.html
```

Download or open the localized HTML files for review with regional stakeholders.
Keep the canonical YAML files as the source of truth for agents, validation,
and automation.

## What You Learned

- Refresh processes changed and new source documents by default.
- `--all-sources` forces full reprocessing.
- `portfolio sync` rebuilds browser output from edited YAML without an LLM.
- Version snapshots support review and governance over time.
- `portfolio localize` adds localized HTML review pages without changing the
  canonical YAML artifacts.

## Next Lesson

Continue to
[Lecture 20: Final review: human view and agent-ready YAML](../20-final-review-human-view-and-agent-ready-yaml/).
