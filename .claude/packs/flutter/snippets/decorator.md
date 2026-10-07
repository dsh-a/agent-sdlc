# Decorator — Dart idiom

> **Shape**: `.claude/agents/scaffold/decorator.md`
> **Source**: illustrative (no project exemplar)

The decorator implements the same interface and holds one, so callers cannot tell the difference:

```dart
class CachingOrderRepository implements IOrderRepository {
  final IOrderRepository _inner;
  final Map<String, Order> _cache = {};

  CachingOrderRepository(this._inner);

  @override
  Future<Order?> getById(String id) async {
    final hit = _cache[id];
    if (hit != null) return hit;              // deliberate short-circuit
    final order = await _inner.getById(id);
    if (order != null) _cache[id] = order;
    return order;
  }

  @override
  Future<void> save(Order order) async {
    await _inner.save(order);                  // always delegates
    _cache.remove(order.id);
  }
}
```

Compose the stack once, at the composition root, so the order is visible in one place:

```dart
Provider<IOrderRepository>(
  create: (context) => LoggingOrderRepository(
    CachingOrderRepository(
      OrderRepository(context.read<AppDatabase>()),
    ),
  ),
),
```

- One concern per decorator. A class that caches *and* logs is two decorators.
- No extra public methods — that leaks the wrapper and breaks transparency.
- Order is meaningful; document it where the stack is built.
- Dart's `noSuchMethod` can auto-forward undeclared methods. Avoid it here: it defeats the
  compiler's check that you implemented the full interface.
