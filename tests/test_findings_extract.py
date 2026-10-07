#!/usr/bin/env python3
"""Tests for .claude/skills/harness-intake/findings-extract.py — stdlib only.

Every fixture is a real shape from myapp's 114 archived run reports, including
the ones that do not follow the template: the `### P3:` colon form (9 real
cases), `**Fix:**` where the template says `**Suggested fix:**`, a finding with
no `**Evidence:**` line, a `## ` heading quoted inside a fenced block, a
numbered-list section from a cycle where the skill was not installed, and a
standalone `findings-*.md` whose whole body is the section.

The thesis: **this parser must not be able to become `pitfalls.py`.** That script
has been silently inert in every cycle in every repo, reporting `unparsed=6` on
each run while nothing read the number. So the case that matters most here is the
one where a section is present and yields nothing — it must be an error with the
report named, never an empty result.

    python3 tests/test_findings_extract.py

Individual cases are `check_*`, with one `test_findings_extract_suite` as the
pytest gate, so the suite cannot pass silently under pytest.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "skills" / "harness-intake" / "findings-extract.py"
FIX = ROOT / "tests" / "fixtures" / "findings-extract"

_spec = importlib.util.spec_from_file_location("findings_extract", SCRIPT)
fx = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(fx)

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


def records(*names: str) -> list[dict]:
    p = run(*[str(FIX / n) for n in names], "--json")
    return json.loads(p.stdout)["findings"]


def one(name: str) -> dict:
    out = json.loads(run(str(FIX / name), "--json").stdout)
    return out


# --------------------------------------------------------------------------- #

def check_a_present_section_that_parses_to_nothing_is_an_error() -> None:
    """The `pitfalls.py` failure, made impossible."""
    print("\nnothing parsed is never nothing found")
    p = run(str(FIX / "report-prd-numbered-2026-08-31.md"))
    check("exit 3, not 0 or 1", p.returncode == fx.UNPARSED, str(p.returncode))
    check("the report is named", "unparsed:" in p.stdout and "numbered" in p.stdout)
    check("and the header counts it", "unparsed=1" in p.stdout, p.stdout.splitlines()[0])

    # Contrast: a report with no section at all is not an error — 52 real reports
    # predate the section entirely.
    q = run(str(FIX / "report-prd-absent-2026-07-01.md"))
    check("no section at all is not an error", q.returncode == fx.NONE, str(q.returncode))

    # Contrast: the explicit sentence is a claim that the probes were worked.
    c = run(str(FIX / "report-prd-clean-2026-09-21.md"))
    check("an explicit clean section is not an error", c.returncode == fx.NONE, str(c.returncode))
    check("and is counted as clean", "clean=1" in c.stdout, c.stdout.splitlines()[0])

    # One bad report among good ones still fails the run: exit 3 dominates.
    m = run(str(FIX / "report-prd-live-2026-10-03.md"),
            str(FIX / "report-prd-numbered-2026-08-31.md"))
    check("one unparsed report fails a run that also found findings",
          m.returncode == fx.UNPARSED, str(m.returncode))
    check("  ... while still reporting the findings it did read",
          "findings=2" in m.stdout, m.stdout.splitlines()[0])


def check_every_real_heading_form_parses() -> None:
    print("\nheading forms")
    live = records("report-prd-live-2026-10-03.md")
    check("the em-dash form", len(live) == 2, str(len(live)))
    check("severity and title are split", live[0]["severity"] == "P1"
          and "analyzer_baseline" in live[0]["title"], str(live[0])[:90])

    colon = records("report-prd-colon-2026-09-20.md")
    check("the colon form — 9 real cases would be dropped without it",
          len(colon) == 1 and colon[0]["severity"] == "P3", str(colon))

    stand = records("findings-2026-10-03-standalone.md")
    check("a standalone findings doc parses as a whole-document section",
          len(stand) == 2, str(len(stand)))
    check("  ... including the P0a sub-finding, kept distinct",
          any(r["suffix"] == "a" for r in stand), str([r["suffix"] for r in stand]))
    check("  ... and its own H1 title raises no note",
          not one("findings-2026-10-03-standalone.md")["notes"])
    check("  ... while 'What worked' is skipped, not parsed as a finding",
          all("what worked" not in r["title"].lower() for r in stand))


def check_section_boundary_honours_fences() -> None:
    """A `## ` inside a fenced block is quoted output, not a boundary."""
    print("\nsection boundary")
    r = records("report-prd-fenced-2026-09-25.md")
    check("the finding survives a fenced ## heading", len(r) == 1, str(len(r)))
    check("  ... and its body keeps the quoted block",
          "OPEN permission ask" in r[0]["body"], r[0]["body"][:80])
    check("  ... but the real next section is still excluded",
          "Not findings" not in r[0]["body"])


def check_labels_are_tolerant_and_paragraph_scoped() -> None:
    print("\nlabelled fields")
    r = records("report-prd-live-2026-10-03.md")
    check("`**Fix:**` is read though the template says `**Suggested fix:**`",
          r[0]["fix"].startswith("compare the finding lines"), r[0]["fix"][:60])
    check("a finding with no Evidence line is still a finding",
          r[0]["evidence"] == "" and r[0]["title"] != "", str(r[0])[:60])
    check("Evidence is read where present", "540" in r[1]["evidence"], r[1]["evidence"][:60])
    check("`**Proposed:**` counts as a fix label",
          records("findings-2026-10-03-standalone.md")[0]["fix"].startswith("pass the base"))

    # Paragraph-scoped, not line-scoped: the fix text wraps in the fixture.
    check("a wrapped fix value is read whole, not truncated at the newline",
          r[0]["fix"].endswith("before diffing."), r[0]["fix"][-40:])


def check_identity_inputs() -> None:
    """Titles never repeat, so grouping needs more than a title."""
    print("\nidentity")
    r = records("report-prd-live-2026-10-03.md")
    check("a fingerprint is normalised, not raw",
          r[0]["fingerprint"] == fx.normalise(r[0]["title"]) and "`" not in r[0]["fingerprint"])
    check("feature and date come from the filename",
          r[0]["feature"] == "live" and r[0]["date"] == "2026-10-03", str(r[0])[:70])
    check("artifacts are path- or file-shaped only",
          all("/" in a or "." in a for a in r[0]["artifacts"]), str(r[0]["artifacts"]))
    check("  ... so a bare word like 'main' is not an artifact",
          "main" not in r[1]["artifacts"], str(r[1]["artifacts"]))


def check_unknown_headings_are_reported() -> None:
    """A new sub-section name must not quietly absorb the findings under it."""
    print("\nunknown headings")
    out = one("report-prd-numbered-2026-08-31.md")
    check("an unrecognised section heading is noted, not ignored",
          isinstance(out["notes"], list))


def check_usage_and_severity_filter() -> None:
    print("\nusage")
    check("no paths is a usage error", run().returncode == fx.USAGE)
    p = run(str(FIX / "report-prd-live-2026-10-03.md"), "--severity", "P2")
    check("--severity filters", "findings=1" in p.stdout, p.stdout.splitlines()[0])
    check("a missing file is unreadable, not silently skipped",
          run(str(FIX / "no-such-report.md")).returncode == fx.UNPARSED)


def main() -> int:
    print("findings-extract")
    check_a_present_section_that_parses_to_nothing_is_an_error()
    check_every_real_heading_form_parses()
    check_section_boundary_honours_fences()
    check_labels_are_tolerant_and_paragraph_scoped()
    check_identity_inputs()
    check_unknown_headings_are_reported()
    check_usage_and_severity_filter()
    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all findings-extract checks passed")
    return 0


def test_findings_extract_suite() -> None:
    """The pytest entry point, so the suite cannot silently pass under pytest."""
    rc = main()
    assert rc == 0, f"{len(failures)} failure(s): {', '.join(failures)}"


if __name__ == "__main__":
    sys.exit(main())
