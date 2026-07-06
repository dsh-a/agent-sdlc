# Scaffold

You are scaffolding a new component. This skill is an **index** — it routes you to the right pattern file. Per-type detail lives in `.claude/agents/scaffold/` (language-neutral pattern shapes + any project-specific patterns); language idioms come from the active pack's `scaffold-snippets.md`. Do not duplicate that detail here; load and follow it.

The component to scaffold: **$ARGUMENTS**

---

## Step 1 — Determine scaffold type

Inspect `$ARGUMENTS`. If ambiguous, ask the user.

| Type | Trigger | Pattern file |
|---|---|---|
| Entity / model | "entity", "model", or a noun that implies a data object | `scaffold/interface.md` (+ pack snippets) |
| Use case | "use case" or a verb phrase | `scaffold/use-case.md` |
| Facade | "facade" | `scaffold/facade.md` |
| Service | "service" | `scaffold/service.md` |
| Command | "command", "handler" | `scaffold/command.md` |
| Strategy / Observer / Interface | matching keyword | `scaffold/<pattern>.md` |
| Presentation (view-model + view) | "view", "screen", "page", "component" | hand off to the `ui-story` agent |

---

## Step 2 — Check for conflicts

Search the source tree for existing files/types with the same name. If found, stop and ask the user whether to extend or rename.

---

## Step 3 — Load the pattern

Priority order:
1. **Project-specific** (`Type: project-specific`) — `.claude/agents/scaffold/<name>.md`. If present, follow it verbatim — it reflects this project's actual conventions.
2. **Default pattern** — `.claude/agents/scaffold/<name>.md` (language-neutral shape) + the active pack's `scaffold-snippets.md` for the idiom. Use as a starting point, adapt to the codebase.
3. **No pattern file** — explore the source tree for 1–2 existing examples of the same type, extract conventions.

Also read `.omp/agent-config.md` § Architecture Review Rules for layer boundaries.

**Bootstrap.** If no project-specific pattern files exist at all, autonomously spawn a setup-scaffold pass before proceeding:

```
Agent(subagent_type: "general-purpose", model: "sonnet",
      prompt: "Run the /setup-scaffold skill in scan mode. Read
               .claude/skills/setup-scaffold/SKILL.md and follow its steps.
               Do not ask the user questions. Report what was created.")
```

Wait for it to complete, then re-read `.claude/agents/scaffold/` and continue.

---

## Step 4 — Execute the pattern

Follow the loaded pattern file end-to-end. It owns the per-type detail (file locations, dependencies, DI wiring, codegen, data-schema considerations). This skill does not duplicate that content.

---

## Step 5 — Verify

- Run the **Analyze / lint** command (`.omp/agent-config.md` § Project Commands)
- Confirm the project compiles cleanly
- List remaining steps the user needs (tests, additional wiring, schema migrations if deferred)
