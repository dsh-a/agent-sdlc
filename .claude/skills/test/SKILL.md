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

- Check if a test file already exists (test path should mirror lib/ structure)
- Read `test/test_helpers.dart` for shared mocks and utilities (e.g. `MockAuthService`, `fakeAuthResponse`, `createTestApp`)
- Reuse existing mocks from test_helpers.dart before creating new ones
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
- State changes (isLoading, errorMessage, notifyListeners)
- Property-based tests for any critical function (see Step 6 — Property-based tests)

### Present the plan as a checklist
Format each AC-driven test as:
`- [ ] AC <section>: <criterion summary> → test: <what the test does>`

List non-AC tests in a separate "Additional" section.

Wait for user approval before writing.

## Step 6 — Write the tests

Follow these conventions exactly:

### File location and naming
- Test path mirrors `lib/` structure: `lib/ui/auth/view_models/login_view_model.dart` → `test/ui/auth/login_view_model_test.dart`
- File name: `<class_under_test>_test.dart`

### Structure
- Use `group()` to organize by method or behavior
- Each `test()` should verify exactly one assertion (one `expect` per test)
- Use descriptive test names that state the expected outcome
- Pattern: **Arrange → Act → Assert** — blank lines separating each phase

### Mocking
- Use `mocktail` for mocks (`extends Mock implements <Interface>`)
- Prefer reusing mocks from `test/test_helpers.dart` over defining new ones
- If new mocks are needed for multiple test files, add them to `test_helpers.dart`
- If new mocks are only for this test file, define them at the top of the file
- Use `registerFallbackValue()` in `setUpAll` for any enum or model types passed to `any()`

### Setup
- Declare dependencies and the class under test as `late` variables at the group/main level
- Instantiate everything in `setUp()` so each test starts fresh

### Widget tests — Views

Widget tests verify that a View renders correctly and responds to user interaction. They run headlessly — no device or emulator needed.

**Setup pattern:**
```dart
Widget buildTestApp(MyViewModel viewModel) {
  return MultiProvider(
    providers: [
      ChangeNotifierProvider<MyViewModel>.value(value: viewModel),
      // Add other required providers
    ],
    child: const MaterialApp(home: MyView()),
  );
}
```
Reuse helpers from `test/test_helpers.dart` where possible. If creating new helpers needed by multiple test files, add them to test_helpers.dart.

**What to test in a View:**

| Category | What to verify | Example |
|---|---|---|
| **Rendering** | Key widgets present in initial state | `expect(find.byType(TextField), findsNWidgets(2))` |
| **Loading state** | Loading indicator shown, interactions disabled | `expect(find.byType(CircularProgressIndicator), findsOneWidget)` |
| **Error state** | Error message displayed to user | `expect(find.text('Invalid email'), findsOneWidget)` |
| **Empty state** | Appropriate message when no data | `expect(find.text('No exercises found'), findsOneWidget)` |
| **Interactions** | Tap/input triggers correct ViewModel method | `await tester.tap(find.byType(ElevatedButton)); verify(() => vm.login()).called(1)` |
| **Navigation** | Correct route pushed on action | Use `MockGoRouter` or verify `GoRouter.of(context).go()` |
| **Conditional UI** | Auth-gated elements hidden for guests | `expect(find.byKey(Key('share_button')), findsNothing)` |

**Interaction testing pattern:**
```dart
testWidgets('tapping Save calls viewModel.save()', (tester) async {
  await tester.pumpWidget(buildTestApp(mockViewModel));
  await tester.tap(find.byKey(const Key('save_button')));
  await tester.pumpAndSettle();
  verify(() => mockViewModel.save()).called(1);
});
```

**Text input pattern:**
```dart
testWidgets('entering email updates viewModel', (tester) async {
  await tester.pumpWidget(buildTestApp(mockViewModel));
  await tester.enterText(find.byKey(const Key('email_field')), 'test@example.com');
  verify(() => mockViewModel.setEmail('test@example.com')).called(1);
});
```

**State-driven rendering — test ViewModel state changes reflected in UI:**
```dart
testWidgets('shows error message when viewModel has error', (tester) async {
  when(() => mockViewModel.errorMessage).thenReturn('Network error');
  await tester.pumpWidget(buildTestApp(mockViewModel));
  expect(find.text('Network error'), findsOneWidget);
});
```

### Widget tests — ViewModels

ViewModel tests are unit tests (no widget tree), but they verify UI-facing behavior:

| Category | What to verify |
|---|---|
| **State transitions** | `isLoading` goes true → false during async operations |
| **Error handling** | `errorMessage` is set on failure, cleared on retry |
| **notifyListeners** | Called after state changes (use a listener mock or count) |
| **Input validation** | Invalid inputs produce error states before calling services |

### Golden tests

Golden tests capture a screenshot and compare against a blessed baseline. They catch visual regressions that widget assertions miss (wrong colors, broken layouts, clipped text).

**When to write golden tests:**
- Views with significant visual design (not simple forms or dialogs)
- Components used across multiple screens (shared widgets)
- Views where the design spec (DESIGN.md) specifies particular visual qualities

**When NOT to write golden tests:**
- Views that are purely data-driven with no custom styling
- Views still in rapid iteration (goldens will need constant updating)

**Pattern:**
```dart
testWidgets('default state matches golden', (tester) async {
  await tester.pumpWidget(buildTestApp(viewModel));
  await tester.pumpAndSettle();
  await expectLater(
    find.byType(MyView),
    matchesGoldenFile('goldens/my_view_default.png'),
  );
});
```

**Golden file location:** `test/goldens/` mirroring the view path.

**Generate goldens:** `flutter test --update-goldens <test_file>`

**Important:** Never auto-update goldens. Always present the update command to the user and let them review the generated images. Golden updates are a visual approval gate.

### Property-based tests

For any function that implements a rule that must hold across a range of inputs — validation, numeric calculation, string transformation, collection operation — write at least one property test using a loop over representative values:

```dart
// Example: password validation must hold for all lengths around the boundary
for (final entry in {
  0: false,
  1: false,
  5: false,
  6: true,   // boundary — must pass
  7: true,
  100: true,
}.entries) {
  test('password of length ${entry.key} is ${entry.value ? "valid" : "invalid"}',
      () {
    final result = validatePassword('x' * entry.key);
    expect(result.isValid, entry.value);
  });
}
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
```dart
// integration_test/login_flow_test.dart
import 'package:integration_test/integration_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:your_app/main.dart' as app; // Replace 'your_app' with your package name

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('user can log in and reach home', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    // ... interact with the full app
  });
}
```

Integration tests are **not run by the pre-commit hook or CI by default** — they require a running device. Flag them for manual execution in the cycle report.

### What NOT to do
- Do not test private methods — test them through public API
- Do not test generated code (`.g.dart`)
- Do not use `print` — use `expect` for assertions
- Do not write integration tests in unit test files
- Do not auto-update golden files without user approval

## Step 7 — Run and verify

Run validation in this order:

### 1. Static analysis first
Run `flutter analyze` (or `mcp__dart__analyze_files`). Fix all errors and warnings before running tests. A test that compiles is not the same as a test that is correct.

### 2. Full test suite
Run `flutter test` — not just the new test file — to catch regressions in existing tests. Fix any failures before proceeding.

### 3. Adversarial second pass (subagent)

Spawn the `adversarial-tester` agent:

```
Agent(subagent_type: "adversarial-tester",
      prompt: "Source: [path]. Tests: [path]. Spec: [spec from Step 5].")
```

If it finds gaps, add the new tests (and fix the implementation if genuinely broken), then re-run the full suite.

Report final state: analyze clean, full suite passing, adversarial cases found/resolved.
