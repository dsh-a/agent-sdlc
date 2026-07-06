# Observer Pattern

> **Type**: template

## When to use

Scaffold an observer when the task requires a publish-subscribe mechanism — reacting to state changes, domain events, lifecycle hooks, or decoupling producers from consumers. Typically expressed via the language's event/stream primitives or a domain event bus.

## File locations

| File | Path |
|---|---|
| Event base abstraction | `<domain layer>/Events/DomainEvent.<ext>` (shared, create once) |
| Event definition | `<domain layer>/<feature>/Events/<Name>Event.<ext>` |
| Handler / listener | `<domain layer>/<feature>/Events/<Name>Handler.<ext>` |
| Test | `<test tree>/<feature>/Events/<Name>HandlerTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

## Dependencies

- Event: none (immutable data object, no framework imports).
- Handler: repositories, services, or other dependencies injected via constructor.
- Event bus / stream: shared infrastructure (the language's event primitive or a custom bus).

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Shared (create once): a DomainEvent base (carries an occurred-at timestamp) +
//   a DomainEventHandler<TEvent> abstraction with a single handle(event) method.
// Specific event: an immutable data object describing what happened (payload).
// Handler: implements the handler abstraction; dependencies injected; reacts to the event.
// Optional bus: a publisher exposing a stream/event of the type + a subscriber that
//   registers a listener and disposes it on teardown.
```

## Wiring

Register event-handler mappings in the DI container or event-bus dispatcher (per `.omp/agent-config.md` § Pattern Compliance). If using a stream/bus, expose it and inject it wherever events are published or consumed.

## Conventions

- Events are immutable — no methods.
- Event names describe something that already happened (past tense: `UserCreated`, `OrderCompleted`).
- Handlers are independent — one handler failing should not block others.
- Events flow one direction: producer → bus → handlers. Handlers never call back to the producer.
- No framework imports in domain events or handlers.
- Use the project logger, never raw console output.

## Tests

- Test each handler independently with a constructed event.
- Verify side effects (service calls, state changes).
- Test that handlers are independent (one failure doesn't affect others).
- Test event emissions using the framework's async/stream assertions.
