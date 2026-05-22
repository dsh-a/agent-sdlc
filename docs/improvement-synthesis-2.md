# Improvement Synthesis (v2)

Independent read of the four source docs. Tags trace recommendations back:

- **[A]** = `anecdote_improvements.md`
- **[K]** = `cycle-reports-improvements.md` (K for "kanban-of-incidents")
- **[C]** = `culture-improvements.md`
- **[X]** = `extract-agent-skills.md`

---

## TL;DR

The four docs are not four equal critiques. They line up as:

- **One operational bug** that is by far the most damaging single thing in the system: worktree base-mismatch **[K1]**. Ship the fix this week; nothing else here is hard-blocked by it but everything else is harder to measure while it's still happening.
- **One convergent architectural shift**: from a fixed script to a *conductor* with *in-flight supervision* and *typed agent contracts*. This is the union of **[A4]**, **[A5]**, **[C1]**, **[C2]**, **[C4]**, **[K10]**, **[K3]**, **[X]**. Four docs all want the orchestrator to be smarter and the agents to be leaner — but each describes a different facet. Treat as one program of work, sequenced.
- **One systemic test-quality problem**: verify is doing real work, the `test` agent is shipping coverage-by-presence, and adversarial-tester exists but is not in the default loop. **[K4]**, **[K5]**, **[K6]**, **[A2]** all point at this. Cheap to fix relative to the architectural work.
- **A handful of small wins**: deviations field on implementer handoffs **[K8]**, rescue logging **[K10]**, recurring-bug surfacing **[K7]**, analyzer baseline **[K11]**.

If I had three weeks: week 1 fixes worktree + folds adversarial-tester into Phase 3 + ships canonical artifact paths. Week 2 ships typed agent contracts + rescue logging + per-agent token tracking. Week 3 starts the conductor refactor (the lean/hotfix modes, not the full adaptive orchestrator).

The skill-extraction plan **[X]** is correct but lower priority than its own internal urgency suggests — see "Where I'd push back" below.

---

## Underlying critique

There's one critique with three faces:

> **The framework is optimized for the worst-case story and treats every story as if it were that one.**

- **Shape** — every story gets the same 7-phase pipeline regardless of size **[A3]**.
- **Depth** — every story gets `verify` + `review` at max effort regardless of risk **[A1]**.
- **Context** — every spawned agent pays for the full system prompt regardless of whether the embedded rules apply **[A5][X]**.

All three feed the same outcome: small stories feel disproportionately expensive, large stories feel under-supervised (because the supervision is at the wrong granularity — phase boundaries, not turn-level).

The *secondary* critique, which is operational rather than architectural: **the framework hides its own failures.** Orchestrator rescues are invisible **[K10]**. Verify reports go missing **[K3]**. Worktree mismatches get silently worked around **[K1] 1.51.5**. Recurring bugs get logged 3+ times without resolution **[K7]**. The pipeline runs well-lit only when nothing goes wrong; everything that does go wrong is repaired in the dark.

These two critiques are independent. You could fix the operational opacity without making the orchestrator adaptive, and vice versa. But the adaptive orchestrator **[A4]** is only debuggable if the opacity is fixed first — so the operational items are not just P0 in isolation, they are unblockers for the architectural work.

---

## Themes (clustered across docs)

### Theme 1 — Operational visibility (no architecture changes)

| # | Item | Source | Notes |
|---|---|---|---|
| 1.1 | Fix worktree base-branch logic | [K1] | 5/12 cycles. Most-cited single bug. |
| 1.2 | Canonical artifact paths enforced on exit | [K3][C4] | Verify reports go to one path, validated by orchestrator. |
| 1.3 | Watchdog → incremental write + salvage pass | [K2] | Append-as-you-go, Haiku salvage if stall. |
| 1.4 | `rescues: []` log in cycle state | [K10] | Categorize: stall, worktree-mismatch, watchdog, scope-creep. |
| 1.5 | Per-agent token + wall-clock tracking | [X open Q][A1] | Prerequisite for measuring everything else. The docs treat this as an aside; I'd promote it. |

**Convergence**: 1.2 and 1.4 are the same mechanism (orchestrator validates agent output, logs deviations). 1.5 is the missing instrumentation that makes 1.3, 1.4, and any future tuning measurable.

### Theme 2 — Test-quality reinforcement

| # | Item | Source | Notes |
|---|---|---|---|
| 2.1 | Make adversarial-tester default for every test file | [K4][A2 indirectly] | Currently exists but rarely invoked. |
| 2.2 | Ban conditional assertions in test agent self-check | [K5] | `if (finder.isNotEmpty) expect(...)` patterns fail their own check. |
| 2.3 | Migrate-or-flag policy when test patterns diverge | [K6] | Either migrate old tests in same commit or surface the split. |
| 2.4 | Pre-flight test-reconciliation pass | [A2] | Cheap classify-as-keep/update/delete before `test` agent runs. |
| 2.5 | Explicit "contradiction" exit signal in test agent | [A2] | Stop thrashing; emit structured question. |

**Convergence**: 2.1 and 2.4 are alternative fixes for the same failure mode (test agent under-rigor + over-thrashing). 2.4 is preventative (cheaper, before the agent runs); 2.1 is corrective (after the agent runs). Do *both* — they catch different failure modes. 2.4 prevents thrashing; 2.1 catches coverage-by-presence.

**Tension**: 2.1 increases the agent count per cycle (adversarial after every test write). 2.5 reduces it (test agent stops earlier on contradiction). Net is probably neutral on token cost, very positive on correctness.

### Theme 3 — Adaptive shape (conductor pattern)

| # | Item | Source | Notes |
|---|---|---|---|
| 3.1 | Cycle modes: `full` / `lean` / `hotfix` | [A3] | User-selected at invocation. |
| 3.2 | Per-phase skip flags in config | [A3] | E.g. `skip_verify_if_files_changed_lt: 3`. |
| 3.3 | Conductor: shape the cycle from the story | [A4] | Orchestrator decides which phases/agents/depth up front. |
| 3.4 | Run verify + review in parallel | [A1] | They don't share state. Easy win. |
| 3.5 | Tiered verify/review depth | [A1] | Lite vs. full based on size/risk signals. |
| 3.6 | Gate consolidation in lean mode | [A3] | 1C + 2B collapse to one approval. |

**Convergence**: 3.1, 3.2, 3.3 are a progression — same goal (don't pay full cost for small stories) at increasing levels of mechanism. Ship 3.1 first (cheap, user-explicit), then 3.2 (config-driven, still explicit), then 3.3 (orchestrator-inferred, the hard one).

**Open decision** (see Open Questions): do we want the conductor to *infer* the mode (3.3) or do we want the user to always declare it (3.1)? My read: declared-by-default with an inferred *suggestion*, never silent inference. The docs lean toward inference; I'd be more conservative.

### Theme 4 — Mid-flight supervision

| # | Item | Source | Notes |
|---|---|---|---|
| 4.1 | Haiku supervisor checks every N tool calls | [C1] | Detect SPIRALING/DRIFT/STALLING/SHALLOW. |
| 4.2 | Escalation ladder for supervisor: whisper → strong whisper → pause+alert | [C1] | Verbatim from culture. |
| 4.3 | Whisper channel — `agent_states/whispers/<agent>.md` | [C2] | Agent checks between sub-tasks. |
| 4.4 | Circuit breaker — "3 failures in 5 min → stop" | [C honorable] | Probably implicit already; formalize. |

**Convergence**: 4.1, 4.2, 4.3 are one feature. Don't ship them separately — a supervisor without a whisper channel can only alert, and a whisper channel without a supervisor has nothing to write.

**Tension with Theme 5 (extraction)**: a Haiku supervisor reading the last K tool calls between sub-tasks adds latency and tokens. It's net positive *if* the implementation agents are slimmer (Theme 5) and *if* the worktree bugs are fixed (1.1) so the supervisor isn't catching downstream effects of an upstream bug.

### Theme 5 — Lean agents + on-demand skills

| # | Item | Source | Notes |
|---|---|---|---|
| 5.1 | Typed agent frontmatter: `requires:`, `produces:`, `artifact_dir:` | [C4] | Enables 1.2 (orchestrator validates handoffs). |
| 5.2 | Skill-extraction roadmap — HIGH items | [X] | `test.md`, `ui-story.md`, `flutter-conventions`, scaffold dedup. |
| 5.3 | Skill-extraction roadmap — MEDIUM items | [X] | `verify.md`, `review.md`, `self-improve.md`, `create-prd.md`. |
| 5.4 | Centralize autonomous preamble | [X] | ~18 lines, hygiene win. |
| 5.5 | Move orchestration concerns out of agents (`scaffold` spawn, `test→adversarial` spawn) | [X] | Pairs with Theme 4. |
| 5.6 | Context compaction at phase boundaries | [C3] | `/compact` at Phase 2→3, 3→4. |

**Convergence**: 5.1 (typed contracts) is the same change required by 1.2 (validated handoffs). They are the same PR with different motivations.

**Convergence with Theme 3**: a conductor (3.3) that "decides the shape" must know what each agent does and produces — i.e. it needs typed contracts (5.1). So 5.1 is also a prerequisite for the conductor.

**Tension**: 5.2 wants smaller agent prompts. **[A5]** also wants smaller prompts. But **[K8]** wants *more* fields on implementer handoffs (deviations) and **[K7]** wants more fields again (recurring-bug awareness). These are not contradictory in token-budget terms — adding output fields is cheap; trimming static reference material is the big win — but be honest that "lean agents" is a slogan that covers two distinct trims (input prompt, output report) which have different cost profiles.

### Theme 6 — Cross-cycle memory

| # | Item | Source | Notes |
|---|---|---|---|
| 6.1 | Surface recurring bugs to self-improve | [K7] | `ExerciseSet.copyWith` logged 3+ times, no cycle to fix. |
| 6.2 | Triage path for bugs discovered in cycle reports | [K honorable] | Bugs go in, nothing comes out. |
| 6.3 | Analyzer baseline gate | [K11] | Optional; monotonically decrease. |
| 6.4 | Deviations field on implementer handoff | [K8] | Differences between PRD and impl, surfaced to user. |
| 6.5 | Mid-cycle scope changes logged structurally | [K9] | Currently prose only. |

**Convergence**: 6.1, 6.2, 6.5 all want the cycle/run reports to feed back into something — currently they are write-only. The cheapest fix is a single `documentation/bugs.md` aggregator + a `self-improve` pass that reads it monthly. Don't over-engineer (no ticket system in the framework).

---

## Where the docs disagree or are in tension

### T1 — Lean prompts vs. richer agent contracts

[A5] and [X] want agents to be smaller (less input prompt overhead). [K8], [K9], [C4] want agents to produce *more* structured output (deviations, scope changes, typed handoffs). These don't actually conflict, but they could be conflated by a casual reader. **Be clear in roadmap PRs which dimension is being trimmed/grown.** Input prompt is the cost center; output structure is the leverage point.

### T2 — Conductor pattern vs. explicit user modes

[A4] proposes an orchestrator that *infers* shape from the story. [A3] proposes user-declared modes. The doc treats these as escalating sophistication of the same idea. I disagree. **User-declared modes are not inferior to inferred modes — they are more debuggable.** An inferred mode that gets it wrong is a worse failure than a wrong mode the user declared explicitly. Ship 3.1 (user-declared) before 3.3 (inferred), and even after 3.3 ships, keep the user-declared override as a first-class path.

### T3 — Supervisor cadence vs. token cost

[C1] proposes a Haiku check every N tool calls. [A5] / [X] are simultaneously trying to *reduce* per-spawn token cost. A naive supervisor implementation could swallow the savings. **Mitigation**: the supervisor is cheap-per-call (Haiku, short context), but it scales with implementation-agent verbosity. Slimmer agents (Theme 5) make Theme 4 cheaper. So sequence Theme 5 before Theme 4 if budget is the concern; or ship Theme 4 first if correctness is.

### T4 — Skip-verify-on-small-stories vs. verify-catches-real-bugs

[A1] suggests skipping or "lite-ing" verify on small stories. [K4] shows verify is consistently surfacing real test gaps that would otherwise ship. **Tension**: skipping verify on small stories means small stories ship with the bad tests verify would have caught. Resolution: a "lite" verify pass (AC-coverage-only, no architecture audit) is fine; *skipping* verify on anything that touches tests is dangerous given the test-quality data in [K4]. Encode the rule as "skip if files changed < N **and** no test files touched."

### T5 — Mirror-skill fate

[X] §"Open questions" asks whether `skills/test/`, `skills/verify/`, etc. should remain as user-invocable slash commands. **My take**: yes, keep them, but invert the relationship — make the agent prompt `@include` the skill instead of duplicating it. The slash-command surface is genuinely useful for one-off invocations outside `/cycle`. Don't sacrifice that to optimize per-spawn tokens.

---

## Gaps in the source docs

Things none of the four docs cover that I'd flag:

1. **Per-agent telemetry is the prerequisite for everything**. [X] flags it as an open question. [A1] hints at it. But no doc treats it as a P0 — and without it, "did verify get faster?" "did skill extraction save tokens?" "is the conductor making the right calls?" are all unanswerable. **Add per-agent token + wall-clock + tool-call-count fields to the run report. This is one day of work and unlocks all measurement.**

2. **No story-of-rollback**. What happens when a cycle ships code that breaks something post-merge? `documentation/CHANGELOG.md` is append-only. The framework has no "revert this cycle" concept. Not urgent, but worth a one-line acknowledgement that the SDLC pipeline ends at merge and post-merge bugs go into the next cycle as new features rather than as rollback.

3. **No mention of secrets/credentials handling**. Agents have `Bash` permissions and run autonomously. There's no doc on what happens if an agent encounters `.env` or `credentials.json`. Probably fine in practice because the system prompts don't direct them there, but worth one sentence in the agent base prompt.

4. **Test fixtures**. [K6] shows the test agent re-creates `_StubViewModel` alongside existing mocktail mocks. The deeper issue isn't pattern divergence — it's that test fixtures aren't versioned or shared in any structured way. A `test/fixtures/` discoverability convention (or just a `test/CLAUDE.md` index) would help.

5. **Multi-feature parallelism**. The pipeline assumes one active cycle at a time. The state-file naming (`cycle-state-[feature-name].md`) supports multiple, but nothing in the orchestrator handles "what if there are two active cycles." Not urgent, but the docs don't acknowledge it.

6. **The conductor's risk**. [A4] flags that an adaptive orchestrator is harder to debug. It does not flag the worse risk: **an adaptive orchestrator that's wrong on small stories is invisible**. If the conductor decides "this is a hotfix, skip verify" and it was actually a regression-prone change, the user finds out post-merge. The mitigation isn't just "log the decision" (the doc's suggestion) — it's "always preserve the option to upgrade mode mid-cycle, and surface that option to the user at the dry-run plan."

7. **Skill discoverability — concrete mechanism**. [A5] flags this as the hard problem ("if a skill exists but the agent doesn't know to load it, the rule isn't enforced") and [X] proposes "orchestrator pre-attaches based on task type." But the actual *trigger logic* — how the orchestrator decides "this task needs `drift-migration`" — is unspecified. This is the load-bearing detail. Two options:
   - **Static map**: `task.touches_files matching lib/data/database/` → load `drift-migration`. Simple, works for ~80% of cases.
   - **Pre-digest classification**: the pre-digest agent (already in the pipeline) returns a `skills_needed: [...]` field. Slower but generalizes.
   I'd start with static map and only escalate to classification if it proves insufficient.

---

## Prioritized roadmap

Read this as **what to ship and in what order**, not as a fixed Gantt.

### Milestone 0 — Stop the bleeding (1 week)

**Goal**: kill the largest observable bug class and get telemetry. Nothing here is architectural.

| Item | Source | Effort | Why now |
|---|---|---|---|
| 0.1 Fix worktree base-branch in `cycle/SKILL.md` | [K1] | S | 5/12 cycles. Blocks measuring anything else. |
| 0.2 Add merge-base assertion in every implementation agent startup | [K1] | S | Defense-in-depth. |
| 0.3 Add `rescues: []` array to cycle state, emit on every silent substitution | [K10] | S | Makes the framework's failures visible. |
| 0.4 Add per-agent token + wall-clock + tool-call count to run report | gap #1 | S | Prereq for measuring everything below. |
| 0.5 Run verify + review in parallel | [A1] | XS | Cheap. Half the wrap-up wall time. |

Dependencies: 0.4 should land before or with 0.1 so we can confirm the worktree fix worked. Everything else parallel.

### Milestone 1 — Fix the test-quality regression (1 week)

**Goal**: stop the "wave-4 verify gap-fill" pattern. Test agents ship rigorous tests.

| Item | Source | Effort | Why now |
|---|---|---|---|
| 1.1 Fold adversarial-tester into Phase 3 default flow | [K4] | M | Orchestrator spawns after every `test` agent. |
| 1.2 Test-agent self-check: ban conditional assertion patterns | [K5] | S | grep gate at agent exit. |
| 1.3 Pre-flight test-reconciliation Haiku pass | [A2] | M | Classifies existing tests as keep/update/delete before `test` runs. |
| 1.4 "Contradiction" exit signal in `test` agent | [A2] | S | Halt + emit question instead of thrash. |
| 1.5 Migrate-or-flag policy for divergent test patterns | [K6] | S | Document in `test` agent prompt. |
| 1.6 Watchdog → incremental write + Haiku salvage | [K2] | M | Stop losing verify/review reports. |
| 1.7 Canonical artifact paths enforced at agent exit | [K3] | S | Pairs with 5.1 (typed contracts) but can ship standalone. |

Dependencies: 1.1 depends on adversarial-tester being callable from orchestrator (already is). 1.6 should land before any conductor work that would skip verify on small stories.

### Milestone 2 — Typed contracts + structural handoffs (1 week)

**Goal**: agents declare what they consume and produce. Orchestrator validates. Pre-req for conductor work.

| Item | Source | Effort | Why now |
|---|---|---|---|
| 2.1 Add `requires:` / `produces:` / `artifact_dir:` frontmatter to all agents | [C4] | M | One PR across all 10 agents. |
| 2.2 Orchestrator validates produces-file-exists at agent exit | [C4][K3] | S | Pairs with 1.7. |
| 2.3 Deviations field on implementer handoff | [K8] | S | Implementer enumerates PRD↔impl differences. |
| 2.4 Mid-cycle scope changes logged structurally | [K9] | S | Add to cycle state, surface to verify. |
| 2.5 Tag-based dispatch: task files declare `scaffold_kind:` | [C honorable] | M | Orchestrator dispatches directly. |
| 2.6 Aggregate bugs into `documentation/bugs.md` with `seen_in: [cycle-ids]` | [K7][K honorable] | S | Surfaces recurring patterns to self-improve. |

Dependencies: 2.2 depends on 2.1. 2.6 standalone.

### Milestone 3 — Cycle modes (user-declared) (1 week)

**Goal**: small stories pay small cost. User picks mode at invocation.

| Item | Source | Effort | Why now |
|---|---|---|---|
| 3.1 Implement `--mode lean` / `--mode hotfix` flags | [A3] | M | Skips PRD generation / gate consolidation / single agent. |
| 3.2 Per-phase skip flags in `config.md` (`skip_verify_if_files_changed_lt: N`) | [A3] | S | Conservative defaults. |
| 3.3 Gate consolidation: lean mode collapses 1C + 2B | [A3] | S | One approval. |
| 3.4 Tiered verify (`--lite` flag): AC-coverage only | [A1] | M | For small stories or explicit opt-in. |
| 3.5 Context compaction at phase boundaries (`/compact` 2→3, 3→4) | [C3] | S | Reduces orchestrator drift. |

Dependencies: 3.4 must respect rule from T4: never skip verify when test files touched. 3.2 needs 0.4 (telemetry) to validate the heuristics.

### Milestone 4 — In-flight supervision (1–2 weeks)

**Goal**: catch agent spirals during Phase 3, not at wrap-up.

| Item | Source | Effort | Why now |
|---|---|---|---|
| 4.1 Whisper channel: `agent_states/whispers/<agent>.md` | [C2] | M | Foundation for supervisor. |
| 4.2 Implementation agents check whisper file between sub-tasks | [C2] | S | One line in agent prompt. |
| 4.3 Haiku supervisor: read last K tool calls every N intervals | [C1] | L | Detects SPIRALING/DRIFT/STALLING/SHALLOW. |
| 4.4 Escalation ladder: whisper → strong whisper → pause + alert | [C1] | M | Verbatim from culture. |
| 4.5 Formalize circuit breaker (already implicit) | [C honorable] | S | 3 failures in 5 min → stop. |

Dependencies: 4.3 depends on 4.1 + 4.2. 4.5 standalone but cheap.

### Milestone 5 — Skill extraction (1–2 weeks)

**Goal**: trim agent prompts. Lower per-spawn token cost.

| Item | Source | Effort | Why now |
|---|---|---|---|
| 5.1 Dedupe `skills/scaffold/SKILL.md` (343 → 50, index-only) | [X HIGH #4] | S | Zero behavior change. Ship first to validate Skill-loading model. |
| 5.2 Slim `test.md` to ~60 lines, extract `widget-test-patterns` + `ac-audit-rubric` | [X HIGH #1] | M | Highest-frequency agent. |
| 5.3 Slim `ui-story.md` to ~75 lines, delegate to `scaffold` + `test` skills | [X HIGH #2] | M | Second-highest leverage. |
| 5.4 Create `flutter-conventions` skill | [X HIGH #3] | M | Kills ~80 lines of cross-agent duplication. |
| 5.5 MEDIUM items in [X] | [X MEDIUM] | M each | After HIGH ships and is measured. |
| 5.6 Centralize autonomous preamble | [X LOW] | XS | Hygiene. |

Dependencies: **5.1 must ship and be measured (per-spawn token cost before/after) before the rest.** This is the empirical test of [X]'s thesis. If it doesn't show savings, the rest of [X] needs rethinking. Per-agent telemetry (0.4) is the prerequisite.

### Milestone 6 — Conductor (2–3 weeks, research-heavy)

**Goal**: orchestrator shapes the cycle from the story.

| Item | Source | Effort | Why now |
|---|---|---|---|
| 6.1 Orchestrator reads story up-front, proposes cycle plan in dry-run | [A4] | L | Plan = phases + agents + depth + skills. |
| 6.2 Plan revision logging in cycle state | [A4] | S | Every mid-cycle change recorded. |
| 6.3 Mode inference (suggest lean/hotfix to user) | [A4][A3] | M | Suggestion, not silent. |
| 6.4 Dynamic verify/review depth from Phase 3 signals (retry count, files changed) | [A4][A1] | L | Adaptive depth. |

Dependencies: 6.1 needs 5.1 (typed contracts), 0.4 (telemetry), 1.x (test quality fixed — otherwise the conductor learns from a broken baseline). 6.4 needs 0.4.

---

## Dependency graph (compressed)

```
0.4 telemetry ─┬─→ 3.2 skip heuristics
               ├─→ 5.1 skill dedup measurement
               └─→ 6.4 dynamic verify depth

0.1 worktree fix ──→ everything else can be measured cleanly

2.1 typed contracts ─┬─→ 2.2 handoff validation (= 1.7)
                     ├─→ 5.x skill extraction (cleaner if agent contract is typed)
                     └─→ 6.1 conductor needs agent contracts

1.6 watchdog fix ──→ 3.4 lite-verify (don't ship lite if reports still vanish)

4.1 whisper channel ──→ 4.3 supervisor (no point without channel)

5.1 scaffold skill dedup ──→ 5.2/5.3/5.4 (validates extraction model)
```

The critical path is short: **0.1 → 0.4 → 2.1 → (5.x parallel, 1.x parallel, 3.x parallel) → 6.x**. Milestone 4 (supervision) is parallel to almost everything but most useful after Milestone 1.

---

## Open questions (need user input before sequencing)

1. **Conductor scope** — inferred vs. user-declared modes? My recommendation is user-declared first, inferred-as-suggestion second, silent-inference never. The docs lean further toward silent inference than I would. **Decide before Milestone 6.**

2. **Skill invocation mechanism** — [X open question] does the Skill tool reliably get invoked mid-task by sub-agents, or only at top of conversation? **This is a Claude Code platform question that gates the entire skill-extraction roadmap.** Need to measure before Milestone 5 starts. If only top-of-conversation, the orchestrator must pre-attach (the [X] doc anticipates this).

3. **`--lite` verify scope** — what does verify-lite skip? My proposed rule: skip live-widget-tree audit, skip golden-review, skip non-functional audit. Keep AC-coverage and adversarial-pattern. **Decide before Milestone 3.4.**

4. **Mirror-skill fate** — keep `/test`, `/verify`, `/review` as user-invocable slash commands? My read: yes, but make them `@include` the extracted sub-skills. **Decide before Milestone 5.2.**

5. **Recurring-bug surfacing** — does `self-improve` get a new "recurring bugs" input source, or does the framework take a position that this is project-side (i.e. project bugs.md owned by user, not framework)? The docs are ambiguous. I lean framework-side: aggregate, surface, but don't fix.

6. **Analyzer baseline gate [K11]** — is this framework or project? [K] flags it as probably-out-of-scope. I agree but the optional config flag is cheap (~20 lines of `cycle/SKILL.md`); ship it as opt-in if it costs that little. Decide via cost-of-implementation, not principle.

7. **Conductor's small-story failure mode** — see gap #6 above. If we ship the conductor (Milestone 6), do we add a "user can upgrade the mode mid-cycle" mechanism? I think yes; the docs don't address it.

---

## Where I'd push back on the source docs

- **[X] extract-agent-skills is overweighted by its own urgency.** It's well-structured and the analysis is sound, but the *measured* benefit is "per-spawn token cost drops substantially" — and we don't currently measure per-spawn token cost. Doing [X] before instrumenting (0.4) means we ship a 1-week refactor without ability to confirm it worked. Land per-agent telemetry first, dedupe `skills/scaffold/SKILL.md` (zero behavior change) as the empirical canary, then commit to the rest.

- **[A1] tier-the-depth on verify/review may be solving the wrong problem.** The data in [K4] shows verify is doing real work — the "wave-4 gap-fill" pattern means verify catches things that would otherwise ship. If we tier verify down on small stories, we ship the bugs verify would have caught, *on the small stories where the user is least likely to notice them in review*. The right fix is faster verify (parallel — 0.5), not lite verify. Use lite-verify sparingly and never on test-touching changes.

- **[C1] supervisor pattern is the highest-leverage culture item, agreed, but [C] overstates how directly it ports.** Culture's daemons are long-lived and have history; our worktreed sub-agents are turn-shallow. A per-N-tool-call supervisor catches a *different* failure mode than Culture's — it catches "I am re-editing the same file" rather than "I am drifting from my purpose." Both are useful, but be honest about what we're getting.

- **[K11] analyzer warnings.** The doc itself calls this out-of-scope; I'd actually argue *strongly* out-of-scope. Framework should not be opinionated about whether a project has clean `flutter analyze`. Make it a one-line opt-in config and otherwise leave alone.

- **[A4] conductor framed as "highest-leverage."** True in isolation, but it's also the highest-risk and the longest critical path. It's correctly the *last* big item, not the first. The docs are framing it as a north star, which is right; an inexperienced reader might mistake that for "start here," which would be wrong.

- **None of the docs mention the relationship between the conductor and the supervisor.** A conductor decides the shape up front; a supervisor catches in-flight drift. They are complementary but they overlap at one decision: "should I upgrade verify depth because Phase 3 had 6 retries?" Both could make that call. I'd give it to the supervisor (mid-flight, has actual data) not the conductor (upfront, predicting).

---

## One-screen executive plan (for skim)

**Now (week 1)**: worktree fix, telemetry, rescue logging, parallel verify+review.

**Then (week 2)**: adversarial-tester in default flow, test-agent self-check, watchdog incremental write, canonical paths.

**Then (week 3)**: typed agent contracts, deviations field, bug aggregation.

**Then (week 4)**: cycle modes (`--mode lean` / `--mode hotfix`), per-phase skip flags, lite-verify.

**Then (weeks 5–6)**: whisper channel + Haiku supervisor + escalation ladder.

**Then (weeks 6–7)**: skill extraction (scaffold dedup canary first, then HIGH items).

**Then (weeks 8–10)**: conductor (plan-up-front, plan-revision logging, mode inference as suggestion).

The first three weeks deliver ~70% of the observable user value at ~10% of the architectural risk. Don't reorder. Specifically: don't start the conductor before the test-quality fixes ship, because the conductor will be making depth decisions on a baseline that's still under-rigorous.
