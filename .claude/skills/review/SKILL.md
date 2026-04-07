---
disable-model-invocation: true
---

# Review — Independent Code Review

You are an independent code reviewer. You did NOT write the code being reviewed. Your job is to evaluate code quality, architecture adherence, and convention compliance — complementing `/verify` which focuses on acceptance criteria coverage.

The feature branch or PR to review: **$ARGUMENTS**

## Live State (auto-injected)

Current branch:
!`git branch --show-current`

Changed files vs master:
!`git diff --name-only master...HEAD 2>/dev/null | head -20`

If $ARGUMENTS is empty, ask the user for a branch name or PR number.

---

## Step 1 — Gather the changeset

- If given a branch: `git diff develop...[branch]` to see all changes
- If given a PR number: use `gh pr diff [number]`
- Catalog every file changed, added, or deleted
- Read the associated PRD (search `agent_tasks/` by feature name) for context on what was intended

---

## Step 2 — Architecture review

Check that the changes respect the project's layer boundaries:

- **Domain layer** (`lib/domain/`): no Flutter imports, no data layer imports
- **Data layer** (`lib/data/`): no UI imports, may import domain
- **UI layer** (`lib/ui/`): no direct data layer imports — must go through ViewModels which use use cases/facades

For each violation found, note the file, line, and which boundary is crossed.

---

## Step 3 — Convention compliance

Check each changed file against CLAUDE.md conventions:

### Class member order
1. External package deps
2. Internal deps
3. Variables
4. Constructors
5. Public methods
6. Protected / internal methods
7. Private methods

### Code style
- **Naming**: `PascalCase` classes/enums, `camelCase` members/variables, `snake_case` files
- **Line length**: 80 characters max
- **Functions**: single purpose, aim for <20 lines
- **Logging**: uses `Logger`, never `print`
- **Null safety**: sound null-safe, avoids `!` unless guaranteed
- **Comments**: `///` for public API, comments explain *why* not *what*

### Pattern compliance
- ViewModels extend `ChangeNotifier`, wired via `Provider`
- Views never call repositories, services, or use cases directly
- Models with sync: use `Syncable` mixin, have `copyWith`
- Adapters implement `ModelAdapter` with all required methods
- Repositories implement `IRepository<T>` interface
- New dependencies follow the DI load order in `dependencies.dart`

---

## Step 4 — Code quality

### Complexity
- Flag methods longer than 20 lines
- Flag deeply nested logic (3+ levels)
- Flag methods with more than 3 parameters that could use a parameter object

### Duplication
- Check if new code duplicates existing utilities in `lib/utils/`
- Check if similar logic exists elsewhere that could be shared

### Error handling
- Async methods should have proper error handling
- Errors at system boundaries (Supabase calls, Drift operations) should be caught
- Internal code between trusted layers does not need excessive defensive checks

### Security (for code touching auth, user data, or network)
- No hardcoded credentials or tokens
- User input validated before use
- No SQL injection vectors in raw queries (if any)

---

## Step 5 — Test review

For each changed source file, check:
- Does a corresponding test file exist?
- Do the tests cover the changed behavior?
- Are mocks appropriate (not mocking the thing being tested)?

This is a lighter check than `/verify` — flag missing tests but don't audit test quality in depth.

---

## Step 6 — Produce the review

### Review format

```
## Architecture
[violations found or "Clean — no layer violations"]

## Convention Compliance
[issues found, grouped by type, or "All conventions followed"]

## Code Quality
[complexity, duplication, error handling findings]

## Test Coverage
[missing or insufficient tests]

## Summary
- Critical issues (must fix): [n]
- Warnings (should fix): [n]
- Suggestions (nice to have): [n]
- Verdict: [APPROVE / REQUEST CHANGES / NEEDS DISCUSSION]
```

For each finding, include:
- File path and line number
- What the issue is
- Suggested fix (be specific)
- Severity: **critical** (blocks merge), **warning** (should fix), **suggestion** (optional)

---

## Step 7 — Present and offer fixes

Present the review and ask: **"Would you like me to fix the critical issues and warnings?"**

- If yes: fix them on the feature branch, run `flutter test` and `flutter analyze`, commit the fixes
- If no: the review stands as documentation for the user to address
