# Visitor — Dart idiom

> **Shape**: `.claude/agents/scaffold/visitor.md`
> **Source**: illustrative (no project exemplar)

**Preferred — `sealed` + exhaustive `switch`.** Dart 3 gives the visitor's safety property
(a new node type breaks every operation at compile time) without the double-dispatch ceremony:

```dart
sealed class RoutineNode { const RoutineNode(); }
class ExerciseLeaf extends RoutineNode { final Duration d; const ExerciseLeaf(this.d); }
class RoutineGroup extends RoutineNode { final List<RoutineNode> c; const RoutineGroup(this.c); }

// One operation = one function. Adding a node type fails compilation here.
Duration totalDuration(RoutineNode node) => switch (node) {
  ExerciseLeaf(:final d) => d,
  RoutineGroup(:final c) =>
    c.fold(Duration.zero, (sum, child) => sum + totalDuration(child)),
};

String describe(RoutineNode node) => switch (node) {
  ExerciseLeaf() => 'exercise',
  RoutineGroup(:final c) => 'group of ${c.length}',
};
```

**Classic double dispatch — only for an open hierarchy** that callers outside the library extend,
where `sealed` is not available:

```dart
abstract interface class RoutineVisitor<R> {
  R visitLeaf(ExerciseLeaf leaf);
  R visitGroup(RoutineGroup group);
}

abstract class RoutineNode {
  R accept<R>(RoutineVisitor<R> v);
}

class ExerciseLeaf extends RoutineNode {
  @override
  R accept<R>(RoutineVisitor<R> v) => v.visitLeaf(this);  // exactly this one line
}
```

- `accept` is one line: call the visit method for **this** node's own type. A copy-paste error
  here routes silently to the wrong branch and is this pattern's most common bug.
- Never add a `default:` clause or a catch-all visit method — that discards the compile-time
  exhaustiveness that justifies the pattern.
- A visitor accumulating state is single-use; create a fresh one per traversal.
