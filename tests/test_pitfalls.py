#!/usr/bin/env python3
"""Tests for .claude/skills/cycle/pitfalls.py — stdlib only.

Three properties make the output safe to paste into a spawn prompt unread:

  * a malformed entry is **reported**, never dropped — a pitfall exists because
    it already cost a cycle;
  * an unreadable `Severity:` reads as **hard**, the fail-safe direction;
  * `*` does not cross a `/`, so the file's own `**` means something.

And one that keeps the caller honest: "no file" and "no match" are different
exit codes, because one is optional configuration and the other is a result.

    python3 tests/test_pitfalls.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "skills" / "cycle" / "pitfalls.py"
FIX = "tests/fixtures/pitfalls/known-pitfalls.md"

_spec = importlib.util.spec_from_file_location("pitfalls", SCRIPT)
pf = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(pf)

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=ROOT)


def fix(*args: str) -> subprocess.CompletedProcess:
    return run("--path", FIX, *args)


def m(glob: str, path: str) -> bool:
    return pf.glob_to_regex(glob).match(path) is not None


def test_glob_translation() -> None:
    print("\nglob translation")
    check("* stays inside a segment", not m("test/*", "test/a/b.dart"))
    check("* matches within a segment", m("test/*.dart", "test/a.dart"))
    check("** spans segments", m("lib/**", "lib/a/b/c.dart"))
    check("**/ spans zero segments",
          m("lib/**/data/**", "lib/data/foo.dart"))
    check("**/ spans many segments",
          m("lib/**/data/**", "lib/feature/x/data/foo.dart"))
    check("a mid-segment * after **/ works",
          m("test/**/*_repository_test.dart",
            "test/data/foo_repository_test.dart"))
    check("? is one char, not a separator", not m("a/?", "a/bc"))
    check("a dot is literal, not any-char", not m("a.dart", "axdart"))
    check("the match is anchored at both ends",
          not m("lib/a.dart", "src/lib/a.dart.bak"))
    check("no match is not a crash on an empty glob", not m("", "a"))


def test_norm() -> None:
    print("\npath normalisation")
    check("leading ./ is stripped", pf.norm("./lib/a.dart") == "lib/a.dart")
    check("backticks from a markdown list are stripped",
          pf.norm("`lib/a.dart`") == "lib/a.dart")
    check("backslashes become slashes",
          pf.norm("lib\\a.dart") == "lib/a.dart")
    check("a leading slash is stripped", pf.norm("/lib/a.dart") == "lib/a.dart")


def test_severity_fails_safe() -> None:
    """The refusal that decides whether the preface is printed."""
    print("\nseverity fails toward hard")
    e = pf.Entry("x", 1)
    check("an unreadable severity is hard", e.effective_severity == "hard")
    e.severity = "hardd"
    check("a typo is hard, not warn", e.effective_severity == "hard")
    e.severity = "warn"
    check("only the literal word warn is warn", e.effective_severity == "warn")
    r = fix("lib/x.dart")
    check("the typo'd fixture entry gets the hard preface",
          pf.HARD_PREFACE in r.stdout)
    check("and its problem is named rather than swallowed",
          "neither warn nor hard" in r.stdout,
          [l for l in r.stdout.splitlines() if "note:" in l])


def test_broken_entries_are_reported() -> None:
    print("\nmalformed entries")
    r = fix("lib/x.dart")
    check("the header counts them", "unparsed=2" in r.stdout,
          r.stdout.splitlines()[0])
    check("the globless entry is named with its line",
          "'Entry with no globs' (line 21)" in r.stdout)
    check("the bodyless entry is named",
          "'Entry with no body'" in r.stdout)
    check("neither is attached as a pitfall",
          "Entry with no globs" not in r.stdout.split(
              "## Known pitfalls for files you'll touch")[1])


def test_exit_codes() -> None:
    print("\nexit codes")
    check("a match exits 0", fix("lib/data/a.dart").returncode == 0)
    r = fix("server/main.go")
    check("no match exits 1", r.returncode == 1, str(r.returncode))
    check("and says to attach nothing", "attach no pitfalls" in r.stdout)
    r = run("--path", "tests/fixtures/pitfalls/nope.md", "lib/a.dart")
    check("an absent file exits 3, not 1", r.returncode == 3, str(r.returncode))
    check("and calls it optional configuration rather than a finding",
          "not a finding" in r.stdout)
    r = run("--path", "", "lib/a.dart")
    check("an empty configured path is the documented disable, also 3",
          r.returncode == 3 and "disabled" in r.stdout, r.stdout[:120])
    check("no files and no --list is exit 2",
          run().returncode == 2)


def test_output_block() -> None:
    print("\nspawn-prompt block")
    r = fix("lib/data/foo_repository.dart")
    body = r.stdout.split("\n")
    check("emits the section heading 5.8.3 specifies",
          "## Known pitfalls for files you'll touch" in body)
    check("hard entries carry the preface", pf.HARD_PREFACE in r.stdout)
    # `lib/ui/a.dart` matches the warn entry and the typo'd hard one, so the
    # claim to pin is that the preface appears once per hard match, not that it
    # is absent from everything after a warn heading.
    out = fix("lib/ui/a.dart").stdout
    theme = out.split("### Theme accent selector rebuild")[1].split("###")[0]
    check("a warn entry's own block carries no preface",
          pf.HARD_PREFACE not in theme, theme[:160])
    check("the preface appears exactly once per hard match",
          out.count(pf.HARD_PREFACE) == 1, str(out.count(pf.HARD_PREFACE)))
    check("each entry cites the file and glob that matched it",
          "via `lib/**/data/**`" in r.stdout,
          [l for l in body if "Matched" in l])
    check("the header precedes the block, so a caller can branch before "
          "reading it", r.stdout.index("PITFALLS ") < r.stdout.index("## Known"))


def test_files_from() -> None:
    print("\n--files-from")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--path", FIX, "--files-from", "-"],
        input="- `lib/data/a.dart`\n# a comment\n\nlib/ui/b.dart\n",
        capture_output=True, text=True, cwd=ROOT)
    check("reads a markdown bullet list as paths", r.returncode == 0)
    check("both paths matched", "files=2" in r.stdout,
          r.stdout.splitlines()[0])
    check("the comment is not a path", "# a comment" not in r.stdout)
    r = run("--path", FIX, "--files-from", "tests/fixtures/pitfalls/nope.txt")
    check("an unreadable --files-from is exit 2, not an empty match",
          r.returncode == 2 and "cannot read" in r.stdout,
          r.stdout.strip()[:120])


def test_list() -> None:
    print("\n--list")
    r = fix("--list")
    check("lists without matching", r.returncode == 0 and "entries=5" in r.stdout)
    check("shows each entry's effective severity", "— hard," in r.stdout)
    check("shows a globless entry as (none)", "(none)" in r.stdout)


def test_document_level_frontmatter() -> None:
    """The shape that made this script inert in every cycle, in every repo.

    myapp's `known-pitfalls.md` scopes the document with `Globs: test/**` in
    frontmatter and carries its entries at `###` with `**Severity: hard**` in
    prose. Against that file this script reported `matched=0 entries=6
    unparsed=6` on every run, so a 370-line pitfalls document never loaded once.
    """
    print("\ndocument-level frontmatter")
    p = run("test/widget/foo_test.dart", "--path", "tests/fixtures/pitfalls/frontmatter-pitfalls.md")
    head = p.stdout.splitlines()[0] if p.stdout else ""
    check("entries are read at the depth that carries Severity",
          "entries=3" in head, head)
    check("  ... and nothing is unparsed", "unparsed=0" in head, head)
    check("  ... with the document's globs applied to each",
          "matched=3" in head, head)
    check("  ... and emphasis-wrapped severity understood",
          "hard=2" in head, head)
    check("a file outside the document's globs matches nothing",
          "matched=0" in (run("lib/main.dart", "--path",
                              "tests/fixtures/pitfalls/frontmatter-pitfalls.md").stdout.splitlines() or [""])[0])


def main() -> int:
    print("pitfalls")
    test_glob_translation()
    test_norm()
    test_severity_fails_safe()
    test_broken_entries_are_reported()
    test_exit_codes()
    test_output_block()
    test_files_from()
    test_list()
    test_document_level_frontmatter()
    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all pitfalls checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
