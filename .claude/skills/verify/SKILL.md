# Verify — Independent AC Coverage Audit

You are an independent auditor. You did NOT write the code or tests being verified. Your job is to evaluate whether the implementation and test suite genuinely satisfy the acceptance criteria in the PRD — with fresh eyes and no assumptions.

The PRD or feature to verify: **$ARGUMENTS**

## Live State (auto-injected)

Recent verify reports:
!`ls agent_tasks/reports/verify-*.md 2>/dev/null | tail -3 || echo "none"`

Current branch:
!`git branch --show-current`

If $ARGUMENTS is empty, ask the user for the path to a PRD file (e.g. `agent_tasks/prd-feature-name.md`).

---

## Step 1 — Extract acceptance criteria

Read the PRD file. Extract every testable criterion from:
- **Functional requirements** (numbered items)
- **User stories** (the "so that" implies a verifiable outcome)
- **Acceptance criteria** (if explicitly listed)

Produce a numbered checklist of criteria. Each entry should be a single, specific, testable statement. If a requirement contains multiple conditions, split them.

Example:
```
1. Profile is inserted exactly once during registration
2. isAuthenticated is set to true when creating authenticated user
3. Email field shows inline error when empty
4. Email field shows inline error when format is invalid
5. Password shorter than 6 characters is rejected
...
```

Present this list to the user and ask: **"Is this the complete set of criteria to verify against?"** Wait for confirmation before proceeding.

---

## Step 2 — Locate the test suite

If file paths were provided (from the task file's "Relevant Files" section), use those directly — skip searching.

Otherwise, search `test/` for all test files relevant to this feature. Use the PRD's "Relevant Files" section if available, but also search independently — tests may exist in unexpected locations.

For each test file found, read it and catalog what it tests. Build a map of: test file → list of behaviors verified.

---

## Step 3 — Locate the implementation

If source file paths were provided, use those directly — skip searching.

Otherwise, search `src/` (or the project's source root) for all source files relevant to this feature. Read each one to understand what was actually implemented.

---

## Step 4 — Audit: AC → Test coverage

For each acceptance criterion from Step 1, determine:

### A. Does a test exist?
Search the test catalog from Step 2 for a test that targets this criterion. Record the test file, test name, and line number.

### B. Does the test actually verify the criterion?
Read the test carefully. Apply these checks:

1. **Naive shortcut test**: If the implementation were replaced with a hardcoded return value, a simple regex, or a no-op stub, would this test still pass? If yes → **WEAK TEST**.

2. **Boundary test**: If the criterion specifies a threshold (e.g., "at least 6 characters"), does the test check both sides of the boundary (5 fails, 6 passes)? If only one side → **INCOMPLETE BOUNDARY**.

3. **Side effect test**: If the criterion specifies something must happen (e.g., "inserted exactly once"), does the test verify the side effect (e.g., `verify(...).called(1)`) or just check a return value? If only return value → **MISSING SIDE EFFECT CHECK**.

4. **Negative path test**: If the criterion implies something must NOT happen (e.g., "no auth call made when validation fails"), is there a `verifyNever(...)` or equivalent? If missing → **MISSING NEGATIVE ASSERTION**.

5. **Independence test**: Does the test set up its own state, or does it rely on state from a previous test? If coupled → **TEST COUPLING**.

6. **Adversarial coverage**: Are there inputs specifically designed to expose silent failures — off-by-one values, null propagation, type coercion, concurrent state mutations — that no existing test covers? If obvious adversarial cases are unprotected → **MISSING ADVERSARIAL COVERAGE**.

### C. Does the implementation satisfy the criterion?
Read the implementation. Does the code actually do what the criterion requires, or does it appear to take a shortcut?

---

## Step 4b — Scope creep audit

Compare what was implemented against what was asked:

1. Run `git diff develop --name-only` to list all files changed relative to the `develop` branch
2. For each changed file, determine whether the change is:
   - **In scope**: directly required by the PRD or a necessary side effect (e.g., updating an adapter when a model changes)
   - **Out of scope**: changes beyond what the task required — refactors, dependency additions, config changes, unrelated bug fixes
3. Flag out-of-scope changes in the report under a **"Scope Creep"** section

Scope creep is the primary source of agent-introduced regressions. Out-of-scope changes are not necessarily wrong, but they require conscious review.

---

## Step 5 — Produce the audit report

Generate a report with three sections:

### Coverage Matrix

| # | Acceptance Criterion | Test File | Test Name | Verdict |
|---|---|---|---|---|
| 1 | Profile inserted exactly once | user.service.test.ts:45 | `inserts profile once on registration` | PASS |
| 2 | isAuthenticated set to true | user.service.test.ts:62 | `sets isAuthenticated true` | WEAK — test checks return value but not DB state |
| 3 | Inline error on empty email | — | — | NO TEST |

Verdicts:
- **PASS** — criterion is tested and the test is robust
- **WEAK** — test exists but would pass with a naive implementation (explain why)
- **INCOMPLETE** — test exists but missing boundary/negative/side-effect checks (explain what's missing)
- **NO TEST** — no test found for this criterion
- **NO IMPL** — criterion is not implemented in the code

### Summary Statistics

```
Total criteria:    N
PASS:              N (N%)
WEAK:              N (N%)
INCOMPLETE:        N (N%)
NO TEST:           N (N%)
NO IMPL:           N (N%)
```

### Scope Creep

List any out-of-scope changes identified in Step 4b. For each:
- File changed
- Nature of the change
- Assessment: benign side effect or potential regression risk

If no out-of-scope changes were found, write: "None detected."

### Recommendations

For each non-PASS verdict, provide a specific, actionable recommendation:
- For WEAK: explain what the test should verify instead
- For INCOMPLETE: specify the missing assertion or boundary check
- For NO TEST: describe what test should be written and where
- For NO IMPL: flag as a gap the user needs to address

---

## Step 6 — Verify non-functional requirements

If the PRD includes non-functional requirements (performance, security, observability), check:
- Are there tests or assertions for these?
- Does the implementation include proper logging, error handling, and null/undefined safety?
- Are there any obvious security issues (hardcoded values, missing validation at system boundaries)?

Add findings to the report under a "Non-Functional" section.

---

## Step 7 — Live application verification (if available)

If the application is running and accessible (e.g., via a dev server, browser, or connected tooling):

1. Check each UI-facing AC by inspecting the running application
2. For each criterion, verify expected elements are present and interactive:
   - Buttons, inputs, labels mentioned in the AC
   - Conditional UI (e.g., "share button is hidden for guests") — verify presence/absence based on state
   - Loading indicators, error messages — trigger the relevant state and re-check
3. Check for runtime errors in the console or error reporting
4. Add a "Live Verification" section to the audit report with findings

**If no running app is available**, skip this step. Note in the report: "Live verification skipped — no running app connected."

This step supplements — not replaces — the test-based audit. An element being present doesn't mean it behaves correctly; a test passing doesn't mean it renders. Both are needed.

---

## Step 8 — Snapshot / visual regression test review (if applicable)

Check for snapshot or visual regression tests related to this feature's UI components. Common locations: `__snapshots__/`, `test/snapshots/`, `test/goldens/`, or framework-specific snapshot directories. If they exist:

1. Note which views/components have snapshot coverage and which don't
2. Check whether snapshot tests are included in the test suite and passing
3. If components lack snapshot coverage, recommend adding them in the Recommendations section

If no snapshot tests exist for any component in this feature and the project uses snapshot testing, add to Recommendations: "No snapshot test coverage — visual regressions are not detectable. Consider adding snapshot tests for [specific components]."

---

## Step 9 — Final check

Run in this order:
1. `npm run typecheck && npm run lint` — fix all errors before running tests
2. `npm test` — full test suite, not just feature-specific tests

Both must be green before closing the audit. Report results.

Present the full audit report and ask: **"Would you like me to flag specific items for the implementing agent to fix?"**

---

## Step 10 — Update run report

Check `agent_tasks/reports/` for a run report matching this PRD (by filename or PRD path reference). If one exists:
- Update the `/verify results` section under **Effectiveness** with your verdict counts
- Add any **Skill gaps observed** you identified during the audit

If no run report exists, save your audit report as a standalone file. Derive the report name directly from the PRD filename so the two are traceable by name:
- PRD `agent_tasks/prd-login-registration.md` → report `agent_tasks/reports/verify-prd-login-registration-2026-04-04.md`

Include this header block at the top of every report file:

```yaml
PRD: agent_tasks/prd-[feature-name].md
Story: [story number or title from the PRD]
Verified: [YYYY-MM-DD]
Verdict: PASS | PARTIAL | FAIL
```

This ensures every report is traceable to its source PRD by filename and by header, and that `/self-improve` can correlate reports with the features they cover.

This data feeds into `/self-improve` for continuous improvement of the pipeline.
