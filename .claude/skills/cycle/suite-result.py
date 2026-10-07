#!/usr/bin/env python3
"""suite-result — learn whether the suite passed without reading the suite.

Measured, v0 run 2: the orchestrator ran

    flutter test test/ui/setup/ --reporter compact 2>&1 | tail -5

and **22,819 characters** entered its context. The `tail -5` bounded nothing —
the harness captures the command's full output regardless of what the pipeline
does with it. It did this twice, ~11k tokens, to learn that 81 tests passed.
Across that run, tool output was 52.6% of everything that accumulated in the
orchestrator's transcript, and this was its largest single contributor.

`run-suite.sh` already solved half of this: it captures to a file and `check`
prints a bounded tail. But a tail is still prose, it still scales with the
reporter's verbosity, and nothing stops an agent running the bare command
instead — which is exactly what happened. This closes the other half:

  * **The command's output never reaches stdout.** It goes to a file; one line
    comes back. There is nothing for a harness to expand.
  * **The verdict is parsed, not tailed.** `tests=3891 failed=0` is the fact the
    caller wanted; the 18,800 lines it was extracted from are on disk if anyone
    needs them.
  * **Stack-specific patterns live in the pack**, not here. This file knows how
    to run a command and read a table; it knows nothing about Dart or .NET.

    python3 .claude/skills/cycle/suite-result.py run  <name> -- <cmd...>
    python3 .claude/skills/cycle/suite-result.py check <name>
    python3 .claude/skills/cycle/suite-result.py parse <logfile>

`run` and `check` share `run-suite.sh`'s state directory, so the two tools read
each other's runs: start a suite with `run-suite.sh start`, read its verdict
with `suite-result.py check`.

Exit 0 passed, 2 failed, 3 still running, 4 finished but unparseable, 1 usage.

**4 is not 2.** If the patterns do not match, this reports `UNPARSED` and the
raw exit code rather than inferring a verdict from it. A suite that exits 0
having run no tests, and a suite that passed, are different facts; so are "the
suite failed" and "this tool does not understand this reporter". The framework
has been bitten twice by a tool that reported a confident zero where it had no
measurement, and that is what the distinct code is for.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
import time

DEFAULT_MAX_FAILURES = 15


# ── locating things ──────────────────────────────────────────────────────────

def repo_root() -> pathlib.Path:
    """Git root, so this resolves the same from any subdirectory.

    The cycle skill calls every scoped script by its project-relative path, and
    a cycle can be started from a subdirectory; deriving paths from cwd is how
    the gitignore guard once read no config and concluded no vault.
    """
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("suite-result: not in a git repo")
    return pathlib.Path(r.stdout.strip())


def active_pack(root: pathlib.Path) -> str:
    """Read § Active Pack from .omp/agent-config.md. Defaults to flutter."""
    cfg = root / ".omp" / "agent-config.md"
    try:
        text = cfg.read_text(encoding="utf-8")
    except OSError:
        return "flutter"
    m = re.search(r"^\|\s*active_pack\s*\|\s*`?([A-Za-z0-9_-]+)`?\s*\|",
                  text, re.MULTILINE)
    return m.group(1) if m else "flutter"


def load_patterns(root: pathlib.Path, pack: str,
                  explicit: str | None) -> dict[str, re.Pattern[str]]:
    """Read `| field | \\`regex\\` |` rows out of the pack's pattern table.

    A markdown table because every other thing a pack publishes is one, and the
    person editing it is reading the rest of the pack. Rows whose regex does not
    compile are skipped with a warning rather than taking the run down: a broken
    pattern should cost you the parse, not the suite.
    """
    path = (pathlib.Path(explicit) if explicit
            else root / ".claude" / "packs" / pack / "suite-patterns.md")
    if not path.is_absolute():
        path = root / path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    out: dict[str, re.Pattern[str]] = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*([a-z_]+)\s*\|\s*`(.+?)`\s*\|\s*$", line.strip())
        if not m:
            continue
        field, pattern = m.group(1), m.group(2)
        try:
            out[field] = re.compile(pattern)
        except re.error as exc:
            print(f"suite-result: pattern '{field}' does not compile ({exc}) "
                  f"— skipped", file=sys.stderr)
    return out


# ── parsing ──────────────────────────────────────────────────────────────────

class Result:
    def __init__(self) -> None:
        self.verdict = "UNPARSED"
        self.passed: int | None = None
        self.failed: int | None = None
        self.skipped: int | None = None
        self.failures: list[str] = []

    @property
    def total(self) -> int | None:
        if self.passed is None:
            return None
        return self.passed + (self.failed or 0) + (self.skipped or 0)


def _int(m: re.Match[str], name: str) -> int | None:
    """A pattern need not declare every group; a missing one is 'not reported',
    not zero. `skipped=0` and 'this reporter does not mention skips' differ."""
    try:
        v = m.group(name)
    except IndexError:
        return None
    return int(v) if v is not None else None


def parse(text: str, pats: dict[str, re.Pattern[str]],
          max_failures: int = DEFAULT_MAX_FAILURES) -> Result:
    """Scan the log for a summary line, then collect bounded failure detail.

    Scans **backwards** for the summary. A suite prints progress lines that look
    like its summary line for the whole run; the last match is the real one, and
    an earlier match is a test whose name happens to contain the wording.
    """
    res = Result()
    lines = text.splitlines()

    for name, verdict in (("summary_pass", "PASS"), ("summary_fail", "FAIL")):
        pat = pats.get(name)
        if not pat:
            continue
        for line in reversed(lines):
            m = pat.search(line)
            if not m:
                continue
            res.verdict = verdict
            res.passed = _int(m, "passed")
            res.failed = _int(m, "failed")
            res.skipped = _int(m, "skipped")
            break
        if res.verdict != "UNPARSED":
            break

    # Failure detail only when it is the thing the caller needs. On a green run
    # it is noise, which is the whole point of this script.
    if res.verdict == "FAIL" and "failure_line" in pats:
        pat = pats["failure_line"]
        seen: set[str] = set()
        for line in lines:
            m = pat.search(line)
            if not m:
                continue
            try:
                name = m.group("test").strip()
            except IndexError:
                name = line.strip()
            if name in seen:
                continue
            seen.add(name)
            res.failures.append(name)
            if len(res.failures) >= max_failures:
                break
    return res


# ── reporting ────────────────────────────────────────────────────────────────

def emit(name: str, res: Result, elapsed: int | None, log: pathlib.Path,
         rc: int | None, more: int = 0) -> int:
    bits = [f"SUITE {name} {res.verdict}"]
    if res.total is not None:
        bits.append(f"tests={res.total}")
    if res.failed is not None:
        bits.append(f"failed={res.failed}")
    if res.skipped:
        bits.append(f"skipped={res.skipped}")
    if elapsed is not None:
        bits.append(f"elapsed={elapsed}s")
    if res.verdict == "UNPARSED" and rc is not None:
        bits.append(f"exit={rc}")
    bits.append(f"log={log}")
    print(" ".join(bits))

    for f in res.failures:
        print(f"  FAILED {f}")
    if more > 0:
        print(f"  ... and {more} more — see {log}")

    if res.verdict == "PASS":
        return 0
    if res.verdict == "FAIL":
        return 2
    print(f"suite-result: no pattern matched this reporter's output. "
          f"Read {log}, and add a pattern to the pack if this reporter is "
          f"one the project uses.", file=sys.stderr)
    return 4


# ── subcommands ──────────────────────────────────────────────────────────────

def state_dir(root: pathlib.Path, name: str) -> pathlib.Path:
    """Shared with run-suite.sh on purpose — one place suites are recorded."""
    return root / "agent_states" / "suite" / name


def cmd_run(args: argparse.Namespace, root: pathlib.Path,
            pats: dict[str, re.Pattern[str]]) -> int:
    if not args.command:
        print("suite-result: no command given after --", file=sys.stderr)
        return 1

    sd = state_dir(root, args.name)
    sd.mkdir(parents=True, exist_ok=True)
    log = sd / "out"

    began = time.time()
    with log.open("w", encoding="utf-8", errors="replace") as fh:
        # Output goes to the file, never to our stdout. This is the line that
        # keeps 22,819 characters out of a context window.
        proc = subprocess.run(" ".join(args.command), shell=True,
                              stdout=fh, stderr=subprocess.STDOUT, cwd=root)
    elapsed = int(time.time() - began)
    (sd / "rc").write_text(f"{proc.returncode}\n", encoding="utf-8")

    text = log.read_text(encoding="utf-8", errors="replace")
    res = parse(text, pats, args.max_failures)
    more = _count_more(text, pats, res, args.max_failures)
    return emit(args.name, res, elapsed, log, proc.returncode, more)


def cmd_check(args: argparse.Namespace, root: pathlib.Path,
              pats: dict[str, re.Pattern[str]]) -> int:
    sd = state_dir(root, args.name)
    log = sd / "out"
    if not log.exists():
        print(f"suite-result: no run named '{args.name}' "
              f"(nothing at {log})", file=sys.stderr)
        return 1
    if not (sd / "rc").exists():
        # run-suite.sh writes rc last; its absence means still in flight.
        started = sd / "started_at"
        age = ""
        if started.exists():
            try:
                age = f" for {int(time.time()) - int(started.read_text().strip())}s"
            except ValueError:
                age = ""
        print(f"SUITE {args.name} RUNNING{age} log={log}")
        return 3

    rc = None
    try:
        rc = int((sd / "rc").read_text().strip())
    except (OSError, ValueError):
        pass
    elapsed = None
    try:
        elapsed = (int((sd / "ended_at").read_text().strip())
                   - int((sd / "started_at").read_text().strip()))
    except (OSError, ValueError):
        pass

    text = log.read_text(encoding="utf-8", errors="replace")
    res = parse(text, pats, args.max_failures)
    more = _count_more(text, pats, res, args.max_failures)
    return emit(args.name, res, elapsed, log, rc, more)


def cmd_parse(args: argparse.Namespace, root: pathlib.Path,
              pats: dict[str, re.Pattern[str]]) -> int:
    log = pathlib.Path(args.logfile)
    if not log.is_absolute():
        log = root / log
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"suite-result: cannot read {log} ({exc})", file=sys.stderr)
        return 1
    res = parse(text, pats, args.max_failures)
    more = _count_more(text, pats, res, args.max_failures)
    return emit(log.stem, res, None, log, None, more)


def _count_more(text: str, pats: dict[str, re.Pattern[str]], res: Result,
                cap: int) -> int:
    """How many failures were truncated, so the caller knows the list is partial.

    Reporting 15 of 40 without saying so reads as 15, and a caller acting on a
    truncated list is the same class of error as a tool reporting zero where it
    had no measurement.
    """
    if res.verdict != "FAIL" or "failure_line" not in pats:
        return 0
    pat = pats["failure_line"]
    seen: set[str] = set()
    for line in text.splitlines():
        m = pat.search(line)
        if not m:
            continue
        try:
            seen.add(m.group("test").strip())
        except IndexError:
            seen.add(line.strip())
    return max(0, len(seen) - len(res.failures))


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True, description=__doc__.split("\n")[0])
    ap.add_argument("--pack", help="override the pack whose patterns are used")
    ap.add_argument("--patterns", help="path to a pattern file, overriding the pack")
    ap.add_argument("--max-failures", type=int, default=DEFAULT_MAX_FAILURES,
                    help=f"failure lines to print (default {DEFAULT_MAX_FAILURES})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run a suite; print one line")
    p_run.add_argument("name")
    p_run.add_argument("command", nargs=argparse.REMAINDER)

    p_check = sub.add_parser("check", help="read a run by name")
    p_check.add_argument("name")

    p_parse = sub.add_parser("parse", help="parse an existing log file")
    p_parse.add_argument("logfile")

    args = ap.parse_args()

    if args.cmd == "run":
        if args.command and args.command[0] == "--":
            args.command = args.command[1:]

    root = repo_root()
    pack = args.pack or active_pack(root)
    pats = load_patterns(root, pack, args.patterns)
    if not pats:
        print(f"suite-result: no usable patterns for pack '{pack}'. Expected "
              f".claude/packs/{pack}/suite-patterns.md", file=sys.stderr)

    if args.cmd == "run":
        return cmd_run(args, root, pats)
    if args.cmd == "check":
        return cmd_check(args, root, pats)
    return cmd_parse(args, root, pats)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
