#!/usr/bin/env python3
"""pitfalls — the entries that match these files, as a spawn-prompt block.

`known-pitfalls.md` is the project's record of bugs that already cost a cycle.
Two callers consume it and both consume it the same way: read the whole file,
match every entry's `Globs:` line against a task's Relevant Files, paste the
bodies that hit. That is the orchestrator at Phase 3.3 and `generate-tasks` at
Step 5b, and the matching is the same glob arithmetic in both.

Measured, v0 run 2: **5,179 tokens in a single tool call** to read the file, for
a handful of entries that matched. Nine entries were read to attach two, and the
whole file lands in context whatever the match rate is — so the cost grows with
the project's accumulated bug history rather than with the task.

    $ python3 .claude/skills/cycle/pitfalls.py lib/data/foo_repository.dart
    PITFALLS matched=1 entries=9 hard=1 path=documentation/known-pitfalls.md

    ## Known pitfalls for files you'll touch

    ### Async Future.delayed race — severity hard
    Read this carefully — the same bug has happened before:

    <body>

    _Matched lib/data/foo_repository.dart via `lib/**/data/**`._

The block is the one § Known pitfalls (5.8.3) specifies, including the `hard`
preface, so a caller pastes it rather than assembling it.

Exit 0 matched, **1 nothing matched** (emit no section at all), **3 no pitfalls
file** — the path is empty or absent, which is optional configuration and not a
finding, so it is deliberately not conflated with 1. Exit 2 is bad usage.

**An entry that does not parse is reported, never dropped.** A pitfall exists
because it already cost a cycle; one silently skipped for a missing `Globs:`
line is the exact failure this mechanism was built to stop. Unparseable entries
are counted in the header and named under `unparsed:`, and a malformed
`Severity:` reads as `hard` rather than `warn` — the fail-safe direction, since
the cost of an unnecessary preface is a sentence and the cost of a missing one
is the bug again.

**Globs are translated, not fnmatched.** `fnmatch` lets `*` cross a `/`, so
`tests/*` would match `tests/a/b/c` and the file's `**` would mean nothing. The
translation here gives `*` and `?` a single path segment, `**/` any number of
leading segments, and `**` the rest of the path.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

CONFIG_REL = pathlib.Path(".omp") / "agent-config.md"
DEFAULT_PATH = "documentation/known-pitfalls.md"
HARD_PREFACE = "Read this carefully — the same bug has happened before:"


def repo_root() -> pathlib.Path:
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("pitfalls: not in a git repo")
    return pathlib.Path(r.stdout.strip())


def config_path(root: pathlib.Path) -> str:
    """The `known_pitfalls_path` row of § Hygiene flags.

    An empty cell is the documented way to disable the feature, so an empty
    string is a real answer here and is not replaced by the default.
    """
    try:
        text = (root / CONFIG_REL).read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_PATH
    m = re.search(r"^\|\s*`?known_pitfalls_path`?\s*\|\s*`?([^|`]*)`?\s*\|",
                  text, re.MULTILINE)
    return m.group(1).strip() if m else DEFAULT_PATH


# ── glob translation ─────────────────────────────────────────────────────────

def glob_to_regex(glob: str) -> re.Pattern[str]:
    r"""Translate one `Globs:` pattern to an anchored regex.

    `*` and `?` stay inside a path segment; `**/` spans any number of leading
    segments (including none, so `lib/**/data` matches `lib/data`); a trailing
    or bare `**` spans the rest. Everything else is literal.

    Deliberately not `fnmatch.translate`: there `*` matches `/` too, which makes
    `tests/*` match `tests/a/b/c` and makes the file's own `**` decorative.
    """
    out = []
    i = 0
    while i < len(glob):
        c = glob[i]
        if glob.startswith("**/", i):
            out.append(r"(?:[^/]+/)*")
            i += 3
        elif glob.startswith("**", i):
            out.append(r".*")
            i += 2
        elif c == "*":
            out.append(r"[^/]*")
            i += 1
        elif c == "?":
            out.append(r"[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def norm(path: str) -> str:
    p = path.strip().strip("`").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


# ── parsing ──────────────────────────────────────────────────────────────────

class Entry:
    def __init__(self, title: str, line: int) -> None:
        self.title = title
        self.line = line
        self.globs: list[str] = []
        self.severity: str | None = None
        self.body: str = ""
        self.problems: list[str] = []

    @property
    def effective_severity(self) -> str:
        """`hard` unless the file says `warn` in as many words.

        A missing or misspelled severity reads as `hard`. The cost of an
        unnecessary preface is one sentence; the cost of a missing one is the
        bug a second time.
        """
        return "warn" if self.severity == "warn" else "hard"

    @property
    def usable(self) -> bool:
        return bool(self.globs) and bool(self.body.strip())


FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def document_globs(text: str) -> list[str]:
    """`Globs:` from the document's own frontmatter, or empty.

    **This is why the mechanism was inert.** myapp's `known-pitfalls.md` scopes
    the whole document with `Globs: test/**` in frontmatter and carries 19
    entries, each with `**Severity: hard**` in its prose. Reading only per-entry
    `Globs:` lines, this script reported `matched=0 entries=6 unparsed=6` for
    every file set, in every cycle, in every repo — and a 370-line document
    written to load whenever an edit touches `test/**` never loaded once.

    The document's shape is reasonable and more than one repo will have written
    it this way after reading the header, so the script learns the shape rather
    than the file being restructured.
    """
    m = FRONTMATTER.match(text)
    if not m:
        return []
    g = re.search(r"^\s*Globs:\s*(.*)$", m.group(1), re.IGNORECASE | re.MULTILINE)
    return [norm(x) for x in g.group(1).split(",") if x.strip()] if g else []


def entry_depth(text: str) -> int:
    """The heading level that carries the entries: the one `Severity:` sits under.

    In the frontmatter form the `##` headings are topical groups and the real
    entries are `###`. Choosing the level by where severity markers actually
    appear reads both shapes without a flag.
    """
    best, score = 2, -1
    for depth in (2, 3, 4):
        heads = re.findall(rf"^#{{{depth}}}\s+(?!#)", text, re.MULTILINE)
        if not heads:
            continue
        sev = len(re.findall(r"^\s*[*_]*\s*Severity:", text, re.IGNORECASE | re.MULTILINE))
        # The level whose heading count is closest to the severity-marker count.
        s = -abs(len(heads) - sev)
        if s > score:
            best, score = depth, s
    return best


def parse(text: str) -> list[Entry]:
    """Read `<heading>` / `Globs:` / `Severity:` / `Body:` entries.

    Tolerant of the fields appearing in any order and of a body that runs to the
    next heading, because the file is written by hand between incidents and a
    format nit should cost a warning rather than the entry.

    Two shapes are accepted. The original: per-entry `Globs:`, `Severity:` and
    `Body:` lines under `##`. And the frontmatter form: one `Globs:` for the
    document, entries at the depth where `Severity:` appears, and the entry's
    prose as its body. See `document_globs`.
    """
    doc_globs = document_globs(text)
    depth = entry_depth(text) if doc_globs else 2
    entries: list[Entry] = []
    cur: Entry | None = None
    in_body = False

    for i, raw in enumerate(text.splitlines(), start=1):
        h = re.match(rf"^#{{{depth}}}\s+(?!#)(.*\S)\s*$", raw)
        if h:
            cur = Entry(h.group(1), i)
            entries.append(cur)
            in_body = False
            continue
        if cur is None:
            continue

        m = re.match(r"^\s*Globs:\s*(.*)$", raw, re.IGNORECASE)
        if m:
            cur.globs = [norm(g) for g in m.group(1).split(",") if g.strip()]
            in_body = False
            continue
        m = re.match(r"^\s*[*_]*\s*Severity:\s*(.*)$", raw, re.IGNORECASE)
        if m:
            v = m.group(1).strip().strip("`*_").lower()
            cur.severity = v
            if v not in ("warn", "hard"):
                cur.problems.append(f"severity {v!r} is neither warn nor hard")
            in_body = False
            continue
        if re.match(r"^\s*Body:\s*$", raw, re.IGNORECASE):
            in_body = True
            continue
        m = re.match(r"^\s*Body:\s*(\S.*)$", raw, re.IGNORECASE)
        if m:
            in_body = True
            cur.body += m.group(1) + "\n"
            continue
        if in_body or doc_globs:
            cur.body += raw + "\n"

    for e in entries:
        if not e.globs and doc_globs:
            e.globs = list(doc_globs)      # the document scopes what it does not
        if not e.globs:
            e.problems.append("no Globs: line, so it can never match")
        if not e.body.strip():
            e.problems.append("no Body:, so there is nothing to attach")
        if e.severity is None:
            e.problems.append("no Severity:, read as hard")
    return entries


def matches(entry: Entry, files: list[str]) -> list[tuple[str, str]]:
    """(file, glob) pairs, first matching glob per file, in caller order."""
    hits: list[tuple[str, str]] = []
    pats = [(g, glob_to_regex(g)) for g in entry.globs]
    for f in files:
        for g, p in pats:
            if p.match(f):
                hits.append((f, g))
                break
    return hits


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Known-pitfall entries matching these files.")
    ap.add_argument("files", nargs="*", help="paths, repo-relative")
    ap.add_argument("--files-from",
                    help="file with one path per line, or - for stdin")
    ap.add_argument("--path", help="override the config's known_pitfalls_path")
    ap.add_argument("--list", action="store_true",
                    help="every entry with its globs and severity, no matching")
    args = ap.parse_args()

    root = repo_root()

    files = [norm(f) for f in args.files]
    if args.files_from:
        try:
            src = (sys.stdin.read() if args.files_from == "-"
                   else (root / args.files_from
                         if not pathlib.Path(args.files_from).is_absolute()
                         else pathlib.Path(args.files_from)
                         ).read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"pitfalls: cannot read {args.files_from} ({exc})")
            return 2
        for line in src.splitlines():
            line = line.strip().lstrip("-* ").strip()
            if line and not line.startswith("#"):
                files.append(norm(line))
    seen: set[str] = set()
    files = [f for f in files if f and not (f in seen or seen.add(f))]

    if not files and not args.list:
        print("pitfalls: no files given. Pass paths, --files-from FILE, or "
              "--list.")
        return 2

    rel = args.path if args.path is not None else config_path(root)
    if not rel:
        print("PITFALLS disabled — known_pitfalls_path is empty. Skip the "
              "step; this is optional configuration, not a finding.")
        return 3
    path = pathlib.Path(rel)
    if not path.is_absolute():
        path = root / path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        print(f"PITFALLS absent — no file at {rel}. Skip the step; this is "
              f"optional configuration, not a finding.")
        return 3

    entries = parse(text)
    broken = [e for e in entries if not e.usable]
    noted = [e for e in entries if e.problems and e.usable]

    if args.list:
        print(f"PITFALLS entries={len(entries)} unparsed={len(broken)} "
              f"path={rel}")
        for e in entries:
            print(f"  {e.title} — {e.effective_severity}, "
                  f"globs: {', '.join(e.globs) or '(none)'}"
                  + (f"  [{'; '.join(e.problems)}]" if e.problems else ""))
        return 0

    hit = [(e, m) for e in entries if e.usable and (m := matches(e, files))]
    hard = sum(1 for e, _ in hit if e.effective_severity == "hard")

    print(f"PITFALLS matched={len(hit)} entries={len(entries)} hard={hard} "
          f"unparsed={len(broken)} files={len(files)} path={rel}")
    for e in broken:
        print(f"unparsed: {e.title!r} (line {e.line}) — {'; '.join(e.problems)}")
    for e in noted:
        print(f"note: {e.title!r} (line {e.line}) — {'; '.join(e.problems)}")

    if not hit:
        print("No entry matches these files — attach no pitfalls section.")
        return 1

    print()
    print("## Known pitfalls for files you'll touch")
    for e, m in hit:
        print()
        print(f"### {e.title} — severity {e.effective_severity}")
        if e.effective_severity == "hard":
            print(HARD_PREFACE)
        print()
        print(e.body.strip())
        print()
        shown = ", ".join(f"{f} via `{g}`" for f, g in m[:3])
        more = f", +{len(m) - 3} more" if len(m) > 3 else ""
        print(f"_Matched {shown}{more}._")
    return 0


if __name__ == "__main__":
    sys.exit(main())
