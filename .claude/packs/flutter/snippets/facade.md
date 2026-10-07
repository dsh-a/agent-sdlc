# Facade — Dart idiom

> **Shape**: `.claude/agents/scaffold/facade.md`
> **Source**: extracted from this project

```dart
// lib/domain/<feature>/facades/<feature>_facade.dart
class FeedWorkoutFacade {
  final Logger _log = Logger('Feed Workout Facade');

  final ISessionRepository sessionRepository;
  final IRoutineRepository routineRepository;

  FeedWorkoutFacade({
    required this.sessionRepository,
    required this.routineRepository,
  });

  /// Feature-level operation combining several sources — not a 1:1 pass-through.
  Future<WorkoutSummary?> getWorkoutSummary(String sessionId) async {
    final (session, routine) = await (
      sessionRepository.get(sessionId),
      routineRepository.getForSession(sessionId),
    ).wait;

    if (session == null) return null;
    return WorkoutSummary(session: session, routine: routine);
  }
}
```

- Dependencies are named required params typed as interfaces.
- Independent reads run concurrently. Dart 3's record `.wait` keeps the result types intact;
  `Future.wait([...])` erases them to a `List`.
- A method that only forwards to one repository belongs on that repository's consumer instead —
  see `facade.md` § Not when.
