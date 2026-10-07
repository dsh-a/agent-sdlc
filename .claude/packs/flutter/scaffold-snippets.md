# Flutter Scaffold Snippets (pack: flutter)

> Dart/Flutter idioms the `scaffold` agent uses when generating new components.
> Pattern **shapes** are language-neutral in `.claude/agents/scaffold/` (routed via its
> `INDEX.md`); this file routes to the idiom. Shapes describe structure — snippets describe syntax.

**This file is an index.** Find the row for the shape you were routed to and open that one
snippet. Do not read the whole `snippets/` directory.

## Coverage

| Shape | Snippet | Source |
|---|---|---|
| `interface.md` | [snippets/interface.md](snippets/interface.md) | extracted |
| `use-case.md` | [snippets/use-case.md](snippets/use-case.md) | extracted |
| `service.md` | [snippets/service.md](snippets/service.md) | extracted |
| `facade.md` | [snippets/facade.md](snippets/facade.md) | extracted |
| `adapter.md` | [snippets/adapter.md](snippets/adapter.md) | extracted |
| `abstract-factory.md` | [snippets/abstract-factory.md](snippets/abstract-factory.md) | illustrative |
| `builder.md` | [snippets/builder.md](snippets/builder.md) | illustrative |
| `factory-method.md` | [snippets/factory-method.md](snippets/factory-method.md) | illustrative |
| `prototype.md` | [snippets/prototype.md](snippets/prototype.md) | illustrative |
| `singleton.md` | [snippets/singleton.md](snippets/singleton.md) | illustrative |
| `bridge.md` | [snippets/bridge.md](snippets/bridge.md) | illustrative |
| `composite.md` | [snippets/composite.md](snippets/composite.md) | illustrative |
| `decorator.md` | [snippets/decorator.md](snippets/decorator.md) | illustrative |
| `flyweight.md` | [snippets/flyweight.md](snippets/flyweight.md) | illustrative |
| `proxy.md` | [snippets/proxy.md](snippets/proxy.md) | illustrative |
| `chain-of-responsibility.md` | [snippets/chain-of-responsibility.md](snippets/chain-of-responsibility.md) | illustrative |
| `command.md` | [snippets/command.md](snippets/command.md) | illustrative |
| `interpreter.md` | [snippets/interpreter.md](snippets/interpreter.md) | illustrative |
| `iterator.md` | [snippets/iterator.md](snippets/iterator.md) | illustrative |
| `mediator.md` | [snippets/mediator.md](snippets/mediator.md) | illustrative |
| `memento.md` | [snippets/memento.md](snippets/memento.md) | illustrative |
| `observer.md` | [snippets/observer.md](snippets/observer.md) | illustrative |
| `state.md` | [snippets/state.md](snippets/state.md) | illustrative |
| `strategy.md` | [snippets/strategy.md](snippets/strategy.md) | illustrative |
| `template-method.md` | [snippets/template-method.md](snippets/template-method.md) | illustrative |
| `visitor.md` | [snippets/visitor.md](snippets/visitor.md) | illustrative |

### Cross-cutting (no pattern file)

| Topic | Snippet |
|---|---|
| ViewModel (`ui-story` agent owns presentation) | [snippets/viewmodel.md](snippets/viewmodel.md) |
| DI registration — every shape's § Wiring points here | [snippets/di-registration.md](snippets/di-registration.md) |

## Reading the Source column

- **extracted** — taken from this project's existing code. It is house convention; follow it.
- **illustrative** — idiomatic Dart written as a reference, with no project exemplar behind it.
  Follow the shape and the Dart idiom, but defer to any existing code in the feature you are
  touching, and to `conventions.md`, where they disagree.

## If there is no row for your shape

Follow the shape file's `## Template` structure and take the idiom from `conventions.md` in this
pack — naming, member order, logging, error handling, and imports are specified there. Do **not**
invent a house style, and do not treat a missing snippet as permission to skip the pattern's
conventions. Note the gap in your report so `/setup-scaffold` can capture it.

## Where Dart's answer differs from the textbook

Several shapes have an idiomatic Dart form that is not a transliteration of the classic pattern.
The snippets lead with the Dart answer; these are the ones most often got wrong:

| Shape | Dart's answer |
|---|---|
| `flyweight` | `const` constructors — the compiler canonicalizes identical const instances |
| `prototype` | `copyWith` (hand-written or `freezed`), not a `clone()` method |
| `iterator` | `sync*` generators returning `Iterable`, never a hand-rolled cursor |
| `visitor` | `sealed` + exhaustive `switch`; double dispatch only for open hierarchies |
| `state`, `interpreter` | `sealed` + pattern matching |
| `observer` | `Stream` / `ChangeNotifier`, never a hand-rolled listener list |
| `singleton` | A `Provider` single-instance registration |
| `builder` | Named/optional constructor arguments answer most cases |
| `factory-method` | **Not** Dart's `factory` constructor — that returns its own type |
| `template-method` | Dart has no `final` methods; the guarantee is convention, not compiler |

> Codegen: if the component needs generated code (Drift, json_serializable, freezed),
> run the **Code generation** command in `.omp/agent-config.md` § Project Commands
> (`flutter pub run build_runner build --delete-conflicting-outputs`) — never hand-edit
> `.g.dart` files.
