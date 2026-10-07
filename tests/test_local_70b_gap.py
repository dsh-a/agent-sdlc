#!/usr/bin/env python3
"""How far is the fleet from running on hardware you could buy?

A 552B model is a provider you rent — engineering-meta `inference/deployment-plan.md` prices its serving
floor at a 4-GPU tray, $16-42/hr, roughly an order of magnitude worse than
paying per token. So the portability question that actually matters is: **which
roles run at or under 70B**, where one card is $1.49-3.99/hr and mirroring the
weights is an external SSD rather than half a terabyte.

At that size exactly one model has cleared any probe — `openai/gpt-oss-20b`,
which scored 100% on review, 100% on verify and 83% on test-preflight in
`docs/internal/qualification-matrix.md`, beating every larger model tested. It
holds 131,072 tokens.

So the gap is not capability, it is context. This test pins which side of that
line each role sits on, and fails when the set changes **in either direction**:

  * a role dropping under the line is the goal of Workstream A and the chain
    work, and should be noticed the moment it happens rather than months later;
  * a role crossing over is the same silent growth that took the orchestrator
    baseline up 60% in three weeks before anything objected.

This is a ratchet, not a gate on correctness. `local-70b` is a target preset and
`model_allocation.py --column local-70b` is *expected* to report problems; what
must not drift unnoticed is which ones.

    python3 tests/test_local_70b_gap.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import model_allocation  # noqa: E402

# Measured 2026-09-24 against docs/internal/data/peak-context-history.jsonl.
# Re-record deliberately, with the reason, when a number here moves.
OVER_131K = {
    "orchestrator": 375_233,
    "review": 285_899,
    "verify": 251_457,
    "test": 173_564,
}

WINDOW = 131_072

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def main() -> int:
    print("local-70b gap")

    # This is a ratchet over measured p90 context, and the measurements live in
    # `docs/internal/data/peak-context-history.jsonl` — private-only, so the
    # public core is synced without them. Skip rather than run: with no data
    # every role trivially "fits" its window, the over-131k set empties, and the
    # failure text reads "If that is real, this is the win" — a missing file
    # reported as the goal being achieved. Loudly skipped beats vacuously
    # passed, and beats failing on a checkout that was never meant to carry the
    # data.
    if not model_allocation.peaks_available():
        print(f"  no measured peak-context history at "
              f"{model_allocation.PEAKS.relative_to(model_allocation.ROOT)}")
        print("\nlocal-70b gap: SKIPPED — needs private measurement data")
        return 0

    text = model_allocation.CONFIG.read_text(encoding="utf-8")
    alloc = model_allocation.allocation(text, "local-70b")
    check("the local-70b column exists and is populated", bool(alloc),
          "no column, or no concrete ids in it")
    if not alloc:
        return 1

    prov = model_allocation.provenance(text)
    sizes = {prov.get(m) for m in alloc.values()}
    check("every local-70b cell is a model listed in Provenance",
          None not in sizes, str(sorted(alloc.values())))
    check("every local-70b cell holds 131k or less — nothing above 70B crept in",
          all(s is not None and s <= WINDOW for s in sizes), str(sorted(sizes)))

    problems = model_allocation.run("local-70b")
    over = {p.split(":")[0] for p in problems}

    check("the set of roles over the window is unchanged",
          over == set(OVER_131K),
          f"expected {sorted(OVER_131K)}, got {sorted(over)}")

    if over != set(OVER_131K):
        for role in sorted(set(OVER_131K) - over):
            print(f"    -> '{role}' now FITS {WINDOW:,}. If that is real, this is "
                  f"the win — update OVER_131K and say what shrank it.")
        for role in sorted(over - set(OVER_131K)):
            print(f"    -> '{role}' has crossed OVER {WINDOW:,}. Context grew; "
                  f"find out where before re-recording.")

    fitting = len(alloc) - len(over)
    print(f"\n  {fitting}/{len(alloc)} roles fit a 20B model's window today.")
    for role, peak in sorted(OVER_131K.items(), key=lambda kv: -kv[1]):
        if role in over:
            print(f"    {role:14} {peak:>8,}  needs {peak / WINDOW:.2f}x the window")

    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("local-70b gap unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
