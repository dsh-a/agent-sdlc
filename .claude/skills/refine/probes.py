#!/usr/bin/env python3
"""probes.py — enumerate a story's probeable artifacts, and own the question queue.

`/refine` Step 3 was 74 lines of prose asking the agent to consider seven topics
through five personas. It produced a finding only when the agent happened to think
of one, and `clean` on the coverage line was a claim nobody could check: a probe
never run and a probe that found nothing printed the same word. Of ~25 bullets in
those five sections, about five were probes — an input, a question, a falsifiable
verdict — and the rest were topics. The topics found nothing on the one story the
lenses were trialled against.

So stop asking for coverage and start counting it. A probe takes an **artifact** —
one acceptance criterion, one unmeasured number, one inherited citation — and
returns a verdict about that artifact. Coverage is then arithmetic: nineteen open
ACs and nineteen `ac-strict` verdicts, or a named gap. That requires the artifacts
to be enumerable, which is this script's job.

    python3 .claude/skills/refine/probes.py artifacts --body - < body.md
    ARTIFACTS ac=19 number=12 citation=9 xref=14 mechanism=7 deferral=6 question=9
    AC  ac-1  open,pos        Each suite has the home decided in this pass…
    AC  ac-12 open,pos,threshold  A PR-time freshness assertion notices a dead…
    NUMBER  num-3  ungrounded  6 minutes

**What is deterministic and what is not.** `AC`, `QUESTION`, `CITATION` and `XREF`
are structural — a checkbox under a named heading, a `file.ext:line`, a `#1234`.
`NUMBER`, `MECHANISM` and `DEFERRAL` are **heuristic candidates**, and the header
says so. The script's contract is to enumerate and to flag; every verdict is the
agent's. A candidate the agent dismisses costs one line. A missed artifact is
invisible, which is the failure this replaces, so the patterns err toward noise.

**The flags are what keep the gate usable.** #413 carries 28 citations; asking for
28 `inherited-claim` verdicts is a gate that cries wolf and therefore a gate whose
failures get dismissed (`evidence` § tables). So a citation sitting next to a
grounding marker is flagged `grounded` and the probe skips it; `coverage` requires
verdicts only for the residue.

Verbs:

  artifacts   enumerate the probeable artifacts in an issue body
  probes      print the probe table — the single source of truth for SKILL.md
  coverage    cross the artifacts against this pass's verdicts; name the gaps
  queue       read / next-id / add / resolve the `## Open questions` section
  profiles    parse the project's customer-profile file into probe inputs

**Nothing here writes a file and nothing invokes a shell.** Mutating verbs print
the whole modified body to stdout for `gh issue edit --body-file -`, so a partial
write is unexpressible and the result is verifiable with
`evidence.py round-trip`.

Exit codes follow the house convention, not grep's:

    0   determinate — the work produced a result
    1   determinate — refused, or nothing matched
    2   bad usage
    3   **could not determine**

Three invariants, each one a failure class already paid for:

  * **A section that is present and yields nothing exits 3**, with the section
    named. `pitfalls.py` shipped for months reporting `unparsed=6` on every run
    while nothing read the number; an empty result that looks like a clean result
    is how a gate goes inert.
  * **An absent section is not an empty one.** A spike legitimately has no
    acceptance criteria, so `ac=0 (absent)` and `ac=0 (present, unparsed)` are
    different outcomes with different exit codes.
  * **Nothing accepts an expected total.** Predicted counts were wrong three times
    in one session while the content was right, so `coverage` reports each pair's
    disposition and has no total to check against.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
import sys

OK, REFUSED, USAGE, UNDETERMINED = 0, 1, 2, 3


# --------------------------------------------------------------------------- #
# The probe table. SKILL.md renders this; `framework_checks` asserts the two
# agree, so the doc and the script cannot drift.
# --------------------------------------------------------------------------- #

PROBES: dict[str, tuple[tuple[str, ...], str | None, str]] = {
    "inherited-claim": (
        ("CITATION",), "ungrounded",
        "Is this true today? A claim inherited from the epic or a sibling is "
        "suspect by default — agreeing with the parent is a shared source, not "
        "corroboration.",
    ),
    "measured-number": (
        ("NUMBER",), "ungrounded",
        "Was this measured, or inherited? Name the measurement or demote it to "
        "an open question.",
    ),
    "mechanism-exists": (
        ("MECHANISM",), "unproven",
        "Does this behave as claimed? Run it and paste the command with its "
        "exact output — reading the docs is not proving. And is a sibling "
        "already introducing it? One mechanism across siblings, not two.",
    ),
    "ac-strict": (
        ("AC",), "open",
        "Could this be marked satisfied while the thing it protects is still "
        "broken, or could two engineers disagree that it passed?",
    ),
    "deferred-number": (
        ("AC",), "threshold",
        "A deferred number is not an agreed one. Name it, or make it an open "
        "question — an unnamed threshold is satisfiable by one that never fires.",
    ),
    "concrete-deferral": (
        ("DEFERRAL",), "prose",
        "What does the user see concretely — hidden, disabled, or "
        "visible-and-inert?",
    ),
    "named-edge": (
        ("XREF",), "dependency",
        "Is this edge filed as a dependency, or invented? Two stories touching "
        "one subject are not dependent; record that you checked and found none.",
    ),
    "independently-demonstrable": (
        ("CHILD",), None,
        "Can this child be demonstrated without running its sibling? A seam "
        "needs evidence, not a count.",
    ),
    "profile-impact": (
        ("PROFILE",), None,
        "Does this story serve or degrade this customer? 'All of them equally' "
        "is the answer to distrust.",
    ),
}


# --------------------------------------------------------------------------- #
# Fence-aware structure
# --------------------------------------------------------------------------- #

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def fenced(lines: list[str]) -> list[bool]:
    """Index -> is this line inside a fenced block (the fence lines included).

    A `## ` inside a fenced block is quoted output, not a section boundary. The
    same bug cost `findings-extract.py` a finding before its fixtures caught it.
    """
    out: list[bool] = []
    marker: str | None = None
    for line in lines:
        m = FENCE.match(line)
        if marker is None and m:
            marker = m.group(1)[0]
            out.append(True)
            continue
        if marker is not None:
            out.append(True)
            if m and m.group(1)[0] == marker:
                marker = None
            continue
        out.append(False)
    return out


def section(lines: list[str], pattern: str) -> tuple[int, int] | None:
    """Fence-aware span of a `##`/`###` section whose title matches `pattern`.

    Returns (first body line, end-exclusive), or None when the heading is absent
    — which is a different outcome from a heading whose body is empty.
    """
    inside = fenced(lines)
    head = re.compile(r"^(#{2,4})\s*" + pattern, re.I)
    start = level = None
    for i, line in enumerate(lines):
        if inside[i]:
            continue
        m = head.match(line)
        if m and start is None:
            start, level = i + 1, len(m.group(1))
            continue
        if start is not None and not inside[i]:
            m2 = re.match(r"^(#{1,4})\s", line)
            if m2 and len(m2.group(1)) <= level:
                return start, i
    if start is None:
        return None
    return start, len(lines)


CHECKBOX = re.compile(r"^(\s*)[-*]\s+\[([ xX])\]\s*(.*)$")
# Acceptance criteria are a checkbox list on one story and an ordered list on its
# sibling — #413 writes `- [ ] (+) …` and #488 writes `1. (+) …`, both live in
# epic 0.36. Reading only one convention reported `ac=0` on half the corpus.
ORDERED = re.compile(r"^(\s*)\d{1,3}[.)]\s+(.*)$")
BULLET = re.compile(r"^(\s*)[-*]\s+(?!\[[ xX]\])(.*)$")


def list_items(lines: list[str], span: tuple[int, int],
               bullets: bool = False) -> list[dict]:
    """Top-level list items in a span, each carrying its continuation lines.

    Checkbox, ordered and (optionally) plain-bullet items all count. An item with
    no checkbox is `checked=False`: a numbered AC is open until something else
    says otherwise, and guessing it closed would hide it from `ac-strict`.

    Acceptance criteria in the live corpus are multi-line — #413's first AC holds
    a six-row markdown table and its fifteenth a blockquote. A line-scoped reader
    sees a fragment of each, which is the `evidence` rule about judging paragraphs
    rather than lines, applied to list items.
    """
    inside = fenced(lines)
    start, end = span
    items: list[dict] = []
    cur: dict | None = None
    for i in range(start, end):
        line = lines[i]
        m = mo = mb = None
        if not inside[i]:
            m = CHECKBOX.match(line)
            mo = None if m else ORDERED.match(line)
            mb = None if (m or mo) or not bullets else BULLET.match(line)
        if m and len(m.group(1)) == 0:
            if cur:
                items.append(cur)
            cur = {
                "line": i + 1,
                "checked": m.group(2).lower() == "x",
                "head": m.group(3).strip(),
                "body": [m.group(3).strip()],
            }
            continue
        if (mo or mb) and len((mo or mb).group(1)) == 0:
            if cur:
                items.append(cur)
            head = (mo or mb).group(2).strip()
            cur = {"line": i + 1, "checked": False, "head": head,
                   "body": [head]}
            continue
        if cur is None:
            continue
        if not inside[i] and re.match(r"^#{1,4}\s", line):
            break
        if not inside[i] and re.match(r"^---+\s*$", line):
            break
        if line.strip() == "" or line.startswith((" ", "\t", ">")) or inside[i]:
            cur["body"].append(line.strip())
            continue
        # A flush-left non-checkbox line ends the list.
        break
    if cur:
        items.append(cur)
    for it in items:
        it["text"] = " ".join(x for x in it["body"] if x).strip()
    return items


# --------------------------------------------------------------------------- #
# Artifact extraction
# --------------------------------------------------------------------------- #

GROUNDED_NEAR = re.compile(
    r"\b(measured|verified|re-verified|proven|grounding|grounded|observed|"
    r"confirmed|checked)\b", re.I)

PROOF_MARKER = re.compile(
    r"\b(proven by experiment|measured \d|exit \d+|→ exit|verified mechanism|"
    r"re-verified|not assumed|established by running)\b", re.I)

THRESHOLD_WORD = re.compile(
    r"\b(an? agreed|appropriate|reasonable|acceptable|suitable|sensible|"
    r"TBD|to be determined|some|a defined)\s+"
    r"(threshold|limit|budget|ceiling|number|value|cadence|interval)\b", re.I)

DEP_WORD = re.compile(
    r"\b(blocked[_ ]by|blocking|blocker|depends? on|dependenc|prerequisite|"
    r"after|requires)\b", re.I)

UNIT = (r"(?:minutes?|mins?|seconds?|secs?|hours?|hrs?|days?|weeks?|months?|"
        r"ms|bytes?|[KMG]B|rows?|files?|lines?|tests?|runs?|commits?|"
        r"occurrences?|chars?|tokens?|%)")
NUMBER_RE = re.compile(
    rf"(?<![\w#:.\-/])((?:\d+(?:[,.]\d+)*)\s*{UNIT})\b", re.I)
DURATION_RE = re.compile(r"(?<![\w#:.\-])(\d+m\d+s)\b")
EXIT_RE = re.compile(r"\bexits?\s+(\d{1,3})\b", re.I)

CITATION_RE = re.compile(
    r"\b([\w./-]+\.(?:dart|ya?ml|md|json|py|sh|ts|tsx|cs|sql|toml|cfg))"
    r"(:\d+(?:[-–]\d+)?)")
BARE_LINE_RE = re.compile(r"`(:\d+(?:[-–]\d+)?)`")
XREF_RE = re.compile(r"(?<![\w])#(\d{1,6})\b")

# A mechanism claim is about behaviour you could run, so its subject has to be
# command- or annotation-shaped: a tool with an argument, a flag, or an
# annotation. A bare `ci.yml` mention is a reference, not a claim — matching it
# produced 52 candidates on one story, which is a gate nobody would read.
MECHANISM_SUBJECT = re.compile(
    r"`(?:[^`]*(?:--[a-z][\w-]+|(?<![\w-])-[a-zA-Z](?![\w-]))[^`]*"
    r"|@[A-Z]\w+\([^`]*\)"
    r"|(?:flutter|dart|gh|git|npm|pytest|supabase|python3?)\s+[\w./-]+[^`]*)`")
MECHANISM_VERB = re.compile(
    r"\b(does|do|is|are|will|cannot|can|rejects?|honou?rs?|reads?|applies|"
    r"exits?|supports?|ignores?|requires?|selects?|runs?|fails?|accepts?|"
    r"overrides?|respects?)\b", re.I)

DEFERRAL_PHRASE = re.compile(
    r"\b(out of scope|not in scope|deferred?|defers? to|will not|does not|"
    r"is not included|excluded from this story|not this story|later story)\b",
    re.I)

NEG_AC = re.compile(r"^\(\s*[−\-–]\s*\)")
POS_AC = re.compile(r"^\(\s*\+\s*\)")


def _near(lines: list[str], i: int, radius: int, pat: re.Pattern) -> bool:
    lo, hi = max(0, i - radius), min(len(lines), i + radius + 1)
    return bool(pat.search(" ".join(lines[lo:hi])))


def _clip(text: str, width: int = 110) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= width else text[: width - 1] + "…"


def extract(body: str) -> tuple[list[dict], dict, list[str]]:
    """Enumerate artifacts. Returns (rows, section-status, notes)."""
    lines = body.splitlines()
    inside = fenced(lines)
    rows: list[dict] = []
    notes: list[str] = []
    status: dict[str, str] = {}
    n = {k: 0 for k in
         ("AC", "QUESTION", "NUMBER", "CITATION", "XREF", "MECHANISM",
          "DEFERRAL")}

    # Dedup key -> row. An artifact is a distinct thing, not an occurrence:
    # `#554` appears 14 times in one real body and is one dependency to judge,
    # not fourteen. Flags union across occurrences, and `grounded` wins over
    # `ungrounded` — a claim measured anywhere in the body is measured.
    seen: dict[tuple[str, str], dict] = {}

    def add(kind: str, flags: list[str], text: str, line: int,
            key: str | None = None) -> dict:
        k = (kind, (key if key is not None else text).strip().lower())
        if k in seen:
            row = seen[k]
            merged = set(row["flags"]) | set(flags)
            if kind != "NUMBER" and "grounded" in merged:
                merged.discard("ungrounded")
            if kind == "NUMBER" and "ungrounded" in merged:
                merged.discard("grounded")
            if "dependency" in merged:
                merged.discard("mention")
            row["flags"] = sorted(merged)
            row["seen"] += 1
            return row
        n[kind] += 1
        row = {"kind": kind, "id": f"{kind.lower()}-{n[kind]}",
               "flags": sorted(set(flags)), "text": _clip(text), "line": line,
               "seen": 1}
        rows.append(row)
        seen[k] = row
        return row

    # -- acceptance criteria -------------------------------------------------
    span = section(lines, r"Acceptance Criteria\b")
    if span is None:
        status["ac"] = "absent"
    else:
        items = list_items(lines, span)
        status["ac"] = "ok" if items else "unparsed"
        for it in items:
            flags = ["closed" if it["checked"] else "open"]
            flags.append("neg" if NEG_AC.match(it["head"]) else "pos")
            if THRESHOLD_WORD.search(it["text"]):
                flags.append("threshold")
            row = add("AC", flags, it["head"], it["line"],
                      key=f"ac@{it['line']}")
            row["full"] = it["text"]
            if "neg" in flags:
                add("DEFERRAL", ["ac"], it["head"], it["line"],
                    key=f"deferral@{it['line']}")

    # -- open questions ------------------------------------------------------
    span = section(lines, r"Open questions\b")
    if span is None:
        status["question"] = "absent"
    else:
        items = list_items(lines, span)
        status["question"] = "ok" if items else "unparsed"
        for it in items:
            qid = re.search(r"\bQ-\d+(?:\s*/\s*Q-\d+)*", it["text"])
            flags = ["resolved" if it["checked"] else "open"]
            tag = re.search(r"\((AC|Behavior|Scope|Data|Deps|Risk|Size)\)",
                            it["head"])
            if tag:
                flags.append(tag.group(1).lower())
            row = add("QUESTION", flags, it["head"], it["line"],
                      key=f"q@{it['line']}")
            row["qid"] = qid.group(0) if qid else ""

    # -- line-scanned artifacts ---------------------------------------------
    for i, line in enumerate(lines):
        if inside[i] or not line.strip():
            continue
        grounded = ("grounded" if _near(lines, i, 2, GROUNDED_NEAR)
                    else "ungrounded")

        for m in CITATION_RE.finditer(line):
            add("CITATION", [grounded], m.group(1) + m.group(2), i + 1)
        for m in BARE_LINE_RE.finditer(line):
            add("CITATION", [grounded, "bare"], m.group(1), i + 1)

        for m in XREF_RE.finditer(line):
            flags = [grounded,
                     "dependency" if DEP_WORD.search(line) else "mention"]
            add("XREF", flags, m.group(0), i + 1)

        for pat in (NUMBER_RE, DURATION_RE):
            for m in pat.finditer(line):
                add("NUMBER", [grounded], m.group(1), i + 1)
        for m in EXIT_RE.finditer(line):
            add("NUMBER", ["grounded", "exit-code"], m.group(0), i + 1)

        if MECHANISM_SUBJECT.search(line) and MECHANISM_VERB.search(line):
            proven = (PROOF_MARKER.search(line)
                      or _near(lines, i, 3, PROOF_MARKER))
            add("MECHANISM", ["proven" if proven else "unproven"],
                line, i + 1, key=re.sub(r"[^a-z0-9]+", "", line.lower())[:160])

        if DEFERRAL_PHRASE.search(line) and not CHECKBOX.match(line):
            add("DEFERRAL", ["prose"], line, i + 1)

    if not rows:
        notes.append("no artifacts of any kind — is this an issue body?")
    return rows, status, notes


# --------------------------------------------------------------------------- #
# Verbs
# --------------------------------------------------------------------------- #

def read_body(arg: str) -> str:
    if arg == "-":
        return sys.stdin.read()
    p = pathlib.Path(arg)
    if not p.exists():
        print(f"unresolved: {arg}", file=sys.stderr)
        sys.exit(UNDETERMINED)
    return p.read_text(encoding="utf-8")


def applicable(rows: list[dict], probe: str) -> list[dict]:
    kinds, flag, _ = PROBES[probe]
    return [r for r in rows
            if r["kind"] in kinds and (flag is None or flag in r["flags"])]


def cmd_artifacts(args: argparse.Namespace) -> int:
    rows, status, notes = extract(read_body(args.body))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["kind"].lower()] = counts.get(r["kind"].lower(), 0) + 1

    if args.json:
        print(json.dumps({"counts": counts, "sections": status,
                          "artifacts": rows, "notes": notes}, indent=2))
    else:
        head = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        bits = [f"{k}:{v}" for k, v in sorted(status.items()) if v != "ok"]
        print(f"ARTIFACTS {head}" + (f" sections[{' '.join(bits)}]" if bits else ""))
        for r in rows:
            if args.kind and r["kind"] != args.kind.upper():
                continue
            print(f"{r['kind']}\t{r['id']}\t{','.join(r['flags'])}\t"
                  f"L{r['line']}\t{r['text']}")
        for note in notes:
            print(f"note: {note}")
        print()
        print("probe workload (artifacts each probe must verdict):")
        for probe in PROBES:
            hits = applicable(rows, probe)
            if hits:
                print(f"  {probe:<28} {len(hits):>3}  "
                      f"{' '.join(r['id'] for r in hits[:8])}"
                      f"{' …' if len(hits) > 8 else ''}")

    if "unparsed" in status.values():
        bad = [k for k, v in status.items() if v == "unparsed"]
        print(f"unparsed: section present but yielded nothing: {', '.join(bad)}",
              file=sys.stderr)
        return UNDETERMINED
    return OK if rows else REFUSED


def cmd_probes(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps({k: {"kinds": list(v[0]), "flag": v[1], "asks": v[2]}
                          for k, v in PROBES.items()}, indent=2))
        return OK
    print("| Probe | Input (enumerated) | Asks |")
    print("|---|---|---|")
    for name, (kinds, flag, asks) in PROBES.items():
        scope = "/".join(k.lower() for k in kinds)
        if flag:
            scope += f" `{flag}`"
        print(f"| `{name}` | each {scope} | {asks} |")
    return OK


def cmd_coverage(args: argparse.Namespace) -> int:
    """Cross the artifacts against this pass's verdicts and name the gaps.

    The verdict file is `probe<TAB>artifact-id<TAB>verdict`, written by the agent
    as it works. Nothing parses the log comment's prose: a coverage line derived
    from prose is a coverage line that drifts from it.
    """
    rows, _, _ = extract(read_body(args.body))
    by_id = {r["id"]: r for r in rows}

    given: dict[tuple[str, str], str] = {}
    unknown: list[str] = []
    carried = 0

    text = read_body(args.verdicts)
    if not text.strip():
        print("verdicts file is empty", file=sys.stderr)
        return USAGE
    if args.prior:
        # A prior verdict is reusable only if the artifact still reads the same.
        # Keying on the id alone would carry a verdict onto whatever artifact
        # inherited that number after an edit, which is the renumbering trap
        # `enumerate` exists to catch.
        for raw in read_body(args.prior).splitlines():
            parts = [x.strip() for x in raw.split("\t")]
            if len(parts) < 4 or parts[0] not in PROBES:
                continue
            probe, aid, verdict, was = parts[0], parts[1], parts[2], parts[3]
            r = by_id.get(aid)
            if r is not None and r["text"] == was:
                given[(probe, aid)] = verdict
                carried += 1

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        parts = [p.strip() for p in raw.split("\t")]
        if len(parts) < 3:
            parts = [p.strip() for p in raw.split(None, 2)]
        if len(parts) < 3:
            unknown.append(f"malformed: {raw.strip()}")
            continue
        probe, aid, verdict = parts[0], parts[1], parts[2]
        if probe not in PROBES:
            unknown.append(f"unknown probe: {probe}")
            continue
        if aid not in by_id and probe not in ("independently-demonstrable",
                                              "profile-impact"):
            unknown.append(f"unknown artifact: {aid}")
            continue
        given[(probe, aid)] = verdict

    gaps: list[tuple[str, str]] = []
    summary: list[str] = []
    for probe in PROBES:
        need = applicable(rows, probe)
        if not need:
            continue
        missing = [r["id"] for r in need if (probe, r["id"]) not in given]
        gaps += [(probe, m) for m in missing]
        summary.append(f"{probe} {len(need) - len(missing)}/{len(need)}")

    print(f"COVERAGE probes={len(summary)} gaps={len(gaps)} "
          f"carried={carried} unknown={len(unknown)}")
    for probe, aid in gaps:
        r = by_id.get(aid)
        print(f"GAP\t{probe}\t{aid}\t{r['text'] if r else ''}")
    for u in unknown:
        print(f"UNKNOWN\t{u}")
    print()
    print("**Probes:** " + " · ".join(summary) if summary
          else "**Probes:** no applicable artifacts")

    if unknown:
        return UNDETERMINED
    return REFUSED if gaps else OK


# -- queue ------------------------------------------------------------------ #

QUEUE_HEADING = "## Open questions"
QUEUE_NOTE = ("<!-- Auto-maintained by /refine. Edit answers here only if you "
              "want them treated as resolved. -->")


def queue_span(lines: list[str]) -> tuple[int, int] | None:
    return section(lines, r"Open questions\b")


def cmd_queue(args: argparse.Namespace) -> int:
    if args.queue_verb == "next-id":
        high = 0
        for src in args.body_files:
            for m in re.finditer(r"\bQ-(\d+)\b", read_body(src)):
                high = max(high, int(m.group(1)))
        print(f"Q-{high + 1}")
        return OK if high else REFUSED

    body = read_body(args.body)
    lines = body.splitlines()
    span = queue_span(lines)

    if args.queue_verb == "read":
        if span is None:
            print("QUEUE absent", file=sys.stderr)
            return UNDETERMINED
        items = list_items(lines, span)
        if not items:
            print("QUEUE present but yielded nothing", file=sys.stderr)
            return UNDETERMINED
        openn = sum(1 for i in items if not i["checked"])
        print(f"QUEUE items={len(items)} open={openn} "
              f"resolved={len(items) - openn}")
        for it in items:
            qid = re.search(r"\bQ-\d+(?:\s*/\s*Q-\d+)*", it["text"])
            print(f"{'x' if it['checked'] else ' '}\t"
                  f"{qid.group(0) if qid else '-'}\tL{it['line']}\t"
                  f"{_clip(it['head'])}")
        return OK

    # Mutating verbs print the whole body; nothing is written here.
    if span is None:
        print("refusing: no `## Open questions` section to modify",
              file=sys.stderr)
        return REFUSED
    start, end = span

    if args.queue_verb == "add":
        entry = f"- [ ] ({args.tag}) {args.text}"
        if args.id:
            entry = f"- [ ] ({args.tag}) **{args.id}** — {args.text}"
        insert = end
        while insert > start and not lines[insert - 1].strip():
            insert -= 1
        new = lines[:insert] + [entry] + lines[insert:]
        print("\n".join(new))
        return OK

    if args.queue_verb == "resolve":
        items = list_items(lines, span)
        target = None
        for it in items:
            if args.id.lower() in it["text"].lower() and not it["checked"]:
                target = it
                break
        if target is None:
            print(f"refusing: no open queue item matching {args.id!r}",
                  file=sys.stderr)
            return REFUSED
        i = target["line"] - 1
        m = CHECKBOX.match(lines[i])
        assert m
        date = args.date or _dt.date.today().isoformat()
        head = m.group(3).strip()
        lines[i] = (f"{m.group(1)}- [x] ~~{head}~~ → {args.answer} "
                    f"(resolved {date})")
        print("\n".join(lines))
        return OK

    return USAGE


# -- profiles --------------------------------------------------------------- #

PROFILE_FIELDS = ("Goal", "Session shape", "Data volume", "Breaks when")


def cmd_profiles(args: argparse.Namespace) -> int:
    """Parse the project's customer-profile file into probe inputs.

    **An absent file is `unavailable`, never `clean`.** Could-not-determine is
    never absent (`evidence` § The discipline). A profile probe that silently
    reported nothing because nobody wrote the file is `pitfalls.py` again: inert
    for months, printing a number nobody read.
    """
    p = pathlib.Path(args.path)
    if not p.exists():
        print(f"PROFILES verdict=unavailable path={args.path} reason=absent")
        print("unresolved: the profile probe cannot run; say so in the log "
              "rather than reporting the lens clean", file=sys.stderr)
        return UNDETERMINED

    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    inside = fenced(lines)
    profiles: list[dict] = []
    cur: dict | None = None
    for i, line in enumerate(lines):
        if inside[i]:
            continue
        m = re.match(r"^##\s+(?!#)(.+?)\s*$", line)
        if m:
            if cur:
                profiles.append(cur)
            cur = {"name": m.group(1).strip(), "line": i + 1, "fields": {}}
            continue
        if cur is None:
            continue
        fm = re.match(r"^\s*[-*]?\s*\*{0,2}(" + "|".join(PROFILE_FIELDS)
                      + r")\*{0,2}\s*:\s*(.*?)\s*$", line, re.I)
        if fm:
            last = fm.group(1).strip().lower()
            cur["fields"][last] = fm.group(2).strip()
            continue
        # A field value wraps. Judge paragraphs, not lines: `Breaks when` is the
        # longest field and the one the `degrades` verdict reads, so truncating
        # it at the first newline loses the half that names the condition.
        if cur["fields"] and line.strip() and line.startswith((" ", "\t")):
            key = list(cur["fields"])[-1]
            cur["fields"][key] = (cur["fields"][key] + " " + line.strip()).strip()
    if cur:
        profiles.append(cur)

    # A `##` section with *none* of the four fields is prose, not a half-written
    # profile. The first real profile file opened with two prose sections
    # explaining a tension in the design doc, and both were counted as profiles
    # with zero fields — `count=6` where there were four.
    #
    # Zero fields is prose; one to three is a profile that is incomplete. Both
    # are reported, because collapsing them would let a typo'd field name pass as
    # "not a profile" and vanish.
    wanted = {f.lower() for f in PROFILE_FIELDS}
    prose = [p_ for p_ in profiles if not (wanted & set(p_["fields"]))]
    named = [p_ for p_ in profiles
             if p_["name"].lower() != "template" and (wanted & set(p_["fields"]))]
    if not named:
        print(f"PROFILES verdict=unavailable path={args.path} "
              f"reason=no-profiles")
        print("unresolved: file present but defines no profile", file=sys.stderr)
        return UNDETERMINED

    incomplete = [p_["name"] for p_ in named
                  if not set(f.lower() for f in PROFILE_FIELDS)
                  <= set(p_["fields"])]
    print(f"PROFILES verdict=available count={len(named)} "
          f"incomplete={len(incomplete)} prose={len(prose)}")
    for k, p_ in enumerate(named, 1):
        breaks = p_["fields"].get("breaks when", "")
        print(f"PROFILE\tprofile-{k}\t{p_['name']}\t{_clip(breaks, 90)}")
    for p_ in named:
        missing = [f for f in PROFILE_FIELDS if f.lower() not in p_["fields"]]
        if missing:
            print(f"note: {p_['name']} is missing: {', '.join(missing)}")
    for p_ in prose:
        print(f"note: skipped as prose (no profile fields): {p_['name']}")
    return OK


# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="probes.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="verb", required=True)

    a = sub.add_parser("artifacts", help="enumerate probeable artifacts")
    a.add_argument("--body", required=True, help="issue body file, or - for stdin")
    a.add_argument("--kind", help="print only this kind")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_artifacts)

    p = sub.add_parser("probes", help="print the probe table")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_probes)

    c = sub.add_parser("coverage", help="cross artifacts against verdicts")
    c.add_argument("--body", required=True)
    c.add_argument("--verdicts", required=True,
                   help="TSV: probe<TAB>artifact-id<TAB>verdict")
    c.add_argument("--prior",
                   help="a previous pass's verdict TSV; a verdict carries "
                        "forward only when the artifact's text is unchanged")
    c.set_defaults(func=cmd_coverage)

    q = sub.add_parser("queue", help="own the `## Open questions` section")
    qs = q.add_subparsers(dest="queue_verb", required=True)
    qr = qs.add_parser("read")
    qr.add_argument("--body", required=True)
    qn = qs.add_parser("next-id", help="highest Q-n across an epic, plus one")
    qn.add_argument("body_files", nargs="+")
    qa = qs.add_parser("add", help="print the body with one question appended")
    qa.add_argument("--body", required=True)
    qa.add_argument("--tag", required=True)
    qa.add_argument("--text", required=True)
    qa.add_argument("--id")
    qv = qs.add_parser("resolve", help="print the body with one question closed")
    qv.add_argument("--body", required=True)
    qv.add_argument("--id", required=True)
    qv.add_argument("--answer", required=True)
    qv.add_argument("--date")
    q.set_defaults(func=cmd_queue)

    pr = sub.add_parser("profiles", help="parse the customer-profile file")
    pr.add_argument("--path", required=True)
    pr.set_defaults(func=cmd_profiles)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
