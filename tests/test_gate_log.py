"""Gate-wait capture — .claude/hooks/gate-log.py + skills/cycle/gate-report.py.

Fan-out 1 produced a gate log containing its header and nothing else: manual
logging across three concurrent sessions lost to the work of running them
(evidence-run1 E7). These tests pin the automated replacement, and in particular
the property that makes it trustworthy — an interval is recorded even when the
gate cannot be classified, so a bad regex costs a label and never a measurement.

Stdlib only:

    python3 tests/test_gate_log.py
"""

from __future__ import annotations

import json
import os
import importlib.util
import pathlib
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/gate-log.py"
REPORT = ROOT / ".claude/skills/cycle/gate-report.py"

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def git(*args: str, cwd: pathlib.Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(tmp: pathlib.Path) -> pathlib.Path:
    repo = tmp / "repo"
    (repo / "agent_states").mkdir(parents=True)
    git("init", "-q", "-b", "main", str(repo), cwd=tmp)
    return repo


def transcript(repo: pathlib.Path, text: str) -> str:
    """A minimal Claude Code transcript whose last assistant message is `text`."""
    p = repo / "t.jsonl"
    with p.open("w") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "go"}}) + "\n")
        f.write(json.dumps({"type": "assistant", "message": {
            "content": [{"type": "text", "text": text}]}}) + "\n")
    return str(p)


def stale_transcript(repo: pathlib.Path, old_text: str, new_text: str | None = None) -> str:
    """A transcript caught mid-flush: the newest entry is a *user* entry.

    This is the J1 shape. The assistant turn that just ended has not been written,
    so the newest assistant text belongs to an earlier turn. Optionally append the
    real message afterwards to simulate the flush completing.
    """
    p = repo / "t.jsonl"
    with p.open("w") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "go"}}) + "\n")
        f.write(json.dumps({"type": "assistant", "message": {
            "content": [{"type": "text", "text": old_text}]}}) + "\n")
        f.write(json.dumps({"type": "user", "message": {"content": "next"}}) + "\n")
    if new_text is not None:
        with p.open("a") as f:
            f.write(json.dumps({"type": "assistant", "message": {
                "content": [{"type": "text", "text": new_text}]}}) + "\n")
    return str(p)


def flush(repo: pathlib.Path, text: str) -> None:
    """Append the message Stop was too early to see."""
    with (repo / "t.jsonl").open("a") as f:
        f.write(json.dumps({"type": "assistant", "message": {
            "content": [{"type": "text", "text": text}]}}) + "\n")


def denial_transcript(repo: pathlib.Path, entries) -> str:
    """A transcript carrying tool calls, some of which were refused.

    `entries` is a list of (tool_use_id, command, result_text). A refusal is a
    `tool_result` whose body carries the harness's refusal wording; the tool
    never ran, so there is no PostToolUse for it anywhere.
    """
    p = repo / "d.jsonl"
    with p.open("w") as f:
        for tid, cmd, result in entries:
            f.write(json.dumps({"type": "assistant", "timestamp": "2026-09-13T04:00:00.000Z",
                                "message": {"content": [
                                    {"type": "tool_use", "id": tid, "name": "Bash",
                                     "input": {"command": cmd}}]}}) + "\n")
            f.write(json.dumps({"type": "user", "timestamp": "2026-09-13T04:00:01.000Z",
                                "message": {"content": [
                                    {"type": "tool_result", "tool_use_id": tid,
                                     "content": result}]}}) + "\n")
    return str(p)


DENIED = ("Permission for this action was denied by the Claude Code auto mode "
          "classifier. Reason: [Auto-Mode Bypass]. If you have other tasks...")
REJECTED = ("The user doesn't want to proceed with this tool use. The tool use "
            "was rejected. STOP what you are doing...")
# The project's own deny list, not the classifier. Its two halves straddle the
# command, which is why a single-substring check missed it: fan-out 7's c5 was
# refused twice this way and the first cut of the scanner saw neither.
DENY_RULE = ("Permission to use Bash with command rm -f /tmp/x.dart; git status "
             "--short has been denied.")


def fire(repo: pathlib.Path, event: str, **kw) -> None:
    payload = {"hook_event_name": event, "session_id": "s1", "cwd": str(repo), **kw}
    subprocess.run([sys.executable, str(HOOK)], cwd=repo, input=json.dumps(payload),
                   text=True, capture_output=True, timeout=30)


def rows(repo: pathlib.Path) -> list[list[str]]:
    p = repo / "agent_states" / "gate-log.tsv"
    if not p.exists():
        return []
    return [ln.split("\t") for ln in p.read_text().splitlines()[1:] if ln]


def report(repo: pathlib.Path, *extra: str) -> str:
    p = subprocess.run([sys.executable, str(REPORT), *extra],
                       cwd=repo, capture_output=True, text=True, timeout=30)
    return p.stdout + p.stderr


def backdate(repo: pathlib.Path, seconds: int) -> None:
    """Age the open gate so a wait can be asserted without sleeping."""
    p = repo / "agent_states" / "gate-open.json"
    rec = json.loads(p.read_text())
    then = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    rec["raised_at"] = then.strftime("%Y-%m-%dT%H:%M:%SZ")
    p.write_text(json.dumps(rec))


def backdate_perm(repo: pathlib.Path, seconds: int) -> None:
    """Age every open permission ask, so a wait can be asserted without sleeping."""
    d = repo / "agent_states" / "permission-open"
    then = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    for f in d.iterdir():
        rec = json.loads(f.read_text())
        rec["raised_at"] = then.strftime("%Y-%m-%dT%H:%M:%SZ")
        f.write_text(json.dumps(rec))


def main() -> int:
    print("gate-log")

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        fire(repo, "Stop", transcript_path=transcript(
            repo, "Here is the PRD summary.\n\n**Proceed to tasks?**"))
        check("Stop leaves an open-gate record",
              (repo / "agent_states" / "gate-open.json").is_file())
        check("  ... classified from the skill's own prompt",
              json.loads((repo / "agent_states" / "gate-open.json").read_text())["gate"]
              == "gate-1")
        check("  ... and no row yet — an unanswered gate is not a wait", rows(repo) == [])

        out = report(repo)
        check("an open gate is reported as open, not counted",
              "OPEN gate 'gate-1'" in out and "unanswered" in out, out)

        backdate(repo, 125)
        fire(repo, "UserPromptSubmit", prompt="yes, proceed")
        r = rows(repo)
        check("the answer closes it into one row", len(r) == 1, str(r))
        check("  ... with the measured wait", r and 120 <= int(r[0][2]) <= 130, str(r))
        check("  ... and the gate name", r and r[0][5] == "gate-1", str(r))
        check("  ... and the answer text", r and "yes, proceed" in r[0][8], str(r))
        check("  ... and the open record is cleared",
              not (repo / "agent_states" / "gate-open.json").exists())

    with tempfile.TemporaryDirectory() as tmp:
        # The property that makes the measurement trustworthy: an unrecognised
        # gate still yields an interval. A regex miss must not read as no wait.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        fire(repo, "Stop", transcript_path=transcript(
            repo, "I have finished phase 3 and moved on."))
        backdate(repo, 40)
        fire(repo, "UserPromptSubmit", prompt="ok")
        r = rows(repo)
        check("an unclassified turn is still measured", len(r) == 1 and r[0][5] == "-", str(r))
        check("  ... excluded from the gate summary by default",
              "none classified as a gate" in report(repo), report(repo))
        check("  ... but visible under --all",
              "1 gate(s)" in report(repo, "--all"), report(repo, "--all"))

    with tempfile.TemporaryDirectory() as tmp:
        # An unreadable transcript must not lose the interval either.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        fire(repo, "Stop", transcript_path=str(repo / "does-not-exist.jsonl"))
        backdate(repo, 15)
        fire(repo, "UserPromptSubmit", prompt="hi")
        check("a missing transcript costs the label, not the row", len(rows(repo)) == 1,
              str(rows(repo)))

    with tempfile.TemporaryDirectory() as tmp:
        # Fan-out: per-clone log AND the shared run-level log the operator reads.
        t = pathlib.Path(tmp)
        run_log = t / "cycles" / "gate-log.tsv"
        clones = []
        for n in (1, 2):
            repo = t / f"c{n}"
            (repo / "agent_states").mkdir(parents=True)
            git("init", "-q", "-b", "main", str(repo), cwd=t)
            (repo / "agent_states" / ".fanout-clone").write_text(
                f"issue=41{n}\nclone=c{n}\ngate_log={run_log}\n")
            clones.append(repo)
        for n, repo in enumerate(clones, 1):
            fire(repo, "Stop", transcript_path=transcript(repo, "Begin implementation?"))
            backdate(repo, 60 * n)
            fire(repo, "UserPromptSubmit", prompt="go")
        check("each clone keeps its own log",
              all(len(rows(c)) == 1 for c in clones),
              str([rows(c) for c in clones]))
        shared = [ln.split("\t") for ln in run_log.read_text().splitlines()[1:] if ln]
        check("both also land in the shared run log", len(shared) == 2, str(shared))
        check("  ... tagged by clone and issue",
              sorted(r[3] for r in shared) == ["c1", "c2"]
              and sorted(r[4] for r in shared) == ["411", "412"], str(shared))
        check("  ... with one header only", run_log.read_text().count("raised_at") == 1)

        out = subprocess.run([sys.executable, str(REPORT), "--log", str(run_log), "--json"],
                             cwd=clones[0], capture_output=True, text=True, timeout=30)
        data = json.loads(out.stdout)
        check("the run-level summary aggregates both",
              data["gates"] == 2 and data["by_gate"]["gate-2"]["n"] == 2, out.stdout)

    with tempfile.TemporaryDirectory() as tmp:
        # No log is "not captured" — never a plausible-looking zero.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        out = report(repo)
        check("a missing log says not captured, not zero",
              "not captured" in out and "median" not in out and "gate(s)" not in out, out)

    with tempfile.TemporaryDirectory() as tmp:
        # The hook must never speak to the model: UserPromptSubmit stdout is
        # injected into context.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        fire(repo, "Stop", transcript_path=transcript(repo, "Proceed to tasks?"))
        p = subprocess.run(
            [sys.executable, str(HOOK)], cwd=repo,
            input=json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": str(repo),
                              "prompt": "yes"}),
            text=True, capture_output=True, timeout=30)
        check("hook writes nothing to stdout", p.stdout == "", repr(p.stdout))
        check("  ... and exits 0", p.returncode == 0, str(p.returncode))

        p = subprocess.run([sys.executable, str(HOOK)], cwd=repo, input="{{not json",
                           text=True, capture_output=True, timeout=30)
        check("garbage payload exits 0 silently",
              p.returncode == 0 and p.stdout == "", p.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        # The reason F3 existed: 30 of 33 logged intervals ended because a background
        # agent finished, not because a person answered, and counting them as gates
        # overstated human wait 40x. This whole path shipped untested.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        fire(repo, "Stop", transcript_path=transcript(repo, "Working on task 2.0."))
        backdate(repo, 900)
        fire(repo, "UserPromptSubmit",
             prompt="<task-notification>\n<task-id>abc</task-id>\n</task-notification>")
        r = rows(repo)
        check("an agent wakeup is labelled, not counted as a gate",
              len(r) == 1 and r[0][5] == "wakeup", str(r))

        # And a real person answering the same shape of turn is not.
        fire(repo, "Stop", transcript_path=transcript(repo, "Proceed to tasks?"))
        backdate(repo, 60)
        fire(repo, "UserPromptSubmit", prompt="yes, go ahead")
        r = rows(repo)
        check("  ... while a human answer stays a gate",
              len(r) == 2 and r[1][5] == "gate-1", str(r))

        out = report(repo)
        check("the report separates wakeups from human wait",
              "1 of 2 interval(s) ended on an agent-completion wakeup" in out, out)
        # Tolerant to the second, deliberately. `backdate` sets raised_at to
        # now-900s and the answer lands whenever the next subprocess gets to
        # run, so under load the interval renders 15m01s or 15m02s. Asserting
        # the exact second made this suite fail only when the whole runner ran,
        # which is the worst kind of flake: green alone, red in CI, and blamed
        # on load rather than on the assertion.
        check("  ... and excludes them from the gate total",
              any(f"15m{n:02d}s" in out for n in range(0, 6)) and "9h" not in out, out)

        data = json.loads(subprocess.run(
            [sys.executable, str(REPORT), "--json"], cwd=repo,
            capture_output=True, text=True, timeout=30).stdout)
        check("  ... reports them in JSON too",
              data["wakeups"]["n"] == 1 and data["gates"] == 1, out)
        # ~60, not ~960: the 900s wakeup must not be in the human total.
        check("  ... and the wakeup's 900s are not in the gate total",
              55 <= data["wait_total_s"] <= 70, str(data.get("wait_total_s")))

    with tempfile.TemporaryDirectory() as tmp:
        # A human answer that merely *mentions* a notification is still a human.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        fire(repo, "Stop", transcript_path=transcript(repo, "Begin implementation?"))
        backdate(repo, 30)
        fire(repo, "UserPromptSubmit", prompt="the <task-notification> looked wrong, but proceed")
        r = rows(repo)
        check("a prompt that merely mentions a wakeup tag is not one",
              len(r) == 1 and r[0][5] == "gate-2", str(r))

    with tempfile.TemporaryDirectory() as tmp:
        # An unreadable transcript must say why, in a form nothing else produces.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        fire(repo, "Stop", transcript_path=str(repo))          # a directory
        backdate(repo, 20)
        fire(repo, "UserPromptSubmit", prompt="ok")
        r = rows(repo)
        check("an unreadable transcript records why, not a blank",
              r and r[0][7].startswith("[unclassified:"), str(r))
        check("  ... naming the actual cause",
              r and "directory" in r[0][7], str(r))

    # The two prefix lists are separate code and drifted once already. Compare the
    # loaded values, not the source text: a regex over the source matched only
    # double-quoted literals, so reformatting to single quotes made BOTH sides
    # empty and the test passed while the lists disagreed — a parity check that
    # fails open is worse than none.
    def load(path, name):
        spec = importlib.util.spec_from_file_location(f"_m{abs(hash(path))}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return set(getattr(mod, name))

    hp = load(HOOK, "WAKEUP_PREFIXES")
    gp = load(REPORT, "WAKEUP_ANSWER")
    check("hook and report agree on what a wakeup looks like", hp == gp,
          f"hook-only={sorted(hp - gp)} report-only={sorted(gp - hp)}")
    check("  ... and the lists are not empty (a vacuous pass is not a pass)",
          len(hp) >= 3, str(hp))

    hl = load(HOOK, "LOCAL_COMMAND_PREFIXES")
    gl = load(REPORT, "LOCAL_CMD_ANSWER")
    check("  ... and on what a local-command wrapper looks like", hl == gl,
          f"hook-only={sorted(hl - gl)} report-only={sorted(gl - hl)}")

    # Tier 3 duplicates the same two constants across hook and reader for the same
    # dependency-free reason, so it gets the same pinning.
    hr, gr = load(HOOK, "RESUME_PREFIXES"), load(REPORT, "RESUME_PREFIXES")
    check("  ... and on what a resume answer looks like", hr == gr,
          f"hook-only={sorted(hr - gr)} report-only={sorted(gr - hr)}")
    check("  ... non-vacuously", len(hr) >= 3, str(hr))
    hn, gn = load(HOOK, "NOT_PERMISSION_TOOLS"), load(REPORT, "NOT_PERMISSION_TOOLS")
    check("  ... and on which tools are not permission dialogs", hn == gn,
          f"hook-only={sorted(hn - gn)} report-only={sorted(gn - hn)}")

    hm, gm = load(HOOK, "MERGE_ANSWERS"), load(REPORT, "MERGE_ANSWERS")
    check("  ... and on what a merge answer looks like", hm == gm,
          f"hook-only={sorted(hm - gm)} report-only={sorted(gm - hm)}")
    check("  ... non-vacuously", len(hm) >= 3, str(hm))

    # --- Tier 1: an explicit tag outranks every heuristic --------------------
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        # Text that tier 2 would call gate-1, tagged as something else. The tag
        # must win: it is the only tier that is not guessing.
        fire(repo, "Stop", transcript_path=transcript(
            repo, "Gate 1 — proceed to tasks? <!-- gate:gate-4b -->"))
        fire(repo, "UserPromptSubmit", prompt="yes")
        r = rows(repo)
        check("an explicit tag outranks the patterns", r and r[0][5] == "gate-4b", str(r))

    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        fire(repo, "Stop", transcript_path=transcript(
            repo, "quoting <!-- gate:gate-1 --> earlier, now <!-- gate:gate-2 -->"))
        fire(repo, "UserPromptSubmit", prompt="yes")
        r = rows(repo)
        check("  ... and the last tag wins, not the first", r and r[0][5] == "gate-2", str(r))

    # --- Tier 2: patterns grounded in text the orchestrator actually writes ---
    for text, want in (
        ("**Phase 2 complete.** --- ## Gate 1C+2B (lean — consolidated)", "gate-1+2"),
        ("**4B is blocked.** Verify's PASS does not clear this", "gate-4b"),
        ("## Cycle 426 — dry-run plan (`--mode lean`)", "plan"),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(pathlib.Path(tmp))
            fire(repo, "Stop", transcript_path=transcript(repo, text))
            fire(repo, "UserPromptSubmit", prompt="ok")
            r = rows(repo)
            check(f"tier 2 names {want!r} from observed text", r and r[0][5] == want, str(r))

    # The one label the old classifier ever produced was this false positive: a
    # message about a settings conflict that merely mentioned a report filename.
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        fire(repo, "Stop", transcript_path=transcript(
            repo, "that's the thread — see cycle_reports/pr-body-443-defer.md for context"))
        fire(repo, "UserPromptSubmit", prompt="ok")
        r = rows(repo)
        check("a mention of a pr-body filename is no longer a gate",
              r and r[0][5] == "-", str(r))

    # --- Tier 3: the answer names the gate the question did not ---------------
    for prompt, want in (("merged", "pr-merge"), ("/cycle --exe", "resume")):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(pathlib.Path(tmp))
            fire(repo, "Stop", transcript_path=transcript(repo, "PR #456 open. Changelog next."))
            fire(repo, "UserPromptSubmit", prompt=prompt)
            r = rows(repo)
            check(f"tier 3 names {want!r} from the answer {prompt!r}",
                  r and r[0][5] == want, str(r))

    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        fire(repo, "Stop", transcript_path=transcript(repo, "Gate 1C+2B — approve?"))
        fire(repo, "UserPromptSubmit", prompt="merged")
        r = rows(repo)
        check("  ... but never overrides a gate named by the question",
              r and r[0][5] == "gate-1+2", str(r))

    # --- J4: AskUserQuestion is a pipeline question, not a harness dialog -----
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        fire(repo, "PermissionRequest", tool_name="AskUserQuestion",
             tool_input={"questions": [{"question": "delete or un-nest?"}]})
        check("AskUserQuestion opens no permission record",
              not (repo / "agent_states" / "permission-open").exists()
              or not list((repo / "agent_states" / "permission-open").glob("*.json")))
        out = report(repo)
        check("  ... so nothing is reported as an open permission ask",
              "OPEN permission ask" not in out, out)

    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        fire(repo, "PermissionRequest", tool_name="Bash",
             tool_input={"command": "git push -u origin HEAD"})
        out = report(repo)
        check("  ... while a real Bash dialog still is",
              "OPEN permission ask" in out, out)

    # --- J1: Stop reading the transcript before the raising message lands ----
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        # Stop fires while only the *previous* turn is written.
        t = stale_transcript(repo, "Task 1.0 merged and green. Running the next task.")
        fire(repo, "Stop", transcript_path=t)
        rec = json.loads((repo / "agent_states/gate-open.json").read_text())
        check("a stale transcript is not classified from the wrong turn",
              rec["gate"] == "-" and rec["stale"] is True, str(rec))
        check("  ... and the excerpt says why, not the wrong text",
              "stale-transcript" in rec["excerpt"], str(rec))

        # The real gate message lands before the human answers.
        flush(repo, "## Gate 1C+2B — approve? <!-- gate:gate-1+2 -->")
        fire(repo, "UserPromptSubmit", prompt="/cycle --exe")
        r = rows(repo)
        check("  ... and answer-time re-read recovers the tag",
              r and r[0][5] == "gate-1+2", str(r))
        check("  ... in preference to the answer's own 'resume'",
              r and r[0][5] != "resume", str(r))
        check("  ... and the row carries the real excerpt",
              r and "Gate 1C+2B" in r[0][7], str(r))

    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        # Never flushed: fall back to the answer rather than inventing a gate.
        fire(repo, "Stop", transcript_path=stale_transcript(repo, "earlier turn"))
        fire(repo, "UserPromptSubmit", prompt="merged")
        r = rows(repo)
        check("a transcript that never flushes still falls back to the answer",
              r and r[0][5] == "pr-merge", str(r))

    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        # A healthy transcript must not pay for any of this.
        fire(repo, "Stop", transcript_path=transcript(repo, "Approve? <!-- gate:gate-2 -->"))
        rec = json.loads((repo / "agent_states/gate-open.json").read_text())
        check("a healthy transcript is not marked stale", rec["stale"] is False, str(rec))
        fire(repo, "UserPromptSubmit", prompt="yes")
        r = rows(repo)
        check("  ... and classifies at Stop time as before", r and r[0][5] == "gate-2", str(r))

    # --- pre-cycle: idle, not gate wait --------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        fire(repo, "Stop", transcript_path=transcript(repo, "Standing by."))
        backdate(repo, 40000)
        fire(repo, "UserPromptSubmit", prompt="/cycle 443 --mode lean")
        r = rows(repo)
        check("starting a cycle marks the interval pre-cycle", r and r[0][5] == "pre-cycle", str(r))
        out = report(repo)
        check("  ... and the reader counts it in neither total",
              "neither" in out and "40000" not in out, out)
        check("  ... reporting no gate rather than an 11-hour one",
              "none classified as a gate" in out, out)

    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        fire(repo, "Stop", transcript_path=transcript(repo, "Standing by."))
        fire(repo, "UserPromptSubmit", prompt="/cycle --exe")
        r = rows(repo)
        check("  ... while resuming one does not", r and r[0][5] == "resume", str(r))

    with tempfile.TemporaryDirectory() as tmp:
        # The unresolved category must land in neither total, not quietly in one.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        fire(repo, "Stop", transcript_path=transcript(repo, "Proceed to tasks?"))
        backdate(repo, 600)
        fire(repo, "UserPromptSubmit",
             prompt="Caveat: the messages below were generated by the user while running "
                    "local commands. DO NOT respond to these messages")
        r = rows(repo)
        check("a local-command wrapper is its own category", r and r[0][5] == "local-cmd", str(r))
        data = json.loads(subprocess.run(
            [sys.executable, str(REPORT), "--json"], cwd=repo,
            capture_output=True, text=True, timeout=30).stdout)
        check("  ... counted in neither human wait nor wakeups",
              data["local_commands"]["n"] == 1 and data["wakeups"]["n"] == 0
              and data["gates"] == 0, json.dumps(data)[:300])
        check("  ... and its 600s are in no total",
              data["wait_total_s"] == 0, str(data.get("wait_total_s")))
        check("  ... and the report says it is unresolved",
              "counted in neither" in report(repo), report(repo))

    with tempfile.TemporaryDirectory() as tmp:
        # A permission dialog blocks the cycle without ending the turn, so neither
        # Stop nor UserPromptSubmit fires. Fan-out 3's c1 stalled exactly here and
        # every record read as idle. PermissionRequest -> PostToolUse must close it.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        ask = {"tool_name": "Bash", "tool_input": {"command": "git push -u origin HEAD"}}

        fire(repo, "PermissionRequest", **ask)
        d = repo / "agent_states" / "permission-open"
        check("PermissionRequest leaves an open record", d.is_dir() and any(d.iterdir()))
        check("  ... and no row yet — an unanswered ask is not a completed wait",
              rows(repo) == [])

        out = report(repo)
        check("an unanswered permission ask is reported, not silent",
              "OPEN permission ask" in out and "never granted" in out, out)
        check("  ... naming the command that is blocked",
              "git push -u origin HEAD" in out, out)

        backdate_perm(repo, 900)
        fire(repo, "PostToolUse", **ask)
        r = rows(repo)
        check("the grant closes it into one row", len(r) == 1, str(r))
        check("  ... labelled permission, not a gate", r and r[0][5] == "permission", str(r))
        check("  ... with the measured wait", r and 895 <= int(r[0][2]) <= 910, str(r))
        check("  ... and the open record is cleared", not any(d.iterdir()))

        data = json.loads(subprocess.run(
            [sys.executable, str(REPORT), "--json"], cwd=repo,
            capture_output=True, text=True, timeout=30).stdout)
        check("  ... counted as a permission prompt",
              data["permissions"]["n"] == 1, json.dumps(data)[:300])
        check("  ... and NOT as gate wait, a wakeup, or a local command",
              data["gates"] == 0 and data["wait_total_s"] == 0
              and data["wakeups"]["n"] == 0 and data["local_commands"]["n"] == 0,
              json.dumps(data)[:300])
        check("  ... and the report says it blocked the cycle",
              "permission prompt(s) blocked the cycle" in report(repo), report(repo))

    with tempfile.TemporaryDirectory() as tmp:
        # The hook now runs on EVERY PostToolUse. The no-ask path is the common
        # case by orders of magnitude and must produce nothing at all.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        fire(repo, "PostToolUse", tool_name="Read", tool_input={"file_path": "/x"})
        check("a tool call with no preceding ask logs nothing", rows(repo) == [])
        check("  ... and creates no state", not (repo / "agent_states" / "permission-open").exists())

    with tempfile.TemporaryDirectory() as tmp:
        # The join is by tool name + input, so an unrelated call must not close
        # someone else's ask — that would invent a wait and delete a real stall.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        fire(repo, "PermissionRequest", tool_name="Bash",
             tool_input={"command": "git push -u origin HEAD"})
        fire(repo, "PostToolUse", tool_name="Bash", tool_input={"command": "git status"})
        check("an unrelated tool call does not close a pending ask", rows(repo) == [])
        check("  ... and the ask is still open",
              any((repo / "agent_states" / "permission-open").iterdir()))

    def load_attr(path, name):
        spec = importlib.util.spec_from_file_location(f"_a{abs(hash(path))}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, name)

    hd, rd = load_attr(HOOK, "PERM_DIR"), load_attr(REPORT, "PERM_DIR")
    check("hook and report agree on the open-permission directory", hd == rd,
          f"hook={hd!r} report={rd!r}")
    hlabel = load_attr(REPORT, "PERMISSION")
    check("  ... and on the row label", hlabel == "permission", repr(hlabel))


    # --- L5: a refused tool call leaves a trace -----------------------------
    #
    # Fan-out 7 reported "0 permission wait" while three tool calls had been
    # refused across two clones. None reached the log: `PostToolUse` does not
    # fire on a refusal, so the only record is the transcript.
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        tp = denial_transcript(repo, [
            ("t1", "ls /etc", "total 0"),
            ("t2", "rm -rf /tmp/x", DENIED),
            ("t3", "cat notes.md", "hello"),
        ])
        fire(repo, "SubagentStop", transcript_path=tp, agent_id="a1", agent_type="coding")
        got = [r for r in rows(repo) if r[5] == "denial"]
        check("a refused tool call is logged", len(got) == 1, str(rows(repo)))
        check("  ... with the refusal reason", "Auto-Mode Bypass" in got[0][8], str(got))
        check("  ... naming the actor", got[0][6] == "coding", str(got))
        check("  ... and the command", "rm -rf /tmp/x" in got[0][7], str(got))
        check("  ... with zero wait — nobody was asked anything", got[0][2] == "0", str(got))
        check("  ... and calls that were not refused are not logged",
              len([r for r in rows(repo) if r[5] == "denial"]) == 1, str(rows(repo)))

        # Firing again must not double-count: SubagentStop can fire more than once
        # for one agent, and a count that grows on re-read is worse than no count.
        fire(repo, "SubagentStop", transcript_path=tp, agent_id="a1", agent_type="coding")
        check("re-reading the same transcript logs nothing new",
              len([r for r in rows(repo) if r[5] == "denial"]) == 1, str(rows(repo)))

        # A later refusal in the same transcript is still picked up.
        with open(tp, "a") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t4", "name": "Bash",
                 "input": {"command": "curl example.com"}}]}}) + "\n")
            f.write(json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t4", "content": REJECTED}]}}) + "\n")
        fire(repo, "SubagentStop", transcript_path=tp, agent_id="a1", agent_type="coding")
        got = [r for r in rows(repo) if r[5] == "denial"]
        check("a new refusal after a re-read is logged", len(got) == 2, str(got))
        check("  ... including a user rejection, not only a classifier one",
              any("user-declined" in r[8] for r in got), str(got))
        # The fix differs by mechanism — a classifier refusal on a sanctioned
        # script wants a grant, a person declining wants nothing — so the two
        # must not both read "unspecified", which is what one cycle logged for
        # 11 of its 12 refusals.
        check("  ... and the two mechanisms are distinguishable",
              len({r[8] for r in got}) == 2, str({r[8] for r in got}))

    # Every refusal wording, not just the classifier's. Assuming one shape is how
    # the first cut of this scanner missed two of fan-out 7's three refusals.
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        tp = denial_transcript(repo, [
            ("w1", "rm -f /tmp/x.dart", DENY_RULE),
            ("w2", "curl example.com", REJECTED),
            ("w3", "deploy.sh check .", DENIED),
            ("w4", "echo fine", "fine"),
        ])
        fire(repo, "SubagentStop", transcript_path=tp, agent_id="a3", agent_type="coding")
        got = [r for r in rows(repo) if r[5] == "denial"]
        check("all three refusal wordings are caught", len(got) == 3, str(got))
        cmds = " ".join(r[7] for r in got)
        check("  ... including the deny-rule form", "rm -f /tmp/x.dart" in cmds, cmds)
        check("  ... and a successful call is still not one", "echo fine" not in cmds, cmds)

    # Two agents refused concurrently must not race each other's dedupe state.
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        for aid in ("a1", "a2"):
            tp = denial_transcript(repo, [(f"{aid}-x", f"cmd-{aid}", DENIED)])
            # each agent writes its own transcript path
            pathlib.Path(tp).rename(repo / f"d-{aid}.jsonl")
            fire(repo, "SubagentStop", transcript_path=str(repo / f"d-{aid}.jsonl"),
                 agent_id=aid, agent_type="test")
        got = [r for r in rows(repo) if r[5] == "denial"]
        check("two agents' refusals are both kept", len(got) == 2, str(got))

    # M18: many agents, ONE transcript. This is the shape the test above misses
    # by giving each agent its own file. `SubagentStop` hands back the *parent*
    # session's transcript_path, so under a fan-out every subagent rescans the
    # same transcript. Keyed per agent, each found the same refusal under a fresh
    # dedupe file and logged it again: round 9 wrote ten denial rows for two
    # events, one appearing seven times with only `phase` differing. The count
    # every round's headline is read from was inflated ~5x.
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        tp = denial_transcript(repo, [("s1", "rm agent_states/state.md", DENY_RULE)])
        fire(repo, "Stop", transcript_path=tp, agent_id="orchestrator")
        for aid, at in (("a1", "test"), ("a2", "review"), ("a3", "Explore"),
                        ("a4", "coding"), ("a5", "verify"), ("a6", "generate-tasks")):
            fire(repo, "SubagentStop", transcript_path=tp, agent_id=aid, agent_type=at)
        got = [r for r in rows(repo) if r[5] == "denial"]
        check("one refusal in a shared transcript is logged once, not once per agent",
              len(got) == 1, f"{len(got)} rows: {got}")
        check("  ... attributed to the agent that actually hit it",
              got[0][6] == "orchestrator", str(got))
        check("  ... and the claim store holds one entry, not one per agent",
              sum(len(files) for _, _, files in
                  os.walk(repo / "agent_states" / "denial-seen")) == 1,
              str(list(os.walk(repo / "agent_states" / "denial-seen"))))

        # A second, genuinely new refusal in the same shared transcript still lands.
        with open(tp, "a") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "s2", "name": "Bash",
                 "input": {"command": "rmdir test/integration"}}]}}) + "\n")
            f.write(json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "s2", "content": DENY_RULE}]}}) + "\n")
        for aid in ("a1", "a2", "a3"):
            fire(repo, "SubagentStop", transcript_path=tp, agent_id=aid, agent_type="test")
        got = [r for r in rows(repo) if r[5] == "denial"]
        check("a new refusal in the shared transcript is still caught once",
              len(got) == 2, f"{len(got)} rows: {got}")

    # Order must not decide the actor. Here a subagent stops FIRST and claims the
    # refusal; without a recorded session transcript the row would read "test".
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        tp = denial_transcript(repo, [("o1", "rm agent_states/state.md", DENY_RULE)])
        # the main loop has been through at least one prompt before any subagent
        fire(repo, "UserPromptSubmit", transcript_path=tp, prompt="/cycle 421 --mode lean")
        fire(repo, "SubagentStop", transcript_path=tp, agent_id="a1", agent_type="test")
        got = [r for r in rows(repo) if r[5] == "denial"]
        check("a subagent claiming first does not steal the attribution",
              len(got) == 1 and got[0][6] == "orchestrator", str(got))

    # And with no session note at all, the payload's own claim still stands —
    # unknown must fall back, never assert.
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        tp = denial_transcript(repo, [("p1", "curl example.com", REJECTED)])
        fire(repo, "SubagentStop", transcript_path=tp, agent_id="a7", agent_type="review")
        got = [r for r in rows(repo) if r[5] == "denial"]
        check("with no session note the payload's actor is kept",
              len(got) == 1 and got[0][6] == "review", str(got))

    # The under-count, which is the worse half. `SubagentStop` names the PARENT
    # transcript, but a subagent's tool calls live at
    # `<parent stem>/subagents/agent-<agent_id>.jsonl`. Round 9 logged 2 of its
    # 6 refusals: the four inside coding/test/review were never read at all.
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        # the helper reuses one path, so build the subagent's copy first
        subdir = repo / "d" / "subagents"
        subdir.mkdir(parents=True)
        own = denial_transcript(repo, [("m2", "rm test/probe_test.dart", DENY_RULE)])
        pathlib.Path(own).rename(subdir / "agent-a42.jsonl")
        parent = denial_transcript(repo, [("m1", "rm agent_states/x.md", DENY_RULE)])

        fire(repo, "UserPromptSubmit", transcript_path=parent, prompt="/cycle 480")
        fire(repo, "SubagentStop", transcript_path=parent, agent_id="a42", agent_type="coding")
        got = [r for r in rows(repo) if r[5] == "denial"]
        check("a refusal inside a subagent's own transcript is found",
              len(got) == 2, f"{len(got)} rows: {got}")
        by = {r[6]: r[7] for r in got}
        check("  ... attributed to the subagent", "probe_test.dart" in by.get("coding", ""), str(got))
        check("  ... while the parent's stays the orchestrator's",
              "agent_states/x.md" in by.get("orchestrator", ""), str(got))

        # Re-firing must not double either of them.
        fire(repo, "SubagentStop", transcript_path=parent, agent_id="a42", agent_type="coding")
        check("  ... and neither doubles on a re-read",
              len([r for r in rows(repo) if r[5] == "denial"]) == 2, str(rows(repo)))

    # A missing subagent transcript is silence, not an error: harness layouts
    # differ, and a guess must never cost the parent's refusal.
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        tp = denial_transcript(repo, [("n1", "rm x", DENY_RULE)])
        fire(repo, "UserPromptSubmit", transcript_path=tp, prompt="/cycle 1")
        fire(repo, "SubagentStop", transcript_path=tp, agent_id="nope", agent_type="test")
        check("no subagent transcript still logs the parent's refusal",
              len([r for r in rows(repo) if r[5] == "denial"]) == 1, str(rows(repo)))

    # Two different transcripts that happen to reuse a tool_use_id are two events.
    # Clone reuse makes id collisions across runs plausible, and losing a real
    # refusal is the failure this scanner exists to prevent.
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        for n_ in ("one", "two"):
            tp = denial_transcript(repo, [("dup", f"cmd-{n_}", DENIED)])
            pathlib.Path(tp).rename(repo / f"t-{n_}.jsonl")
            fire(repo, "SubagentStop", transcript_path=str(repo / f"t-{n_}.jsonl"),
                 agent_id="a1", agent_type="coding")
        got = [r for r in rows(repo) if r[5] == "denial"]
        check("the same id in two transcripts counts twice", len(got) == 2, str(got))

    # --- the report must never fold a refusal into a wait figure ------------
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        tp = denial_transcript(repo, [("z1", "sudo rm -rf /", DENIED)])
        fire(repo, "SubagentStop", transcript_path=tp, agent_id="a9", agent_type="verify")
        out = report(repo)
        check("the report names the refusal count", "1 tool call(s) refused" in out, out)
        check("  ... and says why it was invisible", "PostToolUse" in out, out)
        check("  ... attributing it to an actor", "verify 1" in out, out)
        check("  ... and does not call it a permission ask",
              "OPEN permission ask" not in out, out)
        check("  ... nor a gate", "1 gate(s)" not in out, out)

        data = json.loads(report(repo, "--json"))
        check("json counts refusals apart", data.get("denial_count") == 1, report(repo, "--json"))
        check("  ... and they are absent from the gate rows",
              all(g.get("gate") != "denial" for g in data.get("gates", []) or []),
              report(repo, "--json"))

    if FAILURES:
        print("\nFAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\ngate-log: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
