# Interface / Contract

> **Type**: template

## When to use

Scaffold an interface when the task requires defining a contract between layers — repository interfaces, service contracts, or any abstraction boundary. Dart `abstract interface class` enables dependency inversion and testability without coupling to implementations.

## File locations

| File | Path |
|---|---|
| Interface | `lib/data/repositories/<feature>/i_<name>_repository.dart` |
| Implementation | `lib/data/repositories/<feature>/<name>_repository.dart` |
| Test | `test/data/repositories/<feature>/<name>_repository_test.dart` |

Adapt paths to the project's existing directory structure. Service interfaces follow the same pattern under `lib/data/services/`.

## Dependencies

- Interface: domain models and types only — no Flutter imports, no infrastructure packages
- Implementation: data sources (Drift, Supabase, Hive, etc.) injected via constructor

## Template

```dart
// --- Interface definition ---

abstract interface class I<Name>Repository implements IRepository<<Entity>> {
  Future<<Entity>?> findById(String id);
  Future<List<<Entity>>> findAll({<Filter>? filter});
  Future<<Entity>> insert(<Entity> entity);
  Future<<Entity>> update(<Entity> entity);
  Future<void> delete(String id);
}

// --- Implementation ---

class <Name>Repository implements I<Name>Repository {
  <Name>Repository({
    required DriftDataSource localDataSource,
    required RemoteDataSource remoteDataSource,
    required ConnectivityService connectivityService,
    required <Entity>Adapter adapter,
  })  : _local = localDataSource,
        _remote = remoteDataSource,
        _connectivity = connectivityService,
        _adapter = adapter;

  final DriftDataSource _local;
  final RemoteDataSource _remote;
  final ConnectivityService _connectivity;
  final <Entity>Adapter _adapter;
  final Logger _log = Logger('<Name> Repository');

  @override
  Future<<Entity>?> findById(String id) async {
    // implementation
  }

  // ... remaining methods
}
```

## Wiring

Bind the interface to its implementation in the DI container. Consumers import and depend on the interface (`I<Name>Repository`), never the implementation directly.

```dart
// Example: Provider
Provider<I<Name>Repository>(
  create: (_) => <Name>Repository(
    localDataSource: ...,
    remoteDataSource: ...,
    connectivityService: ...,
    adapter: ...,
  ),
),
```

## Conventions

- Interface names use `I` prefix (e.g., `IUserRepository`, `IAuthService`)
- Interfaces live at the layer boundary — domain interfaces in `lib/domain/`, data interfaces in `lib/data/`
- Keep interfaces focused — prefer multiple small interfaces over one large one
- Return domain types, not data layer types (return `User`, not `UserData`)
- No Flutter imports in the interface or domain models

## Tests

- Test the implementation against the interface contract
- Each interface method should have at least one test
- Mock the interface (using `mocktail`) in tests for consumers
- Use `isA<I<Name>Repository>()` assertions to catch contract violations
