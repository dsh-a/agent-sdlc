# Command — Dart idiom

> **Shape**: `.claude/agents/scaffold/command.md`
> **Source**: illustrative (no project exemplar)

The command is inert data; the handler holds the dependencies and the logic:

```dart
// Command — immutable, no methods, no dependencies.
class PlaceOrderCommand {
  final String customerId;
  final List<OrderItem> items;
  const PlaceOrderCommand({required this.customerId, required this.items});
}

// Handler — one per command.
abstract interface class ICommandHandler<TCommand, TResult> {
  Future<TResult> handle(TCommand command);
}

class PlaceOrderHandler implements ICommandHandler<PlaceOrderCommand, Order> {
  final IOrderRepository _orders;
  final Logger _log = Logger('PlaceOrder Handler');

  PlaceOrderHandler(this._orders);

  @override
  Future<Order> handle(PlaceOrderCommand command) async {
    if (command.items.isEmpty) {
      throw const DomainException('An order must contain at least one item.');
    }
    return _orders.save(Order.fromCommand(command));
  }
}
```

- Commands are immutable data objects, named as verb phrases (`PlaceOrderCommand`).
- One handler per command.
- Keep only primitives and domain value types in a command if it will be queued or logged —
  never a service or a closure, which are not serialisable.
- Register the handler against its command type and fail loudly at startup on a command with no
  handler; a missing registration must not become a run-time no-op.
