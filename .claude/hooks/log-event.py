#!/usr/bin/env python3
"""log-event — Claude Code PostToolUse + SubagentStop hook.

Appends one JSONL line per event to ``<main-root>/agent_states/events/<agent_id>.jsonl``,
where ``<main-root>`` is resolved from the git common dir so this works identically
from the main checkout or from any Phase-3 worktree. Pure logging — never fails
the calling tool.

Wired from ``.claude/settings.json`` as a ``PostToolUse`` and ``SubagentStop`` hook.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return

    # Resolve main project root via git common dir (works from any worktree).
    try:
        common = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        main_root = os.path.dirname(os.path.abspath(common))
    except Exception:
        return

    events_dir = os.path.join(main_root, "agent_states", "events")
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

    if line is None:
        return

    target = os.path.join(events_dir, f"{agent_id}.jsonl")
    try:
        with open(target, "a") as f:
            f.write(json.dumps(line, separators=(",", ":")) + "\n")
    except Exception:
        return


if __name__ == "__main__":
    try:
        main()
    finally:
        # Logging must never break the calling tool.
        sys.exit(0)
