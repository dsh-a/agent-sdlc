# Abstract Factory — Dart idiom

> **Shape**: `.claude/agents/scaffold/abstract-factory.md`
> **Source**: illustrative (no project exemplar)

```dart
// lib/domain/<feature>/factories/i_<name>_factory.dart
abstract interface class IStorageFactory {
  ILocalStore createLocalStore();
  IRemoteStore createRemoteStore();
}

// lib/data/<feature>/factories/<variant>_<name>_factory.dart
class SqliteStorageFactory implements IStorageFactory {
  final AppDatabase _db;
  const SqliteStorageFactory(this._db);

  @override
  ILocalStore createLocalStore() => DriftLocalStore(_db);

  @override
  IRemoteStore createRemoteStore() => SupabaseRemoteStore();
}
```

- Every method returns the **abstract** product type. A concrete return type defeats the pattern.
- One concrete factory per family variant; a factory never returns another variant's product.
- Register the factory interface once at the composition root and inject it; never register the
  products individually, since that is what allows a family to be mixed.
- Adding a product type changes the interface and **every** implementation — Dart gives you a
  compile error at each one, which is the intended cost.
