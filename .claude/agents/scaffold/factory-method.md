# Factory Method Pattern

> **Type**: template
> **Category**: creational
> **Triggers**: factory method, virtual constructor, defer instantiation, subclass decides type
> **Aliases**: Virtual Constructor
> **Related**: abstract-factory, prototype, template-method

## Intent

Define an interface for creating an object, but let subclasses decide which class to instantiate. Factory Method lets a class defer instantiation to subclasses.

## When to use

Scaffold a factory method when a class must create objects but **cannot know their concrete type** — the type is chosen by whichever subclass or configuration is in play.

- A class can't anticipate the class of objects it must create.
- A class wants its **subclasses** to specify the objects it creates.
- You are delegating responsibility to one of several helper subclasses and want to localize *which* helper is the delegate.
- A framework must instantiate application-specific types it has never heard of.

**Not when:**
- You need a whole **family** of related products created together → `abstract-factory.md`.
- The choice is a simple map from a key to a type with no subclassing involved — a plain static factory function or a registry is simpler and honours `minimalism`.
- Creation is a straight `new` with no variation. Do not wrap a constructor for its own sake.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Product | Declares the interface of the objects the factory method creates | `<domain layer>/<feature>/I<Product>.<ext>` |
| ConcreteProduct | Implements the Product interface | `<data layer>/<feature>/<Variant><Product>.<ext>` |
| Creator | Declares the factory method returning a Product; may supply a default; calls it from its own operations | `<domain layer>/<feature>/<Name>Creator.<ext>` |
| ConcreteCreator | Overrides the factory method to return one ConcreteProduct | `<data layer>/<feature>/<Variant><Name>Creator.<ext>` |
| Test — creator | Asserts each concrete creator produces the expected product type | `<test tree>/<feature>/<Variant><Name>CreatorTests.<ext>` |
| Test — product | Verifies each concrete product against the Product contract | `<test tree>/<feature>/<Variant><Product>Tests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
        Creator                          «interface» Product
   + factoryMethod() ──creates──▶                △
   + anOperation()                               │
          △                                      │
   ConcreteCreator ─────────────creates──── ConcreteProduct
   + factoryMethod()
```

**Collaborations:** the Creator relies on its subclasses to define the factory method so that it returns the appropriate ConcreteProduct. The Creator's own operations are written against the Product interface and never change.

## Dependencies

- Product interface and Creator: domain types only — no framework imports.
- ConcreteCreator: the concrete product it instantiates.
- ConcreteProduct: may depend on SDKs, clients, and platform APIs at the data/infrastructure layer.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Product: I<Product> — the interface every created object satisfies.
// Creator: <Name>Creator — abstract (or with a default); declares
//   create<Product>(args) -> I<Product> as the single point of instantiation,
//   and calls it from its concrete template operations.
// ConcreteCreator: <Variant><Name>Creator overrides create<Product>() and is the
//   ONLY place the concrete product type is named.
// ConcreteProduct: <Variant><Product> implements I<Product>.
```

## Wiring

Register the Creator→ConcreteCreator binding in the DI container (per `.omp/agent-config.md` § Pattern Compliance), choosing the variant at the composition root. Consumers depend on the Creator, and receive products only as the Product interface. Where the language makes subclassing awkward, a parameterised factory — one creator taking a type key — is an accepted variation; keep the key-to-type mapping in a single table.

## Conventions

- The factory method is the **only** place a concrete product type is named. If `new ConcreteProduct` appears elsewhere, the pattern is not doing its job.
- The factory method returns the Product interface, never a concrete type.
- The Creator's other operations are written entirely against the Product interface, so adding a variant never edits them.
- Provide a default implementation in the Creator only when a sensible default product exists; otherwise leave it abstract so a missing override is a compile error.
- No framework imports in the Creator or the Product interface.

## Tests

- For each ConcreteCreator, assert the factory method returns the expected concrete type.
- Test the Creator's template operations against a test subclass returning a stub product — proving they depend only on the interface.
- Test each ConcreteProduct against the Product contract.
- If a parameterised variation is used, test the unknown-key path produces a domain error rather than a null or a default.

## Consequences

1. **Eliminates the need to bind application-specific classes into your code.** Code deals only with the Product interface, so it works with any user-defined ConcreteProduct.
2. **Provides hooks for subclasses.** Creating objects via a factory method is always more flexible than creating them directly — subclasses get an extension point for free.
3. **Connects parallel class hierarchies.** When a product hierarchy mirrors a creator hierarchy, the factory method is the seam that pairs them.
4. **Cost: a subclass just to create an object.** If the Creator has no other reason to be subclassed, you inherit a whole hierarchy for one method. Prefer a parameterised factory or plain DI registration in that case.
