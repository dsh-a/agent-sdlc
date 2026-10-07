# Prototype Pattern

> **Type**: template
> **Category**: creational
> **Triggers**: prototype, clone, copy existing instance, copyWith, deep copy, template instance
> **Related**: abstract-factory, composite, decorator, memento

## Intent

Specify the kinds of objects to create using a prototypical instance, and create new objects by copying this prototype.

## When to use

Scaffold a prototype when new objects are best described as **variations on an existing configured instance** rather than as a set of constructor arguments.

- The classes to instantiate are specified at run-time — loaded dynamically, registered by plugins, or chosen from a catalogue.
- You want to avoid a creator hierarchy that parallels the product hierarchy.
- Instances of a class can be in only a handful of **different state combinations**; cloning pre-configured prototypes is cheaper and clearer than reconstructing state each time.
- Construction is expensive (parsed config, warmed cache, seeded state) and copying is not.

**Not when:**
- The language already gives you idiomatic copying — Dart/Kotlin `copyWith`, records, value types, `dataclasses.replace`. **In the default Flutter pack this is nearly always the right answer**; use the built-in and skip the pattern.
- The object graph has cycles or shared mutable references, where a correct deep copy is harder to maintain than a factory.
- The object is cheap to construct. A constructor is simpler and `minimalism` prefers it.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Prototype | Declares the cloning operation | `<domain layer>/<feature>/I<Name>Prototype.<ext>` |
| ConcretePrototype | Implements cloning by copying itself | `<domain layer>/<feature>/<Variant><Name>.<ext>` |
| PrototypeRegistry | Holds named prototypes and returns clones on request (optional but common) | `<domain layer>/<feature>/<Name>PrototypeRegistry.<ext>` |
| Client | Asks a prototype (or the registry) for a clone and mutates the copy | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test — clone | Verifies copy depth and independence from the original | `<test tree>/<feature>/<Variant><Name>CloneTests.<ext>` |
| Test — registry | Verifies registration, lookup, and that lookups never hand out the original | `<test tree>/<feature>/<Name>PrototypeRegistryTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──▶ «interface» Prototype          PrototypeRegistry
                   + clone()                  { key -> Prototype }
                        △                            │
        ┌───────────────┴───────────────┐            │ returns clone()
  ConcretePrototypeA        ConcretePrototypeB ◀──────┘
```

**Collaborations:** a client asks a prototype to clone itself, then configures the copy. The original is never handed out and never mutated.

## Dependencies

- Prototype interface and concrete prototypes: domain types only — no framework imports.
- Registry: the prototype interface plus whatever seeds the catalogue (config, plugin scan).
- Client: the Prototype interface or the registry — never a concrete prototype type.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Prototype: I<Name>Prototype declaring clone() -> I<Name>Prototype.
// ConcretePrototype: <Variant><Name> implements clone() by copying its own fields.
//   Document per field whether the copy is deep or shallow; deep-copy anything mutable.
//   Where the language has copyWith/record copy, implement clone() in terms of it.
// Registry (optional): register(key, prototype) / create(key) -> clone. create() ALWAYS
//   returns a clone, never the stored instance.
// Client: obtains a clone, then mutates the copy only.
```

## Wiring

Seed the registry once at the composition root and register it in the DI container (per `.omp/agent-config.md` § Pattern Compliance) as a single shared instance — the registry is shared, the prototypes inside it are never handed out directly. Clients depend on the registry or the Prototype interface. If prototypes are contributed by plugins or config, register them during startup before the first resolve.

## Conventions

- `clone()` returns the Prototype interface type so clients stay decoupled from concrete types.
- Every mutable field is deep-copied; every immutable or intentionally shared field is shallow-copied **and commented as deliberate**. Undocumented shallow copies are this pattern's defining bug.
- The registry hands out clones only — returning a stored prototype lets a client corrupt the catalogue for everyone.
- Prototypes are configured once and then treated as read-only.
- Prefer the language's native copy idiom inside `clone()` rather than hand-rolled field assignment, so a new field can't be silently dropped.
- No framework imports in prototypes or the registry.

## Tests

- Clone an instance and assert every field matches the original — this is the test that catches a field added later but forgotten in `clone()`.
- Mutate the clone and assert the original is unchanged, and vice versa.
- For each mutable nested object, assert the clone holds a **different instance**, not a shared reference.
- Test the registry returns a distinct instance on every `create()` call for the same key.
- Test an unknown registry key produces a domain error, not null.

## Consequences

1. **Adding and removing products at run-time.** A new product is incorporated by registering a prototype instance; that is the cheapest form of dynamic registration a system can offer.
2. **Specifying new objects by varying values.** Highly dynamic systems let you define new behaviour through object composition rather than new classes — effectively new "classes" without writing any.
3. **Reduced subclassing.** Prototype avoids the creator hierarchy that `factory-method.md` requires; cloning replaces the parallel hierarchy entirely.
4. **Cost: every subclass must implement clone, and correctly.** This is hard when a class already exists, holds circular references, or contains objects that don't support copying — and a clone that shares a mutable reference by accident fails silently and far from the cause.
