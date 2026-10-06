---
name: cycle
description: SDLC feature pipeline orchestrator. Run /cycle to go from a feature description to a tested, reviewed PR — creates PRD, generates tasks, spawns parallel implementation agents, verifies, reviews, and opens the PR. Supports --mode full|lean|hotfix, --exe, --manual, and resume from state file.
disable-model-invocation: true
---

# Cycle — SDLC Feature Pipeline

You are the orchestrator. You run at the opus tier (resolve through `.omp/agent-config.md` § Model Versions; under omp this is `modelRoles.slow`). Manage gates, delegate to agents, make judgment calls. You do not write implementation code — spawn agents for that.

Feature or PRD: **$ARGUMENTS**

## Configuration

Read `.omp/agent-config.md` at startup for model allocation, effort settings, artifact paths, optional agent settings, and cycle options. Use these values throughout — do not use hardcoded defaults when the config file exists. If no config file exists, fall back to: sonnet for implementation agents, haiku for pre-digest and monitor, opus for orchestrator.

When passing `model:` to Agent calls, resolve the label (opus/sonnet/haiku) through the **Model Versions** table in .omp/agent-config.md. Pass the specific model ID (e.g. `claude-opus-4-6`) rather than the alias label. If no Model Versions table exists, pass the alias label as-is.

## Live Environment (auto-injected)

Active cycle states:
!`ls agent_states/cycle-state-*.md 2>/dev/null || echo "none"`

**Janitor check**: for each state file listed above, check whether a matching cycle report already exists in `cycle_reports/` (match by feature name substring). If a match exists, the cycle completed without sending `FINALIZE` — delete the state file now and do not offer to resume it.

**Task-branch janitor**: omp's isolated tasks create `omp/task/<id>` branches during Phase 3. Run `git branch --list 'omp/task/*'`. For any whose cycle is not among the active state files above (orphaned from a crashed cycle), prune: `git branch -D <branch>`. omp cleans up its own isolation workspaces on completion, but task branches can linger if a cycle was interrupted mid-merge.

**Gitignore guard** — ensure runtime artifacts (cycle state, telemetry event logs) are never committed to the project repo. Idempotent; appends a marked block once:
!`grep -q 'agent-sdlc (managed)' .gitignore 2>/dev/null || printf '\n# >>> agent-sdlc (managed — do not edit) >>>\nagent_states/\n# <<< agent-sdlc <<<\n' >> .gitignore`

Only runtime artifacts are ignored. `agent_tasks/` (live PRD + task files) and `documentation/` are **durable** — they travel with the feature branch and must stay committed. Cycle reports and run reports are written to the external docs vault (see config **Artifact Paths**) and never land in the project repo at all.

**Vault link guard** — read the **Docs Vault** section of `.omp/agent-config.md`. If `vault_root` is non-empty, wire the vault before any report is written this cycle:
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

**Under omp**, the dry-run maps to omp's native plan mode. Launch the session with `--plan`:
```bash
omp --plan
/cycle Add CSV export to the reports page
```
omp plan mode restricts tools to `read`/`search`/`find`/`lsp`/`web_search` — no writes, no task spawns — preventing accidental implementation during dry-run. This is the equivalent of running `/cycle` without `--exe`, but enforced at the harness level. When `--plan` is active, skip the `--exe` flag entirely (plan mode cannot spawn agents).
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

### Phase-3 isolation (native omp)

Under omp, each Phase-3 implementation agent spawns with `isolated: true`. omp captures a baseline from the current HEAD (the feature branch), creates an isolated workspace, runs the agent, commits to a task branch (`omp/task/<id>`), and cherry-picks into the parent (feature branch). This replaces the manual git worktree protocol entirely — no `git worktree add`, no worktree-startup preamble, no WORKTREE MISMATCH rescue, no manual merge/teardown.

**Mode override:** in `--mode hotfix`, isolation is skipped. A single implementation agent runs in the main checkout on the feature branch (`isolated: false`). The rest of this section applies only when mode is `full` or `lean`.

**One isolated workspace per agent** — the implementer and test agent no longer share a worktree. The implementer commits → omp merges into the feature branch → the test agent gets a fresh workspace from the updated HEAD. This is cleaner: the test agent sees committed, merged code rather than worktree-local state.

**Dependency ordering:** dependent tasks fork from the post-merge HEAD automatically — spawn a dependent task only after its prerequisite's isolated agent has completed and omp has merged the task branch.

**Handoff format** — every Phase-3 implementation agent's final response must include a `## Deviations` section. Each item: `task: [task-id] | ac: [AC ref] | implemented: [what] | reason: [why]`. Write `None` if the implementation matches PRD AC literally. The orchestrator forwards each deviation to monitor via a `DEVIATIONS` message (see §3.4 Success).

Named agents (`scaffold`, `ui-story`, `test`, etc.) have their model set in their definition. Pass `model:` only to override or for generic haiku agents (monitor, pre-digest).

### Agent identity (`role` field)

Every task spawn includes a `role:` field — a short identity string that becomes the agent's system-prompt persona and registry display name (visible in `irc(op: "list")`). Format: `<role> (task <task-number>)`. Example: `role: "Scaffold engineer (task 2.0)"`. This replaces the old `label` frontmatter convention for status display.

### Shared context (`local://` files — on-demand, not injected)

Write each piece of shared background to a `local://` file once. Subagents share the parent's `local://` root. Each agent's `assignment` references only the files it needs — the agent reads them on demand via the `read` tool. This avoids injecting the full shared context as input tokens into every agent's system prompt (which the `context` field would do).

**Granular files** (write once, reference per-agent):

| File | Contents | Who reads it |
|---|---|---|
| `local://prd.md` | PRD path + feature description | implementer, test, verify, review |
| `local://ac.md` | Pre-extracted AC from PRD | test, verify, implementer |
| `local://ctx-sources.md` | Context-source blocks (stage `implement`) | implementer, test |
| `local://digest-<task>.md` | Pre-digest summary for task N | implementer for task N only |
| `local://commands.md` | Project Commands (test, analyze, codegen) | any agent that runs them |

**Do NOT use the `context` field** for batch spawns — it raw-injects all shared background into every subagent's system prompt as input tokens. Use `local://` files + `read` instead so each agent pulls only what it needs. Pass an empty `context` (or minimal one-liner) in batch calls; the `assignment` carries the `local://` file references.

**Prompt budget**: pre-digest prompts <200 words. Implementation agent `assignment`: sub-task list + `local://` file references only — instructions live in the agent definition.

### Context Sources retrieval

A reusable step invoked at five stages (`prd`, `tasks`, `implement`, `review`, `verify`). The full contract is in the `context-sources` skill; the mechanics:

1. Read `.omp/agent-config.md` § Context Sources. Select rows where `enabled` is `true` **and** `consult_at` contains the current stage. If none, skip silently.
2. For each selected `mcp` source: query it once with the row's `query_hint` plus concrete context (feature name, the task's Relevant Files, touched symbols). For `skill` sources, run the named skill.
3. Write the trimmed result to `local://ctx-sources.md` (append per source). Each agent's `assignment` references this file if it needs context-source data. Instruct the agent to echo `context-sources-consulted: <ids|none>` in its handoff.

This is the same inject-downward pattern as Pre-digestion and Known pitfalls. `predigest` is intentionally **not** a consult stage by default (the pre-digest is a cheap summarizer).

### Handoff validation

At every agent handoff, the orchestrator confirms the agent's frontmatter `produces:` file exists at the expected path. Missing = agent failure: re-spawn (Phase 1A / 2), escalate (Phase 3), or run **Stall salvage** (Phase 4A — already wired).

---

## Branch strategy

All work on feature branches, never directly on the base branch.

- **Naming**: read `feature_branch_pattern` from the **Branch Configuration** table in `.omp/agent-config.md`. Default: `feature/[short-description]`, `fix/...`, or `refactor/...`
- **Create at Phase 2B**: `git checkout -b feature/[name] [base_branch]` — where `[base_branch]` is the `base_branch` value from `.omp/agent-config.md`
- **Parallel tasks**: each isolated agent gets its own workspace from `feature/[name]` HEAD. omp creates `omp/task/<id>` branches and cherry-picks into `feature/[name]` on completion. See **Phase-3 isolation** (§ Agent spawn rules).
- **Merge order**: dependency order. Run the test and typecheck/lint commands (from **Project Commands** in `.omp/agent-config.md`) after each merge.
- **Conflicts**: sonnet agent resolves. Ambiguous conflicts → escalate to user.
- **After Phase 4**: do NOT merge into the base branch. User decides after `/verify` + `/review`.

---

## State persistence

State directory: `agent_states/` (ephemeral — deleted on completion).

### State persistence

The orchestrator keeps `agent_states/cycle-state-<feature>.md` current throughout the cycle, using the template and verb list in `.omp/agents/monitor.md`. **Two modes**, selected by `agent_messaging` in `.omp/agent-config.md` § Cycle Options (default `false`):

- **`agent_messaging: false` (default) — inline.** *You*, the orchestrator, write the state file directly. The monitor's verb list (`GATE`, `SPAWNED`, `PARENT`, `RESCUE`, `DEVIATIONS`, `SCOPE_CHANGE`, `SUPERVISOR_HEALTH`, …) is your **checklist of what to record when**. This is the normal path and is **not** a degradation — never log it as a rescue. No background monitor is spawned. Inline is also the only mode that works without the irc tool / agent-teams.
- **`agent_messaging: true` — delegated.** Spawn the background monitor once at Phase 3 start. The monitor blocks on `irc(op: "wait", from: "Main", timeoutMs: 0)` to receive verbs in real time — send each verb via `irc(op: "send", to: "<monitor-id>", message: "<verb>")`. It writes the state file so your context stays lean:
  ```
  Spawn the `monitor` agent (model tier: haiku, id: "monitor") as a background task with this prompt:
  > Feature: [name]. State file: agent_states/cycle-state-[name].md. You are in streaming mode — block on irc(op: "wait", from: "Main", timeoutMs: 0) to receive state-update verbs. Write each verb to the state file immediately. On FINALIZE, archive and clean up.
  ```

**Reading convention for the rest of this skill:** wherever a step says "emit / send / forward / update `<VERB>` to monitor," it means *record that verb in cycle state* — write it inline (default) or send it to the monitor via the `irc` tool (when `agent_messaging: true`). Verb formats are defined in `monitor.md`.

**Save-before-spawn:** before spawning any sonnet/opus agent, bring the state file current first (inline) or send the pending verbs to the monitor — so a crash mid-spawn leaves an accurate recovery point.

**Finalize is always a one-shot spawn.** Regardless of mode, cleanup runs as a single short-lived monitor spawn — it holds the `rm agent_states/*` permission the orchestrator does not:
```
Spawn the `monitor` agent (model tier: haiku) with this prompt:
> FINALIZE report:[run-report-path]. Archive per monitor.md, delete all agent_states/ files for this cycle, then exit.
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
| Empty | Check `agent_states/` for active/paused cycles. If none: read `feature_idea_on_empty` from `.omp/agent-config.md` Cycle Options. If true, read the Feature Ideas path from config (default `documentation/FEATURES.md`) and present any unstarted items — offer to start a cycle for one, or run `/feature-idea` to capture a new idea. If FEATURES.md doesn't exist, has no unstarted items, or `feature_idea_on_empty` is false, ask for a feature description. |

Create/update state file immediately after determining entry point.

**Checkpoint recovery (omp).** Under omp, you can checkpoint your session before risky operations (escalation ladder L3 revert, mid-cycle scope changes, complex merges). If the operation fails, `rewind` to the checkpoint instead of restarting the cycle:
```
checkpoint(action: "set", label: "pre-L3-revert-task-2.0")
# ... attempt the operation ...
# if it fails:
rewind(to: "pre-L3-revert-task-2.0")
```
This is faster than resume-from-state-file when the failure is recent and the state file hasn't been updated yet. Use checkpoints at: before each escalation ladder step, before mid-cycle scope changes, before complex dependency-order merges.

**Phase tracking (todo tool).** Initialize the `todo` tool with the pipeline phases as a visible progress tracker. Mark each phase `in_progress` when entering, `done` when complete. This gives the user real-time progress in the TUI alongside the cycle state file:
```
todo(op: "init", items: ["Phase 1A — Create PRD", "Phase 1C — Gate 1", "Phase 2 — Generate tasks", "Phase 2B — Gate 2", "Phase 3 — Implementation", "Phase 4A — Wrap-up", "Phase 4B — Release"])
```
On resume, re-initialize and mark completed phases `done` before continuing.

---

## Mode-conditional phase routing (5.6.1)

Before entering Phase 1A, route per the active `--mode`:
- **`full`** — all phases run as written below.
- **`lean`** — skip `create-prd` spawn in Phase 1A; derive AC inline from the feature description and store under cycle state `## References` → `AC summary:`. Skip Phase 1C (folded into Phase 2B). Phase 2 still spawns `generate-tasks` (with the inline AC summary as input). Phase 2B presents AC + tasks together for one combined approval.
- **`hotfix`** — skip Phases 1A, 1C, 2, 2B entirely. Treat the feature description as a single implicit task. Go directly to Phase 3 with one agent, no isolation (`isolated: false`), no pre-digest. Phase 4A runs verify (lite depth) only.

## Phase 1A — Create PRD

Spawn the `create-prd` agent (model: sonnet) with the feature description. The agent explores the codebase, checks the roadmap, scans existing PRDs, and returns a complete PRD draft and file path.

Run **Context Sources retrieval** for stage `prd` (see § Context Sources retrieval) — results go to `local://ctx-sources.md`.

```
task(agent: "create-prd", context: "Create a PRD from the feature description.",
  tasks: [{ id: "create-prd", role: "PRD author",
    assignment: "Feature: [description]. [Any roadmap story number or context]. Read local://ctx-sources.md if it exists for context-source data." }])
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

Run **Context Sources retrieval** for stage `tasks` — results go to `local://ctx-sources.md`.

```
task(agent: "generate-tasks", context: "Decompose the PRD into implementation tasks.",
  tasks: [{ id: "generate-tasks", role: "Task planner",
    assignment: "PRD: [prd-file-path]. Read local://ctx-sources.md if it exists for context-source data." }])
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

If `analyzer_baseline` in `.omp/agent-config.md` § Hygiene flags is `soft_warn` or `hard_fail_if_exceeded`, capture the baseline at Phase 3 start by running the **Analyze / lint** command from `.omp/agent-config.md` § Project Commands and redirecting its output:

```
<analyze-lint command> > cycle_reports/<feature>/analyzer-baseline.txt 2>&1 || true
```

Phase 4A re-runs the same command and diffs. New warnings in the diff:
- `soft_warn` → flagged in the run report under a new "Analyzer drift" section; cycle proceeds.
- `hard_fail_if_exceeded` → review verdict flips to REQUEST CHANGES regardless of other findings; the diff is included in the review report.

### Known pitfalls (5.8.3)

If `known_pitfalls_path` in `.omp/agent-config.md` § Hygiene flags points at an existing file, read it once at Phase 3.3 (before spawning implementation agents). File format:

```markdown
## <Short title>
Globs: src/**/Infrastructure/**, tests/**/Data*
Severity: warn | hard
Body:
[One paragraph describing the pitfall and how to avoid it. Cite a real incident if available.]
```

For each parent task, match the task's "Relevant Files" paths against each entry's `Globs:` line. For every match, append the entry's `Body:` to the agent's spawn prompt under a `## Known pitfalls for files you'll touch` section. Severity `hard` entries get a "Read this carefully — the same bug has happened before:" preface. The framework provides the matching mechanism; the project owns the file content.

### Compact at phase boundaries (5.8.2)

If `auto_compact_at_boundaries` in `.omp/agent-config.md` § Hygiene flags is `on`, invoke `/compact` at:
- **Phase 2→3 transition** — after Gate 2 is approved, before any Phase 3 spawn.
- **Phase 3→4A transition** — after the last parent task merges, before the Phase 4A wrap-up runs.

Compaction reclaims context but can cost orchestrator decision-continuity; keep `off` until telemetry shows the trade-off is favorable for your cycles.

### 3.1 — Pre-flight

Check `.claude/agents/scaffold/` for project-specific pattern files (files with `Type: project-specific`). If none exist and the task list includes scaffold-type work, autonomously spawn a setup-scaffold agent:

```
task(agent: "explore", context: "Run the /setup-scaffold skill in scan mode.",
  tasks: [{ id: "setup-scaffold", role: "Pattern discovery",
    assignment: "Read .claude/skills/setup-scaffold/SKILL.md and follow its steps. Do not ask the user questions — use your best judgment for pattern discovery and create all pattern files you find. Report what was created." }])
```

Run this in the background — it does not block Phase 3 from continuing. Scaffold agents spawned later will pick up the pattern files once they exist.

Initialize state persistence per **§ State persistence**: by default (`agent_messaging: false`) write the state file inline — no agent spawned. Only when `agent_messaging: true`, spawn the background monitor here (model: monitor row from **Model Allocation** table in `.omp/agent-config.md`).

**The supervisor (item 5.5.1)** runs distinct from monitor (monitor: deterministic state archival; supervisor: heuristic observation). OQ-9 (consolidation) is deferred pending real telemetry.

The supervisor is **not** a long-lived daemon and needs **no** agent-messaging. The orchestrator drives it by spawning a fresh, short-lived check per cadence tick (below); each spawn does exactly one check for one agent and exits, with continuity persisted on disk in `agent_states/supervisor/state.md`. This is what makes supervision work in environments without the irc tool / agent-teams.

**Skip the supervisor entirely** when the task file has fewer than `skip_supervisor_if_total_subtasks_lt` sub-tasks (Per-phase skip flags in `.omp/agent-config.md`, default 3) — observation overhead exceeds value on small task lists. Log the skip as `SUPERVISOR_HEALTH status:disabled spawns:0 stalls:0 heartbeat:none disabled_at:[ts] reason:skip-flag` so the run report reflects it.

**Cadence — when to spawn a check.** No messaging required; it's control-flow driven. The orchestrator spawns a `CHECK <agent-id>` at these triggers:
1. **On wave boundary** — after spawning a parallel wave, and each time control returns from a completing background agent, spawn a check for every *still-active* agent-id. This catches mid-run `spiral` / `stall` / `drift` while other agents keep working.
2. **On agent completion** — when a Phase-3 implementation agent returns, before omp merges its task branch, spawn a final check for that agent-id (catches `shallow` / `drift` on the finished output).

Each check is a short **foreground** spawn: the orchestrator waits for the one-line summary, then drains any escalations via `irc(op: "inbox")` and acts on `pause-request` / `depth-recommendation` per the escalation ladder (5.5.4). Maintain a `supervisor_checks` counter and a `supervisor_check_failures` counter in cycle state — they feed the run report and the health watchdog below.

```
task(agent: "supervisor", context: "CHECK [agent-id]. One check per spawn.",
  tasks: [{ id: "supervisor-<tick>", role: "Supervisor check",
    assignment: "CHECK [agent-id]. Feature: [name]. Cycle state: agent_states/cycle-state-[name].md. Agent ID convention: <role>-<task-number>. Do exactly one check per supervisor.md, then exit." }])
```

The supervisor sends whispers via `irc` to implementation agents and escalations via `irc` to the orchestrator. It writes `agent_states/supervisor/state.md` (ladder state) and touches `agent_states/supervisor/heartbeat`. It reads the agent's omp session transcript (`history://<agent-id>`) and `agent_states/cycle-state-*.md`.

**Artifact layout (Phase 3):**

```
agent_states/
  cycle-state-<feature>.md       # orchestrator writes inline (monitor if agent_messaging)
  supervisor/state.md            # supervisor writes (ladder + last_check)
  supervisor/heartbeat           # supervisor touches
```

Whispers and escalations travel via irc — no file artifacts. Agent transcripts (`<id>.jsonl`) live in the omp artifacts dir.

### 3.2 — Dependency analysis

Classify parent tasks: **independent** (start now) or **dependent** (wait for prerequisite).
Classify sub-tasks by type → assign agent per the delegation table in 3.3.

Present analysis in dry-run mode. In `--exe` mode, proceed.

### 3.3 — Spawn agents

Before spawning any implementation agent:

1. **Extract file paths** from the task file's "Relevant Files" section — pass these per-agent in each `assignment`.
2. **Extract AC** from the PRD's Acceptance Criteria section — write to `local://ac.md`. Test and verify agents read it; implementer reads it.
3. **Run Context Sources retrieval** for stage `implement` once per parent task — write results to `local://ctx-sources.md`. Implementer and test agents reference it.
4. **Write `local://prd.md`** with the PRD path + feature description. Any agent that needs PRD context reads it.

#### Parallel task waves (batch mode)

For **independent** parent tasks, spawn them as a batch — one `task` call with a `tasks[]` array. Each item gets its own `id`, `role`, `assignment`, and `isolated: true`. The `context` field is left minimal (omp requires it for batch mode but it raw-injects into every system prompt — keep it to a one-liner). Shared background lives in `local://` files that each agent reads on demand:

```
task(
  agent: "<kind-agent>",        // scaffold, ui-story, coding, or task
  context: "Read local:// files referenced in your assignment for shared context.",
  tasks: [
    { id: "scaffold-1.0", role: "Scaffold engineer (task 1.0)", isolated: true,
      assignment: "Sub-tasks: [list]. Relevant files: [paths]. Read local://prd.md and local://ac.md for PRD context. Read local://digest-1.0.md if it exists. Read local://ctx-sources.md for context-source data." },
    { id: "coding-2.0", role: "Software engineer (task 2.0)", isolated: true,
      assignment: "Sub-tasks: [list]. Relevant files: [paths]. Read local://prd.md and local://ac.md. Read local://digest-2.0.md if it exists. Read local://ctx-sources.md." },
    ...
  ]
)
```

The session semaphore bounds concurrency. Each isolated agent gets its own workspace from the feature-branch HEAD; omp merges each task branch when the agent completes.

For **dependent** tasks, wait for the prerequisite's isolated agent to complete and omp to merge its branch, then spawn the dependent task (it forks from the updated HEAD automatically).

#### Per-task agent sequence

For each parent task (whether batched or sequential), the sequence is:

1. **Pre-digest** (haiku, background job) — default for any task touching ≥ `skip_predigest_if_files_lt` existing files (default 2). Spawn all independent tasks' pre-digests as parallel background jobs, then collect via `job poll`:
   ```
   task(agent: "task", context: "Read source files and return a structured summary.",
     tasks: [{ id: "predigest-1.0", role: "Pre-digest (task 1.0)", assignment: "Files: [paths]. Return ~150-line summary: public API, constructor deps, key patterns. Dense — no prose." },
             { id: "predigest-2.0", role: "Pre-digest (task 2.0)", assignment: "Files: [paths]. ..." }])
   ```
   Collect each via `job poll` when its implementation agent is ready. Write the digest to `local://digest-<task-number>.md`. The implementation agent's `assignment` references it.

2. **Implement** — dispatch by the parent task's `[kind: …]` tag:

   | `kind` value | agent |
   |---|---|
   | `scaffold` or `scaffold-*` | `scaffold` |
   | `ui-story` | `ui-story` |
   | `test` | `test` |
   | `coding` | `coding` |
   | `task (generic)` | `task` |

   Each implementation agent spawns with `isolated: true`, `id: "<kind>-<task-number>"`, `role: "<role> (task <task-number>)"`. The `assignment` carries the sub-task list, relevant files, and `local://` file references. The agent reads only what it needs.

   For `scaffold-*` kinds, pass the pattern name in the `assignment` so the agent loads `.claude/agents/scaffold/<pattern>.md`.

   - Agent marks sub-tasks `[x]` as it completes them
   - On failure/ambiguity: report to orchestrator, continue independent sub-tasks
   - omp merges the task branch into the feature branch on completion

3. **Pre-flight** (haiku, after implementer merges, before test agent). Skip when `skip_preflight_if_no_existing_tests` is `true` and grep of the **Test path glob** for any public symbol the implementer touched returns no hits. The pre-flight agent needs ONLY changed source files + base ref — no shared context files:
   ```
   task(agent: "test-preflight", context: "Classify existing tests for changed symbols.",
     tasks: [{ id: "preflight-<task-number>", role: "Pre-flight classifier (task <n>)", isolated: true,
       assignment: "Changed source files: [paths]. Base ref: feature/[name]." }])
   ```
   The classifier returns a `## Existing test classifications` table. Lift it into the test agent's `assignment`.

4. **Test** (separate agent from implementer; gets a fresh isolated workspace from the updated feature-branch HEAD after the implementer's merge). The test agent reads `local://ac.md` and `local://ctx-sources.md` but does NOT need the digest:
   - **Write**: `task(agent: "test", context: "Write tests for the implemented feature.", tasks: [{ id: "test-<n>", role: "Test engineer (task <n>)", isolated: true, assignment: "Source files: [paths]\nTest files: [paths]\nTask: [desc]\nRead local://ac.md for AC. Read local://ctx-sources.md for context-source data.\n[pre-flight table]" }])`
   - **Fix**: re-spawn `test` agent with failure output and source paths

### 3.4 — Handle results

- **Success**: capture the agent's `## Deviations` section — forward each to monitor (`DEVIATIONS [task-id] AC [ac-id]: [what] | reason: [why]`). omp has already merged the task branch into the feature branch (branch-mode merge on isolated agent completion). Run the **Run all tests** + **Analyze / lint** commands (§ Project Commands) to verify the merge is clean. Send status to monitor.
- **Failure**: escalation ladder (below)
- **Contradiction-exit** (agent's return contains `status: contradiction-exit` per the `contradiction-exit` skill — item 5.4.4): emit `RESCUE contradiction-loop [task-id]: [trigger value] | resolution: human escalation | artifact: [report path or "agent return"]` to monitor, then jump to **L4** immediately. Do **not** run the escalation ladder for L1–L3 — the agent already exhausted its retries by construction. Preserve the structured block verbatim in the user-facing message.
- **Stalled** (agent killed by the harness watchdog, or returns no clean result): run **Stall salvage** (below), then the escalation ladder using the salvage assessment as context
- **Blocked**: notify user, continue independent tasks

### Supervisor cadence (5.5.4)

**Under omp (default):** the task tool's async job progress and the agent registry status (`running` / `idle` / `parked`) replace the counter files. At your watchdog tick (and at each sub-task boundary), check `irc(op: "list")` for live agents. For each agent that has been `running` long enough to exceed the cadence threshold (default 5 tool calls — approximate via transcript length: read `history://<agent-id>` and count tool-call entries), spawn a supervisor check:
  ```
  Spawn the `supervisor` agent (model tier: [supervisor row from Model Allocation] — resolve through Model Versions, pass the concrete model id, id: "supervisor-<tick>") with this prompt:
  > CHECK <agent-id>. Feature: [name].
  ```
- After spawn returns, drain any escalations via `irc(op: "inbox")`.
- **Skip cadence checks entirely if supervisor health Status is `disabled`** (degraded mode — see below).

Supervisor spawns are fresh per check — continuity lives in `agent_states/supervisor/state.md`. The escalation channel below is how the supervisor signals back to you.

**Claude Code fallback:** the PostToolUse hook increments a per-agent counter at `agent_states/counters/<agent-id>` on every tool call. Read all counter files; for each agent-id whose counter ≥ `cadence_n` (default 5), spawn a supervisor check. Reset the counter to `0` after.

### Supervisor health (5.5.5)

Six layered mechanisms, evaluated as you spawn and collect each check (the cadence above):

1. **Last-check record (not a liveness watchdog).** The supervisor touches `agent_states/supervisor/heartbeat` at the end of every successful check. Because checks are intermittent *by design*, a stale heartbeat is **not** an outage signal — never treat heartbeat age as "offline." Record the heartbeat mtime as the supervisor's `last_check` for the run report. Liveness is judged per-check by mechanism 2.
2. **Per-check spawn watchdog.** When you spawn a `CHECK <agent-id>`, treat the spawn as failed if it errors or does not return a summary within 30s. Increment `supervisor_check_failures`, emit `RESCUE supervisor-stall [supervisor]: check [agent-id] no return in [N]s | resolution: skip-or-disable | artifact: agent_states/supervisor/state.md` to monitor, and skip this tick's result.
3. **Rescue logging on outage.** Already provided by (2) — `supervisor-stall` is in the rescue type enum.
4. **Circuit breaker.** Maintain the **Supervisor health** section in cycle state (via monitor's `SUPERVISOR_HEALTH` verb). If `supervisor_check_failures` increments 3 times within a 5-minute window, **disable** the supervisor for the rest of the cycle: emit `RESCUE supervisor-disabled [supervisor]: 3 check failures in 5m | resolution: degraded mode | artifact: cycle-state` and forward `SUPERVISOR_HEALTH status:disabled spawns:[n] stalls:[n] heartbeat:[last] disabled_at:[now] reason:circuit-breaker`. Stop spawning supervisor checks; the cycle continues in degraded mode (no whispers, no escalations — falls back to today's behavior).
5. **Run-report check success rate.** When you build the cycle run report at Phase 4A, populate the **Supervisor health** subsection of the Agent Telemetry block from cycle state: `supervisor_checks` attempted, `supervisor_check_failures`, and success rate. Classify the cycle as **degraded** if success rate < 90% or status is `disabled`.
6. **`self-improve` hook.** Documented in `.omp/agents/self-improve.md` Step 2 (Effectiveness patterns → Supervisor health). When `supervisor-stall` or `supervisor-disabled` appears in ≥ 3 of the last 5 cycles, `self-improve` raises a P0 recommendation.

### Plan-revision flow (5.5.6)

When you process a `depth-recommendation` escalation, you decide — the supervisor only *recommends*. Three rules:

1. **Decide accept or reject** with a one-line rationale grounded in current cycle context (task progress, AC scope, escalation ladder state, time pressure). Examples: "accepted — task 2.0 has 3 unrelated sub-tasks per Relevant Files," "rejected — split would create cross-cutting test dependencies," "rejected — too late in Phase 3 to re-shape."
2. **Emit `SUPERVISOR_REC suggestion:[text] accepted:[true|false] rationale:[text]` to monitor** for every recommendation — accepted *and* rejected. Silent drops destroy the audit trail and starve `self-improve` of tuning data.
3. **If accepted, apply the change** within your existing primitives — re-spawn a task with a different model, split a parent task into two task-file entries, insert a verify pass, etc. The recommendation is not a pipeline-design override; the orchestrator still owns pipeline shape.

If a recommendation conflicts with a recommendation you accepted earlier (or with mid-cycle scope changes), prefer the later signal but record both decisions.

### Supervisor escalation polling

The orchestrator collects supervisor escalations at three moments only (item 5.5.2):
1. **Phase transition** — end of Phase 3, before spawning verify/review.
2. **Sub-task boundary** — after each parent task's Commit protocol, before spawning the next.
3. **After each supervisor check** — you've just collected a check's result (see 5.5.5: per-check spawn watchdog + circuit breaker), so drain any escalations it emitted.

**Under omp (default):** drain your irc inbox at each moment — `irc(op: "inbox")` returns all pending escalation messages from the supervisor. No cursor tracking needed (messages are consumed on read). See the `escalations` skill § Transport for the per-type handling (`pause-request` → recovery decision + `RESCUE`; `depth-recommendation` → log decision in cycle state; `bug-pattern` → log + surface in run report). For time-sensitive `pause-request` handling at watchdog ticks, `irc(op: "wait", from: "supervisor-<tick>", timeoutMs: 30000)`. Never block mid-tool-call.

**Claude Code fallback:** poll `agent_states/escalations.jsonl` with a per-cycle `escalation_cursor:` field tracking the last processed line.

**Agent-ID stamp.** Every Phase-3 implementation agent must be spawned with `id: "<role>-<task-number>"` (e.g., `id: "test-3.0"`, `id: "ui-story-2.1"`) in the task spawn. Under omp, this `id` field sets the child session's agentId — it becomes the irc address (supervisor sends whispers via `irc(op: "send", to: "test-3.0", …)`), the registry key, and the artifact filename (`test-3.0.jsonl`, `test-3.0.md`). The supervisor reads the agent's omp session transcript (`history://test-3.0` for concise view, or the `<id>.jsonl` artifact for full tool-call detail) instead of a hook-written event log. Under Claude Code, the PostToolUse hook routes events into `agent_states/events/<agent-id>.jsonl` — pass the agent-id in the spawn prompt text since Claude Code's Agent() call has no `id` field.

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
task(agent: "task", context: "Salvage only what is recoverable — do NOT redo its work.",
  tasks: [{ id: "salvage-<agent-id>", role: "Salvage pass",
    assignment: "The [agent role] agent for [task/feature] stalled. Inputs: [partial report path if any] and the git state (run git diff [base] and git log). Produce a PARTIAL — agent stalled artifact at [path]: record what completed, mark what is missing, assess whether the result is coherent. Return the artifact path." }])
```

Send `RESCUE stall [agent-id]: [agent role] stalled before finishing | resolution: ran Haiku salvage | artifact: [salvage report path]` to monitor. Then: for a stalled `verify`/`review`, the `PARTIAL` report feeds the 4A gate; for a stalled implementation agent, proceed via the escalation ladder with the salvage assessment as the "what was attempted" context.

### Bug tracking

Existing-code bugs (not agent-written code):
1. Log in `documentation/bugs.md` (next BUG-NNN ID)
2. Note in cycle state
3. Don't fix unless blocking. If blocking: fix, move to `bugs_resolved.md`.

### Commit protocol

Per parent task, when all sub-tasks pass:
1. **Clean-check** — assert `git status --porcelain` in the main checkout is empty. The orchestrator writes no implementation code, so a dirty main checkout means something leaked: abort, report to the user.
2. Run test + typecheck/lint commands (from **Project Commands** in `.omp/agent-config.md`) in the main checkout (omp has already merged the task branch).
3. **Silent-skip gate** — grep the diff of test files (`git diff [base]...HEAD -- '<test-glob>'`, where `<test-glob>` is the **Test path glob** from `.omp/agent-config.md` § Project Commands) for the regex patterns in the active pack's **Test anti-patterns** file. Any hit blocks.
   On hit: emit `RESCUE silent-skip [task-id]: [file:line + pattern] | resolution: re-spawn test agent | artifact: none` to monitor, then re-spawn the `test` agent (isolated) with the offending file + matched pattern. One retry; a second hit escalates per L3.
4. Green and gate clean → mark parent `[x]`, update monitor. omp has already merged the task branch and cleaned up the workspace — no manual `git worktree remove` or `git branch -D` needed.
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
3. Schedule auto-resume — under **Claude Code** use `CronCreate` (durable, one-shot, offset from round marks); under **omp** there is no built-in scheduler, so resume manually with `/cycle --exe agent_states/cycle-state-[name].md`
4. Report to user: what's done, resume point, manual fallback command

---

## Phase 4 — Completion

Two parts: **4A** runs immediately with no user interaction. **4B** runs when the user returns after verify/review (or says to proceed now).

### 4A — Wrap-up (MANDATORY — execute immediately, do not stop or ask; step 7 MUST execute even if the user skips 4B)

1. Run test + typecheck/lint commands from **Project Commands** in `.omp/agent-config.md` (final full suite). **Analyzer drift check (5.8.1):** if `analyzer_baseline` is `soft_warn` or `hard_fail_if_exceeded`, diff the current analyze output against `cycle_reports/<feature>/analyzer-baseline.txt` recorded at Phase 3 start. Append the diff (or "None") to the run report's `## Analyzer drift` section. Under `hard_fail_if_exceeded`, force the review verdict to REQUEST CHANGES if the diff is non-empty.
2. Mark ALL tasks and sub-tasks `[x]` in the task file (final sweep)
3. Generate cycle report → `cycle_reports/[feature-name]-[YYYY-MM-DD].md`:
   - Summary (what was implemented, per parent task)
   - Branch name, commits (hash + message), database/schema changes (or "none")
   - Bugs discovered, known limitations, blocked tasks, follow-up items
   - Deviations from PRD AC (copy the cycle state's **Deviations** section verbatim; write "None" if empty)
   - Scope changes (copy the cycle state's **Scope changes** section verbatim; write "None" if empty)
4. Present cycle report to user inline
5. Generate run report → `agent_tasks/reports/report-prd-[feature-name]-[YYYY-MM-DD].md` using template `.claude/skills/cycle/report-template.md`. **Agent Audit**, **Rescues**, and **Agent Telemetry** sections are required. Copy the **Rescues** list from the cycle state file verbatim into the run report's `## Rescues` section (write "None" if cycle state has no rescues). For Agent Telemetry, read all files in `agent_states/events/` and aggregate one row per `agent_id` — fields: `agent_type`, tool-call count, breakdown by `tool`, error count (`exit:error`), wallclock (last `ts` − first), and `stop_reason` from any `subagent_stop` line. If `agent_states/events/` is empty or missing, write *"Telemetry not collected — enable hooks per README."* in place of the table. If >10 reports exist, summarize oldest into `agent_tasks/agent_metrics.md`.
6. **Autonomous verify & review** — read `.omp/agent-config.md` Optional Agents section.

   **Mode override:** in `--mode hotfix`, **skip the review spawn entirely** and spawn only `verify` at **lite** depth (see 5.6.6). In `--mode lean` and `--mode full`, behave as below.

   **Skip flag:** when `skip_review_if_files_lt` (Per-phase skip flags in `.omp/agent-config.md`, default 0/off) is > 0 and `git diff [base] --name-only | wc -l` is below it, also skip review. Note the skip in the run report's Agent Audit (`review: skipped — files changed N < threshold M`).

   If both are enabled, issue the two `Agent` calls in a **single message** so they run concurrently — verify and review share no state and must not gate each other.

   Run **Context Sources retrieval** for stages `verify` and `review` (see § Context Sources retrieval) and prepend any `## Context: <id>` blocks to the respective prompts below.

   **Compute verify depth (5.6.6).** Before spawning verify, gather the inputs from cycle state and the git diff:
   - `files_changed_count` = `git diff [base] --name-only | wc -l`
   - `test_files_touched` = any changed path matches the **Test path glob** (`.omp/agent-config.md` § Project Commands)
   - `domain_or_migration_files_touched` = any changed path under a domain/data layer (per `.omp/agent-config.md` § Layer Boundaries) or matches `**/migrations/**`
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

   If `verify` is **enabled**: spawn the `verify` agent (not isolated — reads the main checkout):
   ```
   task(agent: "verify", context: "Audit AC coverage for the implemented feature.",
     tasks: [{ id: "verify", role: "AC auditor",
       assignment: "Source files: [paths]. Test files: [paths]. Branch: [branch-name]. Depth: <lite|standard|deep>. Read local://ac.md for AC. Read local://prd.md for PRD context. Report path: agent_tasks/reports/verify-[prd-stem]-[date].md — write your report there. Work autonomously." }])
   ```

   If `review` is **enabled**: spawn the `review` agent (not isolated — reads the main checkout):
   ```
   task(agent: "review", context: "Review code quality and architecture adherence.",
     tasks: [{ id: "review", role: "Code reviewer",
       assignment: "Branch: [branch-name]. Read local://prd.md for PRD context. Report path: agent_tasks/reports/review-[feature]-[date].md — write your report there. Work autonomously." }])
   ```

   Verify and review can be spawned as a single batch call (two items, minimal `context`) since they run concurrently. Each reads `local://` files on demand.

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

7b. **Vault sync** — if `vault_root` (§ Docs Vault in `.omp/agent-config.md`) is non-empty, commit and push the vault repo so this cycle's reports reach its remote (e.g. `myapp-docs`). Orchestrator-run — the finalize monitor holds only `rm agent_states/*`, not git. **Best-effort: a vault push failure must not fail the cycle.**

   ```
   git -C "{vault_root}" add -A
   git -C "{vault_root}" diff --cached --quiet || git -C "{vault_root}" commit -m "cycle {feature}: reports ({app_slug})"
   git -C "{vault_root}" push || echo "vault push failed — reports are committed locally in the vault; push manually."
   ```

   If `vault_root` is empty, skip — reports are committed to the app repo as usual (backward-compatible default).

**4A is not complete until steps 1–7 are done (plus 7b when a vault is configured). Do not skip any step.**

### 4B — Release (after gate passes; user confirmation required for PARTIAL)

8. Push branch, `gh pr create` targeting the `pr_target` from `.omp/agent-config.md`
9. Update roadmap (skip if cycle didn't originate from a roadmap story):
   - `documentation/ROADMAP.md`: set story Status to `DONE` in Story Index
   - Move story's full section to `documentation/roadmap_completed.md` under the appropriate Phase heading. Mark all AC `[x]`.
10. Append changelog entry to `documentation/CHANGELOG.md`

