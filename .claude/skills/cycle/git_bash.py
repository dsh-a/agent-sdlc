#!/usr/bin/env python3
"""git_bash — the bash a pipeline script hands a shell command to.

A command a script runs for the caller (`suite-result.py run`, `evidence.py
round-trip`) is POSIX shell. Off Windows the platform shell already is one. On
Windows it is cmd.exe, which reads the same command differently, so there the
command goes to Git Bash, and when Git Bash cannot be found the script stops
and says so. bash is always resolved to a full path: CreateProcess searches
System32 before PATH, and System32's bash.exe is WSL, which is Linux and cannot
see C:\\ paths.

Importers add this file's real directory to sys.path: a project reaches the
skill scripts through links, and only the real path leads back here.

    python3 .claude/skills/cycle/git_bash.py

prints the bash scripts use, or exits 1 with two lines on stderr: where it
looked, and the fix.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import sys

# Directories whose bash.exe is a WSL launcher.
WSL_DIRS = ("system32", "windowsapps")

FIX = "install Git for Windows, or put its usr\\bin on PATH ahead of C:\\Windows\\System32"


class GitBashNotFound(RuntimeError):
    """Windows, and no Git Bash. The message names where it looked and the fix."""

    def __init__(self, finding: str) -> None:
        self.finding, self.fix = finding, FIX
        super().__init__(f"{finding}. Fix: {FIX}; the framework's `deploy.sh doctor` checks this")


def usable(path: str) -> bool:
    """False for a bash.exe under System32 or WindowsApps: those are WSL."""
    parts = {p.lower() for p in pathlib.PureWindowsPath(path).parts}
    return not parts.intersection(WSL_DIRS)


def find() -> str:
    """Git Bash's bash.exe; raises GitBashNotFound.

    Looks, in order, at: the bash PATH resolves first; each later bash on PATH;
    bin\\bash.exe in the Git install that holds the `git` on PATH. The first
    that is not WSL wins.
    """
    found = [shutil.which("bash")]
    found += [shutil.which("bash", path=d)
              for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    for bash in found:
        if bash and usable(bash):
            return bash
    skipped = sorted({b for b in found if b})
    looked = ["bash on PATH (" + (", ".join(skipped) + ": WSL" if skipped else "none") + ")"]

    git = shutil.which("git")
    if git:
        # git.exe sits in <root>\cmd, <root>\bin or <root>\mingw64\bin.
        up = os.path.dirname(os.path.dirname(git))
        for root in (up, os.path.dirname(up)):
            exe = os.path.join(root, "bin", "bash.exe")
            if os.path.isfile(exe) and usable(exe):
                return exe
        looked.append(f"bin\\bash.exe in the Git install holding {git}")
    else:
        looked.append("bin\\bash.exe beside git (git is not on PATH)")
    raise GitBashNotFound(f"no Git Bash found; looked at {'; '.join(looked)}")


def git_bash() -> str | None:
    """Git Bash on Windows; None elsewhere, where the platform shell is POSIX."""
    return find() if os.name == "nt" else None


def bash() -> str:
    """The bash to run a .sh file with: Git Bash on Windows, PATH's bash elsewhere."""
    return git_bash() or shutil.which("bash") or "bash"


if __name__ == "__main__":
    try:
        print(bash())
    except GitBashNotFound as e:
        print(f"{e.finding}\n{e.fix}", file=sys.stderr)
        sys.exit(1)
