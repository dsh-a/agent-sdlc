# Flutter analyzer finding patterns (pack: flutter)

Read by `/cycle` § Analyzer drift (5.8.1). Kept apart from `suite-patterns.md` because that file is `suite-result.py`'s contract and carries exactly its three fields — a fourth row there fails `tests/framework_checks.py`, correctly.

| Field | Pattern |
|---|---|
| analyzer_finding | `^\s*(info|warning|error)\s+•` |

`flutter analyze` prints one bulleted line per finding, e.g.
`   info • Unused import • lib/foo.dart:3:8 • unused_import`.

**Why a pattern and not a diff of the output.** `flutter analyze` prints
`No issues found! (ran in 5.4s)` — the elapsed time is *in* the output, so a whole-file diff is
non-empty on every run even when both captures have zero findings. Measured in one cycle: baseline
`(ran in 5.4s)` against `(ran in 14.5s)`, plus an upgrade banner in one capture and not the other,
with zero findings on both sides. Under `hard_fail_if_exceeded` that forced the review verdict to
REQUEST CHANGES on every cycle regardless of the code, which made the flag unusable as written.
