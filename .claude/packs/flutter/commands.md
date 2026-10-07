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
| Run single test by name | `flutter test <path> --plain-name "<test name>"` |
| CI workflow (dispatchable) | `ci.yml` |
| Analyze / lint | `flutter analyze` |
| Format | `dart format .` |
| Code generation | `flutter pub run build_runner build --delete-conflicting-outputs` |
| Test path glob | `test/**` |
| Test anti-patterns | `.claude/packs/flutter/test-antipatterns.md` |

- **CI workflow** is the `workflow_dispatch`-enabled GitHub Actions workflow `verify` and `review` trigger for a full-suite result instead of running it locally. Leave blank if the project has none; agents then fall back to `run-suite.sh`. Requires the workflow to accept a `ref` input.
- **Run single test by name** is what forced falsification runs against. Scoping the run to one test is what makes the evidence checkable: a broad run can go red for an unrelated reason and be attributed to the wrong assertion, which is how a falsification that could not possibly reproduce was once reported as observed.
- **Format** must be run after editing any Dart file — CI enforces it with `dart format --set-exit-if-changed`, so an unformatted file fails the build. Implementation agents run it as part of their Definition of Done.
- **Code generation** is optional — omit it if the project has no codegen step.
- **Test path glob** scopes the silent-skip gate and preflight short-circuit (`test/**` for Flutter; .NET-style layouts use `tests/**`).
- **Test anti-patterns** points at this pack's regex list, grepped by the cycle silent-skip gate.
