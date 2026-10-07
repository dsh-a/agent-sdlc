#!/usr/bin/env python3
"""findings-extract — harness findings out of run reports, as records.

Every cycle writes a `## Harness findings` section; `cycle/SKILL.md` § Finalize
makes it mandatory and `harness-findings` owns the probes and the P0-P3 scale. So
the findings exist. What has never existed is anything that reads them **across**
cycles.

That gap has a measured cost. myapp's vault holds 114 run reports, 62 with a
findings section and 226 findings between them. A base-mismatch fault appears in
35 of those reports, and where it appears as a findings heading it has been rated
**P0 three times, P1 once, P2 three times, P3 once** — the same recurring fault,
scored across the whole scale. It was first filed P0 on 2026-08-24 and was still
live six weeks later.

Nothing was lost for want of writing it down. **Severity is a single-cycle guess
by the agent that just finished the cycle, and recurrence is invisible from
inside one run.** This script is the first half of making it visible: the reports
become records, and `harness-intake` counts them.

    $ findings-extract.py ~/dev/myapp-docs/reports/myapp/report-prd-foo-2026-10-03.md
    FINDINGS reports=1 findings=7 p0=0 p1=3 p2=3 p3=1 clean=0 unparsed=0
    P1  analyzer_baseline drift detection cannot work as specified   foo 2026-10-03
    P2  worktree isolation provisioned from main, 540 commits behind foo 2026-10-03
    ...

## Exit codes

    0  findings extracted, every report accounted for
    1  no findings — every report was explicitly clean or had no section
    2  bad usage
    3  **a findings section was present and yielded nothing**

**Exit 3 is the reason this script is written the way it is.** `pitfalls.py` has
been silently inert in every cycle in every repo: it reported `unparsed=6` on
each run and nothing read the number. A parser that answers "nothing found" when
it means "I could not read this" reproduces that failure, so a section that
parses to zero is an error here, never an empty result — and the report is named.

**Labelled lines are optional and matched loosely.** The template says
`**Suggested fix:**`; live reports write `**Fix:**` and omit `**Evidence:**`
entirely. A finding missing them is still a finding, because the heading carries
the severity and the title and that is the whole identity.

**Fields are read per paragraph, never per line.** A label's value runs to the
end of its paragraph, because report prose wraps and a line-scoped read would
truncate every multi-line fix to its first line.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

OK, NONE, USAGE, UNPARSED = 0, 1, 2, 3

SECTION = re.compile(r"^##\s+Harness findings\s*$", re.MULTILINE)
# `### P1 — title`. Three real forms, all measured in myapp's 114 reports:
# 220 use an em dash, **9 use a colon** (`### P3: …`), and one carries a letter
# suffix (`P0a`, a distinct sub-finding). A regex accepting only the dash drops
# the 9 silently, which is the failure this file is built to refuse.
HEADING = re.compile(r"^#{2,4}\s*(P[0-3])([a-z]?)\s*[—–:-]+\s*(.+?)\s*$")

# Real `###` headings that sit inside a findings section and are not findings.
# 52 of them across the corpus. They are skipped, but an *unrecognised* heading
# is reported rather than dropped — a new sub-section name must not quietly eat
# the findings under it.
KNOWN_SUBHEADINGS = (
    "what worked", "probes checked", "probes answered", "skill gaps",
    "rescue", "orchestrator", "what would actually help", "calibration",
)
ANY_HEADING = re.compile(r"^#{1,4}\s+\S")
# The explicit "nothing to report" sentence. `harness-findings` requires it to be
# written only when the probes were actually worked, so it is a claim, not a
# default — and it is a different fact from a section that would not parse.
CLEAN = re.compile(r"\bNone\b.{0,40}\bprobes?\b.{0,40}\bclean\b", re.IGNORECASE | re.DOTALL)

# Label synonyms. The template and the live reports disagree, and both are real.
LABELS = {
    "fix": ("suggested fix", "fix", "proposed", "proposed fix"),
    "evidence": ("evidence", "where", "source"),
}
# `**Fix:** text` puts the colon *inside* the emphasis. An earlier version of
# this pattern required a colon on both sides of it and so matched none of the
# 204 real fix lines in the corpus — caught by a fixture copied from a live
# report, which is the only reason it was caught.
LABEL_LINE = re.compile(r"^\s*\**\s*([A-Za-z][A-Za-z ]{1,24}?)\s*:\s*\**\s*")

REPORT_NAME = re.compile(r"^report-(?:prd-)?(?P<feature>.+?)-(?P<date>\d{4}-\d{2}-\d{2})\.md$")

WS = re.compile(r"\s+")


def normalise(s: str) -> str:
    """Whitespace-collapsed, lowercased, markdown emphasis and code ticks gone.

    The fingerprint of a finding. Titles reword between cycles — "inert for every
    cycle" became "inert in every cycle, in every repo" — so this is the input to
    a similarity match, not an equality test. `harness-intake` owns the matching.
    """
    s = re.sub(r"[`*_]", "", s)
    return WS.sub(" ", s).strip().lower()


def paragraphs(text: str) -> list[str]:
    out, buf = [], []
    for ln in text.splitlines():
        if ln.strip():
            buf.append(ln)
        elif buf:
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out


def labelled(body: str, which: str) -> str:
    """A label's value, from the label to the end of its run. Empty when absent.

    The label is **not** at a paragraph boundary in real reports — it lands on the
    last line of a prose paragraph, with no blank line before it:

        ... so the diff is guaranteed non-empty on every cycle.
        **Fix:** compare the finding lines or strip the `(ran in …)` tail.

    So the scan is line-anchored and the value runs from the label to the next
    blank line, the next label, or the next heading — never merely to the end of
    the line it started on, because these values wrap.
    """
    wanted = LABELS[which]
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        m = LABEL_LINE.match(ln)
        if not m or normalise(m.group(1)) not in wanted:
            continue
        parts = [ln[m.end():]]
        for nxt in lines[i + 1:]:
            if not nxt.strip() or ANY_HEADING.match(nxt) or LABEL_LINE.match(nxt):
                break
            parts.append(nxt)
        return WS.sub(" ", " ".join(parts)).strip()
    return ""


FENCE = re.compile(r"^\s{0,3}(```|~~~)")


def fenced_lines(lines: list[str]) -> set[int]:
    """Indices of lines inside a fenced code block, fence markers included.

    Reports quote `##` and `###` headings inside fenced output. Without this the
    section boundary *and* each finding's body end on quoted text — the section
    boundary was fixed first and the per-finding split was not, which a fixture
    carrying a real quoted `## Harness findings` block caught.
    """
    out: set[int] = set()
    fence: str | None = None
    for i, ln in enumerate(lines):
        f = FENCE.match(ln)
        if f:
            if fence and ln.strip().startswith(fence):
                out.add(i)
                fence = None
                continue
            if fence is None:
                fence = f.group(1)
        if fence is not None:
            out.add(i)
    return out


def section_of(text: str, whole: bool = False) -> str | None:
    """The `## Harness findings` body, or None when the report has no section.

    **Fence-aware.** Reports quote `## ` lines inside fenced blocks, and two in
    the corpus put one where a naive scan cuts the section short. The same
    orchestrator error is recorded in the 2026-10-03 findings doc: partitioning a
    Markdown body on a heading string that also appeared in its own prose
    reported `ACs: 0` for a document with 9.

    With `whole`, the entire document is the section — the mode for a standalone
    `findings-*.md`, which has no enclosing `## Harness findings` heading. That
    is selected by filename, so it is an explicit mode and never an inference.
    """
    if whole:
        return text
    m = SECTION.search(text)
    if not m:
        return None
    rest = text[m.end():]
    out, fence = [], None
    for line in rest.splitlines(keepends=True):
        f = FENCE.match(line)
        if f:
            fence = None if fence and line.strip().startswith(fence) else (fence or f.group(1))
        elif fence is None and re.match(r"^##\s+(?!#)", line):
            break
        out.append(line)
    return "".join(out)


# Path- and file-shaped backticked tokens only. A looser pattern pulled in
# `main`, `develop`, `test` and a commit sha, which group everything to
# everything. Restricting to tokens carrying a `/` or a known extension keeps the
# ones that identify a component.
ARTIFACT = re.compile(r"`([A-Za-z0-9_@.-]*(?:/[A-Za-z0-9_@.*-]+)+"
                      r"|[A-Za-z0-9_-]+\.(?:py|sh|ts|md|dart|yml|yaml|json|sample))`")


def artifacts_in(title: str, body: str) -> list[str]:
    """Backticked script, path and config tokens, lowercased and deduped.

    Titles never repeat — 226 findings in the corpus have 226 distinct titles —
    so recurrence cannot be matched on wording alone. What the six occurrences of
    the worktree fault *do* share is the artifact they name: `worktree`,
    `isolation`. These tokens are the stable half of a finding's identity and the
    input `harness-intake` groups on.
    """
    seen: list[str] = []
    for m in ARTIFACT.finditer(f"{title}\n{body}"):
        tok = m.group(1).lower().strip("./")
        tok = tok.rsplit("/", 1)[-1] if tok.endswith((".py", ".sh", ".ts")) else tok
        if tok and tok not in seen:
            seen.append(tok)
    return seen[:12]


def findings_in(text: str, source: pathlib.Path) -> tuple[list[dict], str, list[str]]:
    """`(records, status, notes)`; status is `ok`, `clean`, `absent` or `unparsed`.

    `unparsed` is the case the whole script exists to make loud: a section that is
    present, is not the explicit clean sentence, and yields no finding.
    """
    whole = source.name.startswith("findings-")
    body = section_of(text, whole=whole)
    if body is None:
        return [], "absent", []

    m = REPORT_NAME.match(source.name)
    feature = m.group("feature") if m else source.stem
    date = m.group("date") if m else ""
    if not date:
        d = re.search(r"(\d{4}-\d{2}-\d{2})", source.name)
        date = d.group(1) if d else ""

    records: list[dict] = []
    notes: list[str] = []
    lines = body.splitlines()
    inside = fenced_lines(lines)
    starts = [(i, h) for i, ln in enumerate(lines)
              if i not in inside and (h := HEADING.match(ln))]
    known = {i for i, _ in starts}

    # An unrecognised heading inside the section is reported, never ignored: a new
    # sub-section name must not quietly absorb the findings beneath it.
    for i, ln in enumerate(lines):
        if i in known or i in inside or not ANY_HEADING.match(ln):
            continue
        if whole and ln.startswith("# "):
            continue                      # the standalone doc's own title
        name = normalise(re.sub(r"^#+\s*", "", ln))
        if not any(k in name for k in KNOWN_SUBHEADINGS):
            notes.append(f"{source}:{i + 1} — heading {name[:56]!r} is neither "
                         f"P[0-3] nor a known sub-section")

    for n, (i, h) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        for j in range(i + 1, end):
            if j in inside:
                continue
            if ANY_HEADING.match(lines[j]) and not HEADING.match(lines[j]):
                end = j
                break
        title = h.group(3).strip()
        text_body = "\n".join(lines[i + 1:end]).strip()
        records.append({
            "severity": h.group(1),
            "suffix": h.group(2),
            "title": title,
            "fingerprint": normalise(title),
            "artifacts": artifacts_in(title, text_body),
            "body": text_body,
            "fix": labelled(text_body, "fix"),
            "evidence": labelled(text_body, "evidence"),
            "report": str(source),
            "feature": feature,
            "date": date,
        })

    if records:
        return records, "ok", notes
    if CLEAN.search(body):
        return [], "clean", notes
    return [], "unparsed", notes


def collect(paths: list[pathlib.Path]) -> tuple[list[dict], dict[str, list[str]]]:
    records: list[dict] = []
    status: dict[str, list[str]] = {"clean": [], "absent": [], "unparsed": [],
                                   "unreadable": [], "notes": []}
    for p in sorted(paths):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            status["unreadable"].append(f"{p} ({e})")
            continue
        recs, st, notes = findings_in(text, p)
        records.extend(recs)
        status.setdefault("notes", []).extend(notes)
        if st != "ok":
            status[st].append(str(p))
    return records, status


def resolve(a: argparse.Namespace) -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for raw in a.paths:
        p = pathlib.Path(raw).expanduser()
        if p.is_dir():
            paths.extend(sorted(p.glob(a.glob)))
            paths.extend(sorted(p.glob("findings-*.md")))
        elif p.is_file():
            paths.append(p)
        else:
            paths.append(p)      # reported as unreadable, never skipped silently
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="findings-extract.py",
        description="Harness findings out of run reports, as records. "
                    "0 found, 1 none, 2 usage, 3 a section that would not parse.",
    )
    ap.add_argument("paths", nargs="*", help="report files and/or directories of them")
    ap.add_argument("--glob", default="report-*.md",
                    help="pattern used inside a directory (default: report-*.md)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--severity", action="append", choices=("P0", "P1", "P2", "P3"),
                    help="keep only these; repeatable")
    ap.add_argument("--max-rows", type=int, default=40)
    a = ap.parse_args(argv)

    if not a.paths:
        print("FINDINGS verdict=usage — name at least one report or directory", file=sys.stderr)
        return USAGE

    paths = resolve(a)
    records, status = collect(paths)
    if a.severity:
        records = [r for r in records if r["severity"] in a.severity]

    tally = {s: sum(1 for r in records if r["severity"] == s) for s in ("P0", "P1", "P2", "P3")}
    head = (f"FINDINGS reports={len(paths)} findings={len(records)} "
            + " ".join(f"{k.lower()}={v}" for k, v in tally.items())
            + f" clean={len(status['clean'])} unparsed={len(status['unparsed'])}")

    if a.as_json:
        json.dump({"header": head, "findings": records,
                   "clean": status["clean"], "absent": status["absent"],
                   "unparsed": status["unparsed"], "unreadable": status["unreadable"],
                   "notes": status["notes"]},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(head)
        for r in records[: a.max_rows]:
            print(f"{r['severity']}  {r['title'][:68]:70} {r['feature'][:28]} {r['date']}")
        if len(records) > a.max_rows:
            print(f"... {len(records) - a.max_rows} more")
        for p in status["unparsed"]:
            print(f"unparsed: {p} — has a findings section that yielded nothing")
        for n in status["notes"][: a.max_rows]:
            print(f"note: {n}")
        for p in status["unreadable"]:
            print(f"unreadable: {p}")

    if status["unparsed"] or status["unreadable"]:
        return UNPARSED
    return OK if records else NONE


if __name__ == "__main__":
    sys.exit(main())
