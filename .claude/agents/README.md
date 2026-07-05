# `.claude/agents/` — the agent team

Each `*.md` file is a subagent: YAML frontmatter (name, model, `tools:`, `skills:`,
`produces:`) plus a system-prompt body. The orchestrator (`/cycle`) spawns these during the
pipeline; it writes no implementation code itself.

## Catalog

| Agent | Phase | Role |
|---|---|---|
| `create-prd` | 1A | Writes the PRD from a feature description |
| `generate-tasks` | 2 | Decomposes the PRD into a tagged task list |
| `scaffold` | 3 | Creates new components from pattern shapes + pack snippets |
| `ui-story` | 3 | Implements presentation-layer features + tests |
| `test` | 3 | Writes rigorous, anti-faking tests |
| `test-preflight` | 3 | Classifies existing tests (keep / update / delete) before the test agent |
| `verify` | 4A | Independent AC-coverage audit |
| `review` | 4A | Independent code review |
| `adversarial-tester` | opt-in | Second-pass test hardening |
| `monitor` | 3–4 | Cycle-state persistence / finalize |
| `supervisor` | 3 | Observes event logs; emits whispers + escalations |
| `self-improve` | — | Applies pipeline improvements from run reports |

## How conventions reach an agent

Conventions are loaded **deterministically** via the `skills:` frontmatter — e.g. `ui-story`,
`test`, `review`, `scaffold` list `project-conventions`. That skill is the active stack's
conventions (populated from a pack). This is why there is no runtime "read a pointer, chase a
file" hop — the skill name in frontmatter resolves at spawn time.

## How external context reaches an agent

The orchestrator queries enabled **Context Sources** once per stage and **injects the result
text downward** into the spawned agent's prompt as a `## Context: <id>` block — the same
mechanism as the pre-digest and known-pitfalls. Agents do **not** call MCPs themselves (the
narrow agents have no MCP tools), and they echo `context-sources-consulted: <ids|none>` in
their handoff for auditability. See [`../skills/context-sources/SKILL.md`](../skills/context-sources/SKILL.md).

## Two per-agent things that are NOT config-driven

- **`tools:` frontmatter** — the Bash/MCP allowlist is static per agent. The default packs
  use `Bash(dotnet …)` + `mcp__ide__getDiagnostics`. Switching toolchains means editing these
  tokens across the implementation/review agents.
- **Data-layer schema checks** — `review`, `verify`, `test-rubric`, and `adversarial-tester`
  contain a **context-gated** schema-drift check that activates only when a data-schema
  Context Source is enabled. With none wired, the check is skipped and noted as not performed.

## `scaffold/` pattern shapes

`agents/scaffold/*.md` are **language-neutral** GoF/architecture shapes (interface, service,
facade, use-case, command, strategy, observer). They describe structure; the concrete idiom
comes from the active pack's `scaffold-snippets.md`. `/setup-scaffold` can add
`Type: project-specific` files that override a shape via a `Replaces:` header.
