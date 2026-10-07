# ViewModel — Dart/Flutter idiom

> **Shape**: presentation — owned by the `ui-story` agent, not a scaffold pattern file
> **Source**: extracted from this project

```dart
// lib/ui/<feature>/view_models/<feature>_view_model.dart
class FeatureViewModel extends ChangeNotifier {
  final PlaceOrderUseCase _placeOrder;
  final Logger _log = Logger('Feature ViewModel');

  FeatureViewModel(this._placeOrder);

  bool _isLoading = false;
  bool get isLoading => _isLoading;

  Future<void> submit(PlaceOrderParams params) async {
    _isLoading = true;
    notifyListeners();
    try {
      await _placeOrder.execute(params);
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
```

State is private with a public getter. `notifyListeners()` fires after every state change,
including in the failure path — a `finally` block, not a happy-path-only call.
See `conventions.md` § ViewModels for member order and disposal rules.
