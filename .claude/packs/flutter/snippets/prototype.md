# Prototype — Dart idiom

> **Shape**: `.claude/agents/scaffold/prototype.md`
> **Source**: illustrative (no project exemplar)

**In Dart this is `copyWith`.** Implement the pattern through the language idiom rather than a
hand-rolled `clone()`:

```dart
class Order {
  final String id;
  final List<OrderItem> items;
  const Order({required this.id, required this.items});

  Order copyWith({String? id, List<OrderItem>? items}) => Order(
    id: id ?? this.id,
    // deep-copy anything mutable; a shared list is this pattern's silent bug
    items: items ?? List<OrderItem>.from(this.items),
  );
}
```

`freezed` generates `copyWith` correctly, including for nested classes — prefer it over
hand-written copies for anything with more than a few fields, and run the **Code generation**
command after changing the model.

For a registry of pre-configured prototypes:

```dart
class OrderTemplateRegistry {
  final Map<String, Order> _templates = {};

  void register(String key, Order prototype) => _templates[key] = prototype;

  /// Always returns a copy — handing out the stored instance lets a caller
  /// corrupt the catalogue for everyone.
  Order create(String key) {
    final proto = _templates[key];
    if (proto == null) throw DomainException('Unknown template: $key');
    return proto.copyWith();
  }
}
```

Every field added to the model must be added to `copyWith`. That drift is silent — test it by
copying an instance and asserting field-for-field equality.
