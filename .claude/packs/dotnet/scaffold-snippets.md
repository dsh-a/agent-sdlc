# .NET Scaffold Snippets (pack: dotnet)

> C# idioms the `scaffold` agent uses when generating new components.
> Pattern **shapes** are language-neutral in `.claude/agents/scaffold/` (routed via its
> `INDEX.md`); this file routes to the idiom. Shapes describe structure — snippets describe syntax.

**This file is an index.** Find the row for the shape you were routed to and open that one
snippet. Do not read the whole `snippets/` directory.

> **Status.** This pack ships as an alternate template and is largely unwritten. Most rows below
> are gaps, not omissions to work around — see *If there is no snippet for your shape*. The
> `flutter` pack is the worked reference for what a complete pack looks like.

## Coverage

| Shape | Snippet | Source |
|---|---|---|
| `interface.md` | [snippets/interface.md](snippets/interface.md) | extracted from the shipped template |
| `use-case.md` | [snippets/use-case.md](snippets/use-case.md) | extracted from the shipped template |
| `service.md` | [snippets/service.md](snippets/service.md) | extracted from the shipped template |
| `facade.md` | — not yet written | — |
| `adapter.md` | — not yet written | — |
| `abstract-factory.md` | — not yet written | — |
| `builder.md` | — not yet written | — |
| `factory-method.md` | — not yet written | — |
| `prototype.md` | — not yet written | — |
| `singleton.md` | — not yet written | — |
| `bridge.md` | — not yet written | — |
| `composite.md` | — not yet written | — |
| `decorator.md` | — not yet written | — |
| `flyweight.md` | — not yet written | — |
| `proxy.md` | — not yet written | — |
| `chain-of-responsibility.md` | — not yet written | — |
| `command.md` | — not yet written | — |
| `interpreter.md` | — not yet written | — |
| `iterator.md` | — not yet written | — |
| `mediator.md` | — not yet written | — |
| `memento.md` | — not yet written | — |
| `observer.md` | — not yet written | — |
| `state.md` | — not yet written | — |
| `strategy.md` | — not yet written | — |
| `template-method.md` | — not yet written | — |
| `visitor.md` | — not yet written | — |

### Cross-cutting (no pattern file)

| Topic | Snippet |
|---|---|
| DI registration — every shape's § Wiring points here | [snippets/di-registration.md](snippets/di-registration.md) |

## If there is no snippet for your shape

Follow the shape file's `## Template` structure and take the idiom from `conventions.md` in this
pack — naming, member order, logging, error handling, and imports are specified there. Do **not**
invent a house style, and do not treat a missing snippet as permission to skip the pattern's
conventions. Note the gap in your report so `/setup-scaffold` can capture it as a project-specific
pattern file rather than leaving the next agent to improvise the same shape.
