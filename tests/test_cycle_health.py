"""Tests for .claude/skills/cycle/cycle-health.py.

The failure this tool exists to end: in round 9 three of five cycles were killed
by the host, and every one was logged as a `wakeup` — the same row a healthy
cycle writes while it thinks. So the assertions that matter are the ones that
separate "working", "stopped", and "stopped for a reason we can name".

    python3 tests/test_cycle_health.py
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / ".claude/skills/cycle/cycle-health.py"

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def run(root, projects, *args):
    env = dict(os.environ, CYCLE_HEALTH_PROJECTS=str(projects))
    p = subprocess.run([sys.executable, str(TOOL), "--root", str(root), *args],
                       capture_output=True, text=True, timeout=30, env=env)
    return p.returncode, p.stdout + p.stderr


def clone(root: pathlib.Path, name: str, *, event_age_s: float | None) -> pathlib.Path:
    c = root / name
    (c / "agent_states" / "events").mkdir(parents=True)
    if event_age_s is not None:
        f = c / "agent_states" / "events" / "a1.jsonl"
        f.write_text('{"event":"post_tool"}\n')
        t = time.time() - event_age_s
        os.utime(f, (t, t))
    return c


def transcript(projects: pathlib.Path, c: pathlib.Path, text: str) -> None:
    d = projects / str(c).replace("/", "-")
    d.mkdir(parents=True, exist_ok=True)
    (d / "s.jsonl").write_text(
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": text}]}}) + "\n")


tmp = tempfile.TemporaryDirectory()
R = pathlib.Path(tmp.name).resolve()
PROJ = R / "projects"
CL = R / "cycles"
CL.mkdir()

# A working clone, a quiet one, one with nothing yet.
c_run = clone(CL, "app-c1", event_age_s=30)
c_old = clone(CL, "app-c2", event_age_s=60 * 90)
c_new = clone(CL, "app-c3", event_age_s=None)

rc, out = run(CL, PROJ)
check("a clone with recent telemetry is running", "running  app-c1" in out, out)
check("  ... silence past the threshold is stalled", "stalled  app-c2" in out, out)
check("  ... and a clone with no events yet is idle, not stalled",
      "idle     app-c3" in out, out)
check("a stalled clone makes the check fail", rc == 1, f"rc={rc}")

# The round-9 wordings. Each killed a real cycle, and each must be `dead` —
# distinguishable from `stalled`, because "it stopped" and "we know why" are
# different claims and conflating them is what hid this for two rounds.
for name, text, meaning in (
    ("app-c4", "API Error: Your computer went to sleep mid-response.", "host slept"),
    ("app-c5", "Not logged in · Please run /login", "lost authentication"),
):
    c = clone(CL, name, event_age_s=60 * 90)
    transcript(PROJ, c, text)
rc, out = run(CL, PROJ)
check("a host-sleep death is dead, not stalled", "dead     app-c4" in out, out)
check("  ... and names why", "host slept" in out, out)
check("an auth death is dead too", "dead     app-c5" in out, out)
check("  ... and names why", "lost authentication" in out, out)
check("  ... while the unexplained one stays stalled", "stalled  app-c2" in out, out)

# A fatal wording must not be read from an ancient transcript when the clone is
# demonstrably alive: liveness is the stronger signal, but a death is sticky —
# the process that would clear it is the one that stopped. Documented either way.
rc, out = run(CL, PROJ, "--stall-min", "0.01")
check("the stall threshold is adjustable", "stalled  app-c1" in out or "dead" in out, out)

# JSON, for anything that wants to act on this rather than read it.
rc, out = run(CL, PROJ, "--json")
data = json.loads(out)
states = {r["clone"]: r["state"] for r in data["clones"]}
check("json reports every clone", len(states) == 5, str(states))
check("  ... with the same verdicts", states["app-c4"] == "dead" and states["app-c2"] == "stalled",
      str(states))

# Failure modes: a health check that crashes reports nothing.
rc, out = run(R / "nope", PROJ)
check("a missing root exits 2, not 0", rc == 2, f"rc={rc}")
empty = R / "empty"; empty.mkdir()
rc, out = run(empty, PROJ)
check("no clones is not a failure", rc == 0, f"rc={rc} {out}")

bad = clone(CL, "app-c6", event_age_s=10)
d = PROJ / str(bad).replace("/", "-"); d.mkdir(parents=True, exist_ok=True)
(d / "s.jsonl").write_text("not json at all\n\x00\x01")
rc, out = run(CL, PROJ)
check("a malformed transcript does not crash the check", "app-c6" in out, out)

tmp.cleanup()

print()
if FAILURES:
    print(f"{len(FAILURES)} failed:")
    for f in FAILURES:
        print("  " + f)
    sys.exit(1)
print("all cycle-health tests passed")
