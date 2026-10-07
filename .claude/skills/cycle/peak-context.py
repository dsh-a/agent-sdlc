#!/usr/bin/env python3
"""peak-context.py — the largest prompt each agent actually held.

`docs/internal/agent-requirement-profiles.md` (Artifact B) profiles every agent
with the context it needs, and had to estimate the field that decides the answer.
Static load is measurable from the framework — body plus autoloaded skills — but
what a long Phase-3 agent actually holds at its peak, across thirty tool calls, is
not in the framework at all. That document says so plainly: "treat every
context_floor above as a lower bound".

This fills it, and needs no new instrumentation. Every assistant message in a
transcript carries `message.usage`, and the prompt the model saw for that request
is the sum of three of its fields:

    input_tokens + cache_read_input_tokens + cache_creation_input_tokens

Cache split is a billing distinction, not a context one — a cached token still
occupies the window. So the peak over a session's messages is the largest context
that agent ever held, and transcripts outlive the clones they came from, which
means this is recoverable from runs that finished weeks ago.

Attribution is exact rather than heuristic here. Claude Code writes a sibling
`<transcript>.meta.json` for every subagent carrying `agentType`, `model` and
`spawnDepth`; `attributionAgent` on the message is the fallback.

Top-level transcripts need more care than that, and the first version of this got
it wrong. "A transcript at the project root is the orchestrator" over-included
every ad-hoc session held in a project directory — which put a 977,036-token
session running `artifact-design` and `example-skill` into the orchestrator
row and inflated its p90 by 35%. Records carry `attributionSkill`, so the
dominant skill in a top-level transcript names it precisely: `/cycle` sessions
become `orchestrator (/cycle)`, other skill-dominated sessions are labelled by
skill, and the rest are `session (ad-hoc)` and stay out of the fleet numbers.

Two things that would corrupt the measurement, and how each is handled:

  - **Duplicate usage blocks.** One transcript entry per content block means a
    single assistant message with thinking + text + two tool calls appears four
    times carrying the same usage. `cache-usage.py` documents a ~1.8x inflation
    from summing those. A maximum is immune to duplication, but the percentiles
    and message counts are not, so ids are deduplicated anyway.
  - **Compaction.** If a session compacts, the peak observed is a floor on real
    demand rather than the demand itself. The run reports whether any compaction
    markers were seen so the caveat is stated by the data, not assumed.

Stdlib only, reads only, never mutates a transcript.

    peak-context.py                        every project under ~/.claude/projects
    peak-context.py --match cycles-myapp  only projects whose slug contains this
    peak-context.py --agent test           one agent's sessions, listed
    peak-context.py --json                 machine-readable
    peak-context.py <dir> [<dir> ...]      named transcript roots
    peak-context.py --snapshot             append a dated reading to the history

`~/.claude/projects` rotates and sessions are eventually swept, so a reading taken
today is not reproducible tomorrow. `--snapshot` appends the per-agent summary —
not the per-session rows, which are large and personal — to
`docs/internal/data/peak-context-history.jsonl`, stamped with the date, the
corpus size and the framework commit. Each line is one reading; the file is the
series. Run it deliberately, the way `context_budget.py --update` is run: the
diff is the artifact.

Exit code is 0 whether or not anything was found. This describes runs; it must
never fail one.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

DEFAULT_ROOT = os.path.expanduser("~/.claude/projects")
HISTORY = (os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "..", "docs", "internal", "data",
                        "peak-context-history.jsonl"))

# Rows that are not fleet agents: ad-hoc sessions, generic helpers, and the
# harness's own built-ins. Kept out of the history so the series stays comparable
# as those come and go.
NON_FLEET = {"session (ad-hoc)", "fork", "Explore", "general-purpose", "Plan",
             "claude", "unknown"}


def transcripts(root):
    """Every .jsonl under root, at any depth. Subagent transcripts live in a
    per-session `subagents/` directory and matter as much as the top-level one."""
    if os.path.isfile(root):
        yield root
        return
    for dirpath, _dirs, files in os.walk(root):
        for f in sorted(files):
            if f.endswith(".jsonl"):
                yield os.path.join(dirpath, f)


# A top-level transcript is labelled by the skill that dominates it. The bar is
# low on purpose: a cycle run attributes hundreds of records to `cycle`, while a
# session that merely invoked a skill once attributes one or two.
SKILL_DOMINANCE = 10


def attribution(path, project_root):
    """(agent_type, model). Exact where the harness recorded it.

    The sidecar is authoritative — written at spawn with the agent type the
    orchestrator asked for. Absent that, the message-level `attributionAgent`.
    Top-level transcripts are resolved by dominant skill; see the module
    docstring on why position alone is not good enough.
    """
    meta = path[:-len(".jsonl")] + ".meta.json"
    if os.path.exists(meta):
        try:
            d = json.load(open(meta, encoding="utf-8"))
            if d.get("agentType"):
                return d["agentType"], d.get("model")
        except (OSError, ValueError):
            pass
    return None, None


def top_level_label(skill_counts):
    """orchestrator (/cycle) | skill:<name> | session (ad-hoc)."""
    if not skill_counts:
        return "session (ad-hoc)"
    skill, n = max(skill_counts.items(), key=lambda kv: kv[1])
    if n < SKILL_DOMINANCE:
        return "session (ad-hoc)"
    return "orchestrator (/cycle)" if skill == "cycle" else f"skill:{skill}"


def scan_transcript(path, project_root):
    """One transcript -> its peak prompt, message count, agent type and model."""
    agent, model = attribution(path, project_root)
    is_top_level = (os.path.realpath(os.path.dirname(path))
                    == os.path.realpath(project_root))
    skill_counts = {}
    seen = set()
    peak = 0
    sizes = []
    compacted = False

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue

            if rec.get("type") in ("compact", "summary") or rec.get("isCompactSummary"):
                compacted = True
            skill = rec.get("attributionSkill")
            if skill:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            if msg.get("context_management"):
                compacted = True
            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue

            mid = msg.get("id")
            if mid:
                if mid in seen:
                    continue
                seen.add(mid)

            if agent is None and rec.get("attributionAgent"):
                agent = rec["attributionAgent"]
            if model is None and msg.get("model"):
                model = msg["model"]

            size = ((usage.get("input_tokens") or 0)
                    + (usage.get("cache_read_input_tokens") or 0)
                    + (usage.get("cache_creation_input_tokens") or 0))
            sizes.append(size)
            peak = max(peak, size)

    if agent is None and is_top_level:
        agent = top_level_label(skill_counts)

    return {
        "path": path,
        "agent": agent or "unknown",
        "model": model,
        "peak": peak,
        "messages": len(sizes),
        "compacted": compacted,
    }


def percentile(values, q):
    """Nearest-rank: rank = ceil(q * n), value = ordered[rank - 1].

    Deliberately not interpolated. With eight pre-digest sessions in the corpus,
    an interpolated p90 would imply a precision the sample does not have.
    """
    if not values:
        return 0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def collect(roots):
    sessions = []
    for root in roots:
        if os.path.isfile(root):
            sessions.append(scan_transcript(root, os.path.dirname(root)))
            continue
        for path in transcripts(root):
            rec = scan_transcript(path, root)
            if rec["peak"]:
                sessions.append(rec)
    return sessions


def summarize(sessions):
    by_agent = {}
    for s in sessions:
        by_agent.setdefault(s["agent"], []).append(s)
    out = []
    for agent, rows in by_agent.items():
        peaks = [r["peak"] for r in rows]
        out.append({
            "agent": agent,
            "sessions": len(rows),
            "median": percentile(peaks, 0.50),
            "p90": percentile(peaks, 0.90),
            "max": max(peaks),
            "compacted_sessions": sum(1 for r in rows if r["compacted"]),
            "models": sorted({r["model"] for r in rows if r["model"]}),
        })
    return sorted(out, key=lambda r: -r["max"])


def render(rows, sessions):
    if not rows:
        return "No transcripts with usage data found."
    lines = ["| Agent | Sessions | Median peak | p90 | Max |", "|---|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['agent']} | {r['sessions']} | {r['median']:,} "
                     f"| {r['p90']:,} | **{r['max']:,}** |")
    total = len(sessions)
    compacted = sum(1 for s in sessions if s["compacted"])
    lines += ["", f"{total} transcripts with usage data."]
    if compacted:
        lines.append(f"**{compacted} compacted** — their peaks are a floor on real demand, "
                     "not the demand itself.")
    else:
        lines.append("No compaction markers seen, so these peaks are demand actually "
                     "reached rather than demand clipped.")
    lines.append("Peak = input + cache_read + cache_creation. A cached token still "
                 "occupies the window.")
    return "\n".join(lines)


def framework_commit():
    """Short SHA, so a reading can be tied to the framework that produced it."""
    try:
        import subprocess
        here = os.path.dirname(os.path.abspath(__file__))
        r = subprocess.run(["git", "-C", here, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001 — a missing git must not fail a measurement
        return None


def snapshot(rows, sessions, path=HISTORY):
    """Append one dated reading. Fleet agents only; summary only, never sessions."""
    import datetime
    fleet = [r for r in rows if r["agent"] not in NON_FLEET]
    record = {
        "date": datetime.date.today().isoformat(),
        "commit": framework_commit(),
        "transcripts": len(sessions),
        "compacted": sum(1 for s in sessions if s["compacted"]),
        "agents": {r["agent"]: {"sessions": r["sessions"], "median": r["median"],
                                "p90": r["p90"], "max": r["max"]} for r in fleet},
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("roots", nargs="*", help=f"transcript roots (default: {DEFAULT_ROOT})")
    ap.add_argument("--match", help="only projects whose path contains this substring")
    ap.add_argument("--agent", help="list individual sessions for one agent type")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--snapshot", action="store_true",
                    help="append a dated reading to docs/internal/data/peak-context-history.jsonl")
    args = ap.parse_args(argv)

    roots = args.roots or ([os.path.join(DEFAULT_ROOT, d)
                            for d in sorted(os.listdir(DEFAULT_ROOT))]
                           if os.path.isdir(DEFAULT_ROOT) else [])
    if args.match:
        roots = [r for r in roots if args.match in r]
    if not roots:
        print("No transcript roots found.")
        return 0

    sessions = collect(roots)

    if args.agent:
        rows = sorted((s for s in sessions if s["agent"] == args.agent),
                      key=lambda s: -s["peak"])
        if args.json:
            print(json.dumps(rows, indent=2))
            return 0
        if not rows:
            print(f"No sessions for agent '{args.agent}'.")
            return 0
        for s in rows:
            print(f"{s['peak']:>9,}  {s['messages']:>5} msgs  {os.path.basename(s['path'])}")
        return 0

    rows = summarize(sessions)

    if args.snapshot:
        rec = snapshot(rows, sessions)
        print(f"recorded {rec['date']} @ {rec['commit']} — "
              f"{rec['transcripts']:,} transcripts, {len(rec['agents'])} fleet agents")
        return 0

    if args.json:
        print(json.dumps({"agents": rows, "transcripts": len(sessions)}, indent=2))
    else:
        print(render(rows, sessions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
