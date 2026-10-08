#!/usr/bin/env python3
"""Tests for discard-untracked.py — stdlib only.

The whole value of this script is what it REFUSES, so most of these assert a
refusal and that the file is still there afterwards. A delete tool whose guards
are untested is a delete tool with no guards.

    python3 tests/test_discard_untracked.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/cycle/discard-untracked.py"

FAILED = 0


def ok(label: str) -> None:
    print(f"ok    {label}")


def bad(label: str, detail: str) -> None:
    global FAILED
    print(f"FAIL  {label}\n     {detail}")
    FAILED = 1


def chk(label: str, got, want) -> None:
    ok(label) if got == want else bad(label, f"want [{want}] got [{got}]")


def run(cwd: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          cwd=cwd, capture_output=True, text=True, timeout=30)


def repo(tmp: pathlib.Path) -> pathlib.Path:
    r = tmp / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=r, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=r, check=True)
    (r / ".gitignore").write_text(".env\nlocal/\n")
    (r / "tracked.dart").write_text("// committed\n")
    subprocess.run(["git", "add", "-A"], cwd=r, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=r, check=True)
    return r


def main() -> int:
    print("discard-untracked")

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        r = repo(t)

        # The case it exists for: a /refine probe inside the test glob.
        probe = r / "test" / "zz_probe_529_test.dart"
        probe.parent.mkdir(parents=True)
        probe.write_text("// throwaway\n")

        p = run(r, "test/zz_probe_529_test.dart")
        chk("a dry run exits 0", p.returncode, 0)
        chk("  ... and does not remove the file", probe.exists(), True)
        chk("  ... and says it was a dry run",
            "pass --apply to remove" in p.stdout, True)

        p = run(r, "test/zz_probe_529_test.dart", "--apply")
        chk("--apply removes the probe", p.returncode, 0)
        chk("  ... and the file is gone", probe.exists(), False)
        chk("  ... naming what it removed",
            "test/zz_probe_529_test.dart" in p.stdout, True)

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        r = repo(t)

        # A tracked file has a commit to go back to; this is not that job.
        p = run(r, "tracked.dart", "--apply")
        chk("a tracked file is refused", p.returncode, 2)
        chk("  ... and still exists", (r / "tracked.dart").exists(), True)
        chk("  ... pointing at git checkout instead",
            "git checkout" in p.stderr, True)

        # Ignored is not disposable: .env is ignored and is local credentials.
        (r / ".env").write_text("SECRET=1\n")
        p = run(r, ".env", "--apply")
        chk("an ignored file is refused", p.returncode, 2)
        chk("  ... and still exists", (r / ".env").exists(), True)
        chk("  ... saying ignored is not a throwaway",
            "local config" in p.stderr, True)

        # A directory is the `git clean -d` footgun. Never.
        (r / "test").mkdir()
        (r / "test" / "a.dart").write_text("x\n")
        p = run(r, "test", "--apply")
        chk("a directory is refused", p.returncode, 2)
        chk("  ... and its contents survive", (r / "test" / "a.dart").exists(), True)
        chk("  ... saying it removes files, never trees",
            "never trees" in p.stderr, True)

        # `..` must not escape, even though the string looks repo-relative.
        outside = t / "outside.txt"
        outside.write_text("keep\n")
        p = run(r, "../outside.txt", "--apply")
        chk("a .. path out of the tree is refused", p.returncode, 2)
        chk("  ... and the file survives", outside.exists(), True)
        chk("  ... naming the work tree it compared against",
            "outside the work tree" in p.stderr, True)

        # A symlink pointing out of the repo is resolved, then refused — not
        # followed and unlinked at its target.
        target = t / "precious.txt"
        target.write_text("keep\n")
        link = r / "link.txt"
        try:
            link.symlink_to(target)
        except OSError:
            ok("  ... (symlink case skipped — not supported here)")
        else:
            p = run(r, "link.txt", "--apply")
            chk("a symlink out of the tree is refused", p.returncode, 2)
            chk("  ... and its target survives", target.exists(), True)

        p = run(r, "no/such/file.dart", "--apply")
        chk("a nonexistent path is refused, not silently ignored", p.returncode, 2)

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        r = repo(t)
        # Two passes: one bad path in the batch must stop the whole batch, or a
        # refusal leaves the operator working out which half ran.
        good = r / "scratch.dart"
        good.write_text("x\n")
        p = run(r, "scratch.dart", "tracked.dart", "--apply")
        chk("one refused path refuses the whole batch", p.returncode, 2)
        chk("  ... and the valid one is NOT removed", good.exists(), True)

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        # Outside a repo there is no work tree to bound anything against.
        p = run(t, "anything.txt", "--apply")
        chk("outside a git work tree it refuses", p.returncode, 2)
        chk("  ... saying so", "not inside a git work tree" in p.stderr, True)

    print(f"\ndiscard-untracked: "
          f"{'all checks passed.' if FAILED == 0 else 'FAILURES above.'}")
    return FAILED


if __name__ == "__main__":
    sys.exit(main())
