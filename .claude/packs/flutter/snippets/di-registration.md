# DI registration — Dart/Flutter idiom

> **Shape**: cross-cutting — every pattern file's § Wiring points here
> **Source**: extracted from this project

Bind the interface, so consumers resolve the abstraction:

```dart
// lib/dependencies/di_services.dart
Provider<IConnectivityService>(
  create: (_) => ConnectivityService(),
  dispose: (_, service) => service.dispose(),
),
```

ViewModels use `ChangeNotifierProvider`, reading their dependencies from the context:

```dart
// lib/dependencies/di_view_models.dart
ChangeNotifierProvider<FeatureViewModel>(
  create: (context) => FeatureViewModel(context.read<PlaceOrderUseCase>()),
),
```

- A single shared instance is `Provider` (created once); a fresh instance per consumer is a
  factory function passed in, not a Provider.
- Anything with a `dispose()` gets the `dispose:` callback wired at registration — Provider will
  not guess.
- Register at the composition root only. Domain and data classes never reach for the container.
