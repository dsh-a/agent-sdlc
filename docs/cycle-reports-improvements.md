# Cycle Reports → agent-sdlc: Potential Improvements

Patterns drawn from reading 12 cycle reports across the 1.51.x and 2.1.x series (`ignite_flutter/cycle_reports/`, 2026-05-05 → 2026-05-16). Each item below recurred across at least two cycles or surfaced a structural failure mode rather than a one-off mistake.

---

## Recurring infrastructure failures

### 1. Worktree base mismatch (P0 — appears in 5/12 cycles)

Surfaces in **1.51.5, 1.51.9, 1.51.10, 1.51.11, 2.1.1**. Phase 3 implementation agents spawned with `isolation: "worktree"` branch from a stale `develop` commit (often `751b904`) instead of the current feature-branch HEAD. Downstream effects observed:

- **1.51.5** — wave 2 agents were spawned *without* `isolation: "worktree"` as a workaround, violating the cycle skill's own rule.
- **1.51.10** — test agent's worktree caused a wholesale rewrite of `routine_canvas_test.dart`; orchestrator preserved old tests by renaming the new file rather than merging.
- **1.51.11** — orchestrator applied the fix manually to the feature branch rather than merging the worktree.
- **2.1.1** — T6 test agent wrote tests against the **pre-rename** API; required a full rewrite. T5↔T4 merge conflict in `profile_view_model.dart`.

**Recommendation:** Fix the worktree-spawn logic in `.claude/skills/cycle/SKILL.md` (or wherever worktree creation lives) to explicitly branch from `feature/<story>` HEAD, not `develop`. Add a startup assertion in each implementation agent: "verify your worktree's merge-base is the current feature branch tip; if not, abort and report."

This is the single most-cited process problem across the dataset.

### 2. Phase 4A `verify` / `review` watchdog stalls (P1)

Both **1.51.10** and **1.51.11** report verify+review agents stalling at the 600s watchdog with no report file produced. Manual recovery filled the gap. Partial transcript output existed but no verdict.

**Recommendation:** Two things —
- Investigate root cause (transcript length? tool-call loops? token budget?). The 1.51.10 report notes the verify agent "got through AC enumeration and source file inspection but did not emit a verdict" — suggests the agent is producing work but failing to *write the report file*. Force the agent to write incrementally (append-as-you-go) so a stall still leaves a partial report on disk.
- Add a fallback: on watchdog stall, the orchestrator should spawn a single Haiku-level "salvage" pass that reads the transcript and emits a `PARTIAL — agent stalled` report file. Right now the orchestrator silently substitutes manual analysis with no audit trail.

### 3. Verify report file inconsistency

Verify agents sometimes emit a file (`agent_tasks/verify-*.md`, `agent_tasks/reports/verify-*.md`), sometimes "kept results inline" (1.51.9), sometimes produced no file at all (1.51.10, 1.51.11). Path varies across cycles.

**Recommendation:** Enforce a single canonical path in the verify agent's frontmatter (`produces:` contract — see culture-improvements.md #4). If the file isn't on disk at agent exit, the orchestrator should treat verify as failed.

---

## Test-quality patterns

### 4. Wave-4 "verify gap-fill" is the norm, not the exception

Cycles **1.51.5, 1.51.7, 1.51.8, 1.51.9** all required a dedicated post-verify commit to close test gaps (`c9111a3`, `d251bfb`, `570f3e4`, etc.). The pattern is so consistent it's effectively a hidden 6th wave of every cycle. Verify is doing real work — but the test agent is consistently shipping tests that pass coverage-by-presence rather than coverage-by-assertion.

Common gap shapes:
- "AC says button is disabled" → test asserts button *exists*, not its `onPressed == null` state.
- "AC says X renders in order Y" → test asserts X renders, not the positional order.
- "AC says regex rejects @" → test rejects emoji (different category); the literal AC example is untested.
- Property assertions (`maxLines`, `TextOverflow.ellipsis`, exact text) routinely missing.

**Recommendation:** Strengthen the `test` agent's spec or fold the adversarial-tester pass into Phase 3 (not just on-demand). The adversarial-tester already exists for "silent failures, boundary violations, missing negative assertions" — this is exactly its job, and the data says it's not being routinely invoked. Either (a) make the orchestrator spawn adversarial-tester after every test file write, or (b) bake those checks into the `test` agent's review checklist.

Alternatively: feed the verify report's gap list back as an automatic Phase 3.5 retry, instead of requiring a manual wave 4.

### 5. Silent-skip test patterns

**1.51.3** flagged `if (...isNotEmpty) { ... }` patterns in structural panel tests — tests that pass when the assertion never runs. Likely exists in other cycles but only this report called it out.

**Recommendation:** Add an analyzer/grep gate in the test agent's self-check: any `if (find...isNotEmpty)`, `if (finder.evaluate()...)`, or `try { ...assert... } catch { return }` pattern should fail the test agent's own pre-commit. These are conditional assertions and should be unconditional.

### 6. Test architecture divergence (mocktail vs. stub)

**1.51.10** ended with two test files in the same directory using different patterns: pre-existing mocktail mocks vs. new `_StubViewModel extends ChangeNotifier`. The project convention (`test/CLAUDE.md`) prefers stubs, but the test agent didn't migrate the old file — it created a new one alongside, leaving the directory split.

**Recommendation:** When the test agent touches a directory that already has tests in a non-conventional pattern, it should either (a) migrate the old tests in the same commit, or (b) note the divergence explicitly in its handoff so the orchestrator can decide. Currently divergence happens silently.

---

## Implementation patterns

### 7. `copyWith` field drops keep recurring

**1.51.2**: `firstMeasureType`/`secondMeasureType` silently dropped at 4 manual `ExerciseSet(...)` reconstruction sites. **1.51.7**: same fields, same bug, caught again by reviewer (auto-fixed). **BUG-005** (`ExerciseSet.copyWith` self-referential `lastUpdated`) referenced across 1.51.2, 1.51.7, 1.51.13.

The reviewer catches these reliably. The implementer keeps making them. The pattern: when an implementer needs to "reconstruct" an entity inline, they list the fields they care about and drop the rest.

**Recommendation:** Add to the `ui-story` / `scaffold` agent prompt: "When constructing an entity inline (not via `copyWith`), enumerate **every** field on the class and explain why each value was chosen. If unsure, use `copyWith` instead." Or, project-side, ban inline entity construction outside of factories — but that's a project rule, not a framework rule.

Also: the same `ExerciseSet.copyWith` bug has been logged 3+ times without a cycle to fix it. The pipeline doesn't currently have a way to surface "recurring bugs flagged across N cycles" — would be a useful `self-improve` signal.

### 8. PRD/implementation deviations that aren't flagged proactively

**1.51.10 AC4** — "persistent Add Exercise button on every phase section" implemented as "persistent within the body" (collapsed phases have no button). Implementer left a code comment, but the deviation wasn't called out until review.

**1.51.9** — PRD says Clear calls `resetFilters()`, implementation introduces `resetDropdownFilters()`. Verify flagged.

**Recommendation:** Add a "deviations" field to the implementer's handoff: "list any place your implementation differs from the literal PRD, and why." This goes directly into the cycle report and the user sees it at gate, rather than discovering it in review.

### 9. Mid-cycle scope creep is uncaptured

**1.51.10** "expanded scope (per refinement) to ship the long-missing per-section Add exercise affordance" and "subsumed 1.51.12 during refinement." This happened during Phase 3, not at gate 1C.

**Recommendation:** Mid-cycle scope changes should either (a) require a return to gate 1C, or (b) be logged structurally in the cycle state so verify knows the AC set has changed. Currently this is captured in prose only.

---

## Orchestrator process patterns

### 10. Orchestrator silently rescues stalled agents

**1.51.6** task 4.0 — "implementation agent stalled mid-task; orchestrator completed it manually." **1.51.11** — verify/review stalled, orchestrator did manual analysis. **1.51.5** — wave 2 spawn pattern changed mid-cycle to work around worktree bug.

These rescues keep the cycle moving but they're invisible to `/self-improve`. The run report should record each rescue as a distinct event with a category (stall, worktree-mismatch, watchdog-timeout, etc.) so `self-improve` can spot trends.

**Recommendation:** Add a `rescues: []` array to the cycle state file, written by the orchestrator every time it bypasses or substitutes for an agent. Surface it in the run report.

### 11. Pre-existing analyzer warnings are everywhere and nobody owns them

Every single cycle reports "95 pre-existing warnings, no new ones introduced." The number is stable (90, 91, 92, 95, 95, 96, 97) — slowly growing. There's no mechanism to either pay them down or freeze the baseline.

**Recommendation:** Probably out of scope for the framework (it's a project hygiene issue) but consider an optional `analyze_baseline` config: cycle fails if `flutter analyze` count > recorded baseline + N. Forces the count to monotonically decrease over time.

---

## Honorable mentions

- **Run report vs. cycle report split** — cycle reports include "skill-gap recommendation" notes (1.51.10) that read like they should be in the run report consumed by `/self-improve`. The two artifacts are blurring.
- **Critical fixes by the review agent** — **1.51.7** had the review agent autonomously fix the `ExerciseSet.copyWith` measure-type drop. Good in this case, but blurs the line between review and implementation. Codify what review is allowed to fix vs. what it must flag.
- **Bug discovery has no triage path** — cycles consistently surface "BUG-005", "BUG-006", "BUG-NEW" in the cycle report's *Bugs discovered* section, then nothing happens. The framework should either pipe these into a tracked list or stop pretending it does.
