# Flyweight — Dart idiom

> **Shape**: `.claude/agents/scaffold/flyweight.md`
> **Source**: illustrative (no project exemplar)

**Dart gives you this for free with `const`.** Identical `const` instances are canonicalized by
the compiler to a single object — that is the flyweight pool, with no factory to write:

```dart
class ExerciseIcon {
  final String assetPath;
  final int colorValue;
  const ExerciseIcon(this.assetPath, this.colorValue); // const constructor

  void paint(Canvas canvas, Offset position) { /* extrinsic state as a parameter */ }
}

// Both references are the SAME object.
const a = ExerciseIcon('barbell.svg', 0xFF00FF00);
const b = ExerciseIcon('barbell.svg', 0xFF00FF00);
assert(identical(a, b));
```

Where keys are only known at run-time, an explicit pool is needed:

```dart
class ExerciseIconFactory {
  final Map<String, ExerciseIcon> _pool = {};

  ExerciseIcon get(String assetPath, int colorValue) =>
      _pool.putIfAbsent('$assetPath:$colorValue',
          () => ExerciseIcon(assetPath, colorValue));
}
```

- Measure first. This is an optimisation; profile before scaffolding one.
- Intrinsic state is immutable and context-independent; everything context-dependent is a
  **parameter**, never a field.
- Register the factory as a single shared instance — a per-request factory defeats the sharing.
- Never compare flyweights by identity in client logic, and bound the pool if its key comes from
  user input.
