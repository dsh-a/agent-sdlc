#!/usr/bin/env python3
"""symbol-refs — which tests reference these symbols, clustered, instead of grep.

`test-preflight` Step 2 says: "for each public symbol from Step 1, grep the
project's test tree recursively for references. Cluster by test file and test
name." The grep is mechanical; the clustering is mechanical; only the verdict in
Step 3 is judgement. Today the agent pays for all three, and it pays for the
first one in raw grep output.

Measured, v0 run 2: **6,525 tokens in a single tool call** — one recursive grep
over `test/`, returned as matching lines. The agent then re-derived the cluster
from those lines by reading them. Every token of that is the script's job.

    $ python3 .claude/skills/cycle/symbol-refs.py FooRepository insert
    SYMBOL-REFS hits=9 files=2 symbols=2/2 glob=test/**

    | Test file | Test name | Symbol | Lines |
    |---|---|---|---|
    | test/foo/foo_repository_test.dart | inserts row | FooRepository | 12, 42 |
    | test/foo/foo_repository_test.dart | inserts row | insert | 44 |
    | test/foo/foo_view_model_test.dart | loads > on init | FooRepository | 31 |

The columns are Step 4's columns minus `Verdict` and `Reason`, so the agent fills
in the two it is actually for and lifts the rest.

**Stack-specific patterns live in the pack**, not here. This file knows how to
walk a tree and how to read a table of regexes; it knows nothing about Dart or
C#. See `.claude/packs/<pack>/test-ref-patterns.md`.

Exit 0 hits found, **1 no hits** — which is the greenfield short-circuit
`skip_preflight_if_no_existing_tests` already describes, so the caller can branch
on the exit code rather than on prose — 2 bad usage, 3 unreadable patterns.

**A symbol with no hits is reported, not dropped.** `symbols=2/3` plus an
`unreferenced:` line is the difference between "this symbol is safe to change"
and "the grep never ran for it", and the agent cannot tell those apart from an
absence.

**Names are resolved, never guessed.** A hit inside a test reports the test; a
hit inside a group but no test — a `setUp`, a shared fixture — reports the group
alone, because that is what it is really scoped to. A hit in neither reports `—`
and the header says `names=partial`. An invented test name is worse than no
name: it is a row the test agent will try to find and cannot.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

CONFIG_REL = pathlib.Path(".omp") / "agent-config.md"
DEFAULT_GLOB = "test/**"
MAX_LINES_PER_ROW = 6

# Files a test tree carries that are not test sources. Matching inside a lockfile
# or a golden image is a hit no one can act on.
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
                 ".zip", ".gz", ".so", ".dylib", ".dll", ".lock", ".bin"}


def repo_root() -> pathlib.Path:
    """Git root, so this resolves the same from any subdirectory."""
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("symbol-refs: not in a git repo")
    return pathlib.Path(r.stdout.strip())


def active_pack(root: pathlib.Path) -> str:
    """Read § Active Pack from .omp/agent-config.md. Defaults to flutter."""
    try:
        text = (root / CONFIG_REL).read_text(encoding="utf-8")
    except OSError:
        return "flutter"
    m = re.search(r"^\|\s*active_pack\s*\|\s*`?([A-Za-z0-9_-]+)`?\s*\|",
                  text, re.MULTILINE)
    return m.group(1) if m else "flutter"


def config_test_glob(root: pathlib.Path) -> str:
    """The `Test path glob` row of § Project Commands — the same one the
    silent-skip gate and the preflight short-circuit scope to. Reading it here
    keeps one project from having two notions of where its tests live."""
    try:
        text = (root / CONFIG_REL).read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_GLOB
    m = re.search(r"^\|\s*Test path glob\s*\|\s*`?([^|`]+?)`?\s*\|",
                  text, re.MULTILINE)
    return m.group(1).strip() if m else DEFAULT_GLOB


def load_patterns(root: pathlib.Path, pack: str,
                  explicit: str | None) -> dict[str, re.Pattern[str]]:
    """Read `| field | \\`regex\\` |` rows out of the pack's pattern table.

    Same shape and same loader rules as `suite-patterns.md`, deliberately: a
    pack author who has edited one has edited both. Rows whose regex does not
    compile are skipped with a warning — a broken pattern costs you the name
    column, not the search.
    """
    path = (pathlib.Path(explicit) if explicit
            else root / ".claude" / "packs" / pack / "test-ref-patterns.md")
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
            print(f"symbol-refs: pattern '{field}' does not compile ({exc}) "
                  f"— skipped", file=sys.stderr)
    return out


# ── walking ──────────────────────────────────────────────────────────────────

def test_files(root: pathlib.Path, glob: str) -> list[pathlib.Path]:
    """Resolve the configured glob to a file list.

    `test/**` is how the config spells "that tree, recursively", and pathlib
    reads `**` as directories only, so the trailing form is normalised rather
    than handed to `glob` as written.
    """
    g = glob.strip().rstrip("/")
    if g.endswith("/**"):
        base = root / g[:-3]
        it = base.rglob("*") if base.is_dir() else []
    elif g.endswith("**"):
        base = root / g[:-2]
        it = base.rglob("*") if base.is_dir() else []
    else:
        it = root.glob(g)
    return sorted(p for p in it
                  if p.is_file() and p.suffix.lower() not in SKIP_SUFFIXES)


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def scope(groups: list[tuple[int, str]],
          current: tuple[int, str] | None) -> str | None:
    """The innermost scope a line sits in, or None if it sits in no scope.

    A hit in a `setUp` is inside the group but inside no test, and reporting it
    as `—` throws away the one fact the test agent needs about it: which group's
    fixtures it belongs to. `FooRepository > —` would be worse still — a name
    nothing can be looked up by — so the group path alone is the answer, and a
    hit above every declaration in the file stays None.
    """
    parts = [g[1] for g in groups] + ([current[1]] if current else [])
    return " > ".join(parts) if parts else None


def name_index(lines: list[str],
               pats: dict[str, re.Pattern[str]]) -> list[str | None]:
    """For each line, the enclosing test name, or None if it is not inside one.

    Scope is tracked by indentation: a declaration at indent *i* owns every
    following line indented deeper than *i*, and is popped when one is not.
    That is an approximation — it is right for Dart's `group(...)`/`test(...)`
    nesting and for brace languages written with normal formatting, and wrong
    for a file that puts a whole test on one line. It is not brace-counting:
    a language whose bodies are not indented past their declaration will report
    `—`, which is the honest answer rather than a wrong one. A wrong *name* is survivable
    because the file and line beside it are exact; a wrong *file* would not be,
    which is why nothing here affects which lines are reported.
    """
    test_decl = pats.get("test_decl")
    group_decl = pats.get("group_decl")
    out: list[str | None] = [None] * len(lines)
    if not test_decl:
        return out

    groups: list[tuple[int, str]] = []   # (indent, name)
    current: tuple[int, str] | None = None

    for i, line in enumerate(lines):
        # A lone `{` on its own line is the declaration above it continuing, not
        # a sibling of it. Allman-braced C# puts that brace at the declaration's
        # own indent, so counting it as content closed every class and method
        # the moment it opened, and the whole file reported `—`.
        if line.strip() and line.strip() != "{":
            ind = indent_of(line)
            while groups and ind <= groups[-1][0]:
                groups.pop()
            if current and ind <= current[0]:
                current = None

        m = test_decl.search(line)
        if m and m.groupdict().get("name") is not None:
            current = (indent_of(line), m.group("name"))
            out[i] = scope(groups, current)
            continue

        if group_decl:
            gm = group_decl.search(line)
            if gm and gm.groupdict().get("name") is not None:
                groups.append((indent_of(line), gm.group("name")))
                current = None
                out[i] = scope(groups, None)
                continue

        out[i] = scope(groups, current)
    return out


def symbol_pattern(sym: str) -> re.Pattern[str]:
    r"""`\bSym\b`, with dots taken literally.

    So a bare identifier (`insert`) matches the call site a test actually
    contains, and a qualified one (`FooRepository.insert`) matches only the
    qualified form. Passing qualified symbols and getting nothing back is a real
    answer about this codebase's call style, not a bug — which is why the
    unreferenced list exists.
    """
    return re.compile(r"(?<![\w$])" + re.escape(sym) + r"(?![\w$])")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Cluster test references to symbols, instead of grepping.")
    ap.add_argument("symbols", nargs="*", help="public symbols to look for")
    ap.add_argument("--symbols-from",
                    help="file with one symbol per line (blank/# lines ignored)")
    ap.add_argument("--glob", help="override the config's Test path glob")
    ap.add_argument("--pack", help="override the pack whose patterns are used")
    ap.add_argument("--patterns", help="pattern file, overriding the pack")
    ap.add_argument("--max-lines", type=int, default=MAX_LINES_PER_ROW,
                    help=f"line numbers listed per row (default "
                         f"{MAX_LINES_PER_ROW}); the rest become '+N more'")
    args = ap.parse_args()

    root = repo_root()

    symbols = list(args.symbols)
    if args.symbols_from:
        p = pathlib.Path(args.symbols_from)
        if not p.is_absolute():
            p = root / p
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    symbols.append(line)
        except OSError as exc:
            print(f"symbol-refs: cannot read {args.symbols_from} ({exc})")
            return 2
    # Preserve caller order; de-duplicate, because a symbol listed twice would
    # otherwise double every row it appears in.
    seen: set[str] = set()
    symbols = [s for s in symbols if not (s in seen or seen.add(s))]
    if not symbols:
        print("symbol-refs: no symbols given. Pass them as arguments or "
              "--symbols-from FILE.")
        return 2

    glob = args.glob or config_test_glob(root)
    pack = args.pack or active_pack(root)
    pats = load_patterns(root, pack, args.patterns)
    if not pats:
        print(f"symbol-refs: no usable patterns for pack '{pack}'. Expected "
              f".claude/packs/{pack}/test-ref-patterns.md", file=sys.stderr)

    compiled = [(s, symbol_pattern(s)) for s in symbols]
    files = test_files(root, glob)

    # (file, test name, symbol) -> line numbers
    rows: dict[tuple[str, str, str], list[int]] = {}
    hit_symbols: set[str] = set()
    hit_files: set[str] = set()
    unnamed = 0

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not any(p.search(text) for _, p in compiled):
            continue
        lines = text.splitlines()
        names = name_index(lines, pats)
        rel = path.relative_to(root).as_posix()
        for i, line in enumerate(lines):
            for sym, pat in compiled:
                if not pat.search(line):
                    continue
                name = names[i] or "—"
                if names[i] is None:
                    unnamed += 1
                rows.setdefault((rel, name, sym), []).append(i + 1)
                hit_symbols.add(sym)
                hit_files.add(rel)

    total = sum(len(v) for v in rows.values())
    unref = [s for s in symbols if s not in hit_symbols]
    names_state = ("none" if not pats.get("test_decl")
                   else "partial" if unnamed else "resolved")

    print(f"SYMBOL-REFS hits={total} files={len(hit_files)} "
          f"symbols={len(hit_symbols)}/{len(symbols)} rows={len(rows)} "
          f"names={names_state} glob={glob} pack={pack}")
    if unref:
        print(f"unreferenced: {', '.join(unref)}")

    if not rows:
        print("No existing test references these symbols — greenfield for "
              "this change.")
        return 1

    print()
    print("| Test file | Test name | Symbol | Lines |")
    print("|---|---|---|---|")
    for (rel, name, sym) in sorted(rows):
        nums = rows[(rel, name, sym)]
        shown = ", ".join(str(n) for n in nums[:args.max_lines])
        if len(nums) > args.max_lines:
            shown += f", +{len(nums) - args.max_lines} more"
        # A pipe in a test name would end the cell it is quoted into.
        safe = name.replace("|", "\\|")
        print(f"| {rel} | {safe} | {sym} | {shown} |")

    if names_state != "resolved":
        print()
        print(f"names={names_state}: rows with `—` are hits the pack's "
              f"patterns could place in no test and no group — imports, "
              f"top-level helpers, or a shape the pack does not match. The file "
              f"and line are exact; read those rather than assuming a name.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
