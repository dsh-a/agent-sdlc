# Memento — Dart idiom

> **Shape**: `.claude/agents/scaffold/memento.md`
> **Source**: illustrative (no project exemplar)

Dart's library privacy (`_`) is the narrow/wide interface split: the memento's state is visible
inside its library and opaque outside it.

```dart
// lib/domain/<feature>/mementos/<name>_memento.dart
class RoutineDraftMemento {
  final String _name;
  final List<Exercise> _exercises;

  const RoutineDraftMemento._(this._name, this._exercises);
}

class RoutineDraft {
  String name = '';
  List<Exercise> exercises = [];

  RoutineDraftMemento createMemento() =>
      RoutineDraftMemento._(name, List.unmodifiable(exercises));

  /// Replaces state wholesale — a partial restore leaves a state that never existed.
  void restore(RoutineDraftMemento m) {
    name = m._name;
    exercises = List.of(m._exercises);
  }
}

/// Caretaker treats the memento as an opaque token.
class RoutineDraftHistory {
  final List<RoutineDraftMemento> _stack = [];
  static const _maxDepth = 20;

  void save(RoutineDraft d) {
    _stack.add(d.createMemento());
    if (_stack.length > _maxDepth) _stack.removeAt(0);
  }

  void undo(RoutineDraft d) {
    if (_stack.isNotEmpty) d.restore(_stack.removeLast());
  }
}
```

- The memento is immutable and holds a **complete** copy. Copy mutable collections on both the way
  in and the way out — sharing a list restores nothing.
- Every field added to the originator's restorable state must be added to the memento; this drift
  silently breaks undo, so round-trip test it field by field.
- Bound the history and scope the caretaker per document or session, never app-wide.
- For a small snapshot a Dart **record** works as the memento: `(name: name, exercises: [...])`.
