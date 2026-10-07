# Composite Pattern

> **Type**: template
> **Category**: structural
> **Triggers**: composite, part-whole hierarchy, tree structure, treat leaf and container uniformly, recursive composition
> **Related**: decorator, iterator, visitor, chain-of-responsibility, interpreter

## Intent

Compose objects into tree structures to represent part-whole hierarchies. Composite lets clients treat individual objects and compositions of objects uniformly.

## When to use

Scaffold a composite when the data is a **tree**, and the client should not have to ask whether it holds a leaf or a branch.

- You want to represent part-whole hierarchies of objects.
- You want clients to be able to **ignore the difference** between a composition of objects and an individual object — clients treat every object in the structure uniformly.
- Operations must recurse naturally over a nested structure: totalling, rendering, validating, searching.

**Not when:**
- The structure is a flat list or a fixed two-level shape. A collection is simpler and `minimalism` prefers it.
- Leaves and containers genuinely need different client handling — forcing a common interface then produces methods that throw on half the implementations.
- You want to add responsibilities to a single object rather than compose many → `decorator.md`.
- You only need to traverse an existing structure → `iterator.md`, or `visitor.md` to add operations to it.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Component | Declares the common interface; declares child-management operations where they are shared | `<domain layer>/Composites/I<Name>Component.<ext>` (shared, create once) |
| Leaf | A primitive with no children; implements the Component operations directly | `<domain layer>/<feature>/Composites/<Name>Leaf.<ext>` |
| Composite | Stores children and implements Component operations by delegating to them | `<domain layer>/<feature>/Composites/<Name>Composite.<ext>` |
| Client | Manipulates the structure through the Component interface only | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test — leaf | Verifies primitive behaviour and child-operation handling | `<test tree>/<feature>/Composites/<Name>LeafTests.<ext>` |
| Test — composite | Verifies recursion, ordering, and empty/nested cases | `<test tree>/<feature>/Composites/<Name>CompositeTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──▶ «interface» Component
                 + operation()
                 + add/remove/getChild()
                        △
            ┌───────────┴───────────┐
          Leaf                  Composite ──children──┐
     + operation()          + operation()  ◀──────────┘
                            (forwards to each child)
```

**Collaborations:** clients use the Component interface to interact with objects. If the recipient is a Leaf, the request is handled directly; if it is a Composite, it forwards to its children, possibly performing work before or after forwarding.

## Dependencies

- Component interface: domain types only — no framework imports.
- Leaf: whatever the primitive operation needs; keep it small.
- Composite: the Component interface for its children — never a concrete Leaf or Composite type.
- Client: the Component interface only.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Component (create once): I<Name>Component declaring the business operation(s).
//   Decide ONE child-management policy and apply it everywhere (see Conventions):
//   either declare add/remove/children on Component, or only on Composite.
// Leaf: <Name>Leaf implements the operation directly; has no children.
// Composite: <Name>Composite holds an ordered collection of I<Name>Component and
//   implements the operation by folding over its children. Owns add/remove/children.
// Client: recurses through I<Name>Component with no type checks.
```

## Wiring

Composites are usually **built**, not injected — assembled by a factory, a parser, or a builder at the point the tree is known. Register that assembler in the DI container (per `.omp/agent-config.md` § Pattern Compliance) rather than registering individual nodes. Where leaves need injected services, have the assembler pass them in at construction so nodes stay free of service-locator lookups.

## Conventions

- Pick one child-management policy and hold it. **Declaring `add`/`remove` on Component** maximises uniformity but forces Leaf to implement operations it cannot honour — make them fail with a domain error, never silently. **Declaring them only on Composite** keeps types honest but requires the client to distinguish. Prefer the latter unless uniform child access is the actual requirement.
- Child order is part of the contract if any operation depends on it — state it in the Component interface and test it.
- The Composite delegates; it does not special-case particular child types. A `if (child is Leaf)` in a Composite means the interface is wrong.
- Guard against cycles when the tree is built from external input — a parent added beneath itself makes every recursive operation hang.
- Keep the recursion depth in mind: for deep or untrusted trees prefer an explicit stack over recursion.
- No framework imports in the Component, Leaf, or Composite.

## Tests

- Test a Leaf standalone.
- Test a Composite with zero children — the empty case is where fold identities are wrong.
- Test a Composite with one level of children, then a nested Composite, asserting the operation recurses to full depth.
- Assert child order is preserved when the operation is order-dependent.
- Test the client against a mixed tree with no type checks, proving uniform treatment.
- If child operations live on Component, test that a Leaf rejects `add` with a domain error.

## Consequences

1. **Defines class hierarchies of primitive and composite objects.** Primitives can be composed into more complex objects, which in turn can be composed — recursively, wherever client code expects a primitive.
2. **Makes the client simple.** Clients treat composite structures and individual objects uniformly, and normally cannot tell which they are handling. This removes the type-test-and-branch code that these structures otherwise attract.
3. **Makes it easier to add new kinds of components.** New Leaf or Composite subclasses work automatically with existing structures and client code — no client changes.
4. **Cost: your design can become overly general.** Making every component uniform means you **cannot rely on the type system** to restrict what goes into a composite; you must use run-time checks where only certain children are legal. That trade is the price of the uniformity in point 2.
