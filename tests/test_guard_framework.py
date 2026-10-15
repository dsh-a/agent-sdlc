"""Tests for .claude/hooks/guard-framework.py.

A blocking hook has two failure modes and they are not symmetric. Missing a
framework write lets a cycle change what its siblings are running, uncommitted,
mid-round. Blocking ordinary work stalls a cycle for hours.

So the false-positive cases below matter at least as much as the true ones, and
the largest of them has its own section: reading the framework must stay free.

    python3 tests/test_guard_framework.py
"""

from __future__ import annotations

import importlib.util
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

# Forward slashes: these strings go into Bash commands, and bash reads an
# unquoted `C:\Users\x` as `C:Usersx`. `as_posix()` is the identity off Windows
# and `C:/Users/...` on it — the form a Windows agent actually types. The
# backslash and `/c/...` forms get their own section below.
AGENT = (FW / ".claude/agents/coding.md").as_posix()

# ---------------------------------------------------------------- it blocks
#
# sed a grant into an agent definition.
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
# is itself a symlink into the framework. That is the route an agent-definition
# edit takes, since a clone has no .claude/agents of its own.
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
check("  ... stating the rule, not an incident", "Fan-out" not in err, err[:200])
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
      not blocked(PROJ, "Bash", command=f"ls -la {FW.as_posix()}/.claude/agents/"))
check("  ... and diffing against it",
      not blocked(PROJ, "Bash", command=f"diff -q {AGENT} {AGENT}"))

# Running the framework's own tooling is a read. `python3` is in WRITERS, so
# word-splitting hands back the script itself as a write target; blocking it
# stops Phase 4B from aggregating telemetry and clearing agent_states.
check("running a framework script is allowed",
      not blocked(PROJ, "Bash", command="python3 .claude/skills/cycle/aggregate-telemetry.py"))
check("  ... with arguments",
      not blocked(PROJ, "Bash", command="python3 .claude/skills/cycle/clear-agent-states.py --all"))
check("  ... by absolute path",
      not blocked(PROJ, "Bash", command=f"python3 {FW.as_posix()}/.claude/skills/cycle/gate-report.py"))
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
      blocked(PROJ, "Bash", command=f"python3 -m pip install --target {FW.as_posix()}/.claude"))
check("  ... nor is a redirect past an exempt script",
      blocked(PROJ, "Bash", command=f"python3 .claude/skills/cycle/gate-report.py > {AGENT}"))
check("  ... and sh -c carrying a sed still blocks",
      blocked(PROJ, "Bash", command=f"sh -c \"sed -i '' s/a/b/ {AGENT}\""))
check("  ... copying over a framework script is not 'running' it",
      blocked(PROJ, "Bash", command=f"cp /tmp/evil.py {FW.as_posix()}/.claude/skills/cycle/gate-report.py"))

# A stream editor only writes with -i: `sed -n '1,200p' <framework>/...` is a
# read. The interpreter exemption does not reach these because they are writers,
# not interpreters.
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

# A program that writes *about* a framework path is not writing to one, such as
# Python assembling a run report whose text quotes `aggregate-telemetry.py`. A
# path in a program counts only on a line that also does something write-shaped.
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
      not blocked(PROJ, "Bash", command=f"sed -i '' 's/a/b/' {PROJ.as_posix()}/lib/app.dart"))
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

# ------------------------------------------------- Windows command names
#
# A command is matched by name whatever spelling the shell accepts for it:
# `.exe`, `.cmd` and `.bat` suffixes, any case, a directory prefix in either
# separator, and the launchers `py` and `powershell`. Pure string work, so these
# run on every host.
check("python.exe writing the framework is blocked",
      blocked(PROJ, "Bash", command=f"python.exe -c \"open('{AGENT}','w').write('x')\""))
check("  ... and py, the python.org launcher",
      blocked(PROJ, "Bash", command=f"py -c \"open('{AGENT}','w').write('x')\""))
check("  ... and py -3",
      blocked(PROJ, "Bash", command=f"py -3 -c \"open('{AGENT}','w').write('x')\""))
check("  ... and an upper-case, directory-qualified PYTHON.EXE",
      blocked(PROJ, "Bash",
              command=f"'C:\\Python312\\PYTHON.EXE' -c \"open('{AGENT}','w').write('x')\""))
check("  ... and pwsh",
      blocked(PROJ, "Bash", command=f"pwsh -c \"Copy-Item x {AGENT}; rm {AGENT}\""))
check("  ... and powershell",
      blocked(PROJ, "Bash", command=f"powershell -c \"rm {AGENT}\""))
check("sed.exe -i into an agent definition is blocked",
      blocked(PROJ, "Bash", command=f"sed.exe -i s/a/b/ {AGENT}"))
check("  ... and cp.exe over it", blocked(PROJ, "Bash", command=f"cp.exe /tmp/x {AGENT}"))
check("  ... and a .cmd wrapper", blocked(PROJ, "Bash", command=f"cp.cmd /tmp/x {AGENT}"))
check("  ... and a .bat wrapper", blocked(PROJ, "Bash", command=f"tee.bat {AGENT}"))
check("a python.exe heredoc writing the framework is still blocked",
      blocked(PROJ, "Bash", command=f"python.exe - << 'EOF'\nopen('{AGENT}','w')\nEOF"))
check("sed.exe -n is still a read",
      not blocked(PROJ, "Bash", command=f"sed.exe -n 1,50p {AGENT}"))
check("py running a framework script is allowed",
      not blocked(PROJ, "Bash", command="py .claude/skills/cycle/aggregate-telemetry.py"))
check("  ... and env python.exe running one",
      not blocked(PROJ, "Bash",
                  command="env python.exe .claude/skills/cycle/aggregate-telemetry.py"))
check("a versioned python3.12 writing the framework is blocked",
      blocked(PROJ, "Bash", command=f"python3.12 -c \"open('{AGENT}','w')\""))
check("  ... and python3.12.exe",
      blocked(PROJ, "Bash", command=f"python3.12.exe -c \"open('{AGENT}','w')\""))
check("  ... and ruby3.2",
      blocked(PROJ, "Bash", command=f"ruby3.2 -e \"File.write('{AGENT}','x')\""))
check("  ... and node20",
      blocked(PROJ, "Bash", command=f"node20 -e \"require('fs').write('{AGENT}')\""))

# PowerShell and cmd write with their own verbs. The cmdlet names count in any
# case; the short aliases and cmd's verbs are ordinary words, so they count only
# under a pwsh or cmd head.
for verb in ("Set-Content {a} x", "set-content -Path {a} -Value x", "Add-Content {a} x",
             "'x' | Out-File {a}", "Copy-Item x {a}", "Move-Item x {a}",
             "Remove-Item {a}", "New-Item {a}"):
    check(f"pwsh {verb.format(a='<fw>')} is blocked",
          blocked(PROJ, "Bash", command=f"powershell.exe -Command \"{verb.format(a=AGENT)}\""))
for verb in ("sc {a} x", "ac {a} x", "cpi x {a}", "mi x {a}", "ri {a}", "ni {a}",
             "del {a}", "copy x {a}", "move x {a}"):
    check(f"pwsh alias: {verb.format(a='<fw>')} is blocked",
          blocked(PROJ, "Bash", command=f"pwsh -c \"{verb.format(a=AGENT)}\""))
check("cmd /c copy into the framework is blocked",
      blocked(PROJ, "Bash", command=f"cmd /c copy x {AGENT}"))
check("  ... and cmd.exe /c del",
      blocked(PROJ, "Bash", command=f"cmd.exe /c del {AGENT}"))
check("pwsh reading the framework is allowed",
      not blocked(PROJ, "Bash", command=f"pwsh -c \"Get-Content {AGENT}\""))
check("  ... and cmd /c type", not blocked(PROJ, "Bash", command=f"cmd /c type {AGENT}"))
check("a python program whose text says copy, move or del is not a write",
      not blocked(PROJ, "Bash",
                  command=f"python3 -c \"print('copy {AGENT}, move on, del later')\""))

# ------------------------------------------------- perl, ruby and node writes
#
# perl and ruby edit in place with -i, alone or in any short-flag cluster; node
# writes through its fs methods. Each reads with the same interpreter, and those
# reads stay free.
for flags in ("-i -pe s/a/b/", "-pi -e s/a/b/", "-i.bak -pe s/a/b/", "-pi.bak -e s/a/b/",
              "-0777 -pi -e s/a/b/", "-pie s/a/b/", "-i -n -e print"):
    check(f"perl {flags} <fw> is blocked",
          blocked(PROJ, "Bash", command=f"perl {flags} {AGENT}"))
check("  ... and perl5.36 -pi", blocked(PROJ, "Bash", command=f"perl5.36 -pi -e s/a/b/ {AGENT}"))
check("  ... and env perl -pi", blocked(PROJ, "Bash", command=f"env perl -pi -e s/a/b/ {AGENT}"))
check("  ... and a relative path through the clone's symlink",
      blocked(PROJ, "Bash", command="perl -pi -e s/a/b/ .claude/skills/cycle/SKILL.md"))
check("  ... and a framework script edited in place, not run",
      blocked(PROJ, "Bash", command="perl -pi -e s/a/b/ .claude/skills/cycle/x.pl"))
check("  ... and the files after a script that edits them",
      blocked(PROJ, "Bash", command=f"perl -i /tmp/edit.pl {AGENT}"))
check("  ... and inside sh -c",
      blocked(PROJ, "Bash", command=f"sh -c \"perl -pi -e s/a/b/ {AGENT}\""))
check("ruby -pi into the framework is blocked",
      blocked(PROJ, "Bash", command=f"ruby -pi -e 'sub(/a/, \"b\")' {AGENT}"))
check("  ... and ruby -i.bak", blocked(PROJ, "Bash", command=f"ruby -i.bak -pe 1 {AGENT}"))

for call in ("writeFileSync('{a}', 'x')", "appendFileSync('{a}', 'x')",
             "writeFile('{a}', 'x', console.log)", "createWriteStream('{a}')",
             "rmSync('{a}')", "rm('{a}', console.log)", "unlinkSync('{a}')",
             "unlink('{a}', console.log)", "renameSync('/tmp/x', '{a}')",
             "rename('/tmp/x', '{a}', console.log)", "copyFileSync('/tmp/x', '{a}')",
             "copyFile('/tmp/x', '{a}', console.log)", "openSync('{a}', 'w')"):
    check(f"node -e fs.{call.format(a='<fw>')} is blocked",
          blocked(PROJ, "Bash", command=f"node -e \"require('fs').{call.format(a=AGENT)}\""))
check("  ... and fs/promises",
      blocked(PROJ, "Bash",
              command=f"node -e \"require('fs/promises').writeFile('{AGENT}', 'x')\""))
check("  ... and fs.promises.rm",
      blocked(PROJ, "Bash", command=f"node -e \"require('fs').promises.rm('{AGENT}')\""))
check("  ... and node:fs/promises unlink",
      blocked(PROJ, "Bash",
              command=f"node --eval \"import('node:fs/promises').then(function (f) {{ return f.unlink('{AGENT}') }})\""))
check("  ... and node -p",
      blocked(PROJ, "Bash", command=f"node -p \"require('fs').writeFileSync('{AGENT}', 'x')\""))
check("  ... and a relative path through the clone's symlink",
      blocked(PROJ, "Bash",
              command="node -e \"require('fs').writeFileSync('.claude/skills/cycle/SKILL.md', 'x')\""))

check("perl -ne print reading the framework is allowed",
      not blocked(PROJ, "Bash", command=f"perl -ne print {AGENT}"))
check("  ... and perl -lne", not blocked(PROJ, "Bash", command=f"perl -lne 'print if /tools/' {AGENT}"))
check("  ... and a perl open for reading",
      not blocked(PROJ, "Bash",
                  command=f"perl -e 'open(F, \"<\", \"{AGENT}\"); print while <F>'"))
check("  ... and perl -I with a directory holding an i",
      not blocked(PROJ, "Bash", command=f"perl -I/tmp/lib -ne print {AGENT}"))
check("  ... and perl -Mstrict, whose module name holds an i",
      not blocked(PROJ, "Bash", command=f"perl -Mstrict -ne print {AGENT}"))
check("  ... and ruby -ne", not blocked(PROJ, "Bash", command=f"ruby -ne 'puts $_' {AGENT}"))
check("  ... and ruby -rjson, whose library name holds no in-place flag",
      not blocked(PROJ, "Bash", command=f"ruby -rjson -ne 'puts $_' {AGENT}"))
check("node -e readFileSync on the framework is allowed",
      not blocked(PROJ, "Bash",
                  command=f"node -e \"console.log(require('fs').readFileSync('{AGENT}', 'utf8'))\""))
check("  ... and fs/promises readFile",
      not blocked(PROJ, "Bash",
                  command=f"node -e \"require('fs/promises').readFile('{AGENT}').then(console.log)\""))
check("running a framework script with node is allowed",
      not blocked(PROJ, "Bash", command="node .claude/skills/cycle/report.js --out /tmp/r.md"))
check("  ... and with perl",
      not blocked(PROJ, "Bash", command=f"perl {FW.as_posix()}/.claude/skills/cycle/report.pl x"))
check("perl -pi on project source is allowed",
      not blocked(PROJ, "Bash", command=f"perl -pi -e s/a/b/ {PROJ.as_posix()}/lib/app.dart"))
check("  ... and node writing project source",
      not blocked(PROJ, "Bash",
                  command=f"node -e \"require('fs').writeFileSync('{PROJ.as_posix()}/lib/app.dart', 'x')\""))

# ------------------------------------------------- Windows, on any host
#
# The Windows rules are named variants in lib/guard_match.py beside the POSIX
# ones, so their string work runs here on every host. The guards are loaded in
# process to show they use the shared objects and, given the Windows variant,
# pick out Windows paths.
sys.path.insert(0, str(HOOK.parent / "lib"))
import guard_match as gm  # noqa: E402


def load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gf = load(HOOK, "guard_framework")
gs = load(HOOK.parent / "guard-secrets.py", "guard_secrets")
check("both guards use the shared native() and command_name()",
      gf.native is gm.native is gs.native
      and gf.command_name is gm.command_name is gs.command_name)
check("guard-framework uses the shared PATHISH", gf.PATHISH is gm.PATHISH)
check("the host picks the variant",
      gm.PATHISH is (gm.PATHISH_WINDOWS if os.name == "nt" else gm.PATHISH_POSIX))

for given, want in (("/c/dev/x", "C:/dev/x"), ("/c", "C:/"), ("/C/Users/x", "C:/Users/x"),
                    ("/d/", "D:/"), ("//srv/share/x", "//srv/share/x"), ("/tmp/x", "/tmp/x"),
                    ("/cygdrive/c/x", "/cygdrive/c/x"), ("C:\\Users\\x", "C:\\Users\\x"),
                    ("rel/x", "rel/x"), (None, None)):
    check(f"windows: msys_to_native({given!r}) is {want!r}", gm.msys_to_native(given) == want,
          repr(gm.msys_to_native(given)))
check("native() converts only on Windows",
      gm.native("/c/dev/x") == ("C:/dev/x" if os.name == "nt" else "/c/dev/x"))

PROG = "open('C:\\\\dev\\\\fw\\\\.claude\\\\agents\\\\coding.md','w')"
check("windows: PATHISH finds a backslash path in a program",
      "C:\\\\dev\\\\fw\\\\.claude\\\\agents\\\\coding.md"
      in [m.group(0) for m in gm.PATHISH_WINDOWS.finditer(PROG)])
check("  ... and a forward-slash drive path",
      [m.group(0) for m in gm.PATHISH_WINDOWS.finditer("open('C:/dev/x.md','w')")] == ["C:/dev/x.md"])
check("  ... which the POSIX form does not",
      "C:/dev/x.md" not in [m.group(0) for m in gm.PATHISH_POSIX.finditer("open('C:/dev/x.md','w')")])
gf.PATHISH = gm.PATHISH_WINDOWS
try:
    check("windows: bash_targets hands a backslash path in a python write to the resolver",
          "C:\\\\dev\\\\fw\\\\.claude\\\\agents\\\\coding.md"
          in gf.bash_targets(f"python3 -c \"{PROG}\""))
finally:
    gf.PATHISH = gm.PATHISH

# ---------------------------------------------------------------- Windows
#
# Native Windows Python reads Git Bash's `/c/dev/x` as `C:\c\dev\x`, so the
# guard normalises MSYS-form paths and cwds; unnormalised, it fails open,
# silently. These resolve through ntpath, so they run on Windows only.
if os.name == "nt":
    def msys(p: pathlib.Path) -> str:
        s = p.as_posix()
        return "/" + s[0].lower() + s[2:]

    AGENT_MSYS = msys(FW / ".claude/agents/coding.md")
    AGENT_BS = str(FW / ".claude/agents/coding.md")
    check("windows: an MSYS-form path is blocked",
          blocked(PROJ, "Bash", command=f"sed -i 's/a/b/' {AGENT_MSYS}"))
    check("  ... through a redirect",
          blocked(PROJ, "Bash", command=f"echo x > {AGENT_MSYS}"))
    check("  ... and inside a python one-liner",
          blocked(PROJ, "Bash",
                  command=f"python3 -c \"open('{AGENT_MSYS}','w').write('x')\""))
    check("windows: a quoted backslash path is blocked",
          blocked(PROJ, "Bash", command=f"sed -i 's/a/b/' '{AGENT_BS}'"))
    check("  ... and through a redirect",
          blocked(PROJ, "Bash", command=f"echo x > '{AGENT_BS}'"))
    check("windows: a lower-case drive letter is still the same file",
          blocked(PROJ, "Bash", command=f"cp /tmp/x {AGENT[0].lower() + AGENT[1:]}"))
    check("windows: a POSIX-form cwd still resolves the deployment",
          blocked(pathlib.PurePosixPath(msys(PROJ)), "Bash",
                  command="echo x > .claude/skills/cycle/SKILL.md"))
    check("windows: reading through an MSYS-form path is still allowed",
          not blocked(PROJ, "Bash", command=f"cat {AGENT_MSYS}"))
    check("  ... and writing project source through one",
          not blocked(PROJ, "Bash", command=f"echo x > {msys(PROJ / 'lib/app.dart')}"))

# ------------------------------------------------------ a path with a space
#
# A Windows profile path can hold a space, so a framework under one is the
# ordinary case there. Each write names the path quoted, as a shell needs it.
SFW = R / "with space/agent-sdlc"
(SFW / ".claude/skills/cycle").mkdir(parents=True)
(SFW / ".claude/agents").mkdir(parents=True)
(SFW / ".claude/agents/coding.md").write_text("tools: Read\n")
(SFW / ".claude/skills/cycle/SKILL.md").write_text("skill\n")
SPROJ = R / "with space/clone"
(SPROJ / ".claude/skills").mkdir(parents=True)
os.symlink(SFW / ".claude/skills/cycle", SPROJ / ".claude/skills/cycle")
SA = (SFW / ".claude/agents/coding.md").as_posix()
for label, command in [
    ("sed -i", f"sed -i '' 's/a/b/' '{SA}'"),
    ("a double-quoted sed -i", f'sed -i "" s/a/b/ "{SA}"'),
    ("a redirect", f"echo x > '{SA}'"),
    ("a double-quoted redirect appended", f'printf x >> "{SA}"'),
    ("cp", f"cp /tmp/x '{SA}'"),
    ("a python one-liner", f"python3 -c \"open('{SA}','w')\""),
    ("node", f"node -e \"fs.writeFileSync('{SA}', 'x')\""),
    ("pwsh", f"pwsh -c \"Set-Content '{SA}' x\""),
    ("perl -pi", f"perl -pi -e s/a/b/ '{SA}'"),
]:
    check(f"framework under a path with a space: {label} is blocked",
          blocked(SPROJ, "Bash", command=command))
check("  ... and the Write tool", blocked(SPROJ, "Write", file_path=SA, content="x"))
check("  ... and reading it is still allowed",
      not blocked(SPROJ, "Bash", command=f"cat '{SA}'"))
check("  ... as is running a framework script whose arguments name it",
      not blocked(SPROJ, "Bash",
                  command=f"python3 .claude/skills/cycle/evidence.py absence --pattern 'rm -rf' '{SA}'"))

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
