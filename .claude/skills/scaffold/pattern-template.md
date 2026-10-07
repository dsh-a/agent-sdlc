# Scaffold Pattern File Standard

This document defines the standard structure for scaffold pattern files in `.claude/agents/scaffold/`. Both `/setup-scaffold` (when generating patterns) and the `scaffold` agent (when reading patterns) reference this standard.

The 26 shipped pattern files all conform to it — read any one of them as a worked example (`bridge.md` is the reference implementation).

---

## File naming

- Default / language-neutral shapes: `<pattern-name>.md` (e.g., `use-case.md`, `service.md`)
- Project-specific patterns: `<descriptive-name>.md` (e.g., `efcore-repository.md`, `http-client-service.md`)

## Routing

`.claude/agents/scaffold/INDEX.md` is the routing table. It exists so an agent can pick a pattern by reading **one** file instead of opening candidates to find out what they cover. Every new pattern file must be added to it — see *Rules for /setup-scaffold* below.

## Required structure

Nine `##` sections, in this exact order. No section is optional; write "None." rather than omitting one. The only permitted `###` is `Structure` inside `## Participants`.

Sections are ordered by **consumption cost**: routing metadata is greppable without opening the body, action sections come before reference material, and the theory sinks to the tail. An agent reading top-down can stop as soon as it has what it needs.

````markdown
# <Pattern Name>

> **Type**: template | project-specific
> **Category**: creational | structural | behavioral | architecture
> **Triggers**: <comma-separated keywords an agent's task text might contain>
> **Aliases**: <other names for this pattern — omit the line if none>
> **Related**: <sibling pattern filenames, no extension>
> **Replaces**: <default shape this supersedes — project-specific files only>

## Intent

<One or two sentences. What the pattern does, stated as a capability.>

## When to use

<A lead sentence tying the pattern to a scaffold task, then applicability bullets.>

**Not when:**
- <Each bullet routes to a sibling pattern file, or to a simpler non-pattern answer.>
- <This section is what makes the corpus navigable — never omit it.>

## Participants

| Role | Responsibility | Path |
|---|---|---|
| <role> | <what it is responsible for> | `<layer>/<feature>/<Name>.<ext>` |
| Test — <aspect> | <what it verifies> | `<test tree>/<feature>/<Name>Tests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
<ASCII diagram — must render in a terminal. No images, no external assets.>
```

**Collaborations:** <one line on how the participants interact at run-time.>

## Dependencies

<What each participant depends on, and which layer it sits in.>

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Language-neutral shape comments, one block per participant.
// NEVER concrete code in a specific language — that belongs in the pack.
```

A pack is not required to carry a snippet for every shape. Each pack's `scaffold-snippets.md` is
an index: it routes a shape to one file under `snippets/<pattern>.md` (named to match this file)
and declares the fallback for a miss (idiom from the pack's `conventions.md`, gap reported).
Write this section so it stands on its own when no snippet exists.

## Wiring

<How to register this — DI container, factory, composition root. Name the lifetime.>

## Conventions

- <Rules that keep the pattern correct, including its characteristic failure mode.>

## Tests

- <What to test, including the negative and boundary cases that matter for this pattern.>

## Consequences

1. **<Benefit>.** <Why it follows.>
2. **Cost: <drawback>.** <Always end with at least one cost, so the section supports a decision rather than selling the pattern.>
````

## Rules for /setup-scaffold when creating pattern files

1. **Discover by example**: Find 2+ existing instances of the pattern in the codebase. Read them to extract the common structure.
2. **Extract, don't invent**: The template should reflect what the project actually does, not what a textbook says. If the project uses a non-standard approach, capture that.
3. **Include real paths**: Use the project's actual directory structure, not generic placeholders.
4. **Mark as project-specific**: Set `Type: project-specific` and `Replaces: <shape>` if it supersedes a default shape.
5. **Preserve the default shape**: Don't delete default shapes — just mark the project-specific file as replacing it. The scaffold agent checks for project-specific files first.
6. **Fill all nine sections**: A generated file with placeholder or missing sections breaks the uniformity agents rely on. `Intent` and `Consequences` are derivable from the observed code — state what the project gains and what it pays.
7. **Register in INDEX.md — only if it is a regular file**: add a row to `.claude/agents/scaffold/INDEX.md` § Project-specific patterns with the pattern name, what it replaces, and its trigger keywords. **If `INDEX.md` is a symlink into agent-sdlc, skip this step** — writing to it would leak this project's patterns into every project sharing the framework. The scaffold agent falls back to the directory listing, which is authoritative either way.

## Rules for the scaffold agent when reading pattern files

1. **Route via INDEX.md** — read it first, match on Triggers, check Disambiguation, then open exactly one pattern file.
2. **Priority order**: Project-specific pattern > default shape (+ pack snippets) > codebase exploration
3. If a project-specific file exists with `Replaces: <shape>`, use it instead of the default shape
4. If no pattern file matches, explore the codebase for existing examples before creating the component
5. Honour the **Not when** section — if it routes you elsewhere, follow it rather than forcing the pattern you first picked
