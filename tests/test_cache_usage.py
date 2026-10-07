"""Tests for .claude/skills/cycle/cache-usage.py.

Two arithmetic traps decide whether this tool measures anything at all, and
both of them inflate quietly rather than erroring.

Claude Code writes one transcript entry per content block, so one assistant
message appears several times carrying the *same* usage block; summing rows
overstates a real transcript by roughly 1.8x. And fan-out clones are reused
between rounds, so a clone directory holds several runs and an unwindowed
total compares one round against the sum of all of them — which is exactly
how the run-5 baseline in the round-6 handoff came to be a three-round total
wearing one round's label.

    python3 tests/test_cache_usage.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / ".claude/skills/cycle/cache-usage.py"

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def eq(name: str, got, want) -> None:
    check(name, got == want, f"want {want!r} got {got!r}")


def entry(mid, ts, write=0, read=0, out=0, eph1h=None, eph5m=0, request=None):
    usage = {
        "input_tokens": 2,
        "cache_creation_input_tokens": write,
        "cache_read_input_tokens": read,
        "output_tokens": out,
        "cache_creation": {
            "ephemeral_1h_input_tokens": write if eph1h is None else eph1h,
            "ephemeral_5m_input_tokens": eph5m,
        },
    }
    rec = {"type": "assistant", "message": {"usage": usage}}
    if mid is not None:
        rec["message"]["id"] = mid
    if request is not None:
        rec["requestId"] = request
    if ts is not None:
        rec["timestamp"] = ts
    return json.dumps(rec)


def write_jsonl(path: pathlib.Path, lines) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(*args):
    p = subprocess.run([sys.executable, str(TOOL), *args],
                       capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout, p.stderr


def totals(*args):
    rc, out, err = run(*args, "--json")
    assert rc == 0, err
    return json.loads(out)["total"]


tmp = tempfile.TemporaryDirectory()
R = pathlib.Path(tmp.name)

# ---------------------------------------------------------------- dedupe
#
# One message, four content blocks, one bill.
P = R / "proj"
write_jsonl(P / "session.jsonl", [
    entry("msg_a", "2026-09-12T17:00:00Z", write=1000, read=5000, out=10),
    entry("msg_a", "2026-09-12T17:00:00Z", write=1000, read=5000, out=10),
    entry("msg_a", "2026-09-12T17:00:01Z", write=1000, read=5000, out=10),
    entry("msg_b", "2026-09-12T17:01:00Z", write=500, read=9000, out=20),
])
t = totals(str(P))
eq("repeated message ids collapse to one message", t["msgs"], 2)
eq("  ... and their tokens are counted once", t["write"], 1500)
eq("  ... reads too", t["read"], 14000)
eq("  ... and output", t["out"], 30)

# Deduplication spans files in one project: a resumed session repeats ids.
write_jsonl(P / "resumed.jsonl", [entry("msg_a", "2026-09-12T17:00:00Z", write=1000, read=5000)])
t = totals(str(P))
eq("dedupe spans transcripts in one project", t["msgs"], 2)
eq("  ... so a resume does not double the bill", t["write"], 1500)

# requestId stands in when message.id is absent — the pairing the transcript
# actually uses, one requestId per API call.
# Subagent transcripts live in a per-session subdirectory, and a fan-out puts
# most of its tokens there. `transcripts()` walks at any depth; nothing asserted
# it, so a flattening regression would have passed. gate-log.py held the opposite
# belief about the same directory and undercounted round 9's refusals 3:1.
NEST = R / "nested"
write_jsonl(NEST / "session.jsonl", [entry("msg_top", "2026-09-13T09:00:00Z", write=1000, read=0)])
write_jsonl(NEST / "session" / "subagents" / "agent-a1.jsonl",
            [entry("msg_sub", "2026-09-13T09:01:00Z", write=2000, read=0)])
tn = totals(str(NEST))
eq("a subagent transcript in a subdirectory is counted", tn["write"], 3000)
eq("  ... as its own message, not folded into the parent's", tn["msgs"], 2)

Q = R / "byrequest"
write_jsonl(Q / "s.jsonl", [
    entry(None, "2026-09-12T17:00:00Z", write=700, request="req_1"),
    entry(None, "2026-09-12T17:00:00Z", write=700, request="req_1"),
])
t = totals(str(Q))
eq("requestId deduplicates when message.id is missing", t["msgs"], 1)
eq("  ... and nothing is flagged unkeyed", t["unkeyed"], 0)

# An entry with neither key is counted anyway and reported. Never strip on
# uncertainty: a block with no id still cost real tokens.
N = R / "nokey"
write_jsonl(N / "s.jsonl", [
    entry(None, "2026-09-12T17:00:00Z", write=300),
    entry(None, "2026-09-12T17:00:00Z", write=300),
])
t = totals(str(N))
eq("unkeyed blocks are still counted", t["write"], 600)
eq("  ... and surfaced as unkeyed", t["unkeyed"], 2)
rc, out, _ = run(str(N))
check("  ... with an anomaly line in the report", "cannot be deduplicated" in out)

# ---------------------------------------------------------------- windows
#
# The clone-reuse trap. Two rounds in one directory.
W = R / "tworounds"
write_jsonl(W / "s.jsonl", [
    entry("r5_1", "2026-09-11T13:40:00Z", write=1000, read=30000),
    entry("r5_2", "2026-09-11T14:10:00Z", write=1000, read=30000),
    entry("r6_1", "2026-09-12T16:50:00Z", write=400, read=20000),
    entry("r6_2", "2026-09-12T17:50:00Z", write=400, read=20000),
])
eq("unwindowed total spans every round in the clone", totals(str(W))["write"], 2800)
eq("--since isolates the later round", totals(str(W), "--since", "2026-09-12T16:40")["write"], 800)
eq("--until isolates the earlier one", totals(str(W), "--until", "2026-09-12T00:00")["write"], 2000)
eq("  ... and both together bound a window",
   totals(str(W), "--since", "2026-09-11T13:00", "--until", "2026-09-11T14:00")["msgs"], 1)

# An undated entry inside a windowed run is kept, and the report says the
# total is therefore an upper bound.
U = R / "undated"
write_jsonl(U / "s.jsonl", [
    entry("d1", "2026-09-12T17:00:00Z", write=100),
    entry("u1", None, write=100),
])
t = totals(str(U), "--since", "2026-09-12T16:40")
eq("an undated entry is kept under a window", t["write"], 200)
eq("  ... and counted as undated", t["undated"], 1)
rc, out, _ = run(str(U), "--since", "2026-09-12T16:40")
check("  ... with the total called an upper bound", "upper bound" in out)
eq("nothing is undated when no window is in force", totals(str(U))["undated"], 0)

# ---------------------------------------------------------------- roles
#
# Attribution is a label. It must never change a total.
A = R / "withagents"
write_jsonl(A / "main.jsonl", [entry("o1", "2026-09-12T17:00:00Z", write=100, read=900)])
write_jsonl(A / "sess" / "subagents" / "agent-x.jsonl",
            [entry("s1", "2026-09-12T17:00:05Z", write=50, read=400)])
write_jsonl(A / "agent-y.jsonl", [entry("s2", "2026-09-12T17:00:06Z", write=25, read=200)])
t = totals(str(A))
eq("subagent transcripts at any depth are counted", t["msgs"], 3)
eq("  ... into the same total", t["write"], 175)
rc, out, _ = run(str(A), "--by-role")
check("orchestrator is attributed", "orchestrator" in out)
check("  ... and subagents too", out.count("subagent") >= 1)

# ---------------------------------------------------------------- TTL split
S = R / "ttl"
write_jsonl(S / "s.jsonl", [
    entry("a", "2026-09-12T17:00:00Z", write=1000, eph1h=1000, eph5m=0),
    entry("b", "2026-09-12T17:00:01Z", write=1000, eph1h=0, eph5m=1000),
])
t = totals(str(S))
eq("1h and 5m writes are tracked apart", (t["eph1h"], t["eph5m"]), (1000, 1000))
eq("  ... and neither is double counted into the write total", t["write"], 2000)
rc, out, _ = run(str(S))
check("  ... reported as a percentage of writes", "50%" in out)

# A split that disagrees with the write total is reported, not corrected --
# the authoritative number is the one the provider billed.
M = R / "mismatch"
write_jsonl(M / "s.jsonl", [entry("a", "2026-09-12T17:00:00Z", write=1000, eph1h=10, eph5m=10)])
t = totals(str(M))
eq("a bad TTL split leaves the write total alone", t["write"], 1000)
eq("  ... and is flagged", t["split_mismatch"], 1)

# ---------------------------------------------------------------- robustness
B = R / "broken"
write_jsonl(B / "s.jsonl", [
    "{not json at all",
    "",
    json.dumps({"type": "user", "message": {"content": "hi"}}),
    json.dumps({"type": "assistant", "message": {"usage": "not-a-dict"}}),
    entry("good", "2026-09-12T17:00:00Z", write=42),
])
t = totals(str(B))
eq("malformed lines are skipped, not fatal", t["msgs"], 1)
eq("  ... and the good one still counts", t["write"], 42)

rc, _, err = run(str(R / "does-not-exist"))
check("an empty scan exits non-zero rather than printing zeros", rc != 0)

E = R / "empty"
E.mkdir()
rc, _, _ = run(str(E))
check("a directory with no transcripts exits non-zero", rc != 0)

# --match narrows by directory name, which is how one fan-out is selected.
rc, out, _ = run(str(P), str(Q), "--match", "byrequest")
rows = [ln.split()[0] for ln in out.splitlines()[1:] if ln.strip()]
check("--match narrows to the named projects", rows == ["byrequest", "TOTAL"], repr(rows))

tmp.cleanup()

print()
if FAILURES:
    print(f"{len(FAILURES)} failed:")
    for f in FAILURES:
        print("  " + f)
    sys.exit(1)
print("all cache-usage tests passed")
