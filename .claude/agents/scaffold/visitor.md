# Visitor Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: visitor, double dispatch, operation over object structure, add operation without changing classes, traverse and act
> **Related**: composite, interpreter, iterator

## Intent

Represent an operation to be performed on the elements of an object structure. Visitor lets you define a new operation without changing the classes of the elements on which it operates.

## When to use

Scaffold a visitor when an object structure is **stable** but the set of operations over it keeps growing — and adding each operation as a method on every element class would scatter unrelated concerns across the hierarchy.

- An object structure contains many classes with differing interfaces, and you want to perform operations that depend on their concrete classes.
- Many distinct and unrelated operations need to be performed on the objects, and you want to avoid polluting their classes with all of them. Visitor keeps related operations together in one class and unrelated ones apart.
- The classes defining the object structure **rarely change**, but you often want to define new operations over it. Changing the structure's classes requires redefining the interface to all visitors — costly. If the classes change often, put the operations in those classes instead.
- Natural fits: an `interpreter.md` expression tree gaining pretty-print, type-check, and optimise passes; a `composite.md` document tree gaining export, validate, and word-count.

**Not when:**
- New element types are added frequently. Every new element forces a change to the visitor interface and to **every** visitor — this is the pattern's defining weakness.
- There is one operation. Put it on the elements; `minimalism` forbids the double-dispatch machinery.
- The operation needs no knowledge of the concrete element type → `iterator.md` and a plain function.
- The language offers exhaustive pattern matching over a closed type hierarchy. That achieves the same result with far less ceremony — prefer it where available.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Visitor | Declares one visit operation per ConcreteElement class | `<domain layer>/<feature>/Visitors/I<Name>Visitor.<ext>` |
| ConcreteVisitor | Implements one operation over the whole structure; accumulates its own state | `<domain layer>/<feature>/Visitors/<Operation><Name>Visitor.<ext>` |
| Element | Declares the `accept` operation taking a visitor | `<domain layer>/<feature>/I<Name>Element.<ext>` |
| ConcreteElement | Implements `accept` by calling the visit method matching its own type | `<domain layer>/<feature>/<Name>Element.<ext>` |
| ObjectStructure | Enumerates its elements and offers a high-level entry point for visiting them | `<domain layer>/<feature>/<Name>Structure.<ext>` |
| Test — visitor | Verifies each operation over a known-shaped structure | `<test tree>/<feature>/Visitors/<Operation><Name>VisitorTests.<ext>` |
| Test — dispatch | Verifies each element routes to its own visit method | `<test tree>/<feature>/<Name>ElementDispatchTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  ObjectStructure ──▶ Element.accept(visitor)
                            │  (1st dispatch: which element)
                            ▼
                     visitor.visitConcreteElementA(this)
                            │  (2nd dispatch: which visitor)
                            ▼
                     ConcreteVisitor does the work
```

**Collaborations:** a client creates a ConcreteVisitor and traverses the object structure, visiting each element. When an element is visited it calls the visitor operation corresponding to its own class, passing itself as an argument — this **double dispatch** is what lets the operation depend on both the element's type and the visitor's.

## Dependencies

- Visitor interface and elements: domain types only — no framework imports.
- ConcreteVisitor: whatever its operation needs, injected via constructor; it also owns the state accumulated across the traversal.
- ObjectStructure: the Element interface.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Visitor: I<Name>Visitor<TResult> with one visit<Element>(<Element> e) method PER
//   concrete element type. Adding an element type here breaks every visitor at
//   COMPILE TIME — that is intended, and is the pattern's safety property.
// Element: I<Name>Element with accept(I<Name>Visitor<TResult> v) -> TResult.
// ConcreteElement: <Name>Element implements accept as `return v.visit<Name>(this);`
//   — exactly that one line, calling the method matching ITS OWN type.
// ConcreteVisitor: <Operation><Name>Visitor implements every visit method and holds
//   the accumulating result as its own state.
// Traversal: decide ONE owner — the object structure, the elements, or the visitor —
//   and apply it consistently (see Conventions).
```

## Wiring

Register each ConcreteVisitor in the DI container (per `.omp/agent-config.md` § Pattern Compliance) where its operation needs injected dependencies; otherwise construct it at the call site, since a visitor accumulating traversal state must **not** be shared. Register the ObjectStructure's producer, not the elements. A visitor that accumulates state is single-use — create a fresh one per traversal.

## Conventions

- `accept` is one line: call the visit method for this element's own type, pass `this`. Any logic in `accept` breaks the dispatch contract.
- Choose one traversal owner and hold it. Putting it in the **object structure** is the most common; putting it in the **visitor** gives the most control (needed when order depends on results); putting it in the **elements** couples traversal to structure. Document which you chose.
- One ConcreteVisitor per operation. A visitor doing two jobs forfeits the separation that justifies the pattern.
- Visitors accumulating state are single-use and never shared.
- Do not add a default or catch-all visit method — losing the compile error on a new element type discards the pattern's main safety property.
- Elements expose whatever the visitors need, which does weaken their encapsulation; keep that surface as narrow as the operations allow (see Consequences).
- No framework imports in elements or the visitor interface.

## Tests

- Test each ConcreteVisitor over a known-shaped structure and assert the accumulated result.
- Test dispatch: each ConcreteElement's `accept` calls its **own** visit method — a copy-paste error here silently routes to the wrong branch, and it is the single most common bug in this pattern.
- Test the empty structure and the single-element structure.
- Assert traversal order where the operation depends on it.
- Test that a visitor reused across two traversals either resets or is rejected.
- Add a compile-time check (or a review note) that a new element type forces every visitor to be updated.

## Consequences

1. **Makes adding new operations easy.** A new operation is a new visitor class; the element classes are untouched. Without the pattern the same operation would be spread across every element class.
2. **Gathers related operations and separates unrelated ones.** Related behaviour is not spread over the structure's classes — it is localised in one visitor — while unrelated behaviour is partitioned into separate visitors. Both the element classes and each operation's own algorithm get simpler.
3. **Visiting across class hierarchies.** Unlike an iterator, a visitor can visit objects that do not share a common parent class; the visitor interface can declare visit methods for any set of types.
4. **Accumulating state.** Visitors can accumulate state as they visit each element. Without one, that state would be passed as extra arguments through the traversal or held in global variables.
5. **Cost: adding new ConcreteElement classes is hard.** Each new element means a new abstract operation on the Visitor interface and a corresponding implementation in **every** ConcreteVisitor. This is the deciding trade-off: use Visitor when the **operations** change often and the **structure** rarely does — and reconsider entirely when it is the other way round.
6. **Cost: breaking encapsulation.** Visitor forces elements to expose enough of their internals for visitors to do their work, which can compromise their encapsulation.
