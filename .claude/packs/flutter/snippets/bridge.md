# Bridge — Dart idiom

> **Shape**: `.claude/agents/scaffold/bridge.md`
> **Source**: illustrative (no project exemplar)

```dart
// Implementor — primitive operations only.
abstract interface class INotificationChannel {
  Future<void> deliver(String title, String body);
}

// Abstraction — composes primitives into higher-level operations.
class Notifier {
  final INotificationChannel _channel;
  const Notifier(this._channel);

  Future<void> notifyOrderPlaced(Order order) =>
      _channel.deliver('Order placed', 'Order ${order.id} is confirmed.');
}

// RefinedAbstraction — extends the abstraction, not the implementor.
class DigestNotifier extends Notifier {
  const DigestNotifier(super.channel);

  Future<void> notifyDigest(List<Order> orders) =>
      _channel.deliver('Daily digest', '${orders.length} orders today.');
}

// ConcreteImplementors vary independently.
class PushChannel implements INotificationChannel { /* ... */ }
class EmailChannel implements INotificationChannel { /* ... */ }
```

- The two interfaces deliberately differ. If `Notifier` mirrors `INotificationChannel`
  method-for-method, this is needless indirection, not a bridge.
- Inject the implementor; when it is chosen at run-time, inject a factory rather than resolving
  inside the abstraction.
- `super.channel` in the subclass constructor is Dart 3's super-parameter shorthand.
