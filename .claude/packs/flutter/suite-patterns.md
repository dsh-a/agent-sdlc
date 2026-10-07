# Flutter suite result patterns (pack: flutter)

Read by `.claude/skills/cycle/suite-result.py` to turn a suite's output into one
line. Stack-specific by construction — the script knows how to run a command and
read this table; it knows nothing about Dart.

| Field | Pattern |
|---|---|
| summary_pass | `\+(?P<passed>\d+)(?: ~(?P<skipped>\d+))?: All tests passed!` |
| summary_fail | `\+(?P<passed>\d+)(?: ~(?P<skipped>\d+))? -(?P<failed>\d+): Some tests failed\.` |
| failure_line | `\+\d+(?: ~\d+)? -\d+: (?P<test>.+) \[E\]` |

Matched against `flutter test`'s default and `--reporter compact` output, whose
progress lines look like:

```
00:02 +5: some test name
00:02 +5 ~1: a skipped test
00:05 +12 -1: test/foo_test.dart: a failing test [E]
00:06 +81: All tests passed!
00:06 +78 -3: Some tests failed.
```

## Rules for editing this table

- **Named groups are the contract.** `passed`, `failed`, `skipped` on the summary
  rows; `test` on `failure_line`. A group the reporter does not emit should be
  *absent*, not zero — the script reports a missing group as "not reported", and
  `skipped=0` is a different claim from "this reporter never mentions skips".
- **No `|` anywhere in a pattern.** The cell is a markdown table cell and a pipe
  ends it. Use a non-capturing optional group rather than alternation; every
  pattern here is written that way for this reason.
- **`summary_pass` is tried before `summary_fail`, and both scan backwards.**
  The last match wins, because a test whose *name* contains the summary wording
  would otherwise be read as the summary.
- **Anchor loosely.** These use `search`, not `match`, so a leading timestamp or
  a `--reporter` prefix does not need to be spelled out. The trade is that a
  pattern which is too loose matches a test name; keep the distinctive part
  (`All tests passed!`, `[E]`) in the pattern.
- **A pattern that does not compile is skipped with a warning**, not fatal. A
  broken row costs you the parse, not the suite run.

If the project uses a reporter none of these match, `suite-result.py` reports
`UNPARSED` with the raw exit code rather than guessing a verdict from it. That is
the signal to add a row here, not to infer PASS from exit 0.
