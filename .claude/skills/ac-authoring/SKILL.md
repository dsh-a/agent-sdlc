---
name: ac-authoring
description: How to write testable acceptance criteria — structure, anti-faking guidance, minimum coverage categories. The contract between PRDs and the implementation/test agents. Loaded by create-prd and refine.
disable-model-invocation: true
---

# Acceptance Criteria Authoring

AC is the contract between a PRD and the agents that implement and test it. Vague AC produces fakeable tests and silent regressions. Follow these rules strictly when writing or revising AC.

---

## Structure

```markdown
**Acceptance Criteria:**
- [ ] (+) [positive criterion — something that MUST work]
- [ ] (-) [negative criterion — something that must NOT happen, or must be handled gracefully]
```

Every feature must have both positive AND negative criteria. A PRD with only `(+)` criteria is incomplete.

---

## Writing testable AC

Each criterion must be:

1. **Observable** — user-visible outcome or system-observable state, not an internal implementation detail.
   - Good: "User can search exercises by name"
   - Bad: "The search function calls the repository"
2. **Specific** — concrete values, limits, behaviors.
   - Good: "Display name is limited to 30 characters; disallowed characters are rejected with an inline error"
   - Bad: "Display name has appropriate validation"
3. **Independent** — testable in isolation.
4. **Falsifiable** — an agent could write a test that either passes or fails.

---

## Anti-faking guidance

Ask before committing each criterion: **"Could an agent satisfy this with a trivial or degenerate implementation?"** If yes, rewrite.

| Vague (fakeable) | Specific (not fakeable) |
|---|---|
| "Login is secure" | "Login fails with a clear error when credentials are incorrect" |
| "Data persists" | "Preference persists across app restarts" |
| "Errors are handled" | "Exercise is not lost if creation fails due to a network error" |
| "Performance is good" | "List of 1000 items renders in under 100ms on the test device" |

---

## Minimum AC coverage

Actively consider each category. Skip only when genuinely not applicable.

- **Happy path** — primary user flow works end-to-end.
- **Boundaries** — limits, maximums, empty states.
- **Error states** — network failure, invalid input, missing data.
- **Authorization** — what guests vs. authenticated users can do.
- **Data integrity** — operations don't corrupt related data.
- **Offline behavior** — what works offline, what doesn't, how the user is informed.
