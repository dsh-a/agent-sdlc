---
name: ac-audit-rubric
description: The verify agent's AC → test coverage audit rubric. Six attack vectors, five verdicts, the coverage-matrix output format. Mirrors the test-rubric (5.4.1) checks from the auditor's perspective — instead of self-iteration, this rubric produces verdicts an independent reviewer assigns to existing tests.
disable-model-invocation: true
---

# AC Audit Rubric

For each acceptance criterion, audit whether the existing tests genuinely verify it and assign a verdict. You are an **independent auditor** — you did not write the tests. Cross-references the `test-rubric` skill (5.4.1) for the underlying check semantics; the verdicts and matrix below are auditor-specific.

---

## Check 0 — does a test exist at all?

**Before any other check, name the test.** Cite a test file and a test name for this
criterion. If you cannot, the verdict is **NO TEST** — regardless of how complete the
implementation looks, and regardless of how many of the six checks below you could
answer in the abstract.

**The test must assert *this* criterion, not merely live in the right file.** If no assertion would fail when the criterion is violated, the verdict is NO TEST — not INCOMPLETE or WEAK, which describe a test that exists.

This gate exists because the six checks all presuppose a test, and without it stated the
audit drifts. Measured 2026-09-20 across twelve models on a fixture where one criterion
was implemented with no test asserting it: answers scattered across PASS, WEAK and
INCOMPLETE, and almost none said NO TEST. Every one of those verdicts reports a criterion
as audited when nothing verifies it — an AC audit signing off untested code while
reporting coverage, which is the precise failure this rubric exists to prevent.

An empty **Test File** or **Test Name** cell in the coverage matrix is therefore not a
formatting lapse. It is the verdict: a row with no citation is NO TEST or NO IMPL, never
PASS, WEAK or INCOMPLETE.

**Precedence when more than one applies:**

| Situation | Verdict |
|---|---|
| Not implemented (whether or not a test exists) | **NO IMPL** |
| Implemented, no test found | **NO TEST** |
| Implemented, test found | run the six checks below |

NO IMPL outranks NO TEST. A criterion the code does not satisfy is a gap in the feature;
whether someone wrote a test for the thing that does not exist is a detail beneath it.
The same measurement found models splitting on exactly this case, because the rubric had
never said which wins.

---

## Per-AC checks

Once Check 0 has named a test, apply these six checks:

1. **Naive-shortcut test.** If the implementation were replaced with a hardcoded return or no-op, would the test still pass? Yes → **WEAK TEST**.
2. **Boundary test.** If the AC specifies a threshold, does the test check both sides? Only one side → **INCOMPLETE BOUNDARY**.
3. **Side-effect test.** If the AC says something must happen, does the test use `verify(...).called(1)` (or framework equivalent) rather than just a return value? Missing → **MISSING SIDE EFFECT CHECK**.
4. **Negative-path test.** If the AC implies something must NOT happen, is there a `verifyNever(...)` or equivalent? Missing → **MISSING NEGATIVE ASSERTION**.
5. **Independence test.** Does the test set up its own state, or does it rely on a previous test? Coupled → **TEST COUPLING**.
6. **Adversarial coverage.** Are obvious silent-failure inputs covered (off-by-one, null propagation, type coercion)? Unprotected → **MISSING ADVERSARIAL COVERAGE**.

Then check the implementation: does the code actually do what the AC requires, or does it take a shortcut?

---

## Verdicts

**One row per AC, always — never a count.** Enumerate every criterion's verdict rather than
reporting how many passed. Predicted AC totals were wrong three times in one session while
the content was right, and only a per-item enumeration told an arithmetic slip apart from a
real coverage gap. `evidence.py enumerate --unit checkbox` is the mechanical half when the
AC list itself changed between two versions of a spec.

For each AC row in the coverage matrix:

| Verdict | Meaning |
|---|---|
| **PASS** | Criterion is tested and the test is robust |
| **WEAK** | Test exists but would pass with a naive implementation |
| **INCOMPLETE** | Test exists but missing boundary / negative / side-effect checks |
| **NO TEST** | Implemented, but no test found for this criterion |
| **NO IMPL** | Criterion is not implemented in the code — outranks NO TEST |

`PASS` requires three things: Check 0 named a real test, that test is robust (all six checks
pass for this AC), AND the implementation actually satisfies the criterion.

**WEAK is not a lesser PASS, and the naive-shortcut check is stricter than it looks.** If a
hardcoded return would satisfy the assertion, the verdict is WEAK even when the
implementation is correct and the criterion is genuinely met — the verdict describes the
*test*, not the code. A test asserting `expect(await repo.getById('x'), isNull)` is WEAK
against "returns null for a missing order", because `return null;` passes it.

---

## Coverage matrix output format

```markdown
### Coverage Matrix

| # | Acceptance Criterion | Test File | Test Name | Verdict |
|---|---|---|---|---|
| 1 | [criterion] | file_test.dart:45 | `test name` | PASS |
```

Follow with summary statistics:

```
Total criteria:    N
PASS:              N
WEAK:              N
INCOMPLETE:        N
NO TEST:           N
NO IMPL:           N
```

---

## Recommendations

For each non-PASS verdict, provide a specific actionable fix:

- **WEAK** → what the test should verify instead
- **INCOMPLETE** → the specific missing assertion or boundary check
- **NO TEST** → what test to write and where
- **NO IMPL** → flag as a gap requiring user action

---

## What this rubric does NOT cover

- Scope-creep audit (changes outside the PRD) — separate verify step.
- Non-functional requirements (performance, security, observability) — separate verify step.
- Snapshot / golden review — separate verify step.
- Implementation correctness audits beyond AC → behavior — that's review's job.
