# Template Method — Dart idiom

> **Shape**: `.claude/agents/scaffold/template-method.md`
> **Source**: illustrative (no project exemplar)

```dart
abstract class SyncJob {
  final Logger _log = Logger('Sync Job');

  /// The template method owns the ORDER. Do not override it.
  Future<SyncResult> run() async {
    final pending = await fetchPending();      // required step
    if (pending.isEmpty) return SyncResult.empty();
    await onBeforePush(pending);               // optional hook
    final pushed = await push(pending);        // required step
    return SyncResult(pushed: pushed);
  }

  @protected
  Future<List<Syncable>> fetchPending();       // abstract: subclass must implement

  @protected
  Future<int> push(List<Syncable> items);      // abstract

  /// Hook with a safe no-op default — override only if needed.
  @protected
  Future<void> onBeforePush(List<Syncable> items) async {}
}

class RoutineSyncJob extends SyncJob {
  @override
  Future<List<Syncable>> fetchPending() async { /* ... */ }

  @override
  Future<int> push(List<Syncable> items) async { /* ... */ }
}
```

- Dart has no `final` method modifier, so the template method's immutability is a **convention**:
  mark steps `@protected`, document that `run()` must not be overridden, and assert it in review.
  This is the one place Dart cannot enforce the pattern's core guarantee.
- Required steps are abstract, so a missing override is a compile error. Optional hooks get a
  no-op default.
- Steps never call one another; only the template method sequences them.
- Where the whole algorithm varies rather than its steps, prefer `strategy` — composition beats
  inheritance here, and Dart allows only one superclass.
