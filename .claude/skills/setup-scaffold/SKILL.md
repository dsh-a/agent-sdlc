# Setup Scaffold — Discover and Codify Project Patterns

Scan the codebase for recurring architectural patterns and generate project-specific scaffold pattern files. This eliminates repeated codebase exploration by the scaffold agent.

**Mode**: $ARGUMENTS

- Empty or `scan`: Full scan — discover all patterns, create files for new ones, skip existing project-specific patterns
- `update`: Incremental — look for new or changed patterns since the last scan, update existing pattern files if the codebase has diverged

This skill can be invoked directly by the user (`/setup-scaffold`) or autonomously by the scaffold agent or cycle pre-flight when no project-specific patterns exist. When running autonomously (spawned by an agent), skip user confirmation steps — use best judgment and create all discovered patterns.

---

## Step 1 — Read the pattern standard

Read `.claude/skills/scaffold/pattern-template.md` for the required structure of pattern files.

## Step 2 — Inventory existing pattern files

Read all files in `.claude/agents/scaffold/`:
- Files with `Type: template` are GoF templates shipped with agent-sdlc
- Files with `Type: project-specific` are previously discovered patterns
- Note which GoF templates have been replaced by project-specific files

In `update` mode: also read the project-specific files to compare against current codebase state.

## Step 3 — Scan the codebase

Search the project's source directory for recurring patterns. For each pattern category below, find 2+ existing instances:

### Application patterns
- **Use cases / interactors**: Classes with a single `execute()` or similarly named public method that orchestrate a business operation
- **Services**: Classes wrapping infrastructure concerns (external APIs, auth, email, storage, caching)
- **Facades**: Classes aggregating multiple repositories or services for a feature area
- **Repositories**: Classes abstracting data access behind interfaces

### Design patterns
- **Interfaces / contracts**: Layer boundary abstractions (repository interfaces, service contracts, port definitions)
- **Commands**: Request objects paired with handlers (CQRS, task queues, action dispatchers)
- **Observers / events**: Domain events, event handlers, pub/sub mechanisms
- **Strategies**: Interchangeable algorithms behind a common interface

### Framework-specific patterns
- **Controllers / handlers**: Request-handling classes (Express routes, NestJS controllers, tRPC procedures, etc.)
- **Middleware**: Request/response interceptors
- **UI components**: Reusable UI patterns specific to this project's framework
- **State management**: Stores, slices, view models, or hooks with a recurring structure

For each discovered pattern, extract:
1. **Common structure**: class shape, constructor dependencies, method signatures
2. **File location convention**: where these files live in the directory tree
3. **Naming convention**: how files and classes are named
4. **Wiring pattern**: how they're registered (DI, module imports, route tables)
5. **Test pattern**: where and how tests are structured for this type

## Step 4 — Present findings

Present a summary to the user:

```
Discovered patterns:
  - [pattern name] — [N] instances found (e.g., src/services/auth.service.ts, src/services/email.service.ts)
    → Will create: .claude/agents/scaffold/[name].md
    → Replaces GoF template: [template name] (or "new — no GoF template")

Already codified:
  - [pattern name] — project-specific file exists, [matches|diverged from] current codebase

No instances found:
  - [GoF template names with no matching project patterns]
```

If running interactively (user invoked `/setup-scaffold`): ask **"Create pattern files for the discovered patterns? I'll skip already-codified ones."**

If running autonomously (spawned by an agent): proceed directly — create all discovered patterns without asking.

In `update` mode, also note: which existing pattern files have diverged from the codebase (structure or conventions changed) and update them (or offer to, if interactive).

## Step 5 — Generate pattern files

For each approved pattern:

1. Read the 2+ example files identified in Step 3
2. Extract the common template following the standard in `pattern-template.md`
3. Write to `.claude/agents/scaffold/<pattern-name>.md`
4. If this pattern matches a GoF template, set `Replaces: <template-name>` in the header

Do NOT delete GoF template files. Project-specific files take priority via the `Replaces` header.

## Step 6 — Summary

Present what was created:

```
Pattern files created:
  - .claude/agents/scaffold/<name>.md (replaces: <GoF template>)
  - .claude/agents/scaffold/<name>.md (new pattern)

GoF templates still active (no project equivalent found):
  - command.md, observer.md, ...

Next steps:
  - The scaffold agent will now use these patterns automatically
  - Run `/setup-scaffold update` after significant codebase changes to keep patterns current
  - Edit any pattern file directly to refine the template
```
