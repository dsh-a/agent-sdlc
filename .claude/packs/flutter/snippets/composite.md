# Composite — Dart idiom

> **Shape**: `.claude/agents/scaffold/composite.md`
> **Source**: illustrative (no project exemplar)

A `sealed` hierarchy lets the compiler prove every node type is handled, which is the safer
default when the node set is closed:

```dart
// lib/domain/<feature>/composites/<name>_component.dart
sealed class RoutineNode {
  const RoutineNode();
  Duration get totalDuration;
}

class ExerciseLeaf extends RoutineNode {
  final Duration duration;
  const ExerciseLeaf(this.duration);

  @override
  Duration get totalDuration => duration;
}

class RoutineGroup extends RoutineNode {
  final List<RoutineNode> children;
  const RoutineGroup(this.children);

  @override
  Duration get totalDuration =>
      children.fold(Duration.zero, (sum, c) => sum + c.totalDuration);
}
```

- Child management lives on the composite, not the base — a leaf forced to implement `add` must
  fail with a domain error, never silently.
- The empty composite is where `fold` identities go wrong; `Duration.zero` above is the identity.
- Use `sealed` when the node types are closed. Use `abstract interface class` when callers outside
  the library must add node types — you lose exhaustiveness checking in exchange.
- Guard against cycles when the tree is built from external input, or every recursive walk hangs.
