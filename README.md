# agent-sdlc

A Claude Code agent team for autonomous feature development on Flutter/Dart projects. Drop these agents and skills into your project's `.claude/` directory and get a full SDLC pipeline — from feature idea to tested, reviewed PR — driven by `/cycle`.

---

## What's included

| Type | Name | Purpose |
|---|---|---|
| Skill | `/cycle` | Main orchestrator — runs the full pipeline end-to-end |
| Skill | `/create-prd` | Write a PRD from a feature description |
| Skill | `/generate-tasks` | Decompose a PRD into an implementation task list |
| Skill | `/process-tasks` | Step through a task list manually (one sub-task at a time) |
| Skill | `/ui-story` | Build or modify a Flutter View + ViewModel |
| Skill | `/test` | Write rigorous, anti-faking tests |
| Skill | `/verify` | Audit whether tests genuinely satisfy acceptance criteria |
| Skill | `/review` | Independent code review before merging |
| Skill | `/scaffold` | Scaffold new components (entities, use cases, facades, services, VMs) |
| Skill | `/feature-idea` | Capture a feature idea and optionally hand off to `/cycle` |
| Skill | `/self-improve` | Analyze past cycle runs and tune agent/skill instructions |
| Agent | `create-prd` | Spawned by `/cycle` — writes PRDs |
| Agent | `generate-tasks` | Spawned by `/cycle` — generates task files |
| Agent | `scaffold` | Spawned by `/cycle` — scaffolds new components |
| Agent | `ui-story` | Spawned by `/cycle` — implements UI |
| Agent | `test` | Spawned by `/cycle` — writes tests |
| Agent | `verify` | Spawned after cycle — audits AC coverage |
| Agent | `review` | Spawned after cycle — reviews code quality |
| Agent | `adversarial-tester` | Spawned by `test` — finds weak assertions |
| Agent | `self-improve` | Spawned by `/self-improve` — applies pipeline improvements |
| Agent | `monitor` | Spawned by `/cycle` — maintains cycle state in the background |

---

## Setup

1. Copy the `.claude/` directory into the root of your Flutter project.
2. Ensure Claude Code is installed and you're running it from your project root.
3. The pipeline expects a few conventions in your project:
   - `agent_tasks/` — where PRDs, task files, and run reports are stored
   - `agent_states/` — ephemeral cycle state (auto-created, auto-deleted)
   - `cycle_reports/` — per-cycle summaries
   - `lib/` — Flutter source following MVVM (ChangeNotifier + Provider)
   - `test/` — mirrors the `lib/` structure
4. In `skills/test/SKILL.md`, replace `your_app` in the integration test example with your actual package name.

---

## The `/cycle` skill

`/cycle` is the main entry point. It orchestrates the full pipeline from feature description to a ready-to-merge PR.

### Basic usage

```
/cycle Add dark mode support
```

By default, `/cycle` runs in **dry-run mode** — it completes Phase 1 (PRD) and Phase 2 (tasks), then presents a plan with agent assignments and parallelism analysis before asking you to confirm. Nothing is implemented until you approve.

To execute immediately after planning:

```
/cycle --exe Add dark mode support
```

### Pipeline phases

```
Phase 1A  Create PRD          (create-prd agent, you review + approve)
Phase 1C  Gate 1              ("Proceed to tasks?")
Phase 2   Generate task list  (generate-tasks agent, you review + approve)
Phase 2B  Gate 2              ("Begin implementation?")
Phase 3   Implementation      (parallel agents in isolated worktrees)
Phase 4A  Wrap-up             (final tests, cycle report, run report)
Phase 4B  Release             (push branch, open PR)
```

You interact at gates (1C and 2B). The rest runs autonomously.

### Starting from different points

`/cycle` accepts any of these as input:

| Input | Starts at |
|---|---|
| Feature description (text) | Phase 1A — creates a new PRD |
| PRD file path | Phase 1B — reviews an existing PRD |
| Task file path | Phase 2 — reviews an existing task list |
| State file path | Resume — picks up a paused cycle |
| Empty | Checks `agent_states/` for active cycles |

### Resuming a paused cycle

If a cycle is interrupted, the monitor agent saves state to `agent_states/`. Resume with:

```
/cycle --exe agent_states/cycle-state-[feature-name].md
```

### After the cycle

Once Phase 4A completes, run these in separate conversations before merging:

```
/verify agent_tasks/prd-[feature-name].md
/review [branch-name]
```

Then return to the original conversation and approve Phase 4B to push and open the PR.

---

## Other skills

### `/process-tasks` — Manual mode

Step through a task list yourself, one sub-task at a time, with Claude assisting at each step:

```
/process-tasks agent_tasks/tasks-prd-feature-name.md
```

Claude will pause after every sub-task and wait for you to say "yes" before continuing. Useful when you want to stay close to the implementation.

### `/feature-idea` — Capture ideas

```
/feature-idea
```

Walks you through capturing a new feature idea, placing it in your features list, and optionally handing off to `/cycle`.

### `/self-improve` — Tune the pipeline

After a few cycle runs, analyze patterns and improve agent instructions:

```
/self-improve
/self-improve economy
/self-improve agent_tasks/reports/report-prd-dark-mode-2026-01-15.md
```

---

## Architecture

Each implementation agent runs in an **isolated git worktree** so parallel tasks never conflict. The orchestrator (`/cycle`) delegates all code writing to specialized agents — it only manages gates, sequencing, and state.

The `monitor` agent runs in the background throughout Phase 3+, maintaining a state snapshot that serves as the recovery point if the orchestrator is interrupted.

---

## Customizing

The agents and skills are plain Markdown files — edit them directly to match your project's conventions. Key files to personalize:

- `.claude/agents/scaffold/*.md` — patterns for your data/domain layer
- `.claude/agents/review.md` — layer boundary rules for your architecture
- `.claude/skills/cycle/SKILL.md` — model assignments, branch strategy, report format
