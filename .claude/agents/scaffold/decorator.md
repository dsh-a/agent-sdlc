# Decorator Pattern

> **Type**: template
> **Category**: structural
> **Triggers**: decorator, wrapper, add behaviour dynamically, layer responsibilities, caching/logging/retry wrapper
> **Aliases**: Wrapper
> **Related**: adapter, composite, proxy, strategy, chain-of-responsibility

## Intent

Attach additional responsibilities to an object dynamically. Decorators provide a flexible alternative to subclassing for extending functionality.

## When to use

Scaffold a decorator when you want to add behaviour **around** an existing operation while keeping its interface identical — so callers cannot tell the difference and layers can be stacked in any combination.

- You want to add responsibilities to individual objects dynamically and transparently, without affecting other objects.
- Responsibilities can be **withdrawn** — a layer enabled in production and absent in tests.
- Extension by subclassing is impractical because combinations explode: a subclass per feature-combination, or a sealed/final class you cannot subclass at all.
- Cross-cutting concerns wrap a domain operation: caching, retry, logging, metrics, authorisation, rate limiting.

**Not when:**
- Only one combination will ever exist. Put the behaviour in the class; `minimalism` forbids a wrapper for a single case.
- The interface must change → `adapter.md`.
- You are controlling *access* to the object rather than adding behaviour → `proxy.md` (same shape, different intent — say which you mean).
- You are swapping the whole algorithm rather than layering around it → `strategy.md`.
- The chain should be able to stop and not call the next link → `chain-of-responsibility.md`.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Component | The interface shared by decorated and undecorated objects | `<domain layer>/<feature>/I<Name>.<ext>` |
| ConcreteComponent | The object to which responsibilities are added | `<domain layer>/<feature>/<Name>.<ext>` |
| Decorator | Holds a Component reference and conforms to its interface | `<domain layer>/<feature>/Decorators/<Name>Decorator.<ext>` (optional base) |
| ConcreteDecorator | Adds one responsibility around the wrapped component | `<data layer>/<feature>/Decorators/<Concern><Name>Decorator.<ext>` |
| Test | Verifies each decorator's added behaviour and its delegation | `<test tree>/<feature>/Decorators/<Concern><Name>DecoratorTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──▶ «interface» Component ◀───────────────┐
                     △                             │ wraps
        ┌────────────┴────────────┐                │
  ConcreteComponent           Decorator ───────────┘
   + operation()          + operation()  → component.operation()
                                △
                    ┌───────────┴───────────┐
            CachingDecorator          RetryDecorator
```

**Collaborations:** a Decorator forwards requests to its Component object, optionally performing additional operations before and after forwarding.

## Dependencies

- Component interface and ConcreteComponent: domain types only — no framework imports.
- ConcreteDecorator: the Component interface plus whatever its concern needs (cache, logger, clock, policy). Infrastructure-flavoured decorators live at the data layer.
- Client: the Component interface. It must never know it holds a decorated object.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Component: I<Name> — the shared interface; identical for wrapped and unwrapped.
// ConcreteComponent: <Name> — the real behaviour, unaware it may be decorated.
// Decorator (optional base): holds I<Name> inner and forwards every method verbatim,
//   so a ConcreteDecorator overrides only the methods it cares about.
// ConcreteDecorator: <Concern><Name>Decorator implements I<Name>, takes I<Name> via
//   constructor, and does before/after work around inner.<method>().
//   It ALWAYS calls through unless its concern is explicitly to short-circuit (cache hit).
```

## Wiring

Compose the stack once at the composition root and register the outermost decorator as the Component binding (per `.omp/agent-config.md` § Pattern Compliance) — clients resolve `I<Name>` and receive the whole stack. Order is meaningful and belongs in one visible place: build it explicitly (e.g. `Logging(Retry(Caching(Real())))`) rather than by registration side effects. Decorators that should be absent in some environments are simply omitted from that expression.

## Conventions

- The decorator implements the Component interface **exactly** — no extra public methods, or clients start depending on the wrapper and the stack stops being transparent.
- One concern per decorator. A decorator that both caches and logs is two decorators.
- Always delegate to the wrapped component unless the concern's whole purpose is to short-circuit; make that intent explicit in the class name and doc.
- Stacking order is documented where the stack is built, because behaviour depends on it (retry-inside-cache and cache-inside-retry mean different things).
- Decorators are stateless with respect to the domain; their state is their own concern's (cache entries, attempt counters).
- Beware object identity: a decorated component is **not** the same object as the component. Never compare by reference or type-test across the seam.

## Tests

- Test each decorator against a fake Component: assert it delegates, and assert its added behaviour occurs.
- Test the pass-through case — arguments and return values must survive the wrapper unchanged.
- Test error propagation: the wrapped component throws, and the decorator either passes it through or handles it deliberately.
- Test short-circuit decorators both ways: on a cache hit the inner component is **not** called; on a miss it is called exactly once.
- Test one representative stack of two or more decorators to confirm ordering behaves as documented.
- Test the ConcreteComponent with no decorators at all.

## Consequences

1. **More flexibility than static inheritance.** Responsibilities can be added and removed at run-time, and the same responsibility can be attached twice. Inheritance would require a class per combination.
2. **Avoids feature-laden classes high up in the hierarchy.** Rather than a base class that pays for every feature, you define a simple component and add functionality incrementally — so features nobody uses cost nothing.
3. **Cost: a decorator and its component are not identical.** A decorated component is not the same object as its component; you cannot rely on object identity or type tests when decorators are in play.
4. **Cost: lots of little objects.** A design using decorators yields many similar-looking objects differing only in how they are interconnected. That is easy to customise but can be hard to learn and debug — a stack trace through five wrappers hides where the real work happened.
