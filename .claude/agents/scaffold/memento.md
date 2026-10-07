# Memento Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: memento, snapshot, undo, rollback, checkpoint, save restore state, token
> **Aliases**: Token
> **Related**: command, iterator, prototype

## Intent

Without violating encapsulation, capture and externalise an object's internal state so that the object can be restored to this state later.

## When to use

Scaffold a memento when state must be **saved now and restored later**, and exposing that state publicly to save it would break the object's encapsulation.

- A snapshot of an object's state must be saved so that it can be restored later — undo, rollback of a failed transaction, a checkpoint before a risky operation, a draft the user can revert.
- A direct interface to obtaining the state would **expose implementation details** and break encapsulation.

**Not when:**
- The object is an immutable value. Keep a reference to the old value; that *is* the snapshot, and `minimalism` forbids the machinery.
- The state is already public and safe to read. A plain copy is simpler.
- You need to reverse an *operation* rather than restore a *state* → `command.md` with an inverse, which is cheaper when operations are small and state is large.
- Snapshots would be large or frequent enough to be a memory problem, and no incremental scheme is planned.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Memento | Stores the originator's internal state; exposes a wide interface to the originator and a narrow one to everyone else | `<domain layer>/<feature>/Mementos/<Name>Memento.<ext>` |
| Originator | Creates a memento of its current state and restores itself from one | `<domain layer>/<feature>/<Name>.<ext>` |
| Caretaker | Keeps mementos safe; never inspects or operates on their contents | `<domain layer>/<feature>/Mementos/<Name>History.<ext>` |
| Test — round trip | Verifies save/mutate/restore returns the originator to its prior state | `<test tree>/<feature>/Mementos/<Name>MementoTests.<ext>` |
| Test — caretaker | Verifies history ordering, depth limits, and opacity | `<test tree>/<feature>/Mementos/<Name>HistoryTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Originator                Caretaker             Memento
  + createMemento() ─────▶  [ m1, m2, m3 ]  ──▶  - state (opaque to Caretaker)
  + restore(m) ◀────────────────┘                 (full access to Originator only)
```

**Collaborations:** a caretaker requests a memento from the originator, holds it for a time, and passes it back to the originator to restore. Caretakers never operate on or examine the mementos they hold — they are **opaque** to everyone but the originator.

## Dependencies

- Memento: domain types only. It is inert data — no services, no framework imports, no behaviour.
- Originator: whatever it already needs. The memento adds no dependency.
- Caretaker: the memento type as an opaque handle, and a history structure.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Memento: <Name>Memento — immutable, holds a COMPLETE copy of the originator's
//   restorable state. Use the language's narrowest visibility (package-private,
//   internal, nested private class) so only the originator can read the contents.
// Originator: <Name> gains createMemento() -> <Name>Memento and
//   restore(<Name>Memento). restore() replaces state wholesale; it does not merge.
// Caretaker: <Name>History — a bounded stack of mementos with save()/undo()
//   (and redo() if required). It treats each memento as an opaque token.
```

## Wiring

Register the caretaker/history in the DI container scoped to the thing it undoes — per editor, per document, per session (per `.omp/agent-config.md` § Pattern Compliance) — never as an application-wide singleton, or one user's undo stack will restore another's state. Mementos are created and passed, never injected. Bound the history depth at registration and state that bound where it is configured.

## Conventions

- The memento is **immutable** and holds a complete copy of the restorable state. A memento sharing a mutable reference with the originator restores nothing.
- Only the originator reads a memento's contents. Enforce it with the language's visibility rules, not by convention alone — a caretaker that can read state has voided the pattern's reason for existing.
- `restore` replaces state wholesale. A partial restore leaves the originator in a state that never existed.
- Every field added to the originator's restorable state must be added to the memento; this is the drift that silently breaks undo.
- The history is bounded, and its eviction policy is documented.
- If a memento must be persisted, it is serialisable — keep primitives and value types in it.
- No framework imports in the memento or the originator.

## Tests

- Round trip: snapshot, mutate every restorable field, restore, and assert the originator matches its original state field for field. This is the test that catches a new field missing from the memento.
- Assert mutating the originator after taking a memento does **not** change the memento.
- Assert the caretaker cannot read the memento's state — ideally a compile-level guarantee, so assert it by the memento's API surface.
- Test multi-step undo ordering, and redo if supported.
- Test the history bound: exceeding it evicts as documented rather than growing without limit.
- Test restoring an out-of-order or stale memento behaves as documented.

## Consequences

1. **Preserves encapsulation boundaries.** Mementos avoid exposing information that only the originator should manage but that must nonetheless be stored outside it — the entire reason to prefer this over a public state accessor.
2. **It simplifies the originator.** In other designs the originator keeps the versions of internal state that clients have requested; this puts the storage burden on the caretaker instead, letting the originator stay focused on its own behaviour.
3. **Cost: using mementos might be expensive.** If the originator must copy large amounts of state, or if snapshots are taken often, the pattern's overhead may be prohibitive — it is only practical when encapsulating and restoring state is cheap relative to its value.
4. **Cost: defining narrow and wide interfaces.** Keeping the memento readable to the originator and opaque to everyone else is awkward in languages without fine-grained visibility, and a half-enforced boundary gives the cost without the benefit.
5. **Cost: hidden costs in caring for mementos.** The caretaker is responsible for deleting mementos it holds but has no idea how much state is in one — a lightweight caretaker can incur large storage costs without any visible signal.
