#!/usr/bin/env python3
"""log-event — Claude Code PostToolUse + SubagentStop hook.

Appends one JSONL line per event to ``<cycle-root>/agent_states/events/<agent_id>.jsonl``.

Resolving ``<cycle-root>`` is the whole subtlety, because two different kinds of
linked worktree want opposite answers:

* A **Phase-3 agent worktree** is a workspace *inside* one cycle. Its events belong
  to that cycle, so they must land in the main checkout — hence ``--git-common-dir``.
* A **fan-out clone** (``start-parallel-cycles.sh``) is a whole cycle of its own that
  happens to be implemented as a linked worktree of the origin. ``--git-common-dir``
  points at the origin, so under a parallel run every clone appended into one
  directory in the origin repo while each clone had no ``agent_states/events/`` at
  all — measured in fan-out 1, see docs/internal/parallel-cycles-evidence-run1.md E1.

Git topology cannot tell the two apart: both are linked worktrees. So the launcher
marks a fan-out clone with ``agent_states/.fanout-clone`` and that marker wins.

Pure logging — never fails the calling tool. Wired from ``.claude/settings.json``
as a ``PostToolUse`` and ``SubagentStop`` hook.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone


# Marker written by start-parallel-cycles.sh into each clone. Its presence means
# "this checkout is a cycle in its own right" — see the module docstring.
FANOUT_MARKER = os.path.join("agent_states", ".fanout-clone")


def _git(args, cwd):
    return subprocess.check_output(
        ["git"] + args, cwd=cwd, stderr=subprocess.DEVNULL, text=True
    ).strip()


def cycle_root(cwd):
    """The checkout whose agent_states/ this event belongs to, or None."""
    try:
        top = _git(["rev-parse", "--show-toplevel"], cwd)
    except Exception:
        return None
    # A fan-out clone owns its own telemetry even though it is a linked worktree.
    if top and os.path.exists(os.path.join(top, FANOUT_MARKER)):
        return top
    try:
        common = _git(["rev-parse", "--git-common-dir"], cwd)
    except Exception:
        return top or None
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)
    return os.path.dirname(os.path.abspath(common))


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return

    cwd = payload.get("cwd") or os.getcwd()
    cycle_dir = cycle_root(cwd)
    if cycle_dir is None:
        return

    events_dir = os.path.join(cycle_dir, "agent_states", "events")
    try:
        os.makedirs(events_dir, exist_ok=True)
    except Exception:
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    agent_id = payload.get("agent_id") or "orchestrator"
    event = payload.get("hook_event_name")

    line = None
    if event == "PostToolUse":
        r = payload.get("tool_response") or payload.get("tool_result") or {}
        is_err = isinstance(r, dict) and (
            r.get("is_error") or r.get("type") == "error"
        )
        inp = payload.get("tool_input") or {}
        line = {
            "ts": ts,
            "session_id": payload.get("session_id"),
            "agent_id": agent_id,
            "agent_type": payload.get("agent_type") or "orchestrator",
            "event": "tool",
            "tool": payload.get("tool_name"),
            "file": inp.get("file_path"),
            "command": inp.get("command"),
            "exit": "error" if is_err else "ok",
        }
    elif event == "SubagentStop":
        line = {
            "ts": ts,
            "session_id": payload.get("session_id"),
            "agent_id": payload.get("agent_id"),
            "agent_type": payload.get("agent_type"),
            "event": "subagent_stop",
            "stop_reason": payload.get("stop_reason"),
        }
        # A stop with no agent_type is not one of this pipeline's agents. Measured
        # across six fan-out sessions: 257 stops, of which 36 carried a type and
        # matched a subagent transcript, and 221 carried none and matched nothing
        # anywhere. The untyped ones arrive at a steady ~1/min in every clone,
        # independent of spawns or tool volume — the harness's own background.
        #
        # They are still recorded, because a count that arrives on a clock is
        # evidence about the harness and dropping it would be stripping on
        # uncertainty. But they go in one pooled file rather than one file each:
        # 154 of c3's 184 event files were a single 172-byte untyped stop, which is
        # how a deployment reached 966 files and made the raw directory unreadable.
        if not payload.get("agent_type"):
            agent_id = "_untyped-stops"

    if line is None:
        return

    target = os.path.join(events_dir, f"{agent_id}.jsonl")
    try:
        with open(target, "a") as f:
            f.write(json.dumps(line, separators=(",", ":")) + "\n")
    except Exception:
        return

    # Supervisor cadence counter (item 5.5.4). Per-agent integer file at
    # agent_states/counters/<agent_id>. Incremented on every PostToolUse event.
    # The orchestrator's watchdog reads + resets these when it decides to
    # spawn a supervisor check. Pure best-effort — never fails the caller.
    if event == "PostToolUse" and agent_id != "orchestrator":
        try:
            counters_dir = os.path.join(cycle_dir, "agent_states", "counters")
            os.makedirs(counters_dir, exist_ok=True)
            counter_path = os.path.join(counters_dir, agent_id)
            current = 0
            if os.path.exists(counter_path):
                with open(counter_path) as f:
                    current = int(f.read().strip() or "0")
            with open(counter_path, "w") as f:
                f.write(str(current + 1))
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    finally:
        # Logging must never break the calling tool.
        sys.exit(0)
