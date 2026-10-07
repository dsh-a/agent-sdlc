# Command Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: command, action, transaction, handler, CQRS, undo redo, queue request, dispatcher
> **Aliases**: Action, Transaction
> **Related**: composite, memento, prototype, chain-of-responsibility

## Intent

Encapsulate a request as an object, thereby letting you parameterize clients with different requests, queue or log requests, and support undoable operations.

## When to use

Scaffold a command when a request must become a **value you can hold** — to queue it, log it, retry it, undo it, or dispatch it without the caller knowing who executes it. Common in CQRS-style architectures, task dispatchers, and action-based systems.

- You want to parameterize objects by an action to perform — the request is data, chosen at run-time.
- You want to specify, queue, and execute requests at **different times**; the command's lifetime is independent of the original request.
- You need to support **undo**: the command stores the state required to reverse its effects, and executed commands are kept on a history stack.
- You need to log changes so they can be reapplied after a crash — commands are serialisable, so the log can be replayed.
- You want to structure a system around high-level operations built on primitive ones, as transactions do.

**Not when:**
- The caller knows the receiver and the call happens immediately, once. Call the method; `minimalism` forbids the wrapper.
- You need the request to try several possible handlers → `chain-of-responsibility.md`.
- You are swapping an algorithm behind a stable call → `strategy.md`.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Command | Declares the interface for executing an operation | `<domain layer>/Commands/Command.<ext>` (shared, create once) |
| ConcreteCommand | An immutable request object carrying the parameters of one operation | `<domain layer>/<feature>/Commands/<Name>Command.<ext>` |
| Handler (Receiver) | Knows how to carry the request out; holds the dependencies and the logic | `<domain layer>/<feature>/Commands/<Name>Handler.<ext>` |
| Invoker | Asks the command to be carried out; owns queueing, history, and logging | `<domain layer>/Commands/<Name>Dispatcher.<ext>` |
| Client | Creates a ConcreteCommand and submits it to the invoker | UI / presentation layer, other features |
| Test — handler | Verifies validation, side effects, and error cases | `<test tree>/<feature>/Commands/<Name>HandlerTests.<ext>` |
| Test — dispatcher | Verifies routing, queueing, and undo history if present | `<test tree>/Commands/<Name>DispatcherTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──creates──▶ ConcreteCommand (immutable data)
                             │
  Invoker ──submits──────────┘──routed to──▶ Handler ──▶ Receiver work
   (queue, log, undo stack)                   (dependencies injected)
```

**Collaborations:** the client creates a ConcreteCommand and specifies its parameters; the invoker stores it and issues the request; the handler carries it out against its dependencies. For undo, the invoker keeps executed commands and reverses them in order.

## Dependencies

- Command: none — an immutable data object with no framework imports and no dependencies.
- Handler: repositories, services, and the project logger, injected via constructor.
- Invoker/dispatcher: the handler registry and, where undo is supported, the history store.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Shared (create once): a Command marker abstraction + a CommandHandler<TCommand, TResult>
//   abstraction with a single execute/handle method.
// ConcreteCommand: <Name>Command — an immutable data object carrying request parameters.
//   No methods, no dependencies, no behaviour.
// Handler: <Name>Handler implements the handler abstraction; dependencies injected via
//   constructor; uses the project logger; validates -> executes -> returns a result.
// Invoker (optional): routes a command to its handler; add queueing/logging here.
// Undo (only if required): the handler returns, or the command carries, the inverse
//   state needed to reverse the operation — see memento.md for capturing that state.
```

## Wiring

Register each handler against its command type in the DI container (per `.omp/agent-config.md` § Pattern Compliance). Invokers submit commands without knowing which handler processes them. Where a dispatcher resolves handlers by command type, register the mapping at the composition root and fail loudly at startup on a command with no handler — a missing registration must not become a run-time no-op.

## Conventions

- Commands are immutable data objects — no methods, no dependencies, no behaviour.
- One handler per command (Single Responsibility). Two commands sharing a handler means one of them is misnamed.
- Handlers contain the execution logic and the dependencies; use the project logger, never raw console output.
- Command names are descriptive verb phrases (`CreateOrderCommand`, `DeleteAccountCommand`); handlers take the command's name plus `Handler`.
- Commands are serialisable if they are queued or logged — keep primitives and domain value types in them, never services or closures.
- Undo support is explicit: either every command in a history is undoable or none is. A partially-undoable stack corrupts state on rollback.
- No framework imports in the domain layer.

## Tests

- Test the handler, not the command (commands are pure data).
- Test validation logic within the handler.
- Test side effects — repository calls made, events emitted, with the expected arguments.
- Test error cases: invalid input produces a domain error; a failing dependency surfaces correctly.
- If a dispatcher exists, test that each command type routes to its registered handler, and that an unregistered command fails loudly.
- If undo is supported, test execute-then-undo restores the prior state, and test undo ordering across a multi-command history.

## Consequences

1. **Decouples the object that invokes the operation from the one that knows how to perform it.** The invoker needs to know only the command interface, so senders and receivers evolve independently.
2. **Commands are first-class objects.** They can be manipulated, stored, passed, queued, logged, and extended like any other object — which is what makes queueing, retry, and crash-recovery replay possible at all.
3. **Commands can be assembled into a composite command.** A macro-command is a `composite.md` of commands, built with no new machinery.
4. **Adding new commands is easy.** No existing class changes, because the invoker depends only on the abstraction — new behaviour arrives as a new command plus a new handler.
5. **Cost: a class pair per operation.** Every request becomes two types and a registration. In a system with few, direct operations this is pure overhead, which is why the *Not when* list above matters.
