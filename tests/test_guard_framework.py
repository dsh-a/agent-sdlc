"""Tests for .claude/hooks/guard-framework.py.

A blocking hook has two failure modes and they are not symmetric. Missing a
framework write lets a cycle change what its siblings are running, uncommitted,
mid-round — the fan-out 8 finding. Blocking ordinary work stalls a cycle for
hours, which is the failure this whole line of work exists to remove.

So the false-positive cases below matter at least as much as the true ones, and
the largest of them has its own section: reading the framework must stay free.

    python3 tests/test_guard_framework.py
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/guard-framework.py"

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def fire(cwd: pathlib.Path, tool: str, **inp) -> tuple[int, str]:
    payload = {"tool_name": tool, "tool_input": inp, "cwd": str(cwd)}
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=20)
    return p.returncode, p.stderr


def blocked(cwd: pathlib.Path, tool: str, **inp) -> bool:
    return fire(cwd, tool, **inp)[0] == 2


tmp = tempfile.TemporaryDirectory()
R = pathlib.Path(tmp.name).resolve()

# A framework and a project deployed from it, shaped like the real thing: the
# project reaches the framework through a symlinked skill directory, which is
# how the hook finds it at all.
FW = R / "agent-sdlc"
(FW / ".claude/skills/cycle").mkdir(parents=True)
(FW / ".claude/agents").mkdir(parents=True)
(FW / ".claude/packs/flutter").mkdir(parents=True)
(FW / ".claude/agents/coding.md").write_text("tools: Read\n")
(FW / ".claude/skills/cycle/SKILL.md").write_text("skill\n")

PROJ = R / "clone"
(PROJ / ".claude/skills").mkdir(parents=True)
(PROJ / "lib").mkdir()
os.symlink(FW / ".claude/skills/cycle", PROJ / ".claude/skills/cycle")
os.symlink(FW / ".claude/packs", PROJ / ".claude/packs")
(PROJ / "lib/app.dart").write_text("void main() {}\n")

AGENT = str(FW / ".claude/agents/coding.md")

# ---------------------------------------------------------------- it blocks
#
# The fan-out 8 command, verbatim in shape: sed a grant into an agent definition.
check("sed into an agent definition is blocked",
      blocked(PROJ, "Bash", command=f"sed -i '' 's/a/b/' {AGENT}"))
check("  ... and the Edit tool route too, which no Bash deny covers",
      blocked(PROJ, "Edit", file_path=AGENT, old_string="a", new_string="b"))
check("  ... and Write", blocked(PROJ, "Write", file_path=AGENT, content="x"))
check("  ... and a redirect, whatever the verb before it",
      blocked(PROJ, "Bash", command=f"echo tools: > {AGENT}"))
check("  ... and a redirect appended",
      blocked(PROJ, "Bash", command=f"printf 'x' >> {AGENT}"))
check("  ... and cp over it", blocked(PROJ, "Bash", command=f"cp /tmp/x {AGENT}"))
check("  ... and a python one-liner writing it",
      blocked(PROJ, "Bash", command=f"python3 -c \"open('{AGENT}','w')\""))
check("  ... reached through the skills symlink rather than the real path",
      blocked(PROJ, "Write", file_path=str(PROJ / ".claude/skills/cycle/SKILL.md"), content="x"))
check("  ... by a relative path, resolved against the agent's cwd not the hook's",
      blocked(PROJ, "Bash", command="sed -i '' 's/a/b/' .claude/skills/cycle/SKILL.md"))
check("  ... and a relative Edit",
      blocked(PROJ, "Edit", file_path=".claude/skills/cycle/SKILL.md",
              old_string="a", new_string="b"))
check("  ... and chained behind a granted command",
      blocked(PROJ, "Bash", command=f"git status --short && sed -i '' 's/a/b/' {AGENT}"))

# The live deployment puts agent definitions at user scope, where ~/.claude/agents
# is itself a symlink into the framework. That is the route fan-out 8 would take
# today, since a clone has no .claude/agents of its own.
USERSCOPE = R / "home/.claude"
(USERSCOPE).mkdir(parents=True)
os.symlink(FW / ".claude/agents", USERSCOPE / "agents")
check("a write through the user-scope agents symlink is blocked",
      blocked(PROJ, "Write", file_path=str(USERSCOPE / "agents/coding.md"), content="x"))
check("  ... and reading through it is still allowed",
      not blocked(PROJ, "Bash", command=f"cat {USERSCOPE}/agents/coding.md"))

rc, err = fire(PROJ, "Edit", file_path=AGENT, old_string="a", new_string="b")
check("the refusal says why it is not answerable by approval",
      "not answerable by approval" in err, err[:200])
check("  ... and names the path it protected", str(FW) in err, err[:200])
check("  ... and tells the agent what to do instead",
      "Harness findings" in err, err[:200])

# ------------------------------------------------------- it does not block
#
# The big one: an agent reading its own definition is how it learns what it is
# for. A guard that blocked this would break every cycle.
check("reading an agent definition is allowed",
      not blocked(PROJ, "Bash", command=f"grep -n '^tools:' {AGENT}"))
check("  ... with cat", not blocked(PROJ, "Bash", command=f"cat {AGENT}"))
check("  ... with the Read tool", not blocked(PROJ, "Read", file_path=AGENT))
check("  ... and listing the directory",
      not blocked(PROJ, "Bash", command=f"ls -la {FW}/.claude/agents/"))
check("  ... and diffing against it",
      not blocked(PROJ, "Bash", command=f"diff -q {AGENT} {AGENT}"))

# Running the framework's own tooling is a read, and the suite did not say so.
# Round 9 blocked `python3 .claude/skills/cycle/aggregate-telemetry.py` 21 times
# across four cycles: `python3` is in WRITERS, so word-splitting handed back the
# script itself as a write target. Every block landed in Phase 4B, so telemetry
# was never aggregated and agent_states never cleared in any cycle. The rule was
# right; this case was missing.
check("running a framework script is allowed",
      not blocked(PROJ, "Bash", command="python3 .claude/skills/cycle/aggregate-telemetry.py"))
check("  ... with arguments",
      not blocked(PROJ, "Bash", command="python3 .claude/skills/cycle/clear-agent-states.py --all"))
check("  ... by absolute path",
      not blocked(PROJ, "Bash", command=f"python3 {FW}/.claude/skills/cycle/gate-report.py"))
check("  ... with bash, which only escaped by accident",
      not blocked(PROJ, "Bash", command="bash .claude/skills/cycle/run-suite.sh log x"))
check("  ... piped, as the orchestrator actually invokes it",
      not blocked(PROJ, "Bash", command="bash .claude/skills/cycle/run-suite.sh log m 2>&1 | tail -30"))

# The exemption is for executing a script, and must not become a way to write
# one. These are the cases that would make the fix a hole.
check("a python one-liner writing the framework is still blocked",
      blocked(PROJ, "Bash", command=f"python3 -c \"open('{AGENT}','w')\""))
check("  ... via a relative path through the clone's symlink",
      blocked(PROJ, "Bash", command="python3 -c \"open('.claude/skills/cycle/SKILL.md','w')\""))
check("  ... and -m with a framework target is not a script argument",
      blocked(PROJ, "Bash", command=f"python3 -m pip install --target {FW}/.claude"))
check("  ... nor is a redirect past an exempt script",
      blocked(PROJ, "Bash", command=f"python3 .claude/skills/cycle/gate-report.py > {AGENT}"))
check("  ... and sh -c carrying a sed still blocks",
      blocked(PROJ, "Bash", command=f"sh -c \"sed -i '' s/a/b/ {AGENT}\""))
check("  ... copying over a framework script is not 'running' it",
      blocked(PROJ, "Bash", command=f"cp /tmp/evil.py {FW}/.claude/skills/cycle/gate-report.py"))

# A stream editor only writes with -i. Round 10 blocked
# `sed -n '1,200p' <framework>/skills/harness-findings/SKILL.md` — a read, and the
# agent had to re-read the file with the Read tool. #31's exemption does not reach
# these because they are writers, not interpreters.
check("sed -n is a read, not a write",
      not blocked(PROJ, "Bash", command=f"sed -n '1,200p' {AGENT}"))
check("  ... unquoted range too",
      not blocked(PROJ, "Bash", command=f"sed -n 1,50p {AGENT}"))
check("  ... and awk reading an agent definition",
      not blocked(PROJ, "Bash", command=f"awk '/tools:/{{print}}' {AGENT}"))
check("  ... but sed -i still writes", blocked(PROJ, "Bash", command=f"sed -i '' 's/a/b/' {AGENT}"))
check("  ... and --in-place", blocked(PROJ, "Bash", command=f"sed --in-place 's/a/b/' {AGENT}"))
check("  ... and -i with a backup suffix",
      blocked(PROJ, "Bash", command=f"sed -i.bak 's/a/b/' {AGENT}"))

# A heredoc body is data. c2 was blocked appending its run report, because the
# report quoted the command that had just been refused and the quoted prose split
# into a segment whose head was `sed`. guard-secrets.py learned this when its
# first version blocked a commit message discussing ~/.ssh/id_rsa; the lesson was
# never ported here.
REPORT = str(PROJ / "report.md")
check("prose in a heredoc naming a framework path is not a write",
      not blocked(PROJ, "Bash", command=(
          f"cat >> {REPORT} << 'EOF'\n"
          f"## Harness findings\n"
          f"- Tried: `sed -n '1,200p' {AGENT}`; refused as a write. False positive.\n"
          f"EOF")))
check("  ... nor is a commit message that names one",
      not blocked(PROJ, "Bash", command=(
          f"git commit -m 'note: {AGENT} needs a grant; reported, not edited'")))

# A program that writes *about* a framework path is not writing to one. Round 10
# blocked two agents whose Python assembled a run report whose text quoted
# `aggregate-telemetry.py`. A path in a program counts only on a line that also
# does something write-shaped.
check("a program whose text quotes a framework path is not a write",
      not blocked(PROJ, "Bash", command=(
          "python3 - << 'EOF'\n"
          "p = 'agent_tasks/reports/r.md'\n"
          "s = open(p).read()\n"
          'tele = """## Telemetry\n'
          "Output of `python3 .claude/skills/cycle/aggregate-telemetry.py`, collected at 4B.\n"
          '"""\n'
          "open(p, 'w').write(s + tele)\n"
          "EOF")))

# ... but an interpreter's heredoc IS a program, and stripping it would be a hole.
check("a python heredoc writing the framework is still blocked",
      blocked(PROJ, "Bash", command=(
          f"python3 - << 'EOF'\nopen('{AGENT}','w')\nEOF")))
check("  ... and tee into the framework, whose body is data but whose target is not",
      blocked(PROJ, "Bash", command=f"tee {AGENT} << 'EOF'\nevil\nEOF"))

# Ordinary project work must be untouched — this is the stall-a-cycle risk.
check("writing project source is allowed",
      not blocked(PROJ, "Write", file_path=str(PROJ / "lib/app.dart"), content="x"))
check("  ... editing it", not blocked(PROJ, "Edit", file_path=str(PROJ / "lib/app.dart"),
                                      old_string="a", new_string="b"))
check("  ... sed against it",
      not blocked(PROJ, "Bash", command=f"sed -i '' 's/a/b/' {PROJ}/lib/app.dart"))
check("  ... committing", not blocked(PROJ, "Bash", command="git add -A && git commit -m x"))
check("  ... running the suite",
      not blocked(PROJ, "Bash", command="flutter test test/widget/foo_test.dart"))
check("  ... and formatting, the command that started all this",
      not blocked(PROJ, "Bash", command="dart format ."))

# Running a framework script is a read — and so are the arguments handed to it.
# Only the script path was exempt, so `evidence.py absence --pattern 'rm -rf'
# <framework path>` was blocked: the write-hint regex matched `rm` inside the
# *search pattern*, and the path scan then picked up the corpus argument.
# Auditing the framework for write operations is exactly what that verb is for.
(FW / ".claude/skills/evidence").mkdir(parents=True, exist_ok=True)
(FW / ".claude/skills/evidence/evidence.py").write_text("script\n")
os.symlink(FW / ".claude/skills/evidence", PROJ / ".claude/skills/evidence")
check("a framework script may be handed a framework path to read",
      not blocked(PROJ, "Bash",
                  command="python3 .claude/skills/evidence/evidence.py absence "
                          "--pattern 'rm -rf' .claude/skills/cycle"))
check("  ... even when the pattern names a redirect",
      not blocked(PROJ, "Bash",
                  command="python3 .claude/skills/evidence/evidence.py absence "
                          "--pattern '> out' .claude/skills/cycle"))
check("  ... while writing over that same script still blocks",
      blocked(PROJ, "Bash", command="cp /tmp/x .claude/skills/evidence/evidence.py"))
check("  ... and a real interpreter write is untouched",
      blocked(PROJ, "Bash",
              command="python3 -c \"open('.claude/skills/cycle/SKILL.md','w')\""))

# Working on the framework itself is not a cycle editing its instrument.
check("editing the framework from inside the framework is allowed",
      not blocked(FW, "Edit", file_path=AGENT, old_string="a", new_string="b"))
check("  ... including with sed",
      not blocked(FW, "Bash", command=f"sed -i '' 's/a/b/' {AGENT}"))

# A project that is not a deployment has no framework to protect, and the hook
# must be inert rather than guessing at one.
PLAIN = R / "plain"
(PLAIN / "lib").mkdir(parents=True)
check("a non-deployment is left alone",
      not blocked(PLAIN, "Write", file_path=str(PLAIN / "lib/x.dart"), content="x"))

# ---------------------------------------------------------------- failure
#
# Every failure of this script exits 0. A guard that crashes must not stop a
# cycle, which is the same contract guard-secrets.py holds.
p = subprocess.run([sys.executable, str(HOOK)], input="not json",
                   capture_output=True, text=True, timeout=20)
check("garbage input exits 0", p.returncode == 0, p.stderr[:120])
p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_name": "Bash"}),
                   capture_output=True, text=True, timeout=20)
check("a payload with no cwd or input exits 0", p.returncode == 0, p.stderr[:120])
check("an unknown tool is not blocked",
      not blocked(PROJ, "WebFetch", url="https://example.com"))

tmp.cleanup()

print()
if FAILURES:
    print(f"{len(FAILURES)} failed:")
    for f in FAILURES:
        print("  " + f)
    sys.exit(1)
print("all guard-framework tests passed")
