# Proxy — Dart idiom

> **Shape**: `.claude/agents/scaffold/proxy.md`
> **Source**: illustrative (no project exemplar)

Same shape as a decorator; the difference is intent — a proxy **controls access**. Name the class
for its kind so the wiring site reads clearly.

```dart
// Virtual proxy — defer expensive creation. `late final` initialises at most once.
class LazyReportRenderer implements IReportRenderer {
  final IReportRenderer Function() _create;
  late final IReportRenderer _inner = _create();

  LazyReportRenderer(this._create);

  @override
  Future<void> render(Report r) => _inner.render(r);
}

// Protection proxy — deny with a domain error, never a silent null.
class OwnerScopedOrderRepository implements IOrderRepository {
  final IOrderRepository _inner;
  final IIdentityService _identity;

  OwnerScopedOrderRepository(this._inner, this._identity);

  @override
  Future<Order?> getById(String id) async {
    final order = await _inner.getById(id);
    if (order != null && order.createdBy != _identity.currentUserId) {
      throw const DomainException('Order not accessible to the current user.');
    }
    return order;
  }
}
```

- Inject a **factory** into a virtual proxy, not an already-constructed instance — otherwise there
  is nothing left to defer.
- `late final` with an initialiser gives lazy, once-only creation without a null check.
- The proxy implements the interface exactly; extra public methods leak its existence.
- Errors from the real subject pass through untouched unless translation is the proxy's job.
