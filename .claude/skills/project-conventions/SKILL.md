---
name: project-conventions
description: Canonical project conventions for this codebase — the single source of truth loaded by ui-story, scaffold, test, and review. Member order, naming, layer boundaries, logging, file locations, entity construction. Do not duplicate these rules in agent prompts. Project-specific overrides live in `.claude/config.md` § Pattern Compliance and § Layer Boundaries.
disable-model-invocation: true
---

# Project Conventions

> **This is the ACTIVE conventions skill.** Agents load it deterministically via their
> `skills:` frontmatter — it is the one place language/framework rules live. The body
> below is the **default .NET placeholder**: it states the *shape* of each rule but leaves
> the specifics for your team to fill in. Run `/setup` to populate it from a language pack
> (`.claude/packs/<lang>/conventions.md`), or edit it directly. See `.claude/packs/README.md`.
>
> **Active pack:** see `.claude/config.md` → **Active Pack** (default `dotnet`).

This codebase targets **.NET / C#**. The rules below are authoritative across agents.
Project-specific overrides live in `.claude/config.md` § Pattern Compliance and
§ Layer Boundaries — read those first; what follows applies unless overridden.

---

## Layer boundaries

> _Fill in your architecture. Example shape for a layered / Clean Architecture solution:_

- **Presentation** (controllers / endpoints / Blazor components / view models) depends on
  application services or use cases — never on infrastructure or data access directly.
- **Application** (use cases, handlers, services) depends on domain abstractions
  (interfaces) — never on concrete infrastructure.
- **Domain** (entities, value objects, domain services) is pure — no framework, no I/O,
  no EF Core, no HTTP. Depends on nothing outward.
- **Infrastructure / Data** (EF Core, repositories, external clients) implements domain
  abstractions. The only layer that references the database or external services.

Map these to your project structure in `.claude/config.md` § Layer Boundaries (path
patterns + allowed/forbidden imports). The `review` agent enforces what you put there.

---

## Member order (all types)

1. Constants and static fields
2. Injected dependencies (constructor parameters → readonly fields)
3. State fields (private, exposed via properties where needed)
4. Constructor(s)
5. Public methods
6. Private methods

---

## Naming defaults

- Files: one public type per file, file name matches the type (`OrderService.cs`).
- Types, methods, properties, constants: `PascalCase`.
- Locals and parameters: `camelCase`.
- Private fields: `_camelCase`.
- Interfaces: `IOrderRepository`. Async methods: `…Async` suffix.
- Booleans: affirmative — `IsLoading`, `HasError`, `CanSubmit`.

---

## Logging

- Use the project logger abstraction (e.g. `ILogger<T>` injected via constructor).
  Never `Console.WriteLine` in production code.
- Owners that emit logs: services, handlers, repositories, infrastructure clients.

---

## Error handling

- `async` methods have proper error handling at **system boundaries** (database, HTTP,
  external services). Internal trusted-layer code does not need excessive defensive checks.
- Prefer the project's established result/exception strategy — state it in
  `.claude/config.md` § Pattern Compliance so agents follow it consistently.

---

## Entity / model construction

- When constructing a domain object with its full constructor, assign **every** field
  explicitly — do not lean on defaults or silently omit nullable fields.
- When copying with a `with` expression (records) or a builder, name only the fields that
  change.
- Before committing, cross-check the construction site against the type's full member list.
  A missing or defaulted field is a common silent data-loss bug.

---

## Testing conventions (cross-reference)

Test patterns live in the `test` skill / agent and the active pack's `test-patterns.md`.
Two cross-cutting rules anchored here:

- Test path mirrors source path per your project's test layout (configure the test glob in
  `.claude/config.md` § Project Commands). Example: `src/Orders/OrderService.cs` →
  `tests/Orders.Tests/OrderServiceTests.cs`.
- Reuse shared test fixtures/builders rather than re-instantiating dependencies per test.

---

## What this skill does NOT cover

- Per-pattern scaffolding detail (use the `scaffold` skill and `.claude/agents/scaffold/*.md`).
- Component/UI test patterns (use the `test` skill / agent and the pack's `test-patterns.md`).
- Architecture-review rubric (use the `review` agent's checklist).
- Project-specific overrides (live in `.claude/config.md` § Pattern Compliance).
