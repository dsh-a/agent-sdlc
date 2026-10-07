# Adapter / mapper — Dart idiom

> **Shape**: `.claude/agents/scaffold/adapter.md`
> **Source**: extracted from this project

This project's adapters are **mappers**: they translate a domain model across two boundaries at
once — the remote wire format and the local persistence format.

```dart
// lib/data/adapter/<name>_adapter.dart
abstract class ModelAdapter<T, D> {
  // Remote (JSON)
  T fromJson(Map<String, dynamic> json);
  Map<String, dynamic> toJson(T model);

  // Local (persistence)
  T fromLocal(D data);
  D toLocal(T model);
}

class OrderAdapter implements ModelAdapter<Order, OrderData> {
  final AppDatabase _db;
  final log = Logger('Order Adapter');

  OrderAdapter(this._db);

  @override
  Order fromJson(Map<String, dynamic> json) => Order(
    id: json['id'],
    placedAt: DateTime.parse(json['placed_at']),
    total: json['total'] as int? ?? 0,
    notes: json['notes'] as String?,
  );

  @override
  Map<String, dynamic> toJson(Order model) => {
    'id': model.id,
    'placed_at': model.placedAt.toIso8601String(),
    'total': model.total,
    'notes': model.notes,
  };
}
```

- snake_case on the wire, camelCase in the domain.
- Every nullable JSON field gets an explicit default or an `as T?` cast — a missing key must not
  throw at parse time.
- **Every field added to the model must be added to all four methods.** That drift is silent, so
  pair the adapter with an exhaustiveness test (see `adapter.md` § Tests).
