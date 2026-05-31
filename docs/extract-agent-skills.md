# Extract Agent Skills — Lightweighting Plan

**Status:** Draft / proposal
**Date:** 2026-05-16
**Related:** `docs/anecdote_improvements.md` §5 ("agents carry too much baked-in prompt overhead"), `docs/cycle-reports-improvements.md` §4 (orchestrator should drive sub-agent spawns)

## Goal

Shrink agent system prompts to **identity + contract + decision rules**, and move static reference material (conventions, templates, rubrics, code-style defaults) into skills that agents (or the `/cycle` orchestrator) invoke on demand. Reduce per-spawn token cost and eliminate duplication between agent prompts and their mirror skills.

## North star

> **Lean base agent prompt = identity + contract + skill manifest.**
> Everything else loaded only when the current task triggers it.

## Current footprint

| Surface | Lines | Notes |
|---|---|---|
| `.claude/agents/*.md` (10 agents) | ~1,283 | Lots of duplication with mirror skills |
| `.claude/agents/scaffold/*.md` (10 patterns) | ~646 | Already correctly factored as lazy-load |
| `.claude/skills/*/SKILL.md` (14 skills) | ~2,647 | Mirror skills duplicate agent prompts |

Largest duplication offenders: `test.md` ↔ `skills/test/SKILL.md` (~100 lines duplicated), `verify.md` ↔ `skills/verify/SKILL.md` (~90), `review.md` ↔ `skills/review/SKILL.md` (~70), `self-improve.md` ↔ `skills/self-improve/SKILL.md` (~80), `skills/scaffold/SKILL.md` ↔ `.claude/agents/scaffold/*.md` (~290).

## Per-agent findings

### `create-prd.md` (132 → ~75 lines target)

- **Duplicates** `skills/create-prd/SKILL.md`: AC format block, anti-faking table, minimum-coverage checklist (lines 71–120), PRD structure list (56–67), roadmap lookup (15–22), related-PRD scan (25–37). ~50 lines.
- **Static**: AC format, anti-faking table, coverage categories.
- **Must stay**: identity, step ordering, sub-agent spawn directive (43–48), report contract (127–132).
- **Extract to**: new `ac-authoring` skill.

### `generate-tasks.md` (124 → ~85 lines)

- **Duplicates**: output format block (92–116) and self-review checklist (74–82) mirror `skills/generate-tasks/SKILL.md`.
- **Must stay**: identity, 4–6 parent-task heuristic + typical structure (40–49), report contract.
- **Extract to**: new `task-file-format` skill (shared with the `generate-tasks` skill).

### `scaffold.md` (65 lines — already lean)

- Agent itself is fine. Pattern templates under `.claude/agents/scaffold/*.md` are the canonical lazy-load model.
- **Action**: trim `skills/scaffold/SKILL.md` (343 → ~50 lines) — it currently re-implements every pattern template. Make it a thin index pointing at `.claude/agents/scaffold/*.md`. No agent change required.
- **Orchestration concern to move**: the autonomous setup-scaffold spawn block (43–50) duplicates `cycle/SKILL.md` Phase 3.1; agent should assume pattern files exist.

### `ui-story.md` (157 → ~75 lines) — highest leverage

- **Duplicates** with `scaffold/view-model-view.md` and `test.md`:
  - ViewModel pattern + conventions + file locations (62–104) → already in `scaffold/view-model-view.md`
  - Widget-test setup, coverage table (110–141) → already in `test.md` / `skills/test/SKILL.md`
  - MVVM rules (24–30) → duplicated in 4 other places
- **Action**: replace VM/View pattern block with "invoke `scaffold` skill, type `view-model-view`"; replace widget-test block with "delegate to `test` agent"; pull MVVM rules into `flutter-conventions` skill.

### `test.md` (181 → ~60 lines) — highest leverage

- **Duplicates** ~100+ lines of `skills/test/SKILL.md`: conventions, `buildTestApp` snippet, View/VM verification tables, golden policy, property-test example, integration guidance, anti-pattern list.
- **Must stay**: identity, AC short-circuit (19), adversarial spawn directive, report contract.
- **Extract to**: `widget-test-patterns` skill; `ac-audit-rubric` skill; small lazy-load skills for `golden-tests`, `integration-tests`, `property-tests` (decision-dependent).
- **Orchestration**: consider moving the adversarial-tester spawn into the orchestrator (per `cycle-reports-improvements.md` §4) so the test agent doesn't carry that branch.

### `adversarial-tester.md` (48 lines — already lean)

- Minor: attack-vector list duplicates `verify.md:62` and `skills/verify/SKILL.md:80`. Pull into a shared `adversarial-patterns` skill (~10 lines saved).

### `verify.md` (177 → ~85 lines)

- **Duplicates** `skills/verify/SKILL.md`: six audit checks (50–66), coverage matrix template (84–94), verdict labels, scope-creep step (71–78), live-widget-tree block (131–139), save-report (161–175).
- **Extract to**: `ac-audit-rubric` skill (audit checks + verdicts + matrix). Lazy-load `live-widget-tree-audit`, `non-functional-audit`, `golden-review` as small optional skills.

### `review.md` (152 → ~80 lines)

- **Duplicates** `skills/review/SKILL.md`: class member order (39–46), code-style defaults (51–57), pattern compliance (60–66), code-quality checks (72–89), report template (121–144).
- **Must stay**: identity, auto-fix step (104–117 — unique to agent), verdict logic.
- **Extract to**: `flutter-conventions` skill (shared); `review-report-format` skill.

### `self-improve.md` (149 → ~70 lines)

- **Duplicates** `skills/self-improve/SKILL.md`: 3Es buckets (18–37), pattern categories (42–60), recommendation format (67–86), priority order, edge cases.
- **Must stay**: identity, autonomous-apply rule (90–99 — differentiates from the skill), dimension-scoping logic.
- **Extract to**: `pipeline-metrics-rubric` skill.

### `monitor.md` (98 lines — leave alone)

- Unique; no mirror skill. State-file template + update-protocol message types are the agent's contract with the orchestrator. Marginal gain from extraction not worth the indirection.

## Cross-cutting extraction candidates

### New skills to create

| Skill | Replaces content in | Lines | Loaded by |
|---|---|---|---|
| `flutter-conventions` | `ui-story.md:24-30`, `scaffold/view-model-view.md:31-47`, `review.md:39-66`, `skills/review/SKILL.md:49-76` | ~40 | ui-story, scaffold, review, test |
| `ac-authoring` | `create-prd.md:71-120` | ~40 | create-prd |
| `ac-audit-rubric` | `verify.md:50-94`, `adversarial-tester.md:22-29`, `test.md:54-58` | ~50 | verify, test, adversarial-tester |
| `widget-test-patterns` | `test.md:93-142`, `ui-story.md:110-141` | ~60 | test, ui-story |
| `task-file-format` | `generate-tasks.md:74-116` | ~30 | generate-tasks |
| `pipeline-metrics-rubric` | `self-improve.md:18-86` | ~60 | self-improve |
| `adversarial-patterns` | `adversarial-tester.md:22-29`, duplicated in verify | ~15 | adversarial-tester, verify |
| (optional) `golden-tests`, `integration-tests`, `property-tests` | `test.md` decision-dependent blocks | ~20 each | test (lazy) |
| (optional) report-format skills (`verify-report-format`, `review-report-format`, `cycle-run-report-format`, `self-improve-report-format`) | inline report templates | ~15 each | corresponding agent |

### Orchestration concerns to migrate into `cycle/SKILL.md`

1. `scaffold.md:43-50` — setup-scaffold autonomous spawn (already duplicated in `cycle/SKILL.md` Phase 3.1).
2. `test.md:163-169` — adversarial-tester spawn. Per `cycle-reports-improvements.md` §4, orchestrator should spawn adversarial after every test run; remove the branch from the test agent.

### Shared autonomous preamble

The "You work autonomously — no user interaction… never use python/heredoc for file I/O" preamble appears verbatim in 6 agents. Put it in the orchestrator's spawn prompt (or a single shared include). ~18 lines reclaimed.

## Prioritized roadmap

### High impact

1. **Slim `test.md` to ~60 lines.** Highest per-cycle frequency, highest duplication. Extract `widget-test-patterns` + `ac-audit-rubric`; delegate to the `test` skill for conventions. Move adversarial-spawn to orchestrator.
2. **Slim `ui-story.md` to ~75 lines.** Replace VM/View pattern with `scaffold` delegation; replace widget-test block with `test` delegation; load `flutter-conventions`.
3. **Create `flutter-conventions` skill.** Removes ~80 lines of duplication across 5 files; kills the biggest drift hazard.
4. **Dedupe `skills/scaffold/SKILL.md` (343 → ~50 lines).** Index-only; point at `.claude/agents/scaffold/*.md`. Zero agent change, immediate win.

### Medium impact

5. **Slim `verify.md` to ~85 lines.** Extract `ac-audit-rubric`; lazy-load optional audit gates.
6. **Slim `review.md` to ~80 lines.** Use `flutter-conventions`; extract report template.
7. **Slim `self-improve.md` to ~70 lines.** Extract `pipeline-metrics-rubric`.
8. **Slim `create-prd.md` to ~75 lines.** Extract `ac-authoring`.
9. **Migrate orchestration concerns out of agents** into `cycle/SKILL.md` (`scaffold` spawn, `test → adversarial` spawn).

### Low impact

10. **Slim `generate-tasks.md` to ~85 lines.** Extract `task-file-format`.
11. **Centralize autonomous preamble.** ~18 lines reclaimed; hygiene + consistency.
12. **Extract `adversarial-patterns` skill.** Minor; mostly anti-drift.
13. **Leave `monitor.md` alone.**

## Aggregate target

Applying HIGH + MEDIUM:

- Agents: **~1,283 → ~605 lines** (≈53% reduction)
- `skills/scaffold/SKILL.md`: −290 lines
- 6–10 new lightweight skills: ~250 lines total
- Net framework footprint: roughly flat; **per-spawn token cost drops substantially** because each agent only loads the skills its task triggers.

## Decision points (need user input)

- **Skill invocation model**: explicit `Skill` tool calls from agents vs. orchestrator-driven preloading vs. hybrid? Currently agents don't routinely invoke skills mid-task; the cleanest separation is orchestrator decides _which_ skills to pre-attach in the spawn prompt based on task type, and the agent body just says "use the loaded skill for X".
- **Skill granularity**: one big `flutter-conventions` vs. several small ones (`naming`, `member-order`, `mvvm`, `logger`)? Recommend starting with one consolidated skill; split only if it grows past ~80 lines.
- **Mirror-skill fate**: when an agent slims down, do the mirror skills (`skills/test/`, `skills/verify/`, etc.) stay as user-invocable `/test`, `/verify` slash commands? Likely yes — but they should `@include` the new extracted sub-skills instead of duplicating content.
- **Migration order**: ship the four HIGH items as one PR (high blast radius but coherent) vs. one PR per agent (safer, more reviewable). Recommend per-agent PRs starting with `scaffold` skill dedup (zero behavior change), then `test.md`, then `ui-story.md`.

## Open questions

- Does Claude Code's `Skill` tool reliably get invoked by sub-agents mid-task, or only at top of conversation? If only top-of-conversation, the orchestrator must pre-attach.
- Token-cost measurement: we don't currently track per-agent token usage in `cycle_reports/`. Adding that (per `cycle-reports-improvements.md`) would let us validate the savings post-migration.
- Are any pattern templates under `.claude/agents/scaffold/` actually consumed today by code outside the `scaffold` agent? If so, the skill-dedup in HIGH #4 needs a shim.
