# Write Tests

You are about to write tests. Follow these steps in order.

## Step 1 — Identify the target

The class or feature to test: **$ARGUMENTS**

If $ARGUMENTS is empty, ask the user what class, method, or feature they want tested.

## Step 2 — Gather acceptance criteria

Before reading any code, search for the PRD or story that governs this work:
- Search `agent_tasks/` for PRD files mentioning the target class, feature, or story number
- Extract every **functional requirement** and **acceptance criterion** that applies to the class under test
- List them explicitly — these are the ground truth for what the tests must verify

If no PRD or story exists, ask the user: "What are the acceptance criteria for this feature?" Do not proceed without them.

## Step 3 — Read the source

- Read the source file for the class under test
- Identify its public API, constructor dependencies, and edge cases
- Note which dependencies need mocking vs faking
- **Cross-reference the implementation against the acceptance criteria from Step 2.** Flag any criteria that the current implementation does not appear to satisfy — these are potential gaps the user needs to know about before you write tests that would pass against incomplete code.

## Step 4 — Check for existing tests and helpers

- Check if a test file already exists (test path should mirror source structure)
- Search for shared test helpers, fixtures, and utilities (e.g., `test/helpers/`, `test/utils/`, `test/setup.ts`, or similar)
- Reuse existing mocks and helpers before creating new ones
- If the test file exists, extend it rather than rewriting

## Step 5 — Plan the test cases

### Write the spec/invariants first

Before listing test cases, produce a formal spec for the class or function under test. For each public method, document:

- **Inputs**: valid types, ranges, and constraints (e.g., `email`: non-empty string, must contain `@`)
- **Outputs**: return values and side effects for each input class
- **Invariants**: conditions that must hold for all valid inputs (e.g., result is never null when input is valid)
- **Edge cases**: boundary values, empty/null inputs, maximum values, concurrent calls

Format as a bullet list — one method per block. This spec is the source of truth: every test case below must trace back to a spec entry.

### Acceptance-criteria-driven tests (required)
For each acceptance criterion from Step 2, write at least one test that:
- **Verifies the real behavior**, not a trivial proxy for it. Ask yourself: "If the implementation were faked with a naive shortcut (hardcoded return, regex-only check, no-op stub), would this test still pass?" If yes, the test is too weak — redesign it.
- **Tests the boundary the criterion implies.** E.g., "password must be at least 6 characters" requires tests at length 5 (fail) AND length 6 (pass), not just length 0 and 10.
- **Verifies side effects when specified.** E.g., "profile is inserted exactly once" → use `verify(...).called(1)`, not just checking the return value.

### Additional coverage
After all acceptance criteria are covered, add tests for:
- Error/exception handling paths not already covered
- Edge cases (null, empty, boundary values)
- State changes (loading flags, error states, event emissions)
- Property-based tests for any critical function (see Step 6 — Property-based tests)

### Present the plan as a checklist
Format each AC-driven test as:
`- [ ] AC <section>: <criterion summary> → test: <what the test does>`

List non-AC tests in a separate "Additional" section.

Wait for user approval before writing.

## Step 6 — Write the tests

Follow these conventions exactly:

### File location and naming
- Test path mirrors source structure: `src/auth/services/login.service.ts` → `test/auth/login.service.test.ts` (adapt to the project's existing test layout)
- File name: `<class_under_test>.test.ts` or `<class_under_test>.spec.ts` — match the project's existing convention

### Structure
- Use `group()` to organize by method or behavior
- Each `test()` should verify exactly one assertion (one `expect` per test)
- Use descriptive test names that state the expected outcome
- Pattern: **Arrange → Act → Assert** — blank lines separating each phase

### Mocking
- Use the project's mocking approach (e.g., `jest.mock()`, `vi.mock()`, `sinon`, manual test doubles)
- Reuse existing mock factories and helpers before defining new ones
- If new mocks are needed across multiple test files, add them to the shared test helpers
- If new mocks are only for this test file, define them at the top of the file
- Mock at boundaries (external services, databases, APIs) — don't mock the thing being tested

### Setup
- Declare dependencies and the class under test at the suite/describe level
- Instantiate everything in `beforeEach()` (or equivalent) so each test starts fresh

### Component / UI tests

Component tests verify that a UI component renders correctly and responds to user interaction.

**Setup pattern:** Render the component with required providers, stores, or context wrappers. Reuse existing render helpers from shared test utilities.

**What to test in a component:**

| Category | What to verify |
|---|---|
| **Rendering** | Key elements present in initial state |
| **Loading state** | Loading indicator shown, interactions disabled |
| **Error state** | Error message displayed to user |
| **Empty state** | Appropriate message when no data |
| **Interactions** | Click/input triggers correct handler or state change |
| **Navigation** | Correct route pushed on action |
| **Conditional UI** | Auth-gated elements hidden for unauthorized users |

**Interaction testing pattern:**
```typescript
it('clicking Save calls the save handler', async () => {
  const onSave = jest.fn(); // or vi.fn()
  render(<MyComponent onSave={onSave} />);
  await userEvent.click(screen.getByRole('button', { name: /save/i }));
  expect(onSave).toHaveBeenCalledTimes(1);
});
```

**State-driven rendering:**
```typescript
it('shows error message when error state is set', () => {
  render(<MyComponent error="Network error" />);
  expect(screen.getByText('Network error')).toBeInTheDocument();
});
```

Adapt patterns to your project's UI framework and testing library. The principles (test rendering, interactions, state-driven UI) apply regardless of framework.

### State / view model tests

State management tests are unit tests (no UI rendering) that verify state logic:

| Category | What to verify |
|---|---|
| **State transitions** | Loading flag goes true → false during async operations |
| **Error handling** | Error state set on failure, cleared on retry |
| **Subscribers notified** | State changes propagate to listeners/subscribers |
| **Input validation** | Invalid inputs produce error states before calling services |

### Snapshot tests

Snapshot tests capture rendered output and compare against a blessed baseline. They catch regressions that assertion-based tests miss (wrong structure, broken layouts, unexpected changes).

**When to write snapshot tests:**
- Components with significant visual design (not simple wrappers)
- Shared components used across multiple screens
- Components where the design spec (DESIGN.md) specifies particular visual qualities

**When NOT to write snapshot tests:**
- Components that are purely data-driven with no custom styling
- Components still in rapid iteration (snapshots will need constant updating)

**Snapshot file location:** check the project's existing pattern (e.g., `__snapshots__/`, `test/snapshots/`).

**Update snapshots:** `npm test -- --updateSnapshot <test_file>` (or framework equivalent)

**Important:** Never auto-update snapshots. Always present the update command to the user and let them review the changes. Snapshot updates are a visual approval gate.

### Property-based tests

For any function that implements a rule that must hold across a range of inputs — validation, numeric calculation, string transformation, collection operation — write at least one property test using a loop over representative values:

```typescript
// Example: password validation must hold for all lengths around the boundary
const cases: [number, boolean][] = [
  [0, false],
  [1, false],
  [5, false],
  [6, true],   // boundary — must pass
  [7, true],
  [100, true],
];

it.each(cases)('password of length %i is %s', (length, expected) => {
  expect(validatePassword('x'.repeat(length)).isValid).toBe(expected);
});
```

**Target functions for property tests:**
- Validation functions (email, password, form fields)
- Numeric calculations (scores, durations, reps/sets)
- String transformations (slugify, format, trim)
- Collection operations (filter, sort, dedup)

**What the test must assert:** the invariant, not just one outcome. Ask: "Does this hold for all valid inputs?" If yes, the loop covers the range; if the invariant has a boundary, test both sides of it.

### Integration tests

Integration tests run the full app on a device or emulator and exercise end-to-end user flows. They live in `integration_test/`.

**When to write integration tests:**
- Critical user flows (login → home, create routine → save, start session → complete)
- Flows that cross multiple screens and involve navigation
- Flows where widget tests can't catch the interaction between screens

**When NOT to write integration tests:**
- Single-screen behavior (use widget tests)
- Business logic (use unit tests)
- During `/cycle` autonomous execution (integration tests require a running device — flag them as follow-up items in the cycle report)

**Pattern:**
```typescript
// e2e/login-flow.test.ts
import { test, expect } from '@playwright/test'; // or your e2e framework of choice

test('user can log in and reach home', async ({ page }) => {
  await page.goto('/login');
  // ... interact with the full app
    // ... interact with the full app
  });
}
```

Integration tests are **not run by the pre-commit hook or CI by default** — they require a running device. Flag them for manual execution in the cycle report.

### What NOT to do
- Do not test private methods — test them through public API
- Do not test generated code (auto-generated types, codegen output)
- Do not use `console.log` for assertions — use `expect`
- Do not write integration tests in unit test files
- Do not auto-update snapshot files without user approval

## Step 7 — Run and verify

Run validation in this order:

### 1. Static analysis first
Run `npm run typecheck && npm run lint`. Fix all errors and warnings before running tests. A test that compiles is not the same as a test that is correct.

### 2. Full test suite
Run `npm test` — not just the new test file — to catch regressions in existing tests. Fix any failures before proceeding.

### 3. Adversarial second pass (subagent)

Spawn the `adversarial-tester` agent:

```
Agent(subagent_type: "adversarial-tester",
      prompt: "Source: [path]. Tests: [path]. Spec: [spec from Step 5].")
```

If it finds gaps, add the new tests (and fix the implementation if genuinely broken), then re-run the full suite.

Report final state: analyze clean, full suite passing, adversarial cases found/resolved.
