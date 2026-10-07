#!/usr/bin/env python3
"""evidence.py — establish an evidentiary claim without going through a shell.

Written after a `/refine` session that produced roughly **ten instrumentation
errors against zero wrong claims about the codebase**. The reasoning from
evidence held up; the gathering of evidence did not. Two of the ten were one step
from being filed as GitHub issues — including a bug report asserting that "every
`session_set` write has been rejected" for want of an INSERT policy, concluded
from reading 1 of 26 migration files.

Four of those failure classes are the same bug four times: **grep was reached
through a shell, and a shell is a lossy channel for both the pattern and the
verdict.**

    grep -rn "epic:" . --include=*.md         # zsh ate the glob; the command
                                              # never ran, and inside an && chain
                                              # that reads as "no results"
    grep -rn "foo" lib | head -20; echo $?    # always 0 — that is head's status
    grep -c PATTERN file                      # counts matching LINES, not matches
    grep -rn X missing/dir                    # exit 2, read as exit 1 "no match"

So this is not a safer grep wrapper. **No subcommand here invokes a shell, and
none invokes grep.** Patterns are `re`, corpora are resolved with `pathlib`, and
every verdict is a word on the first line of stdout — not an exit status the
caller has to remember not to pipe.

    $ evidence.py absence --pattern 'INSERT POLICY' supabase/migrations
    ABSENCE verdict=present pattern=INSERT POLICY unit=paragraph corpus=26/26 files=26 hits=1 occurrences=2
    supabase/migrations/0019_session_set_policies.sql:41

    $ evidence.py absence --pattern 'INSERT POLICY' supabase/migrations/0001_init.sql
    ABSENCE verdict=absent pattern=INSERT POLICY unit=paragraph corpus=1/1 files=1 hits=0 occurrences=0

The second answer is true and useless, and it says so: `corpus=1/1` is the whole
claim's scope, printed next to the verdict. An absence claim without its corpus
is how one of 26 migrations became "the schema".

## Verbs

    absence       a pattern is / is not present in an explicitly named corpus
    anchor        print the exact bytes of a region, to be copied into an edit
    guarded-edit  apply (tag, old, new) edits only if every anchor is unique
    tables        every Markdown table row's cell count matches its header's
    cite          a quoted phrase actually appears in the source it is credited to
    round-trip    what was pushed is what the destination now returns
    enumerate     per-item disposition between two texts: kept/replaced/added/deleted

## Exit codes

    0  determinate — the claim holds
    1  determinate — the claim does not hold
    2  bad usage
    3  **could not determine**

`1` carries the repo's "refused or no hits" meaning (`symbol-refs.py`,
`pitfalls.py`), not grep's. For `absence`, `1` means the pattern is **present** —
the inverse of grep's `1`. That is why `verdict=` on stdout is the primary channel
and the exit code the branchable secondary: a caller with grep habits who reads
only the status gets the right answer backwards, and a caller who pipes to `head`
still sees the word.

**A corpus that did not fully resolve exits 3, even when the part that did
resolve had no hits.** A missing, unreadable or undecodable path is reported on an
`unresolved:` line and never collapses into `absent`. This is the one invariant
the whole file exists for.

**An empty corpus is a usage error, not an empty result.** `absence --pattern X`
with no paths exits 2. "State your corpus" is enforced by argparse rather than by
a sentence in a skill file.

**Nothing here accepts an expected total.** Predicted item counts were wrong three
times in that session while the content was right, so `enumerate` reports every
item's disposition and takes no count to check against.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys

OK, NO, USAGE, UNDETERMINED = 0, 1, 2, 3

# Walked past rather than searched. Named in the header when non-empty, because a
# corpus that silently skipped a directory is a corpus that lied about its scope.
PRUNE = frozenset((
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".dart_tool",
    ".venv", "venv", "build", ".next", ".gradle", "Pods",
))


# --------------------------------------------------------------------------- #
# corpus
# --------------------------------------------------------------------------- #

class Corpus:
    """An explicitly named set of files, plus everything that did not resolve.

    `named` is what the caller asked for; `files` is what was actually read;
    `unresolved` is every path that was named and could not be. A caller that
    reports `absent` while `unresolved` is non-empty is making the exact mistake
    this class exists to prevent, so `determinate` is the only sanctioned read.
    """

    def __init__(self, named: list[str], suffixes: list[str] | None):
        self.named = named
        self.suffixes = [s if s.startswith(".") else "." + s for s in (suffixes or [])]
        self.files: list[pathlib.Path] = []
        self.unresolved: list[str] = []
        self.pruned: set[str] = set()
        self.texts: dict[pathlib.Path, str] = {}
        for n in named:
            self._add(n)

    def _wanted(self, p: pathlib.Path) -> bool:
        return not self.suffixes or p.suffix in self.suffixes

    def _add(self, name: str) -> None:
        p = pathlib.Path(os.path.expanduser(name))
        try:
            if p.is_file():
                # An explicitly named file is always read; the suffix filter
                # narrows a directory walk, it does not veto a direct request.
                self._read(p, name)
                return
            if p.is_dir():
                found = False
                for root, dirs, names in os.walk(p):
                    keep = [d for d in dirs if d not in PRUNE]
                    self.pruned |= {d for d in dirs if d in PRUNE}
                    dirs[:] = keep
                    for fn in sorted(names):
                        f = pathlib.Path(root) / fn
                        if self._wanted(f):
                            found = True
                            self._read(f, name)
                if not found and self.suffixes:
                    # A filter that matched nothing is not an absence result.
                    self.unresolved.append(f"{name} (no file matching {','.join(self.suffixes)})")
                return
        except OSError as e:
            self.unresolved.append(f"{name} ({e.strerror or e})")
            return
        self.unresolved.append(f"{name} (no such path)")

    def _read(self, p: pathlib.Path, named: str) -> None:
        try:
            raw = p.read_bytes()
        except OSError as e:
            self.unresolved.append(f"{p} ({e.strerror or e})")
            return
        if b"\x00" in raw[:8192]:
            self.unresolved.append(f"{p} (binary)")
            return
        try:
            self.texts[p] = raw.decode("utf-8")
        except UnicodeDecodeError:
            self.unresolved.append(f"{p} (not utf-8)")
            return
        self.files.append(p)

    @property
    def resolved(self) -> str:
        return f"{len(self.files)}/{len(self.files) + len(self.unresolved)}"

    @property
    def determinate(self) -> bool:
        return not self.unresolved


# --------------------------------------------------------------------------- #
# units
# --------------------------------------------------------------------------- #

WS = re.compile(r"\s+")


def normalise(s: str, fold: bool) -> str:
    """Collapse every whitespace run to one space. Optionally case-fold.

    This is what lets a phrase match across a line wrap. Four gate failures in
    one session came from a qualifier and the phrase it qualified landing on
    different lines:

        line 203:   ... ⚠️ **Not a Supabase
        line 204:   anonymous session**: `enable_anonymous_sign_ins = false` ...
    """
    out = WS.sub(" ", s).strip()
    return out.lower() if fold else out


def units(text: str, unit: str) -> list[tuple[int, int, str]]:
    """`(first_line, last_line, text)` per unit, 1-indexed and inclusive.

    `paragraph` is the default everywhere, and deliberately so: a default that
    has to be remembered is the bug. A paragraph is a blank-line-delimited block,
    so a wrapped bullet, a wrapped table row and a quoted block each stay whole.
    """
    lines = text.splitlines()
    if unit == "line":
        return [(i + 1, i + 1, ln) for i, ln in enumerate(lines)]
    out: list[tuple[int, int, str]] = []
    start, buf = None, []
    for i, ln in enumerate(lines, 1):
        if ln.strip():
            if start is None:
                start = i
            buf.append(ln)
        elif start is not None:
            out.append((start, i - 1, "\n".join(buf)))
            start, buf = None, []
    if start is not None:
        out.append((start, len(lines), "\n".join(buf)))
    return out


def compile_pattern(pattern: str, literal: bool, fold: bool) -> re.Pattern[str]:
    """A pattern matched against whitespace-normalised text.

    With `--literal`, interior whitespace in the needle becomes `\\s+` so a
    needle that is itself wrapped in the source still matches.
    """
    if literal:
        src = r"\s+".join(re.escape(w) for w in pattern.split())
    else:
        src = pattern
    return re.compile(src, re.IGNORECASE if fold else 0)


# --------------------------------------------------------------------------- #
# absence
# --------------------------------------------------------------------------- #

def cmd_absence(a: argparse.Namespace) -> int:
    if not a.paths:
        print("ABSENCE verdict=usage — name at least one corpus path", file=sys.stderr)
        return USAGE
    fold = not a.case_sensitive
    corpus = Corpus(a.paths, a.suffix)
    try:
        pat = compile_pattern(a.pattern, a.literal, fold)
        allowed = [compile_pattern(c, a.literal_context, fold) for c in (a.allowed_context or [])]
    except re.error as e:
        print(f"ABSENCE verdict=usage — bad pattern: {e}", file=sys.stderr)
        return USAGE

    hits, occurrences, rows, excused = 0, 0, [], []
    for p in corpus.files:
        for first, last, body in units(corpus.texts[p], a.unit):
            flat = normalise(body, fold)
            found = pat.findall(flat)
            if not found:
                continue
            if allowed and any(c.search(flat) for c in allowed):
                excused.append(f"{p}:{first}-{last}")
                continue
            hits += 1
            occurrences += len(found)
            rows.append(f"{p}:{first}" + (f"-{last}" if last != first else ""))

    verdict = "undetermined" if not corpus.determinate else ("present" if hits else "absent")
    head = (f"ABSENCE verdict={verdict} pattern={a.pattern} unit={a.unit} "
            f"corpus={corpus.resolved} files={len(corpus.files)} "
            f"hits={hits} occurrences={occurrences}")
    if corpus.pruned:
        head += f" pruned={','.join(sorted(corpus.pruned))}"
    print(head)
    for r in rows[: a.max_rows]:
        print(r)
    if len(rows) > a.max_rows:
        print(f"... {len(rows) - a.max_rows} more")
    if excused:
        # Printed, never merely counted: an excused unit is the one place a
        # paragraph-scoped allowed-context could be too generous, so the caller
        # gets the line range to eyeball rather than a bare verdict.
        print(f"excused-by-context: {' '.join(excused[: a.max_rows])}")
    for u in corpus.unresolved:
        print(f"unresolved: {u}")
    if not corpus.determinate:
        return UNDETERMINED
    return NO if hits else OK


# --------------------------------------------------------------------------- #
# anchor
# --------------------------------------------------------------------------- #

def cmd_anchor(a: argparse.Namespace) -> int:
    """Print bytes to be copied into an edit, with uniqueness proved at print time.

    `guarded-edit` catches a retyped anchor, which is the right outcome and was
    reached five times in one session — each time costing a turn, each time
    because an `old` string was written from recall of prose authored minutes
    earlier, usually with a line wrap guessed wrong. This is the other half:
    read the file and copy the bytes, as an operation rather than an exhortation.
    """
    try:
        text = pathlib.Path(a.file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"ANCHOR verdict=undetermined — {a.file}: {e}", file=sys.stderr)
        return UNDETERMINED
    lines = text.splitlines(keepends=True)

    if a.lines:
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", a.lines)
        if not m:
            print("ANCHOR verdict=usage — --lines wants N or N-M", file=sys.stderr)
            return USAGE
        first = int(m.group(1))
        last = int(m.group(2) or m.group(1))
        if first < 1 or last < first or last > len(lines):
            print(f"ANCHOR verdict=usage — {a.lines} outside 1-{len(lines)}", file=sys.stderr)
            return USAGE
    else:
        try:
            # MULTILINE because an anchor is a region of lines, so `^...$` is the
            # first thing a caller writes. Without it this silently reported
            # occurrences=0 for a line that was plainly in the file.
            pat = re.compile(a.match, re.MULTILINE)
        except re.error as e:
            print(f"ANCHOR verdict=usage — bad pattern: {e}", file=sys.stderr)
            return USAGE
        found = [m for m in pat.finditer(text)]
        if len(found) != 1:
            # "not-found" and "ambiguous" are different problems with different
            # fixes — widen the pattern, or narrow it — so they are not one word.
            verdict = "not-found" if not found else "ambiguous"
            print(f"ANCHOR verdict={verdict} occurrences={len(found)} match={a.match}")
            for m in found[:10]:
                print(f"{a.file}:{text.count(chr(10), 0, m.start()) + 1}")
            return NO
        first = text.count("\n", 0, found[0].start()) + 1
        last = text.count("\n", 0, found[0].end()) + 1

    body = "".join(lines[first - 1:last])
    # Trailing newline excluded so the anchor is a region, not a region plus a
    # separator the edit would then have to reproduce exactly.
    body = body[:-1] if body.endswith("\n") else body
    n = text.count(body)
    print(f"ANCHOR occurrences={n} lines={first}-{last} bytes={len(body.encode())} file={a.file}")
    print("--- anchor ---")
    print(body)
    print("--- end ---")
    return OK if n == 1 else NO


# --------------------------------------------------------------------------- #
# guarded-edit
# --------------------------------------------------------------------------- #

def guarded_edit(text: str, edits: list[dict]) -> tuple[str | None, list[tuple[str, int]]]:
    """`(new_text, counts)`. `new_text` is None unless every anchor is unique.

    All-or-nothing by construction: every count is taken against the original
    bytes before any substitution, so a batch cannot half-apply.
    """
    counts = [(e.get("tag") or f"#{i}", text.count(e["old"])) for i, e in enumerate(edits, 1)]
    if any(c != 1 for _, c in counts):
        return None, counts
    out = text
    for e in edits:
        out = out.replace(e["old"], e["new"], 1)
    return out, counts


def cmd_guarded_edit(a: argparse.Namespace) -> int:
    try:
        raw = sys.stdin.read() if a.edits == "-" else pathlib.Path(a.edits).read_text("utf-8")
        edits = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        print(f"GUARDED-EDIT verdict=usage — edits: {e}", file=sys.stderr)
        return USAGE
    if not isinstance(edits, list) or not edits:
        print("GUARDED-EDIT verdict=usage — want a non-empty JSON array of {tag,old,new}",
              file=sys.stderr)
        return USAGE
    for e in edits:
        if not isinstance(e, dict) or "old" not in e or "new" not in e:
            print("GUARDED-EDIT verdict=usage — every edit needs 'old' and 'new'", file=sys.stderr)
            return USAGE

    path = pathlib.Path(a.file)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"GUARDED-EDIT verdict=undetermined — {a.file}: {e}", file=sys.stderr)
        return UNDETERMINED

    new, counts = guarded_edit(text, edits)
    bad = [(t, c) for t, c in counts if c != 1]
    verdict = "aborted" if bad else ("applied" if a.apply else "checked")
    print(f"GUARDED-EDIT verdict={verdict} edits={len(edits)} "
          f"ok={len(counts) - len(bad)} bad={len(bad)} file={a.file}")
    for t, c in counts:
        print(f"  {t}: occurrences={c}" + ("" if c == 1 else "  <-- not unique"))
    if bad:
        print("Nothing was written. Copy the anchor's bytes out of the file rather than "
              "retyping them — `evidence.py anchor` prints them with uniqueness proved.")
        return NO
    if a.apply:
        try:
            path.write_text(new or "", encoding="utf-8")
        except OSError as e:
            print(f"GUARDED-EDIT verdict=undetermined — write failed: {e}", file=sys.stderr)
            return UNDETERMINED
    return OK


# --------------------------------------------------------------------------- #
# tables
# --------------------------------------------------------------------------- #

FENCE = re.compile(r"^\s{0,3}(```|~~~)")
DELIM = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")


def cells_strict(row: str) -> int:
    """Cells when `\\|` is honoured as a literal and backtick spans are opaque."""
    parts, cur, i, tick = [], [], 0, 0
    while i < len(row):
        ch = row[i]
        if ch == "\\" and i + 1 < len(row):
            cur.append(row[i:i + 2]); i += 2; continue
        if ch == "`":
            run = len(row[i:]) - len(row[i:].lstrip("`"))
            tick = 0 if tick == run else (run if tick == 0 else tick)
            cur.append(row[i:i + run]); i += run; continue
        if ch == "|" and tick == 0:
            parts.append("".join(cur)); cur = []; i += 1; continue
        cur.append(ch); i += 1
    parts.append("".join(cur))
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return len(parts)


def cells_raw(row: str) -> int:
    """Cells when every `|` is a boundary, backslashes and backticks ignored."""
    parts = row.split("|")
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return len(parts)


PIPE_RUN = re.compile(r"(?:\\\|){2,}")


def table_faults(text: str) -> list[tuple[int, int, int, int, str]]:
    """`(line, header_cells, strict_cells, raw_cells, why)` per faulty row.

    Two fault kinds, and the split matters more than it looks:

    - **`cells`** — the strict count, which honours `\\|` as a literal and treats
      a backtick span as opaque, disagrees with the header. An unambiguous
      structural fault.
    - **`pipe-run`** — the strict count agrees but the row carries a run of two
      or more consecutive escaped pipes (`\\|\\|`) *and* its raw pipe count
      disagrees with the header. This is the shape of the observed defect: six
      raw pipes against a four-pipe header, which GitHub rendered as a
      five-column row inside a three-column table — visible garbage, failing
      silently.

    The second rule is deliberately narrow rather than "any raw disagreement".
    A single `\\|` in a cell is idiomatic and renders correctly, as does a pipe
    inside a code span; flagging either would make this gate cry wolf, and a
    gate whose failures get dismissed as probe artifacts is the ninth failure
    class this file was written against.
    """
    faults: list[tuple[int, int, int, int, str]] = []
    lines = text.splitlines()
    fence: str | None = None
    header: int | None = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = FENCE.match(ln)
        if m:
            if fence is None:
                fence = m.group(1)
            elif ln.strip().startswith(fence):
                fence = None
            header = None
            i += 1
            continue
        if fence is not None or "|" not in ln:
            header = None
            i += 1
            continue
        if header is None:
            if i + 1 < len(lines) and DELIM.match(lines[i + 1]) and "|" in lines[i + 1]:
                header = cells_strict(ln)
                i += 2
                continue
            i += 1
            continue
        s, r = cells_strict(ln), cells_raw(ln)
        if s != header:
            faults.append((i + 1, header, s, r, "cells"))
        elif r != header and PIPE_RUN.search(ln):
            faults.append((i + 1, header, s, r, "pipe-run"))
        i += 1
    return faults


def cmd_tables(a: argparse.Namespace) -> int:
    if not a.paths:
        print("TABLES verdict=usage — name at least one file", file=sys.stderr)
        return USAGE
    corpus = Corpus(a.paths, a.suffix)
    faults, rows = 0, []
    for p in corpus.files:
        for line, head, s, r, why in table_faults(corpus.texts[p]):
            faults += 1
            rows.append(f"{p}:{line} fault={why} header={head} cells={s} cells_raw={r}")
    verdict = ("undetermined" if not corpus.determinate
               else ("malformed" if faults else "wellformed"))
    print(f"TABLES verdict={verdict} corpus={corpus.resolved} "
          f"files={len(corpus.files)} bad_rows={faults}")
    for r in rows[: a.max_rows]:
        print(r)
    for u in corpus.unresolved:
        print(f"unresolved: {u}")
    if not corpus.determinate:
        return UNDETERMINED
    return NO if faults else OK


# --------------------------------------------------------------------------- #
# cite
# --------------------------------------------------------------------------- #

def _read_arg(value: str, label: str) -> tuple[str | None, str]:
    if value == "-":
        return sys.stdin.read(), f"<{label}:stdin>"
    p = pathlib.Path(os.path.expanduser(value))
    if p.is_file():
        try:
            return p.read_text(encoding="utf-8"), str(p)
        except (OSError, UnicodeDecodeError):
            return None, str(p)
    return None, value


def cmd_cite(a: argparse.Namespace) -> int:
    """Check a citation independently of the claim it supports.

    A grounding subagent once attributed a sentence to a GitHub issue's body when
    it had read it from a source-code comment one row earlier in its own report.
    The phrase appeared **0 times** in that issue. Its conclusion survived on
    other evidence — which is the point: a conclusion and its citation fail
    independently, so they have to be checked independently.
    """
    phrase = a.phrase
    if phrase == "-":
        phrase = sys.stdin.read()
    source, label = _read_arg(a.source, "source")
    if source is None:
        print(f"CITE verdict=undetermined hits=0 source={label} — unreadable", file=sys.stderr)
        return UNDETERMINED
    if not source.strip():
        print(f"CITE verdict=undetermined hits=0 source={label} — empty", file=sys.stderr)
        return UNDETERMINED
    needle = normalise(phrase, fold=not a.case_sensitive)
    if not needle:
        print("CITE verdict=usage — empty phrase", file=sys.stderr)
        return USAGE
    hay = normalise(source, fold=not a.case_sensitive)
    hits = hay.count(needle)
    verdict = "supported" if hits else "unsupported"
    print(f"CITE verdict={verdict} hits={hits} source={label} "
          f"chars={len(needle)} normalised=whitespace"
          + ("" if a.case_sensitive else ",case"))
    if not hits:
        print("The citation is struck; the claim reverts to unverified, not false. "
              "Re-ground it from a source read directly, or turn it into a question.")
    return OK if hits else NO


# --------------------------------------------------------------------------- #
# round-trip
# --------------------------------------------------------------------------- #

def canonical(s: str) -> str:
    """Trailing whitespace per line and the trailing newline, normalised. Nothing else."""
    return "\n".join(ln.rstrip() for ln in s.splitlines()).rstrip("\n")


def cmd_round_trip(a: argparse.Namespace) -> int:
    """Compare what was pushed against what the destination now returns.

    A returned URL is acceptance, not content. The read-back is a command the
    caller names, so this script knows nothing about `gh`:

        round-trip --local body.md --remote-cmd 'gh issue view 412 --json body -q .body'
    """
    local, label = _read_arg(a.local, "local")
    if local is None:
        print(f"ROUND-TRIP verdict=undetermined — local unreadable: {label}", file=sys.stderr)
        return UNDETERMINED
    try:
        r = subprocess.run(a.remote_cmd, shell=True, capture_output=True, text=True,
                           timeout=a.timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"ROUND-TRIP verdict=undetermined — read-back failed: {e}", file=sys.stderr)
        return UNDETERMINED
    if r.returncode != 0 or not r.stdout.strip():
        # A failed or empty read-back is never "identical". That conflation is
        # the whole failure this verb exists to prevent.
        print(f"ROUND-TRIP verdict=undetermined rc={r.returncode} "
              f"bytes_remote={len(r.stdout)} — read-back produced nothing usable")
        if r.stderr.strip():
            print(r.stderr.strip()[:400])
        return UNDETERMINED

    lo, re_ = canonical(local), canonical(r.stdout)
    same = lo == re_
    print(f"ROUND-TRIP verdict={'identical' if same else 'differs'} "
          f"bytes_local={len(lo.encode())} bytes_remote={len(re_.encode())} local={label}")
    if not same:
        diff = list(difflib.unified_diff(lo.splitlines(), re_.splitlines(),
                                         "local", "remote", lineterm="", n=1))
        for ln in diff[: a.max_rows]:
            print(ln)
        if len(diff) > a.max_rows:
            print(f"... {len(diff) - a.max_rows} more diff lines")
    return OK if same else NO


# --------------------------------------------------------------------------- #
# enumerate
# --------------------------------------------------------------------------- #

CHECKBOX = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+(.*)$")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")


def items(text: str, unit: str) -> list[str]:
    """List items, each joined with its continuation lines.

    A wrapped item is one item. Counting them per-line is how a four-item list
    was reported for a six-item one.
    """
    pat = CHECKBOX if unit == "checkbox" else BULLET
    out: list[str] = []
    for ln in text.splitlines():
        m = pat.match(ln)
        if m:
            out.append(m.group(1).strip())
        elif out and ln.strip() and not ln[:1].strip():
            out[-1] += " " + ln.strip()
        elif not ln.strip():
            continue
    return [normalise(i, fold=True) for i in out if normalise(i, fold=True)]


def dispositions(before: list[str], after: list[str], threshold: float) -> list[tuple[str, str]]:
    """`(disposition, item)` for every item on either side.

    Enumerates rather than counts. Predicted totals were wrong three times in one
    session while the content was right, and only an enumeration told an
    arithmetic error apart from an edit defect.
    """
    remaining = list(after)
    out: list[tuple[str, str]] = []
    for b in before:
        if b in remaining:
            remaining.remove(b)
            out.append(("kept", b))
            continue
        best, score = None, 0.0
        for c in remaining:
            s = difflib.SequenceMatcher(None, b, c).ratio()
            if s > score:
                best, score = c, s
        if best is not None and score >= threshold:
            remaining.remove(best)
            out.append(("replaced", b))
        else:
            out.append(("deleted", b))
    out.extend(("added", x) for x in remaining)
    return out


def cmd_enumerate(a: argparse.Namespace) -> int:
    before_text, blabel = _read_arg(a.before, "before")
    if before_text is None:
        print(f"ENUMERATE verdict=undetermined — unreadable: {blabel}", file=sys.stderr)
        return UNDETERMINED
    afters: list[tuple[str, list[str]]] = []
    for name in a.after:
        t, label = _read_arg(name, "after")
        if t is None:
            print(f"ENUMERATE verdict=undetermined — unreadable: {label}", file=sys.stderr)
            return UNDETERMINED
        afters.append((label, items(t, a.unit)))

    before = items(before_text, a.unit)

    if len(afters) == 1:
        label, after = afters[0]
        disp = dispositions(before, after, a.threshold)
        tally = {k: sum(1 for d, _ in disp if d == k)
                 for k in ("kept", "replaced", "added", "deleted")}
        print(f"ENUMERATE verdict=ok unit={a.unit} before={len(before)} after={len(after)} "
              + " ".join(f"{k}={v}" for k, v in tally.items()))
        for d, item in disp:
            print(f"  {d}: {item[: a.width]}")
        return OK

    # Several --after files: a split. Every item must land in exactly one child.
    placed: dict[str, list[str]] = {b: [] for b in before}
    for label, after in afters:
        for b in before:
            if b in after or any(
                difflib.SequenceMatcher(None, b, c).ratio() >= a.threshold for c in after
            ):
                placed[b].append(label)
    unplaced = [b for b, ls in placed.items() if not ls]
    duplicated = [(b, ls) for b, ls in placed.items() if len(ls) > 1]
    verdict = "anomalous" if (unplaced or duplicated) else "ok"
    print(f"ENUMERATE verdict={verdict} unit={a.unit} before={len(before)} "
          f"children={len(afters)} unplaced={len(unplaced)} duplicated={len(duplicated)}")
    for b in unplaced:
        print(f"  unplaced: {b[: a.width]}")
    for b, ls in duplicated:
        print(f"  duplicated in {','.join(ls)}: {b[: a.width]}")
    return OK if verdict == "ok" else NO


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="evidence.py",
        description="Establish an evidentiary claim without a shell or grep. "
                    "0 claim holds, 1 claim does not hold, 2 usage, 3 could not determine.",
    )
    sub = ap.add_subparsers(dest="verb", required=True)

    p = sub.add_parser("absence", help="is a pattern present in an explicitly named corpus")
    p.add_argument("paths", nargs="*", help="the corpus — files and/or directories, required")
    p.add_argument("--pattern", required=True, help="regex, or literal text with --literal")
    p.add_argument("--literal", action="store_true",
                   help="treat --pattern as text; interior spaces match across a line wrap")
    p.add_argument("--unit", choices=("paragraph", "line"), default="paragraph",
                   help="matching scope (default: paragraph — a wrapped qualifier stays "
                        "with the phrase it qualifies)")
    p.add_argument("--allowed-context", action="append", metavar="REGEX",
                   help="a unit also matching this is excused, and reported; repeatable")
    p.add_argument("--literal-context", action="store_true",
                   help="treat --allowed-context values as literal text")
    p.add_argument("--case-sensitive", action="store_true", help="default is case-insensitive")
    p.add_argument("--suffix", action="append", metavar=".EXT",
                   help="narrow a directory walk; repeatable. Never passed to a shell")
    p.add_argument("--max-rows", type=int, default=40, help="cap printed rows (default 40)")
    p.set_defaults(fn=cmd_absence)

    p = sub.add_parser("anchor", help="print exact bytes to copy into an edit")
    p.add_argument("file")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--lines", metavar="N[-M]")
    g.add_argument("--match", metavar="REGEX", help="must match exactly once")
    p.set_defaults(fn=cmd_anchor)

    p = sub.add_parser("guarded-edit", help="apply edits only if every anchor is unique")
    p.add_argument("file")
    p.add_argument("--edits", required=True, metavar="PATH|-",
                   help='JSON array of {"tag","old","new"}')
    p.add_argument("--apply", action="store_true",
                   help="write. Omit to check only — checking is the default")
    p.set_defaults(fn=cmd_guarded_edit)

    p = sub.add_parser("tables", help="every Markdown table row's cell count matches its header")
    p.add_argument("paths", nargs="*")
    p.add_argument("--suffix", action="append", metavar=".EXT")
    p.add_argument("--max-rows", type=int, default=40)
    p.set_defaults(fn=cmd_tables)

    p = sub.add_parser("cite", help="a quoted phrase appears in the source it is credited to")
    p.add_argument("--phrase", required=True, metavar="TEXT|-")
    p.add_argument("--source", required=True, metavar="PATH|-")
    p.add_argument("--case-sensitive", action="store_true")
    p.set_defaults(fn=cmd_cite)

    p = sub.add_parser("round-trip", help="what was pushed is what the destination returns")
    p.add_argument("--local", required=True, metavar="PATH|-")
    p.add_argument("--remote-cmd", required=True, help="command whose stdout is the read-back")
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--max-rows", type=int, default=30)
    p.set_defaults(fn=cmd_round_trip)

    p = sub.add_parser("enumerate", help="per-item disposition between two texts")
    p.add_argument("--before", required=True, metavar="PATH|-")
    p.add_argument("--after", required=True, action="append", metavar="PATH|-",
                   help="repeat for a split: every before-item must land in exactly one")
    p.add_argument("--unit", choices=("checkbox", "bullet"), default="bullet")
    p.add_argument("--threshold", type=float, default=0.6,
                   help="similarity above which an item counts as replaced, not deleted+added")
    p.add_argument("--width", type=int, default=90)
    p.set_defaults(fn=cmd_enumerate)

    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
