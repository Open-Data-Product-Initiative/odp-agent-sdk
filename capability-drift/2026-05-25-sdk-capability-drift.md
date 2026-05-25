# SDK Capability Drift Report

This report compares upstream Open Data Product specification helper scripts against the SDK surfaces exposed for humans and AI agents.

Last drift detection run: `2026-05-25T09:59:52Z`

- Upstream sources: ODPC, ODPG, and ODPV specification repositories
- SDK surfaces: public Python API, unified/spec CLI helpers, and MCP tools
- Checked capabilities: 17
- Partial capabilities: 4
- Unresolved capabilities: 2

Possible capability drift detected. Review rows marked `Review` or `Possible drift`.

## Possible Drift Summary

| Spec | Source | Capability | Suggested action |
|---|---|---|---|
| ODPV | `odpv-v1.0/scripts/check_cross_spec_drift.py` | Track terminology drift across ODPS, ODPC, ODPG, and ODPV | Review whether to add SDK/API/CLI/MCP exposure or mark as upstream-only. |
| ODPC | `odpc-v1.0/scripts/check_agent_artifacts.py` | Check ODPC schema, examples, JSONL, and llms.txt agent artifacts | Review whether to add SDK/API/CLI/MCP exposure or mark as upstream-only. |

## ODPC Capability Coverage

- Checked capabilities: 6
- Unresolved capabilities: 1

Unresolved capabilities need review before they can be treated as covered.

| Spec | Upstream source | Capability | API | CLI | MCP | Status | Notes |
|---|---|---|---|---|---|---|---|
| ODPC | `odpc-v1.0/scripts/search_objects.py` | Search ODPC catalog object guidance records | Covered | Covered | Covered | Covered |  |
| ODPC | `odpc-v1.0/scripts/validate_catalog.py` | Validate ODPC catalog documents | Covered | Covered | Covered | Covered |  |
| ODPC | `odpc-v1.0/scripts/explain_catalog.py` | Explain ODPC catalogs for humans and AI agents | Covered | Covered | Covered | Covered |  |
| ODPC | `odpc-v1.0/scripts/generate_catalog_artifacts.py` | Generate derived ODPC catalog schema artifacts | Covered | Covered | Covered | Covered | SDK can generate/check artifacts through API and CLI; MCP exposes read-only generated artifact metadata/content. |
| ODPC | `odpc-v1.0/scripts/build_catalog.py` | Build one ODPC catalog from ODPC fragments and ODPS product files | Covered | Covered | Not mapped | Partial | Catalog building writes through the CLI/API workflow; MCP does not return full generated catalog bodies. |
| **ODPC** | **`odpc-v1.0/scripts/check_agent_artifacts.py`** | **Check ODPC schema, examples, JSONL, and llms.txt agent artifacts** | **Not mapped** | **Not mapped** | **Not mapped** | **Review** | **Upstream docs consistency check; likely outside the SDK runtime surface.** |

## ODPG Capability Coverage

- Checked capabilities: 6
- Unresolved capabilities: 0

No unresolved capability drift detected.

| Spec | Upstream source | Capability | API | CLI | MCP | Status | Notes |
|---|---|---|---|---|---|---|---|
| ODPG | `odpg-v1.0/source/scripts/odpg_validate.py` | Validate ODPG graph documents | Covered | Covered | Covered | Covered |  |
| ODPG | `odpg-v1.0/source/scripts/odpg_summary.py` | Summarize ODPG graph metadata, nodes, edges, and confidence values | Covered | Covered | Covered | Covered |  |
| ODPG | `odpg-v1.0/source/scripts/odpg_traverse.py` | Traverse ODPG relationship paths from a focus node | Covered | Covered | Covered | Covered |  |
| ODPG | `odpg-v1.0/source/scripts/odpg_analyze.py` | Run ODPG strategic and governance analysis checks | Covered | Covered | Covered | Covered |  |
| ODPG | `odpg-v1.0/source/scripts/odpg_agent_context.py` | Extract trusted ODPG graph context around a focus node | Covered | Covered | Covered | Covered |  |
| ODPG | `odpg-v1.0/source/scripts/generate_graph_explorer.py` | Generate a standalone ODPG graph explorer | Covered | Covered | Not mapped | Partial | MCP remains read-only; graph explorer generation is not exposed as an MCP tool. |

## ODPV Capability Coverage

- Checked capabilities: 5
- Unresolved capabilities: 1

Unresolved capabilities need review before they can be treated as covered.

| Spec | Upstream source | Capability | API | CLI | MCP | Status | Notes |
|---|---|---|---|---|---|---|---|
| ODPV | `odpv-v1.0/scripts/search_vocab.py` | Search ODPV vocabulary terms | Covered | Covered | Covered | Covered |  |
| ODPV | `odpv-v1.0/scripts/validate_vocab.py` | Validate bundled ODPV vocabulary data | Covered | Covered | Not mapped | Partial | Useful SDK capability; not currently a dedicated MCP tool. |
| ODPV | `odpv-v1.0/scripts/generate_vocab_artifacts.py` | Generate derived ODPV vocabulary artifacts | Covered | Covered | Not mapped | Partial | Artifact generation writes files and is intentionally not exposed through the safe MCP surface. |
| ODPV | `odpv-v1.0/scripts/agent_vocab_helper.py` | Resolve, explain, and package agent-ready vocabulary term context | Covered | Covered | Covered | Covered | Ported as ODPV resolve/explain/relationship/context API, CLI, and safe MCP term-context tools. |
| **ODPV** | **`odpv-v1.0/scripts/check_cross_spec_drift.py`** | **Track terminology drift across ODPS, ODPC, ODPG, and ODPV** | **Not mapped** | **Not mapped** | **Not mapped** | **Review** | **Upstream maintenance report; review whether SDK should link to reports rather than duplicate terms drift.** |
