# Observer Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: observer, publish subscribe, pub/sub, domain event, listener, notify dependents, event bus, stream
> **Aliases**: Dependents, Publish-Subscribe
> **Related**: mediator, singleton, command

## Intent

Define a one-to-many dependency between objects so that when one object changes state, all its dependents are notified and updated automatically.

## When to use

Scaffold an observer when something happens in one place and an **open-ended set of others** must react, without the source knowing who they are. Typically expressed via the language's event/stream primitives or a domain event bus.

- An abstraction has two aspects, one dependent on the other. Encapsulating them separately lets you vary and reuse them independently.
- A change to one object requires changing others, and **you do not know how many** others there are.
- An object should be able to notify others without making assumptions about who they are — the notifier and its listeners should be loosely coupled.

**Not when:**
- Peers must coordinate bidirectionally → `mediator.md`. Observer broadcasts one way; a mediator routes between colleagues.
- Exactly one known consumer reacts. Call it directly; `minimalism` forbids a bus for a pair.
- The reaction must be guaranteed, ordered, and transactional with the source. Observers are fire-and-forget by nature; use an explicit orchestration or an outbox.
- The consumer needs a result back. Notification is not a request/response channel.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Event (Subject payload) | An immutable description of what happened | `<domain layer>/<feature>/Events/<Name>Event.<ext>` |
| Event base | Shared abstraction carrying the occurred-at timestamp | `<domain layer>/Events/DomainEvent.<ext>` (shared, create once) |
| Subject / publisher | Knows its observers and provides attach/detach; issues notifications | `<domain layer>/<feature>/<Feature>Service.<ext>` or the shared bus |
| Observer (handler) | Defines the updating interface for objects notified of a change | `<domain layer>/<feature>/Events/<Name>Handler.<ext>` |
| Event bus | Shared infrastructure routing events to registered handlers | `<domain layer>/Events/<Name>EventBus.<ext>` |
| Test — handler | Verifies each handler's reaction to a constructed event | `<test tree>/<feature>/Events/<Name>HandlerTests.<ext>` |
| Test — publication | Verifies the event is emitted with the right payload | `<test tree>/<feature>/Events/<Name>PublicationTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Subject                          Observers
  + attach(o) / detach(o)      ┌──▶ HandlerA.handle(event)
  + notify() ──────event──────▶┼──▶ HandlerB.handle(event)
  (state changed)              └──▶ HandlerC.handle(event)
```

**Collaborations:** the subject notifies its observers whenever a change occurs that could make their state inconsistent with its own. Each observer queries the subject — or reads the event payload — to reconcile its state. The subject knows nothing about its observers beyond the interface.

## Dependencies

- Event: none — an immutable data object with no framework imports.
- Handler: repositories, services, or other dependencies injected via constructor.
- Event bus / stream: shared infrastructure (the language's event primitive or a custom bus).

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Shared (create once): a DomainEvent base (carries an occurred-at timestamp) +
//   a DomainEventHandler<TEvent> abstraction with a single handle(event) method.
// Event: <Name>Event — an immutable data object describing what happened (payload).
//   Named in the PAST TENSE; carries everything a handler needs so it need not call back.
// Handler: <Name>Handler implements the handler abstraction; dependencies injected;
//   reacts to the event. Failures are caught and logged, never allowed to break peers.
// Bus (optional): a publisher exposing a stream/event of the type + a subscriber that
//   registers a listener and DISPOSES it on teardown.
```

## Wiring

Register event-handler mappings in the DI container or event-bus dispatcher (per `.omp/agent-config.md` § Pattern Compliance). If using a stream/bus, expose it and inject it wherever events are published or consumed. Subscriptions created outside the container's lifetime — in a view model, a controller, a widget — must be disposed on teardown; an undisposed subscription is a leak and a source of updates delivered to dead objects.

## Conventions

- Events are immutable — no methods, no behaviour.
- Event names describe something that **already happened** (past tense: `UserCreated`, `OrderCompleted`). A present-tense name is a command in disguise.
- The event payload is self-sufficient: a handler should not need to call back into the publisher to do its job.
- Handlers are independent — one handler failing must not block the others. Catch and log per handler.
- Events flow one direction: producer → bus → handlers. Handlers never call back to the producer.
- Handler order is **not** a contract. If two handlers must run in sequence, that is orchestration, not events.
- Every subscription has a matching disposal, tied to the subscriber's lifecycle.
- Beware cascades: a handler that publishes another event can loop. Bound the depth or forbid re-publication.
- No framework imports in domain events or handlers. Use the project logger, never raw console output.

## Tests

- Test each handler independently with a constructed event.
- Verify side effects — service calls made, state changed, with the expected arguments.
- Test that handlers are independent: make one throw and assert the others still run.
- Test event emissions using the framework's async/stream assertions — assert the payload, not just that something fired.
- Test subscription disposal: after teardown, a published event reaches no handler.
- Test that a handler publishing a further event terminates rather than cascading.

## Consequences

1. **Abstract coupling between subject and observer.** The subject knows only that it has a list of observers conforming to a simple interface; it knows none of their concrete classes. Subject and observers can therefore live in different layers and be reused apart.
2. **Support for broadcast communication.** Unlike an ordinary request, the notification need not specify a receiver — it goes to every interested party, and observers can be added and removed at any time. The subject pays no cost per observer beyond the send.
3. **Cost: unexpected updates.** Because observers have no knowledge of one another, they are blind to the cost of changing the subject: a seemingly innocuous operation can cascade through observers and their dependents, and the criteria for those updates are not captured anywhere. This is the pattern's hardest failure mode to debug, and the reason for the cascade and independence rules above.
