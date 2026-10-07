# Use case — Dart idiom

> **Shape**: `.claude/agents/scaffold/use-case.md`
> **Source**: extracted from this project

Pure Dart — no Flutter imports. Constructor injection, one public entry method.

```dart
// lib/domain/<feature>/use_cases/<name>_use_case.dart
class PlaceOrderUseCase {
  final IOrderRepository _orders;
  final Logger _log = Logger('PlaceOrder UseCase');

  PlaceOrderUseCase(this._orders);

  Future<Order> execute(PlaceOrderParams params) async {
    _validate(params);
    final order = await _orders.save(params.toOrder());
    _log.info('Placed order ${order.id}');
    return order;
  }

  void _validate(PlaceOrderParams params) {
    if (params.items.isEmpty) {
      throw const DomainException('An order must contain at least one item.');
    }
  }
}
```

The entry method is `execute`, not `call` — matching `use-case.md` § Conventions. Validation runs
before any repository write, so a rejected request leaves no partial state.
