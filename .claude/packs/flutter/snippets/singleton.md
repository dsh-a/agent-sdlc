# Singleton — Dart idiom

> **Shape**: `.claude/agents/scaffold/singleton.md`
> **Source**: illustrative (no project exemplar)

**Preferred — let the container own the lifetime.** A `Provider` creates its value once and shares
it. This gives you the single instance without a global access point, and it stays injectable:

```dart
// lib/dependencies/di_services.dart
Provider<IAnalyticsService>(
  create: (_) => AnalyticsService(),
  dispose: (_, s) => s.dispose(),
),
```

The class itself is ordinary — no static state, no `instance` getter:

```dart
class AnalyticsService implements IAnalyticsService { /* normal constructor */ }
```

**Classic form — only where no container can own the lifetime** (a platform callback, a static
entry point). Dart's `factory` constructor plus a `static final` gives lazy, thread-safe
initialisation for free:

```dart
class AppClock {
  static final AppClock _instance = AppClock._();
  AppClock._();
  factory AppClock() => _instance;
}
```

- Always define an interface, or the singleton is unmockable and every consumer is welded to it.
- Never call the global accessor from domain code — inject the interface.
- A singleton holding mutable state needs an explicit reset seam, and tests must use it;
  otherwise state leaks between tests.
- Wrap an unavoidable global behind an injectable interface so exactly one adapter class touches it.
