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

Read the **Layer Boundaries** table in `.claude/config.md`. For each layer defined, verify that files in that layer's path pattern only import from allowed sources and flag any import that crosses into a forbidden layer.

If no config file exists, apply these generic defaults:
- **Domain/core layer**: no framework imports, no data layer imports
- **Data/infrastructure layer**: no UI imports, may import domain
- **UI/presentation layer**: no direct data layer imports — must go through an intermediary (services, stores, hooks, view models)

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

Read the **Convention Checks** table in `.claude/config.md` for project-specific rules. If no config file exists, apply these generic defaults:
- **Naming**: `PascalCase` classes/types, `camelCase` functions/variables, `kebab-case` files
- **Line length**: 100 characters max
- **Functions**: single purpose, aim for <20 lines
- **Logging**: uses project logger, never `console.log` in production code
- **Error handling**: async functions have proper error handling at system boundaries
- **Comments**: `/** */` for public API documentation, inline comments explain *why* not *what*

### Pattern compliance

Read the **Pattern Compliance** section in `.claude/config.md`. Check each changed file against the declared patterns.

If no config file exists, check these generic patterns:
- Views/components never call repositories, services, or data sources directly
- State management follows the project's declared pattern (check CLAUDE.md or package.json for clues)
- New dependencies follow the project's module registration / DI pattern
- Interfaces/abstractions are used at layer boundaries

---

## Step 4 — Code quality

### Complexity
- Flag methods longer than 20 lines
- Flag deeply nested logic (3+ levels)
- Flag methods with more than 3 parameters that could use a parameter object

### Duplication
- Check if new code duplicates existing utilities or shared modules
- Check if similar logic exists elsewhere that could be shared

### Error handling
- Async methods should have proper error handling
- Errors at system boundaries (database calls, API calls, external service calls) should be caught
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

- If yes: fix them on the feature branch, run `npm test` and `npm run typecheck && npm run lint`, commit the fixes
- If no: the review stands as documentation for the user to address
