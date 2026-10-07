# Singleton Pattern

> **Type**: template
> **Category**: creational
> **Triggers**: singleton, single instance, global access point, one and only one
> **Related**: abstract-factory, builder, prototype, facade

## Intent

Ensure a class has only one instance, and provide a global point of access to it.

## When to use

> **Read this first.** In a project with a DI container — which this pipeline assumes (per `.omp/agent-config.md` § Pattern Compliance) — the *requirement* "exactly one instance" is satisfied by registering the type with a **singleton/single-instance lifetime**. That gives you the one instance without the global access point, and it stays injectable and testable. Reach for the classic self-managed singleton only when a DI lifetime genuinely cannot apply.

- There must be exactly one instance of a class, and it must be accessible to clients from a well-known access point.
- The sole instance must be **extensible by subclassing**, and clients should be able to use the extended instance without changing their code.

**Not when:**
- A DI container is available and the type can be injected. Register a single-instance lifetime instead — this covers the overwhelming majority of cases and is the correct scaffold here.
- You want convenient global access to state or helpers. That is the anti-pattern form: it hides dependencies, couples every caller to a concrete type, and leaks state between tests.
- The object is stateless. Then instance count is irrelevant; inject a plain instance.
- The value differs per request, per user, or per scope. A singleton will silently serve the wrong one.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Singleton | Defines the instance accessor and guards its own single instantiation | `<domain layer>/<feature>/<Name>.<ext>` |
| Singleton interface | The contract clients depend on, so the instance stays substitutable in tests | `<domain layer>/<feature>/I<Name>.<ext>` |
| Client | Obtains the instance via injection (preferred) or the access point | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test | Verifies single-instance behaviour and per-test state isolation | `<test tree>/<feature>/<Name>Tests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
        Singleton                      Preferred form:
  - instance : Singleton          container.registerSingleton<I<Name>, <Name>>()
  + getInstance() : Singleton                    │
  + operation()                        Client ◀──┘ constructor-injected as I<Name>
       ▲
       │ clients reach through a global access point (avoid)
```

**Collaborations:** clients access a Singleton instance solely through its access point — or, in the preferred form, receive the single registered instance by injection and never see an access point at all.

## Dependencies

- Singleton interface: domain types only — no framework imports.
- Singleton implementation: whatever the resource requires. Keep them injected, so the singleton itself stays testable.
- Client: the interface. A client naming the concrete singleton type is the coupling this pattern is notorious for.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// PREFERRED — DI-managed lifetime:
//   I<Name>: the contract.  <Name>: an ordinary class with a normal constructor.
//   Registered once at the composition root with a single-instance lifetime.
//   No static state, no getInstance(). Clients constructor-inject I<Name>.
//
// CLASSIC — only when no container can own the lifetime:
//   <Name> with a private constructor, a private static instance field, and a
//   static accessor performing lazy, thread-safe initialisation (use the language's
//   idiom: static initialiser, lazy, once-token — not a hand-rolled double-check).
//   Expose a reset/override seam for tests.
```

## Wiring

Register the interface with a single-instance lifetime in the DI container (per `.omp/agent-config.md` § Pattern Compliance). This *is* the wiring — the container becomes the single point of truth for the lifetime, and clients receive the instance by constructor injection. If a classic singleton is unavoidable (a platform callback with no injection seam, a static entry point), wrap it behind an injectable interface at the first opportunity so that only one adapter class touches the global accessor.

## Conventions

- Prefer a container lifetime over a self-managed instance. Scaffold the classic form only with a stated reason.
- Always define an interface. Without it the singleton is unmockable and every consumer is welded to a concrete type.
- Initialisation is lazy and thread-safe via the language's built-in idiom.
- A singleton holding **mutable** state must expose an explicit reset seam, and tests must use it. Undisposed state leaking between tests is this pattern's signature failure.
- Never call the global accessor from domain code. Inject the interface instead.
- Subclassing the sole instance, if needed, is decided at registration — not inside the accessor.

## Tests

- Assert two resolutions return the identical instance (reference equality).
- Assert consumers work against a substituted fake — proving they depend on the interface, not the accessor.
- If the singleton holds mutable state, run two tests that both mutate it and assert the second sees clean state; this fails loudly when the reset seam is missing.
- Test lazy initialisation happens once, even under concurrent access, if the platform has real concurrency.

## Consequences

1. **Controlled access to the sole instance.** The class encapsulates its instance, so it controls strictly how and when clients access it.
2. **Reduced namespace.** An improvement over global variables: it avoids polluting the namespace with names that store sole instances.
3. **Permits refinement of operations and representation.** The class may be subclassed, and the application configured with an instance of the extended class at run-time.
4. **Permits a variable number of instances.** The same approach relaxes to allow more than one instance later, changing only the accessor — clients are unaffected.
5. **Cost: hidden global state.** A self-managed singleton makes dependencies invisible at the call site, couples callers to a concrete type, and carries state across test boundaries. These costs are why the DI-lifetime form is the default here and the classic form needs justification.
