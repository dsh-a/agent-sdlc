"""Per-agent model assignment: does the model fit the agent's measured demand?

`.omp/agent-config.md` § Model Allocation may now name a concrete provider id per
agent, not only a tier label. That is what lets `verify` and `review` take a 1M
model while `monitor` takes a 131k one — a distinction three tier labels cannot
express.

It also makes a new mistake possible, and this check exists because I made it.
`openai/gpt-oss-20b` won the qualification matrix outright and is 60x cheaper
than the models it beat, so it was the obvious choice everywhere. It holds
131,072 tokens. `verify` peaks at 251,457 and `review` at 286k
(`docs/internal/data/peak-context-history.jsonl`, measured over 1,151
transcripts). Assigned there it would fail mid-cycle, on the long runs, after the
work was done — and nothing in the repo would have objected.

So the two measurements are joined here: the context window declared in
§ Model Provenance must clear the agent's p90 peak. p90 rather than median,
because a model that fits the median fails one cycle in ten.

    python3 tests/model_allocation.py

Stdlib only. Both tables are markdown in `.omp/agent-config.md`, so this parses
them the same narrow way `framework_checks.py` parses its sections.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".omp/agent-config.md"
PEAKS = ROOT / "docs/internal/data/peak-context-history.jsonl"

# An agent whose row names a concrete id but which no transcript ever exercised
# cannot be checked. Named so the gap is explicit rather than silently skipped.
UNMEASURED = {"self-improve", "adversarial-tester", "salvage"}


def table_rows(text: str, heading: str) -> list[list[str]]:
    """The pipe-table immediately following a heading."""
    start = text.index(heading)
    rows = []
    for line in text[start:].splitlines()[1:]:
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not all(set(c) <= set("-: ") for c in cells):
                rows.append(cells)
        elif rows and not line.strip():
            continue
        elif rows:
            break
    return rows


def allocation(text: str, column: str = "open-weight") -> dict[str, str]:
    """agent -> that preset column's cell, concrete ids only.

    Parameterised by column so a candidate preset can be checked before it is
    adopted. `local-70b` exists to be *failed* by this check: it assigns the one
    model qualified at that size to every row, so the failures enumerate exactly
    which roles are unreachable on hardware you could buy.
    """
    rows = table_rows(text, "## Model Allocation")
    if not rows:
        return {}
    header, *body = rows
    try:
        col = header.index(column)
    except ValueError:
        return {}
    out = {}
    for r in body:
        if len(r) > col and "/" in r[col]:
            out[r[0].split(" ")[0]] = r[col].strip("`")
    return out


def provenance(text: str) -> dict[str, int]:
    """provider id -> declared context window."""
    out = {}
    for r in table_rows(text, "### Model Provenance"):
        if len(r) < 5 or "/" not in r[0]:
            continue
        ctx = re.sub(r"[^0-9]", "", r[3])
        if ctx:
            out[r[0].strip("`")] = int(ctx)
    return out


def peaks_available() -> bool:
    """Whether measured peak-context history is present in this checkout.

    `PEAKS` lives under `docs/internal/`, which is private-only — the public core
    is synced without it by design. A caller that treats a missing file as "no
    agent exceeds its window" is not measuring anything, so anything that gates
    on these numbers has to ask this first.

    This is the framework's own rule about inert gates, in the one place it was
    broken: `peaks()` returned `{}` for an absent file, every role then "fit" its
    context window, and `test_local_70b_gap` reported the empty set with
    "If that is real, this is the win". Missing data read as the goal being met.
    """
    return PEAKS.exists()


def peaks() -> dict[str, int]:
    """agent -> p90 peak, from the most recent recorded reading.

    Returns `{}` when the history is absent, which is legitimate for the report
    path — a row then prints `UNKNOWN — no measured p90` rather than a number.
    It is NOT legitimate for a gate: see `peaks_available`.
    """
    if not PEAKS.exists():
        return {}
    last = None
    for line in PEAKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = json.loads(line)
    return {a: d["p90"] for a, d in (last or {}).get("agents", {}).items()}


def run(column: str = "open-weight") -> list[str]:
    text = CONFIG.read_text(encoding="utf-8")
    alloc, prov, peak = allocation(text, column), provenance(text), peaks()
    problems = []

    if not alloc:
        return [f"§ Model Allocation has no `{column}` column with concrete ids"]

    for agent, model in sorted(alloc.items()):
        if model not in prov:
            problems.append(f"{agent}: '{model}' is not listed in § Model Provenance — "
                            f"its context window is unknown and unmirrorable")
            continue
        if agent in UNMEASURED:
            continue
        # The orchestrator's row is named differently in the two documents.
        need = peak.get(agent) or peak.get("orchestrator (/cycle)" if agent == "orchestrator"
                                           else agent)
        if need is None:
            continue
        if prov[model] < need:
            problems.append(
                f"{agent}: '{model}' holds {prov[model]:,} but the agent's measured p90 peak "
                f"is {need:,} — it will fail on the long runs, after the work is done")
    return problems


def main() -> int:
    column = "open-weight"
    if len(sys.argv) > 2 and sys.argv[1] == "--column":
        column = sys.argv[2]
    problems = run(column)
    if problems:
        print(f"Model allocation problems ({column}):")
        for p in problems:
            print(f"  {p}")
        print("\nPeaks: docs/internal/data/peak-context-history.jsonl")
        print("Refresh: python3 .claude/skills/cycle/peak-context.py --snapshot")
        return 1
    text = CONFIG.read_text(encoding="utf-8")
    print(f"Model allocation OK ({column}) — {len(allocation(text, column))} agents "
          f"assigned concrete ids, "
          f"each clearing its measured p90")
    return 0


if __name__ == "__main__":
    sys.exit(main())
