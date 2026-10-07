# Abstract Factory Pattern

> **Type**: template
> **Category**: creational
> **Triggers**: abstract factory, kit, product family, family of related objects, platform-specific object set
> **Aliases**: Kit
> **Related**: factory-method, prototype, singleton, bridge

## Intent

Provide an interface for creating families of related or dependent objects without specifying their concrete classes.

## When to use

Scaffold an abstract factory when objects come in **families that must be used together**, and the whole family is chosen at once — per platform, per theme, per tenant, per backend.

- The system must be independent of how its products are created, composed, and represented.
- The system must be configurable with one of **multiple families** of products.
- A family of related products is designed to be used together and you need to **enforce that constraint** — mixing families must be impossible by construction.
- You want to publish a class library of products revealing only their interfaces, not their implementations.

**Not when:**
- There is one product, not a family → use `factory-method.md`.
- The family has exactly one variant today and no second is planned. One implementation behind an abstraction violates `minimalism`.
- Products vary independently along two axes rather than moving as a set → use `bridge.md`.
- Creation is a single step over a simple object → a constructor or a DI registration is enough.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| AbstractFactory | Declares one creation operation per product in the family | `<domain layer>/<feature>/Factories/I<Name>Factory.<ext>` |
| ConcreteFactory | Implements those operations for one variant, returning that variant's products | `<data layer>/<feature>/Factories/<Variant><Name>Factory.<ext>` |
| AbstractProduct | Declares the interface for one product type in the family | `<domain layer>/<feature>/I<Product>.<ext>` |
| ConcreteProduct | One variant's implementation of a product; only its own factory creates it | `<data layer>/<feature>/<Variant><Product>.<ext>` |
| Client | Uses only AbstractFactory and AbstractProduct interfaces | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test — factory | Asserts each concrete factory yields a coherent product family | `<test tree>/<feature>/Factories/<Variant><Name>FactoryTests.<ext>` |
| Test — product | Verifies each concrete product against its abstract contract | `<test tree>/<feature>/<Variant><Product>Tests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──uses──▶ «interface» AbstractFactory ──creates──▶ «interface» AbstractProduct
                            △                                        △
              ┌─────────────┴─────────────┐              ┌───────────┴───────────┐
      ConcreteFactoryA           ConcreteFactoryB    ProductA1/A2          ProductB1/B2
```

**Collaborations:** normally one ConcreteFactory instance is created at run-time and passed to clients; it creates products having a particular implementation. Clients ask the factory, never the product classes.

## Dependencies

- AbstractFactory and AbstractProduct interfaces: domain types only — no framework imports.
- ConcreteFactory: the concrete products it builds, plus any config needed to construct them.
- ConcreteProduct: may depend on SDKs, clients, and platform APIs — it lives at the data/infrastructure layer.
- Client: the two abstractions only. It must never name a concrete factory or product.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// AbstractProduct: I<Product> — one interface per product type in the family.
// AbstractFactory: I<Name>Factory — one create<Product>() method per product type,
//   each returning the AbstractProduct interface, never a concrete type.
// ConcreteFactory: <Variant><Name>Factory implements I<Name>Factory; every method
//   returns that variant's product. Usually stateless; often registered as a singleton.
// ConcreteProduct: <Variant><Product> implements I<Product>.
// Client: receives I<Name>Factory via constructor injection and calls create<Product>().
```

## Wiring

Register the AbstractFactory→ConcreteFactory binding once in the DI container (per `.omp/agent-config.md` § Pattern Compliance), selecting the variant from configuration or platform detection at composition root. Clients receive the factory interface by constructor injection. Do **not** register concrete products individually — only the factory creates them; that is what keeps a family from being mixed.

## Conventions

- Every factory method returns an **abstract** product type. A concrete return type defeats the pattern.
- One ConcreteFactory per family variant; a factory never returns another variant's product.
- Concrete factories are stateless and safe to share as a single instance.
- The variant decision is made once, at the composition root — never re-derived inside clients or products.
- Adding a **variant** means adding one ConcreteFactory plus its products, and touching nothing else. Adding a **product type** means changing the AbstractFactory and every ConcreteFactory — accept this cost knowingly (see Consequences).
- No framework imports in the abstractions or the client.

## Tests

- For each ConcreteFactory, assert every create method returns that variant's product type — this is the family-coherence test.
- Test each ConcreteProduct independently against its AbstractProduct contract.
- Test the client against a fake factory returning stub products; assert it never references a concrete type.
- Add a test that fails if a new product type is added to the AbstractFactory without an implementation in every ConcreteFactory.

## Consequences

1. **Isolates concrete classes.** Clients manipulate instances through abstract interfaces; product class names stay out of client code entirely.
2. **Makes exchanging product families easy.** The concrete factory appears once, so swapping the whole family is a one-line configuration change.
3. **Promotes consistency among products.** When products from a family are designed to work together, the pattern makes using a mixed set difficult by construction.
4. **Cost: supporting new kinds of products is hard.** The AbstractFactory fixes the set of products it can create. Adding a product type means editing the abstraction and every concrete factory — a change that ripples across the whole hierarchy.
