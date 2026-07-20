# Flutter Project Commands (pack: flutter)

Canonical build / test / lint / codegen commands for the Flutter/Dart stack. These are the
**defaults** that seed `.omp/agent-config.md` § Project Commands — the live table every
implementation agent reads at runtime. When activating this pack (via `/setup` or by hand),
copy these into that table; override per-project there as needed (e.g. a different codegen
step or test glob).

| Purpose | Command |
|---|---|
| Run all tests | `flutter test` |
| Run specific test file | `flutter test <path>` |
| Analyze / lint | `flutter analyze` |
| Code generation | `flutter pub run build_runner build --delete-conflicting-outputs` |
| Test path glob | `test/**` |
| Test anti-patterns | `.claude/packs/flutter/test-antipatterns.md` |

- **Code generation** is optional — omit it if the project has no codegen step.
- **Test path glob** scopes the silent-skip gate and preflight short-circuit (`test/**` for Flutter; .NET-style layouts use `tests/**`).
- **Test anti-patterns** points at this pack's regex list, grepped by the cycle silent-skip gate.
