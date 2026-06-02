---
name: ui-test-patterns
description: UI / presentation-layer test patterns — coverage matrix, test-host setup, snapshot/golden tests, integration tests. Loaded by the test and ui-story agents; single source for these patterns. Populated per language pack.
disable-model-invocation: true
---

# UI Test Patterns

> **Active placeholder.** This skill is loaded deterministically by the `test` and
> `ui-story` agents. Populate it from the active pack's UI test patterns
> (`.claude/packs/<lang>/ui-test-patterns.md` — see `packs/flutter/` for a complete worked
> example) via `/setup`, or edit directly. The framework/idiom specifics belong here; the
> coverage *intent* below is language-agnostic.

Conventions for testing presentation-layer code (views, components, view-models). Used by
the `test` and `ui-story` agents. Cross-references `project-conventions` for layer rules.

---

## File location

Test path mirrors source path per your project's test layout (configure the test glob in
`.claude/config.md` § Project Commands).

## Structure

- Organize tests by method or behavior.
- One logical assertion target per test; descriptive names stating the expected outcome.
- **Arrange → Act → Assert** with phases visually separated.

## Mocking / test doubles

- Use the project's standard mocking library (state it in `project-conventions`).
- Reuse shared fakes/builders over re-declaring per test; register fallback values where the
  framework requires them.

## Setup

- Declare dependencies and the subject-under-test once; instantiate fresh per test so each
  starts clean.

---

## Coverage matrix — views / components

| Category | What to verify |
|---|---|
| Rendering | Key elements present in initial state |
| Loading state | Loading affordance shown, interactions disabled |
| Error state | Error surfaced to the user |
| Empty state | Appropriate message when no data |
| Interactions | User action triggers the correct presentation method |
| Conditional UI | Permission/auth-gated elements hidden as expected |

## Coverage matrix — view-models / presenters

| Category | What to verify |
|---|---|
| State transitions | Loading flips true → false around async work |
| Error handling | Error state set on failure, cleared on retry |
| Change notification | Observers notified after state changes |
| Input validation | Invalid inputs produce error states before calling services |

---

## Snapshot / golden tests

Write snapshot tests only for views with significant visual design. **Never auto-update
snapshots** — present the update command in your report for the user to run and review.

## Integration tests

Write integration tests only for critical multi-screen/multi-service flows. **Flag them in
your report as requiring a separate run environment — do not run them autonomously** unless
the project's test setup supports it.

## What NOT to do

- Do not test private methods — test through the public API.
- Do not test generated code.
- Do not auto-update snapshot/golden files.
- Do not mix integration tests into unit-test files.
