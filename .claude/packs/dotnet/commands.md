# .NET Project Commands (pack: dotnet)

Canonical build / test / lint commands for the .NET stack. These are the **defaults** that seed
`.omp/agent-config.md` § Project Commands — the live table every implementation agent reads at
runtime. When a project takes this pack (via `/setup` or by hand), copy these into that table and
override per-project there (a solution path, a different filter, a legacy toolchain).

| Purpose | Command |
|---|---|
| Run all tests | `dotnet test` |
| Run specific test file | `dotnet test <project>` |
| Run single test by name | `dotnet test <project> --filter "FullyQualifiedName~<test name>"` |
| CI workflow (dispatchable) | |
| Analyze / lint | `dotnet format --verify-no-changes` |
| Format | `dotnet format` |
| Code generation | |
| Test path glob | `tests/**` |
| Test anti-patterns | `.claude/packs/dotnet/test-antipatterns.md` |

- **CI workflow** is the `workflow_dispatch`-enabled GitHub Actions workflow `verify` and `review` trigger for a full-suite result. Leave blank if the project has none; agents then fall back to `run-suite.sh`. Requires the workflow to accept a `ref` input.
- **Run single test by name** is what forced falsification runs against; scope it to one test.
- **Code generation** is blank: add the project's step if it has one.
- **Test path glob** scopes the silent-skip gate and preflight short-circuit.
- A .NET Framework project replaces these rows with its own toolchain (`msbuild`, `vstest.console.exe`).
