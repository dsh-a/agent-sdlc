#!/usr/bin/env python3
"""prune-analyzer-baselines.py — remove stale analyzer baselines from cycle_reports/.

The analyzer baseline is scratch for one cycle: written at Phase 3 start, read once
at Phase 4A, meaningless after. It used to be written into
`cycle_reports/<feature>/analyzer-baseline.txt`, which is a permanent record and,
with a vault configured, a shared one. Nothing consumed it and § Report archival
never prunes a vault, so it accumulated — one deployment reached 61 files (~159 KB)
across 61 directories, in a repo holding several applications' history. The cost is
permanence and noise rather than disk.

The cycle skill now writes it to `agent_states/`. This clears what the old path
left behind. Needed once per deployment that ran with `analyzer_baseline` enabled.

**`cycle_reports/<feature>/` is not itself the mistake.** Supervisor whispers and
escalations archive there at cycle end, and stall-salvage artifacts live there too —
those are records and must survive. So this deletes *only* files named exactly
`analyzer-baseline.txt`, and removes a feature directory afterwards only with
`rmdir`, which fails on a non-empty directory. That is the safety property: a
directory holding anything else is structurally protected, not protected by this
script having listed the right exceptions.

Dry run is the DEFAULT here, unlike `clear-agent-states.py`. That script empties an
ephemeral directory; this one edits a permanent, shared record, so acting requires
saying so.

    prune-analyzer-baselines.py            # report what would go
    prune-analyzer-baselines.py --apply    # delete

Exit codes: 0 = done (or nothing to do), 1 = refused, 2 = partial failure.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

TARGET_NAME = "cycle_reports"
SCRATCH = "analyzer-baseline.txt"


def reports_dir() -> pathlib.Path | None:
    """`<git-root>/cycle_reports`, resolved. None when not inside a git repo.

    Resolving is the point: cycle_reports is normally a symlink into a shared vault,
    and the vault is where the litter is. Note that the resolved name is NOT
    `cycle_reports` in a real deployment — myapp's points at
    `myapp-docs/cycle_reports/<app_slug>`, so the last segment is the app slug. The
    safety guarantee therefore cannot come from the resolved name; it comes from
    deriving the path only as `<git-root>/cycle_reports`, deleting only files named
    exactly `analyzer-baseline.txt` one level down, and removing directories with
    `rmdir`, which refuses a non-empty one.

    Not in a git repo -> None, rather than guessing from the working directory. A
    deletion tool should not improvise its own target.
    """
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            link = pathlib.Path(out.stdout.strip()) / TARGET_NAME
            return link.resolve() if link.exists() else link
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def refuse(msg: str) -> None:
    print(f"prune-analyzer-baselines: refusing — {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="actually delete (default is to report only)")
    args = ap.parse_args()

    target = reports_dir()
    if target is None:
        refuse("not inside a git repository — cannot locate cycle_reports/ safely")
    if not target.is_dir():
        print(f"prune-analyzer-baselines: nothing to do — {target} does not exist")
        return 0

    found: list[tuple[pathlib.Path, int]] = []
    for entry in sorted(target.iterdir()):
        if not entry.is_dir() or entry.is_symlink():
            continue
        f = entry / SCRATCH
        # Depth is exactly one, and it must be a real file — never a link out.
        if f.is_file() and not f.is_symlink():
            try:
                found.append((f, f.stat().st_size))
            except OSError:
                found.append((f, 0))

    if not found:
        print(f"prune-analyzer-baselines: nothing to do — no {SCRATCH} under {target}")
        return 0

    total = sum(size for _, size in found)
    print(f"prune-analyzer-baselines: {target}")
    print(f"  {len(found)} {SCRATCH} file(s), {total / 1024:.0f} KB")

    if not args.apply:
        for f, _ in found[:5]:
            print(f"    would delete  {f.parent.name}/{f.name}")
        if len(found) > 5:
            print(f"    … and {len(found) - 5} more")
        print("  Dry run. Re-run with --apply to delete. Feature directories holding "
              "anything else (salvage artifacts, supervisor archives) are kept.")
        return 0

    removed = failed = pruned = 0
    kept: list[str] = []
    for f, _ in found:
        try:
            f.unlink()
            removed += 1
        except OSError as exc:
            print(f"  FAILED {f}: {exc}", file=sys.stderr)
            failed += 1
            continue
        try:
            # rmdir, never rmtree: it refuses a non-empty directory, which is what
            # protects a feature dir that also holds real records.
            f.parent.rmdir()
            pruned += 1
        except OSError:
            kept.append(f.parent.name)

    print(f"  deleted {removed} file(s), removed {pruned} empty directory(ies)")
    if kept:
        print(f"  kept {len(kept)} directory(ies) holding other records: "
              f"{', '.join(sorted(kept)[:5])}{' …' if len(kept) > 5 else ''}")
    if failed:
        return 2
    print("  Commit and push the vault if it is a git repository.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
