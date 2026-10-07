"""Where the telemetry hook writes — .claude/hooks/log-event.py.

Fan-out 1 lost every clone's telemetry to one directory in the origin repo: a
parallel-run clone is a *linked worktree*, so `git rev-parse --git-common-dir`
resolved to the origin. That resolution is still correct for a Phase-3 agent
worktree, whose events do belong to the cycle in the main checkout — so the two
cases are pinned here together. They are indistinguishable by git topology; only
the `agent_states/.fanout-clone` marker separates them.

Stdlib only:

    python3 tests/test_log_event_root.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/log-event.py"

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def git(*args: str, cwd: pathlib.Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def origin_repo(tmp: pathlib.Path) -> pathlib.Path:
    repo = tmp / "origin"
    repo.mkdir()
    git("init", "-q", "-b", "main", ".", cwd=repo)
    git("config", "user.email", "t@t", cwd=repo)
    git("config", "user.name", "t", cwd=repo)
    (repo / "README.md").write_text("x\n")
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "init", cwd=repo)
    return repo


def fire(cwd: pathlib.Path, agent_id: str = "a1") -> None:
    """One PostToolUse event, as Claude Code would deliver it."""
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "s",
        "agent_id": agent_id,
        "agent_type": "coding",
        "tool_name": "Read",
        "tool_input": {"file_path": "x"},
        "tool_response": {},
        "cwd": str(cwd),
    }
    subprocess.run([sys.executable, str(HOOK)], cwd=cwd, input=json.dumps(payload),
                   text=True, capture_output=True, timeout=30)


def fire_stop(cwd: pathlib.Path, agent_id: str, agent_type: str) -> None:
    """One SubagentStop. `agent_type` is what separates one of our agents from
    the harness's own background."""
    payload = {
        "hook_event_name": "SubagentStop",
        "session_id": "s",
        "agent_id": agent_id,
        "agent_type": agent_type,
        "stop_reason": None,
        "cwd": str(cwd),
    }
    subprocess.run([sys.executable, str(HOOK)], cwd=cwd, input=json.dumps(payload),
                   text=True, capture_output=True, timeout=30)


def events(repo: pathlib.Path) -> list[str]:
    d = repo / "agent_states" / "events"
    return sorted(f.name for f in d.iterdir()) if d.is_dir() else []


def main() -> int:
    print("log-event root resolution")

    with tempfile.TemporaryDirectory() as tmp:
        # A Phase-3 agent worktree: events belong to the cycle in the main checkout.
        t = pathlib.Path(tmp)
        repo = origin_repo(t)
        wt = t / "agent-wt"
        git("worktree", "add", "-q", "--detach", str(wt), cwd=repo)
        fire(wt, "impl-2.0")
        check("agent worktree logs to the main checkout", events(repo) == ["impl-2.0.jsonl"],
              f"origin={events(repo)} worktree={events(wt)}")
        check("  ... and not to the worktree itself", events(wt) == [], str(events(wt)))

    with tempfile.TemporaryDirectory() as tmp:
        # A fan-out clone: same topology, opposite answer, because of the marker.
        t = pathlib.Path(tmp)
        repo = origin_repo(t)
        clone = t / "repo-c1"
        git("worktree", "add", "-q", "--detach", str(clone), cwd=repo)
        (clone / "agent_states").mkdir(parents=True, exist_ok=True)
        (clone / "agent_states" / ".fanout-clone").write_text("issue=419\n")
        fire(clone, "impl-2.0")
        check("marked fan-out clone logs to itself", events(clone) == ["impl-2.0.jsonl"],
              f"clone={events(clone)} origin={events(repo)}")
        check("  ... and the origin stays clean", events(repo) == [], str(events(repo)))
        check("  ... and its counter is local",
              (clone / "agent_states" / "counters" / "impl-2.0").is_file())

    with tempfile.TemporaryDirectory() as tmp:
        # Two clones of one origin must not commingle — the fan-out 1 failure.
        t = pathlib.Path(tmp)
        repo = origin_repo(t)
        for n in (1, 2):
            c = t / f"repo-c{n}"
            git("worktree", "add", "-q", "--detach", str(c), cwd=repo)
            (c / "agent_states").mkdir(parents=True, exist_ok=True)
            (c / "agent_states" / ".fanout-clone").write_text(f"clone=c{n}\n")
            fire(c, "impl-1.0")
        check("concurrent clones do not commingle",
              events(t / "repo-c1") == ["impl-1.0.jsonl"]
              and events(t / "repo-c2") == ["impl-1.0.jsonl"]
              and events(repo) == [],
              f"c1={events(t / 'repo-c1')} c2={events(t / 'repo-c2')} origin={events(repo)}")

    with tempfile.TemporaryDirectory() as tmp:
        # The plain case, and the one every non-parallel run takes.
        t = pathlib.Path(tmp)
        repo = origin_repo(t)
        fire(repo, "orchestrator")
        check("main checkout logs to itself", events(repo) == ["orchestrator.jsonl"],
              str(events(repo)))

    with tempfile.TemporaryDirectory() as tmp:
        # Untyped stops pool into one file. Measured: 154 of c3's 184 event files
        # were a single 172-byte untyped stop, which is how a deployment reached
        # 966 files and made the raw directory larger than a context window.
        t = pathlib.Path(tmp)
        repo = origin_repo(t)
        for n in range(6):
            fire_stop(repo, f"a{n}0000000000000", "")
        fire_stop(repo, "verify-1", "verify")
        fire(repo, "coding-1")
        names = events(repo)
        check("untyped stops share one file",
              names.count("_untyped-stops.jsonl") == 1, str(names))
        check("  ... six of them, not six files", len(names) == 3, str(names))
        check("  ... a typed stop keeps its own file",
              "verify-1.jsonl" in names, str(names))
        check("  ... and so does a tool call", "coding-1.jsonl" in names, str(names))

        pooled = (repo / "agent_states/events/_untyped-stops.jsonl").read_text().splitlines()
        check("  ... every untyped stop is kept, not dropped", len(pooled) == 6, str(len(pooled)))
        ids = [json.loads(x)["agent_id"] for x in pooled]
        check("  ... each under its own agent_id, so nothing is conflated",
              len(set(ids)) == 6, str(ids))
        check("  ... and the pooled file is never the agent_id itself",
              all(i != "_untyped-stops" for i in ids), str(ids))

    with tempfile.TemporaryDirectory() as tmp:
        # Never fail the calling tool, whatever it is handed.
        t = pathlib.Path(tmp)
        outside = t / "not-a-repo"
        outside.mkdir()
        p = subprocess.run([sys.executable, str(HOOK)], cwd=outside, input="not json",
                           text=True, capture_output=True, timeout=30)
        check("garbage payload outside a repo exits 0", p.returncode == 0, p.stderr)

    if FAILURES:
        print("\nFAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\nlog-event root resolution: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
