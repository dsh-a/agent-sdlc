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
| └ `refine/probes.py` · `refine/story.py` | Step 3's probe enumeration and the `gh` half; `rationale.md` holds the measurements, `templates.md` the output shapes |

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
| `pr-body-format` | PR description shape written at Phase 4B step 8 |
| `sd-wire` | Wire the framework into a project: omp customDirectories, symlinked agents/packs, Claude Code skill symlinks, and what a cycle clone inherits |
| `harness-findings` | Per-cycle process-fault probes for the run report's Harness findings section |
| `evidence` | Search-method rules for a grep-running subagent, absence/citation discipline, and `evidence.py` |
| `minimalism` | The reuse-first ladder — loaded by `coding` and `generate-tasks` |
| `minimalism-review` | Applies that ladder to a finished change |
| `whispers`, `escalations` | Supervisor↔agent + supervisor↔orchestrator channels |

## Repo-maintenance skills (private-only)

Not part of the deployed pipeline — workflows for maintaining this repo. **Never port to public.**

| Skill | Role |
|---|---|
| `harness-intake` | Turn the findings already in run reports into a ranked, deduplicated issue backlog with an occurrence count |

## Authoring notes

- Keep stack-specific content **in a pack**, not in a core skill. Core skills should read
  commands/paths from `.omp/agent-config.md` and defer conventions to `project-conventions`.
- The `flutter` pack (`../packs/flutter/`) is a complete worked example of pack content.
