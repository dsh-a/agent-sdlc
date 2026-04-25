# Scaffold Pattern File Standard

This document defines the standard structure for scaffold pattern files in `.claude/agents/scaffold/`. Both `/setup-scaffold` (when generating patterns) and the `scaffold` agent (when reading patterns) reference this standard.

---

## File naming

- Default / generic templates: `<pattern-name>.md` (e.g., `use-case.md`, `service.md`)
- Project-specific patterns: `<descriptive-name>.md` (e.g., `drift-repository.md`, `supabase-service.md`)

## Required sections

Every pattern file must include these sections:

```markdown
# <Pattern Name>

> **Type**: template | project-specific
> **Replaces**: <default template name, if this is a project-specific replacement>

## When to use

<1-3 sentences describing when the scaffold agent should use this pattern>

## File locations

| File | Path |
|---|---|
| <component> | <path pattern, e.g., `lib/domain/use_cases/<name>_use_case.dart`> |

## Dependencies

<What this component typically depends on (injected via constructor, imported, etc.)>

## Template

\`\`\`dart
<Complete, copy-paste-ready Dart template with placeholders like <Name>, <Entity>, etc.>
\`\`\`

## Wiring

<How to register this component — Provider, get_it, Riverpod, manual factory, etc.>

## Conventions

<Project-specific conventions observed in existing code — naming, error handling, logging, etc.>

## Tests

<What tests to write and where — reference the /test skill conventions>
```

## Rules for /setup-scaffold when creating pattern files

1. **Discover by example**: Find 2+ existing instances of the pattern in the codebase. Read them to extract the common structure.
2. **Extract, don't invent**: The template should reflect what the project actually does, not what a textbook says. If the project uses a non-standard approach, capture that.
3. **Include real paths**: Use the project's actual directory structure, not generic placeholders.
4. **Mark as project-specific**: Set `Type: project-specific` and `Replaces: <template>` if it supersedes a default template.
5. **Preserve the default template**: Don't delete default templates — just mark the project-specific file as replacing it. The scaffold agent checks for project-specific files first.

## Rules for the scaffold agent when reading pattern files

1. **Priority order**: Project-specific pattern > default template > codebase exploration
2. If a project-specific file exists with `Replaces: <template>`, use it instead of the default template
3. If no pattern file matches, explore the codebase for existing examples before creating the component
