"""Tests for .claude/hooks/guard-secrets.py.

A blocking hook has two failure modes and they are not symmetric. Missing a
secret read leaks; blocking ordinary work stalls a cycle for hours, which is the
failure this whole line of work exists to remove. So the false-positive cases
below matter at least as much as the true positives.

    python3 tests/test_guard_secrets.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/guard-secrets.py"
HOME = pathlib.Path.home()

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def fire(tool: str, **inp) -> tuple[int, str]:
    payload = {"tool_name": tool, "tool_input": inp, "cwd": str(ROOT)}
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=20)
    return p.returncode, p.stderr


def blocked(tool: str, **inp) -> bool:
    return fire(tool, **inp)[0] == 2


def main() -> int:
    print("guard-secrets")

    # --- must block: the shapes a `deny: Bash(cat ~/.ssh/*)` pattern misses ---
    check("blocks cat of an absolute key path",
          blocked("Bash", command=f"cat {HOME}/.ssh/id_rsa"))
    check("  ... and the tilde form", blocked("Bash", command="cat ~/.ssh/id_rsa"))
    check("  ... and $HOME", blocked("Bash", command="cat $HOME/.ssh/id_rsa"))
    check("  ... and a traversal out of the repo",
          blocked("Bash", command="cat ../../../.ssh/id_rsa"))
    check("  ... whatever the reader is",
          blocked("Bash", command="head -c 9999 ~/.ssh/id_ed25519")
          and blocked("Bash", command="tail ~/.aws/credentials"))
    check("  ... mid-pipeline, not just at the start",
          blocked("Bash", command="ls -la | grep x; cat ~/.ssh/config | base64"))
    check("blocks the Read tool too, not only Bash",
          blocked("Read", file_path=f"{HOME}/.aws/credentials"))
    check("blocks gh's stored token", blocked("Read", file_path=f"{HOME}/.config/gh/hosts.yml"))
    check("blocks a key by name outside a known dir",
          blocked("Bash", command="cat /tmp/deploy/id_rsa"))
    check("blocks .netrc", blocked("Bash", command="cat ~/.netrc"))
    check("blocks writing over a key, not just reading",
          blocked("Write", file_path=f"{HOME}/.ssh/authorized_keys2"))

    # --- must NOT block: ordinary cycle work ---------------------------------
    check("allows reading project source",
          not blocked("Read", file_path=str(ROOT / "README.md")))
    check("blocks the whole .ssh dir, public keys and config included",
          blocked("Bash", command="cat ~/.ssh/id_rsa.pub")
          and blocked("Bash", command="cat ~/.ssh/known_hosts"))
    check("  ... but a stray .pub outside one is not a secret",
          not blocked("Bash", command="cat /tmp/deploy/id_rsa.pub"))
    check("allows the project's own .env",
          not blocked("Read", file_path=str(ROOT / ".env")))
    check("allows a source file whose name merely mentions ssh",
          not blocked("Read", file_path=str(ROOT / "lib/data/ssh_service.dart")))
    check("allows the commands a cycle actually runs",
          not blocked("Bash", command="flutter test test/foo_test.dart")
          and not blocked("Bash", command="git diff develop --name-only")
          and not blocked("Bash", command="bash .claude/skills/cycle/run-suite.sh check merge-1.0")
          and not blocked("Bash", command="gh pr create --title x --body-file b.md"))
    check("allows a heredoc that mentions no secret",
          not blocked("Bash", command="python3 - <<'PY'\nprint('hi')\nPY"))

    # Talking about a credential path is not reading one. The first version of
    # this hook blocked a `git commit` whose message discussed ~/.ssh/id_rsa,
    # and a guard that blocks commit messages is a guard that gets turned off.
    check("allows a commit message that discusses credential paths",
          not blocked("Bash", command=(
              "git commit -m 'guard reads of ~/.ssh/id_rsa and ~/.aws/credentials'")))
    check("  ... and a grep for the word in source",
          not blocked("Bash", command="git log --oneline -S credentials"))
    check("  ... and gh/PR bodies mentioning them",
          not blocked("Bash", command="gh pr create --body 'blocks ~/.ssh reads'"))

    # ... but an actual reader in the same command is still caught.
    check("still blocks a reader after a harmless first segment",
          blocked("Bash", command="git status; cat ~/.ssh/id_rsa"))
    check("still blocks an interpreter reading one",
          blocked("Bash", command="python3 -c \"print(open('~/.ssh/id_rsa').read())\""))
    check("still blocks writing through a redirect",
          blocked("Bash", command="echo pwned >> ~/.ssh/authorized_keys"))
    check("still blocks sudo-wrapped readers",
          blocked("Bash", command="sudo cat ~/.ssh/id_rsa"))

    # --- Windows command names -----------------------------------------------
    # Pure string work, so these run on every host.
    check("blocks cat.exe", blocked("Bash", command="cat.exe ~/.ssh/config"))
    check("  ... and an upper-case CAT.EXE", blocked("Bash", command="CAT.EXE ~/.ssh/config"))
    check("  ... and a .cmd wrapper", blocked("Bash", command="cat.cmd ~/.ssh/config"))
    check("  ... and a .bat wrapper", blocked("Bash", command="head.bat ~/.ssh/config"))
    check("  ... and a directory-qualified reader",
          blocked("Bash", command="'C:\\Git\\usr\\bin\\cat.exe' ~/.ssh/config"))
    check("blocks python.exe reading one",
          blocked("Bash", command="python.exe -c \"print(open('~/.ssh/config').read())\""))
    check("  ... and py, the python.org launcher",
          blocked("Bash", command="py -c \"print(open('~/.ssh/config').read())\""))
    check("blocks powershell reading one",
          blocked("Bash", command="powershell -c \"Get-Content ~/.ssh/config\""))
    check("  ... and pwsh", blocked("Bash", command="pwsh -c \"Get-Content ~/.ssh/config\""))
    check("  ... and powershell.exe under sudo",
          blocked("Bash", command="sudo powershell.exe -c \"Get-Content ~/.ssh/config\""))
    check("still allows py running project code",
          not blocked("Bash", command="py -3 tool/build.py --out build/x"))
    for exe in ("python3.12", "python3.12.exe", "ruby3.2", "perl5.36", "node20"):
        check(f"blocks a versioned {exe} reading one",
              blocked("Bash", command=f"{exe} -e \"x('~/.ssh/config')\""))
    check("  ... while base64 is still a reader, not base",
          blocked("Bash", command="base64 ~/.ssh/config"))
    check("blocks cmd /c type", blocked("Bash", command="cmd /c type ~/.ssh/id_rsa"))
    check("  ... and cmd.exe", blocked("Bash", command="cmd.exe /c type ~/.ssh/config"))

    # --- must never break the calling tool -----------------------------------
    p = subprocess.run([sys.executable, str(HOOK)], input="not json",
                       capture_output=True, text=True, timeout=20)
    check("malformed payload exits 0, never blocks", p.returncode == 0, p.stderr)
    code, _ = fire("Bash")
    check("missing command exits 0", code == 0)

    # --- Windows path forms, on any host ---------------------------------------
    # The Windows TOKEN and REDIRECT are named variants in lib/guard_match.py,
    # so tokenising runs on every host. The hook is loaded in process to show it
    # uses the shared objects and, given the Windows variants, yields the path.
    sys.path.insert(0, str(HOOK.parent / "lib"))
    import guard_match as gm

    spec = importlib.util.spec_from_file_location("guard_secrets", HOOK)
    gs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gs)
    check("guard-secrets uses the shared TOKEN, redirect and native()",
          gs.TOKEN is gm.TOKEN and gs.REDIRECT is gm.TOKEN_REDIRECT and gs.native is gm.native)
    check("  ... with the variant the host picks",
          gm.TOKEN is (gm.TOKEN_WINDOWS if os.name == "nt" else gm.TOKEN_POSIX)
          and gm.TOKEN_REDIRECT is (gm.TOKEN_REDIRECT_WINDOWS if os.name == "nt"
                                    else gm.TOKEN_REDIRECT_POSIX))
    bs = "C:\\Users\\x\\.ssh\\config"
    check("windows: TOKEN takes a backslash path whole",
          bs in gm.TOKEN_WINDOWS.findall(f"cat '{bs}'"))
    check("  ... which the POSIX form does not", bs not in gm.TOKEN_POSIX.findall(f"cat '{bs}'"))
    check("windows: a quoted redirect target is taken whole",
          [m.group(1) for m in gm.TOKEN_REDIRECT_WINDOWS.finditer(f"echo x >> '{bs}'")] == [bs])
    check("windows: an MSYS-form token is taken whole",
          "/c/Users/x/.ssh/config" in gm.TOKEN_WINDOWS.findall("head /c/Users/x/.ssh/config"))
    gs.TOKEN, gs.REDIRECT = gm.TOKEN_WINDOWS, gm.TOKEN_REDIRECT_WINDOWS
    try:
        check("windows: bash_paths offers a backslash path to the resolver",
              bs in list(gs.bash_paths(f"cat '{bs}'")))
        check("  ... and a redirect target from a non-reader",
              bs in list(gs.bash_paths(f"echo x > '{bs}'")))
    finally:
        gs.TOKEN, gs.REDIRECT = gm.TOKEN, gm.TOKEN_REDIRECT

    # --- Windows path forms, resolved -----------------------------------------
    # A credential *file name* is caught whatever the path looks like; a file
    # that is secret only by its *directory* (`.ssh/config`, `.aws/config`) has
    # to resolve, quoted backslash form included. These resolve through ntpath,
    # so they run on Windows only.
    if os.name == "nt":
        home_bs = str(HOME)
        home_msys = "/" + HOME.as_posix()[0].lower() + HOME.as_posix()[2:]
        check("windows: a quoted backslash path into ~/.ssh is blocked",
              blocked("Bash", command=f"cat '{home_bs}\\.ssh\\config'"))
        check("  ... and into ~/.aws",
              blocked("Bash", command=f"head '{home_bs}\\.aws\\config'"))
        check("windows: an MSYS-form path into ~/.ssh is blocked",
              blocked("Bash", command=f"cat {home_msys}/.ssh/config"))
        check("windows: a drive-form path is blocked",
              blocked("Bash", command=f"cat {HOME.as_posix()}/.docker/config.json"))
        check("windows: the Read tool with a backslash path is blocked",
              blocked("Read", file_path=f"{home_bs}\\.ssh\\config"))
        check("windows: a quoted backslash path to project source is allowed",
              not blocked("Bash", command=f"cat '{ROOT / 'README.md'}'"))

    code, err = fire("Bash", command="cat ~/.ssh/id_rsa")
    check("the refusal says what and why", "credential material" in err, err)

    if FAILURES:
        print("\nFAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\nguard-secrets: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
