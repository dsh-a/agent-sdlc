---
disable-model-invocation: true
---

# Cycle — SDLC Feature Pipeline

You are the orchestrator. You run as **opus**. Manage gates, delegate to agents, make judgment calls. You do not write implementation code — spawn agents for that.

Feature or PRD: **$ARGUMENTS**

## Configuration

Read `.claude/config.md` at startup for model allocation, effort settings, artifact paths, optional agent settings, and cycle options. Use these values throughout — do not use hardcoded defaults when the config file exists. If no config file exists, fall back to: sonnet for implementation agents, haiku for pre-digest and monitor, opus for orchestrator.

When passing `model:` to Agent calls, resolve the label (opus/sonnet/haiku) through the **Model Versions** table in config.md. Pass the specific model ID (e.g. `claude-opus-4-6`) rather than the alias label. If no Model Versions table exists, pass the alias label as-is.

## Live Environment (auto-injected)

Active cycle states:
!`ls agent_states/cycle-state-*.md 2>/dev/null || echo "none"`

**Janitor check**: for each state file listed above, check whether a matching cycle report already exists in `cycle_reports/` (match by feature name substring). If a match exists, the cycle completed without sending `FINALIZE` — delete the state file now and do not offer to resume it.

**Worktree janitor**: run `git worktree list`. For any worktree under `.claude/worktrees/` on a `cycle/*` branch whose cycle is not among the active state files above, prune it — `git worktree remove --force <path>` then `git branch -D <branch>`. Orphaned Phase-3 worktrees otherwise accumulate indefinitely.

**Gitignore guard** — ensure runtime artifacts (cycle state, telemetry event logs, Phase-3 worktrees) are never committed to the project repo. Idempotent; appends a marked block once:
!`grep -q 'agent-sdlc (managed)' .gitignore 2>/dev/null || printf '\n# >>> agent-sdlc (managed — do not edit) >>>\nagent_states/\n.claude/worktrees/\n# <<< agent-sdlc <<<\n' >> .gitignore`

Only runtime artifacts are ignored. `agent_tasks/` (live PRD + task files) and `documentation/` are **durable** — they travel with the feature branch and must stay committed. Cycle reports and run reports are written to the external docs vault (see config **Artifact Paths**) and never land in the project repo at all.

**Vault link guard** — read the **Docs Vault** section of `.claude/config.md`. If `vault_root` is non-empty, wire the vault before any report is written this cycle:
1. Resolve `app_slug` (config value, else the basename of the repo root).
2. Ensure the vault targets exist: `mkdir -p "{vault_root}/cycle_reports/{app_slug}" "{vault_root}/reports/{app_slug}"`.
3. For each pair `cycle_reports → {vault_root}/cycle_reports/{app_slug}` and `agent_tasks/reports → {vault_root}/reports/{app_slug}`: if the repo path is already the correct symlink, skip; if it is a real directory, move its contents into the vault target then `rm -rf` it; finally `ln -s` the vault target to the repo path.
4. Ensure the managed `.gitignore` block also lists `cycle_reports` and `agent_tasks/reports` (no trailing slash — git treats a symlink as a file, so `dir/` would not match).

If `vault_root` is empty, skip entirely — reports stay local and committed (backward-compatible default).

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

### Cycle modes (5.6.1, 5.6.3)

`/cycle --mode full|lean|hotfix` selects the depth of the pipeline. Default is `full`. Modes are **user-declared** — the orchestrator may *suggest* a mode at dry-run (5.6.4) but never picks silently.

**Behavior matrix:**

| Phase | `full` | `lean` | `hotfix` |
|---|---|---|---|
| 1A PRD | yes | inline — derive AC from the feature description; skip `create-prd` spawn | skip |
| 1C gate | yes | **merged with 2B** (one combined approval) | skip |
| 2 task gen | yes | yes | skip (single implicit task) |
| 2B gate | yes | **merged with 1C** | skip |
| 3 implementation | parallel agents in worktrees | parallel agents in worktrees | single agent, **no worktree** (main checkout) |
| 4A wrap-up | verify + review concurrently | verify + review concurrently | lite verify only; no review |
| 4B release | yes | yes | yes |

**Gate consolidation in lean.** When `--mode lean`, Phases 1C and 2B fuse into one approval point at the end of Phase 2: the user reviews the inline-derived AC summary *and* the generated task list together, then approves once. PRD is not written to a file; the AC summary lives inside the cycle state's `## References` section.

**Hotfix posture.** `--mode hotfix` is for "fix one thing, fast." Single implicit task derived from the feature description (no `generate-tasks` spawn). Implementation runs on the feature branch directly — no worktree, no parallel agents, no pre-digest. Verify runs at **lite** depth (see 5.6.6). Review is skipped. The feature branch and PR open as normal in 4B.

**Mode is recorded** in cycle state's `## References` section as `Mode: full|lean|hotfix` for the run report and `self-improve` aggregation.

### Mode auto-suggestion at dry-run (5.6.4)

If the user did **not** pass `--mode`, apply these heuristics on the feature description and surface a suggestion at dry-run. **Never pick silently** — the user always confirms or overrides.

**Suggest `hotfix`** when ALL of:
- Description contains any of: `fix`, `bug`, `hotfix`, `patch`, `regression`, or matches `^fix:` style.
- Description is ≤ 20 words.
- Description contains NONE of: `migration`, `schema`, `refactor`, `redesign`, `new feature`, `epic`.

**Suggest `lean`** when ALL of (and hotfix-eligibility is false):
- Description is ≤ 40 words.
- Description contains NONE of: `migration`, `schema`, `multi-screen`, `epic`, `refactor`.

**Else suggest `full`.**

At dry-run, print exactly:
```
Suggested mode: <suggestion>. Reason: <short trace of the heuristic that fired>.
Override with --mode full|lean|hotfix.
```

If the user passed `--mode` explicitly, **suppress the suggestion entirely** — their declaration wins. Record the suggestion-vs-actual outcome in cycle state's `## References` as `Mode suggestion: <suggested> | accepted: true|false` so `self-improve` can later calibrate the heuristics from observed acceptance rates.

Dry-run ends with: **"Ready to execute? `/cycle --exe` to begin, or adjust first."**

---

## Agent spawn rules

### Phase-3 worktree protocol (MANDATORY)

The orchestrator creates and owns every Phase-3 worktree. Implementation agents do **not** use `isolation: "worktree"` — worktrees created by that harness flag branch from a stale base instead of the feature branch HEAD. The orchestrator avoids the bug by creating worktrees itself.

**Mode override:** in `--mode hotfix`, worktrees are skipped entirely. A single implementation agent runs in the main checkout on the feature branch. No agent_id-based events, no parallel agents, no worktree-startup preamble. The rest of this section applies only when mode is `full` or `lean`.

**One worktree per parent task** — the implementer and the test agent for that task share it.

For each parent task, before spawning its agents:

1. **Create the worktree** from the current feature-branch HEAD: `git worktree add -b cycle/[story]/task-[N.0] .claude/worktrees/[story]-task-[N.0] feature/[name]`. The base is `feature/[name]` HEAD *at creation time* — create it immediately before spawning, so a dependent task forks from the post-merge HEAD that already contains its prerequisite.
2. **Spawn the agent non-isolated** — no `isolation:` parameter — with the worktree-startup preamble (below) prepended to its prompt.
3. The agent works entirely inside its worktree; the orchestrator merges and tears it down (see **Commit protocol**).

Separate worktree directories already give full isolation — each has its own working tree, index, and build artifacts; the shared git object store is concurrency-safe. The `isolation:` flag is unnecessary once the orchestrator owns worktree creation.

**Worktree-startup preamble** — prepend to EVERY Phase-3 implementation agent prompt, with `[path]` and `[branch]` filled in:

> Before any other action: run `cd [path]`, then verify `git rev-parse --show-toplevel` equals `[path]` AND `git branch --show-current` equals `[branch]`. If either check fails, do NOT proceed — stop immediately and report `WORKTREE MISMATCH`. Every file path in this prompt is absolute and inside your worktree; never Read, Edit, or Write a path outside `[path]`.

The orchestrator rewrites the task's "Relevant Files" paths to the worktree root before injecting them, so the agent is never handed a main-checkout path.

**On `WORKTREE MISMATCH`** — if an agent aborts with this signal, the orchestrator sends `RESCUE worktree-mismatch [agent-id]: [short description] | resolution: [retry|escalate] | artifact: none` to monitor before proceeding via the escalation ladder.

**Handoff format** — every Phase-3 implementation agent's final response must include a `## Deviations` section. Each item: `task: [task-id] | ac: [AC ref] | implemented: [what] | reason: [why]`. Write `None` if the implementation matches PRD AC literally. The orchestrator forwards each deviation to monitor via a `DEVIATIONS` message (see §3.4 Success).

Named agents (`scaffold`, `ui-story`, `test`, etc.) have their model set in their definition. Pass `model:` only to override or for generic haiku agents (monitor, pre-digest).

### Agent labels

Each agent definition includes a `label` field in its frontmatter (e.g., `[SCAFFOLD]`, `[TEST]`). When reporting status to the user or sending updates to the monitor, prefix messages with the agent's label for identification. Example: `[SCAFFOLD] Task 1.2 complete` or `[TEST] 3 tests added for LoginService`.

### Pre-digestion

Before spawning a named implementation agent, optionally spawn a **haiku** agent (background) to read relevant source files and return a ~200-line context digest. Pass the digest in the implementation agent's prompt to reduce redundant file reads.

**Prompt budget**: haiku prompts <200 words (single task, no background). Implementation agent prompts: task context + digest only — no instructions, those live in the agent definition.

### Context Sources retrieval

A reusable step invoked at five stages (`prd`, `tasks`, `implement`, `review`, `verify`). The full contract is in the `context-sources` skill; the mechanics:

1. Read `.claude/config.md` § Context Sources. Select rows where `enabled` is `true` **and** `consult_at` contains the current stage. If none, skip silently.
2. For each selected `mcp` source: load its tool via `ToolSearch` if deferred, then query it once with the row's `query_hint` plus concrete context (feature name, the task's Relevant Files, touched symbols). For `skill` sources, run the named skill.
3. Prepend the trimmed result to the agent's spawn prompt as a `## Context: <id>` block, and instruct the agent to echo `context-sources-consulted: <ids|none>` in its handoff.
4. **Degrade gracefully.** Unavailable (no tool match / error / timeout): `optional` → write `context-source <id>: unavailable` to the run report and proceed; `required` → gate the user (interactive) or log `context-source <id>: DEGRADED` and proceed (autonomous). Never block on an `optional` source. `enabled: false` rows are never queried.

This is the same inject-downward pattern as Pre-digestion and Known pitfalls. `predigest` is intentionally **not** a consult stage by default (the pre-digest is a cheap summarizer).

### Handoff validation

At every agent handoff, the orchestrator confirms the agent's frontmatter `produces:` file exists at the expected path. Missing = agent failure: re-spawn (Phase 1A / 2), escalate (Phase 3), or run **Stall salvage** (Phase 4A — already wired).

---

## Branch strategy

All work on feature branches, never directly on the base branch.

- **Naming**: read `feature_branch_pattern` from the **Branch Configuration** table in `.claude/config.md`. Default: `feature/[short-description]`, `fix/...`, or `refactor/...`
- **Create at Phase 2B**: `git checkout -b feature/[name] [base_branch]` — where `[base_branch]` is the `base_branch` value from `.claude/config.md`
- **Parallel tasks**: the orchestrator creates one git worktree per parent task, branched from `feature/[name]` HEAD — branch `cycle/[story]/task-[N.0]`, path `.claude/worktrees/[story]-task-[N.0]`. See **Phase-3 worktree protocol**. (`feature/[name]/task-N` cannot be used as a branch name — it collides with the `feature/[name]` ref.)
- **Merge order**: dependency order. Run the test and typecheck/lint commands (from **Project Commands** in `.claude/config.md`) after each merge.
- **Conflicts**: sonnet agent resolves. Ambiguous conflicts → escalate to user.
- **After Phase 4**: do NOT merge into the base branch. User decides after `/verify` + `/review`.

---

## State persistence

State directory: `agent_states/` (ephemeral — deleted on completion).

### State persistence

The orchestrator keeps `agent_states/cycle-state-<feature>.md` current throughout the cycle, using the template and verb list in `.claude/agents/monitor.md`. **Two modes**, selected by `agent_messaging` in `.claude/config.md` § Cycle Options (default `false`):

- **`agent_messaging: false` (default) — inline.** *You*, the orchestrator, write the state file directly. The monitor's verb list (`GATE`, `SPAWNED`, `PARENT`, `RESCUE`, `DEVIATIONS`, `SCOPE_CHANGE`, `SUPERVISOR_HEALTH`, …) is your **checklist of what to record when**. This is the normal path and is **not** a degradation — never log it as a rescue. No background monitor is spawned. Inline is also the only mode that works without SendMessage / agent-teams.
- **`agent_messaging: true` — delegated.** Spawn the background monitor once at Phase 3 start and *send* it each verb via SendMessage; it writes the state file so your context stays lean:
  ```
  Agent(subagent_type: "monitor", run_in_background: true,
        prompt: "Feature: [name]. State file: agent_states/cycle-state-[name].md")
  ```

**Reading convention for the rest of this skill:** wherever a step says "emit / send / forward / update `<VERB>` to monitor," it means *record that verb in cycle state* — write it inline (default) or SendMessage it to the monitor (when `agent_messaging: true`). Verb formats are defined in `monitor.md`.

**Save-before-spawn:** before spawning any sonnet/opus agent, bring the state file current first (inline) or send the pending verbs to the monitor — so a crash mid-spawn leaves an accurate recovery point.

**Finalize is always a one-shot spawn.** Regardless of mode, cleanup runs as a single short-lived monitor spawn — it holds the `rm agent_states/*` permission the orchestrator does not:
```
Agent(subagent_type: "monitor",
      prompt: "FINALIZE report:[run-report-path]. Archive per monitor.md, delete all agent_states/ files for this cycle, then exit.")
```

---

## Entry point

Inspect $ARGUMENTS:

| Input | Start at |
|---|---|
| State file (`agent_states/cycle-state-*.md`) | Resume: read state + digests, verify codebase, resume state persistence (§ State persistence), skip completed phases |
| PRD file (`agent_tasks/prd-*.md`) | Phase 1B |
| Task file (`agent_tasks/tasks-*.md`) | Phase 2 review |
| Story number (e.g., `1.6`) | Phase 1A (pre-populate from `documentation/ROADMAP.md`) |
| Feature description (text) | Phase 1A (check ROADMAP.md for match first) |
| Empty | Check `agent_states/` for active/paused cycles. If none: read `feature_idea_on_empty` from `.claude/config.md` Cycle Options. If true, read the Feature Ideas path from config (default `documentation/FEATURES.md`) and present any unstarted items — offer to start a cycle for one, or run `/feature-idea` to capture a new idea. If FEATURES.md doesn't exist, has no unstarted items, or `feature_idea_on_empty` is false, ask for a feature description. |

Create/update state file immediately after determining entry point.

On resume: cancel any scheduled cron (`CronDelete`), re-check blockers with user, reuse saved digests.

---

## Mode-conditional phase routing (5.6.1)

Before entering Phase 1A, route per the active `--mode`:
- **`full`** — all phases run as written below.
- **`lean`** — skip `create-prd` spawn in Phase 1A; derive AC inline from the feature description and store under cycle state `## References` → `AC summary:`. Skip Phase 1C (folded into Phase 2B). Phase 2 still spawns `generate-tasks` (with the inline AC summary as input). Phase 2B presents AC + tasks together for one combined approval.
- **`hotfix`** — skip Phases 1A, 1C, 2, 2B entirely. Treat the feature description as a single implicit task. Go directly to Phase 3 with one agent, no worktree (main checkout), no pre-digest. Phase 4A runs verify (lite depth) only.

## Phase 1A — Create PRD

Spawn the `create-prd` agent (model: sonnet) with the feature description. The agent explores the codebase, checks the roadmap, scans existing PRDs, and returns a complete PRD draft and file path.

Run **Context Sources retrieval** for stage `prd` (see § Context Sources retrieval) and prepend any `## Context: <id>` blocks to the prompt below.

```
Agent(subagent_type: "create-prd", model: "sonnet",
      prompt: "[Context blocks if any]
               Feature: [description]. [Any roadmap story number or context].")
```

Confirm the PRD file exists at the agent's `produces:` path. Missing = re-spawn or escalate.

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

Run **Context Sources retrieval** for stage `tasks` and prepend any `## Context: <id>` blocks to the prompt below.

```
Agent(subagent_type: "generate-tasks", model: "sonnet",
      prompt: "[Context blocks if any]
               PRD: [prd-file-path]")
```

Confirm the task file exists at the agent's `produces:` path. Missing = re-spawn or escalate.

Existing task file → present for review instead of re-generating.

## Phase 2B — Gate 2

Present task list. Ask: **"Begin implementation?"**

In `--mode lean`, **also present the inline AC summary above the task list** — this is the consolidated 1C+2B gate. One combined approval covers both AC and tasks.

Approved → create feature branch, update state, Phase 3. Changes → apply, re-ask.

---

## Phase 3 — Implementation

You delegate and track. You do not write code. If you ever complete work that should have gone through an agent (e.g., applying a trivial fix to the feature branch yourself), emit `RESCUE manual-completion [task-id]: [what you did] | resolution: [why] | artifact: [commit hash or path]` to monitor — silent substitutions destroy the audit trail.

**Mid-cycle scope changes.** If after Gate 2 you add, remove, or modify an acceptance criterion (e.g., the PRD missed a case discovered during implementation), emit `SCOPE_CHANGE [added|removed|modified] AC [ac-id]: [text] | reason: [why]` to monitor. `verify` reads this list and audits against the current truth, not the frozen PRD.

### Analyzer baseline (5.8.1)

If `analyzer_baseline` in `.claude/config.md` § Hygiene flags is `soft_warn` or `hard_fail_if_exceeded`, capture the baseline at Phase 3 start by running the **Analyze / lint** command from `.claude/config.md` § Project Commands and redirecting its output:

```
<analyze-lint command> > cycle_reports/<feature>/analyzer-baseline.txt 2>&1 || true
```

Phase 4A re-runs the same command and diffs. New warnings in the diff:
- `soft_warn` → flagged in the run report under a new "Analyzer drift" section; cycle proceeds.
- `hard_fail_if_exceeded` → review verdict flips to REQUEST CHANGES regardless of other findings; the diff is included in the review report.

### Known pitfalls (5.8.3)

If `known_pitfalls_path` in `.claude/config.md` § Hygiene flags points at an existing file, read it once at Phase 3.3 (before spawning implementation agents). File format:

```markdown
## <Short title>
Globs: src/**/Infrastructure/**, tests/**/Data*
Severity: warn | hard
Body:
[One paragraph describing the pitfall and how to avoid it. Cite a real incident if available.]
```

For each parent task, match the task's "Relevant Files" paths against each entry's `Globs:` line. For every match, append the entry's `Body:` to the agent's spawn prompt under a `## Known pitfalls for files you'll touch` section. Severity `hard` entries get a "Read this carefully — the same bug has happened before:" preface. The framework provides the matching mechanism; the project owns the file content.

### Compact at phase boundaries (5.8.2)

If `auto_compact_at_boundaries` in `.claude/config.md` § Hygiene flags is `on`, invoke `/compact` at:
- **Phase 2→3 transition** — after Gate 2 is approved, before any Phase 3 spawn.
- **Phase 3→4A transition** — after the last parent task merges, before the Phase 4A wrap-up runs.

Compaction reclaims context but can cost orchestrator decision-continuity; keep `off` until telemetry shows the trade-off is favorable for your cycles.

### 3.1 — Pre-flight

Check `.claude/agents/scaffold/` for project-specific pattern files (files with `Type: project-specific`). If none exist and the task list includes scaffold-type work, autonomously spawn a setup-scaffold agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet", run_in_background: true,
      prompt: "Run the /setup-scaffold skill in scan mode. Read .claude/skills/setup-scaffold/SKILL.md and follow its steps. Do not ask the user questions — use your best judgment for pattern discovery and create all pattern files you find. Report what was created.")
```

Run this in the background — it does not block Phase 3 from continuing. Scaffold agents spawned later will pick up the pattern files once they exist.

Initialize state persistence per **§ State persistence**: by default (`agent_messaging: false`) write the state file inline — no agent spawned. Only when `agent_messaging: true`, spawn the background monitor here (model: monitor row from **Model Allocation** table in `.claude/config.md`).

**The supervisor (item 5.5.1)** runs distinct from monitor (monitor: deterministic state archival; supervisor: heuristic observation). OQ-9 (consolidation) is deferred pending real telemetry.

The supervisor is **not** a long-lived daemon and needs **no** agent-messaging. The orchestrator drives it by spawning a fresh, short-lived check per cadence tick (below); each spawn does exactly one check for one agent and exits, with continuity persisted on disk in `agent_states/supervisor/state.md`. This is what makes supervision work in environments without SendMessage/agent-teams.

**Skip the supervisor entirely** when the task file has fewer than `skip_supervisor_if_total_subtasks_lt` sub-tasks (Per-phase skip flags in `.claude/config.md`, default 3) — observation overhead exceeds value on small task lists. Log the skip as `SUPERVISOR_HEALTH status:disabled spawns:0 stalls:0 heartbeat:none disabled_at:[ts] reason:skip-flag` so the run report reflects it.

**Cadence — when to spawn a check.** No messaging required; it's control-flow driven. The orchestrator spawns a `CHECK <agent-id>` at these triggers:
1. **On wave boundary** — after spawning a parallel wave, and each time control returns from a completing background agent, spawn a check for every *still-active* agent-id. This catches mid-run `spiral` / `stall` / `drift` while other agents keep working.
2. **On agent completion** — when a Phase-3 implementation agent returns, before merging its worktree, spawn a final check for that agent-id (catches `shallow` / `drift` on the finished output).

Each check is a short **foreground** spawn: the orchestrator waits for the one-line summary, then reads any new lines appended to `agent_states/escalations.jsonl` and acts on `pause-request` / `depth-recommendation` per the escalation ladder (5.5.4). Maintain a `supervisor_checks` counter and a `supervisor_check_failures` counter in cycle state — they feed the run report and the health watchdog below.

```
Agent(subagent_type: "supervisor", model: "[supervisor row from Model Allocation]",
      prompt: "CHECK [agent-id]. Feature: [name].
               Cycle state: agent_states/cycle-state-[name].md.
               Agent ID convention: <role>-<task-number>.
               Do exactly one check per supervisor.md, then exit.")
```

The supervisor writes to `agent_states/whispers/`, `agent_states/escalations.jsonl`, and `agent_states/supervisor/` (heartbeat + state.md). It reads from `agent_states/events/*.jsonl` (the per-agent telemetry from 5.2.1) and `agent_states/cycle-state-*.md`.

**Artifact layout (Phase 3):**

```
agent_states/
  cycle-state-<feature>.md       # orchestrator writes inline (monitor if agent_messaging)
  events/<agent-id>.jsonl        # PostToolUse hook writes
  whispers/<agent-id>.md         # supervisor writes
  escalations.jsonl              # supervisor writes
  supervisor/state.md            # supervisor writes
  supervisor/heartbeat           # supervisor touches
```

### 3.2 — Dependency analysis

Classify parent tasks: **independent** (start now) or **dependent** (wait for prerequisite).
Classify sub-tasks by type → assign agent per the delegation table in 3.3.

Present analysis in dry-run mode. In `--exe` mode, proceed.

### 3.3 — Spawn agents

Before spawning any implementation agent:

1. **Extract file paths** from the task file's "Relevant Files" section — pass these explicitly in every agent prompt. This eliminates discovery round-trips.
2. **Extract AC** from the PRD's Acceptance Criteria section — pass directly to test and verify agents so they skip PRD search.

For each parent task (independent in parallel, dependent when ready), first **create the task worktree** per the **Phase-3 worktree protocol** (`git worktree add` from `feature/[name]` HEAD), then:

1. **Pre-digest** (haiku, background) — default for any task touching ≥ `skip_predigest_if_files_lt` existing files (Per-phase skip flags in `.claude/config.md`, default 2). Reads relevant source files and returns a ~150-line structured summary (public API, constructor deps, key patterns). Skip when below threshold, when the task creates all-new files, or when a digest was already saved.

   ```
   Agent(model: "[pre-digest model from Model Allocation table in .claude/config.md]", run_in_background: true,
         prompt: "Read these files and return a ~150-line structured summary
                  covering: public API (class names, method signatures, constructor
                  deps), key patterns, and anything an implementer needs to know.
                  Files: [file paths from Relevant Files section].
                  Be dense — no prose explanations, just facts.")
   ```

   Wait for the digest before spawning the implementation agent. Pass digest content in the implementation agent's prompt.

2. **Implement** — dispatch by the parent task's `[kind: …]` tag (set by `generate-tasks`). If the tag is missing on an existing task file, fall back to inferring from the prose. The agent runs in the task worktree; no `isolation:` parameter.

   | `kind` value | subagent_type | Model |
   |---|---|---|
   | `scaffold` or `scaffold-*` | `scaffold` | per config |
   | `ui-story` | `ui-story` | per config |
   | `test` | `test` | per config |
   | `coding` | `coding` | per config |
   | `general-purpose` | general-purpose | per config |

   For `scaffold-*` kinds (e.g., `scaffold-facade`), pass the pattern name in the agent's prompt so it loads the matching `.claude/agents/scaffold/<pattern>.md`.

   Read the **Model Allocation** table in `.claude/config.md` for each agent's assigned model under the active preset. If no config file exists, default to sonnet for all implementation agents.

   Run **Context Sources retrieval** for stage `implement` (see § Context Sources retrieval) once for the parent task — query with the task's Relevant Files + touched symbols — and reuse the result across every agent spawned for this task (do not re-query per sub-agent). Prepend any `## Context: <id>` blocks to the prompt.

   ```
   Agent(subagent_type: "scaffold", model: "[per config]",
         prompt: "[worktree-startup preamble — Phase-3 worktree protocol]
                  [Context blocks if any]
                  PRD: [prd-path]
                  Source files: [paths from Relevant Files, rooted at the worktree]
                  AC (pre-extracted): [AC items from PRD]
                  Task: [sub-task list]
                  Digest: [digest content if available]")
   ```

   - Agent marks sub-tasks `[x]` as it completes them
   - On failure/ambiguity: report to orchestrator, continue independent sub-tasks

3. **Pre-flight contradiction classifier** (haiku, runs in the same task worktree after implementer commits, before test agent). Skip when `skip_preflight_if_no_existing_tests` is `true` (Per-phase skip flags in `.claude/config.md`, default true) **and** grep of the **Test path glob** (`.claude/config.md` § Project Commands) for any public symbol the implementer touched returns no hits — true greenfield needs no classification.

   ```
   Agent(subagent_type: "test-preflight", model: "haiku",
         prompt: "[worktree-startup preamble]
                  Changed source files: [paths the implementer modified]
                  AC (pre-extracted): [AC items from PRD]
                  Base ref: feature/[name]")
   ```

   The classifier returns a `## Existing test classifications` table. Lift it verbatim into the test agent's spawn prompt (next step). It produces no file artifact — its output lives in the return value only.

4. **Test** (separate agent from implementer; runs in the **same task worktree** as the implementer, after pre-flight — so it sees the implemented code; no `isolation:` parameter):
   - **Write** (sonnet): `Agent(subagent_type: "test", model: "sonnet", prompt: "[worktree-startup preamble] PRD: [prd-path]\nSource files: [paths]\nTest files: [paths]\nAC (pre-extracted): [AC items]\nTask: [task description]\n[pre-flight classifications table if non-empty]")`
   - **Fix** (sonnet): re-spawn `test` agent with failure output and source paths

### 3.4 — Handle results

- **Success**: capture the agent's `## Deviations` section — forward each to monitor (`DEVIATIONS [task-id] AC [ac-id]: [what] | reason: [why]`); then run the **Commit protocol** below (clean-check → test → merge task worktree into feature branch → teardown), send status to monitor
- **Failure**: escalation ladder (below)
- **Contradiction-exit** (agent's return contains `status: contradiction-exit` per the `contradiction-exit` skill — item 5.4.4): emit `RESCUE contradiction-loop [task-id]: [trigger value] | resolution: human escalation | artifact: [report path or "agent return"]` to monitor, then jump to **L4** immediately. Do **not** run the escalation ladder for L1–L3 — the agent already exhausted its retries by construction. Preserve the structured block verbatim in the user-facing message.
- **Stalled** (agent killed by the harness watchdog, or returns no clean result): run **Stall salvage** (below), then the escalation ladder using the salvage assessment as context
- **Blocked**: notify user, continue independent tasks

### Supervisor cadence (5.5.4)

The PostToolUse hook increments a per-agent counter at `agent_states/counters/<agent-id>` on every tool call. At your watchdog tick (and at each sub-task boundary), read all counter files:

- For each agent-id whose counter ≥ `cadence_n` (Supervisor Thresholds in `.claude/config.md`, default 5), spawn a supervisor check:
  ```
  Agent(subagent_type: "supervisor", model: "[supervisor row from Model Allocation]",
        prompt: "CHECK <agent-id>. Feature: [name].")
  ```
- After spawn returns (or on a separate completion signal), reset that agent's counter to `0` by overwriting the file.
- **Skip cadence checks entirely if supervisor health Status is `disabled`** (degraded mode — see below).

Supervisor spawns are fresh per check — continuity lives in `agent_states/supervisor/state.md`. The escalation channel below is how the supervisor signals back to you.

### Supervisor health (5.5.5)

Six layered mechanisms, evaluated as you spawn and collect each check (the cadence above):

1. **Last-check record (not a liveness watchdog).** The supervisor touches `agent_states/supervisor/heartbeat` at the end of every successful check. Because checks are intermittent *by design*, a stale heartbeat is **not** an outage signal — never treat heartbeat age as "offline." Record the heartbeat mtime as the supervisor's `last_check` for the run report. Liveness is judged per-check by mechanism 2.
2. **Per-check spawn watchdog.** When you spawn a `CHECK <agent-id>`, treat the spawn as failed if it errors or does not return a summary within 30s. Increment `supervisor_check_failures`, emit `RESCUE supervisor-stall [supervisor]: check [agent-id] no return in [N]s | resolution: skip-or-disable | artifact: agent_states/supervisor/state.md` to monitor, and skip this tick's result.
3. **Rescue logging on outage.** Already provided by (2) — `supervisor-stall` is in the rescue type enum.
4. **Circuit breaker.** Maintain the **Supervisor health** section in cycle state (via monitor's `SUPERVISOR_HEALTH` verb). If `supervisor_check_failures` increments 3 times within a 5-minute window, **disable** the supervisor for the rest of the cycle: emit `RESCUE supervisor-disabled [supervisor]: 3 check failures in 5m | resolution: degraded mode | artifact: cycle-state` and forward `SUPERVISOR_HEALTH status:disabled spawns:[n] stalls:[n] heartbeat:[last] disabled_at:[now] reason:circuit-breaker`. Stop spawning supervisor checks; the cycle continues in degraded mode (no whispers, no escalations — falls back to today's behavior).
5. **Run-report check success rate.** When you build the cycle run report at Phase 4A, populate the **Supervisor health** subsection of the Agent Telemetry block from cycle state: `supervisor_checks` attempted, `supervisor_check_failures`, and success rate. Classify the cycle as **degraded** if success rate < 90% or status is `disabled`.
6. **`self-improve` hook.** Documented in `.claude/agents/self-improve.md` Step 2 (Effectiveness patterns → Supervisor health). When `supervisor-stall` or `supervisor-disabled` appears in ≥ 3 of the last 5 cycles, `self-improve` raises a P0 recommendation.

### Plan-revision flow (5.5.6)

When you process a `depth-recommendation` escalation, you decide — the supervisor only *recommends*. Three rules:

1. **Decide accept or reject** with a one-line rationale grounded in current cycle context (task progress, AC scope, escalation ladder state, time pressure). Examples: "accepted — task 2.0 has 3 unrelated sub-tasks per Relevant Files," "rejected — split would create cross-cutting test dependencies," "rejected — too late in Phase 3 to re-shape."
2. **Emit `SUPERVISOR_REC suggestion:[text] accepted:[true|false] rationale:[text]` to monitor** for every recommendation — accepted *and* rejected. Silent drops destroy the audit trail and starve `self-improve` of tuning data.
3. **If accepted, apply the change** within your existing primitives — re-spawn a task with a different model, split a parent task into two task-file entries, insert a verify pass, etc. The recommendation is not a pipeline-design override; the orchestrator still owns pipeline shape.

If a recommendation conflicts with a recommendation you accepted earlier (or with mid-cycle scope changes), prefer the later signal but record both decisions.

### Supervisor escalation polling

The orchestrator polls `agent_states/escalations.jsonl` at three moments only (item 5.5.2):
1. **Phase transition** — end of Phase 3, before spawning verify/review.
2. **Sub-task boundary** — after each parent task's Commit protocol, before spawning the next.
3. **After each supervisor check** — you've just collected a check's result (see 5.5.5: per-check spawn watchdog + circuit breaker), so read any escalations it appended.

Use a per-cycle `escalation_cursor:` field in cycle state to track the last processed line. See the `escalations` skill for per-type handling (`pause-request` → recovery decision + `RESCUE`; `depth-recommendation` → log decision in cycle state; `bug-pattern` → log + surface in run report). Never poll mid-tool-call.

**Agent-ID stamp.** Every Phase-3 implementation agent must be spawned with an `agent_id` of the form `<role>-<task-number>` (e.g., `test-3.0`, `ui-story-2.1`). The PostToolUse hook routes events into `agent_states/events/<agent-id>.jsonl` and the supervisor writes whispers to `agent_states/whispers/<agent-id>.md` keyed on this ID. Include the agent-id explicitly in the spawn prompt so the agent knows which whisper file to poll.

### Escalation ladder

Max 3 attempts per sub-task, 5 total per parent task.

| Level | Trigger | Action |
|---|---|---|
| L1 | Compile/analysis/simple test error | **Haiku** fix agent, 1 attempt |
| L2 | L1 failed or non-trivial error | Next model up with error + context |
| L3 | L2 failed | Revert changes, **opus** fresh attempt (anti-pattern: what failed) |
| L4 | All auto-recovery failed | Block, report to user, continue independent tasks |

Send every escalation to monitor: `ESCALATION [task-id] L[1-4]: [model] [reason]`

### Stall salvage

A stalled agent — one the harness watchdog kills before it returns cleanly, or one that exits with its expected artifact missing or still `IN PROGRESS` — must leave an audit trail, not be silently replaced by manual work.

On detecting a stall, spawn one inline Haiku salvage pass — do not analyze the stall yourself:

```
Agent(subagent_type: "general-purpose",
      model: "[salvage model from Model Allocation table in .claude/config.md]",
      prompt: "The [agent role] agent for [task/feature] stalled before finishing.
               Salvage only what is recoverable — do NOT redo its work.
               Inputs: [partial report path if any] and the git state of [worktree or branch]
               (run `git diff [base]` and `git log`).
               Produce a `PARTIAL — agent stalled` artifact at [path]: record what
               completed, mark what is missing, assess whether the result is coherent.
               Return the artifact path.")
```

Send `RESCUE stall [agent-id]: [agent role] stalled before finishing | resolution: ran Haiku salvage | artifact: [salvage report path]` to monitor. Then: for a stalled `verify`/`review`, the `PARTIAL` report feeds the 4A gate; for a stalled implementation agent, proceed via the escalation ladder with the salvage assessment as the "what was attempted" context.

### Bug tracking

Existing-code bugs (not agent-written code):
1. Log in `documentation/bugs.md` (next BUG-NNN ID)
2. Note in cycle state
3. Don't fix unless blocking. If blocking: fix, move to `bugs_resolved.md`.

### Commit protocol

Per parent task, when all sub-tasks pass:
1. **Clean-check** — assert `git status --porcelain` in the **main checkout** is empty. The orchestrator writes no implementation code, so a dirty main checkout means an agent leaked outside its worktree: abort the merge, report to the user, do not proceed.
2. Run test + typecheck/lint commands (from **Project Commands** in `.claude/config.md`) in the task worktree.
3. **Silent-skip gate** — grep the diff of test files (`git diff feature/[name]...HEAD -- '<test-glob>'` inside the worktree, where `<test-glob>` is the **Test path glob** from `.claude/config.md` § Project Commands) for the regex patterns in the active pack's **Test anti-patterns** file (`.claude/config.md` § Project Commands → *Test anti-patterns*; one regex per line, `#`-comments stripped). Any hit blocks the merge.
   On hit: emit `RESCUE silent-skip [task-id]: [file:line + pattern] | resolution: re-spawn test agent | artifact: [worktree path]` to monitor, then re-spawn the **test** agent in the same worktree with the offending file + matched pattern in its prompt. One retry allowed; a second hit escalates per L3 of the ladder. Scope is the test glob only — production-code matches are not flagged (legitimate production patterns).
4. Green and gate clean → ensure the task work is committed on `cycle/[story]/task-[N.0]` (conventional format), merge that branch into `feature/[name]`, mark parent `[x]`, update monitor, then **tear down the worktree**: `git worktree remove --force .claude/worktrees/[story]-task-[N.0]` and `git branch -D cycle/[story]/task-[N.0]`.
5. Red tests → escalation ladder from L1

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

1. Run test + typecheck/lint commands from **Project Commands** in `.claude/config.md` (final full suite). **Analyzer drift check (5.8.1):** if `analyzer_baseline` is `soft_warn` or `hard_fail_if_exceeded`, diff the current analyze output against `cycle_reports/<feature>/analyzer-baseline.txt` recorded at Phase 3 start. Append the diff (or "None") to the run report's `## Analyzer drift` section. Under `hard_fail_if_exceeded`, force the review verdict to REQUEST CHANGES if the diff is non-empty.
2. Mark ALL tasks and sub-tasks `[x]` in the task file (final sweep)
3. Generate cycle report → `cycle_reports/[feature-name]-[YYYY-MM-DD].md`:
   - Summary (what was implemented, per parent task)
   - Branch name, commits (hash + message), database/schema changes (or "none")
   - Bugs discovered, known limitations, blocked tasks, follow-up items
   - Deviations from PRD AC (copy the cycle state's **Deviations** section verbatim; write "None" if empty)
   - Scope changes (copy the cycle state's **Scope changes** section verbatim; write "None" if empty)
4. Present cycle report to user inline
5. Generate run report → `agent_tasks/reports/report-prd-[feature-name]-[YYYY-MM-DD].md` using template `.claude/skills/cycle/report-template.md`. **Agent Audit**, **Rescues**, and **Agent Telemetry** sections are required. Copy the **Rescues** list from the cycle state file verbatim into the run report's `## Rescues` section (write "None" if cycle state has no rescues). For Agent Telemetry, read all files in `agent_states/events/` and aggregate one row per `agent_id` — fields: `agent_type`, tool-call count, breakdown by `tool`, error count (`exit:error`), wallclock (last `ts` − first), and `stop_reason` from any `subagent_stop` line. If `agent_states/events/` is empty or missing, write *"Telemetry not collected — enable hooks per README."* in place of the table. If >10 reports exist, summarize oldest into `agent_tasks/agent_metrics.md`.
6. **Autonomous verify & review** — read `.claude/config.md` Optional Agents section.

   **Mode override:** in `--mode hotfix`, **skip the review spawn entirely** and spawn only `verify` at **lite** depth (see 5.6.6). In `--mode lean` and `--mode full`, behave as below.

   **Skip flag:** when `skip_review_if_files_lt` (Per-phase skip flags in `.claude/config.md`, default 0/off) is > 0 and `git diff [base] --name-only | wc -l` is below it, also skip review. Note the skip in the run report's Agent Audit (`review: skipped — files changed N < threshold M`).

   If both are enabled, issue the two `Agent` calls in a **single message** so they run concurrently — verify and review share no state and must not gate each other.

   Run **Context Sources retrieval** for stages `verify` and `review` (see § Context Sources retrieval) and prepend any `## Context: <id>` blocks to the respective prompts below.

   **Compute verify depth (5.6.6).** Before spawning verify, gather the inputs from cycle state and the git diff:
   - `files_changed_count` = `git diff [base] --name-only | wc -l`
   - `test_files_touched` = any changed path matches the **Test path glob** (`.claude/config.md` § Project Commands)
   - `domain_or_migration_files_touched` = any changed path under a domain/data layer (per `.claude/config.md` § Layer Boundaries) or matches `**/migrations/**`
   - `deviations_non_empty` = cycle state `## Deviations` has entries
   - `phase3_retry_count` = count of `ESCALATION` lines (any level) in cycle state
   - `phase3_contradiction_exits` = count of `RESCUE contradiction-loop` entries in cycle state's `## Rescues`
   - `mid_cycle_scope_expansion` = cycle state `## Scope changes` has any `added` or `modified` entry

   Apply the rule:
   - **`--mode hotfix` forces `lite`** (overrides everything else).
   - **`deep`** when ANY of: `phase3_retry_count > 3` OR `phase3_contradiction_exits >= 1` OR `mid_cycle_scope_expansion`. Deep wins over lite if both conditions fire.
   - **`lite`** when ALL of: `files_changed_count < 3` AND NOT `test_files_touched` AND NOT `domain_or_migration_files_touched` AND NOT `deviations_non_empty`.
   - Otherwise **`standard`**.

   Record the chosen depth and its inputs in cycle state under `## References` → `Verify depth: <tier> | inputs: <key:value pairs>` for `self-improve` calibration.

   If `verify` is **enabled**: spawn the `verify` agent with the PRD path, source file paths, test file paths, pre-extracted AC, **and the computed depth**:
   ```
   Agent(subagent_type: "verify", model: [per config Model Allocation],
         prompt: "[Context blocks if any]
                  PRD: [prd-path]. Source files: [paths]. Test files: [paths].
                  AC: [pre-extracted]. Branch: [branch-name]. Depth: <lite|standard|deep>.
                  Report path: agent_tasks/reports/verify-[prd-stem]-[date].md — write your report there.
                  Work autonomously — no user interaction.")
   ```

   If `review` is **enabled**: spawn the `review` agent with the branch name:
   ```
   Agent(subagent_type: "review", model: [per config Model Allocation],
         prompt: "[Context blocks if any]
                  Branch: [branch-name]. PRD: [prd-path].
                  Report path: agent_tasks/reports/review-[feature]-[date].md — write your report there.
                  Work autonomously — no user interaction.")
   ```

   Wait for both to complete.

   **Report-file check** — for each agent spawned, confirm its report file exists at the dictated path and its header `Verdict:` is no longer `IN PROGRESS`. A missing file or a still-`IN PROGRESS` verdict means the agent stalled before finishing — run **Stall salvage** (§3.4); its `PARTIAL — agent stalled` report then feeds the gate below.

   Include verify and review summaries in the cycle report (step 3). Then apply this gate before allowing 4B:

   | Verify verdict | NO IMPL count | 4B gate |
   |---|---|---|
   | PASS | 0 | Proceed to 4B automatically |
   | PARTIAL | 0 | Proceed — but present gaps and ask user to confirm before 4B |
   | PARTIAL | > 0 | Block 4B — present unimplemented criteria, require user to fix or explicitly accept the gaps |
   | FAIL | any | Block 4B — present failures, require fixes before release |

   If `verify` was skipped, the gate does not apply — proceed to 4B but note: **"Verify was skipped — run `/verify` before merging."**

   If either agent is set to `skip` in config, do not spawn it. Instead recommend: **"Run `/verify` and/or `/review` in separate conversations, then return here for release."**

7. Run the **Finalize one-shot spawn** (§ State persistence) with `FINALIZE report:[path]` — it archives, then deletes the state file. **Do not skip.** The cycle may end here if the user handles the PR manually.

**4A is not complete until steps 1–7 are done. Do not skip any step.**

### 4B — Release (after gate passes; user confirmation required for PARTIAL)

8. Push branch, `gh pr create` targeting the `pr_target` from `.claude/config.md`
9. Update roadmap (skip if cycle didn't originate from a roadmap story):
   - `documentation/ROADMAP.md`: set story Status to `DONE` in Story Index
   - Move story's full section to `documentation/roadmap_completed.md` under the appropriate Phase heading. Mark all AC `[x]`.
10. Append changelog entry to `documentation/CHANGELOG.md`

