# Orca ↔ agent-sdlc Synergy — Handoff Findings

> **Status:** carry-over from an exploratory conversation about the Orca app.
> **Date:** 2026-05-22
> **Purpose:** seed a cross-analysis. The session that picks this up should read
> this alongside `improvement-synthesis-final.md` (especially §5.5 supervisor and
> §5.6 cycle modes) and produce a synergy plan that slots into the existing
> themed plan in §5.

---

## 0. The one constraint that governs everything

`agent-sdlc` deploys as a `.claude/` folder copied into arbitrary projects
(see repo `CLAUDE.md` → "Deployment"). It **must keep working without Orca.**

Therefore every synergy idea below is an **optional enhancement tier**: a
detect-Orca-and-augment layer, never a hard dependency. The framework's
file-based mechanisms stay as the portable baseline; Orca primitives, when
present, back or surface them. Treat "degrades gracefully when `orca` is absent"
as an acceptance criterion for every item.

---

## 1. What Orca is (brief)

An agentic development environment: an Electron app + a headless runtime + an
`orca` CLI control plane. It manages **repos, worktrees, terminals, scheduled
automations, and multi-agent orchestration**. Agents drive it through the same
`orca` CLI a human uses.

## 2. Orca primitives relevant to this framework

- **Worktrees** — `orca worktree create/set/ps`. Each carries an
  agent-writable `--comment` status field shown live in the Orca UI.
- **Terminals** — `create/read/send/wait`. `terminal wait --for tui-idle`
  natively detects a coding agent's working→idle transition (OSC title).
- **Orchestration** (`orca orchestration`, experimental feature):
  - *Messaging* — SQLite-backed mail store, push-on-idle delivery. Message
    types: `status`, `dispatch`, `worker_done`, `merge_ready`, `escalation`,
    `handoff`, `decision_gate`. Group addresses (`@claude`, `@idle`,
    `@worktree:<id>`).
  - *Tasks* — DAG with `deps`; statuses `pending → ready → dispatched →
    completed | failed | blocked`. Completing a task auto-promotes dependents.
  - *Dispatch* — assigns a ready task to a terminal; `--inject` sends a
    preamble teaching the worker to report back via `worker_done`. Circuit
    breaker: 3 consecutive failures → task `failed`.
  - *Decision gates* — `gate-create` / `gate-resolve`: human-in-the-loop
    checkpoints that block a task until resolved.
  - *Coordinator* — `orchestration run`: a background loop that dispatches
    ready tasks and processes `worker_done`/`escalation`. Phases:
    `decomposing → dispatching → monitoring → merging → done`.
- **Automations** — scheduled prompts (cron / RRULE), either a fresh worktree
  per run or an existing worktree.

## 3. The two-worktree-layer reality

- `/cycle` Phase 3 spawns implementation agents with
  `Agent(isolation: "worktree")` → Claude Code worktrees nested under
  `.claude/worktrees/`. Orca **sees** these in `worktree ps` but does **not**
  manage their lifecycle — `/cycle`'s orchestrator does.
- An Orca worktree is the durable, UI-visible *feature* home; the agent
  worktrees are short-lived sub-task scratch space inside it.
- Any synergy must respect that `/cycle` owns the inner layer. Orca owns the
  outer feature worktree.

---

## 4. Cross-analysis seeds (the actual work)

Each item names the friction found and the synthesis section to reconcile it
against.

### A. Interactive gates vs. unattended runs — reconcile with §5.6

`/cycle` Gates 1C, 2B, 4B are terminal prompts. Any automation or unattended
run **parks** at Gate 1 waiting for a human. Orca already has a first-class
decision-gate primitive (`orchestration gate-create` / `gate-resolve`) that
blocks a task and is resolvable asynchronously from the Orca UI.

Question: should `/cycle`'s gates optionally become Orca decision gates, so
approval is async and UI-driven instead of blocking a terminal? This dovetails
with §5.6.3 (gate consolidation in lean mode) and §5.6.1's `hotfix` mode (gates
skipped). A `hotfix`/no-gate mode is exactly what an unattended automation
needs.

### B. The §5.5 supervisor vs. Orca orchestration — the big one

§5.5 designs a Haiku sidecar supervisor with **file-based channels**:
`agent_states/events/*.jsonl`, `whispers/*.md`, `escalations.jsonl`, heartbeat
files, per-check watchdogs, a respawn circuit breaker.

Orca orchestration **already provides** much of this shape: an `escalation`
message type, a coordinator loop, `worker_done` completion signals, a dispatch
circuit breaker (3 failures), and native idle detection. Mapping:

| §5.5 mechanism            | Orca equivalent                              |
|---------------------------|----------------------------------------------|
| `escalations.jsonl`       | `orchestration send --type escalation`       |
| orchestrator poll moments | `orchestration check --wait --types ...`     |
| agent completion          | `worker_done` message                        |
| respawn circuit breaker   | dispatch circuit breaker (3 failures)        |
| heartbeat / watchdog      | `terminal wait --for tui-idle` (see E)       |

Cross-analysis: decide how much §5.5 plumbing collapses onto Orca primitives
**when Orca is present**, while keeping the file-based channels as the portable
fallback (per §0). The whisper channel (supervisor→agent advisories) has no
clean Orca analog — `orchestration send` is the closest but whispers are
poll-between-subtasks, not push-on-idle. Likely whispers stay file-based either
way.

### C. Worktree comment as live cycle status — likely a Tier-0 quick win

`/cycle`'s monitor maintains `agent_states/cycle-state-*.md` (internal). Orca's
worktree `--comment` is the **UI-visible** status field. The orchestrator (or
monitor) calling `orca worktree set --comment` at phase transitions would
surface live cycle progress in the Orca UI with zero behavior change and full
graceful degradation. Lowest-risk synergy — good first deliverable / canary.

### D. Automations as a `/cycle` entry point — reconcile with §5.6

Caveats found while wiring real automations:
1. `cycle/SKILL.md` has `disable-model-invocation: true` → an automation's
   prompt must be a **literal** `/cycle …` slash command, not prose.
2. The automation prompt is **static** — it cannot pick "the next story."
3. Unattended runs **park** at the first gate (see A).

§5.6's `lean`/`hotfix` modes + gate consolidation would make scheduled cycles
genuinely viable. Relates to synthesis Open Question 3 ("platform spike for
direct slash → agent invocation").

### E. `terminal wait --for tui-idle` vs. §5.5.5 heartbeats

§5.5.5 builds heartbeat files + per-check watchdogs to detect a stalled
supervisor/agent. Orca's `terminal wait --for tui-idle` already detects the
working→idle transition natively. When running under Orca, idle detection could
back the watchdog layer instead of polling touch-files.

### F. Telemetry (§5.2) vs. Orca automation run history — minor

Orca's `automations runs` keeps per-run history/outcomes. §5.2's telemetry
event log is richer and project-local; note the small overlap, don't over-index
on it.

---

## 5. Artifacts created during the exploratory session

- **Two Orca automations on the Ocelot repo, both DISABLED:**
  - A — `b12b77e5-606b-4b5d-a0ad-9552daa0783f` — prompt `/cycle 2.1.4`, daily 06:30
  - B — `9d118f13-267f-4fff-83e3-4ad2598b5b84` — prompt `/create-prd 2.1.4`, weekdays 06:00
- **This worktree** — `echo/orca-synergy` in the `agent-sdlc` repo, branched
  from `develop`. The `docs/` improvement drafts were untracked in the main
  checkout and have been copied in and committed here so this branch carries
  the full corpus.

## 6. Suggested next steps for the picking-up session

1. Read this doc + `improvement-synthesis-final.md` §5.5, §5.6, §10.
2. Lock the framing: Orca synergy as an **optional enhancement tier** that
   degrades gracefully (per §0).
3. Produce a synergy addendum that slots into the §5 themed plan — most likely
   annotations on §5.5/§5.6 plus one new low-tier item for §4.C.
4. Start with §4.C (worktree-comment status) as the canary: additive, no
   behavior change, easy to verify.
