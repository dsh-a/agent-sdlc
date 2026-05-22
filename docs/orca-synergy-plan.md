# Orca ↔ agent-sdlc Synergy Plan

**Date:** 2026-05-22
**Status:** Draft — dialogue rounds 1–4 + live `orca` CLI probes (worktree + orchestration) incorporated. Slots into `improvement-synthesis-final.md` §5 as a new §5.9 + annotations.
**Inputs:** `orca-synergy-findings.md` (seeds A–F), `improvement-synthesis-final.md` (§5.5, §5.6, §10)

Answers three questions:

1. How to integrate Orca into the agent-sdlc framework.
2. How to leverage Orca's features from inside the framework.
3. Whether — and how — to separate the Orca improvements from the non-Orca improvements.

The framework must keep working without Orca (findings §0). Every Orca item here is
an **optional augment layer** over a portable file-based baseline. The baseline (the
synthesis §5.1–§5.8) is never behind a flag — it is always on. The flag governs only
the augment layer.

---

## 1. Framing

`agent-sdlc` ships as a `.claude/` folder copied into arbitrary projects. Orca is
present or it is not. The framework detects this once per cycle and is otherwise
indifferent. "Degrades to baseline when `orca` is absent" is an acceptance criterion
for every Orca item.

---

## 2. The altitude question (the core decision)

This is the decision everything else hangs on, and dialogue round 1 settled it.

### 2.1 What "feature" means — precision the framework supplies, not Orca

Orca's structural intent treats a worktree's "feature" as amorphous: a relatively
decoupled unit, but not otherwise defined. agent-sdlc does not have to accept that
vagueness. The framework already has a **precise** definition available:

> **A feature = one ROADMAP story = one PRD = one `/cycle` run = one Orca worktree.**

ROADMAP.md + `/cycle --next` (see P6) are what *impose* that precision on Orca. Orca
supplies the durable, UI-visible container; the framework supplies the discipline
that one container holds exactly one story. The user does not adopt Orca's amorphous
"feature" — the user overwrites it with the framework's.

### 2.2 The bundling problem: context isolation ≠ filesystem isolation

`/cycle`'s value is **process decoupling via subagent context**: each Phase-3
subagent gets fresh context, the primary session stays lean. That value comes from
*context* isolation.

Today, `Agent(isolation: "worktree")` welds two separate things together:

| Isolation kind | What it buys | Cost | When actually needed |
|---|---|---|---|
| **Context** | fresh context per subagent; lean primary session | cheap | **always** — this is the point of `/cycle` |
| **Filesystem** (a nested worktree) | parallel agents don't race the working tree | a worktree in the Orca sidebar | only when agents run **in parallel** |

In a Flutter/codegen project, parallel agents *do* race — shared `.dart_tool/`,
`build_runner` outputs, the git index. So filesystem isolation is needed **whenever
agents run concurrently**, not whenever there are multiple tasks. The worktree count
is therefore governed by **degree of parallelism**, not task count.

### 2.3 Resolution: elastic inner worktrees — not flat, not unbounded

Three models were on the table:

| Model | Shape | Verdict |
|---|---|---|
| **Nested, unbounded** (today) | Orca worktree per feature; `/cycle` worktree per task | sidebar explosion: `cycles × (1 + tasks)` |
| **Flat** | `/cycle` subtasks become Orca worktrees, same level as features | **Rejected.** Breaks findings §3 ownership; makes Orca's "feature" UI unit a scattered set — *amplifies* the amorphousness the user wants gone |
| **Nested, bounded** (chosen) | Orca worktree per feature; `/cycle` nests worktrees but caps live concurrency at K | **Chosen.** Two altitudes kept; inner altitude's *peak width* is a declared number |

The lever is a concurrency cap, **`max_parallel_agents`** (new core config knob,
placeholder per Principle 2):

| Level | K | Notes |
|---|---|---|
| `off` *(initial default)* | unbounded | today's behavior — spawn the whole wave; no queue, no orchestrator change |
| `high` | 4 | maps from cycle mode `full` |
| `medium` | 2 | maps from `lean` |
| `low` | 1 | maps from `hotfix` — single agent in the feature worktree, no nested worktree |

**Decision (dialogue): ship with `K = off`.** Early experimental Orca+`/cycle` runs
keep today's unbounded wave-spawn — no dispatch queue, no orchestrator change — so
the experiment can start immediately and we *observe* what the worktree footprint
actually looks like before optimizing it. Finite K is a **deferred optimization**,
not Milestone-1 work.

When finite K *is* enabled later: cycle mode sets the level, an explicit
`--max-parallel-agents` overrides, and under fan-out K is clamped to `medium`.
Sidebar clutter then becomes predictable arithmetic: `cycles × (1 + K)` — and P9's
lineage adoption collapses even those under one node per cycle regardless of K.

**Why deferred — the risk that makes it not-free.** Finite K changes Phase-3
dispatch from "spawn the whole wave" to "spawn ≤K, queue the rest, refill on
completion." That is a real orchestrator change — it interacts with wave
dependencies (`SKILL.md` §3.2), the `monitor`'s task tracking, the per-agent
watchdog, and the supervisor's event window. It must be validated against the
existing `/cycle` Phase-3 loop, not bolted on. See SQ-8. Shipping `K = off`
sidesteps all of it.

**This is the happy medium the dialogue asked for.** Context isolation stays
universal (the point of `/cycle` is untouched). Filesystem isolation becomes
*bounded and declared* instead of emergent. The two altitudes stay distinct — which
is what keeps "feature" precise — but the inner one is elastic.

Two supporting moves:
- **Name inner worktrees with the story id as prefix** (`2.1.4/task-3`) so Orca's
  sidebar groups them visually under their parent feature worktree.
- `max_parallel_agents` and cycle mode are **Orca-agnostic** — they are good
  hygiene regardless. Orca only makes their effect *visible* and gives a concrete
  reason to tune K down.

### 2.4 Consequence for the §5.5 supervisor (findings seed B)

The findings doc seed B proposes collapsing the §5.5 supervisor's file-based
plumbing onto Orca orchestration primitives. **Declined**, confirmed in dialogue.

The §5.5 supervisor is an *observer* operating **inside one cycle**; Orca
orchestration is a *dispatcher* operating **across features**. Different altitudes
(§2.3). The shared vocabulary (`escalation`, `worker_done`, circuit breaker) is
coincidental naming, not shared mechanism. Adopting seed B would admit an
experimental Orca subsystem into the framework's most load-bearing inner loop.

**The inner control loop — orchestrator, monitor, supervisor, whispers,
escalations, event logs — stays file-based and Orca-agnostic, exactly as the
synthesis §5.5 designs it.** Orca's role is the *outer* level (fan-out, P3) plus
visibility, gates, idle detection, and message *delivery* at the inner level. Orca
rings doorbells; the files remain the channels.

### 2.5 Side-finding: monitor vs. supervisor — one cycle sidecar, not two

Surfaced in dialogue. Today `monitor` (Haiku, background) transcribes orchestrator
status messages into `cycle-state-*.md` and, on `FINALIZE`, archives state and
deletes `agent_states/`. It does **not** write the cycle report or run report — the
orchestrator does that itself (`SKILL.md` 4A). The synthesis §5.5 adds a *second*
Haiku background agent — the supervisor — with its own `state.md`, heartbeat, and
six health-monitoring mechanisms (§5.5.5).

Two observations:

- **The crash-durability case for a separate `monitor` is weak.** The orchestrator
  writing `cycle-state-*.md` itself is equally crash-durable — the write happens
  before the crash either way. `monitor`'s real and only justification is
  **orchestrator context hygiene**: keeping a growing state file out of the
  expensive opus orchestrator's context. Modest but real — so "just let the
  orchestrator do it" is *not* the answer; it re-imports context bloat into the most
  expensive agent and cuts against the synthesis's closed-loop thesis (the
  orchestrator emits signal, it does not self-report into its own context).
- **Two cheap Haiku background observers is one too many.** Once §5.5 lands the
  framework health-monitors two sidecars. `monitor`'s transcription job is purely
  mechanical — no judgment, no source reads — so it does **not** violate the §5.5.1
  narrow-scope rule. The clean move is to **fold `monitor` into the supervisor**:
  one "cycle sidecar" with two responsibilities — observe event logs →
  whispers/escalations, *and* transcribe orchestrator status → `cycle-state-*.md`.
  One heartbeat, one §5.5.5 apparatus. It must be re-scoped from "Phase 3
  supervisor" to "Phase 3–4 cycle sidecar."

This is a **synthesis-side** decision (it moves §5.5's agent boundary), not an Orca
one — but Orca sharpens it: P1's status-publish port gives that single sidecar a
third sink (the worktree comment) for free. Recommendation: the synthesis revisits
§5.5.1's agent boundary with monitor-consolidation on the table. Near-term `monitor`
stays as-is; consolidation happens when §5.5 is built. Tracked as SQ-9.

---

## 3. The integration seam: ports & adapters (answers Q1)

One seam, not many bolts. A small set of **ports**; each has a **file-based default
adapter** (portable baseline) and an **Orca adapter** (when `orca` CLI detected).
The orchestrator and agents call the port — never `orca` directly. Dialogue
confirmed: scattering `if orca_present` checks at call sites rots fast — the seam is
worth its indirection.

Detection: at cycle start the orchestrator runs one probe, records `orca_present`
and the chosen adapters into cycle state, never re-probes. `config.md` forces the
answer (`orca: auto|on|off`) — this is the "quick declare present/absent" switch the
dialogue asked for.

| Port | Baseline adapter | Orca adapter | Kind |
|---|---|---|---|
| **status-publish** | write to `cycle-state-*.md` | also `worktree set --comment` | augment |
| **gate** | terminal prompt (blocking) | `gate-create` / `gate-resolve` (async, UI) | augment |
| **idle-detect** | watchdog timeout polling | `terminal wait --for tui-idle` | augment |
| **notify** | file append (`whispers/`, `escalations.jsonl`) | also `orchestration send` push delivery | augment |
| **cycle-fanout** | not available (single cycle) | `orchestration` task DAG of `/cycle` runs | new capability |

Augment ports keep the baseline running and add a second sink or better signal.
`cycle-fanout` is a capability that simply does not exist without Orca.

---

## 4. Proposals — leveraging Orca (answers Q2)

### P1 — Status-publish port → live cycle status in the Orca UI *(canary)*

Findings seed C. The `monitor` already holds phase/task progress. Route every status
write through the **status-publish port**; the Orca adapter adds `orca worktree set
--comment` with a compact string, e.g. `[2.1.4 offline-sync] Phase 3/4 · 3/5 tasks · K=2 · ⚠1 esc` — leading with the
story id + slug so the worktree conveys its *contents*, not just a number. The
adapter can also set the native `workspaceStatus` enum (`in-progress`/`completed`,
confirmed via CLI probe) — a second, structured status sink alongside the comment.

Zero behavior change, pure addition, trivially graceful. Subsumes synthesis §5.8.6
(progress webhook): webhook, worktree comment, cycle-state file become three sinks
of one `progress-emit` event. **Ship first**, independent of everything else — it is
the canary that proves detection + adapter selection + graceful degradation.

Also the cheap path to the observability the dialogue wants (see P8): route the
supervisor's heartbeat/state through this port so Orca's UI shows supervisor health
without a separate terminal.

### P2 — Gate port → async, UI-resolvable approvals

Findings seed A. `/cycle`'s Gates 1C/2B/4B are blocking terminal prompts. Route them
through the **gate port**; the Orca adapter creates an `orchestration gate-create`,
the task parks in `blocked` state (UI-visible, *not* a hung terminal), a human
resolves it via `gate-resolve`.

Decouples that a gate *exists* (a decision point) from that a gate *blocks a
terminal* (a transport choice). Synthesis §5.6.3 reduces gate *count*; this changes
gate *transport* — they compose. This is the real fix for unattended automations
(seed D caveat 3): an unattended `/cycle` parks as a resolvable Orca task, not a
hung prompt. Strictly better than `hotfix`'s "skip gates" — the gate is preserved
and deferred, not discarded.

### P3 — Cycle fan-out → multi-feature parallelism *(near-term)*

Synthesis §9 deferred multi-feature parallel cycles because it pictured one
orchestrator scaling to N features (and §4 rejected that god-orchestrator). Orca's
one-feature-per-worktree model delivers it differently: **N independent
single-feature `/cycle` runs in N Orca worktrees.** `/cycle`'s orchestrator never
changes — each cycle is still single-feature. No god-orchestrator; just N ordinary
ones with Orca above them.

Dialogue confirmed fan-out as **near-term** — plan for it now. Two real costs, both
mitigated:

- **Worktree count.** Orca's sidebar shows feature worktrees *and* `/cycle`'s nested
  worktrees. Peak = `cycles × (1 + K)`. **Initially `K = off` (unbounded)** — early
  experimental fan-out runs accept a busy sidebar to see how Orca handles it; finite
  K (§2.3) is the later mitigation. New cross-cycle knob: **`max_parallel_cycles`**
  (default 1; raise deliberately).
- **Token usage.** Parallel teams across cycles is heavy. Mitigations: (a)
  `max_parallel_cycles` caps it; (b) fanned-out cycles default to `lean` mode
  (fewer agents, lower K); (c) a fan-out may pin a budget-conscious model preset —
  `config.md` already has `personal`/`team`/`enterprise` presets and per-agent
  allocation.

Merge contention is the one genuine shared resource: N features → one `main`. Each
`/cycle` runs its own Phase 4B behind a shared merge-lock task in the Orca DAG —
implementation parallel, release serialized. Orca's `merge_ready` message models
this.

Gate behind `orca_fanout` (default off) — Orca orchestration is itself experimental.
Depends on the §7 worktree-local-state audit.

### P4 — Idle-detect port → native working→idle signal

Findings seed E. `terminal wait --for tui-idle` natively detects the working→idle
transition. The Orca adapter uses it instead of polling touch-files. Consumers:
- **Watchdog** (§5.5.5 mech. 2): a real stall signal beats a timeout guess.
- **Whisper/notify timing** (§5.5.4): `tui-idle` gives a *precise* "agent is idle
  now" trigger — far better than the fuzzy "between sub-tasks" poll. Composes
  directly with P7.

Boundary: the heartbeat file tracks *supervisor* liveness; `tui-idle` tracks *agent
terminal* liveness. Different subjects — keep both. §5.5.5 is built regardless (the
portable baseline); P4 is an additional signal, not a replacement.

### P5 — Escalation surfacing + supervisor-pause as a decision gate

Findings seed B (the salvageable part). `escalations.jsonl` stays file-based —
both endpoints live in one worktree, a file is simpler and portable. Two augments:
- **Surface** escalations to the Orca UI via the `notify` port (read-only mirror).
- **The escalation ladder's terminal rung** (§5.5.4 step 3: `pause-request`)
  becomes an **Orca decision gate** via the P2 gate port. This answers synthesis
  **OQ-9** (mid-cycle plan-revision UX): it is neither a silent change nor a
  blocking interrupt — it is an async decision gate.

### P6 — `/cycle --next` + ROADMAP/stories convention + automations

Findings seed D. Three caveats and their resolutions:

1. *Automation prompts must be literal slash commands* (`disable-model-invocation`)
   — documented, not a bug.
2. *Static prompts can't pick "the next story"* — fixed by making the *command*
   dynamic, not the prompt. New **core** feature `/cycle --next`:
   - Reads `documentation/stories/README.md` — the agent-readable index of stories,
     each with a status marker and a link to its story file. (`ROADMAP.md` is the
     human-facing roadmap; this index is its machine-readable equivalent.)
   - Each `documentation/stories/<id>_<slug>.md` holds the full story text — **this
     file is the precise definition of "feature"** (§2.1). One story file ⟺ one
     cycle ⟺ one Orca worktree.
   - Picks the first not-done/not-in-progress story, runs the cycle on its story
     file, updates the marker in the index on completion.
   - An Orca automation schedules a *static, literal* `/cycle --next`; selection is
     dynamic *inside* the command. One automation drives the whole roadmap over
     time.
3. *Unattended runs park at the first gate* — fixed by P2.

Bonus: Orca automations are also the natural host for periodic `/self-improve`.

### P7 — `notify` port: Orca messaging as push delivery (not a new agent channel)

Dialogue raised Orca's mailbox / cross-talk. Two distinct uses — keep them apart:

- **(a) Transport for *existing* framework channels — adopt.** Whispers and
  escalations stay file-authoritative (`whispers/<agent-id>.md`,
  `escalations.jsonl` remain the source of truth and audit log). The Orca adapter
  *additionally* push-delivers via `orchestration send`. Orca's push-on-idle
  delivery is genuinely *better* than the §5.5 "poll between sub-tasks" design — the
  agent gets the whisper exactly when it goes idle (composes with P4). If a message
  is missed, the file poll still catches it. This is an augment, file-authoritative,
  consistent with §2.4 — Orca rings the doorbell, the file is the channel.
- **(b) New agent-to-agent direct messaging — stays rejected** (synthesis §4.4).
  Fan-out (P3) creates exactly one legitimate future need: two parallel cycles
  touching shared code. Parked as a known future item, not built now.

### P8 — Supervisor as an Orca terminal *(considered, recommended deferred)*

The idea: run the §5.5 supervisor as its own Orca terminal so Orca's `tui-idle`
monitors its liveness natively. Dialogue expressed interest, conditioned on the
§2 reasoning.

**Recommendation: defer.** Reasoning, given the §2 decisions:
- It does **not** let you skip building §5.5.5 health monitoring — the portable
  baseline must exist for `orca: off`. You build §5.5.5 either way; P8 only bypasses
  it when Orca is present. No work saved.
- It forks the supervisor's *spawn path* (Claude Code `Agent` vs. `orca terminal
  create`) — a second launch environment to maintain. Mild tension with the
  "adapters not forks" principle the dialogue endorsed.
- The observability it promises — "better insight into a single cycle" — is
  obtainable **cheaply** by routing the supervisor's heartbeat/state through the P1
  status-publish port. Orca's UI then shows supervisor health with no fork and
  without crossing the §2.4 line.

So: get the observability via P1; revisit P8 only if P1 surfacing proves
insufficient in practice. Kept on the list, explicitly parked.

### P9 — Worktree lifecycle: teardown (primary) + optional lineage adoption *(CLI-probe finding)*

The live `orca` CLI probe surfaced a QoL bug worth fixing and a verified-but-optional
nicety.

**(a) Teardown — the load-bearing fix.** The probe found completed `worktree-agent-*`
worktrees from *past* cycles still registered in Orca (`workspaceStatus: completed`,
persisting indefinitely). Orca never GCs them; today `/cycle` deletes the *branch*
after merge but does not fully remove the worktree, so they accumulate — and once
Orca is in the picture every stale worktree is a permanent sidebar row. **A real QoL
regression that adding Orca makes visible.** Fix:

- *Core (Orca-agnostic):* after merging a Phase-3 worktree, the orchestrator runs a
  full teardown — `git worktree remove --force` + branch delete, not branch-only,
  **per task, immediately after merge.** Teardown is the **orchestrator's** job — it
  outlives the subagent and owns the merge. Good hygiene with or without Orca.
- *Core janitor:* extend `SKILL.md`'s existing startup janitor (it already prunes
  stale *state files*) to also prune orphaned `worktree-agent-*` worktrees whose
  cycle is no longer active.
- *Orca adapter:* teardown additionally calls `orca worktree rm` to deregister, so
  the sidebar row disappears with the worktree.

Prompt per-task teardown also keeps inner worktrees **short-lived** — only a few
alive at any moment — which shrinks the sidebar-grokking problem to near-nothing on
its own. That is why (b) is optional.

**(b) Lineage adoption — verified, but a non-happy-path option.** Orca groups the
sidebar by explicit `parentWorktreeId` lineage, and harness-created worktrees land
orphaned. The probe **confirmed** `orca worktree set --parent-worktree` works on a
*discovered* worktree (sets `parentWorktreeId` + a `lineage` object with
`origin: manual`, `capture.confidence: explicit`; `--no-parent` reverts cleanly). So
grafting is possible — but per dialogue it is an **unusual circumstance**, not the
happy path: with prompt teardown (a), too few worktrees are alive at once for
grouping to matter. Keep adoption **opt-in** (`orca_worktree_lineage`, default off)
for the rare high-concurrency case. If used, the **subagent self-adopts on startup**
(it knows its own worktree via `orca worktree current`; the orchestrator does not —
the harness names worktrees `worktree-agent-<hash>`), with the feature-worktree
selector passed in its spawn prompt.

**Net effect on §2.3.** Teardown (a) solves sidebar *accumulation* and, by keeping
worktrees short-lived, most of *grokking* too. Optional adoption (b) handles the
residual high-concurrency case. Finite K stays a token/throughput lever, not a UI
one.

---

## 5. Seed reconciliation

| Seed | Finding | Disposition |
|---|---|---|
| **A** gates vs. unattended | Real friction | **Adopt** → P2 |
| **B** §5.5 supervisor vs. Orca orchestration | Category error — different altitudes (§2.4) | **Mostly decline.** Inner loop stays file-based. Salvage: surface escalations + pause→gate (P5), push delivery (P7) |
| **C** worktree comment as status | Clean Tier-0 win | **Adopt** → P1, ship first |
| **D** automations as entry point | Real, 3 caveats | **Adopt** → P6 (+ P2 for caveat 3) |
| **E** `tui-idle` vs. heartbeats | Useful auxiliary signal | **Adopt** → P4 |
| **F** telemetry vs. Orca run history | Minor overlap | **Note only.** Optionally echo a one-line cycle outcome to Orca automation history; do not merge schemas |

---

## 6. Separation strategy (answers Q3)

Separate along **three axes**; the flag is only one.

**6a. Planning — separate documents.** Synthesis §5.1–§5.8 stays the Orca-agnostic
core plan. This document is the addendum (proposed home: a new §5.9). The core plan
is *annotated* (§7), never forked.

**6b. Runtime — one switch, adapters not forks.** One master switch + augment
sub-keys in `config.md`:

```
## Orca Integration
| Key                 | Value | Notes                                          |
|---------------------|-------|------------------------------------------------|
| orca                | auto  | auto = detect `orca` CLI; on = require; off = off |
| orca_status_comment | true  | P1 — publish status to worktree --comment      |
| orca_gates          | auto  | P2 — route gates through decision-gate primitive |
| orca_notify         | auto  | P7 — push-deliver whispers/escalations         |
| orca_worktree_lineage | off | P9(b) — graft Phase-3 worktrees into Orca lineage (opt-in) |
| orca_fanout         | off   | P3 — multi-feature fan-out (experimental)      |
```

`orca: off` ⇒ every port uses its baseline adapter; byte-for-byte the portable
framework. The non-Orca improvements are never behind a flag — they are the
baseline.

**6c. Delivery — Orca track sequenced after core seams.** Augment adapters can only
ship after the baseline they augment exists (§8).

---

## 7. Annotations to the §5 core plan (seam requirements)

Core, non-Orca tasks the synthesis plan should adopt so Orca adapters slot in later
without rework — all have standalone value.

| Core item | Annotation |
|---|---|
| **NEW — Phase 3** | `max_parallel_agents` knob: `off` *(initial default — today's unbounded wave-spawn)*, plus `high/medium/low` = 4/2/1 for later. Finite K introduces a dispatch queue → **deferred optimization, not M1; see §2.3 + SQ-8.** Inner worktrees named with story-id prefix. |
| §5.6 cycle modes | Mode also governs K (full/lean/hotfix → high/low/1). Add a "Phase-3 worktree footprint" row to the §5.6 behavior matrix. |
| §5.2.1 event log / §5.8.6 webhook | One `progress-emit` event + a **status-publish port** with a pluggable sink list. |
| §5.6 gates | Route gate presentation through a **gate port**, not inline `read`. |
| §5.5.5 watchdog | Express stall detection as an **idle-detect port** call. |
| §5.5.2 whispers + escalations | Keep files authoritative; add a **notify hook** after each append (baseline no-op). |
| §9 multi-feature | **NEW core task:** audit that `agent_tasks/`, `agent_states/`, `cycle_reports/` writes are strictly worktree-local — no repo-root-absolute or `$HOME` shared paths. Required for P3. |
| `/cycle` entry | **NEW core task:** `/cycle --next` reads `documentation/stories/README.md` (the index) → individual story files. Define the index status-marker + link convention. |
| **NEW — story naming** | Story files gain a human-readable slug: `documentation/stories/<id>_<slug>.md` (today just `<id>`, a bare number). Improves branch names, inner-worktree names, and the Orca UI label. |
| **NEW — worktree teardown** | After merging each Phase-3 worktree, `/cycle` runs full `git worktree remove --force` + branch delete (today: branch only → stale worktrees accumulate). Extend the startup janitor to prune orphaned `worktree-agent-*`. Core hygiene; surfaced by Orca — P9(b). |

---

## 8. Sequencing — the Orca track

| Step | Item | Depends on | Flag |
|---|---|---|---|
| O-0 | P1 status-publish port + Orca comment adapter | §7 progress-emit port | `orca_status_comment` |
| O-0b | P9 worktree teardown (core + `orca worktree rm`); optional lineage adoption | O-0 | `orca` / `orca_worktree_lineage` |
| O-1 | `/cycle --next` + story-index convention + story-slug naming (core) | §7 entry + naming tasks | — |
| O-2 *(deferred)* | finite `max_parallel_agents` K + dispatch queue + cycle-mode coupling | SQ-8, §5.6 modes | — |
| O-3 | P4 idle-detect adapter | synthesis M3 + §7 idle port | `orca` |
| O-4 | P7 notify port + push delivery; P5 escalation surfacing | O-3, M3 | `orca_notify` |
| O-5 | P2 gate port + Orca decision-gate adapter; P5 pause→gate | synthesis M4 + §7 gate port | `orca_gates` |
| O-6 | P3 cycle fan-out | §7 worktree-local audit | `orca_fanout` |

O-0 and O-1 can start now — neither blocks on synthesis milestones; O-0 is the
canary. O-2 (finite K) is **deferred** — `max_parallel_agents` ships `off`, so
fan-out (O-6) runs on today's unbounded behavior and accepts a busy sidebar for the
early experimental runs.

---

## 9. Open questions

- **SQ-1 — RESOLVED (live `orca` CLI probe, 2026-05-22).** `orca worktree
  ps/list/show` **do** surface the nested `.claude/worktrees/agent-*` worktrees.
  Orca does **not** GC them — even `workspaceStatus: completed` ones persist (no
  conflict with P3; but stale worktrees accumulate, a `/cycle` cleanup-hygiene
  matter). Sidebar grouping is **by explicit `parentWorktreeId` lineage, not name
  prefix** — Claude-Code-created worktrees land orphaned (`parentWorktreeId: null`,
  `lineage: null`). Fix → P9. Story contents surface via two settable fields:
  `comment` (free text — P1) and the `workspaceStatus` enum.
- **SQ-2 — RESOLVED (CLI probe, authorized; probe task created then `orchestration
  reset`).** Orchestration task object: `{id, parent_id, spec, status, deps, result,
  created_at, completed_at}`. `deps` is a JSON array of task ids; a no-dep task
  starts `ready`. Merge-lock confirmed viable: each per-feature Phase-4B task lists
  one shared release-lock task id in its `deps`. Micro-detail for O-6: the
  `task-create` flag that populates `deps` (defaults to `[]`; likely `--deps`).
- **SQ-3.** `documentation/stories/README.md` index convention: status-marker syntax
  (`TODO`/`IN PROGRESS`/`DONE`/`BLOCKED`) and link format. Story files named
  `documentation/stories/<id>_<slug>.md`. First-draft format provided in dialogue;
  the user may finalize the index separately. `/cycle`'s existing `ROADMAP.md`
  touchpoints (`SKILL.md` entry-point table + 4B roadmap update) must be repointed
  at the new structure.
- **SQ-4.** `hotfix` mode + Orca gate adapter: skip or defer gates? Proposal:
  `hotfix` skips (mode wins over transport).
- **SQ-5.** Initial K defaults per mode (`full`/`lean`/`hotfix`) and
  `max_parallel_cycles` default — placeholders per Principle 2, telemetry-grounded
  later.
- **SQ-6.** Relation to synthesis OQ-3 (can `/skill` directly invoke an agent) and
  seed D caveat 1 — resolve together.
- **SQ-7.** P8 revisit trigger: what observation would justify reopening
  supervisor-as-Orca-terminal after P1 surfacing ships?
- **SQ-8.** *(non-blocking — K ships `off`.)* When finite `max_parallel_agents` is
  later enabled, does its dispatch queue interfere with `/cycle` Phase-3
  orchestration — wave sequencing (`SKILL.md` §3.2), `monitor` task tracking, the
  per-agent watchdog, the supervisor event window? Investigate before enabling a
  finite K; it likely needs an orchestrator change, not just a config knob.
- **SQ-9.** Fold `monitor` into the §5.5 supervisor as one Phase 3–4 "cycle
  sidecar" (§2.5)? Synthesis-side decision; revisit when §5.5 is scoped.

---

## 10. Summary

1. **One seam, not many bolts** — a ports-and-adapters layer, file-based baseline,
   Orca adapters, selected once per cycle by detection. `orca: auto|on|off`.
2. **Two altitudes, elastic inner layer** — feature = one ROADMAP story = one Orca
   worktree (precise, framework-imposed). `/cycle`'s inner worktrees stay nested but
   their peak count is *bounded and declared* via `max_parallel_agents = K`, set by
   cycle mode. Not flat, not unbounded. The §5.5 inner control loop stays
   file-based and Orca-agnostic.
3. **Leverage Orca where the framework is weak** — multi-feature fan-out (P3,
   near-term), async UI gates (P2), live status (P1), worktree teardown + optional
   lineage (P9), native idle detection (P4), push delivery for existing channels
   (P7). Do *not* let Orca into the §5.5 inner control loop.
4. **Separate on three axes** — separate docs, one runtime switch (adapters not
   forks), a delivery track sequenced after each core seam.

The core plan ships and stands alone. The Orca track is upside layered on top; the
worktree-comment canary (O-0) proves the whole seam at near-zero risk.
