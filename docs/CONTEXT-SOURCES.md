# Context Sources — wiring MCP / RAG knowledge into the cycle

A **Context Source** is external knowledge the pipeline pulls in at a specific stage: a
documentation MCP (`company-a-docs`), a RAG codebase-analysis service (`codebase-rag`), an
ADR store, a design-system index. This is the plug-in point that lets the team inject their
own tools at precise places in the cycle **without editing any agent or orchestrator code** —
a config row plus a connected MCP server.

The authoritative contract lives in
[`.claude/skills/context-sources/SKILL.md`](../.claude/skills/context-sources/SKILL.md);
this doc is the operator's guide.

---

## How it works (orchestrator-side retrieval → local:// files)

The orchestrator queries each enabled source **once per stage** and writes the result to
`local://ctx-sources.md`. Each spawned agent's `assignment` references this file if it needs
context-source data — the agent reads it on demand via the `read` tool. Agents never call
the MCP themselves.

Why this design:

- **Narrow agents work too.** `create-prd` and `generate-tasks` have no MCP tools; writing
  results to `local://` files means they don't need any.
- **No query tax on parallel waves.** A Phase-3 wave of N implementers shares one query, not N.
- **Token economy.** Results go to `local://` files (read on demand), not injected as
  system-prompt input tokens. Each agent reads only if its `assignment` references the file.
- **One place for failure handling** — degradation lives in the orchestrator.

Under omp, MCP tools are auto-discovered from `.omp/mcp.json` — no `ToolSearch` or deferred
loading needed. Agents echo `context-sources-consulted: <ids|none>` in their handoff so
consultation is auditable in the run report.

---

## The registry (`config.md` § Context Sources)

| Column | Meaning |
|---|---|
| `id` | Source name; matches the MCP server key in `.omp/mcp.json` |
| `type` | `mcp` (connected server) or `skill` (a local skill the orchestrator runs) |
| `tool / skill` | The MCP tool to call (e.g. `mcp__company-a-docs__search`) or skill name |
| `consult_at` | Stages: `prd`, `tasks`, `predigest`, `implement`, `review`, `verify` |
| `required` | `optional` (degrade silently) or `required` (gate on unavailability) |
| `enabled` | `false` rows are skipped cleanly |
| `query_hint` | Guidance the orchestrator uses to build the query |

### Stage vocabulary

| Stage | Consulted before | Good for |
|---|---|---|
| `prd` | the create-prd agent | domain/product docs for the feature area |
| `tasks` | the generate-tasks agent | similar prior implementations, decomposition patterns |
| `implement` | each Phase-3 implementation agent | API shapes, patterns, constraints for the touched files |
| `review` | the review agent | review checklists, architectural guidelines |
| `verify` | the verify agent | known verification gotchas, schema-of-record |
| `predigest` | the pre-digest (off by default — cost) | usually skip |

---

## The two default sources

```
| id              | type | tool                          | consult_at                     | required | enabled |
| company-a-docs | mcp  | mcp__company-a-docs__search  | prd, tasks, implement, review  | optional | true    |
| codebase-rag    | mcp  | mcp__codebase-rag__query      | tasks, implement, verify       | optional | false   |
```

- **`company-a-docs`** — the team's engineering + product documentation MCP. Enabled by
  default, optional (degrades silently if the server isn't connected).
- **`codebase-rag`** — RAG codebase-analysis context. **Not yet released** — ships
  `enabled: false`. When it lands, connect it in `.omp/mcp.json` and flip `enabled: true`.

---

## Adding a source

1. **Connect the server.** Add it to `.omp/mcp.json` (template `.omp/mcp.json.sample`).
   Gitignore `.omp/mcp.json` if it carries credentials.
2. **Register it.** Add a row to `.omp/agent-config.md` § Context Sources.
3. That's it — omp auto-discovers MCP tools; the orchestrator reads the registry; no agent
   code changes.

### Data-layer schema sources

If a source can answer "what does the live schema look like," the `review`, `verify`,
`test-rubric`, and `adversarial-tester` agents already contain a **context-gated** schema-drift
check that activates automatically when such a source is enabled (and is skipped, noted as not
performed, when none is wired).

---

## Graceful degradation

A source is "unavailable" if the MCP call errors or times out.

- **`optional`** → write `context-source <id>: unavailable` to the run report's Context
  Sources section and **proceed**. Never blocks.
- **`required`** → interactive: gate the user ("required source unavailable — proceed
  degraded / abort?"); autonomous: log `context-source <id>: DEGRADED` and proceed. **Never
  mark an unreleased source `required`.**
- **`enabled: false`** → never queried, never logged.

Every cycle's run report (`agent_tasks/reports/report-*.md`) has a **Context Sources** table
recording the outcome per (stage, source).
