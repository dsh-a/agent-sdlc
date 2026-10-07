# Flyweight Pattern

> **Type**: template
> **Category**: structural
> **Triggers**: flyweight, shared instances, intrinsic extrinsic state, object explosion, memory pressure, interning
> **Related**: composite, singleton, state, strategy

## Intent

Use sharing to support large numbers of fine-grained objects efficiently.

## When to use

> **Measure first.** Flyweight is an optimisation and it makes code harder to read. Scaffold it only against an observed memory or allocation problem, never on suspicion — `minimalism` treats a speculative flyweight as unrequested complexity.

Apply the pattern only when **all** of the following hold:

- The application uses a **large number** of objects.
- Storage costs are high because of that sheer quantity.
- Most object state can be made **extrinsic** — moved out of the object and passed in by the client.
- Many groups of objects can be replaced by relatively few shared objects, once extrinsic state is removed.
- The application **does not depend on object identity**. Since flyweights are shared, identity comparisons will conflate objects the client thinks are distinct.

**Not when:**
- The object count is thousands rather than millions, or profiling shows no pressure. The indirection costs more than it saves.
- The objects are mutable. A shared mutable flyweight corrupts every holder at once.
- Clients compare instances by reference, or attach per-instance metadata.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Flyweight | Declares operations that can receive extrinsic state as parameters | `<domain layer>/<feature>/Flyweights/I<Name>Flyweight.<ext>` |
| ConcreteFlyweight | Stores intrinsic (shareable) state; must be immutable and context-independent | `<domain layer>/<feature>/Flyweights/<Name>Flyweight.<ext>` |
| UnsharedConcreteFlyweight | A Flyweight subclass that is not shared, typically a parent of shared children | `<domain layer>/<feature>/Flyweights/<Name>Unshared.<ext>` |
| FlyweightFactory | Creates and manages flyweights; ensures they are shared properly | `<domain layer>/<feature>/Flyweights/<Name>FlyweightFactory.<ext>` |
| Client | Holds references to flyweights and computes or stores their extrinsic state | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test — factory | Verifies sharing, pooling, and that identical keys return the identical instance | `<test tree>/<feature>/Flyweights/<Name>FlyweightFactoryTests.<ext>` |
| Test — flyweight | Verifies operations are correct for varying extrinsic state | `<test tree>/<feature>/Flyweights/<Name>FlyweightTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  FlyweightFactory  { pool: key -> Flyweight }
        │ getFlyweight(key) returns existing or creates
        ▼
  «interface» Flyweight
   + operation(extrinsicState)
        △
  ConcreteFlyweight            UnsharedConcreteFlyweight
   - intrinsicState (shared)    - allState (not shared)
        ▲
  Client ──holds──┘  + owns/computes extrinsicState
```

**Collaborations:** state needed by a flyweight is either intrinsic (stored in the ConcreteFlyweight) or extrinsic (stored or computed by the Client and passed in on each call). Clients obtain flyweights **only** through the factory, never by constructing them.

## Dependencies

- Flyweight interface and ConcreteFlyweight: domain types only — no framework imports, no injected services (a flyweight must stay context-free).
- FlyweightFactory: the flyweight types and a pool structure.
- Client: the factory and the Flyweight interface; it owns the extrinsic state.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Flyweight: I<Name>Flyweight with operation(<Extrinsic> state) — every context-
//   dependent value arrives as a PARAMETER, never as a field.
// ConcreteFlyweight: <Name>Flyweight holds only immutable intrinsic state.
//   Value-equality and a stable hash on the intrinsic state form the pool key.
// FlyweightFactory: <Name>FlyweightFactory with a pool map and
//   get(key) -> I<Name>Flyweight that returns the pooled instance or creates and
//   pools one. The constructor is private/internal so clients cannot bypass the pool.
// Client: stores extrinsic state alongside its flyweight reference.
```

## Wiring

Register the FlyweightFactory in the DI container as a **single shared instance** (per `.omp/agent-config.md` § Pattern Compliance) — a per-request factory defeats the sharing that is the entire point. Never register individual flyweights. If the pool must be bounded, put the eviction policy in the factory and document it; if the pool is unbounded, say so, because it will live for the process lifetime.

## Conventions

- Intrinsic state is **immutable** and context-independent. Any mutable or per-context value is extrinsic, full stop.
- Clients obtain flyweights only via the factory; hide or restrict the constructor so the pool cannot be bypassed.
- Extrinsic state is a parameter on every operation, never a field and never a thread-local.
- Never compare flyweights by identity in client logic, and never attach per-instance metadata to one.
- Document the pool's lifetime and bound. An unbounded pool keyed on user input is a memory-exhaustion path.
- Keep the intrinsic key small and cheap to hash; the lookup runs on the hot path this pattern exists to relieve.

## Tests

- Assert `get(key)` twice with the same key returns the **identical** instance, and different keys return different instances.
- Assert the pool grows by exactly one per distinct key across many requests — this is the test that proves sharing.
- Test operations across several different extrinsic states against one shared flyweight, confirming no state bleeds between calls.
- Assert the flyweight exposes no mutating API; attempting to mutate should not compile, or must fail.
- If the pool is bounded, test the eviction policy at the boundary.
- Benchmark or assert an allocation count if the memory saving is the acceptance criterion — otherwise there is no evidence the pattern earned its complexity.

## Consequences

1. **Storage savings, in proportion to the sharing achieved.** Savings come from the reduced total number of instances, the reduced intrinsic state per instance, and whether extrinsic state is computed rather than stored. The more flyweights are shared, the greater the saving.
2. **Extrinsic state must be found, transferred, or computed on every call** — a run-time cost traded for the space saving. That trade is only worth it when extrinsic state is cheap to compute or already at hand.
3. **Cost: object identity is destroyed.** Conceptually distinct objects become the same instance, so identity comparison, per-instance metadata, and reference-keyed maps all break silently.
4. **Cost: readability.** Splitting an object's state across the object and its callers is unusual, and every call site must now carry the extrinsic half. This is why the pattern needs a measured justification.
