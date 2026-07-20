# `.claude/skills/` — skill catalog

Skills are Markdown + YAML frontmatter. `disable-model-invocation: true` means a skill loads
only when referenced (by an agent's `skills:` frontmatter or by name) — not auto-invoked.

## Entry-point skills (user-invocable)

| Skill | Purpose |
|---|---|
| `cycle` | The pipeline orchestrator (`/cycle`) |
| `setup` | Stack-detecting configuration wizard |
| `setup-scaffold` | Discover project patterns → scaffold pattern files |
| `create-prd`, `generate-tasks`, `process-tasks` | Planning entry points |
| `scaffold`, `ui-story`, `test`, `verify`, `review` | Per-task entry points (shims over the agents) |
| `feature-idea`, `refine`, `self-improve` | Idea capture, story refinement, pipeline tuning |

## Pack-provided / active skills

These hold **stack-specific** content, populated from the active pack:

| Skill | Source |
|---|---|
| `project-conventions` | `packs/<lang>/conventions.md` — layer boundaries, naming, logging, member order |
| `ui-test-patterns` | `packs/<lang>/ui-test-patterns.md` — presentation-layer test patterns |

Switching packs repopulates these (see [`../packs/README.md`](../packs/README.md)).

## Core support skills (stack-neutral)

| Skill | Role |
|---|---|
| `context-sources` | The MCP/RAG plug-in contract — registry schema, retrieval, degradation |
| `autonomous-agent` | Shared preamble (file-I/O rules, whisper polling, deviations) |
| `ac-authoring`, `ac-audit-rubric` | AC structure + the audit rubric |
| `task-file-format` | Task-file output format + `[kind: …]` dispatch taxonomy |
| `test-rubric` | In-process test self-check (silent-skip, schema-constraint checks) |
| `pattern-divergence` | Honor a directory's dominant test pattern |
| `contradiction-exit` | Structured bail-out when inputs conflict |
| `review-report-format`, `pipeline-metrics-rubric` | Report formats for review + self-improve |
| `whispers`, `escalations` | Supervisor↔agent + supervisor↔orchestrator channels |

## Authoring notes

- Keep stack-specific content **in a pack**, not in a core skill. Core skills should read
  commands/paths from `.omp/agent-config.md` and defer conventions to `project-conventions`.
- The `flutter` pack (`../packs/flutter/`) is a complete worked example of pack content.
