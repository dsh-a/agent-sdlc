# Bridge Pattern

> **Type**: template
> **Category**: structural
> **Triggers**: bridge, handle, body, decouple abstraction, swap implementation at runtime
> **Aliases**: Handle, Body
> **Related**: abstract-factory, adapter, strategy

## Intent

Decouple an abstraction from its implementation so that the two can vary independently.

## When to use

Scaffold a bridge when an abstraction and its implementation must evolve on separate axes — and the cross-product of the two would otherwise explode into a subclass per combination.

- The implementation must be selected or switched **at run-time**, so a permanent compile-time binding won't do.
- **Both** the abstraction and the implementation need to be extensible by subclassing, and you want to combine them freely.
- Changes to an implementation must not ripple to clients — no client recompilation, no client edits.
- You need to hide the implementation from clients entirely.
- Class count is proliferating from "nested generalizations" — a hierarchy that varies along two dimensions at once (e.g. `IcedLatte`, `HotLatte`, `IcedMocha`, `HotMocha`).
- An implementation is shared across many abstraction instances, and that sharing must stay invisible to the client.

**Not when:**
- Only one implementation exists or is ever likely to. Prefer a plain class — this is a last-resort pattern, and `minimalism` forbids an abstraction with a single implementation.
- The variation is a swappable *algorithm* rather than a whole implementation hierarchy → use `strategy.md`.
- You are conforming an existing incompatible type to an expected interface → use an adapter.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Abstraction | Defines the client-facing interface; holds a reference to an Implementor | `<domain layer>/<feature>/<Name>.<ext>` |
| RefinedAbstraction | Extends the Abstraction's interface with higher-level operations | `<domain layer>/<feature>/<Variant><Name>.<ext>` |
| Implementor | Declares the primitive-operation interface; need **not** mirror the Abstraction's interface | `<domain layer>/<feature>/Implementors/I<Name>Implementor.<ext>` |
| ConcreteImplementor | Implements the Implementor interface for one platform/backend | `<data layer>/<feature>/Implementors/<Variant><Name>Implementor.<ext>` |
| Test — abstraction | Verifies delegation and higher-level composition | `<test tree>/<feature>/<Name>Tests.<ext>` |
| Test — implementor | Verifies each concrete implementor's primitives | `<test tree>/<feature>/Implementors/<Variant><Name>ImplementorTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
    Abstraction ──────────has-a──────────▶ «interface» Implementor
         △                                        △
         │ extends                                │ implements
  RefinedAbstraction                    ConcreteImplementorA/B
```

**Collaborations:** the Abstraction forwards client requests to its Implementor object, composing the Implementor's primitive operations into higher-level operations.

## Dependencies

- Abstraction: the Implementor interface only — never a concrete implementor.
- RefinedAbstraction: its parent Abstraction; domain types only, no framework imports.
- Implementor interface: domain types only.
- ConcreteImplementor: may depend on SDKs, platform channels, clients, and config — it lives at the data/infrastructure layer.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Implementor: I<Name>Implementor — primitive operations only
//   (e.g. drawLine, drawArc — not drawRectangle).
// ConcreteImplementor: one class per backend, implementing the primitives.
// Abstraction: <Name> holds a reference to I<Name>Implementor, injected via
//   constructor; exposes client-facing operations built from the primitives.
// RefinedAbstraction: <Variant><Name> extends <Name>, adding higher-level
//   operations; does not know which ConcreteImplementor is behind it.
```

## Wiring

Register each ConcreteImplementor in the DI container (per `.omp/agent-config.md` § Pattern Compliance). The Abstraction receives its Implementor via constructor injection. When the implementation must be chosen at run-time, inject a factory that resolves the correct ConcreteImplementor from configuration or platform detection rather than resolving it inside the Abstraction.

## Conventions

- The Implementor interface exposes **primitive** operations; the Abstraction composes them into higher-level ones. The two interfaces deliberately differ — if they are identical, this is a needless indirection, not a bridge.
- Clients depend on the Abstraction only, never on the Implementor.
- ConcreteImplementors are stateless where possible; if an implementor is shared across abstractions, that sharing is an implementation detail and must not leak.
- Adding a backend means adding a ConcreteImplementor only — no change to the Abstraction hierarchy, and vice versa.
- Framework/platform imports are permitted in ConcreteImplementors, never in the Abstraction or the Implementor interface.

## Tests

- Test each ConcreteImplementor independently against the Implementor contract.
- Test the Abstraction against a fake/mock Implementor — assert it delegates to the primitives and composes them correctly.
- Test that the same Abstraction produces equivalent results across two different ConcreteImplementors (interchangeability).
- Test run-time implementor swapping if the abstraction supports it.
- Do not assert on concrete implementor internals from Abstraction tests — that couples the axes the pattern exists to separate.

## Consequences

1. **Decoupled interface and implementation.** The implementation is not permanently bound to the interface; it can be configured — even changed — at run-time. Compile-time dependencies on the implementation disappear, so changing an implementation class does not force recompilation of the Abstraction or its clients (essential for binary compatibility across library versions). Encourages layering: the high-level part of the system knows only Abstraction and Implementor.
2. **Improved extensibility.** The Abstraction and Implementor hierarchies extend independently.
3. **Implementation details hidden from clients.** Clients are shielded from implementor sharing and any accompanying reference-counting.
4. **Cost: indirection.** Every abstraction call is a delegation hop, and the two-hierarchy structure is harder to read than a single class. Only pay this when the two axes genuinely vary.
