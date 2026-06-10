# Lecture 7: Installing and Running the SDK

This lesson gets a clean SDK workspace ready and runs the first simple command.
If Python or the SDK is not installed yet, complete
[Guide 00: Set Up Python](../00-setup-python/) first.

## 1. Create The Course Workspace

```bash
mkdir -p odps-sdk-guides
cd odps-sdk-guides
```

Create the folders used across later lessons:

```bash
mkdir -p source_docs
mkdir -p fragments
mkdir -p catalogs
mkdir -p graphs
mkdir -p portfolio
mkdir -p reports
```

## 2. Check The SDK Command

```bash
open-data-products --help
```

You should see the main command groups for validation, generation, ODPC, ODPG,
ODPV, and portfolio workflows.

## 3. Run A Simple JSON Command

```bash
open-data-products manifest --json
```

The manifest output is a machine-readable description of the SDK surface.

## 4. Keep The Folder Shape

The rest of the course uses this practical structure:

```text
source_docs/
fragments/
catalogs/
graphs/
portfolio/
reports/
```

You can create a separate lesson folder later when you want to keep one
exercise isolated.

## What You Learned

- The SDK command is `open-data-products`.
- `--help` shows the available workflows.
- `manifest --json` proves the package imports and the CLI can render
  machine-readable output.
- The course workspace separates source material, generated fragments,
  catalogs, graphs, portfolio outputs, and reports.

## Next Lesson

Continue to
[Lecture 8: Validating and explaining standards files](../08-validating-and-explaining-standards-files/).
