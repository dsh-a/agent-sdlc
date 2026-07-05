---
name: context-sources
description: The contract for Context Sources — external MCP/RAG knowledge the cycle consults at specific stages. Defines the registry schema, the stage vocabulary, the orchestrator-side retrieval + local:// inject-downward mechanism, graceful degradation, and the audit line. Loaded by the cycle orchestrator.
disable-model-invocation: true
---

# Context Sources

A **Context Source** is external knowledge the pipeline pulls in at a specific stage: a documentation MCP (e.g. `company-a-docs`), a codebase-analysis / RAG service (e.g. `codebase-rag`), an ADR store, a design-system index, etc. Sources are declared in `.claude/config.md` § Context Sources and connected as MCP servers in `.omp/mcp.json` (template `.omp/mcp.json.sample`).

This skill defines the **contract**. The orchestrator implements it; agents only consume the injected text.

---

## Why orchestrator-side retrieval

The orchestrator queries each source **once per stage** and writes the result to a `local://` file that spawned agents read on demand. This is deliberate:

- **No per-agent tool grants.** Narrow agents (`create-prd`, `generate-tasks`) have no MCP tools. Orchestrator-side retrieval means they never need them.
- **No query tax on parallel waves.** A Phase-3 wave of N implementation agents would otherwise each hammer the same source. One query, written to `local://ctx-sources.md`, read by N agents on demand, is cheaper.
- **Token economy.** Results go to `local://` files, not injected as system-prompt input tokens. Each agent reads only if its `assignment` references the file.
- **One place for degradation.** Availability handling lives in the orchestrator, not scattered across every agent.

---

## Stage vocabulary

| Stage | When | Written to | Read by |
|---|---|---|---|
| `prd` | Phase 1A, before spawning `create-prd` | `local://ctx-sources.md` | create-prd |
| `tasks` | Phase 2, before spawning `generate-tasks` | `local://ctx-sources.md` | generate-tasks |
| `predigest` | Phase 3.3 pre-digest (off by default — cost) | `local://ctx-sources.md` | pre-digest agent |
| `implement` | Phase 3.3, before each implementation agent | `local://ctx-sources.md` | implementer, test |
| `review` | Phase 4A, before spawning `review` | `local://ctx-sources.md` | review |
| `verify` | Phase 4A, before spawning `verify` | `local://ctx-sources.md` | verify |

A source is consulted at a stage iff its `consult_at` list contains that stage **and** its `enabled` is `true`.

---

## Retrieval protocol (orchestrator)

At each stage, for every enabled source whose `consult_at` includes the stage:

1. **Resolve the tool.** For `type: mcp`, the tool named in the registry is available as `mcp__<id>__<tool>` — call it directly (omp auto-discovers MCP tools from `.omp/mcp.json`). For `type: skill`, run the named skill.
2. **Build the query** from the stage's `query_hint` plus the concrete context (feature name, the task's Relevant Files, touched public symbols). Keep it scoped — these calls cost tokens and latency.
3. **Write to `local://ctx-sources.md`** (append per source). Each agent's `assignment` references this file if it needs context-source data.
4. **Require an audit line.** Instruct the spawned agent to echo, in its handoff/report, a line: `context-sources-consulted: <id>[, <id>...]` (or `none`). This makes consultation auditable via the run report.

## Graceful degradation

A source is unavailable if the MCP call errors or times out.

- **`required: optional`** → write `context-source <id>: unavailable` into the run report's context section and **proceed**. Never block.
- **`required` (true)** → in interactive mode, surface a gate to the user ("source `<id>` is required but unavailable — proceed degraded / abort?"). In autonomous mode, log `context-source <id>: DEGRADED` and proceed. **Never** mark an unreleased source `required`.
- **`enabled: false`** → skip cleanly; do not query, do not log unavailability.

---

## Adding a new source

1. Connect the MCP server in `.omp/mcp.json` (see `.omp/mcp.json.sample`).
2. Add a row to `.claude/config.md` § Context Sources (id, type, tool, `consult_at`, `required`, `enabled`, `query_hint`).
3. If the source is for data-layer schema checks, the `review` / `verify` / `test-rubric` agents already have a **context-gated data-schema check** that activates when such a source is enabled.

No agent or orchestrator code changes are needed — the registry drives everything.
