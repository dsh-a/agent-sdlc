# Observer Pattern

> **Type**: template

## When to use

Scaffold an observer when the task requires a publish-subscribe mechanism — reacting to state changes, domain events, lifecycle hooks, or decoupling producers from consumers. Common in event-driven architectures, notification systems, and reactive state management.

## File locations

| File | Path |
|---|---|
| Event / subject interface | `src/domain/events/event-emitter.interface.ts` (shared, create once) |
| Event definition | `src/domain/<feature>/events/<name>.event.ts` |
| Handler / listener | `src/domain/<feature>/events/<name>.handler.ts` |
| Test | `test/domain/<feature>/events/<name>.handler.test.ts` |

Adapt paths to the project's existing directory structure.

## Dependencies

- Event: none (pure data object)
- Handler: repositories, services, or other dependencies needed to react to the event
- Event emitter/bus: shared infrastructure

## Template

```typescript
// --- Shared event interface (create once) ---

export interface IDomainEvent {
  readonly type: string;
  readonly occurredAt: Date;
}

export interface IEventHandler<TEvent extends IDomainEvent> {
  handle(event: TEvent): Promise<void>;
}

// --- Specific event ---

export class <Name>Event implements IDomainEvent {
  readonly type = '<feature>.<name>';
  readonly occurredAt = new Date();

  constructor(
    public readonly entityId: string,
    // event payload — what happened
  ) {}
}

// --- Handler / listener ---

export class On<Name>Handler implements IEventHandler<<Name>Event> {
  constructor(
    private readonly someService: ISomeService,
  ) {}

  async handle(event: <Name>Event): Promise<void> {
    // react to the event
  }
}
```

## Wiring

Register event-handler mappings in the event bus/dispatcher or DI container. If using Node.js EventEmitter, typed-emitter, or a library like `eventemitter2`, adapt the registration pattern accordingly.

## Conventions

- Events are immutable data objects describing something that already happened (past tense: `UserCreated`, `OrderShipped`)
- Handlers are independent — one handler failing should not block others
- Events flow one direction: producer → bus → handlers. Handlers never call back to the producer.
- Keep event payloads minimal — include IDs and essential data, not full entity snapshots

## Tests

- Test each handler independently with a constructed event
- Verify side effects (service calls, state changes)
- Test error isolation (handler failure doesn't propagate)
- Test with realistic event payloads
