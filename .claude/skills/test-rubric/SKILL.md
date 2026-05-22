---
name: test-rubric
description: Self-check rubric the test agent runs against its own output before declaring done. Absorbs the adversarial-tester checklist (off-by-one, null propagation, silent shortcuts, boundary violations) into an in-process pass. Invoked from the test agent's Step 6.3 (or skill Step 7.3); not auto-invoked.
disable-model-invocation: true
---

# Test Self-Check Rubric

You have just written or modified tests. Before declaring done, run this rubric against your output. **Fail any check → fix → re-run.** Cap at 2 iterations; on the second failure, emit a `contradiction-exit` signal (see end) rather than thrash.

The rubric is applied **per acceptance criterion**, then once globally for the silent-skip and schema-constraint checks.

---

## Per-AC checks

For each AC covered by this test suite:

### 1. AC literalness
Does a test assert the **literal AC behavior** — not a proxy?
- AC says "displays the user's name" → test asserts `find.text(user.name)`, not just "screen renders without error."
- Fail → rewrite the assertion against the literal AC text.

### 2. Naive-shortcut detection
If the implementation under test were replaced with a hardcoded return value or no-op, would the test still pass?
- Read each test. Mentally substitute the impl with `return null` / `return ''` / `return const Result.ok()`. If the test still passes, it's testing nothing.
- Fail → add an assertion that distinguishes the real implementation from a stub (e.g., input-dependent output, side effect on a mock).

### 3. Boundary
If the AC specifies a threshold or range, are **both sides** of the boundary tested?
- AC "password must be at least 6 characters" → tests at length 5 (fail) AND length 6 (pass).
- Fail → add the missing boundary case.

### 4. Side effect
If the AC says something **must happen** (insert, emit, call, write), does a test assert it via `verify(...).called(N)` (or framework equivalent)?
- Return-value-only assertions miss side effects.
- Fail → add the `verify(...)` assertion.

### 5. Negative path
If the AC says something **must NOT happen** under some condition, is there a `verifyNever(...)` (or framework equivalent)?
- "Saves only when valid" implies a `verifyNever(save(...))` test for the invalid input case.
- Fail → add the negative assertion.

---

## Global checks

Run these once across the entire test file (or files) you wrote.

### 6. Silent-skip patterns (mechanical grep)
Grep your new test files for these patterns — any hit is a hard fail:

- `if (find...isNotEmpty)` — gates an assertion on whether something exists, so it never fails when missing
- `if (finder.evaluate()` — same pattern, different finder API
- `try { ...expect... } catch` — swallows the expect's exception, turning failure into silent pass
- `skip:`, `@Skip(`, `it.skip(`, `test.skip(`, `xit(`, `xtest(` — skipped tests masquerading as coverage

Fail → remove the guard (let the assertion fail loudly when the precondition isn't met), or rewrite as an explicit `expect(find..., findsNothing)` when "absence" is the actual AC.

### 7. Schema constraints (data layer only)
If any source file under test is a repository, adapter, or DAO under `lib/data/`:
- Call `mcp__supabase__list_tables` to identify NOT NULL / UNIQUE / CHECK / FK constraints on the touched table.
- For each constraint not currently asserted by a test, add a violation test (or note it as a deliberate gap in the report).

Skip this check if no `lib/data/` files are in scope.

---

## Iteration protocol

```
iteration = 1
loop:
  run all checks above
  if all pass: done — proceed to final report
  if iteration >= 2: emit contradiction-exit, stop
  fix the failures (edit tests; or fix impl if genuinely broken)
  re-run the full test suite to confirm green
  iteration += 1
```

**Cap at 2 iterations.** A third pass means the rubric is fighting the impl or the AC — that's a signal, not a bug to grind through.

---

## Contradiction-exit signal

If iteration 2 still fails the rubric, **do not silently accept**. Include this block in your final report, verbatim:

```
status: contradiction-exit
rubric_check: [which numbered check kept failing — 1 through 7]
iterations: 2
detail: [one-paragraph description of why the check could not be satisfied — e.g., "AC #3 requires a boundary at length 6, but the impl rejects all inputs regardless of length; can't add a passing length-6 test without changing impl."]
recommendation: [what a human should decide — "AC is ambiguous", "impl is wrong", "test infrastructure missing fake clock", etc.]
```

The orchestrator routes contradiction-exit reports to Stall salvage or human escalation rather than treating the task as done.

---

## What this rubric does **not** cover

- Property-based tests for invariants beyond the AC (the test agent adds these in Step 4/5 of its main flow).
- Golden / snapshot review (separate manual gate).
- Integration tests (flagged for manual device execution).

If you suspect a deeper hardening pass is warranted (e.g., a security-sensitive boundary), the `adversarial-tester` agent is still available as an opt-in spawn — but it is no longer in the default Phase-3 loop.
