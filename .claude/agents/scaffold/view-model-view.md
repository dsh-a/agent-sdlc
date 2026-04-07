# ViewModel + View

ViewModels are `ChangeNotifier`s that expose state and actions to Views.

## File locations
- ViewModel: `lib/ui/<feature>/view_models/<feature>_view_model.dart`
- View: `lib/ui/<feature>/views/<feature>_view.dart`

## ViewModel pattern
```dart
import 'package:flutter/foundation.dart';
import 'package:logging/logging.dart';

class <Feature>ViewModel extends ChangeNotifier {
  final Logger _log = Logger('<Feature> ViewModel');

  bool _isLoading = false;
  bool get isLoading => _isLoading;

  String? _errorMessage;
  String? get errorMessage => _errorMessage;

  // Constructor with required deps

  // Public methods (called by View)

  // Private methods
}
```

## ViewModel convention
- Extend `ChangeNotifier`
- Dependencies via constructor (use cases, facades — never repos directly)
- Expose state via getters (`isLoading`, `errorMessage`, data fields)
- Expose actions as public methods
- Use `Logger`, never `print`
- Follow class member order: external deps → internal deps → variables → constructor → public → private

## View convention
- Use `context.watch<ViewModel>()` or `context.read<ViewModel>()` from Provider
- Use `Theme.of(context).textTheme` and `Theme.of(context).colorScheme` — never hardcoded styles
- Use `const` constructors where possible
- Break large `build()` into small private `Widget` classes (when it exceeds ~40 lines)
- Use `Key` values on widgets that need to be found in tests
- Handle loading and error states explicitly
- Never perform network calls or heavy computation inside `build()`
- Use `ListView.builder` / `SliverList` for any list longer than a handful of static items

## Wire into DI
- ViewModel: add to `lib/dependencies/di_view_models.dart` as a `ChangeNotifierProvider`
- Route (if needed): add to `lib/router.dart`
