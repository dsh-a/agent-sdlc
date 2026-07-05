# Flutter Test Anti-Patterns (pack: flutter)

The original Dart/`flutter_test` silent-skip patterns for the cycle orchestrator's
**silent-skip gate**. Active only when the flutter pack is active.

```
if \(find\w*\.isNotEmpty            # gated assertion
if \(finder\.evaluate\(\)           # same shape, different API
try \{[^}]*expect[^}]*\} catch      # swallowed expect
\.skip\(|@Skip\(|xit\(|xtest\(      # skipped tests
```

**Scope:** changed test files only (`test/**`). Production (`lib/`) matches are not flagged.
