# Facade

Facades aggregate multiple repositories for complex feature logic. They live in `lib/domain/`.

## File location
`lib/domain/<feature>/facades/<feature>_facade.dart`

## Pattern
```dart
import 'package:logging/logging.dart';

class <Feature>Facade {
  final Logger _log = Logger('<Feature> Facade');
  final ISomeRepository someRepository;
  final IOtherRepository otherRepository;

  <Feature>Facade({
    required this.someRepository,
    required this.otherRepository,
  });
}
```

## Convention
- Dependencies are repository **interfaces** (not implementations)
- Public constructor fields (not private) — unlike use cases, facades expose their repos for flexibility
- No Flutter imports — pure Dart
- Contains cross-repo orchestration logic, not business rules (those go in use cases)

## Wire into DI
Add to `lib/dependencies/di_facades.dart` as a `Provider`.
