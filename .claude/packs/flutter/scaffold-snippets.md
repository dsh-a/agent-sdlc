# Flutter Scaffold Snippets (pack: flutter)

> Placeholder language snippets the `scaffold` agent uses when generating new components.
> The pattern *shapes* (interface, service, facade, use-case, command, strategy, observer)
> are defined language-neutrally in `.claude/agents/scaffold/*.md`; this file supplies the
> Dart/Flutter idiom for each. Fill in to match your project.

## Interface / contract (repository)

```dart
abstract interface class IOrderRepository {
  Future<Order?> getById(String id);
  Future<void> save(Order order);
}
```

## Use case (constructor injection, pure Dart — no Flutter imports)

```dart
class PlaceOrderUseCase {
  final IOrderRepository _orders;
  final Logger _log = Logger('PlaceOrder UseCase');

  PlaceOrderUseCase(this._orders);

  Future<Result> call(PlaceOrder command) async {
    // ...
  }
}
```

## ViewModel (ChangeNotifier + Provider)

```dart
class FeatureViewModel extends ChangeNotifier {
  final PlaceOrderUseCase _placeOrder;
  final Logger _log = Logger('Feature ViewModel');

  FeatureViewModel(this._placeOrder);

  bool _isLoading = false;
  bool get isLoading => _isLoading;

  Future<void> submit() async {
    // set state → call the use case → notifyListeners()
  }
}
```

File location: `lib/ui/<feature>/view_models/<feature>_view_model.dart`.

## DI registration (Provider)

```dart
// lib/dependencies/di_view_models.dart
ChangeNotifierProvider<FeatureViewModel>(
  create: (context) => FeatureViewModel(context.read<PlaceOrderUseCase>()),
),
```

> Codegen: if the component needs generated code (Drift, json_serializable, freezed),
> run the **Code generation** command in `.omp/agent-config.md` § Project Commands
> (`flutter pub run build_runner build --delete-conflicting-outputs`) — never hand-edit
> `.g.dart` files.
