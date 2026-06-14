# SDK Capability Drift Reports

This folder contains dated drift reports that compare helper scripts in the
Open Data Product specification repositories against the SDK surfaces exposed
for humans and AI agents.

The reports help detect when a capability exists in ODPC, ODPG, or ODPV source
tooling but is missing, partially exposed, or intentionally left out of the
`open-data-products` SDK.

## Report Files

Reports use this filename pattern:

```text
YYYY-MM-DD-sdk-capability-drift.md
```

There is one report per day. If the drift check runs more than once on the same
day, the latest run overwrites that day's report. This keeps a daily history
without creating multiple near-duplicate files.

## Current Inputs

The drift check compares the SDK against a source-backed inventory of upstream
helper scripts:

| Spec | Source area |
|---|---|
| ODPC | `odpc-v1.0/scripts/*.py` |
| ODPG | `odpg-v1.0/source/scripts/*.py` |
| ODPV | `odpv-v1.0/scripts/*.py` |

Each inventory row maps one upstream capability to the SDK's public Python API,
CLI helper, and MCP tool exposure where that mapping exists.

## How To Read A Report

Start with the top-level totals:

- `Checked capabilities` shows how many upstream capabilities were compared.
- `Partial capabilities` shows capabilities exposed through some SDK surfaces
  but not all surfaces.
- `Unresolved capabilities` shows capabilities that need human review.
- `Possible Drift Summary` lists unresolved capability candidates.

The detailed tables show each compared capability:

| Status | Meaning |
|---|---|
| `Covered` | All mapped SDK surfaces are present. |
| `Partial` | The capability exists in at least one SDK surface but is not mapped everywhere. |
| `Review` | No SDK mapping is configured yet; decide whether it belongs in the SDK. |
| `Possible drift` | A configured SDK mapping is missing. |

Rows marked `Review` or `Possible drift` should be reviewed and resolved by
adding SDK/API/CLI/MCP exposure, documenting the capability as upstream-only, or
updating the capability inventory when the expected mapping changes.

## Automation

The weekly GitHub Action is defined in:

```text
.github/workflows/capability-drift.yml
```

It runs every Monday at 06:00 UTC and can also be started manually with
`workflow_dispatch`. The action:

1. installs the package dependencies,
2. runs `scripts/check_capability_drift.py`,
3. validates the generated report,
4. runs the SDK import and manifest checks,
5. commits changed files under `docs/reports/capability-drift/`.

## Local Commands

Generate or refresh today's report:

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/check_capability_drift.py
```

Check that today's committed report is in sync:

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/check_capability_drift.py --check
```

After changing the drift script or SDK surfaces, also run:

```bash
pytest -q tests/test_capability_drift.py
python -c "import open_data_products"
python -m open_data_products.cli manifest --json | python -m json.tool
```

## AI Analysis Use

These dated reports are intended to become a history of implementation
alignment across ODPS, ODPC, ODPG, and ODPV. They can be used later as input for
AI-assisted analysis of which upstream specification capabilities tend to become
SDK/API/CLI/MCP work and which remain specification-maintenance tooling.
