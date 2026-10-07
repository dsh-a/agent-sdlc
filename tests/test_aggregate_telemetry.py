"""Regression tests for .claude/skills/cycle/aggregate-telemetry.py.

The script replaces in-context aggregation at Phase 4A step 5, so the properties
worth pinning are the ones that would otherwise fail silently: a missing directory
must say "not collected" rather than emit an empty-looking table, malformed lines
must be counted rather than dropped, and the two warnings must fire — a tidy table
over collapsed agent ids, or over events spanning several cycles, is worse than no
table at all.

Stdlib only, and runnable without pytest:

    python3 tests/test_aggregate_telemetry.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/cycle/aggregate-telemetry.py"

FAILURES: list[str] = []


def run(events: pathlib.Path, *extra: str) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--events", str(events), *extra],
        capture_output=True, text=True, timeout=30,
    )
    return p.returncode, p.stdout


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def write(d: pathlib.Path, name: str, lines: list[str]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("\n".join(lines) + "\n")


def ev(ts: str, aid: str, tool: str = "Read", exit_: str = "ok", atype: str = "test",
       session: str = "sess-aaaaaaaa") -> str:
    return json.dumps({"ts": ts, "agent_id": aid, "agent_type": atype, "session_id": session,
                       "event": "tool", "tool": tool, "exit": exit_,
                       "command": "x" * 200})  # command is bulk and must be ignored


def stop(ts: str, aid: str, session: str = "sess-aaaaaaaa", atype: str = "") -> str:
    """A subagent_stop with no tool calls — the shape behind J11.

    `atype` is the whole diagnosis. A stop carrying a type came from an agent this
    pipeline spawned and is worth a look; a stop carrying none is the harness's own
    background, and pooling the two is what left J11 open for three rounds."""
    return json.dumps({"ts": ts, "agent_id": aid, "agent_type": atype, "session_id": session,
                       "event": "subagent_stop", "stop_reason": None})


def main() -> int:
    print("aggregate-telemetry")
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)

        # A telemetry step must never fail the cycle it describes.
        code, out = run(t / "does-not-exist")
        check("missing dir → exit 0 + 'not collected'",
              code == 0 and "Telemetry not collected" in out, out[:80])

        empty = t / "empty"; empty.mkdir()
        code, out = run(empty)
        check("empty dir → 'not collected', not an empty table",
              code == 0 and "Telemetry not collected" in out and "| Agent ID |" not in out)

        # Counting, error tallying, stop reason, and malformed-line accounting.
        good = t / "good"
        write(good, "test-1.0.jsonl", [
            ev("2026-09-06T10:00:00Z", "test-1.0"),
            "{ not json",
            ev("2026-09-06T10:00:30Z", "test-1.0", tool="Bash", exit_="error"),
            json.dumps({"ts": "2026-09-06T10:01:00Z", "agent_id": "test-1.0",
                        "event": "subagent_stop", "stop_reason": "end_turn"}),
        ])
        code, out = run(good)
        check("counts tool calls, excludes subagent_stop", "| 2 |" in out, out)
        check("tallies errors", "| 1 |" in out)
        check("reports stop reason", "end_turn" in out)
        check("malformed line counted, not dropped", "1 malformed line" in out, out)
        check("wallclock computed", "1m00s" in out)

        # A stop-only event must not be counted as a tool call.
        code, out = run(good, "--format", "json")
        data = json.loads(out)
        check("json: one agent, 2 calls", len(data["agents"]) == 1
              and data["agents"][0]["tool_calls"] == 2, out[:120])
        check("json: totals present", data["totals"]["tool_calls"] == 2
              and data["totals"]["errors"] == 1)
        check("json: malformed surfaced", data["malformed_lines"] == 1)

        # The two warnings that stop a wrong-but-tidy table going into a report.
        collapsed = t / "collapsed"
        write(collapsed, "orchestrator.jsonl",
              [ev("2026-09-06T10:00:00Z", "orchestrator", atype="orchestrator")])
        code, out = run(collapsed)
        check("agent-id collapse warned", "Agent-id collapse" in out, out[:120])

        stale = t / "stale"
        write(stale, "a.jsonl", [ev("2026-09-01T10:00:00Z", "coding-1.0"),
                                 ev("2026-09-06T10:00:00Z", "coding-1.0")])
        code, out = run(stale)
        check("multi-cycle span warned", "Events span" in out, out[:120])

        # No warning when the data is clean — the warnings must be signal, not noise.
        clean = t / "clean"
        write(clean, "a.jsonl", [ev("2026-09-06T10:00:00Z", "coding-1.0"),
                                 ev("2026-09-06T10:05:00Z", "coding-1.0")])
        code, out = run(clean)
        check("clean data → no warnings",
              "Events span" not in out and "collapse" not in out, out[:120])

    with tempfile.TemporaryDirectory() as tmp:
        # A SubagentStop with no PostToolUse yields an all-zero row. One real run
        # tabulated 51 agents of which 11 had done anything, and the 40 empties were
        # misread as events leaking from other clones.
        d = pathlib.Path(tmp) / "events"
        d.mkdir()
        (d / "real-1.0.jsonl").write_text(
            '{"ts":"2026-09-08T01:00:00Z","agent_id":"real-1.0","agent_type":"coding",'
            '"event":"tool","tool":"Read","exit":"ok"}\n')
        for n in range(4):
            (d / f"silent-{n}.jsonl").write_text(
                f'{{"ts":"2026-09-08T01:00:0{n}Z","agent_id":"silent-{n}",'
                f'"agent_type":"test","event":"subagent_stop","stop_reason":"stop"}}\n')
        _, out = run(d)
        check("silent agents are not tabulated", out.count("| `silent-") == 0, out)
        check("  ... but they are counted",
              "4 spawned agent(s) logged a stop with no tool calls" in out, out)
        check("  ... and the real agent still appears", "| `real-1.0` |" in out, out)

        data = json.loads(run(d, "--format", "json")[1])
        check("  ... json separates them",
              data["totals"]["agents"] == 1 and data["totals"]["silent_agents"] == 4,
              json.dumps(data["totals"]))
        check("  ... and names them for anyone who needs them",
              len(data["silent_agents"]) == 4, str(data.get("silent_agents")))

    # --- H7: the orchestrator row is session lifetime, not Phase-3 work -------
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp) / "events"
        # Orchestrator spans the whole session; one spawned agent works 2 minutes.
        write(t, "orchestrator.jsonl", [
            ev("2026-09-10T00:00:00Z", "orchestrator", atype="orchestrator"),
            ev("2026-09-10T09:23:00Z", "orchestrator", atype="orchestrator"),
        ])
        write(t, "test-2.0.jsonl", [
            ev("2026-09-10T04:00:00Z", "test-2.0"),
            ev("2026-09-10T04:02:00Z", "test-2.0"),
        ])
        code, out = run(t)
        check("orchestrator is excluded from Phase-3 wallclock",
              "| Phase-3 wallclock (first→last event) | 2m00s |" in out
              and "| Phase-3 wallclock (first→last event) | 9h23m |" not in out, out)
        check("  ... and a normal cycle is not called a full id collapse",
              "every event resolved to" not in out, out)
        check("  ... but still appears in the agent table", "`orchestrator`" in out, out)
        check("  ... and the exclusion is stated, not silent",
              "not counted here" in out, out)
        check("  ... totals count only spawned agents' calls",
              "| Total tool calls | 2 |" in out, out)
        code, js = run(t, "--format", "json")
        d = json.loads(js)
        check("  ... json names what it excluded",
              d["totals"]["excludes"] == ["orchestrator"], js[:400])

    # Excluding it must never produce a report of a cycle that did nothing.
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp) / "events"
        write(t, "orchestrator.jsonl", [
            ev("2026-09-10T00:00:00Z", "orchestrator", atype="orchestrator"),
            ev("2026-09-10T00:05:00Z", "orchestrator", atype="orchestrator"),
        ])
        code, out = run(t)
        check("all-orchestrator data is kept, not zeroed",
              "| Total tool calls | 2 |" in out, out)
        check("  ... and says the totals are the session, not Phase 3",
              "not Phase 3" in out, out)

    # --- H7: a wallclock that is really one long gap --------------------------
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp) / "events"
        # 33 calls of real work, then a background process killed hours later.
        lines = [ev(f"2026-09-10T04:{m:02d}:00Z", "test-2.1") for m in range(0, 30, 1)]
        lines.append(ev("2026-09-10T08:21:00Z", "test-2.1"))
        write(t, "test-2.1.jsonl", lines)
        code, out = run(t)
        check("a wallclock dominated by one gap is flagged",
              "mostly one gap" in out, out)
        check("  ... naming the gap and the span",
              "3h52m" in out and "4h21m" in out, out)
        check("  ... and saying the tool calls are still real",
              "tool calls are real" in out, out)

    # Sustained work must not be flagged, however long it runs. A full-suite run
    # is a single tool call that legitimately spans 1099s under fan-out
    # contention, which is why gaps are reported rather than subtracted.
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp) / "events"
        write(t, "test-3.0.jsonl", [
            ev("2026-09-10T04:00:00Z", "test-3.0"),
            ev("2026-09-10T04:20:00Z", "test-3.0"),   # one 1200s suite run
            ev("2026-09-10T04:40:00Z", "test-3.0"),   # and another
        ])
        code, out = run(t)
        check("evenly spaced long tool calls are not flagged",
              "mostly one gap" not in out, out)

    # --- J11: one events directory, more than one session --------------------
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp) / "events"
        write(t, "own.jsonl", [ev("2026-09-10T04:41:00Z", "test-1.0"),
                               ev("2026-09-10T04:43:00Z", "test-1.0")])
        # A session that ended before this cycle began — the measured shape.
        write(t, "foreign.jsonl", [ev("2026-09-10T00:47:00Z", "coding-9.9",
                                      session="sess-bbbbbbbb")])
        code, out = run(t)
        check("two sessions in one directory is warned", "span 2 sessions" in out, out)
        check("  ... naming each with its event count",
              "`sess-aaa` 2 events" in out and "`sess-bbb` 1 events" in out, out)
        check("  ... and saying the figures are a mixture", "describe a mixture" in out, out)
        # Reported, never filtered: dropping the smaller session would silently
        # change numbers a reader compares against earlier runs.
        check("  ... while still counting every event", "| Total tool calls | 3 |" in out, out)
        code, js = run(t, "--format", "json")
        d = json.loads(js)
        check("  ... and json carries the per-session breakdown",
              sorted(d["sessions"]) == ["sess-aaaaaaaa", "sess-bbbbbbbb"], js[:300])

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp) / "events"
        write(t, "one.jsonl", [ev("2026-09-10T04:41:00Z", "test-1.0")])
        code, out = run(t)
        check("a single-session directory is not warned about", "sessions" not in out, out)

    # Tool-less stops are attributed, which is what made "55 stops, 10 agents"
    # a mystery: the sessions were pooled.
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp) / "events"
        write(t, "real.jsonl", [ev("2026-09-10T04:41:00Z", "test-1.0")])
        write(t, "s1.jsonl", [stop("2026-09-10T04:42:00Z", "ghost-1", atype="verify")])
        write(t, "s2.jsonl", [stop("2026-09-10T00:50:00Z", "ghost-2",
                                   session="sess-bbbbbbbb", atype="review")])
        code, out = run(t)
        check("silent agents are attributed by session",
              "by session:" in out and "`sess-aaa` 1" in out and "`sess-bbb` 1" in out, out)

    # --- J11: a stop with no agent_type is not one of ours -------------------
    #
    # Measured across six fan-out sessions: 257 stop events, 36 typed and matching
    # a subagent transcript, 221 untyped and matching nothing anywhere. The untyped
    # ones arrive at ~1/min regardless of what the cycle is doing. Reporting them
    # as agents produced "84 agent(s) logged a stop with no tool calls" against a
    # cycle that spawned 11.
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp) / "events"
        write(t, "real.jsonl", [ev("2026-09-12T17:00:00Z", "coding-1.0", atype="coding")])
        write(t, "quiet.jsonl", [stop("2026-09-12T17:01:00Z", "test-1.0", atype="test")])
        write(t, "_untyped-stops.jsonl",
              [stop(f"2026-09-12T17:0{n}:00Z", f"a{n}00000000000000") for n in range(5)])
        code, out = run(t)
        check("untyped stops are not counted as silent agents",
              "1 spawned agent(s) logged a stop" in out, out)
        check("  ... they are reported on their own line",
              "5 untyped stop event(s) recorded and excluded" in out, out)
        check("  ... and named as harness background, not a defect",
              "harness's own background" in out and "Not a defect" in out, out)
        check("  ... and none of them is tabulated", out.count("| `a000") == 0, out)

        data = json.loads(run(t, "--format", "json")[1])
        check("  ... json counts them apart",
              data["totals"]["silent_agents"] == 1 and data["totals"]["untyped_stops"] == 5,
              json.dumps(data["totals"]))
        check("  ... and names them for anyone who wants to look",
              len(data["untyped_stops"]) == 5, str(data.get("untyped_stops")))
        check("  ... without leaking into the silent list",
              data["silent_agents"] == ["test-1.0"], str(data.get("silent_agents")))

    # A typed agent that ran nothing is the real signal, and must survive the
    # split — it is the one this filter could plausibly have swallowed.
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp) / "events"
        write(t, "v.jsonl", [stop("2026-09-12T17:00:00Z", "verify-1", atype="verify")])
        code, out = run(t)
        check("a typed agent with no tool calls is still surfaced",
              "1 spawned agent(s) logged a stop" in out, out)
        check("  ... and is called out as worth a look", "worth a look" in out, out)

    if FAILURES:
        print("\nFAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\naggregate-telemetry: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
