---
name: widget-test-patterns
description: Flutter widget-test and ViewModel-test patterns — coverage matrix, setup helpers, golden tests, property-based tests, integration tests. Loaded by test and ui-story agents; single source for these patterns.
disable-model-invocation: true
---

# Widget Test Patterns

Conventions for testing Flutter Views and ViewModels in this codebase. Used by the `test` agent and the `ui-story` agent. Cross-references `flutter-conventions` for layer rules.

---

## File location

Test path mirrors source path: `lib/ui/auth/login_view_model.dart` → `test/ui/auth/login_view_model_test.dart`. File name: `<class_under_test>_test.dart`.

## Structure

- Use `group()` to organize by method or behavior.
- Each `test()` verifies exactly one assertion (one `expect` per test).
- Descriptive names that state the expected outcome.
- Pattern: **Arrange → Act → Assert** with blank lines separating phases.

## Mocking

- `mocktail` is the project default — `class MockX extends Mock implements X`.
- Reuse mocks from `test/test_helpers.dart` over defining new ones; add cross-file mocks back into `test_helpers.dart`.
- `registerFallbackValue()` in `setUpAll` for any enum/model types passed to `any()`.
- For directory-level pattern conflicts (mocktail vs. manual stubs), apply the `pattern-divergence` skill.

## Setup

- Declare dependencies and class-under-test as `late` variables at the group/main level.
- Instantiate everything in `setUp()` so each test starts fresh.

---

## Widget tests — Views

```dart
Widget buildTestApp(MyViewModel viewModel) {
  return MultiProvider(
    providers: [
      ChangeNotifierProvider<MyViewModel>.value(value: viewModel),
    ],
    child: const MaterialApp(home: MyView()),
  );
}
```

Coverage matrix:

| Category | What to verify |
|---|---|
| Rendering | Key widgets present in initial state |
| Loading state | Loading indicator shown, interactions disabled |
| Error state | Error message displayed to user |
| Empty state | Appropriate message when no data |
| Interactions | Tap/input triggers correct ViewModel method |
| Conditional UI | Auth-gated elements hidden for guests |

## Widget tests — ViewModels

| Category | What to verify |
|---|---|
| State transitions | `isLoading` goes true → false during async operations |
| Error handling | `errorMessage` set on failure, cleared on retry |
| notifyListeners | Called after state changes |
| Input validation | Invalid inputs produce error states before calling services |

---

## Golden tests

Write golden tests only for Views with significant visual design or shared components. **Never auto-update goldens** — present the update command in your report for the user to run and review.

Golden file location: `test/goldens/` mirroring the view path.

---

## Property-based tests

For validation, numeric calculation, string transformation, or collection operations:

```dart
for (final entry in {
  5: false,
  6: true,   // boundary
  7: true,
}.entries) {
  test('password of length ${entry.key} is ${entry.value ? "valid" : "invalid"}', () {
    expect(validatePassword('x' * entry.key).isValid, entry.value);
  });
}
```

---

## Integration tests

Write integration tests only for critical multi-screen flows. **Flag them in your report as requiring manual device execution — do not attempt to run them autonomously.** Live in `integration_test/`. Not run by pre-commit or CI by default.

---

## What NOT to do

- Do not test private methods — test through public API.
- Do not test generated code (`.g.dart`).
- Do not auto-update golden files.
- Do not write integration tests in unit test files.
