# Service — Dart idiom

> **Shape**: `.claude/agents/scaffold/service.md`
> **Source**: extracted from this project (interface convention is forward-looking — see note)

```dart
// lib/data/services/<name>_service.dart
abstract interface class IConnectivityService {
  Stream<bool> get connectionChange;
  bool get isConnected;
}

class ConnectivityService implements IConnectivityService {
  final Logger _log = Logger('Connectivity Service');
  final Connectivity _connectivity;
  final StreamController<bool> _controller = StreamController<bool>.broadcast();
  late final StreamSubscription<List<ConnectivityResult>> _subscription;

  ConnectivityService({Connectivity? connectivity})
    : _connectivity = connectivity ?? Connectivity();

  @override
  Stream<bool> get connectionChange => _controller.stream;

  @override
  bool get isConnected => _isConnected;

  void dispose() {
    _subscription.cancel();
    _controller.close();
  }
}
```

- A service owning a stream or subscription exposes `dispose()`; whoever registers it calls it.
- Translate package exceptions into domain errors here. A plugin's exception type must not reach
  the domain layer.
- An optional-with-default constructor param (`Connectivity? connectivity`) keeps the real
  dependency injectable for tests without forcing every call site to supply it.

> **Convention note.** New services define an interface. Existing services predating this
> convention are being migrated; do not treat an interface-less legacy service as drift, and do
> not refactor one as a side effect of unrelated work.
