"""Regression tests for .claude/skills/cycle/clear-agent-states.py.

The finished/live decision is the dangerous one: a false "finished" deletes a live
cycle's only recovery point. An earlier version substring-matched the Status *line*
against "complete", so a real file reading "Phase 2B complete — Gate 2 approved,
awaiting --exe" would have been deleted, while one reading "active" for a cycle
whose PR had merged was kept. Both cases are pinned below.

Stdlib only, and runnable without pytest:

    python3 tests/test_clear_agent_states.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/cycle/clear-agent-states.py"

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def make_repo(tmp: pathlib.Path) -> pathlib.Path:
    """A throwaway git repo — the script anchors on the git root."""
    repo = tmp / "repo"
    (repo / "agent_states").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    return repo


def state(repo: pathlib.Path, feature: str, status: str) -> pathlib.Path:
    f = repo / "agent_states" / f"cycle-state-{feature}.md"
    f.write_text(f"# Cycle State: {feature}\nStatus: {status}\n\n## References\n- Mode: lean\n")
    return f


def report(repo: pathlib.Path, name: str) -> None:
    d = repo / "cycle_reports"
    d.mkdir(exist_ok=True)
    (d / name).write_text("# report\n")


def run_real(repo: pathlib.Path, *extra: str) -> str:
    """Actually delete. The archive step is deliberately skipped on a dry run —
    copying files is a side effect, and --dry-run promises none."""
    p = subprocess.run([sys.executable, str(SCRIPT), *extra],
                       cwd=repo, capture_output=True, text=True, timeout=30)
    return p.stdout + p.stderr


def run(repo: pathlib.Path, *extra: str) -> str:
    p = subprocess.run([sys.executable, str(SCRIPT), "--dry-run", *extra],
                       cwd=repo, capture_output=True, text=True, timeout=30)
    return p.stdout + p.stderr


def run_real(repo: pathlib.Path, *extra: str) -> str:
    p = subprocess.run([sys.executable, str(SCRIPT), *extra],
                       cwd=repo, capture_output=True, text=True, timeout=30)
    return p.stdout + p.stderr


def main() -> int:
    print("clear-agent-states")
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)

        # The bug this test exists for: phase prose is not cycle status.
        repo = make_repo(t)
        state(repo, "431-rpe-range-bounds",
              "Phase 2B complete — Gate 2 approved, awaiting `--exe`. Phase 3 NOT started.")
        out = run(repo)
        check("'Phase 2B complete' is NOT treated as finished",
              "cycle-state-431-rpe-range-bounds.md" not in out.split("would delete:")[-1].split("kept:")[0],
              out)
        check("  ... and is reported as kept", "kept:" in out and "431-rpe-range-bounds" in out, out)

    with tempfile.TemporaryDirectory() as tmp:
        # The inverse: 'active' but a cycle report exists -> the cycle finished
        # without sending FINALIZE (the framework's own janitor rule).
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        state(repo, "adjust-all-zero-coercion", "active")
        report(repo, "adjust-all-zero-coercion-2026-09-04.md")
        out = run(repo)
        check("'active' + matching report IS treated as finished",
              "adjust-all-zero-coercion" in out.split("would delete:")[-1].split("kept:")[0], out)

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        state(repo, "no-report-yet", "active")
        out = run(repo)
        check("'active' with no report is kept", "kept:" in out and "no-report-yet" in out, out)

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        state(repo, "done-cycle", "finished")
        out = run(repo)
        check("a terminal Status value is finished",
              "done-cycle" in out.split("would delete:")[-1].split("kept:")[0], out)

    with tempfile.TemporaryDirectory() as tmp:
        # Report prefix must anchor: 'auth' must not be finished by 'auth-refactor'.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        state(repo, "auth-refactor", "active")
        report(repo, "auth-2026-09-01.md")
        out = run(repo)
        check("report match anchors on prefix, not bare substring",
              "kept:" in out and "auth-refactor" in out, out)

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        state(repo, "live-one", "active")
        out = run(repo, "--all")
        check("--all overrides and would delete a live file",
              "live-one" in out.split("would delete:")[-1].split("kept:")[0], out)

    with tempfile.TemporaryDirectory() as tmp:
        # The fan-out marker is provenance, not state. Clearing it mid-cycle sends
        # the rest of the run's telemetry to the origin repo (evidence-run1 E1).
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        (repo / "agent_states" / ".fanout-clone").write_text("issue=419\n")
        (repo / "agent_states" / "events").mkdir()
        out = run(repo, "--all")
        would_go = out.split("would delete:")[-1].split("kept:")[0]
        check(".fanout-clone survives --all", ".fanout-clone" not in would_go, out)
        check("  ... while events/ still goes", "events" in would_go, out)

    with tempfile.TemporaryDirectory() as tmp:
        # A fan-out clone's telemetry is the only record of what several concurrent
        # cycles did to one machine, and it can only be read after they all finish —
        # by which time each clone has cleared itself. Archive, then clear.
        t = pathlib.Path(tmp)
        run_root = t / "cycles"; run_root.mkdir()
        repo = make_repo(t)
        st = repo / "agent_states"
        (st / "events").mkdir()
        (st / "events" / "impl-2.0.jsonl").write_text('{"tool":"Read"}\n')
        (st / "counters").mkdir()
        (st / "counters" / "impl-2.0").write_text("7")
        (st / "gate-log.tsv").write_text("raised_at\tcycle\nx\tc1\n")
        (st / ".fanout-clone").write_text(
            f"issue=419\nclone=c1\ngate_log={run_root}/gate-log.tsv\n")

        out = run_real(repo, "--all")
        check("clearing a fan-out clone archives its telemetry first",
              "archived telemetry" in out, out)
        arch = run_root / "telemetry" / "c1"
        check("  ... events survive at the run root",
              (arch / "events" / "impl-2.0.jsonl").is_file(), str(list(arch.rglob("*"))))
        check("  ... so does the gate log",
              (arch / "gate-log.tsv").is_file(), str(list(arch.rglob("*"))))
        check("  ... and the clone is still cleared",
              not (st / "events").exists(), str(list(st.iterdir())))
        check("  ... while the marker itself is preserved",
              (st / ".fanout-clone").is_file())

    with tempfile.TemporaryDirectory() as tmp:
        # A failed archive must not look like a solo cycle. It is the difference
        # between "nothing to keep" and "the run's only cross-clone evidence is
        # gone", and both printed the same thing before.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        st = repo / "agent_states"
        (st / "events").mkdir()
        (st / ".fanout-clone").write_text(
            f"issue=419\nclone=c1\ngate_log={t}/does-not-exist/gate-log.tsv\n")
        out = run_real(repo, "--all")
        check("an archive that cannot find its run root says so",
              "telemetry NOT archived" in out, out)
        rc = subprocess.run([sys.executable, str(SCRIPT), "--all"], cwd=repo,
                            capture_output=True, text=True, timeout=30).returncode
        check("  ... and exits non-zero, not just prints", rc == 2, str(rc))
        dry = run(repo)
        check("  ... while a dry run previews the problem without deleting",
              "telemetry NOT archived" in dry, dry)
        check("  ... and warns the events are going unarchived",
              "unarchived" in out, out)

    with tempfile.TemporaryDirectory() as tmp:
        # A marker with no gate_log is a format drift, not a solo cycle.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        (repo / "agent_states" / "events").mkdir()
        (repo / "agent_states" / ".fanout-clone").write_text("issue=419\nclone=c1\n")
        out = run_real(repo, "--all")
        check("a marker without gate_log is reported, not ignored",
              "names no gate_log" in out, out)

    with tempfile.TemporaryDirectory() as tmp:
        # A solo cycle has no run root and must be unaffected.
        t = pathlib.Path(tmp)
        repo = make_repo(t)
        (repo / "agent_states" / "events").mkdir()
        out = run_real(repo, "--all")
        check("a solo cycle archives nothing", "archived telemetry" not in out, out)

    # --- J5: the runtime task file nothing owned -----------------------------
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        tasks = repo / "agent_tasks"; tasks.mkdir(parents=True, exist_ok=True)
        (tasks / "tasks-453-programs-remount.md").write_text("- [x] 1.0\n")
        (tasks / "prds").mkdir(exist_ok=True)
        (tasks / "prds" / "prd-453.md").write_text("prd\n")
        (tasks / "agent_metrics.md").write_text("metrics\n")
        out = run_real(repo, "--all")
        check("the runtime task file is deleted",
              not (tasks / "tasks-453-programs-remount.md").exists(), out)
        check("  ... and named in the report", "agent_tasks/tasks-453" in out, out)
        # agent_tasks/ also holds PRDs and metrics, which are not runtime.
        check("  ... while a PRD is untouched", (tasks / "prds" / "prd-453.md").exists(), out)
        check("  ... and so is anything not named tasks-*.md",
              (tasks / "agent_metrics.md").exists(), out)

    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        tasks = repo / "agent_tasks"; tasks.mkdir(parents=True, exist_ok=True)
        (tasks / "tasks-x.md").write_text("x\n")
        out = run(repo, "--all")
        check("a dry run reports the task file without deleting it",
              "agent_tasks/tasks-x.md" in out and (tasks / "tasks-x.md").exists(), out)

    # The report must not claim an empty directory: the session keeps writing.
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(pathlib.Path(tmp))
        out = run_real(repo, "--all")
        check("the report says files will reappear, rather than claiming empty",
              "will write here again" in out, out)

    if FAILURES:
        print("\nFAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\nclear-agent-states: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
