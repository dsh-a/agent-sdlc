# Agent-SDLC Improvement Synthesis (Round 1)

**Date:** 2026-05-16
**Sources:**
- `docs/anecdote_improvements.md` — user-felt friction (cited as **A**)
- `docs/cycle-reports-improvements.md` — patterns from 12 cycle reports, 1.51.x–2.1.x (cited as **C**)
- `docs/culture-improvements.md` — borrowable ideas from agentculture/culture (cited as **K**)
- `docs/extract-agent-skills.md` — agent-prompt lightweighting analysis (cited as **X**)

This synthesis collapses 4 documents into one prioritized plan. Every recommendation traces back to at least one source via the **A/C/K/X** tags above. Where multiple sources converge on the same fix, it is called out as **convergent** and ranked higher.

---

## 1. Unifying critique

Read together, the four documents describe a pipeline with four interlocking weaknesses:

1. **Fixed shape, fixed cost.** Every story — typo fix to multi-layer rewrite — pays the same orchestration overhead, runs the same gates, spawns the same agents at the same depth (**A3, A4**). The framework optimizes for the worst-case story and bills it on every story.
2. **No mid-flight feedback loop.** Once an agent is spawned, it is invisible until exit. Stalls (**C2**), worktree drift (**C1**), test thrashing (**A2**), silent scope creep (**C9**), and silent rescues by the orchestrator (**C10**) all happen below the waterline. Culture's supervisor + whisper model (**K1, K2**) is the missing piece.
3. **Implicit contracts.** Verify report paths vary across cycles (**C3**), test patterns diverge inside the same directory (**C6**), deviations from PRD surface only at review (**C8**), and the orchestrator "rescues" agents without an audit trail (**C10**). Culture's formal I/O contract (**K4**) would make every handoff machine-checkable.
4. **Prompt bloat compounding the above.** Agent prompts have grown ~1,283 lines across 10 files with heavy duplication against their mirror skills (**X**). Every cycle spawns 5–15 agents — each pays full prompt token cost for context it mostly doesn't need (**A5**). Bloated prompts also leave less room for the actual task context, which is exactly what test/verify/review struggle with.

**The four weaknesses reinforce each other:** bloated prompts → confused agents → silent thrashing → no recovery hook → orchestrator manually rescues → no audit trail → no learning loop → bloat keeps growing.

The fix is not one of these in isolation — it's the spine of all four together.

---

## 2. The "if you only do five things" list

Drawn from the convergence of all four documents, ranked by leverage × evidence weight:

| # | Item | Sources | Why first |
|---|---|---|---|
| 1 | **Fix worktree base mismatch** | C1 | P0 reliability bug. 5/12 cycles affected. Every other adaptive-pipeline change is moot if Phase 3 agents start from the wrong commit. |
| 2 | **Add in-flight supervisor (Haiku, every N tool calls) with whisper channel** | K1, K2, A1, A2, C2, C10 | Convergent across 4 docs. Single most-cited structural gap. Unblocks recovery, observability, and self-improve learning. |
| 3 | **Make the orchestrator a conductor, not a script — adaptive cycle modes** | A3, A4, C9 | Highest ceiling. Pays for itself on every small story. Pre-requisite for tiering verify/review depth and for surfacing rescues. |
| 4 | **Slim test agent + auto-spawn adversarial-tester after every test write** | A2, C4, C5, C6, X | Test work is the single most expensive and unreliable surface. Wave-4 gap-fill is effectively a hidden 6th wave today. |
| 5 | **Formal frontmatter contracts (`requires:` / `produces:`) + canonical artifact paths** | K4, C3, C8, C10 | Unlocks #2, #3, and self-improve. Without it, "orchestrator validates handoff" can't be implemented. |

Everything else in this document is in service of, or subordinate to, these five.

---

## 3. Themed roadmap

Recommendations clustered by theme. Each theme has a priority tier; items within a theme are ordered by dependency.

### Theme A — Reliability foundation (P0, ship first)

These are bugs, not features. Without them fixed, the rest of the roadmap measures noise.

**A1. Fix worktree base mismatch (C1)** — Phase 3 implementation agents must branch from `feature/<story>` HEAD, not stale `develop`. Fix the spawn logic in `.claude/skills/cycle/SKILL.md`. Add a startup assertion in every implementation agent: *"verify your worktree's merge-base is the feature branch tip; if not, abort and report."* Single most-cited issue across the cycle-report dataset.

**A2. Force incremental report writes for verify/review (C2)** — Both agents stall at the 600s watchdog with no file on disk. Make verify/review append findings as they produce them so a partial result survives a stall. Add a Haiku-level "salvage" pass that runs on watchdog stall to read the transcript and emit a `PARTIAL — agent stalled` report.

**A3. Enforce canonical verify/review report paths (C3)** — Paths drift (`agent_tasks/verify-*.md`, `agent_tasks/reports/verify-*.md`, inline, missing). Define one path per agent in frontmatter (`produces:`). Orchestrator treats missing file as agent failure, not silent pass.

### Theme B — Mid-flight observability & correction (P1, biggest structural win)

The pipeline currently has no eyes inside Phase 3. Borrows from Culture (K1, K2) but scaled down to our ephemeral-subagent model.

**B1. Sidecar supervisor (Haiku) (K1, A1, A2)** — Every N tool calls (or per sub-task), a Haiku agent reviews the implementation agent's last K tool calls for **SPIRALING / DRIFT / STALLING / SHALLOW**. Use Culture's three-step escalation verbatim: whisper → stronger whisper → pause + alert user. Lives in `.claude/skills/cycle/SKILL.md`. *Culture's "if you only do one thing" — and ours too if reliability foundation is already shipped.*

**B2. Whisper channel (K2)** — Supervisor writes to `agent_states/whispers/<agent>.md`. Implementation agents check between sub-tasks. Primitive but sufficient: lets the supervisor (or user) nudge a worktreed agent without restarting it. Required for B1 to have an action verb.

**B3. Structured rescue log (C10)** — Orchestrator currently rescues stalled agents invisibly (1.51.6, 1.51.11, 1.51.5). Add `rescues: []` to the cycle state file, written every time the orchestrator bypasses or substitutes for an agent. Categories: `stall`, `worktree-mismatch`, `watchdog-timeout`, `manual-completion`. Surface in run report so `self-improve` can spot trends.

**B4. Test-agent contradiction exit signal (A2)** — When test agent hits incompatible sources of truth (existing test vs. PRD AC vs. interface), it must stop and emit a structured question via whisper, not thrash through retries. Cap test-agent token budget separately from other agents — test work has a long-tail distribution.

**B5. (Optional) Progress webhook (K honorable mention)** — `monitor` already has state; one-line Discord/Slack ping on `phase_complete` / `agent_question` / `cycle_error` is cheap. Defer until B1–B3 are in place.

### Theme C — Adaptive pipeline (P1, highest ceiling)

Convert `/cycle` from a script to a conductor.

**C1. Cycle modes (A3)** — Declared at start or inferred from feature description:
- `full` — current behavior
- `lean` — skip PRD generation, generate tasks inline; gates 1C + 2B collapse to one
- `hotfix` — skip task generation, skip 2B, single-agent Phase 3, lightweight Phase 4A

Orchestrator suggests a mode at dry-run; user accepts/overrides.

**C2. Conductor planning step (A4)** — Before spawning anything, orchestrator emits a one-screen plan: phases, agents, depth, skills to attach. User approves. Re-evaluates mid-cycle: if Phase 3 finishes clean in 4 minutes, run lite verify; if it took 6 retries and surfaced 3 bugs, run deep verify. Log every plan + revision to the cycle state so `self-improve` can audit the conductor's calls.

**C3. Per-phase skip flags / depth knobs (A1, A3)** — Conservative defaults in `config.md`:
- `skip_verify_if_files_changed_lt: 3`
- `verify_depth: lite | standard | deep`
- `parallelize_verify_and_review: true` (they don't share state; today they run sequentially)
- `review_only_if_lines_changed_gt: N`

**C4. Mid-cycle scope handling (C9)** — 1.51.10 expanded scope mid-Phase 3 and subsumed 1.51.12 with only prose capture. Mid-cycle scope changes must either (a) return to gate 1C, or (b) log structurally in cycle state so verify knows the AC set has changed.

**C5. Tier verify/review depth by story size (A1)** — A 17-line `shouldRebuild` fix shouldn't get the same audit as a 12-task rewrite. Knob: file count + AC count → `lite | standard | deep`. Lite = spot-check highest-risk ACs only.

### Theme D — Test-agent overhaul (P1, highest evidence weight)

This is where four documents converge most heavily. The current test agent is the single most expensive and unreliable surface in the pipeline.

**D1. Test pre-flight contradiction classifier (A2)** — Before the test agent writes anything, a cheap Haiku pass enumerates "tests that reference symbols you're about to change" and classifies each as `keep / update / delete-because-AC-supersedes`. Hand that to the test agent as input. Converts the task from "reconcile contradictions" to "execute a plan." Single biggest predicted impact on test-task duration variance.

**D2. Auto-spawn adversarial-tester after every test write (C4)** — Wave-4 gap-fill happened in 4/12 cycles (`c9111a3`, `d251bfb`, `570f3e4`). The adversarial-tester already exists for exactly this; it's just not being routinely invoked. Make Phase 3 orchestrator spawn adversarial after every test agent's output. Removes the branch from the test agent (X).

**D3. Silent-skip analyzer gate (C5)** — Test agent's pre-commit self-check greps for `if (find...isNotEmpty)`, `if (finder.evaluate()…)`, `try { ...assert... } catch { return }`. These patterns pass when the assertion never runs. Fail the agent's own commit if found.

**D4. Pattern-divergence handling (C6)** — When test agent touches a directory with tests in a non-conventional pattern (mocktail vs. stub), it must either (a) migrate the old tests in the same commit, or (b) declare the divergence in its handoff. Currently silent.

**D5. Slim `test.md` from 181 → ~60 lines (X)** — Extract `widget-test-patterns`, `ac-audit-rubric`; delegate to `test` skill for conventions. Lazy-load `golden-tests`, `integration-tests`, `property-tests` skills. Companion: delete duplicated content from `skills/test/SKILL.md`.

### Theme E — Formal I/O contracts (P2, enabler for B/C/D)

**E1. Frontmatter contracts on every agent (K4)** — Add to each `.claude/agents/*.md`:
```yaml
requires: [prd-*.md]
produces: [tasks-prd-*.md]
artifact_dir: agent_tasks/
```
Then orchestrator validates handoff: file exists, schema present. Trades prose trust for machine-checkable contract.

**E2. Deviations field in implementer handoff (C8)** — Every implementer (ui-story, scaffold, test) emits a `deviations:` block: places the implementation differs from literal PRD, and why. Goes into cycle report and is visible at gate. AC4 in 1.51.10 ("persistent within the body") would have been caught here, not at review.

**E3. Run report vs cycle report split (C honorable mention)** — Cycle reports currently include skill-gap recommendations that read like run-report content for `/self-improve`. Tighten the boundary: cycle report = what shipped + verdicts; run report = pipeline performance + improvement signals.

**E4. Tag-based agent dispatch (K honorable mention)** — `.claude/agents/scaffold/*` subtypes already form a taxonomy. Let task files declare `scaffold_kind: syncable-entity` and dispatch directly, instead of orchestrator inferring from prose.

### Theme F — Agent prompt lightweighting (P2, the entire **X** doc)

Already covered in detail in `docs/extract-agent-skills.md`. Summary here for synthesis completeness:

**F1. HIGH-impact slimming** — `test.md` 181→60, `ui-story.md` 157→75, create `flutter-conventions` skill, dedupe `skills/scaffold/SKILL.md` 343→50. Per-cycle token cost drops substantially.

**F2. MEDIUM-impact slimming** — `verify.md` 177→85, `review.md` 152→80, `self-improve.md` 149→70, `create-prd.md` 132→75.

**F3. Migrate orchestration concerns out of agents** — `scaffold` autonomous setup spawn → `cycle/SKILL.md`; `test → adversarial` spawn → `cycle/SKILL.md` (already in D2 above).

**F4. Centralize shared autonomous preamble** — One include, not 6 copies.

### Theme G — Implementation-quality patterns (P2)

**G1. `copyWith` field drops (C7)** — `firstMeasureType`/`secondMeasureType` dropped silently 3+ times across 1.51.2, 1.51.7, 1.51.13. Add to `ui-story` / `scaffold` prompts: *"When constructing an entity inline (not via `copyWith`), enumerate every field on the class and explain why each value was chosen."* Project-side ban on inline construction outside factories is the more durable fix; flag it for the project, not the framework.

**G2. Recurring-bug surfacing (C7, C honorable mention)** — Same `ExerciseSet.copyWith` bug logged 3+ cycles without a fix. Add a `self-improve` signal: "bugs flagged in ≥N cycles without a dedicated fix cycle." Triage path for bugs discovered during cycles is currently nonexistent — they appear in cycle reports' "Bugs discovered" section, then nothing.

**G3. Review autonomy boundary (C honorable mention)** — 1.51.7 had review agent autonomously fix the `copyWith` measure-type drop. Good outcome, but blurs review vs implementation. Codify what review is allowed to auto-fix vs must flag. Suggestion: review fixes only safe mechanical edits (drift, lint, single-line copyWith fields it can prove are missing); anything else is a flag.

### Theme H — Hygiene & infrastructure (P3)

**H1. Compact at phase boundaries (K3)** — Orchestrator calls `/compact` deterministically at Phase 2→3 and Phase 3→4. Stops the orchestrator from re-reading PRD scaffolding for the 40th time.

**H2. Per-agent token tracking (X open question)** — Cycle reports currently don't record per-agent token usage. Adding it would let us validate F1/F2 savings post-migration and measure A1's adaptive savings.

**H3. Analyzer baseline (C11)** — Optional `analyze_baseline` config: cycle fails if `flutter analyze` count > baseline + N. Forces the count to monotonically decrease. Probably project-level, not framework-level.

**H4. Circuit breaker (K honorable mention)** — 3 failures in 5 min → stop & alert. Formalize what's probably already implicit in Phase 3 retry logic.

---

## 4. Convergence map

Which themes are reinforced by which docs. Items appearing in 3+ docs are convergent and should be prioritized regardless of their per-doc framing.

| Theme | A | C | K | X | Convergence |
|---|---|---|---|---|---|
| Reliability foundation (A) | — | C1, C2, C3 | — | — | Single-source (C) but P0 by severity |
| Mid-flight supervisor (B) | A1, A2 | C2, C10 | K1, K2 | — | **Convergent ×3** |
| Adaptive pipeline (C) | A3, A4 | C9 | — | — | Convergent ×2 (A is primary) |
| Test-agent overhaul (D) | A2 | C4, C5, C6 | — | X test | **Convergent ×4** |
| Formal contracts (E) | — | C3, C8, C10 | K4 | — | Convergent ×2 |
| Prompt lightweighting (F) | A5 | — | — | X entire | **Convergent ×2 + dedicated doc** |
| Implementation quality (G) | — | C7, C8 | — | — | Single-source (C) |
| Hygiene (H) | — | C11 | K3, honorable | X | Diffuse |

**Test-agent overhaul (D) has the highest convergence score — 4 docs flag it from 4 angles.** Mid-flight supervision (B) is the second-most convergent and the single most-cited structural gap.

---

## 5. Dependency order

Some items unlock others. The execution order matters more than the per-item priority.

```
[Reliability] ─┐
   A1 worktree │
   A2 streamed │
   A3 paths    │
               ├──> [Contracts] ────┬──> [Conductor]
               │      E1 frontmatter│      C1 modes
[Supervisor] ──┤      E2 deviations │      C2 planning
   B1 sidecar  │      E3 reports    │      C3 skip flags
   B2 whispers │                    │      C4 mid-cycle
   B3 rescues  │                    │      C5 tier depth
   B4 contra   │                    │
               │                    └──> [Self-improve loop closes]
               │
               └──> [Test overhaul] ─┬──> [Prompt slim]
                      D1 pre-flight  │      F1 HIGH
                      D2 adversarial │      F2 MED
                      D3 silent-skip │      F3 orchestration
                      D4 divergence  │      F4 preamble
                      D5 slim test.md│
```

**Reading:** Ship reliability and supervisor first (parallelizable). They unblock contracts, which unblock the conductor and close the self-improve loop. Test overhaul can ship in parallel with contracts because its prerequisites (B4 contradiction exit, D2 adversarial auto-spawn) are independent of E1. Prompt slimming is last because contract-driven validation (E1) is cleaner to add to a slimmed-down agent than to one being slimmed mid-migration.

---

## 6. Sequenced milestones

Concrete, shippable chunks. Each milestone is independently valuable; later milestones depend on earlier ones being in place.

### Milestone 1 — Reliability foundation (1–2 PRs)
- A1 worktree base fix + startup assertion
- A2 incremental report writes + Haiku salvage pass
- A3 canonical verify/review paths
- Acceptance: re-run any cycle from 1.51.5/.9/.10/.11/2.1.1 against the fix; worktree-mismatch incidents drop to zero.

### Milestone 2 — Contracts + observability (2–3 PRs)
- E1 frontmatter `requires`/`produces` on every agent
- E2 deviations field on implementer handoff
- B3 structured rescue log in cycle state
- Acceptance: every agent handoff validates on disk; `self-improve` can read a structured rescue log.

### Milestone 3 — Supervisor + whispers (2 PRs)
- B1 sidecar Haiku supervisor (turn-based, simplified Culture model)
- B2 whisper channel
- B4 test-agent contradiction exit
- Acceptance: simulated thrashing agent gets paused after escalation ladder; whisper file exists.

### Milestone 4 — Test-agent overhaul (2 PRs)
- D1 pre-flight contradiction classifier
- D2 orchestrator auto-spawns adversarial-tester after every test write
- D3 silent-skip analyzer gate
- D4 pattern-divergence handling
- D5 slim `test.md` (depends on E1 contracts)
- Acceptance: re-run 1.51.5/.7/.8/.9 — wave-4 gap-fill commits become unnecessary; test-task duration variance drops.

### Milestone 5 — Conductor mode (3–4 PRs)
- C1 cycle modes (lean/hotfix)
- C2 conductor planning step
- C3 per-phase skip flags + parallel verify/review
- C5 tiered verify/review depth
- C4 mid-cycle scope handling
- Acceptance: a typo-fix cycle completes in <half the wall-clock of today's full pipeline; large cycles unchanged.

### Milestone 6 — Prompt lightweighting (3–5 PRs)
- F1 HIGH items (test, ui-story, flutter-conventions, scaffold-skill dedup)
- F2 MEDIUM items (verify, review, self-improve, create-prd)
- F3 orchestration-concern migration
- F4 shared preamble
- Acceptance: agents drop from ~1,283 → ~605 lines; per-spawn token cost measurably lower (requires H2 to validate).

### Milestone 7 — Hygiene & long tail
- H1 compact at phase boundaries
- H2 per-agent token tracking
- G1, G2, G3 implementation-quality patterns
- E4 tag-based dispatch
- B5 progress webhook
- H3 analyzer baseline (project, not framework)
- H4 circuit breaker

---

## 7. Open decisions

These need user input before implementation can start in earnest.

1. **Supervisor cadence (B1).** Culture uses 20 turns × Sonnet-medium. We need something cheaper. Options:
   - Per-N tool calls (N=5? 10?) at Haiku
   - Per sub-task boundary (cleaner but less responsive)
   - Both (Haiku per-N, Sonnet on escalation)
   - Recommendation: per-5-tool-calls at Haiku, escalating to Sonnet on second whisper.

2. **Cycle mode auto-suggestion (C1).** Should the conductor *propose* a mode based on feature-description heuristics (word count, complexity keywords) and let the user override, or always require the user to declare? Recommendation: propose at dry-run, user overrides; default to `full` if unsure.

3. **Mirror-skill fate after prompt slim (X open question).** Do `skills/test/SKILL.md`, `skills/verify/SKILL.md` etc. remain as user-invocable slash commands? Recommendation: yes, but rewritten to `@include` the new extracted sub-skills, not to duplicate content.

4. **Migration order for F (prompt slimming).** One mega-PR vs per-agent PRs. Recommendation: per-agent PRs starting with `skills/scaffold/SKILL.md` dedup (zero behavior change), then test, then ui-story.

5. **Review autonomy boundary (G3).** Where exactly do we draw the line between "review may auto-fix" and "review must flag"? Recommendation: review auto-fixes only mechanical/proof-checkable changes (drift, formatter output, missing `copyWith` fields where the constructor declaration proves intent); everything else is a flag with a suggested diff.

6. **Bug triage path (G2).** Cycle reports' "Bugs discovered" section needs a sink. Options: GitHub Issues integration, a `documentation/BUGS.md` file curated by `self-improve`, or a dedicated `triage` agent run weekly. Recommendation: start with `documentation/BUGS.md` curated by `self-improve`; promote to issue-tracker integration once we know the volume.

7. **Skill invocation model (X open question).** Does Claude Code's `Skill` tool reliably fire from sub-agents mid-task, or only at top of conversation? If only top-of-conversation, the conductor must pre-attach skills in the spawn prompt and the agent body just references the loaded skill. *This is a factual question that needs verification before F1 design is finalized.*

---

## 8. What this synthesis does NOT cover

- **Project-side fixes** that the source docs flag as project concerns rather than framework concerns: analyzer-warning baseline (C11) and inline-entity-construction ban (G1) are noted but live in the consuming Flutter project, not this repo.
- **Quantitative measurement infrastructure.** H2 (per-agent token tracking) is listed but not designed. Should likely be its own small spec — a cycle-report schema change.
- **Backwards compatibility.** This plan assumes a forward-rolling framework where users `git pull` and adopt. If users have customized agent prompts in their own forks, several items in F break those customizations.
- **The `refine` skill.** Recently added (commit `f2ecd7a`) and not yet exercised in any cycle report. Excluded from this round; revisit after 5+ cycles use it.

---

## 9. Closing observation

The four source documents were written from four different vantage points — felt friction, cycle-report archaeology, comparative framework reading, and prompt-engineering analysis — and they converge on the same diagnosis: **the framework is good at executing a fixed pipeline and bad at adapting to what it sees while executing.** Every theme in this synthesis is a different facet of giving the orchestrator the eyes (B), the vocabulary (E), the levers (C), and the headroom (F) to actually conduct rather than execute.

The reliability bugs in Theme A are the only items that block on themselves. Everything else can ship in the order suggested in §6 without invalidating earlier work.
