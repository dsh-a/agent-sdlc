#!/usr/bin/env python3
"""clear-agent-states.py — delete a cycle's ephemeral state under agent_states/.

Exists because the permission layer cannot express this grant. A narrow
`Bash(rm agent_states/*)` allow is shadowed by any broad `Bash(rm *)` in `ask`
or `deny` — most-specific does not win — so the finalize monitor could not clean
up, silently, every cycle. Widening the rm permission is the wrong trade: a glob
permission is a string match against a command, satisfied by a `cd ..` first, a
symlinked directory, or a shell-expanded variable.

This script is the narrower boundary. It takes no argument that can widen its
scope: the target is always `<git-root>/agent_states`, resolved and then checked
to be a non-symlink directory of that exact name. Within it, only known
ephemeral entries are removed, symlinks are never followed, and anything
resolving outside the tree is skipped. No invocation reaches another path.

Stdlib only. Harness-agnostic — no Claude Code / omp assumptions.

    clear-agent-states.py                # stale files only; live cycle state kept
    clear-agent-states.py --all          # including in-flight cycle-state files
    clear-agent-states.py --dry-run      # print what would go, delete nothing
    clear-agent-states.py --archive-only # fan-out clone: copy telemetry out, delete nothing

Exit codes: 0 = cleaned (or nothing to do), 1 = refused, 2 = partial failure.
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

# Directories under agent_states/ that hold per-run telemetry. Always ephemeral:
# Phase 4A has already aggregated them into the run report by finalize time.
# `denial-seen`, `permission-open` and `whispers` are per-session bookkeeping for
# the gate-log hook and the supervisor, read only by the cycle that wrote them.
EPHEMERAL_DIRS = ("events", "counters", "digests", "supervisor", "suite",
                  "denial-seen", "permission-open", "whispers")

# A cycle-state file is the recovery point if the orchestrator crashes, so the
# default is to keep it. Two signals may override that, and the asymmetry is
# deliberate: a false "finished" deletes a live cycle's only recovery point, while
# a false "live" merely leaves a stale file for --all or the next run to clear.
#
# 1. The Status *value* is a terminal word. Matched against the value, never the
#    whole line — an earlier version substring-matched, so "Phase 2B complete —
#    Gate 2 approved, awaiting --exe" read as finished and would have deleted a
#    paused cycle's approved task list. Phase prose is not cycle status.
# 2. A cycle report already exists for the feature. This is the framework's own
#    janitor rule (SKILL.md § Janitor check): a report means the cycle completed
#    without sending FINALIZE. It catches the inverse case, a file still saying
#    "active" for a cycle whose PR merged days ago.
FINISHED_STATUSES = ("finished", "complete", "completed", "released", "done")

# Not state — provenance. `.fanout-clone` marks a checkout as a parallel-run clone
# so the telemetry hook writes events here rather than into the origin it is a
# linked worktree of. It must outlive every clear, including --all: deleting it
# silently sends the rest of the cycle's telemetry to the wrong repo, which is
# exactly the failure it was added to fix.
PRESERVED_FILES = (".fanout-clone",)


# Telemetry a fan-out needs after every clone has finished, but which each clone
# deletes when it finalizes. Copied to the run root first — see archive_fanout().
ARCHIVE = ("events", "counters", "gate-log.tsv")


def _merge_file(src: pathlib.Path, dst: pathlib.Path, header: bool = False) -> None:
    """Append to `dst` whatever `src` holds that `dst` does not.

    Hooks keep writing after a clear, so `src` may be a fresh file, a grown one,
    or one already archived. Both files are append-only: find the longest tail
    of `dst` that is also the head of `src`, and append the rest of `src`.

      overlap          meaning                           appended
      ---------------  --------------------------------  ----------------
      all of dst       src only grew since last archive  src's new lines
      all of src       src is already archived           nothing
      part of each     archived, grew, never cleared     src's new lines
      none             src was recreated after a clear   all of src

    Whole lines are compared, so a half-written last line matches nothing.
    """
    if not dst.exists():
        shutil.copy2(src, dst)
        return
    new = src.read_bytes().splitlines(keepends=True)
    old_raw = dst.read_bytes()
    old = old_raw.splitlines(keepends=True)
    # A recreated TSV starts with its column row again; one is enough.
    if header and new and old and new[0] == old[0]:
        new = new[1:]
    overlap = 0
    if old and new:
        last = old[-1]
        for k in range(min(len(old), len(new)), 0, -1):
            if new[k - 1] == last and old[-k:] == new[:k]:
                overlap = k
                break
    rest = new[overlap:]
    if not rest:
        return
    with open(dst, "ab") as f:
        if old_raw and not old_raw.endswith(b"\n"):
            f.write(b"\n")
        f.writelines(rest)


def _merge_counter(src: pathlib.Path, dst: pathlib.Path) -> None:
    """A counter is one integer that restarts at zero after a clear. Keep the
    larger, so a short post-clear tail does not replace the cycle's real count."""
    def val(path: pathlib.Path) -> int:
        try:
            return int(path.read_text().strip() or "0")
        except (OSError, ValueError):
            return -1
    if not dst.exists() or val(src) >= val(dst):
        shutil.copy2(src, dst)


def archive_fanout(target: pathlib.Path, preview: bool = False) -> str:
    """Copy a fan-out clone's telemetry to the run root before clearing it.

    Phase 4A aggregates a cycle's own telemetry into its run report before
    finalize, so deleting it afterwards is right for a single cycle. It is wrong
    for a fan-out: the cross-clone questions — peak concurrent agents, whether the
    machine was saturated — can only be asked once every clone has finished, and by
    then two of three have cleared themselves. Fan-out 1 could not answer that
    because events went to the wrong repo; fan-out 2 could not because they were
    deleted (evidence-run2 F4).

    Best-effort and silent on failure: a janitor that refuses to clean because it
    could not copy would be worse than the thing it is guarding against.
    """
    marker = target / ".fanout-clone"
    if not marker.is_file():
        return ""          # solo cycle: nothing to archive, and that is not a failure
    fields = {}
    try:
        for line in marker.read_text(errors="replace").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                fields[k.strip()] = v.strip()
    except OSError:
        return ""
    gate_log = fields.get("gate_log")
    if not gate_log:
        return "!marker names no gate_log — cannot locate the run root"
    run_root = pathlib.Path(gate_log).parent
    if not run_root.is_dir():
        return f"!run root {run_root} does not exist"
    dest = run_root / "telemetry" / (fields.get("clone") or target.parent.name)
    if preview:
        return f"~would archive to {dest}"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for name in ARCHIVE:
            src = target / name
            if src.is_symlink():
                continue
            if src.is_dir():
                merge = _merge_counter if name == "counters" else _merge_file
                for f in sorted(src.rglob("*")):
                    if f.is_symlink() or not f.is_file():
                        continue
                    out = dest / name / f.relative_to(src)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    merge(f, out)
            elif src.is_file():
                _merge_file(src, dest / name, header=name.endswith(".tsv"))
    except OSError as exc:
        return f"!could not archive to {dest}: {exc}"
    return str(dest)


def target_dir() -> pathlib.Path:
    """agent_states/ at the root of the git repo we are being run inside.

    Deliberately NOT derived from __file__: skills are commonly deployed by
    symlinking a central framework checkout into ~/.claude/skills, so __file__
    resolves to the framework repo rather than the project being cleaned.

    The git root is the tightest bound available that is still correct: it can
    only ever name a real repository the caller is already inside, and the
    scope checks in main() still require the result to be a non-symlink
    directory named agent_states holding only known entries.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return pathlib.Path(out.stdout.strip()).resolve() / "agent_states"
    except (OSError, subprocess.SubprocessError):
        pass
    # Not a git repo (or no git): fall back to the deployment layout.
    return pathlib.Path(__file__).resolve().parents[3] / "agent_states"


def refuse(msg: str) -> None:
    print(f"clear-agent-states: refusing — {msg}", file=sys.stderr)
    sys.exit(1)


def feature_of(path: pathlib.Path) -> str:
    """`cycle-state-<feature>.md` -> `<feature>`."""
    name = path.stem
    return name[len("cycle-state-"):] if name.startswith("cycle-state-") else name


def report_exists(root: pathlib.Path, feature: str) -> bool:
    """True when cycle_reports/ holds a report for this feature.

    The framework writes `cycle_reports/<feature>-<date>.md`, so anchor on the
    prefix rather than a bare substring — `auth` must not match `auth-refactor`.
    cycle_reports/ is often a symlink into a shared vault; that resolves fine.
    """
    if not feature:
        return False
    d = root / "cycle_reports"
    try:
        if not d.is_dir():
            return False
        return any(f.name.startswith(feature) for f in d.iterdir())
    except OSError:
        return False


def state_is_live(path: pathlib.Path, root: pathlib.Path) -> tuple[bool, str]:
    """(is_live, reason). Keeping is the safe default — see FINISHED_STATUSES."""
    feature = feature_of(path)
    if report_exists(root, feature):
        return False, "cycle report exists"
    try:
        for line in path.read_text(errors="replace").splitlines()[:20]:
            stripped = line.strip().lstrip("*# ").rstrip()
            low = stripped.lower()
            if not low.startswith("status:"):
                continue
            value = stripped.split(":", 1)[1].strip().strip("*_` ").lower()
            # The value must *be* a terminal word, not merely contain one.
            if value in FINISHED_STATUSES:
                return False, f"status: {value}"
            return True, f"status: {value[:40] or 'empty'}"
    except OSError:
        return True, "unreadable"
    return True, "no Status line"


def clear_task_files(root: pathlib.Path, dry_run: bool) -> tuple[list[str], list[str]]:
    """Delete `agent_tasks/tasks-*.md` — runtime state that nothing else owns.

    A second fixed target, and deliberately not an argument: the scope property
    that makes this script safe is that no invocation can point it anywhere, and
    that holds for two hard-coded paths as well as for one.

    The task file is gitignored runtime state the orchestrator ticks through a
    cycle, and until now nothing deleted it. Under a fan-out the clone is swept
    and it goes with it; outside one it accumulated per cycle, forever
    (evidence-run5 J5). Only `tasks-*.md` directly inside `agent_tasks/` — PRDs
    and reports live there too and are not runtime.
    """
    removed, failed = [], []
    d = root / "agent_tasks"
    if d.is_symlink() or not d.is_dir():
        return removed, failed
    for entry in sorted(d.glob("tasks-*.md")):
        if entry.is_symlink() or not entry.is_file():
            continue
        try:
            entry.resolve().relative_to(d.resolve())
        except ValueError:
            continue
        if dry_run:
            removed.append(f"agent_tasks/{entry.name}")
            continue
        try:
            entry.unlink()
            removed.append(f"agent_tasks/{entry.name}")
        except Exception as exc:
            failed.append(f"agent_tasks/{entry.name}: {exc}")
    return removed, failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true",
                    help="also delete cycle-state files for runs that are not marked finished")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be deleted and exit without deleting")
    ap.add_argument("--archive-only", action="store_true",
                    help="copy a fan-out clone's telemetry to the run root and delete nothing")
    args = ap.parse_args()

    target = target_dir()

    # Scope checks. Each one is a reason the permission glob could not be trusted.
    if target.name != "agent_states":
        refuse(f"resolved target is not named agent_states: {target}")
    if target.is_symlink():
        refuse(f"{target} is a symlink")
    if not target.is_dir():
        print(f"clear-agent-states: nothing to do — {target} does not exist")
        return 0

    # Copy telemetry to the run root and delete nothing. `reap-clones.sh sweep`
    # calls this before it removes a clone.
    if args.archive_only:
        archived = archive_fanout(target)
        if archived.startswith("!"):
            print(f"clear-agent-states: telemetry NOT archived — {archived[1:]}",
                  file=sys.stderr)
            return 2
        print(f"clear-agent-states: archived telemetry → {archived}" if archived
              else "clear-agent-states: not a fan-out clone — nothing to archive")
        return 0

    # A dry run performs no archive — copying is a side effect — but it should still
    # tell you whether one *would* work. A malformed marker discovered on the real,
    # irreversible run is discovered too late.
    archived = archive_fanout(target, preview=True) if args.dry_run else archive_fanout(target)

    removed: list[str] = []
    kept: list[str] = []
    failed: list[str] = []

    for entry in sorted(target.iterdir()):
        if entry.name in PRESERVED_FILES:
            kept.append(f"{entry.name} (run provenance — never cleared)")
            continue
        # Never escape the tree: reject anything that does not resolve inside it,
        # and never follow a symlink out.
        if entry.is_symlink():
            kept.append(f"{entry.name} (symlink — not followed)")
            continue
        try:
            entry.resolve().relative_to(target.resolve())
        except ValueError:
            kept.append(f"{entry.name} (resolves outside agent_states)")
            continue

        if entry.is_dir():
            if entry.name not in EPHEMERAL_DIRS:
                kept.append(f"{entry.name}/ (not a known ephemeral directory)")
                continue
        elif entry.name.startswith("cycle-state") and not args.all:
            live, why = state_is_live(entry, target.parent)
            if live:
                kept.append(f"{entry.name} ({why} — not finished; use --all to force)")
                continue

        if args.dry_run:
            removed.append(entry.name + ("/" if entry.is_dir() else ""))
            continue
        try:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            removed.append(entry.name)
        except OSError as exc:
            failed.append(f"{entry.name}: {exc}")

    t_removed, t_failed = clear_task_files(target.parent, args.dry_run)
    removed += t_removed
    failed += t_failed

    verb = "would delete" if args.dry_run else "deleted"
    print(f"clear-agent-states: {target}")
    # A silent failure here is indistinguishable from "this was not a fan-out
    # clone", and the difference is whether a run's only cross-clone evidence just
    # went in the bin. Say which.
    archive_failed = archived.startswith("!")
    if archive_failed:
        print(f"  ! telemetry NOT archived — {archived[1:]}", file=sys.stderr)
        print("  ! this clone's events are about to be deleted unarchived", file=sys.stderr)
    elif archived.startswith("~"):
        print(f"  {archived[1:]}")
    elif archived:
        print(f"  archived telemetry → {archived}")
    print(f"  {verb}: {', '.join(removed) if removed else '(nothing)'}")
    if kept:
        print(f"  kept: {'; '.join(kept)}")
    # The session is still running and its hooks still fire, so files reappear
    # here within seconds — the finalize agent's own tool calls, then the
    # orchestrator's for the remaining steps. That is real telemetry for real
    # work, not a cleanup failure, and it is why this reports what it removed
    # rather than claiming the directory is empty. Measured in fan-out 5 (J5):
    # FINALIZE said it had deleted counters/, events/ and gate-log.tsv, and all
    # three existed again seconds later, which read as the cleanup not working.
    #
    # Silencing the hooks afterwards was the obvious alternative and is worse: a
    # sentinel that outlives its window stops the *next* cycle recording anything,
    # and a telemetry outage is far more expensive than a few leftover files. What
    # remains is removed with the clone by `reap-clones.sh sweep` under a fan-out,
    # and by the next cycle's clear outside one.
    print("  note: this session keeps running, so its hooks will write here again "
          "before the cycle ends — that is expected, not a failed cleanup")
    if failed:
        print(f"  FAILED: {'; '.join(failed)}", file=sys.stderr)
        return 2
    # A lost archive is a partial failure too. Printing to stderr is visible to a
    # human reading a transcript and invisible to anything that checks an exit
    # code — which is the one signal a caller actually gates on.
    if archive_failed:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
