# Observer — Dart idiom

> **Shape**: `.claude/agents/scaffold/observer.md`
> **Source**: illustrative (no project exemplar)

Use `Stream` for domain events and `ChangeNotifier` for UI state — never a hand-rolled listener
list.

```dart
// Event — immutable, past tense.
class OrderPlaced {
  final String orderId;
  final DateTime occurredAt;
  const OrderPlaced({required this.orderId, required this.occurredAt});
}

class OrderEventBus {
  final _controller = StreamController<OrderPlaced>.broadcast();

  Stream<OrderPlaced> get onOrderPlaced => _controller.stream;
  void publish(OrderPlaced event) => _controller.add(event);
  void dispose() => _controller.close();
}
```

Every subscription needs a matching disposal:

```dart
class FeedViewModel extends ChangeNotifier {
  late final StreamSubscription<OrderPlaced> _sub;

  FeedViewModel(OrderEventBus bus) {
    _sub = bus.onOrderPlaced.listen(_onOrderPlaced);
  }

  @override
  void dispose() {
    _sub.cancel();   // an undisposed subscription is a leak
    super.dispose();
  }
}
```

- `.broadcast()` allows many listeners; a single-subscription stream throws on the second `listen`.
- Event names are past tense (`OrderPlaced`); a present-tense name is a command in disguise.
- The payload is self-sufficient — a handler should not need to call back into the publisher.
- Handler order is not a contract. If two handlers must run in sequence, that is orchestration.
- A handler that publishes another event can cascade; bound it or forbid re-publication.
