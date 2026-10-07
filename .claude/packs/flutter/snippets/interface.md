# Interface / contract — Dart idiom

> **Shape**: `.claude/agents/scaffold/interface.md`
> **Source**: extracted from this project

Dart 3's `abstract interface class` declares a contract that can only be implemented, never
extended — the right default for a layer boundary.

```dart
// lib/data/repositories/<feature>/i_<name>_repository.dart
abstract interface class IOrderRepository {
  Future<Order?> getById(String id);
  Future<void> save(Order order);
}
```

Contracts that extend a shared base use `implements`, and document any operation whose purpose
is not obvious from its name:

```dart
abstract interface class IOrderRepository implements IRepository<Order> {
  /// Returns orders where created_by == userId, regardless of visibility.
  /// Local-only — does not hit remote.
  Future<List<Order>> getByCreator(String userId);
}
```

- Return domain types (`Order`), never data-layer types (`OrderData`, `OrderCompanion`).
- Interface file sits beside its implementation, prefixed `i_`.
- No Flutter imports in a domain-facing contract.
