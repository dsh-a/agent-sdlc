#!/usr/bin/env python3
"""aggregate-telemetry.py — build the run report's Agent Telemetry table from event logs.

Phase 4A step 5 asked the orchestrator to read every file in `agent_states/events/`
and compute the table in-context. That is arithmetic over data whose bulk is never
needed: measured on a 58-file directory, 379,391 bytes of JSONL reduce to a 3,073
byte table — 123x. One deployment reached 966 event files, where the raw read would
exceed a context window outright, which is the likely reason run reports in that
vault say "Telemetry not collected."

Most of the saving is simply not reading `command`, which dominates each line and
appears nowhere in the output.

Stdlib only. Harness-agnostic. Reads only — this script never deletes or mutates
anything, and must not grow a cleanup mode; that is clear-agent-states.py's job.

    aggregate-telemetry.py                  # markdown table rows, for the report
    aggregate-telemetry.py --format json    # same data, structured
    aggregate-telemetry.py --events DIR     # explicit directory (default: <git-root>/agent_states/events)

Exit codes: 0 always, including "nothing to report". A telemetry step must never
fail the cycle it is describing.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import pathlib
import subprocess
import sys

# The template's own wording, so a caller can paste this straight in.
NO_DATA = "Telemetry not collected — enable hooks per README."

HEADER = (
    "| Agent ID | Type | Tool calls | Breakdown | Errors | Wallclock | Stop reason |\n"
    "|---|---|---|---|---|---|---|"
)

# Tools listed individually in the breakdown before the rest are summed as "other".
BREAKDOWN_WIDTH = 5


def events_dir(explicit: str | None) -> pathlib.Path:
    """agent_states/events/ at the root of the git repo we are run inside.

    Derived from the git root rather than __file__, for the same reason
    clear-agent-states.py is: skills are commonly symlinked into ~/.claude/skills
    from a central framework checkout, so __file__ resolves to the framework repo
    rather than the project being reported on.
    """
    if explicit:
        return pathlib.Path(explicit).expanduser()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return pathlib.Path(out.stdout.strip()).resolve() / "agent_states" / "events"
    except (OSError, subprocess.SubprocessError):
        pass
    return pathlib.Path("agent_states/events")


def parse(d: pathlib.Path) -> tuple[dict, int, int, dict]:
    """Return (per-agent rows, files read, malformed lines skipped)."""
    agents: dict[str, dict] = {}
    sessions: dict[str, dict] = {}
    files = skipped = 0
    for f in sorted(d.glob("*.jsonl")):
        files += 1
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except (ValueError, TypeError):
                skipped += 1
                continue
            if not isinstance(e, dict):
                skipped += 1
                continue
            aid = str(e.get("agent_id") or "unknown")
            a = agents.setdefault(aid, {
                "agent_type": e.get("agent_type") or "—",
                "typed": False,
                "calls": 0, "tools": collections.Counter(),
                "errors": 0, "first": None, "last": None, "stop": "—",
                "ts": [], "sessions": set(),
            })
            if e.get("agent_type"):
                a["agent_type"] = e["agent_type"]
                a["typed"] = True
            sid = e.get("session_id")
            if sid:
                a["sessions"].add(sid)
                sess = sessions.setdefault(sid, {"events": 0, "first": None, "last": None,
                                                 "stops": 0, "calls": 0})
                sess["events"] += 1
                if e.get("event") == "subagent_stop":
                    sess["stops"] += 1
                else:
                    sess["calls"] += 1
                ts0 = e.get("ts")
                if isinstance(ts0, str) and ts0:
                    sess["first"] = ts0 if sess["first"] is None else min(sess["first"], ts0)
                    sess["last"] = ts0 if sess["last"] is None else max(sess["last"], ts0)
            ts = e.get("ts")
            if isinstance(ts, str) and ts:
                a["first"] = ts if a["first"] is None else min(a["first"], ts)
                a["last"] = ts if a["last"] is None else max(a["last"], ts)
                a["ts"].append(ts)
            if e.get("event") == "subagent_stop":
                a["stop"] = e.get("stop_reason") or e.get("reason") or "stop"
                continue
            a["calls"] += 1
            a["tools"][e.get("tool") or "—"] += 1
            if e.get("exit") == "error":
                a["errors"] += 1
    return agents, files, skipped, sessions


def duration(first: str | None, last: str | None) -> str:
    """Human-readable span between two ISO-8601 Z timestamps."""
    if not first or not last:
        return "—"
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        a = datetime.datetime.strptime(first, fmt)
        b = datetime.datetime.strptime(last, fmt)
    except ValueError:
        return "—"
    secs = int((b - a).total_seconds())
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m{secs % 60:02d}s"
    return f"{secs // 3600}h{(secs % 3600) // 60:02d}m"


def breakdown(counter: collections.Counter) -> str:
    top = counter.most_common(BREAKDOWN_WIDTH)
    parts = [f"{t}×{c}" for t, c in top]
    rest = sum(counter.values()) - sum(c for _, c in top)
    if rest:
        parts.append(f"other×{rest}")
    return ", ".join(parts) or "—"


# An agent row is "orchestrator" when the hook recorded no agent_id — the session
# itself, not a spawned agent. Its events run from session start to session end,
# which is not Phase 3 and is not work the Phase-3 totals should own.
ORCHESTRATOR_IDS = ("orchestrator", "main")


def largest_gap(stamps: list[str]) -> tuple[int, str, str]:
    """(seconds, before, after) of the widest gap between consecutive events."""
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    best = (0, "", "")
    try:
        parsed = sorted(datetime.datetime.strptime(t, fmt) for t in stamps)
    except (ValueError, TypeError):
        # Narrow on purpose. A bare `except Exception` here swallowed a NameError
        # while this was being written and turned the whole check into a silent
        # no-op that still returned a plausible (0, "", "") — the same fail-open
        # shape as the parity regex in tests/. Only a bad timestamp is expected.
        return best
    for x, y in zip(parsed, parsed[1:]):
        gap = int((y - x).total_seconds())
        if gap > best[0]:
            best = (gap, x.strftime(fmt), y.strftime(fmt))
    return best


def gap_warning(aid: str, a: dict) -> str | None:
    """Flag a row whose wallclock is one long gap rather than sustained work.

    Deliberately a *warning*, not a correction. The obvious fix — subtract gaps
    over some threshold and call the remainder "active time" — cannot work here:
    a full-suite run is a single tool call that legitimately spans 1099s under
    fan-out contention, so any threshold low enough to catch an orphan is low
    enough to delete real work. Stating the gap lets the reader decide, which is
    the same choice the gate log makes about unclassified intervals.

    Measured in fan-out 4: `test-2.1` reported 4h22m of wallclock for 33 tool
    calls because a background `find /` it launched sat open until the system
    killed it, and the kill produced the agent's last event hours after its last
    real work. The table read as an agent that worked for four hours.
    """
    span_s = 0
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    try:
        span_s = int((datetime.datetime.strptime(a["last"], fmt)
                      - datetime.datetime.strptime(a["first"], fmt)).total_seconds())
    except Exception:
        return None
    if span_s < 600:
        return None
    gap, _, after = largest_gap(a["ts"])
    if gap * 2 <= span_s:
        return None
    pct = round(100 * gap / span_s)
    return (f"**`{aid}` wallclock is mostly one gap.** {human(gap)} of its "
            f"{human(span_s)} span ({pct}%) passed between two consecutive events, "
            f"ending {after}. Its {a['calls']} tool calls are real; the wallclock is "
            f"not a measure of work.")


def human(seconds: int) -> str:
    h, rem = divmod(max(0, seconds), 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m{sec:02d}s" if m else f"{sec}s"


def session_warning(sessions: dict) -> str | None:
    """Flag an events directory holding more than one session.

    One cycle is one session. More than one means this directory is not a record
    of one cycle, and every figure derived from it — agent counts, Phase-3
    wallclock, the tool-call totals — describes some mixture.

    Not hypothetical, and the reason this exists: partitioning a fan-out 4 clone's
    archive this way found 388 events from its own cycle and 83 from a session
    that had **ended 33 minutes before that cycle began**. The same directory also
    produced "55 agent(s) logged a stop with no tool calls" against a cycle that
    spawned 10 agents (evidence-run5 J11). Those tool-less stops are the foreign
    session's, and nothing in the output said so.

    Reported, never filtered. Dropping the smaller session would silently change
    the numbers a reader is comparing against earlier runs; saying the directory
    is mixed lets them decide what the figure is worth.
    """
    if len(sessions) < 2:
        return None
    rows = sorted(sessions.items(), key=lambda kv: -kv[1]["events"])
    parts = []
    for sid, v in rows:
        span = f"{(v['first'] or '?')[11:19]}–{(v['last'] or '?')[11:19]}"
        parts.append(f"`{sid[:8]}` {v['events']} events ({v['calls']} calls, "
                     f"{v['stops']} stops) {span}")
    return ("**Events span " + str(len(sessions)) + " sessions.** This directory is not a record of "
            "one cycle, so the agent counts and wallclocks below describe a mixture:\n"
            + "\n".join("  - " + p for p in parts)
            + "\n\n  A cycle is one session, and a fan-out clone is reused between rounds, so an "
              "archive directory accumulates them: quote the largest session's figures, or none. "
              "This is not the cause of the zero-call agents that puzzled earlier runs — that was "
              "untyped stops, reported separately below, and they were in the cycle's own "
              "session.")


def id_warning(agents: dict) -> str | None:
    """Flag the known agent-id collapse rather than emitting a table that looks complete.

    Counters and event files are keyed by the *harness* agent id, while the pipeline's
    convention is `<role>-<task-number>`. Under Claude Code the Agent() call has no `id`
    field, so the hook falls back and many agents aggregate under one id. This script
    cannot fix that; reporting a tidy table over collapsed ids would be worse than
    saying so.
    """
    if not agents:
        return None
    generic = {"orchestrator", "unknown", "main"}
    hits = [a for a in agents if a in generic]
    # Full collapse means *every* id is generic. The previous test was
    # `len(agents) <= 2`, which called it full collapse whenever an orchestrator
    # row sat beside a single spawned agent — a normal small cycle — and told the
    # reader "every event resolved to orchestrator" while a named agent was
    # tabulated two lines below.
    if hits and len(hits) == len(agents):
        return (f"**Agent-id collapse:** every event resolved to {', '.join(sorted(hits))}. "
                "Per-agent rows below are not per-agent — the hook could not attribute calls "
                "to individual agents (spawn ids are not set on this harness). Totals are "
                "still valid.")
    if hits:
        return (f"**Partial agent-id collapse:** some events aggregated under "
                f"{', '.join(sorted(hits))} rather than a `<role>-<task>` id. "
                "`orchestrator` is ambiguous by construction — the hook writes it both for "
                "the session itself and for any spawned agent whose id the harness did not "
                "set — so calls that belong to an agent may be sitting in that row, and the "
                "Phase-3 totals exclude them either way. Read its tool breakdown before "
                "trusting the totals: orchestration is Read/Bash/Edit on cycle artifacts, "
                "and anything else there is probably an agent's work.")
    return None


def span_warning(first: str | None, last: str | None) -> str | None:
    """Flag an events directory that plainly spans more than one cycle.

    Same class of risk as id_warning: a stale directory yields a total that looks
    like a cycle's wallclock and is not one. Stating the span is factual — deciding
    whether it is acceptable is the orchestrator's call, not this script's.
    """
    if not first or not last:
        return None
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        hours = (datetime.datetime.strptime(last, fmt)
                 - datetime.datetime.strptime(first, fmt)).total_seconds() / 3600
    except ValueError:
        return None
    if hours > 24:
        return (f"**Events span {hours:.0f}h ({first[:10]} → {last[:10]}).** That is longer than a "
                "cycle, so this directory holds more than one run — totals and wallclocks below "
                "cover all of them. Clear it between cycles (clear-agent-states.py) for per-cycle "
                "figures.")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--format", choices=("markdown", "json"), default="markdown")
    ap.add_argument("--events", help="events directory (default: <git-root>/agent_states/events)")
    args = ap.parse_args()

    d = events_dir(args.events)
    if not d.is_dir():
        print(NO_DATA if args.format == "markdown"
              else json.dumps({"status": "no-data", "reason": f"{d} does not exist"}, indent=2))
        return 0

    agents, files, skipped, sessions = parse(d)
    if not agents:
        print(NO_DATA if args.format == "markdown"
              else json.dumps({"status": "no-data", "reason": f"no parsable events in {d}",
                               "files_read": files, "malformed_lines": skipped}, indent=2))
        return 0

    # An agent that logged a stop but no tool call produces a row of zeroes. That
    # bucket turned out to hold two unrelated things, and pooling them is what kept
    # J11 open for three rounds.
    #
    # Measured across six sessions and four days of fan-out archives: 257 stop
    # events, 36 of them from agents with a real transcript and 221 from ids that
    # appear in no transcript anywhere. The split is total and it is visible in the
    # payload — every one of the 36 carried an `agent_type`, and every one of the
    # 221 carried none. The untyped ones arrive at a steady ~1 per minute in every
    # clone (0.96–1.18/min across four), independent of how many agents were
    # spawned or how many tools ran, which is the signature of something the
    # harness does on a clock rather than anything this pipeline asked for.
    #
    # So they are counted apart. A stop with no type is not a silent agent; a stop
    # *with* a type and no tool calls is, and that one is worth looking at.
    untyped = [aid for aid, a in agents.items() if not a["calls"] and not a["typed"]]
    silent = [aid for aid, a in agents.items() if not a["calls"] and a["typed"]]
    ordered = sorted(((aid, a) for aid, a in agents.items() if a["calls"]),
                     key=lambda kv: (-kv[1]["calls"], kv[0]))
    # Phase-3 totals cover spawned agents. The orchestrator row is the session
    # itself: its first event is session start and its last is session end, so
    # folding it in reports the whole cycle — Phases 1 through 4 — as Phase-3
    # wallclock. Measured in fan-out 4: 9h23m presented as Phase-3 work.
    #
    # Unless it is all there is. When agent ids have collapsed, every event lands
    # under "orchestrator" and excluding it would report a cycle that did nothing.
    # In that case keep it, and let id_warning say why the table is untrustworthy —
    # an honest warning over a real number beats a clean number over an empty one.
    orchestrator_rows = [aid for aid, _ in ordered if aid.lower() in ORCHESTRATOR_IDS]
    phase3 = [(aid, a) for aid, a in ordered if aid.lower() not in ORCHESTRATOR_IDS]
    collapsed_to_orchestrator = not phase3
    if collapsed_to_orchestrator:
        phase3, excluded = ordered, []
    else:
        excluded = orchestrator_rows

    total_calls = sum(a["calls"] for _, a in phase3)
    total_errors = sum(a["errors"] for _, a in phase3)
    firsts = [a["first"] for _, a in phase3 if a["first"]]
    lasts = [a["last"] for _, a in phase3 if a["last"]]
    span = duration(min(firsts), max(lasts)) if firsts and lasts else "—"

    if args.format == "json":
        print(json.dumps({
            "status": "ok",
            "events_dir": str(d), "files_read": files, "malformed_lines": skipped,
            "agents": [{
                "agent_id": aid, "agent_type": a["agent_type"], "tool_calls": a["calls"],
                "breakdown": dict(a["tools"]), "errors": a["errors"],
                "first_ts": a["first"], "last_ts": a["last"],
                "wallclock": duration(a["first"], a["last"]), "stop_reason": a["stop"],
            } for aid, a in ordered],
            "totals": {"tool_calls": total_calls, "errors": total_errors, "wallclock": span,
                       "agents": len(phase3), "silent_agents": len(silent),
                       "untyped_stops": len(untyped),
                       "excludes": excluded,
                       "note": "spawned agents only; the orchestrator row is session "
                               "lifetime, not Phase-3 work"},
            "gap_warnings": [w for w in (gap_warning(aid, a) for aid, a in ordered) if w],
            "silent_agents": sorted(silent),
            "untyped_stops": sorted(untyped),
            "sessions": {sid: v for sid, v in sessions.items()},
            "session_warning": session_warning(sessions),
            "id_warning": id_warning(agents),
            "span_warning": span_warning(min(firsts) if firsts else None,
                                         max(lasts) if lasts else None),
        }, indent=2))
        return 0

    warnings = [session_warning(sessions),
                span_warning(min(firsts) if firsts else None,
                             max(lasts) if lasts else None), id_warning(agents)]
    warnings += [gap_warning(aid, a) for aid, a in ordered]
    for warn in warnings:
        if warn:
            print(warn + "\n")
    print(HEADER)
    for aid, a in ordered:
        print(f"| `{aid}` | {a['agent_type']} | {a['calls']} | {breakdown(a['tools'])} "
              f"| {a['errors']} | {duration(a['first'], a['last'])} | {a['stop']} |")
    print()
    print("### Phase-3 totals")
    print("| Metric | Value |")
    print("|---|---|")
    print(f"| Total tool calls | {total_calls} |")
    print(f"| Total errors | {total_errors} |")
    print(f"| Phase-3 wallclock (first→last event) | {span} |")
    if excluded:
        print(f"\n*Totals cover spawned agents only. `{'`, `'.join(excluded)}` is the "
              f"session itself — its span is the whole cycle, not Phase 3 — so it is "
              f"listed above but not counted here.*")
    if collapsed_to_orchestrator:
        print("\n*Every agent resolved to the orchestrator, so the totals above are the "
              "session, not Phase 3. See the agent-id warning.*")
    if silent:
        # Attribute them by session when there is more than one. "55 agents logged
        # a stop with no tool calls" against a cycle that spawned 10 is only a
        # mystery while the sessions are pooled.
        by_sess: dict[str, int] = {}
        for aid in silent:
            for sid in (agents[aid].get("sessions") or {"?"}):
                by_sess[sid] = by_sess.get(sid, 0) + 1
        note = ""
        if len(sessions) > 1 and by_sess:
            note = " — by session: " + ", ".join(
                f"`{sid[:8]}` {n}" for sid, n in sorted(by_sess.items(), key=lambda kv: -kv[1]))
        print(f"\n*{len(silent)} spawned agent(s) logged a stop with no tool calls and are "
              f"not tabulated above{note}. A typed agent that ran nothing is worth a look.*")
    if untyped:
        print(f"\n*{len(untyped)} untyped stop event(s) recorded and excluded. These carry no "
              f"`agent_type` and match no subagent transcript; they arrive at roughly one per "
              f"minute regardless of what the cycle is doing, so they are the harness's own "
              f"background, not this cycle's agents. Not a defect — do not report them as "
              f"spawned agents.*")
    if skipped:
        print(f"\n*{skipped} malformed line(s) skipped across {files} file(s).*")
    return 0


if __name__ == "__main__":
    sys.exit(main())
