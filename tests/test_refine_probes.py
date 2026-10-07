#!/usr/bin/env python3
"""Tests for .claude/skills/refine/probes.py — stdlib only.

Three of the four story fixtures are **verbatim copies of live issue bodies** from
myapp's epic 0.36 (#413, #488, #418), because the two conventions in that epic
disagree and a template-derived fixture would have shown neither: #413 writes its
acceptance criteria as `- [ ] (+) …` checkboxes and #488 writes them as a `1. (+) …`
ordered list. The first draft of this parser read only checkboxes and reported
`ac=0` on #488 — caught by this fixture, exactly as three `findings-extract.py`
bugs were caught the same way last week.

The cases that matter most:

  * **A section present that yields nothing is exit 3**, with the section named.
    `pitfalls.py` shipped for months printing `unparsed=6` while nothing read the
    number, and an inert gate is worse than no gate because it reads as a pass.
  * **An absent section is not an empty one** — a spike legitimately has no ACs,
    so #418 must be `ac=absent` at exit 0, not an error.
  * **Artifacts dedup.** `#554` occurs 14 times in #413 and is one dependency to
    judge. Before dedup the `inherited-claim` workload was 47 rows, which is a
    gate whose failures get dismissed (`evidence` § tables).
  * **A mutating queue verb changes exactly one line.** The verbs print the whole
    body for `gh issue edit --body-file -`, so a diff against the input is the
    real contract, not the content of the line.

    python3 tests/test_refine_probes.py

Individual cases are `check_*`, with one `test_refine_probes_suite` as the pytest
gate, so the suite cannot pass silently under pytest.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "skills" / "refine" / "probes.py"
FIX = ROOT / "tests" / "fixtures" / "refine"

_spec = importlib.util.spec_from_file_location("refine_probes", SCRIPT)
pb = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(pb)

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=ROOT, input=stdin)


def arts(name: str) -> dict:
    p = run("artifacts", "--body", str(FIX / name), "--json")
    return json.loads(p.stdout)


def rows(name: str, kind: str) -> list[dict]:
    return [r for r in arts(name)["artifacts"] if r["kind"] == kind]


# --------------------------------------------------------------------------- #

def check_both_real_ac_conventions_parse() -> None:
    """The bug this fixture pair exists to catch."""
    print("\nacceptance-criteria conventions")
    cb = rows("story-checkbox-acs.md", "AC")
    check("checkbox ACs parse (#413's `- [ ] (+)`)", len(cb) == 19, str(len(cb)))
    num = rows("story-numbered-acs.md", "AC")
    check("ordered-list ACs parse (#488's `1. (+)`) — read-only-checkboxes "
          "reported 0 here", len(num) == 19, str(len(num)))

    check("polarity comes off the `(+)` / `(−)` marker",
          "pos" in cb[0]["flags"] and any("neg" in r["flags"] for r in cb),
          str(cb[0]["flags"]))
    check("a numbered AC is open, never guessed closed",
          all("open" in r["flags"] for r in num), str(num[0]["flags"]))

    # Multi-line: #413's first AC carries a six-row table, its fifteenth a
    # blockquote. A line-scoped reader sees a fragment of each.
    full = [r for r in arts("story-checkbox-acs.md")["artifacts"]
            if r["kind"] == "AC" and r.get("full")]
    widest = max(len(r["full"]) for r in full)
    check("an AC's continuation lines are read, not truncated at the newline",
          widest > 400, f"widest={widest}")


def check_a_present_section_that_parses_to_nothing_is_an_error() -> None:
    """The `pitfalls.py` failure, made impossible."""
    print("\nnothing parsed is never nothing found")
    p = run("artifacts", "--body", str(FIX / "story-unparsed-acs.md"))
    check("exit 3, not 0 or 1", p.returncode == pb.UNDETERMINED, str(p.returncode))
    check("the section is named", "ac" in p.stderr and "unparsed" in p.stderr,
          p.stderr.strip()[:90])
    check("and the header says so", "ac:unparsed" in p.stdout,
          p.stdout.splitlines()[0])

    q = run("artifacts", "--body", str(FIX / "story-spike-no-acs.md"))
    check("a spike with no AC section is not an error",
          q.returncode == pb.OK, str(q.returncode))
    check("  ... and absent is distinguished from unparsed",
          "ac:absent" in q.stdout, q.stdout.splitlines()[0])


def check_artifacts_dedup_to_distinct_things() -> None:
    print("\ndedup")
    xr = rows("story-checkbox-acs.md", "XREF")
    ids = [r["text"] for r in xr]
    check("an xref appearing many times is one artifact",
          len(ids) == len(set(ids)), f"{len(ids)} rows, {len(set(ids))} distinct")
    busiest = max(xr, key=lambda r: r["seen"])
    check("  ... and the occurrence count is kept, not discarded",
          busiest["seen"] > 5, f"{busiest['text']} seen={busiest['seen']}")

    # Two ACs may read alike and both still need a verdict, so ACs are keyed
    # positionally and never collapse.
    acs = rows("story-numbered-acs.md", "AC")
    check("ACs are positional and never dedup", len(acs) == 19, str(len(acs)))


def check_flag_precedence_is_conservative() -> None:
    """A wrong flag silently removes an artifact from a probe's workload."""
    print("\nflag precedence")
    cites = rows("story-checkbox-acs.md", "CITATION")
    check("a citation grounded at any occurrence is grounded",
          all(not {"grounded", "ungrounded"} <= set(r["flags"]) for r in cites))

    nums = rows("story-checkbox-acs.md", "NUMBER")
    check("a number stays ungrounded if any occurrence is — proximity to the "
          "word 'measured' is weak evidence this figure was",
          all(not {"grounded", "ungrounded"} <= set(r["flags"]) for r in nums))

    xr = rows("story-checkbox-acs.md", "XREF")
    check("`dependency` beats `mention` on the same xref",
          all(not {"dependency", "mention"} <= set(r["flags"]) for r in xr))


def check_the_findings_the_lenses_actually_produced_are_rederivable() -> None:
    """If a probe cannot re-derive a question that mattered, it is the wrong probe.

    Both findings from the one live trial of the five lenses came off #413: an AC
    guarding a dead cron whose threshold was never named, and an unproven
    mechanism claim. Neither was found by the seven original categories.
    """
    print("\nre-deriving the real findings")
    a = arts("story-checkbox-acs.md")
    rs = a["artifacts"]
    thresh = [r for r in rs if r["kind"] == "AC" and "threshold" in r["flags"]]
    check("`deferred-number` flags the AC whose threshold is unnamed",
          len(thresh) == 1, str([r["id"] for r in thresh]))
    check("  ... and it is the freshness-assertion AC",
          "freshness" in thresh[0]["text"].lower() if thresh else False,
          thresh[0]["text"][:70] if thresh else "")

    mech = [r for r in rs if r["kind"] == "MECHANISM" and "unproven" in r["flags"]]
    check("`mechanism-exists` has unproven candidates to probe", len(mech) >= 5,
          str(len(mech)))
    proven = [r for r in rs if r["kind"] == "MECHANISM" and "proven" in r["flags"]]
    check("  ... and a proven mechanism is not re-probed", len(proven) >= 5,
          str(len(proven)))


def check_probe_workload_stays_readable() -> None:
    """A gate that cries wolf is a gate whose failures get dismissed."""
    print("\nworkload")
    a = arts("story-checkbox-acs.md")
    rs = a["artifacts"]
    worst = 0
    for probe in pb.PROBES:
        n = len(pb.applicable(rs, probe))
        worst = max(worst, n)
    check("no single probe asks for more than 25 verdicts on the "
          "heaviest real story", worst <= 25, f"worst={worst}")
    check("the probe table has no two probes over the same input and flag",
          len({(v[0], v[1]) for v in pb.PROBES.values()}) == len(pb.PROBES))


def check_coverage_counts_rather_than_claims() -> None:
    print("\ncoverage")
    body = str(FIX / "story-checkbox-acs.md")
    v = FIX.parent / "refine" / "_verdicts.tmp"
    try:
        v.write_text("deferred-number\tac-12\tdeferred(no number)\n",
                     encoding="utf-8")
        p = run("coverage", "--body", body, "--verdicts", str(v))
        check("gaps make it exit 1, not 0", p.returncode == pb.REFUSED,
              str(p.returncode))
        check("each gap names its probe and artifact",
              "GAP\tac-strict\tac-1" in p.stdout,
              p.stdout.splitlines()[1] if len(p.stdout.splitlines()) > 1 else "")
        check("the log line is emitted ready to paste",
              "**Probes:** " in p.stdout and "deferred-number 1/1" in p.stdout)

        v.write_text("bogus-probe\tac-1\tx\ninherited-claim\tcitation-999\tx\n",
                     encoding="utf-8")
        p = run("coverage", "--body", body, "--verdicts", str(v))
        check("an unknown probe or artifact is exit 3, never ignored",
              p.returncode == pb.UNDETERMINED, str(p.returncode))
        check("  ... and both are named", p.stdout.count("UNKNOWN") == 2)

        v.write_text("", encoding="utf-8")
        check("an empty verdict file is a usage error",
              run("coverage", "--body", body,
                  "--verdicts", str(v)).returncode == pb.USAGE)
    finally:
        v.unlink(missing_ok=True)


def check_carry_forward_requires_unchanged_text() -> None:
    """Keying on the id alone would carry a verdict onto a renumbered artifact."""
    print("\ncarry-forward")
    body = str(FIX / "story-checkbox-acs.md")
    cite = rows("story-checkbox-acs.md", "CITATION")[3]
    v = FIX / "_verdicts.tmp"
    prior = FIX / "_prior.tmp"
    try:
        v.write_text("deferred-number\tac-12\tdeferred\n", encoding="utf-8")
        prior.write_text(
            f"inherited-claim\t{cite['id']}\treground\t{cite['text']}\n"
            f"inherited-claim\tcitation-1\tstale\t:not-the-text-it-has\n",
            encoding="utf-8")
        p = run("coverage", "--body", body, "--verdicts", str(v),
                "--prior", str(prior))
        check("a verdict carries forward when the artifact is unchanged",
              "carried=1" in p.stdout, p.stdout.splitlines()[0])
        check("  ... and does not when its text moved",
              "gaps=60" in p.stdout, p.stdout.splitlines()[0])
    finally:
        v.unlink(missing_ok=True)
        prior.unlink(missing_ok=True)


def check_queue_reads_the_real_shapes() -> None:
    print("\nqueue read")
    p = run("queue", "read", "--body", str(FIX / "story-checkbox-acs.md"))
    check("items are counted", "items=9" in p.stdout, p.stdout.splitlines()[0])
    check("a compound id parses — `Q-3 / Q-11` is one real entry",
          "Q-3 / Q-11" in p.stdout)
    check("an entry with no id prints `-` rather than failing", "\t-\t" in p.stdout)

    q = run("queue", "read", "--body", str(FIX / "story-spike-no-acs.md"))
    check("an absent queue is exit 3, not an empty list",
          q.returncode == pb.UNDETERMINED, str(q.returncode))


def check_queue_mutations_change_exactly_one_line() -> None:
    """The verbs print a whole body, so the diff is the contract."""
    print("\nqueue mutation")
    src = (FIX / "story-checkbox-acs.md").read_text(encoding="utf-8")
    before = src.splitlines()

    p = run("queue", "add", "--body", "-", "--tag", "Risk",
            "--text", "Does the threshold have a number?", stdin=src)
    after = p.stdout.splitlines()
    check("add is exit 0", p.returncode == pb.OK, p.stderr.strip()[:80])
    check("add inserts exactly one line", len(after) == len(before) + 1,
          f"{len(before)} -> {len(after)}")
    added = [x for x in after if x not in before]
    check("  ... and it is the new question, inside the queue section",
          len(added) == 1 and added[0].startswith("- [ ] (Risk)"), str(added))

    # All nine of #413's queue items are already resolved, so resolving has to
    # run against a body that has an open one — and the add output is exactly
    # that. Chaining the two verbs is also the real usage.
    with_open = p.stdout
    r = run("queue", "resolve", "--body", "-",
            "--id", "Does the threshold have a number?",
            "--answer", "**90 days**", "--date", "2026-10-04", stdin=with_open)
    res = r.stdout.splitlines()
    check("resolve is exit 0", r.returncode == pb.OK, r.stderr.strip()[:80])
    check("resolve keeps the line count", len(res) == len(after),
          f"{len(after)} -> {len(res)}")
    changed = [(a, b) for a, b in zip(after, res) if a != b]
    check("resolve rewrites exactly one line", len(changed) == 1,
          str(len(changed)))
    if changed:
        check("  ... striking it through and dating it",
              changed[0][1].startswith("- [x] ~~")
              and "(resolved 2026-10-04)" in changed[0][1],
              changed[0][1][:80])

    check("an id with no match refuses rather than guessing",
          run("queue", "resolve", "--body", "-", "--id", "Q-999",
              "--answer", "x", stdin=src).returncode == pb.REFUSED)
    check("an already-resolved item refuses — resolving twice would overwrite "
          "the answer that is there",
          run("queue", "resolve", "--body", "-", "--id", "Q-12",
              "--answer", "x", stdin=src).returncode == pb.REFUSED)
    check("so does a body with no queue section",
          run("queue", "add", "--body", str(FIX / "story-spike-no-acs.md"),
              "--tag", "Risk", "--text", "x").returncode == pb.REFUSED)


def check_next_id_is_epic_wide() -> None:
    """`Q-19` raised on one story is answered on another, so 1 is never right."""
    print("\nnext-id")
    p = run("queue", "next-id",
            str(FIX / "story-checkbox-acs.md"),
            str(FIX / "story-numbered-acs.md"))
    check("numbering continues from the epic's high-water mark",
          p.stdout.strip().startswith("Q-") and p.stdout.strip() != "Q-1",
          p.stdout.strip())
    check("a cross-story id is counted too — #418 carries `Q-17` only as "
          "`#249 Q-17`, and numbering past it is the point",
          run("queue", "next-id",
              str(FIX / "story-spike-no-acs.md")).stdout.strip() == "Q-18")
    check("a corpus with no ids at all refuses rather than inventing Q-1",
          run("queue", "next-id",
              str(FIX / "profiles-template-only.md")).returncode == pb.REFUSED)


def check_profiles_are_unavailable_not_clean() -> None:
    """The `pitfalls.py` lesson, applied to a probe whose input may not exist."""
    print("\nprofiles")
    p = run("profiles", "--path", str(FIX / "nothing-here.md"))
    check("an absent profile file is exit 3", p.returncode == pb.UNDETERMINED,
          str(p.returncode))
    check("  ... reported `unavailable`, never `clean`",
          "verdict=unavailable" in p.stdout and "clean" not in p.stdout,
          p.stdout.strip()[:80])
    check("  ... and says the probe could not run",
          "cannot run" in p.stderr, p.stderr.strip()[:70])

    t = run("profiles", "--path", str(FIX / "profiles-template-only.md"))
    check("an unfilled template defines no profile", t.returncode == pb.UNDETERMINED,
          str(t.returncode))
    check("  ... with a reason distinct from absent",
          "reason=no-profiles" in t.stdout, t.stdout.strip()[:80])

    g = run("profiles", "--path", str(FIX / "profiles-complete.md"))
    check("four filled profiles are available", g.returncode == pb.OK
          and "count=4" in g.stdout, g.stdout.splitlines()[0])
    check("  ... and `Breaks when` is read whole when it wraps",
          "history loads eagerly." in g.stdout,
          [x for x in g.stdout.splitlines() if "Builder" in x][:1])

    i = run("profiles", "--path", str(FIX / "profiles-incomplete.md"))
    check("a half-filled profile is available but counted incomplete",
          "incomplete=2" in i.stdout, i.stdout.splitlines()[0])
    check("  ... naming the missing fields",
          "missing: Session shape, Data volume" in i.stdout)

    # Found by the first real profile file: its two prose sections explaining a
    # tension in the design doc were counted as profiles with zero fields,
    # `count=6` where there were four. Zero fields is prose; one to three is an
    # incomplete profile. Collapsing the two would let a typo'd field name pass
    # as "not a profile" and vanish.
    check("a `##` section with no profile fields is prose, not a profile",
          "count=4" in g.stdout and "prose=1" in g.stdout,
          g.stdout.splitlines()[0])
    check("  ... and is reported rather than dropped silently",
          "skipped as prose" in g.stdout,
          [x for x in g.stdout.splitlines() if "prose" in x][:1])
    check("a profile missing some fields is still counted, not treated as prose",
          "count=2" in i.stdout and "prose=0" in i.stdout,
          i.stdout.splitlines()[0])


def check_the_probe_table_is_the_single_source() -> None:
    print("\nprobe table")
    p = run("probes", "--json")
    table = json.loads(p.stdout)
    check("every probe names at least one artifact kind",
          all(v["kinds"] for v in table.values()), str(table.keys()))
    check("every probe asks a question, not a topic",
          all(v["asks"].rstrip().endswith(("?", ".")) for v in table.values()))
    md = run("probes").stdout
    check("the markdown rendering carries every probe",
          all(f"`{k}`" in md for k in table), md[:120])


def check_fences_are_honoured() -> None:
    """A `## ` inside a fenced block is quoted output, not a boundary."""
    print("\nfences")
    body = ("## Acceptance Criteria\n\n- [ ] (+) real one\n\n"
            "```\n## Acceptance Criteria\n- [ ] (+) quoted, not real\n```\n")
    p = run("artifacts", "--body", "-", "--json", stdin=body)
    acs = [r for r in json.loads(p.stdout)["artifacts"] if r["kind"] == "AC"]
    check("a fenced heading does not open a section", len(acs) == 1, str(acs))
    check("  ... and a fenced checkbox is not an AC",
          acs and "quoted" not in acs[0]["text"], str(acs))


def main() -> int:
    print("refine probes")
    check_both_real_ac_conventions_parse()
    check_a_present_section_that_parses_to_nothing_is_an_error()
    check_artifacts_dedup_to_distinct_things()
    check_flag_precedence_is_conservative()
    check_the_findings_the_lenses_actually_produced_are_rederivable()
    check_probe_workload_stays_readable()
    check_coverage_counts_rather_than_claims()
    check_carry_forward_requires_unchanged_text()
    check_queue_reads_the_real_shapes()
    check_queue_mutations_change_exactly_one_line()
    check_next_id_is_epic_wide()
    check_profiles_are_unavailable_not_clean()
    check_the_probe_table_is_the_single_source()
    check_fences_are_honoured()
    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all refine-probes checks passed")
    return 0


def test_refine_probes_suite() -> None:
    """The pytest entry point, so the suite cannot silently pass under pytest."""
    rc = main()
    assert rc == 0, f"{len(failures)} failure(s): {', '.join(failures)}"


if __name__ == "__main__":
    sys.exit(main())
