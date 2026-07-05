---
disable-model-invocation: true
---

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

Read `.claude/agents/scaffold/`:
- Files with `Type: project-specific` are previously discovered patterns for this project.
- The remaining files are the language-neutral default pattern shapes shipped with agent-sdlc (paired with the active pack's `scaffold-snippets.md` for the idiom).

Note which default shapes have been superseded by a project-specific file (matched via the `Replaces` header).

In `update` mode: also read the project-specific files to compare against current codebase state.

## Step 3 — Scan the codebase

Search the source tree for recurring patterns. For each pattern category below, find 2+ existing instances (the examples are language-neutral; map them to the active pack's idioms):

### Domain / application patterns
- **Use cases / interactors / handlers**: Classes with a single public entry method that orchestrate a business operation
- **Facades**: Classes aggregating multiple repositories or services for a feature area
- **Models / entities**: Data classes, often with a copy/`with` idiom and serialization

### Data / infrastructure patterns
- **Repositories**: Classes implementing a repository interface, abstracting data access
- **Adapters / mappers**: Classes converting between domain models and data-layer types
- **Services**: Classes wrapping infrastructure concerns (auth, connectivity, platform/external APIs)

### Design patterns
- **Interfaces / contracts**: abstractions at layer boundaries (repository interfaces, service contracts)
- **Commands**: Request objects paired with handlers or dispatchers
- **Observers / events**: Domain events, event handlers, or pub/sub mechanisms
- **Strategies**: Interchangeable algorithms behind a common abstraction

### Presentation patterns
- **Controllers / view-models / presenters**: Classes exposing state and actions to the UI
- **Views / pages / components**: UI classes consuming a presentation object
- **Reusable components**: Shared UI components with a recurring structure

For each discovered pattern, extract:
1. **Common structure**: class shape, constructor dependencies, method signatures
2. **File location convention**: where these files live in the source tree
3. **Naming convention**: how files and types are named
4. **Wiring pattern**: how they're registered (DI container, factory, etc.)
5. **Test pattern**: where and how tests are structured for this type

## Step 4 — Present findings

Present a summary to the user:

```
Discovered patterns:
  - [pattern name] — [N] instances found (e.g., src/Data/Repositories/UserRepository.cs)
    → Will create: .claude/agents/scaffold/[name].md
    → Replaces default template: [template name] (or "new — no default template")

Already codified:
  - [pattern name] — project-specific file exists, [matches|diverged from] current codebase

No instances found:
  - [default template names with no matching project patterns]
```

If running interactively (user invoked `/setup-scaffold`): ask **"Create pattern files for the discovered patterns? I'll skip already-codified ones."**

If running autonomously (spawned by an agent): proceed directly — create all discovered patterns without asking.

In `update` mode, also note: which existing pattern files have diverged from the codebase (structure or conventions changed) and update them (or offer to, if interactive).

## Step 5 — Generate pattern files

For each approved pattern:

1. Read the 2+ example files identified in Step 3
2. Extract the common template following the standard in `pattern-template.md`
3. Write to `.claude/agents/scaffold/<pattern-name>.md`
4. If this pattern matches a default shape, set `Replaces: <shape-name>` in the header

Treat the shipped language-neutral pattern shapes as defaults — a project-specific file with a `Replaces` header takes priority over the shape it names.

## Step 6 — Summary

Present what was created:

```
Pattern files created:
  - .claude/agents/scaffold/<name>.md (replaces: <default shape>)
  - .claude/agents/scaffold/<name>.md (new pattern)

Default shapes still active (no project equivalent found):
  - use-case.md, facade.md, ...

Next steps:
  - The scaffold agent will now use these patterns automatically
  - Run `/setup-scaffold update` after significant codebase changes to keep patterns current
  - Edit any pattern file directly to refine the template
```
