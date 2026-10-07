---
name: scaffold
description: Scaffold new components following established project patterns — entities/models, use cases, facades, services, or presentation (view-model + view) pairs. Routes to the right pattern file and includes DI wiring and codegen.
disable-model-invocation: true
---
# Scaffold

You are scaffolding a new component. This skill routes you to the right pattern file via `.claude/agents/scaffold/INDEX.md`. Per-type detail lives in `.claude/agents/scaffold/` (language-neutral pattern shapes + any project-specific patterns); language idioms come from the active pack's `scaffold-snippets.md`. Do not duplicate that detail here; load and follow it.

The component to scaffold: **$ARGUMENTS**

---

## Step 1 — Determine scaffold type

Read `.claude/agents/scaffold/INDEX.md` — the routing table for every available pattern. Match `$ARGUMENTS` against its **Triggers** column, then check its **Disambiguation** table before committing to a choice. Open exactly **one** pattern file; do not glob the directory to find out what is available.

Two routes INDEX.md does not cover:

| Type | Trigger | Route |
|---|---|---|
| Presentation (view-model + view) | "view", "screen", "page", "component" | hand off to the `ui-story` agent |
| Entity / model | "entity", "model", or a noun that implies a data object | `scaffold/interface.md` (+ pack snippets) |

INDEX.md also flags patterns with a **cheaper default** in this stack (singleton, iterator, builder, prototype, flyweight, interpreter, visitor). Apply the cheaper default unless the pattern file's *When to use* criteria are genuinely met.

**A deployed project may carry only a subset.** If `INDEX.md` is absent, list `.claude/agents/scaffold/` and match on filename and trigger keywords instead. If INDEX.md names a pattern file that is not present here, that shape simply was not linked — fall through to codebase exploration for it rather than inventing its contents. Report either gap; do not stop.

If `$ARGUMENTS` is ambiguous, or nothing matches, ask the user rather than forcing a pattern onto the task.

---

## Step 2 — Check for conflicts

Search the source tree for existing files/types with the same name. If found, stop and ask the user whether to extend or rename.

---

## Step 3 — Load the pattern

Priority order:
1. **Project-specific** — any real file in `.claude/agents/scaffold/` that is not a shipped default, whether or not it carries `Type: project-specific` (projects wired before that convention have unmarked files). If present, follow it verbatim — it reflects this project's actual conventions and supersedes any default it names in a `Replaces` line.
2. **Default pattern** — the file INDEX.md routed you to (language-neutral shape) + the active pack's idiom. `scaffold-snippets.md` is an index — match your shape in its § Coverage table and open that one snippet. Use as a starting point, adapt to the codebase; a snippet marked *illustrative* is reference only, not house convention. If there is no snippet for that shape, follow the index's fallback — idiom from the pack's `conventions.md`, no invented house style, and report the gap.
3. **No pattern file** — explore the source tree for 1–2 existing examples of the same type, extract conventions.

Also read `.omp/agent-config.md` § Architecture Review Rules for layer boundaries.

**Bootstrap.** If no project-specific pattern files exist at all, autonomously spawn a setup-scaffold pass before proceeding:

```
spawn agent: explore
    Run the /setup-scaffold skill in scan mode. Read
    .claude/skills/setup-scaffold/SKILL.md and follow its steps.
    Do not ask the user questions. Report what was created.
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
