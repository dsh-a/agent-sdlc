# .NET suite result patterns (pack: dotnet)

Read by `.claude/skills/cycle/suite-result.py` to turn a suite's output into one
line. See `.claude/packs/flutter/suite-patterns.md` for the rules that govern
this table — they are identical and are not repeated here.

| Field | Pattern |
|---|---|
| summary_pass | `Passed!\s+- Failed:\s+(?P<failed>\d+), Passed:\s+(?P<passed>\d+), Skipped:\s+(?P<skipped>\d+)` |
| summary_fail | `Failed!\s+- Failed:\s+(?P<failed>\d+), Passed:\s+(?P<passed>\d+), Skipped:\s+(?P<skipped>\d+)` |
| failure_line | `^\s*Failed\s+(?P<test>\S+)` |

Matched against `dotnet test`'s console logger, whose summary looks like:

```
  Failed SomeNamespace.SomeClass.SomeMethod [12 ms]
Passed!  - Failed:     0, Passed:    42, Skipped:     0, Total:    42, Duration: 1 s
Failed!  - Failed:     3, Passed:    39, Skipped:     0, Total:    42, Duration: 2 s
```

Two notes specific to this stack:

- **`Total:` is deliberately not parsed.** The script derives the total from
  `passed + failed + skipped`, so a reporter that disagrees with its own
  arithmetic is visible rather than papered over.
- **A multi-project solution prints one summary per project.** These patterns
  scan backwards and take the last match, so what you get is the *last
  project's* result, not the solution's. For a solution build, either run
  `dotnet test` once per project with its own `<name>`, or add a pattern for
  whatever aggregate line your runner emits. This is a real limitation and it is
  written down rather than guessed at.
