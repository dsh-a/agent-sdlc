# Observer Pattern

> **Type**: template

## When to use

Scaffold an observer when the task requires a publish-subscribe mechanism — reacting to state changes, domain events, lifecycle hooks, or decoupling producers from consumers. In Dart, this is typically expressed via `Stream`s, `StreamController`s, or domain event buses.

## File locations

| File | Path |
|---|---|
| Event base class | `lib/domain/events/domain_event.dart` (shared, create once) |
| Event definition | `lib/domain/<feature>/events/<name>_event.dart` |
| Handler / listener | `lib/domain/<feature>/events/<name>_handler.dart` |
| Test | `test/domain/<feature>/events/<name>_handler_test.dart` |

Adapt paths to the project's existing directory structure.

## Dependencies

- Event: none (immutable data object, no Flutter imports)
- Handler: repositories, services, or other dependencies injected via constructor
- Event bus / stream: shared infrastructure (e.g., `StreamController`, a custom `EventBus` class)

## Template

```dart
// --- Shared domain event base class (create once) ---

abstract class DomainEvent {
  const DomainEvent({required this.occurredAt});

  final DateTime occurredAt;
}

abstract class DomainEventHandler<TEvent extends DomainEvent> {
  Future<void> handle(TEvent event);
}

// --- Specific event ---

class <Name>Event extends DomainEvent {
  const <Name>Event({
    required this.entityId,
    required super.occurredAt,
    // event payload — what happened
  });

  final String entityId;
}

// --- Handler / listener ---

class On<Name>Handler implements DomainEventHandler<<Name>Event> {
  On<Name>Handler({
    required ISomeService someService,
  }) : _someService = someService;

  final ISomeService _someService;
  final Logger _log = Logger('On<Name> Handler');

  @override
  Future<void> handle(<Name>Event event) async {
    // react to the event
  }
}

// --- Stream-based event bus (if project uses streams directly) ---

// Publisher side
final _controller = StreamController<<Name>Event>.broadcast();
Stream<<Name>Event> get <name>Events => _controller.stream;

void emit<Name>Event(<Name>Event event) => _controller.add(event);

// Subscriber side
late final StreamSubscription _sub;

void _init() {
  _sub = eventBus.<name>Events.listen(_onEvent);
}

Future<void> _onEvent(<Name>Event event) async {
  // handle event
}

@override
void dispose() {
  _sub.cancel();
  super.dispose();
}
```

## Wiring

Register event-handler mappings in the DI container or event bus dispatcher. If using a `StreamController`-based bus, expose the stream as a getter and inject the bus wherever events are published or consumed.

## Conventions

- Events are immutable — `const` constructor, `final` fields, no methods
- Event names describe something that already happened (past tense: `UserCreated`, `WorkoutCompleted`)
- Handlers are independent — one handler failing should not block others
- Events flow one direction: producer → bus → handlers. Handlers never call back to the producer.
- No Flutter imports in domain events or handlers — pure Dart
- Use `Logger`, never `print`

## Tests

- Test each handler independently with a constructed event
- Verify side effects (service calls, state changes)
- Test that handlers are independent (one failure doesn't affect others)
- Test stream emissions using `expectLater` with a `StreamMatcher`
