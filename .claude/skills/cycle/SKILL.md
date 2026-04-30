---
disable-model-invocation: true
---

# Cycle — SDLC Feature Pipeline

You are the orchestrator. You run as **opus**. Manage gates, delegate to agents, make judgment calls. You do not write implementation code — spawn agents for that.

Feature or PRD: **$ARGUMENTS**

## Configuration

Read `.claude/config.md` at startup for model allocation, effort settings, artifact paths, optional agent settings, and cycle options. Use these values throughout — do not use hardcoded defaults when the config file exists. If no config file exists, fall back to: sonnet for implementation agents, haiku for pre-digest and monitor, opus for orchestrator.

## Live Environment (auto-injected)

Active cycle states:
!`ls agent_states/cycle-state-*.md 2>/dev/null || echo "none"`

**Janitor check**: for each state file listed above, check whether a matching cycle report already exists in `cycle_reports/` (match by feature name substring). If a match exists, the cycle completed without sending `FINALIZE` — delete the state file now and do not offer to resume it.

Recent cycle reports:
!`ls cycle_reports/*.md 2>/dev/null | tail -5 || echo "none"`

Current branch:
!`git branch --show-current`

---

## Execution mode

Dry-run by default. Completes Phases 1–2 and Phase 3 dependency analysis, then presents a plan (agent assignments, models, parallelism) without spawning implementation agents.

Pass `--exe` to execute: `/cycle --exe Add workout templates`

Also accepts PRD paths, task file paths, or state files (for resume). Resuming from a state file implies `--exe`.

Pass `--manual` to use manual mode: `/cycle --manual agent_tasks/tasks-prd-feature.md`

`--manual` delegates to `/process-tasks` logic — one sub-task at a time with user approval gates after each. No parallel agents, no worktrees. Still creates a state file for resume capability. Requires a task file path (or will prompt for one).

Dry-run ends with: **"Ready to execute? `/cycle --exe` to begin, or adjust first."**

---

## Agent spawn rules

### MANDATORY spawn parameters

Every `Agent` tool call for implementation MUST include `isolation: "worktree"`. Without this, parallel agents share the working directory and corrupt each other's changes.

```
Agent(subagent_type: "scaffold", model: "sonnet", isolation: "worktree", prompt: "...")
```

Named agents (`scaffold`, `ui-story`, `test`, etc.) have their model set in their definition. Pass `model:` only to override or for generic haiku agents (monitor, pre-digest).

### Agent labels

Each agent definition includes a `label` field in its frontmatter (e.g., `[SCAFFOLD]`, `[TEST]`). When reporting status to the user or sending updates to the monitor, prefix messages with the agent's label for identification. Example: `[SCAFFOLD] Task 1.2 complete` or `[TEST] 3 tests added for LoginService`.

### Pre-digestion

Before spawning a named implementation agent, optionally spawn a **haiku** agent (background) to read relevant source files and return a ~200-line context digest. Pass the digest in the implementation agent's prompt to reduce redundant file reads.

**Prompt budget**: haiku prompts <200 words (single task, no background). Implementation agent prompts: task context + digest only — no instructions, those live in the agent definition.

---

## Branch strategy

All work on feature branches, never directly on the base branch.

- **Naming**: read `feature_branch_pattern` from the **Branch Configuration** table in `.claude/config.md`. Default: `feature/[short-description]`, `fix/...`, or `refactor/...`
- **Create at Phase 2B**: `git checkout -b feature/[name] [base_branch]` — where `[base_branch]` is the `base_branch` value from `.claude/config.md`
- **Parallel tasks**: worktrees branched from feature branch — `feature/[name]/task-[N.0]`
- **Merge order**: dependency order. Run the test and typecheck/lint commands (from **Project Commands** in `.claude/config.md`) after each merge.
- **Conflicts**: sonnet agent resolves. Ambiguous conflicts → escalate to user.
- **After Phase 4**: do NOT merge into the base branch. User decides after `/verify` + `/review`.

---

## State persistence

State directory: `agent_states/` (ephemeral — deleted on completion).

### Monitor agent

At Phase 3 start, spawn the monitor agent with the feature name and state file path:

```
Agent(subagent_type: "monitor", run_in_background: true,
      prompt: "Feature: [name]. State file: agent_states/cycle-state-[name].md")
```

The orchestrator sends 1–2 sentence updates to the monitor using the message types defined in `.claude/agents/monitor.md` (GATE, SPAWNED, PARENT, ESCALATION, etc.). The monitor writes state. The orchestrator does NOT write state files directly.

**Save-before-spawn**: before spawning any sonnet/opus agent, update the monitor first.

---

## Entry point

Inspect $ARGUMENTS:

| Input | Start at |
|---|---|
| State file (`agent_states/cycle-state-*.md`) | Resume: read state + digests, verify codebase, spawn monitor, skip completed phases |
| PRD file (`agent_tasks/prd-*.md`) | Phase 1B |
| Task file (`agent_tasks/tasks-*.md`) | Phase 2 review |
| Story number (e.g., `1.6`) | Phase 1A (pre-populate from `documentation/ROADMAP.md`) |
| Feature description (text) | Phase 1A (check ROADMAP.md for match first) |
| Empty | Check `agent_states/` for active/paused cycles. If none: read `feature_idea_on_empty` from `.claude/config.md` Cycle Options. If true, read the Feature Ideas path from config (default `documentation/FEATURES.md`) and present any unstarted items — offer to start a cycle for one, or run `/feature-idea` to capture a new idea. If FEATURES.md doesn't exist, has no unstarted items, or `feature_idea_on_empty` is false, ask for a feature description. |

Create/update state file immediately after determining entry point.

On resume: cancel any scheduled cron (`CronDelete`), re-check blockers with user, reuse saved digests.

---

## Phase 1A — Create PRD

Spawn the `create-prd` agent (model: sonnet) with the feature description. The agent explores the codebase, checks the roadmap, scans existing PRDs, and returns a complete PRD draft and file path.

```
Agent(subagent_type: "create-prd", model: "sonnet",
      prompt: "Feature: [description]. [Any roadmap story number or context].")
```

Review the returned PRD for completeness, then proceed to Phase 1C.

Update state → Phase 1C.

## Phase 1B — Review existing PRD

Present sections one at a time for confirmation:
1. User Stories → confirm → apply changes
2. Functional Requirements → confirm → apply changes
3. Acceptance Criteria → confirm → apply changes

Update state → Phase 1C.

## Phase 1C — Gate 1

Summarize PRD (3–5 bullets: problem, stories, scope). Ask: **"Proceed to tasks?"**

Approved → Phase 2. Changes → apply, re-ask.

## Phase 2 — Task generation

Spawn the `generate-tasks` agent (model: sonnet) with the PRD file path. The agent assesses the codebase, decomposes the PRD, and returns a complete task file and path.

```
Agent(subagent_type: "generate-tasks", model: "sonnet",
      prompt: "PRD: [prd-file-path]")
```

Existing task file → present for review instead of re-generating.

## Phase 2B — Gate 2

Present task list. Ask: **"Begin implementation?"**

Approved → create feature branch, update state, Phase 3. Changes → apply, re-ask.

---

## Phase 3 — Implementation

You delegate and track. You do not write code.

### 3.1 — Pre-flight

Check `.claude/agents/scaffold/` for project-specific pattern files (files with `Type: project-specific`). If none exist and the task list includes scaffold-type work, autonomously spawn a setup-scaffold agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet", run_in_background: true,
      prompt: "Run the /setup-scaffold skill in scan mode. Read .claude/skills/setup-scaffold/SKILL.md and follow its steps. Do not ask the user questions — use your best judgment for pattern discovery and create all pattern files you find. Report what was created.")
```

Run this in the background — it does not block Phase 3 from continuing. Scaffold agents spawned later will pick up the pattern files once they exist.

Spawn monitor agent (model: monitor row from **Model Allocation** table in `.claude/config.md`, background) with feature name and state file path.

### 3.2 — Dependency analysis

Classify parent tasks: **independent** (start now) or **dependent** (wait for prerequisite).
Classify sub-tasks by type → assign agent per the delegation table in 3.3.

Present analysis in dry-run mode. In `--exe` mode, proceed.

### 3.3 — Spawn agents

Before spawning any implementation agent:

1. **Extract file paths** from the task file's "Relevant Files" section — pass these explicitly in every agent prompt. This eliminates discovery round-trips.
2. **Extract AC** from the PRD's Acceptance Criteria section — pass directly to test and verify agents so they skip PRD search.

For each parent task (independent in parallel, dependent when ready):

1. **Pre-digest** (haiku, background) — **default for any task touching ≥ 2 existing files**. Reads relevant source files and returns a ~150-line structured summary (public API, constructor deps, key patterns). Skip only if the task creates all-new files or a digest was already saved.

   ```
   Agent(model: "[pre-digest model from Model Allocation table in .claude/config.md]", run_in_background: true,
         prompt: "Read these files and return a ~150-line structured summary
                  covering: public API (class names, method signatures, constructor
                  deps), key patterns, and anything an implementer needs to know.
                  Files: [file paths from Relevant Files section].
                  Be dense — no prose explanations, just facts.")
   ```

   Wait for the digest before spawning the implementation agent. Pass digest content in the implementation agent's prompt.

2. **Implement** (`isolation: "worktree"`) — use the agent matching the task type:

   | Sub-task type | subagent_type | Model |
   |---|---|---|
   | New entity/model end-to-end | `scaffold` | per config |
   | UI screen or component | `ui-story` | per config |
   | DI wiring or use case | `scaffold` | per config |
   | Multi-file implementation (3+ files) | general-purpose | per config |

   Read the **Model Allocation** table in `.claude/config.md` for each agent's assigned model under the active preset. If no config file exists, default to sonnet for all implementation agents.

   ```
   Agent(subagent_type: "scaffold", model: "[per config]", isolation: "worktree",
         prompt: "PRD: [prd-path]
                  Source files: [paths from Relevant Files]
                  AC (pre-extracted): [AC items from PRD]
                  Task: [sub-task list]
                  Digest: [digest content if available]")
   ```

   - Agent marks sub-tasks `[x]` as it completes them
   - On failure/ambiguity: report to orchestrator, continue independent sub-tasks

3. **Test** (separate agent from implementer):
   - **Write** (sonnet): `Agent(subagent_type: "test", model: "sonnet", isolation: "worktree", prompt: "PRD: [prd-path]\nSource files: [paths]\nTest files: [paths]\nAC (pre-extracted): [AC items]\nTask: [task description]")`
   - **Fix** (sonnet): re-spawn `test` agent with failure output and source paths

### 3.4 — Handle results

- **Success**: merge worktree → feature branch, run test + typecheck/lint commands (from **Project Commands** in `.claude/config.md`), send status to monitor
- **Failure**: escalation ladder (below)
- **Blocked**: notify user, continue independent tasks

### Escalation ladder

Max 3 attempts per sub-task, 5 total per parent task.

| Level | Trigger | Action |
|---|---|---|
| L1 | Compile/analysis/simple test error | **Haiku** fix agent, 1 attempt |
| L2 | L1 failed or non-trivial error | Next model up with error + context |
| L3 | L2 failed | Revert changes, **opus** fresh attempt (anti-pattern: what failed) |
| L4 | All auto-recovery failed | Block, report to user, continue independent tasks |

Send every escalation to monitor: `ESCALATION [task-id] L[1-4]: [model] [reason]`

### Bug tracking

Existing-code bugs (not agent-written code):
1. Log in `documentation/bugs.md` (next BUG-NNN ID)
2. Note in cycle state
3. Don't fix unless blocking. If blocking: fix, move to `bugs_resolved.md`.

### Commit protocol

Per parent task, when all sub-tasks pass:
1. Run test + typecheck/lint commands (from **Project Commands** in `.claude/config.md`)
2. Green → merge worktree, stage specific files, commit (conventional format), mark parent `[x]`, update monitor, delete worktree branch
3. Red → escalation ladder from L1

Never auto-revert commits. Report to user with options.

### Dependencies

Agents do NOT add packages. On need:
1. Agent pauses, reports to orchestrator (what, why, alternatives)
2. Orchestrator evaluates
3. If justified → present to user for approval
4. Approved → install the package using the project's package manager

### Usage limits

Signals: explicit warnings, tool failures, truncation, very long session.

1. Finish current in-flight agent only
2. Pause signal to monitor (include worktree paths, current task)
3. Schedule auto-resume: `CronCreate` (durable, one-shot, offset from round marks) with `/cycle --exe agent_states/cycle-state-[name].md`
4. Report to user: what's done, resume point, manual fallback command

---

## Phase 4 — Completion

Two parts: **4A** runs immediately with no user interaction. **4B** runs when the user returns after verify/review (or says to proceed now).

### 4A — Wrap-up (MANDATORY — execute immediately, do not stop or ask; step 7 MUST execute even if the user skips 4B)

1. Run test + typecheck/lint commands from **Project Commands** in `.claude/config.md` (final full suite)
2. Mark ALL tasks and sub-tasks `[x]` in the task file (final sweep)
3. Generate cycle report → `cycle_reports/[feature-name]-[YYYY-MM-DD].md`:
   - Summary (what was implemented, per parent task)
   - Branch name, commits (hash + message), database/schema changes (or "none")
   - Bugs discovered, known limitations, blocked tasks, follow-up items
4. Present cycle report to user inline
5. Generate run report → `agent_tasks/reports/report-prd-[feature-name]-[YYYY-MM-DD].md` using template `.claude/skills/cycle/report-template.md`. **Agent Audit** section is required. If >10 reports exist, summarize oldest into `agent_tasks/agent_metrics.md`.
6. **Autonomous verify & review** — read `.claude/config.md` Optional Agents section.

   If `verify` is **enabled**: spawn the `verify` agent with the PRD path, source file paths, test file paths, and pre-extracted AC:
   ```
   Agent(subagent_type: "verify", model: [per config Model Allocation],
         prompt: "PRD: [prd-path]. Source files: [paths]. Test files: [paths].
                  AC: [pre-extracted]. Branch: [branch-name].
                  Work autonomously — no user interaction.")
   ```

   If `review` is **enabled**: spawn the `review` agent with the branch name:
   ```
   Agent(subagent_type: "review", model: [per config Model Allocation],
         prompt: "Branch: [branch-name]. PRD: [prd-path].
                  Work autonomously — no user interaction.")
   ```

   Spawn both in parallel if both are enabled. Wait for completion and collect their reports.

   Include verify and review summaries in the cycle report (step 3). Then apply this gate before allowing 4B:

   | Verify verdict | NO IMPL count | 4B gate |
   |---|---|---|
   | PASS | 0 | Proceed to 4B automatically |
   | PARTIAL | 0 | Proceed — but present gaps and ask user to confirm before 4B |
   | PARTIAL | > 0 | Block 4B — present unimplemented criteria, require user to fix or explicitly accept the gaps |
   | FAIL | any | Block 4B — present failures, require fixes before release |

   If `verify` was skipped, the gate does not apply — proceed to 4B but note: **"Verify was skipped — run `/verify` before merging."**

   If either agent is set to `skip` in config, do not spawn it. Instead recommend: **"Run `/verify` and/or `/review` in separate conversations, then return here for release."**

7. Tell monitor: `FINALIZE report:[path]` — this deletes the state file. **Do not skip.** The cycle may end here if the user handles the PR manually.

**4A is not complete until steps 1–7 are done. Do not skip any step.**

### 4B — Release (after gate passes; user confirmation required for PARTIAL)

8. Push branch, `gh pr create` targeting the `pr_target` from `.claude/config.md`
9. Update roadmap (skip if cycle didn't originate from a roadmap story):
   - `documentation/ROADMAP.md`: set story Status to `DONE` in Story Index
   - Move story's full section to `documentation/roadmap_completed.md` under the appropriate Phase heading. Mark all AC `[x]`.
10. Append changelog entry to `documentation/CHANGELOG.md`

