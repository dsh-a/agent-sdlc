# Mediator — Dart idiom

> **Shape**: `.claude/agents/scaffold/mediator.md`
> **Source**: illustrative (no project exemplar)

Prefer named interaction methods over a stringly-typed `notify(event)` — the interface should read
as the group's protocol:

```dart
abstract interface class IRoutineFormMediator {
  void onExerciseSelected(ExerciseField sender, Exercise exercise);
  void onSetCountChanged(SetCountField sender, int count);
}

class RoutineFormMediator implements IRoutineFormMediator {
  final ExerciseField exerciseField;
  final SetCountField setCountField;
  final SummaryPanel summaryPanel;
  bool _updating = false;

  RoutineFormMediator({
    required this.exerciseField,
    required this.setCountField,
    required this.summaryPanel,
  });

  @override
  void onExerciseSelected(ExerciseField sender, Exercise exercise) {
    if (_updating) return;            // suppress re-entrancy
    _updating = true;
    try {
      setCountField.setSuggested(exercise.defaultSets);
      summaryPanel.refresh();
    } finally {
      _updating = false;
    }
  }
}
```

- Colleagues hold the mediator interface and never reference each other. A direct peer call is the
  pattern being abandoned.
- Guard re-entrancy explicitly: a mediator updating a colleague that notifies back will loop.
- One mediator per cohesive group. Coordinating two unrelated sets means splitting it.
