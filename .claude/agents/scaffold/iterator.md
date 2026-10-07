# Iterator Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: iterator, cursor, traverse without exposing representation, sequential access, custom traversal
> **Aliases**: Cursor
> **Related**: composite, factory-method, memento, visitor

## Intent

Provide a way to access the elements of an aggregate object sequentially without exposing its underlying representation.

## When to use

> **Use the language's own iteration protocol first.** Every language this pipeline targets ships one — Dart `Iterable`/`Iterator` and `sync*`, C# `IEnumerable`/`yield return`, Python `__iter__`, JS `Symbol.iterator`. Implementing the native protocol *is* applying this pattern, and it comes with the whole standard library's operators for free. Hand-rolling a bespoke iterator interface is almost always the wrong scaffold.

- You want to access an aggregate object's contents **without exposing its internal representation**.
- You need to support **multiple simultaneous traversals** of the same aggregate.
- You want a **uniform interface** for traversing different aggregate structures (polymorphic iteration).
- The traversal itself is non-trivial and worth naming: depth-first vs breadth-first over a `composite.md` tree, paged remote fetches, filtered or windowed views.

**Not when:**
- A native collection already does it. Return `Iterable`/`IEnumerable`; do not wrap it. `minimalism` forbids the ceremony.
- The caller needs random access or the count up front — expose a list.
- You want to perform an **operation** on every element of a structure rather than expose the sequence → `visitor.md`.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Iterator | Declares the traversal interface (advance, current, done) | the language's built-in iterator type |
| ConcreteIterator | Implements traversal and keeps the current position in the aggregate | `<domain layer>/<feature>/Iterators/<Traversal><Name>Iterator.<ext>` |
| Aggregate | Declares the operation that creates an iterator | `<domain layer>/<feature>/I<Name>Collection.<ext>` |
| ConcreteAggregate | Returns an iterator over its own representation | `<domain layer>/<feature>/<Name>Collection.<ext>` |
| Client | Consumes elements through the iterator, never through the representation | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test | Verifies ordering, boundaries, independence, and invalidation | `<test tree>/<feature>/Iterators/<Traversal><Name>IteratorTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──▶ «interface» Aggregate          «interface» Iterator
                 + createIterator() ──────▶  + moveNext() / current
                        △                            △
             ConcreteAggregate ──creates──▶ ConcreteIterator
                                             - position into aggregate
```

**Collaborations:** a ConcreteIterator keeps track of the current object in the aggregate and can compute the succeeding object in the traversal. The aggregate creates it, so the iterator may rely on the aggregate's internals without exposing them to the client.

## Dependencies

- Aggregate interface and iterators: domain types only — no framework imports.
- ConcreteIterator: privileged access to the ConcreteAggregate's representation, and nothing else.
- Client: the Aggregate interface and the language's iteration construct.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// PREFERRED — implement the language's native protocol:
//   <Name>Collection exposes the built-in iterable type; traversal written with the
//   language's generator construct (sync* / yield return / yield) so laziness,
//   composition, and the standard operators come free.
//
// NAMED TRAVERSALS — when more than one order is meaningful:
//   Expose one method per traversal (depthFirst(), breadthFirst(), leavesOnly()),
//   each returning an independent lazy sequence. Do NOT put a mode flag on one method.
//
// EXTERNAL ITERATOR — only when the client must control stepping (merge, lookahead):
//   <Traversal><Name>Iterator with moveNext()/current, position held in the iterator,
//   never in the aggregate.
```

## Wiring

Aggregates are returned by repositories and services, not registered as DI bindings; the iterator is created by the aggregate on demand. Register only the component that produces the aggregate (per `.omp/agent-config.md` § Pattern Compliance). If a traversal needs an injected dependency — a paged remote fetch, for instance — inject it into the **aggregate**, and let the iterator borrow it, so the iterator stays a pure cursor.

## Conventions

- Position lives in the **iterator**, never in the aggregate. An aggregate holding a cursor cannot support two traversals at once, which forfeits the pattern's main benefit.
- Each call to the create-iterator operation returns a **fresh, independent** iterator.
- Iterators are read-only with respect to the aggregate. Traversal never mutates what it traverses.
- Define and document the behaviour when the aggregate changes mid-traversal: either snapshot at creation, or fail fast on modification. Silent skipping or duplication is the classic bug.
- Prefer lazy sequences so a client can stop early without paying for the remainder.
- Name traversals for their order rather than exposing a mode parameter.
- No framework imports in domain aggregates or iterators.

## Tests

- Test the empty aggregate — the traversal yields nothing and does not fail.
- Test single-element and many-element cases, asserting exact order.
- Test that two iterators over the same aggregate advance **independently**.
- Test early termination: stopping after N elements does not compute the rest (this is the test that proves laziness).
- Test the documented mid-traversal modification behaviour explicitly.
- For a tree aggregate, test each named traversal order separately against a known-shaped tree.
- Test that exhausting the iterator past its end fails or reports done as documented, rather than wrapping around.

## Consequences

1. **Supports variations in the traversal of an aggregate.** Complex aggregates may be traversed in many ways; changing the traversal algorithm means replacing the iterator instance, not editing the aggregate. New traversals arrive as new iterator subclasses.
2. **Simplifies the Aggregate interface.** The traversal interface removes the need for a corresponding one on the aggregate, keeping the aggregate focused on holding elements.
3. **More than one traversal can be pending on an aggregate.** Each iterator holds its own traversal state, so several traversals — even of different kinds — can run at once.
4. **Cost: an extra object and a lifetime question.** Iterators can outlive or be invalidated by the aggregate they traverse, and getting the invalidation contract wrong produces failures that appear only under concurrent modification.
