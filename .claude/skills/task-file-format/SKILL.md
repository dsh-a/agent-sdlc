---
name: task-file-format
description: Output format for task files produced by generate-tasks — the Relevant Files block, the Tasks block with kind tags, and the agent-dispatch taxonomy. Loaded by generate-tasks; the orchestrator parses this format mechanically.
disable-model-invocation: true
---

# Task File Format

The `generate-tasks` agent decomposes a PRD into a task file at `agent_tasks/tasks-prd-[feature-name].md`. The orchestrator parses this file mechanically — section names, the bracketed `[kind: …]` tag, and the indented sub-task format are all load-bearing. Do not improvise the shape.

---

## Sections (in this exact order)

```markdown
## Relevant Files

### Source Files (modify)
- `src/path/to/File.cs` — Brief description of why this file is relevant

### Source Files (create)
- `src/path/to/NewFile.cs` — Brief description

### Test Files (create)
- `tests/path/to/FileTests.cs` — Tests for `File.cs`

### Notes
- Tests go in the project's test tree mirroring the source structure (per the **Test path glob** in `.claude/config.md` § Project Commands)
- Use the **Run all tests** / **Run specific test file** commands (§ Project Commands) to run tests

## Tasks

- [ ] 1.0 [kind: scaffold-entity] Parent Task Title
    - [ ] 1.1 Sub-task description
    - [ ] 1.2 Sub-task description
- [ ] 2.0 [kind: ui-story] Parent Task Title
    - [ ] 2.1 Sub-task description
```

---

## `kind:` taxonomy

Every parent task carries one `[kind: <name>]` tag. The orchestrator dispatches directly by tag — no prose inference. Pick the most specific kind that matches; if a parent task spans kinds, split it into two parent tasks.

| `kind` value | Dispatched to |
|---|---|
| `ui-story` | `ui-story` agent (UI screen or component) |
| `test` | `test` agent (test-only tasks) |
| `general-purpose` | `general-purpose` agent (multi-file fallback) |
| `scaffold` | `scaffold` agent (generic — picks pattern itself) |
| `scaffold-entity` | `scaffold` agent, entity/model pattern |
| `scaffold-facade` | `scaffold` agent, facade pattern |
| `scaffold-service` | `scaffold` agent, service pattern |
| `scaffold-use-case` | `scaffold` agent, use-case pattern |
| `scaffold-command` | `scaffold` agent, command pattern |
| `scaffold-strategy` | `scaffold` agent, strategy pattern |
| `scaffold-observer` | `scaffold` agent, observer pattern |
| `scaffold-interface` | `scaffold` agent, interface pattern |

---

## Parent task structure

- 4–6 parent tasks for typical features; 2–3 for smaller features.
- Each parent task should be **independently mergeable and testable**.
- Typical layering:
  - Data / infrastructure layer (model, repository, DI wiring)
  - Application / domain layer (use cases, facades, handlers)
  - Presentation layer (controller / view-model + view)
  - Tests
  - Integration / wiring cleanup (if needed)

---

## Sub-task structure

- Each sub-task is a single focused effort.
- Sub-tasks must logically follow from the parent.
- Cover implementation details implied by the PRD and AC.
- Include validation, error handling, and logging sub-tasks where relevant.
- Use two-space (or 4-space) indentation under the parent — the orchestrator's parser tolerates either; stay consistent within a file.

---

## Don'ts

- Don't omit the `[kind: ...]` tag on a parent task. The orchestrator falls back to prose inference, but that's a degraded path.
- Don't merge multiple kinds into one parent task. Split.
- Don't include sub-tasks at depth > 1 (no sub-sub-tasks).
- Don't describe files that already exist as "create" — use "modify".
