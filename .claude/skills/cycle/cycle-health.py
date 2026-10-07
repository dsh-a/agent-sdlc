#!/usr/bin/env python3
"""cycle-health — is each clone working, stalled, or dead?

Round 9 lost three of five cycles to the machine they ran on: two to system
sleep, one to a wake artefact that surfaced as `Not logged in`. **Every one of
them was recorded by the gate log as a `wakeup` or an unclassified interval —
the same row a healthy cycle produces while it thinks.** That is why the round's
5h21m of idle was first attributed to gates, which had in fact cost 0.2h.

A cycle cannot be trusted to report its own death: the process that would write
the row is the one that stopped. So this reads two things it cannot fake —

  * the age of the newest telemetry event in `<clone>/agent_states/events/`,
    which is written per tool call and so tracks liveness directly;
  * the tail of the clone's transcript, for the wordings a dying session leaves.

and reports one of: **running**, **idle**, **stalled**, **dead**.

`dead` requires a known fatal wording. `stalled` is silence past the threshold
with nothing to explain it — deliberately a different word, because "I know it
stopped" and "I know why it stopped" are different claims and conflating them is
how this was missed the first time.

    python3 cycle-health.py [--root ~/dev/cycles] [--stall-min 20] [--json]

Exit 0 when every clone is running or idle, 1 when any is stalled or dead, 2 on
a usage error. Never raises on a malformed transcript: a health check that
crashes is a health check that reports nothing.

Scope: this answers "is this clone working **now**". Run it during a round. A
finished round's clones read as `stalled`, because a clone that has completed its
work and one that was killed look identical from here — telling those apart is
the run's job, not the clone's, and claiming otherwise would be the same
conflation this tool exists to end.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

# Wordings a dying session leaves behind. Each is a literal seen in a real
# transcript, not a guess: the first two killed c2 and c3 in round 9, the third
# and fourth killed c5 after the host suspended mid-tool-call.
FATAL = (
    ("went to sleep", "the host slept mid-response"),
    ("Your computer went to sleep", "the host slept mid-response"),
    ("Not logged in", "the session lost authentication"),
    ("Please run /login", "the session lost authentication"),
    ("Credit balance is too low", "the account ran out of credit"),
    ("usage limit reached", "the account hit a usage limit"),
)

TAIL_BYTES = 200_000  # enough for the last few exchanges, bounded for a big file


def newest_event_age(clone: str) -> float | None:
    """Seconds since the newest telemetry event, or None if there are none."""
    newest = None
    for f in glob.glob(os.path.join(clone, "agent_states", "events", "*.jsonl")):
        try:
            m = os.path.getmtime(f)
        except OSError:
            continue
        if newest is None or m > newest:
            newest = m
    return None if newest is None else time.time() - newest


def transcript_dir(clone: str) -> str:
    """Claude Code's per-project transcript directory for this path.

    `CYCLE_HEALTH_PROJECTS` overrides the root so this is testable without
    writing into the operator's real `~/.claude/projects`.
    """
    root = os.environ.get("CYCLE_HEALTH_PROJECTS") or os.path.expanduser("~/.claude/projects")
    return os.path.join(root, clone.replace("/", "-"))


def fatal_in_tail(clone: str) -> tuple[str, str] | None:
    """(wording, meaning) if the newest transcript ends on a known fatal one."""
    d = transcript_dir(clone)
    files = [f for f in glob.glob(d + "/*.jsonl")]
    if not files:
        return None
    try:
        newest = max(files, key=os.path.getmtime)
        size = os.path.getsize(newest)
        with open(newest, errors="replace") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES)
                fh.readline()          # discard a partial line
            tail = fh.read()
    except OSError:
        return None
    for needle, meaning in FATAL:
        if needle in tail:
            return needle, meaning
    return None


def classify(clone: str, stall_s: float) -> dict:
    age = newest_event_age(clone)
    fatal = fatal_in_tail(clone)
    if fatal:
        state, why = "dead", fatal[1]
    elif age is None:
        state, why = "idle", "no telemetry events yet"
    elif age > stall_s:
        state, why = "stalled", f"no telemetry for {int(age // 60)}m and nothing in the transcript says why"
    else:
        state, why = "running", f"last event {int(age)}s ago"
    return {
        "clone": os.path.basename(clone),
        "state": state,
        "why": why,
        "last_event_s": None if age is None else int(age),
    }


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--root", default=os.path.expanduser("~/dev/cycles"))
    ap.add_argument("--stall-min", type=float, default=20.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    root = os.path.expanduser(a.root)
    if not os.path.isdir(root):
        print(f"cycle-health: no such directory: {root}", file=sys.stderr)
        return 2

    clones = sorted(
        p for p in glob.glob(os.path.join(root, "*"))
        if os.path.isdir(os.path.join(p, "agent_states"))
    )
    rows = [classify(c, a.stall_min * 60) for c in clones]

    if a.json:
        print(json.dumps({"root": root, "clones": rows}, indent=2))
    elif not rows:
        print(f"  no clones under {root}")
    else:
        for r in rows:
            print(f"  {r['state']:8s} {r['clone']:16s} {r['why']}")
        bad = [r for r in rows if r["state"] in ("stalled", "dead")]
        if bad:
            print()
            print(f"  {len(bad)} of {len(rows)} clone(s) are not working.")
            print("  A dead clone does not resume on its own — reap and requeue it.")

    return 1 if any(r["state"] in ("stalled", "dead") for r in rows) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                       # never crash a health check
        print(f"cycle-health: {exc}", file=sys.stderr)
        sys.exit(2)
