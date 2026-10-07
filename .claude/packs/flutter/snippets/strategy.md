# Strategy — Dart idiom

> **Shape**: `.claude/agents/scaffold/strategy.md`
> **Source**: illustrative (no project exemplar)

```dart
abstract interface class IProgressionStrategy {
  double nextWeight(ExerciseHistory history);
}

class LinearProgression implements IProgressionStrategy {
  final double increment;
  const LinearProgression({this.increment = 2.5});

  @override
  double nextWeight(ExerciseHistory history) =>
      history.lastWeight + increment;
}

class DoubleProgression implements IProgressionStrategy {
  const DoubleProgression();

  @override
  double nextWeight(ExerciseHistory history) =>
      history.hitTopOfRange ? history.lastWeight + 2.5 : history.lastWeight;
}
```

Selection lives outside the strategies, in one table:

```dart
class ProgressionStrategyFactory {
  static const _byKey = <String, IProgressionStrategy>{
    'linear': LinearProgression(),
    'double': DoubleProgression(),
  };

  IProgressionStrategy forKey(String key) =>
      _byKey[key] ?? (throw DomainException('Unknown progression: $key'));
}
```

- Strategies are stateless where possible, which makes them `const` and shareable.
- A strategy that decides *whether* it applies has become a chain-of-responsibility link.
- For a single-method strategy chosen inline, a typedef'd function is often enough:
  `typedef Progression = double Function(ExerciseHistory);` — prefer it when there is no
  configuration or DI involved.
