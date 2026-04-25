# Strategy Pattern

> **Type**: template

## When to use

Scaffold a strategy when the task requires interchangeable algorithms or behaviors — different calculation methods, validation rules, sync strategies, or any family of behaviors selected at runtime. Common in Dart/Flutter apps for things like export formats, notification channels, pricing engines, or auth providers.

## File locations

| File | Path |
|---|---|
| Strategy abstract class | `lib/domain/<feature>/strategies/i_<name>_strategy.dart` |
| Concrete strategy | `lib/domain/<feature>/strategies/<variant>_<name>_strategy.dart` |
| Context (consumer) | `lib/domain/<feature>/<feature>_service.dart` (or wherever the strategy is used) |
| Test | `test/domain/<feature>/strategies/<variant>_<name>_strategy_test.dart` |

Adapt paths to the project's existing directory structure.

## Dependencies

- Strategy abstract class: domain types only — no Flutter imports
- Concrete strategies: may depend on services, configs, or external packages depending on the variant
- Context: depends on the abstract strategy, not concrete implementations

## Template

```dart
// --- Strategy abstract class ---

abstract class I<Name>Strategy {
  Future<OutputType> execute(InputType input);
}

// --- Concrete strategy A ---

class <VariantA><Name>Strategy implements I<Name>Strategy {
  const <VariantA><Name>Strategy();

  @override
  Future<OutputType> execute(InputType input) async {
    // variant A algorithm
  }
}

// --- Concrete strategy B ---

class <VariantB><Name>Strategy implements I<Name>Strategy {
  const <VariantB><Name>Strategy();

  @override
  Future<OutputType> execute(InputType input) async {
    // variant B algorithm
  }
}

// --- Context (consumer) ---

class <Feature>Service {
  <Feature>Service({
    required I<Name>Strategy strategy,
  }) : _strategy = strategy;

  I<Name>Strategy _strategy;
  final Logger _log = Logger('<Feature> Service');

  void setStrategy(I<Name>Strategy strategy) {
    _strategy = strategy;
  }

  Future<OutputType> doWork(InputType input) async {
    return _strategy.execute(input);
  }
}
```

## Wiring

Register concrete strategies in the DI container. The context receives a strategy via constructor injection or a factory that selects the appropriate strategy at runtime.

```dart
// Example: selecting a strategy based on config
Provider<I<Name>Strategy>(
  create: (context) {
    final config = context.read<AppConfig>();
    return config.useVariantA
        ? const <VariantA><Name>Strategy()
        : const <VariantB><Name>Strategy();
  },
),
```

## Conventions

- All strategies implement the same abstract class — they are fully interchangeable
- Strategy selection logic lives outside the strategies (factory, config, or context)
- Concrete strategies are stateless where possible — use `const` constructors
- Each strategy is independently testable in isolation
- No Flutter imports in domain strategies — pure Dart
- Use `Logger` in the context/consumer, not in individual strategies unless complex

## Tests

- Test each concrete strategy independently
- Test the context with different strategies to verify interchangeability
- Test strategy selection logic (factory or config-based selection)
- Each strategy should produce distinct, verifiable output for the same input
