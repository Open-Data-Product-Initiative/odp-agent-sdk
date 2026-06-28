# SDK Activity Logging Plan

This plan describes a fixed-format activity log for SDK use. The log should
record what happened through the SDK, especially CLI command execution, without
turning the SDK into a general debug-tracing framework.

The uncomfortable boundary is that a generic helper function is not enough by
itself. The SDK first needs a stable activity event contract. Rotation,
destination paths, and helper APIs should serve that contract instead of
becoming the design.

## Goal

Add an SDK activity log where one physical line represents one completed
activity.

Each line must show:

- timestamp;
- classification such as `[SUCCESS]`, `[WARNING]`, or `[FAILED]`;
- activity source, starting with CLI;
- CLI command and subcommand executed;
- short human-readable outcome;
- structured machine-readable details for scripts and support review.

Example line:

```text
2026-06-28T16:20:14Z [FAILED] source=cli command=portfolio.build exit_code=1 duration_ms=1842 message="Portfolio build completed with validation errors" details={"workspace":"portfolio/","warnings":2,"errors":3,"strict_validation":true}
```

## Non-Goals

- Do not replace validation reports, recipe run manifests, portfolio reports,
  or JSON command output.
- Do not log full generated document bodies, prompt bodies, source document
  contents, secrets, or raw LLM responses.
- Do not add a second console script or a separate logging daemon.
- Do not make MCP state-changing by introducing log-writing MCP tools before
  the MCP safety model is revisited.
- Do not treat this as Python debug logging. Debug logs can be added later as a
  separate verbosity feature.
- Do not log direct Python API calls in v1. The first implementation covers CLI
  calls only.
- Do not emit JSON Lines in v1. The required output is the readable fixed line
  format defined below.
- Do not add third-party logging dependencies in v1. Use Python's standard
  `logging` package and `logging.handlers.RotatingFileHandler`.

## Current Surfaces

The current CLI entry point is `open_data_products/cli.py::main`.

It already dispatches broad command families:

- document commands: `validate`, `explain`, `refs`, `summary`;
- OKF commands: `okf-validate`, `okf-summary`, `okf-import`, `okf-export`;
- config commands: `config generation`, `config recipes`;
- recipe commands: `recipe list`, `recipe validate`, `recipe catalog`,
  `recipe starter-catalog-check`, `recipe init`, `recipe explain`,
  `recipe search`, `recipe run`, `recipe plan`, `recipe dry-run`;
- generation command: `generate`;
- ODPC commands: `odpc-summary`, `odpc-build`, `odpc-search`,
  `odpc-artifacts`;
- ODPV commands: `odpv-summary`, `odpv-search`, `odpv-resolve`,
  `odpv-explain`, `odpv-relationship`, `odpv-context`;
- ODPG commands: `odpg-summary`, `odpg-build`, `odpg-traverse`,
  `odpg-analyze`, `odpg-agent-context`, `odpg-generate`, `odpg-convert`;
- portfolio commands: `portfolio build`, `portfolio refresh`,
  `portfolio sync`, `portfolio localize`, `portfolio render`,
  `portfolio explain`;
- agent commands: `manifest`, `serve`;
- product commands registered by `add_product_subparser(...)`.

The v1 logging implementation should wrap the CLI dispatch path first. V1 writes
one terminal outcome line per CLI invocation. LLM-backed CLI workflows also write
a separate `llm.invoke` line when the provider is about to be invoked, including
safe provider and model metadata. Deeper workflow modules should not write their
own activity lines in v1; instead, command branches may add safe summary facts
to a shared activity context before returning.

## Event Contract

Introduce one internal activity event model under the package root, likely in
`open_data_products/activity.py`.

Recommended fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `timestamp` | ISO 8601 UTC string | When the event completed. |
| `level` | enum string | `SUCCESS`, `INFO`, `WARNING`, or `FAILED`. |
| `source` | string | `cli` in v1; later `python-api`, `mcp`, or `recipe`. |
| `command` | string | Canonical command id such as `portfolio.build`. |
| `exit_code` | int or null | CLI exit code when available. |
| `duration_ms` | int or null | Wall-clock command duration. |
| `message` | string | One short sentence describing the outcome. |
| `details` | dict | Small structured summary with safe scalar values. |

Classification rules:

- `[SUCCESS]`: command completed with exit code `0` and no warning condition
  was reported.
- `[WARNING]`: command completed with exit code `0`, but validation warnings,
  non-strict validation failures, missing optional tooling, evidence gaps, or
  recoverable workflow warnings were reported.
- `[FAILED]`: command returned a non-zero exit code or raised an exception
  handled by the CLI.
- `[INFO]`: non-terminal informational activity that is useful but not a
  command outcome. Use sparingly in v1.

The command id must be deterministic:

```text
validate
generate
llm.invoke
recipe.run
recipe.plan
portfolio.build
portfolio.refresh
odpc-build
odpg-agent-context
product.<subcommand>
```

For nested argparse commands, join the root command with its subcommand by a
dot. For existing hyphenated top-level commands, keep the current CLI spelling.

## Line Format

Use a line-oriented format that is readable in a terminal and still parseable.
This is the only v1 log format.

Recommended v1 format:

```text
<timestamp> [<LEVEL>] source=<source> command=<command> exit_code=<exit_code> duration_ms=<duration_ms> message="<escaped message>" details=<compact-json>
```

Rules:

- one event is one line;
- no embedded newlines;
- timestamp is UTC with `Z`;
- classification is always bracketed;
- LLM invocation lines use command id `llm.invoke`, level `[INFO]`, and details
  such as `parent_command`, `provider`, `provider_type`, `model`, `phase`, and
  artifact `kind` when available;
- `message` is escaped with JSON string escaping and then written inside double
  quotes;
- `details` is compact JSON with `ensure_ascii=True`, `sort_keys=True`, and no
  embedded newlines;
- path values are user-provided relative paths when possible;
- absolute paths, environment variable values, API keys, prompt content, and
  source document bodies are not logged.

Examples:

```text
2026-06-28T16:20:14Z [SUCCESS] source=cli command=validate exit_code=0 duration_ms=41 message="Document validation passed" details={"document":"product.yaml","spec":"odps","warnings":0}
2026-06-28T16:22:03Z [WARNING] source=cli command=portfolio.sync exit_code=0 duration_ms=297 message="Portfolio sync completed with validation warnings" details={"workspace":"portfolio/","warnings":4,"errors":0,"strict_validation":false}
2026-06-28T16:24:51Z [FAILED] source=cli command=generate exit_code=1 duration_ms=918 message="Generation failed before writing artifacts" details={"kind":"odps-product","provider":"openai","output":"generated/"}
```

## Log Destination And Rotation

V1 logging is enabled by default. The log is evidence of what was done in a
workspace, so the default destination is inside the active workspace rather than
in a global user-level log directory.

Use Python's standard `logging` package for the writer and
`logging.handlers.RotatingFileHandler` for size-based rotation. Do not add
Loguru, structlog, or another logging dependency for v1. The SDK-specific work
is the activity event contract, workspace resolution, redaction, and fixed-line
formatter.

Default behavior:

- log file path: `.open-data-products/activity.log` under the resolved SDK
  workspace root;
- when a command is launched from a subdirectory, walk upward directory by
  directory and use the nearest containing workspace root instead of creating a
  second subdirectory-local log;
- workspace-root markers are, in priority order, an existing
  `.open-data-products/` directory, `portfolio.yaml`, `recipes.config.yaml`,
  `generation.config.yaml`, and `.git/`; marker priority only breaks ties within
  the same directory;
- if no marker is found, treat the current working directory as the workspace
  root and create `.open-data-products/activity.log` there; this fallback is
  intentional so default-on logging still records ad hoc SDK commands;
- create the directory on first write;
- rotate by file size using Python standard library `RotatingFileHandler`;
- default max size: `5 MB`;
- default retained files: `5`;
- rotated names follow the standard suffix pattern:
  `activity.log.1`, `activity.log.2`, and so on.

Add environment-variable overrides:

```text
OPEN_DATA_PRODUCTS_ACTIVITY_LOG=0
OPEN_DATA_PRODUCTS_ACTIVITY_LOG_PATH=/path/to/activity.log
OPEN_DATA_PRODUCTS_ACTIVITY_LOG_MAX_BYTES=5242880
OPEN_DATA_PRODUCTS_ACTIVITY_LOG_BACKUPS=5
```

Environment-variable precedence:

1. `OPEN_DATA_PRODUCTS_ACTIVITY_LOG=0` disables activity logging and wins over
   every other logging setting.
2. `OPEN_DATA_PRODUCTS_ACTIVITY_LOG_PATH` uses that exact file path and bypasses
   workspace-root resolution.
3. `OPEN_DATA_PRODUCTS_ACTIVITY_LOG_MAX_BYTES` and
   `OPEN_DATA_PRODUCTS_ACTIVITY_LOG_BACKUPS` tune rotation for the selected
   path.
4. If no override is provided, use the resolved workspace default.

If the log path cannot be opened, the CLI should continue and print one warning
to stderr. Logging failures must not fail SDK commands in v1.

## CLI Integration

Wrap the parsed CLI execution path in `open_data_products/cli.py::main`.

The wrapper should:

1. parse args;
2. derive the canonical command id from `args.command` and nested command
   attributes such as `args.recipe_command` or `args.portfolio_command`;
3. start a monotonic timer;
4. execute the existing command logic;
5. inspect the exit code and known payload summary signals;
6. write exactly one terminal activity line for that command;
7. preserve the existing stdout, stderr, JSON output, and exit code behavior.

This should not require every command branch to know about files and rotation.
Command branches may optionally return or attach small summary details for the
logger. The central wrapper remains responsible for writing.

Because `argparse` can exit during parsing, the CLI wrapper must cover parse
failures separately. Invalid arguments and unknown commands should write one
`[FAILED]` activity line when logging is enabled, then preserve the normal
argparse stderr and exit code. `--help` and `--version` should not write
activity lines.

Introduce a small activity context object for command branches to populate. The
context should carry:

- detail fields such as `workspace`, `document`, `kind`, `provider`,
  `warnings`, `errors`, and files-written counts;
- an explicit warning flag when a command exits `0` but should classify as
  `[WARNING]`;
- the human-readable message override for commands with better outcome text.

The wrapper should classify from the exit code first, then from the warning flag
and summary counts in the activity context.

For LLM-backed commands, write a separate `[INFO]` `llm.invoke` line after the
provider settings are resolved and the client is created, but before the
workflow function makes model calls. The line must include the parent command,
provider, provider type, model, and a phase label when useful.

Do not add Python API or MCP logging in v1. Those surfaces can reuse the same
event contract later if the SDK needs activity evidence outside CLI calls.

## Workflow-Level Details

The v1 command event should include safe details for high-value workflows:

- `validate`: document path, detected spec, valid flag, error count, warning
  count.
- `generate`: input path, output path, kind, provider reference, model name,
  artifact count when known, validation warning/error counts.
- `portfolio build/refresh`: workspace, changed-source count when known,
  artifact counts, LLM phase count, validation mode, warning/error counts.
- `portfolio sync/render/explain`: workspace, artifact counts, validation mode,
  warning/error counts.
- `portfolio localize`: workspace, language list, provider reference, model
  name, localized file count when known.
- `recipe run/plan/dry-run`: recipe path or starter id, execute/dry-run mode,
  step count, allowed LLM flag, review approval flag, run manifest path when
  written.
- `recipe init`: starter id, output workspace, parameterized flag, files
  written count.
- `odpc-build` and `odpg-build`: input folder, output path, optional TOON/GCF
  outputs, validation flag, object/edge counts when known.
- `okf-import` and `okf-export`: source, output, files written count.

Where a command does not expose summary fields yet, log only command id,
exit code, duration, and a short message. Do not introduce broad refactors just
to enrich the first logging release.

## Privacy And Safety

The activity log is operational metadata, not a content archive.

Redaction rules:

- redact values for keys containing `key`, `token`, `secret`, `password`,
  `authorization`, or `credential`;
- do not serialize full argparse namespaces;
- do not log arbitrary exception tracebacks by default;
- do not log prompt templates, prompt inputs, source document text, generated
  artifact bodies, or full validation result arrays;
- prefer counts, logical ids, filenames, command ids, and boolean flags.

## Testing Plan

Add focused tests before implementation:

- formatting test: one event renders to exactly one line with bracketed level
  and compact JSON details;
- rotation config test: custom max bytes and backup count create rotated files
  through the standard handler;
- CLI success test: `validate` writes `[SUCCESS]` with command `validate`;
- CLI warning test: portfolio non-strict validation failure writes
  `[WARNING]` while preserving exit code `0`;
- CLI failure test: invalid input writes `[FAILED]` and preserves non-zero
  exit code;
- redaction test: sensitive detail keys are masked;
- disabled logging test: `OPEN_DATA_PRODUCTS_ACTIVITY_LOG=0` writes nothing.
- env precedence test: disabled logging wins over an explicit log path.
- explicit path test: `OPEN_DATA_PRODUCTS_ACTIVITY_LOG_PATH` bypasses workspace
  discovery.
- parse failure test: invalid CLI arguments write `[FAILED]` and preserve
  argparse stderr and exit code.
- help/version test: `--help` and `--version` do not write activity lines.
- LLM invocation test: `generate` writes a separate `[INFO]` `llm.invoke` line
  with provider, provider type, model, parent command, and kind before the
  command outcome line.
- default logging test: a CLI call without logging environment overrides writes
  `.open-data-products/activity.log` below `tmp_path`.
- subdirectory logging test: a CLI call from a child directory writes to the
  resolved parent workspace log when a workspace marker exists.
- nearest marker test: workspace discovery uses the nearest marked parent, with
  marker priority only breaking ties inside the same directory.
- unwritable log path test: a configured path failure prints one stderr warning
  and preserves the command's normal exit code.

Use `tmp_path` for all log paths and command inputs. Do not write tests against
the developer machine's real home directory or current project activity log.

## Implementation Tasks

1. Create `open_data_products/activity.py` with the event dataclass, level
   constants, detail sanitizer, line formatter, and rotating writer factory.
2. Add unit tests in `tests/test_activity.py` for formatting, redaction,
   disabling, destination creation, and rotation.
3. Add a small CLI helper in `open_data_products/cli.py` to derive canonical
   command ids from parsed args.
4. Add an activity context object that command branches can populate without
   writing activity lines themselves.
5. Wrap command parsing and execution in timing and terminal
   activity-event writing while preserving all existing stdout, stderr, JSON,
   and exit code behavior.
6. Add targeted CLI tests using a temporary log path environment override.
7. Enrich high-value command details only where data is already available in
   the branch payload.
8. Update `docs/development/README.md` and user-facing command docs because the
   default behavior creates `.open-data-products/activity.log` in SDK
   workspaces.
9. Run the repository pre-completion checks:

```bash
pytest -q
python -c "import open_data_products"
python -m open_data_products.cli manifest --json | python -m json.tool
test ! -e docs/superpowers
git diff --check
```

## Resolved Decisions

- Logging is enabled by default.
- The default log is workspace-local:
  `.open-data-products/activity.log`.
- CLI calls launched from workspace subdirectories use the resolved parent
  workspace log.
- V1 logs CLI calls only.
- V1 writes one terminal outcome line per CLI invocation; workflow internals
  populate context instead of writing their own outcome lines.
- LLM-backed CLI workflows also write an `[INFO]` `llm.invoke` line with
  provider and model details.
- V1 uses the readable fixed line format, not JSON Lines.
- Invalid CLI arguments are logged as `[FAILED]`; `--help` and `--version` are
  not logged.
- Explicit logging environment variables follow disable, path, rotation,
  workspace-default precedence.
- If logging fails, the CLI warns on stderr and continues with its normal exit
  code.
