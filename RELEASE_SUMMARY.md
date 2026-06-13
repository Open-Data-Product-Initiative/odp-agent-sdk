# Release Summary: 0.2.2

Release 0.2.2 adds compact LLM context sidecars for ODPC catalogs and ODPG
graphs. YAML remains the canonical artifact for validation, publishing, and
governance, while TOON and GCF provide smaller prompt-ready context for agents,
generation workflows, MCP clients, and portfolio review.

## Highlights

- ODPC and ODPG build commands can now emit compact LLM context sidecars while
  keeping YAML as the source of truth: `odpc-build --toon/--gcf` writes catalog
  context files, and `odpg-build --toon/--gcf` writes graph context files.
- GCF graph sidecars use deterministic local node IDs so edge context avoids
  repeating full endpoint identifiers; TOON sidecars keep catalog and graph
  collections in compact table form.
- ODPC GCF support covers tiny examples, guide catalog fragments, and portfolio
  workspace catalogs, giving catalog workflows both TOON and GCF output options.
- `odpg-agent-context --context-format {auto,gcf,toon,yaml} --json` can attach
  compact graph context text to the agent context response. The command still
  loads and validates `graph.yaml`; `auto` prefers sibling `graph.gcf`, then
  `graph.toon`, then YAML text, while explicit `gcf`, `toon`, or `yaml` lets an
  agent require one format.
- `load_summary` and the MCP `load_summary` tool now advertise sibling `.gcf`
  and `.toon` context sidecars as body-free metadata, so agents can discover the
  preferred compact artifact before deciding whether to read it.
- Generation prompt source loading now prefers sibling `.gcf`, then `.toon`, for
  YAML catalog or graph context files before falling back to YAML text. Source
  folders include YAML artifacts only when such compact sidecars exist, so
  ordinary generation config files are not pulled into prompts accidentally.
- `odpg-build --context-graph previous-graph.yaml` can pass an existing graph
  into edge inference as prior prompt context, preferring `previous-graph.gcf`,
  then `.toon`, then YAML text.
- The new `scripts/measure_context_sidecars.py` helper compares YAML, TOON, and
  GCF bytes and tokenizer counts on repository fixtures. With `o200k_base`, the
  portfolio catalog drops from 2,311 YAML tokens to 1,405 TOON tokens and 1,388
  GCF tokens, while the portfolio graph drops from 970 YAML tokens to 739 TOON
  tokens and 561 GCF tokens.
- Development documentation now explains the GCF implementation boundary,
  compact-context measurements, MCP/resource summary discovery, generation
  prompt input behavior, and the sidecar-first guidance for agent workflows.
- The Udemy guide flow under `examples/guides/` was smoke-tested against the
  current SDK surface, including local Ollama generation, ODPS product drafts,
  ODPC catalog building, ODPG graph building, portfolio build/refresh/sync,
  final validation, and localized portfolio output.

## Verification

- `pytest -q`
- `python3 -c "import open_data_products; print(open_data_products.__version__)"`
- `python3 -m open_data_products.cli manifest --json | python3 -m json.tool`
- `python3 scripts/measure_context_sidecars.py --encoding o200k_base`
- Prompt rendering smoke check for all bundled generation prompts.
- Guide link and sample-file checks for `examples/guides/`.
- Udemy guide smoke flow using local Ollama `qwen2.5` for generation,
  portfolio, graph, and localization commands.
- `test ! -e docs/superpowers`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m build`
- `python3 -m twine check dist/*`
