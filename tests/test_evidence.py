#!/usr/bin/env python3
"""Tests for .claude/skills/evidence/evidence.py — stdlib only.

Each check below pins one of the specific mistakes that produced ten
instrumentation errors in a single `/refine` session. The thesis is that those
mistakes are now **unexpressible**, not merely discouraged, so several checks
assert on the module's *source* (no `--include` flag, no shelling out to grep)
rather than on its output: a behavioural test passes until someone adds the
hazard back.

    python3 tests/test_evidence.py

Unlike the sibling script tests, the individual cases here are named `check_*`
rather than `test_*`, with one `test_evidence_suite` as the pytest entry point.
The precedent (`test_symbol_refs.py` and friends) collects `test_*` functions
that report through a module-level `failures` list and never assert, so under
pytest they pass whatever they find. A suite that cannot fail is the silent-skip
anti-pattern this file exists to oppose.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "skills" / "evidence" / "evidence.py"
FIX = "tests/fixtures/evidence"

_spec = importlib.util.spec_from_file_location("evidence", SCRIPT)
ev = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ev)

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def run(*args: str, stdin: str | None = None,
        cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin,
                          capture_output=True, text=True, cwd=cwd or ROOT)


def head(p: subprocess.CompletedProcess) -> str:
    return p.stdout.splitlines()[0] if p.stdout.splitlines() else ""


def field(p: subprocess.CompletedProcess, key: str) -> str:
    for tok in head(p).split():
        if tok.startswith(key + "="):
            return tok.split("=", 1)[1]
    return ""


# --------------------------------------------------------------------------- #

def check_no_shell_hazard() -> None:
    """Classes 1-3 and 5 are absent by construction, not by discipline."""
    print("\nthe shell is not in the path")
    src = SCRIPT.read_text()
    check("no --include flag exists to be left unquoted",
          '"--include"' not in src and "'--include'" not in src)
    check("grep is never invoked", "\"grep\"" not in src and "'grep'" not in src
          and "subprocess.run([\"grep" not in src)
    # round-trip takes a caller-named command and is the only shell=True use.
    check("exactly one shell=True, in round-trip", src.count("shell=True") == 1)


def check_corpus_is_mandatory_and_stated() -> None:
    """Class 4 — a subset verdict must label itself as one."""
    print("\nan absence claim carries its corpus")
    full = run("absence", "--pattern", "INSERT POLICY", f"{FIX}/migrations")
    check("present across the whole corpus", field(full, "verdict") == "present", head(full))
    check("names how many files it read", field(full, "corpus") == "4/4", head(full))
    check("exit 1 means the claim does not hold", full.returncode == 1, str(full.returncode))

    one = run("absence", "--pattern", "INSERT POLICY", f"{FIX}/migrations/0001_init.sql")
    check("absent over a one-file subset", field(one, "verdict") == "absent", head(one))
    check("and the subset is visible in the claim", field(one, "corpus") == "1/1", head(one))
    check("exit 0 means the claim holds", one.returncode == 0, str(one.returncode))

    empty = run("absence", "--pattern", "x")
    check("no corpus is a usage error, not an empty result", empty.returncode == ev.USAGE,
          str(empty.returncode))


def check_undetermined_is_never_absent() -> None:
    """Class 5 — the single most expensive conflation in the session."""
    print("\ncould-not-determine is a third outcome")
    p = run("absence", "--pattern", "INSERT POLICY",
            f"{FIX}/migrations/0001_init.sql", f"{FIX}/does/not/exist.sql")
    check("verdict is undetermined", field(p, "verdict") == "undetermined", head(p))
    check("exit 3, not 0", p.returncode == ev.UNDETERMINED, str(p.returncode))
    check("the unresolvable path is named", "unresolved:" in p.stdout
          and "does/not/exist.sql" in p.stdout)
    # The readable file genuinely contains no hit, so a naive implementation
    # would report `absent` here. That is the whole of class 5.
    check("hits=0 did not become absent", field(p, "verdict") != "absent", head(p))

    filtered = run("absence", "--pattern", "x", "--suffix", ".nope", f"{FIX}/migrations")
    check("a suffix filter matching nothing is undetermined, not absent",
          filtered.returncode == ev.UNDETERMINED, head(filtered))


def check_verdict_survives_a_pipe() -> None:
    """Class 2 — a pipeline reports the last command's status, always 0."""
    print("\nthe verdict is in the text, not only the exit code")
    r = subprocess.run(
        f'{sys.executable} "{SCRIPT}" absence --pattern alpha {FIX}/occurrences.txt | head -1',
        shell=True, capture_output=True, text=True, cwd=ROOT)
    check("the pipeline's status is 0, as it always is", r.returncode == 0)
    check("but the verdict word still reached the reader", "verdict=present" in r.stdout,
          r.stdout.strip())


def check_lines_and_occurrences_are_both_answered() -> None:
    """Class 3 — the caller asked an ambiguous question; answer both readings."""
    print("\nhits and occurrences are both always printed")
    p = run("absence", "--pattern", "alpha", "--unit", "line", f"{FIX}/occurrences.txt")
    check("hits counts units", field(p, "hits") == "1", head(p))
    check("occurrences counts matches", field(p, "occurrences") == "3", head(p))


def check_paragraph_is_the_default_unit() -> None:
    """Class 7 — four gate failures from a qualifier wrapping onto another line."""
    print("\nparagraphs, not lines")
    ok = run("absence", "--pattern", "anonymous session",
             "--allowed-context", "Not a Supabase", f"{FIX}/wrapped.md")
    check("the wrapped qualifier excuses the phrase", field(ok, "verdict") == "absent", head(ok))
    check("and the excused unit is printed, not merely counted",
          "excused-by-context:" in ok.stdout)
    check("default unit is paragraph", field(ok, "unit") == "paragraph", head(ok))

    bad = run("absence", "--pattern", "anonymous session", "--unit", "line",
              "--allowed-context", "Not a Supabase", f"{FIX}/wrapped.md")
    check("--unit line reproduces the original false positive",
          field(bad, "verdict") == "present", head(bad))

    folded = run("absence", "--pattern", "under e2e/", "--literal", f"{FIX}/case.md")
    check("matching is case-insensitive by default", field(folded, "verdict") == "present",
          head(folded))
    cased = run("absence", "--pattern", "under e2e/", "--literal", "--case-sensitive",
                f"{FIX}/case.md")
    check("--case-sensitive is opt-in", field(cased, "verdict") == "absent", head(cased))


def check_glob_does_not_depend_on_cwd() -> None:
    """Class 1 — zsh aborted the command and the && chain read it as no results."""
    print("\na suffix filter is resolved in python, not by a shell")
    a = run("absence", "--pattern", "INSERT POLICY", "--suffix", ".sql", f"{FIX}/migrations")
    b = run("absence", "--pattern", "INSERT POLICY", "--suffix", ".sql",
            str(ROOT / FIX / "migrations"), cwd=pathlib.Path(SCRIPT).parent)
    check("same verdict from a directory holding no .sql file",
          field(a, "verdict") == field(b, "verdict") == "present", f"{head(a)} | {head(b)}")
    check("same file count", field(a, "files") == field(b, "files") == "4")


def check_anchors_are_read_not_retyped() -> None:
    """Class 6 — five aborted edits, each from a line wrap guessed wrong."""
    print("\nanchors")
    a = run("anchor", f"{FIX}/anchor.md", "--lines", "1-2")
    check("anchor proves uniqueness at print time", field(a, "occurrences") == "1", head(a))
    check("and delimits the bytes", "--- anchor ---" in a.stdout and "--- end ---" in a.stdout)
    check("exit 0", a.returncode == 0)

    amb = run("anchor", f"{FIX}/occurrences.txt", "--match", "alpha")
    check("a non-unique region is refused, not returned",
          field(amb, "verdict") == "ambiguous" and amb.returncode == 1, head(amb))

    # Found while using the verb on a real .gitignore: without re.MULTILINE this
    # reported occurrences=0 for a line plainly present in the file.
    ml = run("anchor", f"{FIX}/anchor.md", "--match", r"^A second paragraph.*$")
    check("--match anchors per line, not per file",
          field(ml, "occurrences") == "1" and ml.returncode == 0, head(ml))
    none = run("anchor", f"{FIX}/anchor.md", "--match", "^no such line$")
    check("zero matches is not-found, not ambiguous",
          field(none, "verdict") == "not-found", head(none))

    text = (ROOT / FIX / "anchor.md").read_text()
    wrapped_anchor = "context, which is a rule about paragraphs"
    retyped = "a phrase appears only in a corrective context"  # true prose, wrong bytes
    check("the retyped form is genuinely absent from the file", text.count(retyped) == 0)
    check("the real bytes are unique", text.count(wrapped_anchor) == 1)


def check_guarded_edit_is_all_or_nothing() -> None:
    print("\nguarded edits")
    src = ROOT / FIX / "anchor.md"
    original = src.read_text()
    good = '[{"tag":"para","old":"A second paragraph","new":"A replaced paragraph"}]'
    p = run("guarded-edit", str(src), "--edits", "-", stdin=good)
    check("a unique anchor checks clean", field(p, "verdict") == "checked", head(p))
    check("checking is the default — nothing was written", src.read_text() == original)

    batch = ('[{"tag":"para","old":"A second paragraph","new":"X"},'
             '{"tag":"retyped","old":"a phrase appears only in a corrective context",'
             '"new":"Y"}]')
    q = run("guarded-edit", str(src), "--edits", "-", "--apply", stdin=batch)
    check("a bad anchor aborts the batch", field(q, "verdict") == "aborted", head(q))
    check("the failing tag and its count are named",
          "retyped: occurrences=0" in q.stdout, q.stdout)
    check("neither edit applied", src.read_text() == original)
    check("exit 1", q.returncode == 1)

    new, counts = ev.guarded_edit("a b a", [{"tag": "t", "old": "a", "new": "z"}])
    check("a duplicated anchor is refused in-process too", new is None and counts[0][1] == 2)


def check_tables_catches_the_real_defect() -> None:
    """Class 9 — the gate was right and was dismissed as a probe artifact."""
    print("\nmarkdown tables")
    p = run("tables", f"{FIX}/tables.md")
    check("the pipe-run row is reported", "fault=pipe-run" in p.stdout, p.stdout)
    check("with the header width and both cell counts",
          "header=3 cells=3 cells_raw=5" in p.stdout, p.stdout)
    check("exactly one fault — the legitimate rows stay clean",
          field(p, "bad_rows") == "1", p.stdout)
    check("exit 1", p.returncode == 1)

    short = run("tables", f"{FIX}/short-row.md")
    check("a genuinely short row is a cells fault", "fault=cells" in short.stdout, short.stdout)

    faults = ev.table_faults("| a | b |\n|---|---|\n| one | two |\n")
    check("a well-formed table has no faults", faults == [], str(faults))


def check_citations_are_checked_separately() -> None:
    print("\ncitations")
    phrase = "the guard rejects a write whose owner is unset"
    bad = run("cite", "--phrase", phrase, "--source", f"{FIX}/issue-body.txt")
    check("a phrase absent from its credited source is unsupported",
          field(bad, "verdict") == "unsupported" and field(bad, "hits") == "0", head(bad))
    check("exit 1", bad.returncode == 1)
    check("and the failure mode is stated: unverified, not false",
          "unverified, not false" in bad.stdout)

    good = run("cite", "--phrase", phrase, "--source", f"{FIX}/source-comment.txt")
    check("the real source supports it", field(good, "verdict") == "supported", head(good))

    wrapped = run("cite", "--phrase", "a rule about paragraphs and not about lines",
                  "--source", f"{FIX}/anchor.md")
    check("a quote that wrapped differently still matches",
          field(wrapped, "verdict") == "supported", head(wrapped))

    gone = run("cite", "--phrase", phrase, "--source", f"{FIX}/no-such-source.txt")
    check("an unreadable source is undetermined, not unsupported",
          gone.returncode == ev.UNDETERMINED, str(gone.returncode))


def check_round_trip_never_assumes_acceptance() -> None:
    print("\nround trip")
    local = f"{FIX}/acs-before.md"
    same = run("round-trip", "--local", local, "--remote-cmd", f"cat {FIX}/acs-before.md")
    check("identical bytes", field(same, "verdict") == "identical" and same.returncode == 0,
          head(same))
    nl = run("round-trip", "--local", local,
             "--remote-cmd", f"cat {FIX}/acs-before.md; printf '\\n\\n'")
    check("a trailing-newline difference is still identical",
          field(nl, "verdict") == "identical", head(nl))
    diff = run("round-trip", "--local", local, "--remote-cmd", f"cat {FIX}/acs-after.md")
    check("a real difference is reported with a diff",
          field(diff, "verdict") == "differs" and "--- local" in diff.stdout, head(diff))
    check("exit 1", diff.returncode == 1)
    failed = run("round-trip", "--local", local, "--remote-cmd", "exit 7")
    check("a failed read-back is undetermined, never identical",
          failed.returncode == ev.UNDETERMINED and field(failed, "verdict") == "undetermined",
          head(failed))
    empty = run("round-trip", "--local", local, "--remote-cmd", "true")
    check("an empty read-back is undetermined too", empty.returncode == ev.UNDETERMINED,
          head(empty))


def check_enumerate_takes_no_expected_total() -> None:
    """The predicted count was wrong three times while the content was right."""
    print("\nitem dispositions")
    p = run("enumerate", "--before", f"{FIX}/acs-before.md", "--after", f"{FIX}/acs-after.md",
            "--unit", "checkbox")
    check("every item gets a disposition",
          all(f"{k}=" in head(p) for k in ("kept", "replaced", "added", "deleted")), head(p))
    check("a reworded item is replaced, not deleted+added", field(p, "replaced") == "1", head(p))
    check("a removed item is deleted", field(p, "deleted") == "1", head(p))
    check("two genuinely new items are added", field(p, "added") == "2", head(p))
    check("no verb accepts an expected total",
          "--expect" not in SCRIPT.read_text() and "--total" not in SCRIPT.read_text())

    split = run("enumerate", "--before", f"{FIX}/acs-before.md",
                "--after", f"{FIX}/acs-child-1.md", "--after", f"{FIX}/acs-child-2.md",
                "--unit", "checkbox")
    check("a split that drops an item flags it", field(split, "unplaced") == "1", head(split))
    check("a split that duplicates an item flags it too",
          field(split, "duplicated") == "1", head(split))
    check("verdict=anomalous, exit 1",
          field(split, "verdict") == "anomalous" and split.returncode == 1, head(split))

    check("a wrapped list item counts once",
          ev.items("- one item that\n  wraps onto a second line\n", "bullet") ==
          ["one item that wraps onto a second line"])


def check_usage_errors() -> None:
    print("\nusage")
    check("a bad regex is a usage error",
          run("absence", "--pattern", "[", f"{FIX}/case.md").returncode == ev.USAGE)
    check("a bad --lines range is a usage error",
          run("anchor", f"{FIX}/case.md", "--lines", "9-99").returncode == ev.USAGE)
    check("malformed edit json is a usage error",
          run("guarded-edit", f"{FIX}/case.md", "--edits", "-",
              stdin="{not json").returncode == ev.USAGE)
    check("an edit without 'new' is a usage error",
          run("guarded-edit", f"{FIX}/case.md", "--edits", "-",
              stdin='[{"old":"x"}]').returncode == ev.USAGE)


def main() -> int:
    print("evidence")
    check_no_shell_hazard()
    check_corpus_is_mandatory_and_stated()
    check_undetermined_is_never_absent()
    check_verdict_survives_a_pipe()
    check_lines_and_occurrences_are_both_answered()
    check_paragraph_is_the_default_unit()
    check_glob_does_not_depend_on_cwd()
    check_anchors_are_read_not_retyped()
    check_guarded_edit_is_all_or_nothing()
    check_tables_catches_the_real_defect()
    check_citations_are_checked_separately()
    check_round_trip_never_assumes_acceptance()
    check_enumerate_takes_no_expected_total()
    check_usage_errors()
    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all evidence checks passed")
    return 0


def test_evidence_suite() -> None:
    """The pytest entry point, so the suite cannot silently pass under pytest."""
    rc = main()
    assert rc == 0, f"{len(failures)} failure(s): {', '.join(failures)}"


if __name__ == "__main__":
    sys.exit(main())
