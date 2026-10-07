#!/usr/bin/env python3
"""Tests for .claude/skills/cycle/symbol-refs.py — stdlib only.

The properties worth pinning are the ones that make the output safe to lift into
a test agent's prompt without re-checking it:

  * a symbol with no hits is **named**, not silently dropped;
  * a name is **resolved or refused**, never composed;
  * `no hits` is a distinct exit code, because that is the greenfield
    short-circuit the config already describes.

    python3 tests/test_symbol_refs.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "skills" / "cycle" / "symbol-refs.py"
FIX = "tests/fixtures/symbol-refs"

_spec = importlib.util.spec_from_file_location("symbol_refs", SCRIPT)
sr = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(sr)

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


def dart(*symbols: str, extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    return run(*symbols, "--glob", f"{FIX}/test/**", *extra)


def test_symbol_pattern() -> None:
    print("\nsymbol matching")
    p = sr.symbol_pattern("insert")
    check("matches a call site", bool(p.search("await repo.insert(Foo());")))
    check("does not match a longer identifier", not p.search("insertMany(x)"))
    check("does not match a suffix", not p.search("reinsert(x)"))
    q = sr.symbol_pattern("FooRepository.insert")
    check("a qualified symbol matches only the qualified form",
          bool(q.search("FooRepository.insert(x)"))
          and not q.search("repo.insert(x)"))
    check("the dot is literal, not any-char",
          not sr.symbol_pattern("a.b").search("axb"))


def test_scope() -> None:
    print("\nscope resolution")
    pats = sr.load_patterns(ROOT, "flutter", None)
    check("flutter pack publishes both patterns",
          {"test_decl", "group_decl"} <= set(pats), str(list(pats)))
    lines = (ROOT / FIX / "test" / "foo" /
             "foo_repository_test.dart").read_text().splitlines()
    names = sr.name_index(lines, pats)
    check("a hit inside a test names the test",
          names[12] == "FooRepository > inserts row", str(names[12]))
    check("a hit in setUp names the group alone, not a test",
          names[8] == "FooRepository", str(names[8]))
    check("a hit above every declaration has no scope",
          names[1] is None, str(names[1]))
    check("a sibling group does not inherit the previous one",
          names[22] == "edge cases > renders a spinner while loading",
          str(names[22]))


def test_no_patterns_refuses_to_name() -> None:
    """The refusal that keeps a composed name out of the table."""
    print("\nnaming is refused, not composed")
    pats = sr.load_patterns(ROOT, "no-such-pack", None)
    check("an unknown pack yields no patterns", pats == {}, str(pats))
    lines = ["test('a', () {", "  repo.insert();", "});"]
    check("with no test_decl, every line is unscoped",
          sr.name_index(lines, {}) == [None, None, None])


def test_unreferenced_symbols_are_named() -> None:
    print("\nunreferenced symbols")
    r = dart("FooRepository", "FooViewModel", "NeverMentioned")
    check("the header counts found against asked",
          "symbols=1/3" in r.stdout, r.stdout.splitlines()[0])
    check("each missing symbol is named",
          "unreferenced: FooViewModel, NeverMentioned" in r.stdout,
          [l for l in r.stdout.splitlines() if "unreferenced" in l])


def test_greenfield_exit_code() -> None:
    print("\ngreenfield short-circuit")
    r = dart("NeverMentioned")
    check("no hits exits 1, distinct from hits and from an error",
          r.returncode == 1, str(r.returncode))
    check("and says so in words too", "greenfield" in r.stdout, r.stdout[:200])
    r = dart("FooRepository")
    check("hits exit 0", r.returncode == 0, str(r.returncode))


def test_usage_errors() -> None:
    print("\nusage")
    r = run()
    check("no symbols is exit 2, not an empty table",
          r.returncode == 2 and "no symbols given" in r.stdout,
          r.stdout.strip()[:120])
    r = run("Foo", "--symbols-from", "tests/fixtures/symbol-refs/nope.txt")
    check("an unreadable --symbols-from is exit 2, not ignored",
          r.returncode == 2 and "cannot read" in r.stdout,
          r.stdout.strip()[:120])


def test_output_is_a_parseable_table() -> None:
    print("\noutput shape")
    r = dart("FooRepository", "insert", "find")
    body = [l for l in r.stdout.splitlines() if l.startswith("| ")]
    check("emits the Step 4 columns minus Verdict and Reason",
          body[0] == "| Test file | Test name | Symbol | Lines |", body[0])
    check("every row has exactly four cells",
          all(len(l.split(" | ")) == 4 for l in body[2:]),
          str([l for l in body[2:] if len(l.split(" | ")) != 4]))
    check("rows are sorted, so two runs diff cleanly",
          body[2:] == sorted(body[2:]))
    check("duplicate symbols do not duplicate rows",
          dart("insert", "insert").stdout == dart("insert").stdout)


def test_dotnet_pack() -> None:
    print("\ndotnet pack")
    r = run("FooRepository", "Insert", "Find",
            "--pack", "dotnet", "--glob", f"{FIX}/tests/**")
    check("resolves names through Allman braces",
          "names=resolved" in r.stdout, r.stdout.splitlines()[0])
    check("a method hit names class > method",
          "| FooRepositoryTests > InsertsRow | Insert |" in r.stdout,
          [l for l in r.stdout.splitlines() if "Insert " in l])
    check("a field hit names the class alone",
          "| FooRepositoryTests | FooRepository |" in r.stdout)


def test_patterns_have_no_pipe() -> None:
    """The constraint the markdown table imposes, pinned so a pack edit that
    breaks it fails here rather than silently losing the row."""
    print("\npack pattern hygiene")
    for pack in ("flutter", "dotnet"):
        path = ROOT / ".claude" / "packs" / pack / "test-ref-patterns.md"
        check(f"{pack} publishes a pattern table", path.exists())
        pats = sr.load_patterns(ROOT, pack, None)
        check(f"{pack} rows all compile and carry a name group",
              bool(pats) and all("name" in p.groupindex for p in pats.values()),
              str({k: v.groupindex for k, v in pats.items()}))
        check(f"{pack} has no pipe in any pattern",
              all("|" not in p.pattern for p in pats.values()))


def main() -> int:
    print("symbol-refs")
    test_symbol_pattern()
    test_scope()
    test_no_patterns_refuses_to_name()
    test_unreferenced_symbols_are_named()
    test_greenfield_exit_code()
    test_usage_errors()
    test_output_is_a_parseable_table()
    test_dotnet_pack()
    test_patterns_have_no_pipe()
    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all symbol-refs checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
