# Iterator — Dart idiom

> **Shape**: `.claude/agents/scaffold/iterator.md`
> **Source**: illustrative (no project exemplar)

**Use Dart's own protocol.** `sync*` generators give lazy, composable traversal with the whole
`Iterable` API for free — never hand-roll a cursor class:

```dart
extension RoutineTraversal on RoutineNode {
  /// Depth-first, parents before children.
  Iterable<RoutineNode> depthFirst() sync* {
    yield this;
    if (this is RoutineGroup) {
      for (final child in (this as RoutineGroup).children) {
        yield* child.depthFirst();
      }
    }
  }

  Iterable<ExerciseLeaf> leaves() =>
      depthFirst().whereType<ExerciseLeaf>();
}
```

Laziness is the point — this stops after the first match rather than walking the tree:

```dart
final first = routine.leaves().firstWhere((l) => l.duration > threshold);
```

- Name traversals for their order (`depthFirst`, `breadthFirst`) rather than exposing a mode flag.
- Each call returns a fresh, independent sequence, so two traversals can run at once.
- Traversal never mutates what it traverses.
- Document the behaviour if the structure changes mid-traversal: Dart's collections throw
  `ConcurrentModificationError`, which is the correct fail-fast — do not defeat it by copying
  unless a snapshot is genuinely wanted.
