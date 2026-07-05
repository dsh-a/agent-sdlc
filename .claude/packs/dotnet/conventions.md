<!--
PACK REFERENCE FILE — the `dotnet` pack's conventions.
This is the source-of-truth copy for the default .NET pack. The ACTIVE conventions
agents load live in `.claude/skills/project-conventions/SKILL.md`; `/setup` copies this
file's body into that skill when the dotnet pack is selected. Keep the two in sync, or
treat this as the canonical version and re-run `/setup` after editing.
-->

# .NET Conventions (pack: dotnet)

This pack targets **.NET / C#**. The rules below are authoritative when this pack is
active. Project-specific overrides live in `.claude/config.md` § Pattern Compliance and
§ Layer Boundaries — read those first; what follows applies unless overridden.

> These are **placeholder defaults**. Fill in the bracketed/italic parts for your stack
> (ASP.NET Core API, Blazor, MAUI, worker service, etc.) via `/setup` or by editing.

---

## Layer boundaries

- **Presentation** (controllers / minimal-API endpoints / Blazor components / view models)
  → depends on application services. Never references infrastructure/data directly.
- **Application** (use cases, handlers, services) → depends on domain abstractions only.
- **Domain** (entities, value objects) → pure C#. No EF Core, no HTTP, no framework I/O.
- **Infrastructure / Data** (EF Core, repositories, external clients) → implements domain
  abstractions. The only layer that touches the database or external services.

_Map these to real paths in `.claude/config.md` § Layer Boundaries._

## Member order

Constants/statics → injected `readonly` deps → state fields → constructor(s) →
public methods → private methods.

## Naming

`PascalCase` types/methods/properties; `camelCase` locals/params; `_camelCase` private
fields; `IFoo` interfaces; `…Async` async methods; affirmative booleans.

## Logging

`ILogger<T>` via constructor. Never `Console.WriteLine` in production paths.

## Error handling

Error handling at system boundaries (DB, HTTP, external services). Follow the project's
result/exception strategy as stated in § Pattern Compliance.

## Entity / model construction

Assign every field on full construction; name only changed fields in `with` expressions;
cross-check against the type's member list before committing.
