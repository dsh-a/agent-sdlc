# Improvement Synthesis #3

Independent synthesis of the four diagnostic docs in `docs/`:

- **[A]** `anecdote_improvements.md` — felt friction
- **[C]** `cycle-reports-improvements.md` — patterns across 12 cycle reports
- **[K]** `culture-improvements.md` — borrowable ideas from a different framework
- **[X]** `extract-agent-skills.md` — prompt-slimming plan

I did not read syntheses #1 or #2. This is one engineer's independent read.

---

## 1. The unifying critique

There is **one dominant critique** running through all four docs, and a **second, smaller one** that mostly lives in [X] and [A§5].

### Primary critique: the pipeline is open-loop where it should be closed-loop

Every felt pain point in [A], every recurring failure in [C], and the single highest-leverage borrow in [K] (in-flight supervision) reduce to the same shape: **once the orchestrator hands work off, it gets no signal back until the agent either finishes or hits a watchdog.** That open-loop posture is what creates:

- **[C§1] worktree base mismatches** — agents branch from the wrong commit, do real work, and we only learn at merge time. A closed loop catches this at startup.
- **[C§2] verify/review watchdog stalls** — agents are doing work but not writing the report, and we only learn at 600s. A closed loop sees the silence in real time.
- **[C§4] verify gap-fill as a hidden 6th wave** — the test agent ships, we trust it, verify catches the gap, we manually patch. A closed loop has the test agent (or an adversarial sidecar) check itself before declaring done.
- **[C§7] copyWith field drops repeating across 1.51.2 / 1.51.7 / 1.51.13** — the same bug class, three cycles, no learning loop.
- **[C§8/§9] PRD deviations and scope creep going unflagged** — same shape: implementation deviates, nobody hears about it until verify or post-hoc.
- **[C§10] orchestrator silently rescues stalled agents** — the rescue itself is fine; the silence is what breaks `/self-improve`.
- **[A§1–§3] verify/review slowness, test-task slowness, no short-circuiting** — the pipeline can't tier its own depth because it has no feedback mechanism to *decide* depth at runtime.
- **[A§4] conductor-not-script** — explicitly a closed-loop reframe.
- **[K§1–§4] supervision, whispers, context management, formal I/O contracts** — every Culture borrow is a closed-loop primitive.

This is not four problems. It is **one missing capability** (continuous orchestrator ↔ agent observation + correction) showing up at four scales: per-tool-call (whispers), per-task (supervision), per-phase (rescue logging), per-cycle (conductor + self-improve).

### Secondary critique: the framework optimizes for the worst-case story

[A§5] and [X] are the same observation from prompt-shape and runtime-shape angles. The agents carry the worst case in their prompts, the pipeline runs the worst case on every story, and small stories pay the worst-case tax. [A§3] (cycle modes) is the runtime version; [X] is the prompt version. Same critique.

These two critiques are **mostly orthogonal** but they touch in one place: a conductor (primary) is what makes adaptive depth (secondary) actually achievable, because something has to *decide* what depth to run at. Without the conductor, "cycle modes" just becomes another config flag the user has to set correctly.

---

## 2. Convergent recommendations (multiple docs, same fix)

Items where 2+ docs independently propose the same change. Weight these higher.

| Convergent fix | Sources | Strength |
|---|---|---|
| **Closed-loop supervision during Phase 3** (sidecar checks the agent's last K tool calls, can whisper or pause) | [K§1], [K§2], [A§4] (conductor re-evaluates), [C§10] (silent rescues become visible) | Very strong — four angles |
| **Formal agent I/O contracts** (`produces:` / `requires:` in frontmatter, orchestrator validates handoffs) | [K§4], [C§3] (verify report path inconsistency), [X] (mirror-skill drift would fail if contract enforced) | Strong — three angles, including a P0 from [C] |
| **Fold adversarial-tester into Phase 3 by default** (rather than on-demand) | [C§4], [X] roadmap item 9, [A§2] (preflight + structured exit) | Strong — three angles |
| **Orchestrator decides agent depth / shape from story size** | [A§1], [A§3], [A§4] | Strong — three [A] items, same idea |
| **Skill manifest / orchestrator-pre-attached skills replace inline duplication** | [X] entirely, [A§5] | Strong — two docs, full alignment |
| **Mid-flight correction without restart** (whispers) | [K§2], [A§2] (structured contradiction exit is the inverse direction of the same channel) | Medium — same channel, different direction |
| **Run report should record rescues / deviations / scope changes structurally, not in prose** | [C§8], [C§9], [C§10] | Medium — all from [C], but three distinct items |

The first three are the load-bearing convergent items. If only those three ship, most of the friction in [A] and [C] goes away.

---

## 3. Where the docs disagree or sit in tension

### 3.1 Prompt-slimming [X] vs. supervision-adds-overhead [K]

[X] wants every agent prompt smaller. [K§1] wants to add a supervisor sidecar to every Phase 3 agent. These don't actually conflict — supervision adds *cost per cycle*, prompt-slim reduces *cost per agent spawn* — but they pull in opposite directions on total cycle token usage, and the user should be aware that "ship both" still leaves us paying for the supervisor.

**My take:** ship [X] first to bank the savings, then spend a fraction of those savings on [K§1]. Net should still be down or flat.

### 3.2 Conductor [A§4] vs. cycle modes [A§3]

These are in [A] back-to-back but they're not actually compatible solutions to the same problem — they're *competing* solutions.

- **Cycle modes**: declarative, user-picks-at-start, three named presets (`full` / `lean` / `hotfix`). Cheap. Transparent.
- **Conductor**: imperative, orchestrator-decides, dynamic plan per story, re-evaluable mid-cycle. Expensive. Harder to debug.

[A§4] says the conductor is "probably the highest-leverage item in this document." I disagree — at least as a starting point. **Cycle modes are the 80/20 answer.** They get you tiered depth, smaller stories feel small, and they're shippable in a week. The conductor is the *eventual* destination, but it should be built *on top of* the mode system, not instead of it. A conductor that picks between `lean` / `full` / `hotfix` is a much smaller, more constrained problem than one that designs an arbitrary pipeline.

**Recommendation:** ship modes first, treat the conductor as "modes + auto-selection" later. [A§4]'s own risk note ("adaptive orchestrator is harder to debug") confirms this ordering.

### 3.3 Skill manifests [X] vs. agent recognition [A§5]

[X] §"Decision points" surfaces this as an open question; [A§5] proposes two trigger modes (orchestrator-directed and agent-recognized). The tension is real:

- **Orchestrator-directed**: deterministic, easy to test, but the orchestrator now needs to classify every task by "which skills does it need." That logic has to live somewhere and itself grows.
- **Agent-recognized**: cleaner per-agent contract, but [X] correctly notes the open question — does Claude Code's `Skill` tool reliably get invoked mid-task by subagents?

**My take:** orchestrator-pre-attach for the **predictable** axes (task type → scaffold pattern → skill list), agent-recognized for the **content-dependent** axes (e.g., "this AC mentions Drift, load drift-migration"). The hybrid in [A§5] is right; the issue is just labeling which decisions live where. The decision deserves an explicit table in the implementation PRD.

### 3.4 [C§11] "pre-existing analyzer warnings" — flagged as probably-out-of-scope, but it isn't

[C§11] hedges that the slowly-growing analyzer-warning count is "probably out of scope for the framework." I'd push back on that hedge. The framework *already* records analyzer state in every cycle report, and an `analyze_baseline` enforcement gate is exactly the kind of small, mechanical thing the orchestrator should own. Don't punt this to project hygiene. It's three lines of orchestrator logic and one config knob.

### 3.5 [X] mirror-skill fate — bigger than it reads

The "decision point" in [X] ("when an agent slims down, do the mirror skills stay as user-invocable `/test`, `/verify`?") looks small but it's load-bearing. Today, `skills/test/SKILL.md` and `agents/test.md` are partially redundant. If we slim the agent but keep the skill intact, we still have two copies of the truth. If we slim both and have the skill `@include` shared sub-skills, the skill becomes a *thin orchestration layer* — at which point what does it actually do that the agent doesn't?

**My take:** kill the mirror skills as user-invocable surfaces unless they have unique value beyond "run the agent without the orchestrator." If a user wants `/test` standalone, they should get the same agent, not a parallel implementation. Otherwise we've doubled the surface area we have to keep in sync.

---

## 4. What the source docs miss

Items none of the four docs explicitly raise that this synthesis should flag.

1. **No empirical token-cost measurement.** [X] proposes a 53% line-count reduction but says explicitly "we don't currently track per-agent token usage in cycle_reports/." Without that baseline, none of the prompt-slimming ROI claims are verifiable. **Add per-agent input/output token counts to the cycle state file before starting the [X] migration.** Otherwise we're rearranging prompts without knowing whether it helped.

2. **No regression-prevention loop for fixed bugs.** [C§7] notes the same `ExerciseSet.copyWith` bug appearing in 3+ cycles. There's no mechanism in the framework for "we already fixed this once; warn the next agent." A `known-pitfalls/<repo>.md` file that the orchestrator pre-attaches to every implementation agent would handle this for free. Conceptually adjacent to [X]'s skill model but *project-local*, not framework-static.

3. **No measurement of the conductor's actual signal.** If we build [A§4]'s conductor, what's the success metric? "Picked the right mode" how — by post-hoc human grading? Add this to the design or the conductor becomes unfalsifiable.

4. **The "rescues" array [C§10] needs a schema.** Just saying "log rescues" without enumerating the rescue *categories* (stall, worktree-mismatch, watchdog-timeout, contradiction-loop, ...) will produce inconsistent prose that [self-improve] can't analyze. Define the enum at design time.

5. **Gate fatigue isn't named anywhere.** [A§3] talks about "consolidating gates 1C and 2B" for lean mode, but the underlying observation — that the human at the gate is the rate-limiter, not the agents — isn't pulled out as its own theme. Anything that reduces gate count without reducing safety is high-value on a different axis than token cost or wall-clock.

6. **No "graceful degradation" story for when the closed loop itself breaks.** If we add supervision (K§1), what happens when the supervisor stalls? Cascading meta-failure. Worth designing for from day one rather than discovering it.

7. **Cycle reports vs. run reports drift** is a one-line honorable mention in [C], but it's actually the meta-version of the contract problem in [K§4]. The two artifacts have no schema, so categories blur. Same fix (frontmatter contract on the artifact, not just the agent).

8. **Nobody owns "the test agent shipped tests that pass without asserting."** [C§4] and [C§5] are both about this, but they suggest two different fixes (orchestrator spawns adversarial; test agent self-checks). Neither doc reconciles these. My read: do *both*, because they catch different things — adversarial finds semantic gaps, self-check finds syntactic anti-patterns (`if (...isNotEmpty)`). They're complementary, not redundant.

---

## 5. Prioritized roadmap

Five tiers. Within each tier, ordering matters because of dependencies; across tiers, ship one tier mostly before starting the next.

### Tier 0 — Pre-work (must ship before anything else)

These don't change behavior but unblock measurement and consistency. Days of work, not weeks.

| # | Item | Source | Why first |
|---|---|---|---|
| 0.1 | **Per-agent token accounting in cycle state file** | gap | Without this, [X] and [A§1] ROI is unfalsifiable |
| 0.2 | **Rescue-event schema** (enum of categories, struct in state file) | [C§10] + gap | Without this, [self-improve] can't read rescue trends |
| 0.3 | **Frontmatter contract spec** (`requires` / `produces` / `artifact_dir`) on agents AND artifacts | [K§4] + [C§3] | Foundation for handoff validation, conductor, and gate-fatigue work |

### Tier 1 — Stop the bleeding (fix proven recurring failures)

These are P0-equivalent — each addresses a problem that has cost real cycles in the dataset.

| # | Item | Source | Notes |
|---|---|---|---|
| 1.1 | **Fix worktree base mismatch + startup merge-base assertion** | [C§1] | Cited in 5/12 cycles. Mechanical fix. Ship alone. |
| 1.2 | **Enforce verify report path via produces contract** | [C§3] | Requires 0.3 first. |
| 1.3 | **Watchdog-stall salvage pass** (Haiku reads transcript, emits `PARTIAL` report) | [C§2] | Cheap. Closes the silent-rescue gap immediately. |
| 1.4 | **Write-as-you-go for verify/review reports** | [C§2] | Same agents, separate change from 1.3. |
| 1.5 | **Adversarial-tester as default Phase 3.5 step** for every test write | [C§4], [X-9] | Convergent. Spawn at orchestrator level (per [X]'s migration). |
| 1.6 | **Test-agent silent-skip grep gate** (`if (find...isNotEmpty)` etc fail self-check) | [C§5] | Complementary to 1.5, not redundant — catches different failure mode. |

### Tier 2 — Closed-loop primitives (the core architectural shift)

These add the missing observation/correction channels. They depend on Tier 0's contracts.

| # | Item | Source | Notes |
|---|---|---|---|
| 2.1 | **Whisper channel** (`agent_states/whispers/<agent>.md`, agents poll between sub-tasks) | [K§2] | Mechanical; required by 2.2 |
| 2.2 | **Phase 3 supervisor sidecar** (Haiku, reviews last K tool calls, uses Culture's 3-step escalation ladder) | [K§1] | The single largest architectural borrow |
| 2.3 | **Structured "contradiction" exit signal for test agent** (writes question, exits, doesn't thrash) | [A§2] | Uses whisper channel in reverse |
| 2.4 | **Rescues + deviations + scope-changes logged structurally in cycle state** (consumes 0.2's schema) | [C§8] + [C§9] + [C§10] | Three items collapse to one structured-logging change |
| 2.5 | **Handoff validation at every phase boundary** (orchestrator checks `produces:` files exist with expected shape) | [K§4] | Uses 0.3 |

### Tier 3 — Adaptive depth and shape

Once observation works, *vary* the work based on it.

| # | Item | Source | Notes |
|---|---|---|---|
| 3.1 | **Cycle modes** (`full` / `lean` / `hotfix`) declared at `/cycle` invocation | [A§3] | Ships first; conductor builds on this |
| 3.2 | **Verify + review run in parallel** (they don't share state) | [A§1] | Cheap, independent |
| 3.3 | **Per-phase skip flags in config.md** (`skip_verify_if_files_changed_lt: N`) | [A§1], [A§3] | Conservative defaults |
| 3.4 | **Pre-flight test-classification pass** (Haiku enumerates affected tests, classifies keep/update/delete) | [A§2] | Independent of 3.1–3.3 |
| 3.5 | **Conductor mode**: orchestrator picks `full`/`lean`/`hotfix` from feature description, surfaces plan, gate-1A approval | [A§4] | Builds on 3.1; *only* automates mode selection, not arbitrary pipeline design |
| 3.6 | **Mid-cycle plan re-evaluation** (if Phase 3 was clean, downgrade verify depth) | [A§4] | Most ambitious item; depends on 2.4 |

### Tier 4 — Lightweighting [X]

Order is from [X]'s own roadmap. Ship after Tier 0 (so we can measure) and Tier 1.2 (so contracts exist).

| # | Item | Source | Notes |
|---|---|---|---|
| 4.1 | Dedupe `skills/scaffold/SKILL.md` to thin index | [X-4] | Zero behavior change; ship first |
| 4.2 | Create `flutter-conventions` skill | [X-3] | Required by 4.3, 4.4, 4.6 |
| 4.3 | Slim `test.md` + extract `widget-test-patterns`, `ac-audit-rubric` | [X-1] | Convergent with 1.5 (adversarial spawn move) |
| 4.4 | Slim `ui-story.md` + delegate to scaffold/test | [X-2] | |
| 4.5 | Slim `verify.md`, `review.md`, `self-improve.md`, `create-prd.md`, `generate-tasks.md` | [X-5..10] | One PR per agent |
| 4.6 | Centralize autonomous preamble | [X-11] | Hygiene |

### Tier 5 — Hygiene and nice-to-haves

| # | Item | Source | Notes |
|---|---|---|---|
| 5.1 | `analyze_baseline` enforcement in cycle config | [C§11] | Re-scoped from "out of scope" |
| 5.2 | Tag-based scaffold dispatch (`scaffold_kind:` in task files) | [K] honorable | Small win |
| 5.3 | Progress webhook (Discord/Slack on phase_complete) | [K] honorable | Cheap; `monitor` already has the state |
| 5.4 | Bug-triage path for "BUG-005" recurring entries | [C-honorable] | Likely just "append to known-pitfalls and surface in self-improve" |
| 5.5 | Codify what review is allowed to auto-fix vs flag | [C-honorable] | Small clarity win |
| 5.6 | Compact context at Phase 2→3 and 3→4 boundaries | [K§3] | Likely small win; verify with 0.1 first |
| 5.7 | Inline-entity-construction warning in `ui-story` / `scaffold` agent | [C§7] | Project rule, but framework can nudge |

---

## 6. Dependency graph

```
0.1 token accounting ──────────────────► [validates 4.x ROI, 3.x decisions]
0.2 rescue schema ─────────────────────► 2.4, 1.3
0.3 contract spec ─────────────────────► 1.2, 2.4, 2.5, 4.x (helps validate dedup)

1.1 worktree fix       (standalone, ship anytime)
1.2 verify path        ◄── 0.3
1.3 salvage pass       ◄── 0.2
1.4 write-as-you-go    (standalone)
1.5 adversarial default ─► informs 4.3
1.6 silent-skip gate   (standalone)

2.1 whispers           ──► 2.2, 2.3
2.2 supervisor         ◄── 2.1, 0.2 (rescue schema for escalations)
2.3 contradiction exit ◄── 2.1
2.4 structured logging ◄── 0.2, 0.3
2.5 handoff validation ◄── 0.3

3.1 cycle modes        ──► 3.5
3.2 parallel verify/review (standalone)
3.3 skip flags         ──► 3.5
3.4 pre-flight tests   (standalone; informs 1.5/2.3)
3.5 conductor          ◄── 3.1, 3.3, 0.2
3.6 mid-cycle re-eval  ◄── 2.4, 3.5

4.1 scaffold dedup     (standalone, ship first in tier)
4.2 flutter-conventions ──► 4.3, 4.4, 4.5
4.3 test slim          ◄── 4.2, 1.5
4.4 ui-story slim      ◄── 4.2
4.5 other agent slims  ◄── 4.2
4.6 preamble           (standalone)
```

The critical-path items are **0.3 → 2.5** (contracts → validation) and **0.2 → 2.4** (schema → structured rescue logging). Everything in Tier 2 depends on Tier 0.

---

## 7. Open decisions that block work

Items the user must decide before the team can start. Listed in order they'd be needed.

1. **Cycle modes naming and behavior matrix.** [A§3] proposes `full` / `lean` / `hotfix` but the precise behavior of each (which phases run, which agents skip, gate consolidation rules) is the actual design. Needs a table before 3.1 can ship.

2. **Skill invocation model** — orchestrator-pre-attach vs. agent-recognized vs. hybrid. [X]'s open question. Needs an answer before any Tier 4 work beyond 4.1. (My recommendation: hybrid, with explicit decision table — see §3.3.)

3. **Mirror skill fate** ([X] decision point). My recommendation: kill them as parallel surfaces; if users want them as slash commands, they should invoke the same agent. But this is a UX decision, not purely technical.

4. **Conductor scope.** Per §3.2: is the conductor allowed to design arbitrary pipelines, or only choose between named modes? My recommendation: only choose between modes — restrict the search space.

5. **Supervisor cadence and model** for [K§1]. "Every N tool calls" — what's N? "Haiku-level" — Haiku 4.5 or smaller? Token budget per supervisor pass? Needs concrete numbers.

6. **Contradiction exit destination.** When the test agent ([A§2]) hits a contradiction, who hears about it? The orchestrator (escalation to user) or the supervisor (whisper attempt at resolution first)? Affects 2.2 vs 2.3 design.

7. **Adversarial-tester default-on cost.** [C§4] proposes spawning adversarial after *every* test write. That doubles the post-test budget. Acceptable? Or is it conditional ("if test file > N lines" or "if AC count > M")?

8. **Bug-triage destination.** [C-honorable] says "pipe BUG-XXX entries somewhere." Where — `documentation/BUGS.md`? GitHub issues via `gh`? A new `cycle_bugs/` artifact? Affects 5.4.

9. **Analyzer baseline mechanism.** Hard-fail the cycle, soft-warn, or just record? [C§11]/5.1.

---

## 8. What I'd argue is overweighted in the source docs

A senior reviewer wrote these; I'm not going to pretend everything balances perfectly. Three calls:

1. **[X]'s 53% line-reduction headline is misleading as a savings claim.** Lines are not tokens. A 50-line table consumes very different tokens than 50 lines of prose. And the *load-bearing* tokens at spawn time are the task context (PRD + AC + relevant files), not the agent prompt. Until 0.1 is in place, treat [X]'s savings as "directionally good" not "53% cheaper." The *real* benefit of [X] is **drift reduction** (one canonical place for each convention) more than **token reduction**. Reframe accordingly.

2. **[A§4] conductor is positioned as "highest-leverage."** I'd argue the convergent item (closed-loop supervision per [K§1]) is higher leverage because it addresses the larger surface area of failure modes, and it's a *prerequisite* for an effective conductor anyway (the conductor needs to see what's happening to re-plan). The conductor is the *eventual* highest-leverage item; supervision is the *next* highest-leverage item.

3. **[K§3] context management via `/compact` at phase boundaries** is presented as low-cost wisdom but it's actually a behavior change with second-order effects (loses the orchestrator's working memory of why it made earlier decisions). I'd verify with 0.1 measurement before adopting — it may not actually save much, and it might cost decision-continuity that you don't notice until something goes wrong.

---

## 9. Suggested milestone shape

If I were splitting this into shippable milestones:

- **M1 — Foundations (1–2 weeks):** Tier 0 + Tier 1.1 + Tier 4.1. Measurement in place, worst process bug fixed, free dedup win.
- **M2 — Stop the bleeding (1 week):** Tier 1.2–1.6. All known recurring failures get explicit fixes.
- **M3 — Closed loop (2–3 weeks):** Tier 2. The architectural shift. Single biggest investment.
- **M4 — Lightweighting (2 weeks, parallel with M3 if staffing allows):** Tier 4. Independent of Tier 2 as long as 0.3 ships.
- **M5 — Adaptive shape (2 weeks):** Tier 3. Now that we can observe and we have lighter agents, we can vary depth meaningfully.
- **M6 — Hygiene (ongoing):** Tier 5 items folded into appropriate cycles.

If only M1 + M2 ship, the framework is materially better. If M1 + M2 + M3 ship, the framework is *qualitatively* different (open-loop → closed-loop). Everything past M3 is optimization on top of an already-better baseline.

---

## 10. Quick reference — collapsed item list

Every recommendation from the four docs, mapped to a tier. Items that were duplicated across docs appear once.

- [C§1] worktree fix → **1.1**
- [C§2] watchdog stalls → **1.3, 1.4**
- [C§3] verify path → **1.2** (needs 0.3)
- [C§4] verify gap-fill → **1.5** (+ informs 4.3)
- [C§5] silent-skip patterns → **1.6**
- [C§6] mocktail/stub divergence → **5.5** (codify as auto-fix-vs-flag rule)
- [C§7] copyWith drops → **5.7** + **gap-2** (regression prevention loop)
- [C§8] PRD deviations → **2.4**
- [C§9] mid-cycle scope creep → **2.4**
- [C§10] silent rescues → **2.4** (needs 0.2)
- [C§11] analyzer baseline → **5.1**
- [C-honorable] run vs cycle report → **0.3** (contract on artifacts)
- [C-honorable] review auto-fix scope → **5.5**
- [C-honorable] bug triage → **5.4**
- [A§1] verify/review slowness → **3.2, 3.3**
- [A§2] test slowness → **3.4, 2.3, separate budget cap (sub-item of 3.3)**
- [A§3] cycle modes → **3.1**
- [A§4] conductor → **3.5, 3.6**
- [A§5] prompt overhead → **Tier 4**
- [K§1] supervision → **2.2**
- [K§2] whispers → **2.1**
- [K§3] context compaction → **5.6**
- [K§4] I/O contracts → **0.3** + **2.5**
- [K-honorable] circuit breaker → folded into **2.2**
- [K-honorable] tag-based dispatch → **5.2**
- [K-honorable] webhook → **5.3**
- [X-1] slim test.md → **4.3**
- [X-2] slim ui-story.md → **4.4**
- [X-3] flutter-conventions skill → **4.2**
- [X-4] scaffold skill dedup → **4.1**
- [X-5..8] other agent slims → **4.5**
- [X-9] orchestration migration → folded into **1.5**
- [X-10] generate-tasks slim → **4.5**
- [X-11] autonomous preamble → **4.6**
- [X-12] adversarial-patterns skill → **4.5**

No source-doc recommendation is dropped; a few are consolidated (the three [C] structured-logging items collapse to one, the four [K] honorable mentions distribute across tiers, the various [X] slims merge into one PR-per-agent stream).
