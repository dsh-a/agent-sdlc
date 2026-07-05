---
name: ac-audit-rubric
description: The verify agent's AC → test coverage audit rubric. Six attack vectors, five verdicts, the coverage-matrix output format. Mirrors the test-rubric (5.4.1) checks from the auditor's perspective — instead of self-iteration, this rubric produces verdicts an independent reviewer assigns to existing tests.
disable-model-invocation: true
---

# AC Audit Rubric

For each acceptance criterion, audit whether the existing tests genuinely verify it and assign a verdict. You are an **independent auditor** — you did not write the tests. Cross-references the `test-rubric` skill (5.4.1) for the underlying check semantics; the verdicts and matrix below are auditor-specific.

---

## Per-AC checks

For each AC, look for a test and apply these six checks:

1. **Naive-shortcut test.** If the implementation were replaced with a hardcoded return or no-op, would the test still pass? Yes → **WEAK TEST**.
2. **Boundary test.** If the AC specifies a threshold, does the test check both sides? Only one side → **INCOMPLETE BOUNDARY**.
3. **Side-effect test.** If the AC says something must happen, does the test use `verify(...).called(1)` (or framework equivalent) rather than just a return value? Missing → **MISSING SIDE EFFECT CHECK**.
4. **Negative-path test.** If the AC implies something must NOT happen, is there a `verifyNever(...)` or equivalent? Missing → **MISSING NEGATIVE ASSERTION**.
5. **Independence test.** Does the test set up its own state, or does it rely on a previous test? Coupled → **TEST COUPLING**.
6. **Adversarial coverage.** Are obvious silent-failure inputs covered (off-by-one, null propagation, type coercion)? Unprotected → **MISSING ADVERSARIAL COVERAGE**.

Then check the implementation: does the code actually do what the AC requires, or does it take a shortcut?

---

## Verdicts

For each AC row in the coverage matrix:

| Verdict | Meaning |
|---|---|
| **PASS** | Criterion is tested and the test is robust |
| **WEAK** | Test exists but would pass with a naive implementation |
| **INCOMPLETE** | Test exists but missing boundary / negative / side-effect checks |
| **NO TEST** | No test found for this criterion |
| **NO IMPL** | Criterion is not implemented in the code |

`PASS` requires both: test is robust (all six checks pass for this AC) AND the implementation actually satisfies the criterion.

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
