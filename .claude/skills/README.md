# `.claude/skills/` — skill catalog

Skills are Markdown + YAML frontmatter. Every skill carries `disable-model-invocation: true`: an
entry-point skill runs when the user types `/<name>`, and a reference skill is a file an agent
reads.

Agents read reference skills only when a project sets `agent_skills` to `true` in
`.omp/agent-config.md` § Cycle Options. It is `false` by default: agents work from their own
instructions and the project's conventions. Turning it on adds each named skill's text to that
agent's context for the whole run. The `test` agent reads `test-rubric` either way.

## Entry-point skills (user-invocable)

| Skill | Purpose |
|---|---|
| `cycle` | The pipeline orchestrator (`/cycle`) |
| └ `cycle/stack.md` · `cycle/publish-stack.sh` | A sliced story published as a PR stack: build order, slice marks, one PR per layer |
| └ `cycle/start-parallel-cycles.sh` · `cycle/reap-clones.sh` | `/cycle --parallel`: one cycle per issue in a reused pool of `parallel_slots` worktrees; `sweep` gives finished slots' disk back |
| └ `cycle/sparse-set.py` | Opt-in partial checkout for pool slots (`sparse_clones`): the set from a story's `## Slices`, and which tracked paths lie outside it |
| `setup` | Stack-detecting configuration wizard |
| `setup-scaffold` | Discover project patterns → scaffold pattern files |
| `create-prd`, `generate-tasks`, `process-tasks` | Planning entry points |
| `scaffold`, `ui-story`, `test`, `verify`, `review` | Per-task entry points (shims over the agents) |
| `feature-idea`, `refine`, `self-improve` | Idea capture, story refinement, pipeline tuning |
| └ `refine/probes.py` · `refine/story.py` | Step 3's probe enumeration and the `gh` half; `rationale.md` holds the measurements, `templates.md` the output shapes, `slicing.md` how a story is cut for a stack |

## Pack-provided / active skills

These hold **stack-specific** content, populated from the active pack:

| Skill | Source |
|---|---|

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
  commands/paths from `.omp/agent-config.md` and defer conventions to the project's instruction file.
- The `flutter` pack (`../packs/flutter/`) is a complete worked example of pack content.
