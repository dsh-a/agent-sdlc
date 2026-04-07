# UI Story

You are about to work on a UI feature. Before writing any code, complete the following steps in order.

## Step 1 — Load design context

Read the design context file:
@documentation/DESIGN.md

## Step 2 — Load architecture context

This is a Flutter app using MVVM (ChangeNotifier ViewModels + Provider). Views must:
- Call methods on the ViewModel only — never repositories, services, or use cases directly
- Use `Theme.of(context).textTheme` and `Theme.of(context).colorScheme` — never hardcoded styles
- Use `const` constructors wherever possible
- Break large `build()` methods into small, private `Widget` classes
- Never perform network calls or heavy computation inside `build()`
- Use `ListView.builder` / `SliverList` for any list longer than a handful of static items

## Step 3 — Understand the task

The UI story to work on: **$ARGUMENTS**

If $ARGUMENTS is empty, ask the user to describe:
1. What screen or component are we building or modifying?
2. What is the user trying to accomplish on this screen?
3. Are there any existing related views or ViewModels to check for consistency?

## Step 4 — Gather acceptance criteria

Search `agent_tasks/` for the PRD or story that governs this UI work:
- Extract the functional requirements and acceptance criteria relevant to this view
- These drive what the UI must do — not just what it looks like

If no PRD exists, ask the user for the acceptance criteria before proceeding.

## Step 5 — Explore before building

Before writing any code:
- Find and read any existing related View or ViewModel files for this feature area
- Check `lib/ui/core/theme/` for existing theme extensions, color tokens, and text styles in use
- Check `lib/ui/core/widgets/` for reusable components that could be used
- Identify whether a ViewModel already exists or needs to be created
- Identify whether this needs a new route in `lib/router.dart`

## Step 6 — Propose before implementing

Summarize your plan in plain language:
- What the screen/component will look like and why (reference design principles where relevant)
- What widgets you'll use for structure (and what you're deliberately avoiding)
- Whether you're using a bottom sheet, modal, or in-tree collapsible — and why
- Any new ViewModel methods or state needed
- How the acceptance criteria from Step 4 will be satisfied by this UI

Wait for user approval before writing code.

## Step 7 — Implement

Follow these conventions:

### ViewModel (if creating/modifying)
- Extend `ChangeNotifier`
- Dependencies via constructor (use cases, facades — never repos directly)
- Expose state via getters (`isLoading`, `errorMessage`, data fields)
- Expose actions as public methods
- Use `Logger`, never `print`
- Follow class member order from CLAUDE.md

### View
- Use `context.watch<ViewModel>()` or `context.read<ViewModel>()` from Provider
- Use theme tokens: `Theme.of(context).textTheme`, `Theme.of(context).colorScheme`
- Use `const` constructors wherever possible
- Break `build()` into small private widget methods/classes when it exceeds ~40 lines
- Use `Key` values for widgets that need to be found in tests
- Handle loading and error states explicitly

### File locations
- ViewModel: `lib/ui/<feature>/view_models/<feature>_view_model.dart`
- View: `lib/ui/<feature>/views/<feature>_view.dart`
- Route: `lib/router.dart`
- DI: `lib/dependencies/di_view_models.dart`

## Step 8 — Write widget tests

Every view created or significantly modified must have widget tests. Do not skip this step.

### Required coverage

For each view, write widget tests that verify:

1. **Renders correctly** — key widgets are present in the initial state (text, buttons, inputs)
2. **Loading state** — if the view has a loading state, verify it shows the loading indicator and disables interactions
3. **Error state** — if the view has an error state, verify the error message is displayed
4. **User interactions** — tap buttons, enter text, toggle switches — verify the ViewModel methods are called with correct arguments
5. **AC-driven tests** — for each UI-relevant acceptance criterion from Step 4, write a widget test that verifies the criterion through the rendered widget tree

### Golden tests

For views that have significant visual design (not simple forms), generate a golden test:

```dart
testWidgets('matches golden file', (tester) async {
  await tester.pumpWidget(buildTestApp(viewModel));
  await tester.pumpAndSettle();
  await expectLater(
    find.byType(MyView),
    matchesGoldenFile('goldens/my_view_default.png'),
  );
});
```

Generate golden files for:
- Default/empty state
- Populated state (with representative data)
- Error state (if visually distinct)

Golden files are stored in `test/goldens/` mirroring the view path. On first run, generate with `flutter test --update-goldens <test_file>`. Present the golden update command to the user — **never auto-update goldens without user review**.

### Test file location

Widget tests for views go in the test directory mirroring lib/:
`lib/ui/<feature>/views/<view>.dart` → `test/ui/<feature>/<view>_test.dart`

### Patterns

- Wrap the widget under test with the necessary Providers (ViewModel, services) — reuse `test_helpers.dart` where possible
- Use `tester.pumpAndSettle()` after interactions that trigger animations or async work
- Use `find.byKey(Key(...))` for widgets that need precise selection — ensure the view sets `Key` values on testable widgets
- Mock the ViewModel for isolated view tests; use a real ViewModel with mocked dependencies for integration-style widget tests

## Step 9 — Verify

- Run `flutter analyze`
- Run the widget tests: `flutter test <test_file_path>`
- If golden tests were created, remind the user to review the golden images
- Confirm the acceptance criteria from Step 4 are satisfied
