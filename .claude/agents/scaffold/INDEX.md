# Scaffold Pattern Index

Routing table for `.claude/agents/scaffold/`. **Read this file, pick one row, open that one pattern file.** Do not glob the directory or read pattern files to find out what they cover — every pattern file follows the same 9-section structure (`.claude/skills/scaffold/pattern-template.md`), so the answer to "which one" is here and nowhere else.

Every pattern file carries greppable metadata, so a keyword not listed below can be found with:
`grep -l '<keyword>' .claude/agents/scaffold/*.md`

---

## Architecture shapes

Reach for these first — most scaffold tasks in this pipeline are one of these three.

| Pattern | Use when | Triggers |
|---|---|---|
| [use-case](use-case.md) | One business operation with validation and orchestration | use case, interactor, business operation, verb phrase, application service, single action |
| [service](service.md) | Wrapping an infrastructure concern behind a domain contract | service, infrastructure wrapper, external API client, platform feature, email storage cache auth |
| [interface](interface.md) | A contract at a layer boundary; dependency inversion | interface, contract, abstraction boundary, repository interface, service contract, port |

## Creational — how objects get made

| Pattern | Use when | Triggers |
|---|---|---|
| [abstract-factory](abstract-factory.md) | A whole **family** of products must be swapped as a set | abstract factory, kit, product family, platform-specific object set |
| [builder](builder.md) | Multi-step assembly producing different representations | builder, fluent construction, step-by-step assembly, telescoping constructor |
| [factory-method](factory-method.md) | A subclass decides which single product to instantiate | factory method, virtual constructor, defer instantiation |
| [prototype](prototype.md) | New objects are copies of a configured instance | prototype, clone, copy existing instance, copyWith, deep copy |
| [singleton](singleton.md) | Exactly one instance — **prefer a DI single-instance lifetime** | singleton, single instance, global access point |

## Structural — how objects are composed

| Pattern | Use when | Triggers |
|---|---|---|
| [adapter](adapter.md) | Convert an existing incompatible interface to the one you need | adapter, wrapper, incompatible interface, conform third-party API, legacy |
| [bridge](bridge.md) | Abstraction and implementation must vary on separate axes | bridge, handle, body, decouple abstraction, swap implementation at runtime |
| [composite](composite.md) | A tree where leaf and container are treated uniformly | composite, part-whole hierarchy, tree structure, recursive composition |
| [decorator](decorator.md) | Add behaviour around an operation, same interface, stackable | decorator, wrapper, add behaviour dynamically, caching/logging/retry wrapper |
| [facade](facade.md) | One cohesive API over several subsystem parts | facade, unified interface, simplify subsystem, aggregate repositories |
| [flyweight](flyweight.md) | Share instances under measured memory pressure | flyweight, shared instances, intrinsic extrinsic state, object explosion |
| [proxy](proxy.md) | Control access — lazy, guarded, remote, or counted | proxy, surrogate, placeholder, lazy loading, access control, remote stub |

## Behavioral — how objects interact

| Pattern | Use when | Triggers |
|---|---|---|
| [chain-of-responsibility](chain-of-responsibility.md) | Pass a request along until one handler takes it | chain of responsibility, handler chain, pipeline, middleware, escalation |
| [command](command.md) | A request becomes an object — queue, log, retry, undo | command, action, transaction, handler, CQRS, undo redo, dispatcher |
| [interpreter](interpreter.md) | Evaluate sentences of a small grammar as an expression tree | interpreter, grammar, expression tree, DSL, rule engine, query language |
| [iterator](iterator.md) | Sequential access without exposing representation | iterator, cursor, sequential access, custom traversal |
| [mediator](mediator.md) | Peers coordinate through one object instead of each other | mediator, coordinator, decouple many-to-many, colleague objects |
| [memento](memento.md) | Snapshot and restore state without breaking encapsulation | memento, snapshot, undo, rollback, checkpoint, save restore state |
| [observer](observer.md) | One change, many unknown reactors | observer, publish subscribe, pub/sub, domain event, listener, event bus |
| [state](state.md) | Behaviour follows a lifecycle the object moves through | state, state machine, status transitions, workflow states |
| [strategy](strategy.md) | Interchangeable algorithms selected at run-time | strategy, policy, interchangeable algorithm, pluggable rule, export format |
| [template-method](template-method.md) | Fixed step order, subclasses fill in the steps | template method, algorithm skeleton, hook method, invariant steps |
| [visitor](visitor.md) | New operations over a stable structure, via double dispatch | visitor, double dispatch, operation over object structure, traverse and act |

---

## Disambiguation

Confusable pairs, resolved. Each pattern file's **Not when** section carries the full reasoning.

| If you are about to pick… | …but the truth is | Then use |
|---|---|---|
| decorator | you are controlling *access*, not adding behaviour | [proxy](proxy.md) |
| proxy | you are adding behaviour, not controlling access | [decorator](decorator.md) |
| state | the algorithm is handed in and never changes itself | [strategy](strategy.md) |
| strategy | the object transitions itself through a lifecycle | [state](state.md) |
| mediator | communication is one-way to indifferent listeners | [observer](observer.md) |
| mediator | the subsystem does not talk back to the client | [facade](facade.md) |
| observer | peers must coordinate bidirectionally | [mediator](mediator.md) |
| adapter | you control both sides and are designing up front | [bridge](bridge.md) |
| facade | you are converting one interface, not simplifying many | [adapter](adapter.md) |
| template-method | the whole algorithm varies, not just its steps | [strategy](strategy.md) |
| abstract-factory | there is one product, not a family | [factory-method](factory-method.md) |
| composite | you only need to traverse the structure | [iterator](iterator.md) |
| composite | you need to add operations over the structure | [visitor](visitor.md) |
| command | the request must try several possible handlers | [chain-of-responsibility](chain-of-responsibility.md) |
| use-case | it provides a capability rather than decides something | [service](service.md) |
| service | the work is only interface conversion | [adapter](adapter.md) |

## Before scaffolding any of these, check the cheaper answer

These patterns have a simpler default in this pipeline's stacks. Their **When to use** sections open with it. `minimalism` applies: no abstraction with a single implementation.

| Pattern | Prefer instead, unless the pattern's criteria are genuinely met |
|---|---|
| [singleton](singleton.md) | A DI container single-instance lifetime |
| [iterator](iterator.md) | The language's native iteration protocol (`Iterable`, `IEnumerable`, `__iter__`) |
| [builder](builder.md) | Named / optional constructor arguments |
| [prototype](prototype.md) | The language's copy idiom (`copyWith`, records, value types) |
| [flyweight](flyweight.md) | Nothing — profile first; this is an optimisation |
| [interpreter](interpreter.md) | A parser generator, once the grammar is non-trivial |
| [visitor](visitor.md) | Exhaustive pattern matching over a closed hierarchy |

## Not in this directory

| Task | Goes to |
|---|---|
| Presentation — view, screen, page, component, view-model | hand off to the `ui-story` agent |
| Language-specific syntax for any pattern above | the active pack's `scaffold-snippets.md` |
| Layer boundaries, DI conventions, project commands | `.omp/agent-config.md` |

---

## Project-specific patterns

Files in this directory marked `> **Type**: project-specific` are discovered from the codebase by `/setup-scaffold` and reflect what this project actually does. **They take priority over the default shapes listed above.** A project-specific file naming a default in its `Replaces:` metadata supersedes that row entirely.

**The directory listing is authoritative, not this table.** In a deployed project the default
shapes are usually symlinks into agent-sdlc and the project's own patterns are regular files —
`ls -l` tells them apart. A project may also carry only a subset of the shapes above.

`/setup-scaffold` keeps the table current **only when this file is a regular file**. If
`INDEX.md` is a symlink into the framework, do not write project rows into it — that would leak
one project's patterns into every other project sharing the framework. Leave the table empty and
rely on the directory listing.

| Pattern | Replaces | Use when |
|---|---|---|
| _(none yet — run `/setup-scaffold`)_ | | |
