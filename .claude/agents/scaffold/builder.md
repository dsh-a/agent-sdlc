# Builder Pattern

> **Type**: template
> **Category**: creational
> **Triggers**: builder, fluent construction, step-by-step assembly, telescoping constructor, complex object assembly
> **Related**: abstract-factory, composite, prototype

## Intent

Separate the construction of a complex object from its representation, so that the same construction process can create different representations.

## When to use

Scaffold a builder when assembling an object takes **multiple ordered steps** and the same steps should be able to produce different outputs — a document rendered as HTML or PDF, a query emitted as SQL or a filter tree, a report in several formats.

- The algorithm for creating a complex object should be independent of the parts and how they are assembled.
- The construction process must allow **different representations** of the object being built.
- Construction requires validation or accumulation across steps that a constructor cannot express.

**Not when:**
- The object is a plain data bag with a handful of fields. A constructor is the answer.
- The language has named/optional constructor arguments (Dart, Kotlin, Python, C#) and the only complaint is a long parameter list — named args already solve that. **In the default Flutter pack this rules out most builder proposals.**
- You need copies of an existing configured instance → `copyWith` or `prototype.md`.
- There is exactly one representation and no assembly ordering → this is ceremony, and `minimalism` forbids it.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Builder | Declares one step operation per part of the product | `<domain layer>/<feature>/Builders/I<Name>Builder.<ext>` |
| ConcreteBuilder | Assembles one representation; tracks partial state; exposes the retrieval operation | `<domain layer>/<feature>/Builders/<Variant><Name>Builder.<ext>` |
| Director | Runs the step sequence against a Builder; owns the construction algorithm | `<domain layer>/<feature>/Builders/<Name>Director.<ext>` |
| Product | The assembled result; each ConcreteBuilder may produce a different type | `<domain layer>/<feature>/<Product>.<ext>` |
| Test — builder | Verifies each concrete builder's parts and its retrieval result | `<test tree>/<feature>/Builders/<Variant><Name>BuilderTests.<ext>` |
| Test — director | Verifies the step sequence against a fake builder | `<test tree>/<feature>/Builders/<Name>DirectorTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──▶ Director ──uses──▶ «interface» Builder
                                        △
                          ┌─────────────┴─────────────┐
                  ConcreteBuilderA            ConcreteBuilderB
                        │ builds                     │ builds
                     ProductA                     ProductB
```

**Collaborations:** the client creates a ConcreteBuilder and hands it to the Director; the Director calls step operations as parts are needed; the client retrieves the finished product **from the builder**, not from the Director.

## Dependencies

- Builder interface: domain types only — no framework imports.
- ConcreteBuilder: the product type it assembles, plus any formatter/serializer it needs.
- Director: the Builder interface only. It must not know any concrete builder or product type.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Builder: I<Name>Builder — one build<Part>(args) method per part, plus build()/result()
//   returning the finished product. Step methods return void or the builder (fluent).
// ConcreteBuilder: <Variant><Name>Builder implements I<Name>Builder; holds mutable
//   partial state; validates on retrieval; resets after handing the product over.
// Director: <Name>Director takes I<Name>Builder and exposes construct(input) that calls
//   the step methods in the required order. Holds no product state.
// Product: immutable once retrieved.
```

## Wiring

The Director is registered in the DI container and receives a Builder per call or per construction, not as a captured singleton — a builder carries mutable partial state and is **not** safe to share. Where the representation is chosen at run-time, inject a factory that returns a fresh ConcreteBuilder. Never register a ConcreteBuilder as a single shared instance.

## Conventions

- The Director owns the **order**; the ConcreteBuilder owns the **representation**. Neither takes the other's job.
- Builders are single-use or explicitly reset after retrieval — leaking state between products is the pattern's classic bug.
- The retrieval operation lives on the builder, not the Director, because different builders return different types.
- Step methods do not validate cross-part invariants; validate once at retrieval, where the object is whole.
- Products are immutable after retrieval.
- No framework imports in the Director or the Builder interface.

## Tests

- Test each ConcreteBuilder in isolation: call steps directly, retrieve, assert the representation.
- Test the Director against a fake builder that records calls — assert the **sequence** of steps, which is the Director's only responsibility.
- Test that a builder reused after retrieval does not leak parts from the previous product.
- Test retrieval-time validation: an incomplete build fails with a domain error rather than returning a half-built product.
- Test the same Director against two ConcreteBuilders to prove the construction process is representation-independent.

## Consequences

1. **Lets you vary a product's internal representation.** The Director works against an abstract interface, so a new representation means one new ConcreteBuilder and no change to construction logic.
2. **Isolates code for construction and representation.** Clients need know nothing about the classes defining the product's internal structure; those classes never appear in the Builder interface.
3. **Finer control over the construction process.** Unlike creational patterns that build the product in one shot, the builder constructs it step by step under the Director's control — so the product is only retrieved once complete.
4. **Cost: a builder per representation, and mutable intermediate state.** The pattern adds two types and a stateful object to what a constructor might have done. Only pay it when representations genuinely multiply.
