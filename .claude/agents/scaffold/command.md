# Command Pattern

> **Type**: template

## When to use

Scaffold a command when the task requires encapsulating a request as an object — enabling queuing, logging, undo/redo, or decoupling the invoker from the executor. Common in CQRS-style architectures, task dispatchers, and action-based systems in Dart/Flutter.

## File locations

| File | Path |
|---|---|
| Command abstract class | `lib/domain/commands/command.dart` (shared, create once) |
| Command | `lib/domain/<feature>/commands/<name>_command.dart` |
| Handler | `lib/domain/<feature>/commands/<name>_handler.dart` |
| Test | `test/domain/<feature>/commands/<name>_handler_test.dart` |

Adapt paths to the project's existing directory structure.

## Dependencies

- Command: none (pure data object, no Flutter imports)
- Handler: repositories, services, or other dependencies injected via constructor

## Template

```dart
// --- Shared command abstract class (create once) ---

abstract class Command {
  const Command();
}

abstract class CommandHandler<TCommand extends Command, TResult> {
  Future<TResult> execute(TCommand command);
}

// --- Specific command ---

class <Name>Command extends Command {
  const <Name>Command({
    required this.someParam,
    // command parameters — immutable
  });

  final String someParam;
}

// --- Handler ---

class <Name>Handler implements CommandHandler<<Name>Command, ResultType> {
  <Name>Handler({
    required ISomeRepository someRepository,
  }) : _someRepository = someRepository;

  final ISomeRepository _someRepository;
  final Logger _log = Logger('<Name> Handler');

  @override
  Future<ResultType> execute(<Name>Command command) async {
    // validate, execute, return result
  }
}
```

## Wiring

Register the handler in the DI container (Provider, get_it, Riverpod, etc.). Invokers submit commands without knowing which handler processes them.

## Conventions

- Commands are immutable data objects — `const` constructor, `final` fields, no methods, no dependencies
- One handler per command (Single Responsibility)
- Handlers contain execution logic and dependencies; use `Logger`, never `print`
- Command names are descriptive verb phrases (`CreateWorkoutCommand`, `DeleteRoutineCommand`)
- No Flutter imports in domain layer — pure Dart

## Tests

- Test the handler, not the command (commands are pure data)
- Test validation logic within the handler
- Test side effects (repository calls, events emitted)
- Test error cases (invalid input, dependency failures)
