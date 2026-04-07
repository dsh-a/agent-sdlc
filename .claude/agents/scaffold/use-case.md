# Use Case

Use cases encapsulate a single business operation. They live in `lib/domain/`.

## File location
`lib/domain/<feature>/use_cases/<use_case_name>_use_case.dart`

## Pattern
```dart
import 'package:logging/logging.dart';

class <Name>UseCase {
  final Logger _log = Logger('<Name> Use Case');
  final ISomeRepository _someRepository;

  <Name>UseCase({required ISomeRepository someRepository})
      : _someRepository = someRepository;

  Future<ReturnType> execute(ParamType param) async {
    // implementation
  }
}
```

## Convention
- One public method: `execute()` (or a descriptively named method if `execute` is ambiguous)
- Dependencies injected via constructor, stored as private final fields
- Uses `Logger`, never `print`
- No framework imports — pure TypeScript
- Calls repositories/services, never adapters or database directly

## Wire into DI
Add to `lib/dependencies/di_use_cases.dart` as a `Provider`.
