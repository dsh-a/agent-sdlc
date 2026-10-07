# State Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: state, state machine, objects for states, behaviour changes with state, status transitions, workflow states
> **Aliases**: Objects for States
> **Related**: strategy, flyweight, singleton

## Intent

Allow an object to alter its behaviour when its internal state changes. The object will appear to change its class.

## When to use

Scaffold a state when an object's behaviour **depends on its state**, and that dependence has already produced large conditionals repeated across several methods.

- An object's behaviour depends on its state, and it must change that behaviour at run-time depending on that state.
- Operations have **large, multipart conditional statements** that depend on the object's state — typically an enum or several flags, tested the same way in method after method. The State pattern puts each branch in a separate class.
- The valid transitions between states are themselves part of the domain and should be enforced, not just documented: order lifecycles, subscription statuses, upload/download progress, approval workflows.

**Not when:**
- One method branches on a status. An `if` or a switch is clearer, and `minimalism` prefers it.
- The variation is a swappable algorithm chosen by the client rather than a lifecycle the object moves through → `strategy.md`. The structures are near-identical; the difference is that **State objects change themselves over time and know their successors, while strategies are handed in and do not**.
- The states have no behaviour, only data. Then it is an enum with a transition table.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Context | Holds the current state and delegates state-dependent requests to it | `<domain layer>/<feature>/<Name>.<ext>` |
| State | Declares the interface for behaviour associated with a state of the context | `<domain layer>/<feature>/States/I<Name>State.<ext>` |
| ConcreteState | Implements behaviour for one state, and decides the transitions out of it | `<domain layer>/<feature>/States/<StateName><Name>State.<ext>` |
| Test — state | Verifies each state's behaviour and its legal and illegal transitions | `<test tree>/<feature>/States/<StateName><Name>StateTests.<ext>` |
| Test — machine | Verifies the lifecycle end to end and rejects illegal paths | `<test tree>/<feature>/<Name>StateMachineTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──▶ Context ──state──▶ «interface» State
             + request()              + handle(context)
               → state.handle(this)          △
                                ┌────────────┼────────────┐
                            DraftState  SubmittedState  ApprovedState
                                 └── transitions by setting context.state ──┘
```

**Collaborations:** the Context delegates state-specific requests to the current ConcreteState object. Either the Context or the ConcreteState subclasses can decide which state succeeds another, and under what conditions.

## Dependencies

- State interface and concrete states: domain types only — no framework imports.
- ConcreteState: the Context (passed in, not held as a field, when states are shared) plus whatever its own behaviour needs.
- Context: the State interface. It must not name a concrete state outside its initial state.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// State: I<Name>State declaring one method per state-dependent operation, each
//   taking the context: handle(<Name> context).
// ConcreteState: <StateName><Name>State implements the operations for that state.
//   Operations that are illegal in this state fail with a domain error — never
//   silently no-op. Transitions happen by setting the context's state.
// Context: <Name> holds I<Name>State, exposes the public operations, and delegates
//   each to the current state. Its transition method is restricted to the states.
// Stateless concrete states can be shared as single instances (see flyweight.md).
```

## Wiring

Register the Context's factory and the initial state in the DI container (per `.omp/agent-config.md` § Pattern Compliance). Where concrete states are **stateless**, register each as a single shared instance and pass the context in on every call — this avoids allocating a state object per transition. Where a state must carry data, create it per transition instead. Rehydrating a context from storage means mapping a persisted status value back to a state object; keep that mapping in one place beside the states.

## Conventions

- The Context delegates; it does not branch. A surviving `if (status == …)` in the context means the pattern is half-applied and worse than either alternative.
- Each ConcreteState decides its own legal transitions. Scattering the transition table across the context and the states is how these machines become unverifiable.
- An operation illegal in the current state fails with a domain error naming the state; a silent no-op turns an invalid transition into a data bug.
- Stateless states are shared; states carrying data are not. Never share a state that holds per-context data.
- Persisted status values map to exactly one state, and the mapping is exhaustive — an unknown stored value must fail loudly on load.
- Document the full state diagram beside the state classes; the classes *are* the machine and a reviewer needs the map.
- No framework imports in the domain layer.

## Tests

- Test each ConcreteState in isolation: for every operation, assert either the correct behaviour or the correct rejection.
- Assert every **illegal** transition from each state fails with a domain error — the negative cases are the ones that matter here.
- Test each legal transition lands in the expected successor state.
- Test the full lifecycle end to end along the happy path.
- Test rehydration: every persisted status maps to its state, and an unknown value fails loudly.
- If states are shared instances, assert two contexts in the same state do not affect one another.

## Consequences

1. **Localises state-specific behaviour and partitions behaviour for different states.** All behaviour for one state sits in one object, so adding a state means adding a class rather than editing every conditional. The pattern deliberately trades a monolithic conditional for more classes — less compact, but far easier to extend and to verify.
2. **Makes state transitions explicit.** When an object's state is an internal value, transitions have no visible representation; introducing separate objects makes each transition an assignment to one variable, and gives transitions a place to be enforced.
3. **State objects can be shared.** If states have no instance variables — all their state is in the context — they can be shared as flyweights, so the pattern's object cost largely disappears.
4. **Cost: more classes, and dispersed transition logic.** A machine with many states becomes many small files, and the transition rules live across them rather than in one readable table. Documenting the diagram beside the classes is what keeps this reviewable.
