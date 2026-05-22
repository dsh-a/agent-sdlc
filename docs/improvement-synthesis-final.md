# Agent-SDLC Improvement Synthesis (Final)

**Date:** 2026-05-17
**Status:** Draft for review and edit before implementation
**Sources synthesized:**
- `docs/anecdote_improvements.md` — felt friction (tag **[A]**)
- `docs/cycle-reports-improvements.md` — patterns across 12 cycle reports (tag **[C]**)
- `docs/culture-improvements.md` — borrowable ideas from agentculture/culture (tag **[K]**)
- `docs/extract-agent-skills.md` — prompt-slimming analysis (tag **[X]**)
- `docs/improvement-synthesis-1.md`, `-2.md`, `-3.md` — three independent syntheses + collaborative dialogue

This is the merged plan. Decisions that are settled are marked **(settled)**. Decisions that remain open are marked **(open)** and consolidated in §10.

---

## 1. The unifying critique

There are **two independent critiques** running through the four source docs. They are mostly orthogonal but they touch in one place.

**Primary — the pipeline is open-loop where it should be closed-loop.** Once the orchestrator hands work off, it gets no signal back until exit or watchdog. Worktree mismatches **[C§1]**, watchdog stalls **[C§2]**, the hidden wave-4 verify gap-fill **[C§4]**, recurring `copyWith` drops **[C§7]**, PRD deviations **[C§8]**, mid-cycle scope creep **[C§9]**, silent orchestrator rescues **[C§10]**, the [A§4] conductor framing, and every Culture borrow (**[K§1]** supervision, **[K§2]** whispers, **[K§3]** context compaction, **[K§4]** contracts) reduce to the same shape: continuous observation + correction is missing at every scale (per-tool-call, per-task, per-phase, per-cycle).

**Secondary — the framework optimizes for the worst-case story.** Every story pays for the worst case in prompt overhead ([A§5], [X]) and in pipeline shape ([A§3]). Small stories feel disproportionately expensive.

They touch in one place: closing the loop (primary) is what makes adaptive depth (secondary) achievable. Without observation, "lite verify on small stories" is a guess; with observation, it's a decision.

---

## 2. Load-bearing principles

Two principles govern the whole plan. They appear in every theme and they resolve several open questions at once.

### Principle 1 — Two-purpose skill principle (settled)

> A skill exists for one of two purposes, never both:
>
> 1. **User-facing well-trodden path** — `/<skill>` is the user saying "skip the bullshit, here's what I want to do." May invoke agents but does not duplicate them.
>
> 2. **Agent-facing context sandwich** — focused, dense reference material an agent grabs to populate context efficiently. No conversational framing, designed to be loaded mid-task. One topic per file.
>
> A skill that is neither — a parallel implementation of an agent's prompt — is dead weight. Delete it.

Direct consequences:
- Mirror skills under `.claude/skills/` that duplicate agent prompts (`test`, `verify`, `review`, `self-improve`, `create-prd`, `generate-tasks`, `scaffold`, `ui-story`) **are killed**. User-facing slash commands become thin shims that invoke the corresponding agent.
- New skills extracted per [X] (`flutter-conventions`, `widget-test-patterns`, `ac-audit-rubric`, `pipeline-metrics-rubric`, etc.) are **context sandwiches**: dense, focused, no conversational scaffolding.
- Pure user-facing skills (`feature-idea`, `process-tasks`, `refine`, `setup`, `setup-scaffold`) stay as well-trodden paths.

### Principle 2 — Threshold-grounding principle (settled)

> Any framework rule of the form "do X when condition Y holds" is designed to evolve from heuristic thresholds → telemetry-derived thresholds as data accumulates. Initial defaults are placeholders, explicitly marked, and `self-improve` is responsible for tuning them against recorded cycle outcomes.

Applies to:
- Verify-depth selection (§5.5)
- Supervisor check cadence and whisper-detector thresholds (§5.3)
- Watchdog timeouts (currently 600s and 30s — placeholders)
- Cycle-mode auto-suggestion heuristics (§5.4)
- Circuit-breaker thresholds (§5.3)
- Any future "skip / accelerate / escalate when X" rule

Implementation note: every threshold in `config.md` gets a comment marking it as `(placeholder)` or `(telemetry-derived from cycles X..Y)` so users and `self-improve` can tell which is which.

---

## 3. What is being built (high level)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Tier 0 — Reliability + Telemetry + Contracts (foundation)           │
│   Worktree fix · Verify path fix · Watchdog salvage                 │
│   Per-agent event log (events/*.jsonl) → feeds both supervisor      │
│     and run-report telemetry                                        │
│   Frontmatter `requires:` / `produces:` on all agents               │
│   Rescue-event schema (enum, not free prose)                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Tier 1 — Test-quality cluster (highest evidence weight)             │
│   Test-agent self-check rubric (absorbs adversarial-tester [open])  │
│   Silent-skip grep gate                                             │
│   Pre-flight contradiction classifier                               │
│   Structured contradiction-exit signal                              │
│   Pattern-divergence handling                                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Tier 2 — Closed-loop primitives                                     │
│   Whisper channel (supervisor → agent)                              │
│   Escalation channel (supervisor → orchestrator)                    │
│   Haiku supervisor (single agent, dual outputs)                     │
│   Supervisor health monitoring (heartbeat, circuit breaker, degrade │
│     gracefully)                                                     │
│   Structured logging of rescues / deviations / scope changes        │
│   Handoff validation at phase boundaries                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Tier 3 — Adaptive depth and shape                                   │
│   Cycle modes (full / lean / hotfix) — user-declared, never silent  │
│   Parallel verify + review                                          │
│   Lite verify with telemetry-grounded safety rule                   │
│   Mode auto-suggestion at dry-run (suggestion, never silent infer)  │
│   Mid-cycle plan revision via supervisor escalation                 │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Tier 4 — Skill extraction (justified by drift reduction, not tokens)│
│   skills/scaffold/SKILL.md dedup (canary)                           │
│   Kill mirror skills, replace with thin shim slash commands         │
│   Create flutter-conventions, widget-test-patterns, ac-audit-rubric │
│   Slim test.md, ui-story.md, verify.md, review.md, etc.             │
│   Centralize autonomous preamble                                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Tier 5 — Hygiene + long tail                                        │
│   Analyzer baseline [open: ship-vs-punt]                            │
│   Tag-based scaffold dispatch                                       │
│   Compact at phase boundaries                                       │
│   Bug-triage path (known-pitfalls.md mechanism) [open]              │
│   Progress webhook                                                  │
│   Codify review auto-fix vs flag boundary                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. What is NOT being built (settled)

Decisions to *not* build things that the source docs imply:

1. **No god-orchestrator / general-purpose "conductor"** ([A§4] reframed). [A§4]'s conductor conflated three responsibilities (pipeline shape, mid-cycle plan revision, arbitrary pipeline design). Cycle modes (§5.4) own pipeline shape; the supervisor (§5.3) owns mid-cycle plan revision recommendations; **arbitrary pipeline design does not get built.** The orchestrator chooses between named modes; it does not compose pipelines from scratch.

2. **No silent mode inference.** Cycle modes are user-declared. The orchestrator may *suggest* a mode at dry-run based on heuristics from the feature description, but never picks silently.

3. **No mirror skills.** `skills/test/`, `skills/verify/`, `skills/review/`, `skills/self-improve/`, `skills/create-prd/`, `skills/generate-tasks/`, `skills/scaffold/`, `skills/ui-story/` — all killed as duplicative agent prompts. Replaced with thin shim slash commands that invoke the corresponding agent. [Open question 3: platform spike — can `/skill` directly invoke an agent without any skill file? If yes, the shims collapse to nothing.]

4. **No agent-to-agent direct messaging.** Anthropic's agent-teams is experimental and disabled; Culture's IRC-style cross-agent messaging is interesting but out of scope. All cross-agent coordination flows through the orchestrator + filesystem (event logs, whispers, escalations).

5. **Multi-feature parallel cycles** (S2 gap) — out of scope for this round. State-file naming supports it; the orchestrator doesn't. Defer.

6. **Post-merge rollback story** (S2 gap) — out of scope. SDLC pipeline ends at merge; post-merge bugs enter as new cycles. Acknowledged, not built.

---

## 5. Themed plan

### 5.1 Reliability foundation (Tier 0, P0)

**Settled items, ready to scope.**

| Item | Source | Notes |
|---|---|---|
| 5.1.1 Worktree base-branch fix in `cycle/SKILL.md` | [C§1] | Cited in 5/12 cycles. Phase 3 worktrees branch from `feature/<story>` HEAD, not stale `develop`. |
| 5.1.2 Startup merge-base assertion in every implementation agent | [C§1] | Each agent verifies its worktree's merge-base = feature branch tip on startup; aborts if not. |
| 5.1.3 Verify/review incremental report writes | [C§2] | Append findings as produced; partial result survives stall. |
| 5.1.4 Watchdog → Haiku salvage pass | [C§2] | On stall, Haiku agent reads transcript, emits `PARTIAL — agent stalled` report file. |
| 5.1.5 Canonical artifact paths enforced at agent exit | [C§3] | One path per agent in frontmatter `produces:`. Missing file = agent failure, not silent pass. |
| 5.1.6 Parallel verify + review in Phase 4A | [A§1] | They don't share state. Easy win. |

### 5.2 Telemetry foundation (Tier 0, P0)

**The thing none of the source docs treated as P0 but every other improvement depends on.**

| Item | Source | Notes |
|---|---|---|
| 5.2.1 Per-agent event log at `agent_states/events/<agent-id>.jsonl` | gap (S2 + S3) | One line per tool call. Schema: `ts, agent, tool, file, command, summary, retry, exit`. Single write feeds both supervisor and run-report consumers. |
| 5.2.2 Per-agent telemetry rolled into run report | [X open Q] | Token in/out, wallclock, tool-call count, retry count, contradiction-exit count, supervisor whispers received, peak context size. **[Open question 8: schema scope]** |
| 5.2.3 Rescue-event schema (enum, structured) | [C§10] + S3 gap | Enum: `worktree-mismatch`, `watchdog-timeout`, `stall`, `contradiction-loop`, `supervisor-stall`, `supervisor-disabled`, `manual-completion`. Structured per-event records. Schema defined *before* the logger ships. |
| 5.2.4 `rescues: []` array in cycle state, populated on every silent substitution | [C§10] | Surfaces in run report. Read by `self-improve` for cross-cycle trends. |

### 5.3 Contracts foundation (Tier 0, P0)

**Enables Tier 1 handoff validation and Tier 4 skill extraction without drift.**

| Item | Source | Notes |
|---|---|---|
| 5.3.1 Frontmatter contracts on all agents | [K§4] | `requires: [glob...]`, `produces: [glob...]`, `artifact_dir:`. One PR across all 10 agents. |
| 5.3.2 Orchestrator validates handoff at phase boundary | [K§4] + [C§3] | Checks `produces:` files exist with expected shape. Missing = agent failure. |
| 5.3.3 `deviations:` field on implementer handoff | [C§8] | Each implementer enumerates places where the implementation differs from literal PRD AC, with reasons. Surfaces in cycle report at gate, not at review. |
| 5.3.4 Mid-cycle scope changes logged structurally | [C§9] | Add to cycle state; verify reads the updated AC set. Currently captured in prose only. |
| 5.3.5 Tag-based scaffold dispatch | [K honorable] | Task files declare `scaffold_kind: syncable-entity` etc. Orchestrator dispatches directly instead of inferring from prose. |

### 5.4 Test-quality cluster (Tier 1, P1, highest evidence weight)

**Four source docs converge on this. Cheapest cluster relative to its impact.**

| Item | Source | Notes |
|---|---|---|
| 5.4.1 Test-agent self-check rubric (absorbs adversarial-tester logic) | [C§4] + [X] + [C§5] | Test agent runs a hard rubric against its own output before declaring done: "for each AC, does the test assert the literal AC behavior? Are negative paths covered? Boundary cases? Are there `if (...isNotEmpty)` patterns?" Fail → fix → re-run. **[Open question 1: does adversarial-tester get deprecated entirely or kept as a smaller spawn-on-gate? Default plan: deprecate and fold.]** |
| 5.4.2 Silent-skip grep gate | [C§5] | Hard mechanical check at test agent's pre-commit: `if (find...isNotEmpty)`, `if (finder.evaluate()…)`, `try { ...expect... } catch { return }` patterns fail the agent's own commit. |
| 5.4.3 Pre-flight contradiction classifier | [A§2] | Haiku pass before `test` agent runs: enumerates "tests that reference symbols you're about to change," classifies each as `keep` / `update` / `delete-because-AC-supersedes`. Hands plan to test agent. |
| 5.4.4 Structured contradiction-exit signal in test agent | [A§2] | When test agent encounters incompatible sources of truth (existing test vs. AC vs. interface), halt and emit a structured question via whisper channel rather than thrash. Counts as a `contradiction-exit` event in telemetry. |
| 5.4.5 Pattern-divergence handling | [C§6] | When test agent touches a directory with tests in a non-conventional pattern (mocktail vs. stub), either migrate old tests in same commit or declare divergence in `deviations:` handoff. No silent splits. |

### 5.5 Closed-loop primitives — the supervisor (Tier 2, P1)

**The architectural shift. Single largest investment in the plan.**

#### 5.5.1 Supervisor definition (settled)

> The Phase 3 supervisor is a Haiku-level sidecar agent that observes implementation agents' tool-call event logs and produces two outputs: **whispers** (advisory, agent-directed) and **escalations** (structured, orchestrator-directed).
>
> **The supervisor does not:** make depth decisions (only recommends), pause agents (only requests pause), re-shape the cycle plan, or read implementation source files directly.

#### 5.5.2 Channels (settled)

**Channel 1 — Agents → supervisor (telemetry input)**

Each implementation agent writes one line per tool call to `agent_states/events/<agent-id>.jsonl`. Supervisor reads last K=20 events per agent + cycle state for task context. Same event log feeds telemetry (§5.2).

**Channel 2 — Supervisor → agent (whispers)**

Append-only `agent_states/whispers/<agent-id>.md`. Severity levels: `note` (advisory), `strong` (advisory), `pause` (binding). Agents poll between sub-tasks. **`note` and `strong` may be ignored** — agents have context the supervisor lacks. `pause` is binding.

Whisper format:
```yaml
---
ts: 2026-05-17T14:35:01Z
severity: note | strong | pause
detector: spiral | drift | stall | shallow | contradiction
---
Body: corrective note in prose.
```

**Channel 3 — Supervisor → orchestrator (escalations)**

Append-only `agent_states/escalations.jsonl`. Types: `pause-request`, `depth-recommendation`, `bug-pattern`. Orchestrator polls at three moments only:
1. Phase transition (e.g., end of Phase 3 → before spawning verify/review)
2. Sub-task boundary during Phase 3
3. Watchdog tick

Orchestrator does NOT poll mid-tool-call. Up-to-30s latency on pause-request is acceptable; the alternative defeats sidecar separation.

#### 5.5.3 Artifact layout (settled)

```
agent_states/
  cycle-state-<feature>.md
  events/
    <agent-id>.jsonl                # per-agent tool-call log
  whispers/
    <agent-id>.md                   # supervisor → agent advisories
  escalations.jsonl                 # supervisor → orchestrator
  supervisor/
    state.md                        # supervisor working state
    heartbeat                       # touch-file, updated each check
```

At cycle completion, this subtree archives to `cycle_reports/<feature>/supervisor/` for post-hoc analysis (run report + self-improve).

Agent IDs: `<role>-<task-number>` (e.g., `test-3.0`, `ui-story-2.1`). Cleared at cycle start.

#### 5.5.4 Cadence + escalation ladder (settled, with telemetry-grounded thresholds)

| Check | Trigger | Window read | Initial threshold (placeholder) |
|---|---|---|---|
| Whisper check (per agent) | Every N tool calls | Last K=20 events of that agent | N=5, K=20 |
| Escalation check (phase-cumulative) | Per sub-task and phase boundary | Full Phase-3 cumulative state | All boundaries |

Escalation ladder (verbatim from [K§1]):
1. First detection → whisper at `severity: note`
2. Persists across one check → whisper at `severity: strong`
3. Still persists → escalation type `pause-request` to orchestrator + whisper at `severity: pause`

#### 5.5.5 Supervisor health monitoring (settled — heavy posture)

Six layered mechanisms:
1. **Heartbeat file** — supervisor touches `agent_states/supervisor/heartbeat` after each check. Orchestrator reads at watchdog tick. Missing > 60s → declare offline.
2. **Per-check watchdog** — each supervisor check has its own 30s watchdog. Exceeded → kill + respawn. Prevents the supervisor from becoming a stall source.
3. **Rescue logging on outage** — every offline declaration appends to `rescues:` with category `supervisor-stall` + last-heartbeat-ts + duration.
4. **Circuit breaker on respawn** — 3 supervisor crashes in 5 minutes → orchestrator gives up on supervision for the rest of the cycle, logs `supervisor-disabled`, **cycle continues in degraded mode** (no whispers, no escalations, no depth recommendations — falls back to today's behavior).
5. **Run report exposes supervisor uptime %** — cycles with <90% uptime flagged as "degraded" in the run report.
6. **`self-improve` watches the pattern** — `supervisor-stall` or `supervisor-disabled` in ≥N cycles → raises P0.

#### 5.5.6 Supervisor → plan-revision flow

The supervisor's `depth-recommendation` escalations are *recommendations*, not decisions. The orchestrator decides whether to accept and logs the decision either way. Means audit trail of "supervisor said X, orchestrator chose Y, rationale Z."

[Open question 4: supervisor success metric — how do we know whispers and escalations are correct? Likely: log every output, post-hoc human-grade a sample per cycle, feed to `self-improve` for tuning thresholds.]

### 5.6 Cycle modes (Tier 3, P2)

**User-declared, suggestion-not-inference, never silent.**

| Item | Source | Notes |
|---|---|---|
| 5.6.1 Cycle modes `full` / `lean` / `hotfix` | [A§3] | User-declared at `/cycle` invocation via flag. Behavior matrix needs explicit table — see open question 5.6a. |
| 5.6.2 Per-phase skip flags in `config.md` | [A§3] | E.g., `skip_verify_if_files_changed_lt: 3` (placeholder, telemetry-grounded). Conservative defaults. |
| 5.6.3 Gate consolidation in lean mode | [A§3] | 1C + 2B collapse to one approval. |
| 5.6.4 Mode auto-suggestion at dry-run | [A§4] reframed | Orchestrator suggests a mode based on feature-description heuristics (word count, file scope indicators, complexity keywords). User accepts or overrides. **Never picks silently.** |
| 5.6.5 Mid-cycle plan revision via supervisor | [A§4] reframed | The supervisor escalates depth recommendations; orchestrator accepts or rejects. This is the only "adaptive" behavior; it operates on signal, not prediction. |

**Behavior matrix (initial draft — needs user confirmation, see open question 5.6a):**

| Phase | full | lean | hotfix |
|---|---|---|---|
| 1A PRD | yes | inline (skip generation, derive from feature description) | skip |
| 1C gate | yes | merged with 2B | skip |
| 2 task gen | yes | yes | skip (single task) |
| 2B gate | yes | merged with 1C | skip |
| 3 implementation | parallel agents | parallel agents | single agent, no worktree |
| 4A wrap-up | verify + review (standard) | verify + review (parallel) | lite verify, no review |
| 4B release | yes | yes | yes |

#### 5.6.6 Verify-depth selection (settled, telemetry-grounded)

Verify depth selection runs against telemetry-observable inputs only:

- `files_changed_count`
- `test_files_touched` (bool)
- `domain_or_migration_files_touched` (bool)
- `deviations_non_empty` (bool, from implementer handoff)
- `phase3_retry_count` (from supervisor)
- `phase3_contradiction_exits` (from supervisor)
- `mid_cycle_scope_expansion` (bool, from cycle state)

**Initial thresholds (placeholder, until ≥20 cycles of telemetry):**
- **Lite permitted only when ALL of:** `files_changed < 3` AND `not test_files_touched` AND `not domain_or_migration_files_touched` AND `not deviations_non_empty`
- **Deep recommended when ANY of:** `phase3_retry_count > 3` OR `phase3_contradiction_exits >= 1` OR `mid_cycle_scope_expansion`

After ≥20 cycles, thresholds get re-derived from observed correlations between input values and verify-find rates. The rule structure stays; the constants update. `self-improve` proposes the new constants in a normal improvement cycle.

### 5.7 Skill extraction (Tier 4, P2)

**Justified by drift reduction + prompt-cache stability, not by token savings.**

The [X] roadmap stands but the justification is reframed. Token savings is the wrong success metric — load-bearing tokens at spawn time are task context (PRD, AC, files), not agent prompts. The real benefits:

1. **Drift reduction** — one canonical place for each convention. Currently the same MVVM rules appear in 5 places (`ui-story.md`, `scaffold/view-model-view.md`, `test.md`, `review.md`, `skills/review/SKILL.md`).
2. **Prompt-cache stability** — smaller, more stable prefixes are more cacheable.
3. **Per-task context budget** — incidentally, agents have more headroom for the actual task. Tertiary.

| Order | Item | Source | Notes |
|---|---|---|---|
| 5.7.1 | Dedupe `skills/scaffold/SKILL.md` (343 → ~50, index-only) | [X-4] | Zero behavior change. Ship first as canary. Validates "context-sandwich" model. |
| 5.7.2 | Kill mirror skills (`skills/test/`, `skills/verify/`, etc.) | Principle 1 | Replace user-facing slash commands with thin shims that invoke the agent. [Open question 3: platform spike for direct slash → agent invocation.] |
| 5.7.3 | Create `flutter-conventions` skill (context sandwich) | [X HIGH #3] | Consolidates MVVM rules, member order, naming defaults. Loaded by ui-story, scaffold, review, test. |
| 5.7.4 | Slim `test.md` to ~60 lines | [X HIGH #1] | Extract `widget-test-patterns`, `ac-audit-rubric`. Move adversarial-spawn to orchestrator (or remove per open question 1). |
| 5.7.5 | Slim `ui-story.md` to ~75 lines | [X HIGH #2] | Delegate VM/View pattern to scaffold; delegate widget-test block to test. Load `flutter-conventions`. |
| 5.7.6 | Slim `verify.md` to ~85 lines | [X MED] | Extract `ac-audit-rubric`. Lazy-load `live-widget-tree-audit`, `non-functional-audit`, `golden-review`. |
| 5.7.7 | Slim `review.md` to ~80 lines | [X MED] | Use `flutter-conventions`. Extract `review-report-format`. |
| 5.7.8 | Slim `self-improve.md` to ~70 lines | [X MED] | Extract `pipeline-metrics-rubric`. |
| 5.7.9 | Slim `create-prd.md` to ~75 lines | [X MED] | Extract `ac-authoring`. |
| 5.7.10 | Slim `generate-tasks.md` to ~85 lines | [X LOW] | Extract `task-file-format`. |
| 5.7.11 | Centralize autonomous preamble | [X LOW] | One include, ~18 lines reclaimed. |

All new extracted skills are context sandwiches: dense, focused, no preamble.

### 5.8 Hygiene + long tail (Tier 5, P3)

| Item | Source | Notes |
|---|---|---|
| 5.8.1 Analyzer baseline | [C§11] | **[Open question 2: ship or punt?]** If shipping, opt-in config flag with `soft_warn` default + `hard_fail_if_exceeded` mode. |
| 5.8.2 Compact at phase boundaries (Phase 2→3, 3→4) | [K§3] | Deterministic `/compact`. Verify with telemetry before adopting widely — may cost orchestrator decision-continuity. |
| 5.8.3 Known-pitfalls / regression-prevention loop | S3 gap | **[Open question 6.]** `documentation/known-pitfalls.md` mechanism: orchestrator pre-attaches relevant entries to implementation agents based on file globs. Framework provides mechanism; project owns content. |
| 5.8.4 Bug-triage path | [C honorable] | Aggregate "Bugs discovered" entries from cycle reports into `documentation/bugs.md` (curated by `self-improve`). |
| 5.8.5 Codify review auto-fix vs flag boundary | [C honorable] | Review auto-fixes only mechanical/proof-checkable changes (drift, formatter output, missing `copyWith` fields where constructor declaration proves intent). Anything else is flagged with suggested diff. |
| 5.8.6 Progress webhook | [K honorable] | One-line Discord/Slack ping on `phase_complete` / `agent_question` / `cycle_error`. `monitor` already has the state. |
| 5.8.7 Inline-entity-construction nudge | [C§7] | Add to `ui-story` / `scaffold` prompts: "When constructing an entity inline (not via copyWith), enumerate every field and explain each value." Reduces but doesn't fix the copyWith-drop class of bugs. |
| 5.8.8 Secrets/credentials handling sentence in agent prompts | S2 gap | One-sentence addition to base agent prompts: "If you encounter `.env`, credentials, or secrets, do not read or commit them; surface to user." |

---

## 5.9 Orca synergy — optional enhancement tier (P3)

**Full plan:** `docs/orca-synergy-plan.md`. This is the slot-in stub.

`agent-sdlc` deploys as a portable `.claude/` folder and must keep working without
Orca. When the host environment *is* Orca (an agentic dev environment managing
repos, worktrees, terminals, and orchestration), the framework can detect it and
augment several baseline mechanisms.

**Framing.** Orca support is an *augment layer*, never a dependency. §5.1–§5.8 stay
Orca-agnostic and always-on; Orca behavior sits behind a ports-and-adapters seam
with file-based default adapters and Orca adapters selected once per cycle by
detection (`config.md`: `orca: auto|on|off`).

**Two altitudes (load-bearing).** Orca orchestration operates at the *feature* level
(one ROADMAP story = one `/cycle` = one Orca worktree); `/cycle`'s own orchestrator
+ the §5.5 supervisor operate at the *sub-task* level. They do not merge. The §5.5
inner control loop stays file-based and Orca-agnostic — Orca's
`escalation`/`worker_done`/circuit-breaker vocabulary is a coincidental name
collision, not a shared mechanism.

**Headline items** (each sequenced after the core seam it augments):
- *Status / lineage* — publish cycle status to the worktree `--comment`; adopt
  nested Phase-3 worktrees into Orca's `parentWorktree` lineage so the UI groups
  them under one feature node.
- *Gates* — route Gates 1C/2B/4B through Orca decision gates (async, UI-resolvable);
  enables unattended/scheduled cycles.
- *Fan-out* — multi-feature parallelism as N independent `/cycle` runs in N Orca
  worktrees; delivers the §9-deferred capability without a god-orchestrator.
- *Entry* — `/cycle --next` reads a `documentation/stories/` index; an Orca
  automation schedules it.

**Annotations to §5.1–§5.8.** To keep the Orca adapters drop-in, the core plan
should route gate presentation, status emission, stall detection, and
whisper/escalation appends through *named ports* rather than inline transports, and
audit that all `agent_states/` / `agent_tasks/` / `cycle_reports/` writes are
worktree-local. New core (Orca-agnostic) tasks introduced by the synergy plan:
a `max_parallel_agents` knob (ships `off` — today's behavior), `/cycle --next`, and
story-file slug naming. See `orca-synergy-plan.md` §7.

**Cross-reference to §5.5.** The synergy plan (§2.5) raises a synthesis-side
question: once the §5.5 supervisor exists, `monitor` and the supervisor are two
cheap Haiku background observers, each needing health monitoring. Consider folding
them into one Phase 3–4 "cycle sidecar." Revisit §5.5.1's agent boundary when §5.5
is scoped (tracked as SQ-9 in the synergy plan).

---

## 6. Dependency graph

```
Tier 0 — Reliability + Telemetry + Contracts (parallel, all P0)

5.1.x reliability (worktree, paths, watchdog, parallel verify+review)
            │
            ▼
5.2.x telemetry (event log, rescue schema, run-report fields) ─── feeds everything below
            │
            ▼
5.3.x contracts (frontmatter, deviations, scope changes) ──┐
                                                            │
                          ┌─────────────────────────────────┘
                          ▼
                   Tier 1 — Test quality
                   5.4.x (self-check rubric, grep gate, contradiction-exit,
                          pre-flight classifier, divergence handling)
                          │
                          ▼
                   Tier 2 — Closed-loop primitives
                   5.5.x supervisor + whispers + escalations + health
                          │
                          ▼
                   Tier 3 — Adaptive depth
                   5.6.x modes + lite-verify + mode suggestion
                          │
                          ▼
                   Tier 4 — Skill extraction
                   5.7.x scaffold dedup canary → kill mirrors → extract conventions → slim agents
                          │
                          ▼
                   Tier 5 — Hygiene
                   5.8.x analyzer baseline, compact, known-pitfalls, etc.
```

The critical path is short. Tier 0 is week-1 work; Tiers 1–4 build on it; Tier 5 is interleaved opportunistically.

---

## 7. Milestones

Sequenced for shippability. Each milestone is independently valuable.

### Milestone 1 — Tier 0 foundation (1–2 weeks)

5.1.1 worktree fix · 5.1.2 merge-base assertion · 5.1.3 incremental writes · 5.1.4 watchdog salvage · 5.1.5 canonical paths · 5.1.6 parallel verify+review · 5.2.1 event log · 5.2.2 telemetry fields · 5.2.3 rescue schema · 5.2.4 rescues array · 5.3.1 frontmatter contracts · 5.3.2 handoff validation · 5.3.3 deviations field · 5.3.4 scope-change logging · 5.3.5 tag-based dispatch.

**Acceptance:** worktree-mismatch rate → 0; all agent handoffs validated on disk; per-agent telemetry visible in run reports.

### Milestone 2 — Test-quality cluster (1 week)

5.4.1 self-check rubric · 5.4.2 silent-skip grep gate · 5.4.3 pre-flight classifier · 5.4.4 contradiction-exit signal · 5.4.5 divergence handling.

[Open question 1 resolves before this ships — adversarial-tester fate.]

**Acceptance:** wave-4 verify gap-fill commits drop measurably (target: ≥75% reduction); test-task duration variance drops.

### Milestone 3 — Supervisor + whispers (2 weeks)

5.5.1 supervisor definition · 5.5.2 channels · 5.5.3 artifact layout · 5.5.4 cadence + escalation ladder · 5.5.5 health monitoring · 5.5.6 plan-revision flow.

**Acceptance:** simulated spiraling agent gets paused via escalation ladder; supervisor heartbeat visible; degraded-mode fallback works when supervisor killed.

### Milestone 4 — Cycle modes + adaptive depth (1–2 weeks)

5.6.1 modes · 5.6.2 skip flags · 5.6.3 gate consolidation · 5.6.4 auto-suggestion · 5.6.5 plan revision · 5.6.6 verify-depth selection.

**Acceptance:** hotfix-shaped cycle completes in <half wall-clock of full cycle; full cycle unchanged.

### Milestone 5 — Skill extraction (2 weeks)

5.7.1 scaffold dedup canary · 5.7.2 kill mirror skills · 5.7.3 flutter-conventions · 5.7.4 slim test.md · 5.7.5 slim ui-story.md · 5.7.6–10 remaining slims · 5.7.11 preamble.

[Open question 3 resolves before 5.7.2 ships — platform spike for slash → agent invocation.]

**Acceptance:** agent prompts drop ≥40% in line count; drift hazard eliminated (single source per convention).

### Milestone 6 — Hygiene + long tail

5.8.x items folded into appropriate later cycles. Not a discrete milestone.

---

## 8. Where this plan disagrees with the source docs (settled)

For traceability — places this plan deviates from what one or more source docs proposed:

1. **[A§4] "conductor as highest leverage" — demoted.** The conductor concept is split into modes (§5.6) + supervisor plan-revision (§5.5.6). No god-orchestrator is built. Arbitrary pipeline design is explicitly out of scope.

2. **[A§1] tier-down verify on small stories — gated.** Lite verify is allowed but only under a telemetry-derived safety rule (§5.6.6). Never lite when test files touched (S2's call).

3. **[X] "53% line reduction" framing — reframed.** Skill extraction is justified by drift reduction + prompt-cache stability, not token savings. Token-cost-delta is a check, not a goal.

4. **[X] mirror skills — killed, not `@include`d.** Per Principle 1 (two-purpose skills), parallel agent prompts in skill clothing are dead weight regardless of how they're maintained.

5. **[C§4] "fold adversarial-tester into Phase 3 default flow" — reconsidered.** The improvement is the self-check rubric inside the test agent (§5.4.1). [Open question 1: whether adversarial-tester is deprecated entirely.]

6. **[C§11] analyzer baseline — re-elevated from "probably out of scope."** Per S3's pushback: framework provides opt-in mechanism, project owns policy. [Open question 2: ship or punt.]

7. **Per-agent telemetry — promoted from afterthought to Tier 0 P0.** S2 + S3 both flagged this; the source docs didn't.

---

## 9. Out of scope for this round

Acknowledged but not in this plan:

- Multi-feature parallel cycles
- Post-merge rollback / story-of-rollback
- Test-fixture discoverability (`test/fixtures/` convention) — project-side
- Project-side analyzer cleanup (framework provides knob; project does the work)
- The `refine` skill — recently added, not yet exercised in cycle reports. Revisit after 5+ cycles use it.

---

## 10. Open questions (consolidated)

These need explicit resolution before or during implementation. Numbered so they're easy to reference.

**OQ-1. Adversarial-tester existence.** Deprecate-and-fold (current plan) vs. keep-with-gating vs. status-quo. The user has flagged adversarial-tester as a potential token anti-pattern; analysis above supports deprecate-and-fold. Affects 5.4.1, 5.7.4, and the agent roster.

**OQ-2. Analyzer baseline ship-vs-punt.** Three options:
- Off: framework records the count, project owns enforcement (S1/S2 lean)
- Opt-in single mode: config flag, soft-warn only
- Opt-in two modes: config flag with `soft_warn` (default) + `hard_fail_if_exceeded` knob (current plan)

**OQ-3. Mirror-skill kill platform spike.** Can `/skill` directly invoke a named agent without an intermediate skill file? If yes, mirror skill replacements collapse to nothing. If no, they become 3-line shims. Verify before 5.7.2 ships.

**OQ-4. Supervisor success metric.** How do we measure whether whispers and escalations are *correct*? Proposed approach: log every output, post-hoc human-grade a sample per cycle, feed to `self-improve` for tuning. Needs concrete design.

**OQ-5. Cycle-mode behavior matrix.** The draft in §5.6 is a first pass. Needs explicit confirmation, especially:
- Does `lean` mode skip task generation entirely, or generate inline?
- Does `hotfix` mode require a feature branch at all, or commit directly?
- Where does gate consolidation actually happen in `lean` mode (UX flow)?

**OQ-6. Known-pitfalls regression-prevention loop.** Build the mechanism? Where: framework or project? Proposed (S3): framework mechanism (orchestrator pre-attaches), project content (`documentation/known-pitfalls.md`).

**OQ-7. Cycle-mode auto-suggestion heuristics.** What feature-description signals trigger which mode? Word count? Keyword scan? File-scope indicators? Initial heuristics need a first draft; thresholds are placeholder until telemetry exists.

**OQ-8. Telemetry schema scope.** Per-agent fields: token in/out, wallclock, tool-call count, retry count are obvious. Also: contradiction-exit count, supervisor whispers received, peak context size, prompt-cache hit rate? Lock the schema before 5.2.1 ships — adding fields later is more expensive.

**OQ-9. Mid-cycle plan-revision UX.** When the supervisor escalates a depth recommendation and the orchestrator accepts, does the user get notified? At-the-time (interrupt) or at-next-gate (summary)? Affects whether escalations feel like "the system is helping" or "the system is reshaping things behind my back."

---

## 11. Closing observation

The four source documents were written from four vantage points — felt friction, cycle-report archaeology, comparative framework reading, and prompt-engineering analysis — and they converge on the same diagnosis: **the framework is good at executing a fixed pipeline and bad at adapting to what it sees while executing.**

The three independent syntheses converged again: reliability + telemetry + contracts as foundation; test quality as the highest-evidence cluster; supervision as the architectural shift; skill extraction as a follow-on (with reframed justification); the conductor as a misdirection that should be split into named modes + supervisor escalation.

Two load-bearing principles emerged from the dialogue that none of the source docs explicitly named: **two-purpose skills** (Principle 1) and **threshold-grounding** (Principle 2). Both govern decisions across multiple themes and are worth elevating to the framework's CLAUDE.md.

Nine open questions remain (§10). None block Milestone 1 (Tier 0 foundation), which can start immediately on settled work.

---

*End of synthesis. Edits, pushback, and resolutions to open questions welcome.*
