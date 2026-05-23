# Scaffold

You are scaffolding a new component. This skill is an **index** — it routes you to the right pattern file. Per-type detail lives in `.claude/agents/scaffold/` (project-specific) and `.claude/agents/scaffold/templates/` (generic defaults). Do not duplicate that detail here; load and follow it.

The component to scaffold: **$ARGUMENTS**

---

## Step 1 — Determine scaffold type

Inspect `$ARGUMENTS`. If ambiguous, ask the user.

| Type | Trigger | Pattern file |
|---|---|---|
| Syncable entity | "entity", "model", or a noun that implies a data object | `scaffold/syncable-entity.md` |
| Local-only entity | "local entity", "local model", or explicitly no sync | `scaffold/local-entity.md` |
| Use case | "use case" or a verb phrase | `scaffold/templates/use-case.md` |
| Facade | "facade" | `scaffold/templates/facade.md` |
| Service | "service" | `scaffold/templates/service.md` |
| ViewModel + View | "view", "screen", "page" | `scaffold/view-model-view.md` |
| Command / Strategy / Observer / Interface | matching keyword | `scaffold/templates/<pattern>.md` |

---

## Step 2 — Check for conflicts

Search `lib/` for existing files with the same name. If found, stop and ask the user whether to extend or rename.

---

## Step 3 — Load the pattern

Priority order:
1. **Project-specific** (`Type: project-specific`) — `.claude/agents/scaffold/<name>.md`. If present, follow it verbatim — it reflects this project's actual conventions.
2. **Default template** (`Type: template`) — `.claude/agents/scaffold/templates/<name>.md`. Use as a starting point, adapt to the codebase.
3. **No pattern file** — explore `lib/` for 1–2 existing examples of the same type, extract conventions.

Also read `.claude/config.md` § Architecture Review Rules for layer boundaries.

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

Follow the loaded pattern file end-to-end. It owns the per-type detail (file locations, dependencies, DI wiring, codegen, Supabase considerations). This skill does not duplicate that content.

---

## Step 5 — Verify

- Run `flutter analyze`
- Confirm the project compiles cleanly
- List remaining steps the user needs (tests, additional wiring, Supabase migrations if deferred)
