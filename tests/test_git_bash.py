#!/usr/bin/env python3
"""Tests for .claude/skills/cycle/git_bash.py and the scripts that use it — stdlib only.

Windows is simulated: `os.name` is set to "nt" and PATH points at stand-in Git
and Windows directories, so every case runs on every host.

    python3 tests/test_git_bash.py
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
CYCLE = ROOT / ".claude" / "skills" / "cycle"
EVIDENCE = ROOT / ".claude" / "skills" / "evidence"


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# Imported by name, as the scripts import it, so they share one module object.
sys.path.insert(0, str(CYCLE))
import git_bash as gb  # noqa: E402

sr = load("suite_result", CYCLE / "suite-result.py")
ev = load("evidence", EVIDENCE / "evidence.py")

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def exe(path: pathlib.Path) -> pathlib.Path:
    """A stand-in executable, under its POSIX name and its Windows one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for p in (path, path.with_suffix(".exe")):
        p.write_text("#!/bin/sh\n")
        p.chmod(0o755)
    return path


@contextlib.contextmanager
def windows(*dirs: pathlib.Path):
    """os.name "nt", and PATH holding only `dirs`."""
    with mock.patch.object(os, "name", "nt"), \
         mock.patch.dict(os.environ, {"PATH": os.pathsep.join(map(str, dirs))}):
        yield


class Host:
    """A stand-in Windows machine: a WSL bash, a Git install, a Store launcher dir."""

    def __init__(self, base: pathlib.Path) -> None:
        self.system32 = base / "Windows" / "System32"
        self.apps = base / "Users" / "u" / "AppData" / "Local" / "Microsoft" / "WindowsApps"
        self.git = base / "Program Files" / "Git"
        self.wsl = exe(self.system32 / "bash")
        self.store = exe(self.apps / "bash")
        self.usr_bash = exe(self.git / "usr" / "bin" / "bash")
        exe(self.git / "cmd" / "git")
        self.bin_bash = self.git / "bin" / "bash.exe"
        exe(self.git / "bin" / "bash")


def parent(p: str | None) -> str | None:
    return os.path.dirname(p) if p else None


def test_usable() -> None:
    print("\nusable: WSL's launchers are refused, Git's bash is not")
    check("System32 is WSL", not gb.usable(r"C:\WINDOWS\system32\bash.exe"))
    check("WindowsApps is WSL",
          not gb.usable(r"C:\Users\u\AppData\Local\Microsoft\WindowsApps\bash.exe"))
    check("Git's usr\\bin is used", gb.usable(r"C:\Program Files\Git\usr\bin\bash.exe"))
    check("Git's bin is used", gb.usable("C:/Program Files/Git/bin/bash.exe"))


def test_lookup_order() -> None:
    print("\nfind: PATH first, then Git's own bin\\bash.exe")
    with tempfile.TemporaryDirectory() as td:
        h = Host(pathlib.Path(td))
        with windows(h.git / "usr" / "bin", h.git / "cmd"):
            check("the bash PATH resolves, when it is Git's",
                  parent(gb.git_bash()) == str(h.usr_bash.parent), str(gb.git_bash()))
        with windows(h.system32, h.git / "usr" / "bin"):
            check("a later bash on PATH, past System32's",
                  parent(gb.git_bash()) == str(h.usr_bash.parent), str(gb.git_bash()))
        with windows(h.apps, h.system32, h.git / "cmd"):
            check("bin\\bash.exe beside git, when PATH holds only WSL's",
                  gb.git_bash() == str(h.bin_bash), str(gb.git_bash()))
        with windows(h.git / "mingw64" / "bin"):
            exe(h.git / "mingw64" / "bin" / "git")
            check("  ... git under mingw64\\bin finds the same install",
                  gb.git_bash() == str(h.bin_bash), str(gb.git_bash()))


def test_not_found_is_loud() -> None:
    print("\nfind: no Git Bash raises, naming where it looked")
    with tempfile.TemporaryDirectory() as td:
        h = Host(pathlib.Path(td))
        with windows(h.system32):
            try:
                got, msg = gb.git_bash(), ""
            except gb.GitBashNotFound as e:
                got, msg = "raised", str(e)
        check("raises rather than returning WSL or nothing", got == "raised", str(got))
        check("  ... naming the WSL bash it skipped", str(h.system32) in msg, msg)
        check("  ... and that git is not on PATH", "git is not on PATH" in msg, msg)
        check("  ... and the fix", "Git for Windows" in msg and "doctor" in msg, msg)

        (h.git / "bin" / "bash.exe").unlink()
        (h.git / "bin" / "bash").unlink()
        with windows(h.git / "cmd"):
            try:
                gb.git_bash()
                msg = ""
            except gb.GitBashNotFound as e:
                msg = str(e)
        check("  ... and the Git install it searched", "Git install holding" in msg, msg)


def test_off_windows() -> None:
    print("\noff Windows: the platform shell")
    with mock.patch.object(os, "name", "posix"):
        check("git_bash() is None", gb.git_bash() is None)
        check("bash() is PATH's bash", gb.bash() == (shutil.which("bash") or "bash"), gb.bash())


def lookup_on(*dirs: pathlib.Path):
    """The caller's git_bash, run on a stand-in Windows whose PATH is `dirs`.

    Only the lookup is simulated: pathlib refuses to build paths with os.name
    patched, and the callers build paths around it."""
    def look() -> str | None:
        with windows(*dirs):
            return gb.git_bash()
    return look


def test_callers_refuse() -> None:
    print("\ncallers: Windows with no Git Bash runs nothing under cmd.exe")
    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(td)
        h = Host(base / "host")
        root = base / "repo"
        root.mkdir()
        args = argparse.Namespace(name="s", command=["true"], max_failures=15)
        err = io.StringIO()
        with mock.patch.object(sr, "git_bash", lookup_on(h.system32)), \
             mock.patch.object(subprocess, "run", side_effect=AssertionError("ran")), \
             contextlib.redirect_stderr(err):
            rc = sr.cmd_run(args, root, {})
        check("suite-result run exits 1", rc == 1, str(rc))
        check("  ... naming Git Bash", "no Git Bash found" in err.getvalue(), err.getvalue())
        check("  ... and records no run", not (root / "agent_states").exists())

        local = base / "body.md"
        local.write_text("x\n")
        a = argparse.Namespace(local=str(local), remote_cmd="cat body.md", timeout=5,
                               max_rows=5)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(ev, "git_bash", lookup_on(h.system32)), \
             mock.patch.object(subprocess, "run", side_effect=AssertionError("ran")), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ev.cmd_round_trip(a)
        said = out.getvalue() + err.getvalue()
        check("evidence round-trip is undetermined", rc == ev.UNDETERMINED, str(rc))
        check("  ... naming Git Bash", "no Git Bash found" in said, said)

        with mock.patch.object(sr, "git_bash", lookup_on(h.git / "usr" / "bin")), \
             mock.patch.object(subprocess, "run") as run, \
             contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            run.return_value = subprocess.CompletedProcess([], 0)
            sr.cmd_run(args, root, {})
        argv = run.call_args.args[0]
        check("with Git Bash, the suite command goes to it as `bash -c`",
              argv[0] == str(h.usr_bash.parent / "bash") and argv[1:] == ["-c", "true"]
              and run.call_args.kwargs.get("shell") is False, str(run.call_args))


def test_through_a_linked_project() -> None:
    """A project holds links to the skill directories; the helper is reached
    through the link's real path, from either skill."""
    print("\nlinked project: both scripts import the helper through the link")
    with tempfile.TemporaryDirectory() as td:
        proj = pathlib.Path(td) / "app"
        skills = proj / ".claude" / "skills"
        skills.mkdir(parents=True)
        os.symlink(CYCLE, skills / "cycle", target_is_directory=True)
        os.symlink(EVIDENCE, skills / "evidence", target_is_directory=True)
        subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
        packdir = proj / ".claude" / "packs" / "flutter"
        packdir.mkdir(parents=True)
        shutil.copy(ROOT / ".claude" / "packs" / "flutter" / "suite-patterns.md", packdir)
        (proj / "body.md").write_text("same\n")

        def run(*argv: str) -> subprocess.CompletedProcess:
            return subprocess.run([sys.executable, "-I", *argv], cwd=proj,
                                  capture_output=True, text=True)

        r = run(".claude/skills/cycle/suite-result.py", "run", "linked", "--",
                'printf "00:01 +2: All tests passed!\\n"')
        check("suite-result runs a suite", r.returncode == 0 and "tests=2" in r.stdout,
              r.stdout + r.stderr)
        r = run(".claude/skills/evidence/evidence.py", "round-trip", "--local", "body.md",
                "--remote-cmd", "cat body.md")
        check("evidence round-trips", "verdict=identical" in r.stdout, r.stdout + r.stderr)
        r = run(".claude/skills/cycle/git_bash.py")
        check("git_bash.py prints a bash", r.returncode == 0 and "bash" in r.stdout,
              r.stdout + r.stderr)


def main() -> int:
    print("git-bash")
    test_usable()
    test_lookup_order()
    test_not_found_is_loud()
    test_off_windows()
    test_callers_refuse()
    test_through_a_linked_project()
    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all git-bash checks passed")
    return 0


def test_git_bash_suite() -> None:
    """The pytest entry point, so the suite cannot silently pass under pytest."""
    rc = main()
    assert rc == 0, f"{len(failures)} failure(s): {', '.join(failures)}"


if __name__ == "__main__":
    sys.exit(main())
