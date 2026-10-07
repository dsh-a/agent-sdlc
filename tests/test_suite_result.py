#!/usr/bin/env python3
"""Tests for .claude/skills/cycle/suite-result.py — stdlib only.

Pins the three things that would make this tool worse than the raw command it
replaces:

  * it claims PASS when it did not read a pass,
  * it puts the suite's output on stdout,
  * it reports a truncated failure list as if it were complete.

    python3 tests/test_suite_result.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "skills" / "cycle" / "suite-result.py"

_spec = importlib.util.spec_from_file_location("suite_result", SCRIPT)
sr = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(sr)

FLUTTER_PATTERNS = ROOT / ".claude" / "packs" / "flutter" / "suite-patterns.md"
DOTNET_PATTERNS = ROOT / ".claude" / "packs" / "dotnet" / "suite-patterns.md"

FLUTTER_PASS = """\
00:00 +0: loading test/ui/setup/setup_view_test.dart
00:02 +5: SetupView renders all four control sections
00:04 +47: AC-01 — Goals section placement key is present
00:06 +81: All tests passed!
"""

FLUTTER_PASS_SKIPS = """\
00:02 +5 ~1: a skipped test
00:06 +79 ~2: All tests passed!
"""

FLUTTER_FAIL = """\
00:02 +5: SetupView renders all four control sections
00:05 +12 -1: test/foo_test.dart: badge tap deselects [E]
00:05 +12 -2: test/bar_test.dart: chip is 48dp [E]
00:06 +78 -2: Some tests failed.
"""

# A test whose *name* contains the summary wording. The real summary is last.
FLUTTER_ADVERSARIAL = """\
00:01 +1: reports "All tests passed!" when the suite is green
00:06 +2: All tests passed!
"""

DOTNET_PASS = """\
  Determining projects to restore...
Passed!  - Failed:     0, Passed:    42, Skipped:     0, Total:    42, Duration: 1 s
"""

DOTNET_FAIL = """\
  Failed MyApp.Tests.GoalTests.BadgeDeselects [12 ms]
Failed!  - Failed:     1, Passed:    41, Skipped:     2, Total:    44, Duration: 2 s
"""

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def pats(path: pathlib.Path) -> dict:
    return sr.load_patterns(ROOT, "flutter", str(path))


def test_pattern_tables_load() -> None:
    print("\npattern tables")
    for name, path in (("flutter", FLUTTER_PATTERNS), ("dotnet", DOTNET_PATTERNS)):
        p = pats(path)
        check(f"{name} table has all three fields",
              set(p) == {"summary_pass", "summary_fail", "failure_line"},
              f"got {sorted(p)}")
    # A pipe in a pattern silently truncates the markdown cell, so no pattern
    # may contain one. This is the failure the pack file warns about.
    for name, path in (("flutter", FLUTTER_PATTERNS), ("dotnet", DOTNET_PATTERNS)):
        raw = path.read_text(encoding="utf-8")
        rows = [ln for ln in raw.splitlines()
                if ln.startswith("| summary") or ln.startswith("| failure")]
        check(f"{name} patterns contain no bare pipe",
              all(ln.count("|") == 3 for ln in rows),
              "a '|' inside a regex ends the table cell")


def test_flutter_parse() -> None:
    print("\nflutter parsing")
    p = pats(FLUTTER_PATTERNS)

    r = sr.parse(FLUTTER_PASS, p)
    check("pass verdict", r.verdict == "PASS", r.verdict)
    check("pass counts 81", r.total == 81, str(r.total))
    check("pass reports no failures", not r.failures)

    r = sr.parse(FLUTTER_PASS_SKIPS, p)
    check("skips counted into total", r.total == 81, f"{r.passed}+{r.skipped}")
    check("skipped reported", r.skipped == 2, str(r.skipped))

    r = sr.parse(FLUTTER_FAIL, p)
    check("fail verdict", r.verdict == "FAIL", r.verdict)
    check("fail counts", (r.passed, r.failed) == (78, 2), f"{r.passed}/{r.failed}")
    check("failure names collected", len(r.failures) == 2, str(r.failures))
    check("failure name is the test, not the line",
          r.failures[0] == "test/foo_test.dart: badge tap deselects",
          r.failures[0])

    r = sr.parse(FLUTTER_ADVERSARIAL, p)
    check("last summary line wins, not a test named after it",
          r.total == 2, str(r.total))


def test_dotnet_parse() -> None:
    print("\ndotnet parsing")
    p = pats(DOTNET_PATTERNS)

    r = sr.parse(DOTNET_PASS, p)
    check("pass verdict", r.verdict == "PASS", r.verdict)
    check("pass total", r.total == 42, str(r.total))

    r = sr.parse(DOTNET_FAIL, p)
    check("fail verdict", r.verdict == "FAIL", r.verdict)
    check("fail total", r.total == 44, str(r.total))
    check("failure name", r.failures == ["MyApp.Tests.GoalTests.BadgeDeselects"],
          str(r.failures))


def test_unparsed_is_not_pass() -> None:
    print("\nunparsed is its own verdict")
    p = pats(FLUTTER_PATTERNS)
    r = sr.parse("some reporter nobody has seen\nDone.\n", p)
    check("unknown output is UNPARSED, never PASS", r.verdict == "UNPARSED",
          r.verdict)
    check("no counts invented", r.total is None, str(r.total))

    r = sr.parse("", p)
    check("empty log is UNPARSED", r.verdict == "UNPARSED", r.verdict)

    r = sr.parse(FLUTTER_PASS, {})
    check("no patterns means UNPARSED, not PASS", r.verdict == "UNPARSED",
          r.verdict)


def test_truncation_is_declared() -> None:
    print("\ntruncation")
    p = pats(FLUTTER_PATTERNS)
    many = "".join(
        f"00:05 +1 -{i}: test/t{i}_test.dart: failing {i} [E]\n"
        for i in range(1, 21)
    ) + "00:06 +1 -20: Some tests failed.\n"

    r = sr.parse(many, p, max_failures=5)
    check("failure list is capped", len(r.failures) == 5, str(len(r.failures)))
    more = sr._count_more(many, p, r, 5)
    check("the remainder is counted, not dropped", more == 15, str(more))


def test_run_keeps_output_off_stdout() -> None:
    """The whole point: 22,819 characters must not come back on stdout."""
    print("\nrun: output goes to the file, not to the caller")
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / ".omp").mkdir()
        (repo / ".omp" / "agent-config.md").write_text(
            "| Field | Value |\n|---|---|\n| active_pack | `flutter` |\n",
            encoding="utf-8")
        packdir = repo / ".claude" / "packs" / "flutter"
        packdir.mkdir(parents=True)
        (packdir / "suite-patterns.md").write_text(
            FLUTTER_PATTERNS.read_text(encoding="utf-8"), encoding="utf-8")

        noise = "\\n".join(f"00:0{i % 10} +{i}: noisy progress line {i}"
                           for i in range(2000))
        cmd = f"printf '{noise}\\n00:06 +2000: All tests passed!\\n'"

        r = subprocess.run(
            [sys.executable, str(SCRIPT), "run", "noisy", "--", cmd],
            cwd=repo, capture_output=True, text=True)

        check("exit 0 on a green suite", r.returncode == 0, str(r.returncode))
        check("stdout is one line", len(r.stdout.strip().splitlines()) == 1,
              f"{len(r.stdout.splitlines())} lines")
        check("stdout is small", len(r.stdout) < 200, f"{len(r.stdout)} chars")
        check("verdict and count present",
              "PASS" in r.stdout and "tests=2000" in r.stdout, r.stdout.strip())
        check("none of the suite output leaked",
              "noisy progress line" not in r.stdout, "output leaked to stdout")

        log = repo / "agent_states" / "suite" / "noisy" / "out"
        check("full output is on disk", log.exists() and log.stat().st_size > 10000,
              f"{log.stat().st_size if log.exists() else 0} bytes")

        # The reduction this exists for, asserted rather than asserted-about.
        ratio = log.stat().st_size / max(1, len(r.stdout))
        check("context reduction is at least 100x", ratio >= 100, f"{ratio:.0f}x")


def test_failing_command_reports_fail() -> None:
    print("\nrun: a red suite")
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        packdir = repo / ".claude" / "packs" / "flutter"
        packdir.mkdir(parents=True)
        (packdir / "suite-patterns.md").write_text(
            FLUTTER_PATTERNS.read_text(encoding="utf-8"), encoding="utf-8")

        body = FLUTTER_FAIL.replace("\n", "\\n")
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "run", "red", "--",
             f"printf '{body}'; exit 1"],
            cwd=repo, capture_output=True, text=True)

        check("exit 2 on a red suite", r.returncode == 2, str(r.returncode))
        check("failing test names surfaced", "badge tap deselects" in r.stdout,
              r.stdout.strip())
        check("failed count reported", "failed=2" in r.stdout, r.stdout.strip())


def test_unparsed_exit_code() -> None:
    print("\nrun: a reporter nobody has patterns for")
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        packdir = repo / ".claude" / "packs" / "flutter"
        packdir.mkdir(parents=True)
        (packdir / "suite-patterns.md").write_text(
            FLUTTER_PATTERNS.read_text(encoding="utf-8"), encoding="utf-8")

        r = subprocess.run(
            [sys.executable, str(SCRIPT), "run", "odd", "--",
             "printf 'ran 5 examples, 0 failures\\n'"],
            cwd=repo, capture_output=True, text=True)

        check("exit 4, not 0, on an unrecognised reporter", r.returncode == 4,
              str(r.returncode))
        check("says UNPARSED", "UNPARSED" in r.stdout, r.stdout.strip())
        check("reports the raw exit code instead of a verdict",
              "exit=0" in r.stdout, r.stdout.strip())


def main() -> int:
    print("suite-result")
    test_pattern_tables_load()
    test_flutter_parse()
    test_dotnet_parse()
    test_unparsed_is_not_pass()
    test_truncation_is_declared()
    test_run_keeps_output_off_stdout()
    test_failing_command_reports_fail()
    test_unparsed_exit_code()

    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all suite-result checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
