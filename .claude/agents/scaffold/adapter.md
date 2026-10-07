# Adapter Pattern

> **Type**: template
> **Category**: structural
> **Triggers**: adapter, wrapper, incompatible interface, conform third-party API, legacy interface
> **Aliases**: Wrapper
> **Related**: bridge, decorator, proxy, facade

## Intent

Convert the interface of a class into another interface clients expect. Adapter lets classes work together that could not otherwise, because of incompatible interfaces.

## When to use

Scaffold an adapter when you must use an **existing** class whose interface you do not control and cannot change — a vendor SDK, a legacy service, a platform API — and it does not match the interface your code already expects.

- You want to use an existing class, but its interface does not match the one you need.
- You want to create a reusable class that cooperates with unforeseen classes — ones with incompatible interfaces.
- You need to use several existing subclasses, and adapting each by subclassing is impractical; an object adapter adapts the parent's interface once.

**Not when:**
- You control both interfaces. Fix the mismatch at the source; an adapter that exists to paper over your own design is debt.
- You are designing the abstraction/implementation split **up front** → `bridge.md`. Bridge is planned; Adapter is a retrofit.
- You want to simplify a complex subsystem rather than convert one interface → `facade.md`.
- You want to add behaviour while keeping the same interface → `decorator.md`.
- The mismatch is a single field rename at one call site. Inline it; `minimalism` forbids a class for that.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Target | The domain-facing interface the client expects | `<domain layer>/<feature>/I<Name>.<ext>` |
| Adaptee | The existing type with the incompatible interface (not yours to edit) | external SDK / legacy module |
| Adapter | Implements Target by translating calls to the Adaptee | `<data layer>/<feature>/Adapters/<Adaptee><Name>Adapter.<ext>` |
| Client | Collaborates with objects conforming to Target only | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test | Verifies translation in both directions against a faked Adaptee | `<test tree>/<feature>/Adapters/<Adaptee><Name>AdapterTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──▶ «interface» Target          Adaptee  (existing, unmodifiable)
                     △                  + specificRequest()
                     │ implements                △
                  Adapter ──────────holds────────┘
                + request()  →  adaptee.specificRequest()
```

**Collaborations:** clients call operations on an Adapter instance; the Adapter in turn calls Adaptee operations that carry out the request, translating arguments, results, and errors across the seam.

## Dependencies

- Target interface: domain types only — no framework or SDK imports. This is the whole point: the SDK type must not reach the domain.
- Adapter: the Adaptee (SDK/legacy client) plus a mapper and the project logger. It lives at the data/infrastructure layer.
- Client: the Target interface only.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Target: I<Name> — expressed entirely in domain vocabulary and domain types.
// Adapter: <Adaptee><Name>Adapter implements I<Name>; holds the Adaptee via
//   constructor injection (object adapter — prefer this over inheriting the Adaptee).
//   Each method: map domain args -> adaptee args, call, map result -> domain type,
//   and translate adaptee exceptions into domain errors.
// Keep mapping in named private methods (toDomain / toAdaptee) so it is testable.
```

## Wiring

Bind the Target interface to the Adapter in the DI container (per `.omp/agent-config.md` § Pattern Compliance), injecting the Adaptee (SDK client) into the Adapter at the composition root. Domain code depends on the Target. Where several Adaptees back the same Target, register the chosen one by configuration — the client is unaffected either way.

## Conventions

- Prefer the **object adapter** (hold the Adaptee) over the class adapter (inherit it). Composition survives Adaptee changes and works when the Adaptee hierarchy is sealed.
- No Adaptee type appears in the Target interface — not in parameters, returns, or thrown errors. A leaked SDK type defeats the adapter.
- Translate errors as deliberately as data: adaptee exceptions become domain errors, with the original attached as a cause.
- The adapter holds **no business rules**. It converts, and nothing more; rules belong in the use case.
- One adapter per Adaptee. Do not let one class adapt two unrelated SDKs.
- Framework and SDK imports are expected here and forbidden in the Target interface.

## Tests

- Test each Target method against a faked/mocked Adaptee: assert the adaptee call receives correctly translated arguments.
- Test result translation, including the awkward cases — nulls, empty collections, enum values with no domain equivalent.
- Test error translation: make the Adaptee throw and assert a domain error surfaces with the cause preserved.
- Assert no SDK type escapes: the test file for the client should compile with no SDK import at all.
- Test the client against a fake Target, never against the adapter.

## Consequences

1. **Decouples the client from the adaptee.** The client is written once against the Target and works with any Adaptee for which an adapter exists — including ones that did not exist when the client was written.
2. **A single object adapter can adapt a whole hierarchy.** Because it holds rather than inherits, one adapter works with the Adaptee **and all its subclasses**, adding adapted behaviour to all of them at once.
3. **Contains the blast radius of a vendor change.** When the SDK's interface shifts, exactly one class changes.
4. **Cost: an extra indirection and a mapping surface that can drift.** Every adaptee concept must be mapped, and a partially-mapped enum or an unhandled error type fails at run-time. The class adapter variation reduces the indirection but commits you to one concrete Adaptee and forfeits the hierarchy-wide benefit above.
