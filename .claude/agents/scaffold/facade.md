# Facade Pattern

> **Type**: template
> **Category**: structural
> **Triggers**: facade, unified interface, simplify subsystem, aggregate repositories, feature-level API
> **Related**: adapter, mediator, singleton, use-case

## Intent

Provide a unified interface to a set of interfaces in a subsystem. Facade defines a higher-level interface that makes the subsystem easier to use.

## When to use

Scaffold a facade when consumers need a **cohesive feature-level API** over several repositories, services, or use cases, and wiring them together at every call site would spread subsystem knowledge across the codebase.

- You want a simple interface to a complex subsystem. Subsystems get more complex as they evolve; a facade gives the default view that most clients need.
- There are many dependencies between clients and the implementation classes of an abstraction, and you want to decouple them.
- You want to **layer** your subsystems: a facade per layer becomes the single entry point, and layers communicate only through facades.

**Not when:**
- The methods would be thin one-to-one wrappers over a single dependency. That is a pass-through class, not a facade, and `minimalism` forbids it.
- You are converting one incompatible interface to another → `adapter.md`. A facade *simplifies* many; an adapter *converts* one.
- The logic is a single business operation with validation and rules → `use-case.md`.
- Subsystem components need to coordinate with each other bidirectionally → `mediator.md`.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Facade | Knows which subsystem classes handle a request and delegates to them | `<domain layer>/<feature>/<Feature>Facade.<ext>` |
| Subsystem classes | Do the real work; have no knowledge of the facade | `<domain layer>/<feature>/…`, `<data layer>/<feature>/…` |
| Client | Depends on the facade instead of on the subsystem's parts | UI / presentation layer, other features |
| Test | Verifies orchestration and error propagation across mocked subsystem parts | `<test tree>/<feature>/<Feature>FacadeTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
                    ┌──────── subsystem ────────┐
  Client ──▶ Facade │  IRepoA   IRepoB  IService │
                 └──┼──▶  │       │         │    │
                    └───────────────────────────┘
   (clients never reach past the facade into the subsystem)
```

**Collaborations:** clients communicate with the subsystem by sending requests to the Facade, which forwards them to the appropriate subsystem objects. Clients that use the facade do not access its subsystem objects directly.

## Dependencies

- Repository interfaces, service interfaces, other facades, and use cases — all injected via constructor.
- Interfaces only, never implementations.
- No framework imports — the facade sits in the domain layer.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Facade: <Feature>Facade — constructor-injects the subsystem interfaces it coordinates.
// Public methods represent meaningful FEATURE-level operations, named in domain terms.
// Each method: fan out to the subsystem parts (in parallel where independent),
//   combine the results into a domain-level result type, and translate partial
//   failures deliberately.
// Holds no business rules and no state between calls.
```

## Wiring

Register the facade in the DI container (per `.omp/agent-config.md` § Pattern Compliance). Consumers depend on the facade, not on the individual repositories and services it wraps. The facade itself receives subsystem **interfaces**. Where the project layers subsystems, register one facade per layer and forbid cross-layer access to anything else.

## Conventions

- Methods represent meaningful feature-level operations, not thin wrappers over a single dependency.
- The facade **orchestrates**; it holds no business rules — those live in use cases and domain services.
- Dependencies are interfaces, injected via constructor, stored as private readonly fields.
- The facade is stateless between calls.
- Independent subsystem calls are issued concurrently where the language supports it; sequence them only when there is a real data dependency.
- Partial failure is a decision, not an accident: state per method whether one failing dependency fails the whole call or degrades the result.
- Subsystem classes never hold a reference back to the facade.
- No framework imports in the domain layer.

## Tests

- Mock every dependency at the interface level.
- Test orchestration: the correct subsystem calls are made, with the correct arguments, and their results are combined properly.
- Test error propagation — one dependency fails, and the facade handles it as documented (fail the call, or degrade).
- Test that independent calls are actually concurrent where that is a stated requirement.
- Do not re-test subsystem behaviour here; that belongs to each subsystem part's own tests.

## Consequences

1. **Shields clients from subsystem components,** reducing the number of objects clients deal with and making the subsystem easier to use.
2. **Promotes weak coupling between subsystem and clients.** Components within the subsystem can vary — or be replaced entirely — without affecting clients. This also eliminates circular dependencies and reduces compilation churn in large systems.
3. **Does not prevent applications from using subsystem classes directly** if they need to. You keep the choice between ease of use and generality; the facade is a default view, not a wall.
4. **Cost: a facade can become a god object.** Because everything routes through it, it attracts rules that belong elsewhere. Keep it to orchestration, and split it when one feature's surface grows past coherence.
