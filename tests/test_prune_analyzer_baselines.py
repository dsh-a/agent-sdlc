"""Vault-safety tests for .claude/skills/cycle/prune-analyzer-baselines.py.

This script deletes from a permanent, shared record, so the dangerous mistake is
the opposite of clear-agent-states.py's: not "kept something stale" but "removed
something irreplaceable". `cycle_reports/<feature>/` legitimately holds supervisor
archives and stall-salvage artifacts alongside the stale baselines — in the real
vault that prompted this, 2 of 61 directories did — so a blanket directory removal
would have destroyed evidence. The rmdir-not-rmtree property is pinned below.

Stdlib only:

    python3 tests/test_prune_analyzer_baselines.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/cycle/prune-analyzer-baselines.py"

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def make_vault(tmp: pathlib.Path) -> pathlib.Path:
    repo = tmp / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    reports = repo / "cycle_reports"
    for n in range(3):
        d = reports / f"feature-{n}"
        d.mkdir(parents=True)
        (d / "analyzer-baseline.txt").write_text("warning: x\n" * 20)
    # A directory holding a real record alongside the scratch.
    keep = reports / "salvaged-feature"
    keep.mkdir(parents=True)
    (keep / "analyzer-baseline.txt").write_text("warning: y\n")
    (keep / "salvage-task-3.0.md").write_text("# what the stalled agent had done\n")
    # A flat report file, which must never be touched.
    (reports / "feature-0-2026-09-01.md").write_text("# report\n")
    return repo


def run(repo: pathlib.Path, *extra: str) -> str:
    p = subprocess.run([sys.executable, str(SCRIPT), *extra],
                       cwd=repo, capture_output=True, text=True, timeout=30)
    return p.stdout + p.stderr


def main() -> int:
    print("prune-analyzer-baselines")

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        repo = make_vault(t)
        reports = repo / "cycle_reports"

        out = run(repo)
        check("dry run is the default", "Dry run" in out and "4 analyzer-baseline.txt" in out, out)
        check("  ... and deletes nothing",
              (reports / "feature-0" / "analyzer-baseline.txt").exists(), out)

        out = run(repo, "--apply")
        check("--apply removes every baseline",
              not any((reports / f"feature-{n}" / "analyzer-baseline.txt").exists()
                      for n in range(3)), out)
        check("  ... and prunes the directories left empty",
              not any((reports / f"feature-{n}").exists() for n in range(3)), out)

        # The property this script exists to guarantee.
        check("a directory holding a real record survives",
              (reports / "salvaged-feature" / "salvage-task-3.0.md").is_file(), out)
        check("  ... its stale baseline still goes",
              not (reports / "salvaged-feature" / "analyzer-baseline.txt").exists(), out)
        check("  ... and the survival is reported, not silent",
              "kept 1 directory" in out and "salvaged-feature" in out, out)
        check("flat report files are untouched",
              (reports / "feature-0-2026-09-01.md").is_file(), out)

        out = run(repo, "--apply")
        check("a second run is a no-op", "nothing to do" in out, out)

    with tempfile.TemporaryDirectory() as tmp:
        # The real deployment reaches the vault through a symlink; that must resolve.
        t = pathlib.Path(tmp)
        vault = t / "vault" / "cycle_reports" / "app"
        (vault / "feature-a").mkdir(parents=True)
        (vault / "feature-a" / "analyzer-baseline.txt").write_text("x\n")
        repo = t / "deployment"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
        (repo / "cycle_reports").symlink_to(vault)
        out = run(repo, "--apply")
        check("follows a vault symlink and cleans through it",
              not (vault / "feature-a").exists(), out)

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        repo = t / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
        out = run(repo, "--apply")
        check("no cycle_reports is 'nothing to do', not an error", "nothing to do" in out, out)

    if FAILURES:
        print("\nFAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\nprune-analyzer-baselines: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
