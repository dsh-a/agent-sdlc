---
name: context-sources
description: The contract for Context Sources — external MCP/RAG knowledge the cycle consults at specific stages. Defines the registry schema, the stage vocabulary, the orchestrator-side retrieval + inject-downward mechanism, graceful degradation, and the audit line. Loaded by the cycle orchestrator.
disable-model-invocation: true
---

# Context Sources

A **Context Source** is external knowledge the pipeline pulls in at a specific stage: a
documentation MCP (e.g. `company-a-docs`), a codebase-analysis / RAG service (e.g.
`codebase-rag`), an ADR store, a design-system index, etc. Sources are declared in
`.claude/config.md` § Context Sources and connected as MCP servers in `.claude/.mcp.json`
(template `.claude/.mcp.json.sample`).

This skill defines the **contract**. The orchestrator implements it; agents only consume the
injected text.

---

## Why orchestrator-side retrieval

The orchestrator queries each source **once per stage** and injects the returned text
*downward* into the spawned agent's prompt — the same mechanism used for known-pitfalls
(`cycle/SKILL.md` § Known pitfalls) and the pre-digest. This is deliberate:

- **No per-agent tool grants.** Narrow agents (`create-prd`, `generate-tasks`) have no MCP
  tools and no `ToolSearch` in their `tools:` frontmatter. Orchestrator-side retrieval means
  they never need them.
- **No query tax on parallel waves.** A Phase-3 wave of N implementation agents would
  otherwise each hammer the same source. One query, injected into all N prompts, is cheaper.
- **One place for degradation.** Availability handling lives in the orchestrator, not
  scattered across every agent.

The orchestrator runs in the main session and has the broad tool surface (including
`ToolSearch`) needed to load a deferred MCP tool before calling it.

---

## Stage vocabulary

| Stage | When | Injected into |
|---|---|---|
| `prd` | Phase 1A, before spawning `create-prd` | the create-prd prompt |
| `tasks` | Phase 2, before spawning `generate-tasks` | the generate-tasks prompt |
| `predigest` | Phase 3.3 pre-digest (off by default — cost) | the pre-digest prompt |
| `implement` | Phase 3.3, before each implementation agent | the implementation agent prompt |
| `review` | Phase 4A, before spawning `review` | the review prompt |
| `verify` | Phase 4A, before spawning `verify` | the verify prompt |

A source is consulted at a stage iff its `consult_at` list contains that stage **and** its
`enabled` is `true`.

---

## Retrieval protocol (orchestrator)

At each stage, for every enabled source whose `consult_at` includes the stage:

1. **Resolve the tool.** For `type: mcp`, the tool named in the registry may be deferred —
   load it via `ToolSearch` (`select:<tool>` or a keyword query) before calling. For
   `type: skill`, run the named skill.
2. **Build the query** from the stage's `query_hint` plus the concrete context (feature
   name, the task's Relevant Files, touched public symbols). Keep it scoped — these calls
   cost tokens and latency.
3. **Inject downward.** Prepend a block to the spawned agent's prompt:

   ```
   ## Context: <id>
   <retrieved text, trimmed to what's relevant>
   (source: <id> — treat as reference, verify against the actual code.)
   ```

4. **Require an audit line.** Instruct the spawned agent to echo, in its handoff/report, a
   line: `context-sources-consulted: <id>[, <id>...]` (or `none`). This makes consultation
   auditable via the `log-event.py` telemetry and the run report.

## Graceful degradation

A source is unavailable if `ToolSearch` finds no match, the call errors, or it times out.

- **`required: optional`** → write `context-source <id>: unavailable` into the run report's
  context section and **proceed**. Never block.
- **`required` (true)** → in interactive mode, surface a gate to the user ("source `<id>` is
  required but unavailable — proceed degraded / abort?"). In autonomous mode, log
  `context-source <id>: DEGRADED` and proceed. **Never** mark an unreleased source
  `required`.
- **`enabled: false`** → skip cleanly; do not query, do not log unavailability.

---

## Adding a new source

1. Connect the MCP server in `.claude/.mcp.json` (see `.mcp.json.sample`).
2. Add a row to `.claude/config.md` § Context Sources (id, type, tool, `consult_at`,
   `required`, `enabled`, `query_hint`).
3. If the source is for data-layer schema checks, the `review` / `verify` / `test-rubric`
   agents already have a **context-gated data-schema check** that activates when such a
   source is enabled.

No agent or orchestrator code changes are needed — the registry drives everything.
