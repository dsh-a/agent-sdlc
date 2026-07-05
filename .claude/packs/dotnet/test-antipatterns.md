# .NET Test Anti-Patterns (pack: dotnet)

The cycle orchestrator's **silent-skip gate** (`cycle/SKILL.md` § Commit protocol) greps
the diff of changed test files for these patterns. **Any hit blocks the merge** and
re-spawns the test agent. These are the .NET/xUnit-NUnit-MSTest equivalents of the
gated-assertion / swallowed-assert / skipped-test family.

> One regex per line, `#`-comments stripped before use. Adjust for your framework.
> The orchestrator reads this list because the active pack is `dotnet`
> (`.claude/config.md` → Active Pack); to override per-project, set the
> **Test anti-patterns** pointer in `.claude/config.md` § Project Commands.

```
if\s*\([^)]*\.Any\(\)\)\s*Assert         # assertion gated behind a runtime check
foreach\s*\([^)]*\)\s*Assert             # assertion only runs if the collection is non-empty
try\s*\{[^}]*Assert[^}]*\}\s*catch       # swallowed assertion
\[Fact\s*\(\s*Skip\s*=                    # skipped xUnit fact
\[Theory\s*\(\s*Skip\s*=                  # skipped xUnit theory
\[Ignore[\](]                             # NUnit/MSTest ignored test
Assert\.True\(true\)|Assert\.Pass\(\)     # vacuous / always-pass assertion
```

**Scope:** changed test files only (the configured test glob, default `tests/**` for .NET —
see `.claude/config.md` § Project Commands → *Test path glob*). Production-code matches are
not flagged.
