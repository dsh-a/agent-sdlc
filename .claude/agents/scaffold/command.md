# Command Pattern

> **Type**: template

## When to use

Scaffold a command when the task requires encapsulating a request as an object — enabling queuing, logging, undo/redo, or decoupling the invoker from the executor. Common in CQRS-style architectures, task dispatchers, and action-based systems.

## File locations

| File | Path |
|---|---|
| Command base abstraction | `<domain layer>/Commands/Command.<ext>` (shared, create once) |
| Command | `<domain layer>/<feature>/Commands/<Name>Command.<ext>` |
| Handler | `<domain layer>/<feature>/Commands/<Name>Handler.<ext>` |
| Test | `<test tree>/<feature>/Commands/<Name>HandlerTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

## Dependencies

- Command: none (immutable data object, no framework imports).
- Handler: repositories, services, or other dependencies injected via constructor.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Shared (create once): a Command marker abstraction + a CommandHandler<TCommand, TResult>
//   abstraction with a single execute/handle method.
// Specific command: an immutable data object carrying the request parameters.
// Handler: implements the handler abstraction; dependencies injected via constructor;
//   uses the project logger; validates → executes → returns a result.
```

## Wiring

Register the handler in the DI container (per `.omp/agent-config.md` § Pattern Compliance). Invokers submit commands without knowing which handler processes them.

## Conventions

- Commands are immutable data objects — no methods, no dependencies.
- One handler per command (Single Responsibility).
- Handlers contain execution logic and dependencies; use the project logger, never raw console output.
- Command names are descriptive verb phrases (`CreateOrderCommand`, `DeleteAccountCommand`).
- No framework imports in the domain layer.

## Tests

- Test the handler, not the command (commands are pure data).
- Test validation logic within the handler.
- Test side effects (repository calls, events emitted).
- Test error cases (invalid input, dependency failures).
