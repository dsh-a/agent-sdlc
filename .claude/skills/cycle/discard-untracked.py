#!/usr/bin/env python3
"""Delete a throwaway file an agent created, and refuse anything else.

`/refine` Step 2b tells the agent to prove a mechanism by running it and to
"delete it in the same step that records its output". It never said how, and the
two commands that look like they would work are both wrong:

  * `rm` is denied outright in every deployment, for good reason.
  * `git clean -f` asks, and widening that is not an option — a broad `ask`
    shadows a narrower `allow` (see `settings.json.sample` § permissions), so
    there is no safe subset to grant. It is also the wrong tool: it removes
    every untracked non-ignored file under its target, which in a Phase-3 clone
    is the new source an implementation agent has written and not yet committed.
    That work is in no commit and no stash. There is no recovery.

Measured cost of leaving the gap: `git clean -f` with an absolute path stalled a
fan-out clone for 3m39s waiting on a dialog (fan-out 6, recorded in every
implementation agent's body), and a probe that outlived its pass reached a real
repo as `test/zz_probe_529_test.dart` — inside the test glob, where a bare test
run sweeps it and one `git add -A` commits it.

So this is the scoped script the framework's own rule asks for: it takes a path,
resolves it itself, and refuses every path that is not unambiguously a
throwaway. A glob permission is a string match on a command and can be widened
by a `cd ..`, a symlink or a shell variable; a script that re-derives the facts
cannot.

**Refuses unless every named path is all of these:**

  inside the work tree   resolved, with symlinks followed — a link pointing out
                         of the repo is refused, not followed
  a regular file         never a directory. Deleting a tree is not a throwaway
                         operation and `-d` is the flag that turned `git clean`
                         into a footgun
  untracked              a tracked file belongs to a commit; `git checkout --`
                         restores it, which is a different and reversible job
  not ignored            ignored does NOT mean disposable. `.env`,
                         `models.yml` and every local credential file is
                         ignored. `git clean -f` leaves them alone and so does
                         this

Checked in two passes: every path is validated before any is removed, so a
refusal leaves the tree exactly as it was rather than half-cleaned.

Dry by default, like every outward-facing operation here. `--apply` removes.

    discard-untracked.py test/zz_probe_529_test.dart           # print, remove nothing
    discard-untracked.py test/zz_probe_529_test.dart --apply

Exit: 0 removed (or would remove), 1 nothing to do, 2 refused — nothing removed.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys


def git(*args: str, cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def work_tree() -> pathlib.Path | None:
    r = git("rev-parse", "--show-toplevel")
    if r.returncode != 0:
        return None
    return pathlib.Path(r.stdout.strip()).resolve()


def classify(p: str, root: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """(path, "") when discardable, else (None, why not)."""
    raw = pathlib.Path(p)
    # Resolve before every other test. A relative path, a `..` segment and a
    # symlink all have to collapse to one real location first, or each check
    # below is answering a question about a different file than the one that
    # would be unlinked.
    try:
        full = raw.resolve()
    except OSError as exc:
        return None, f"cannot resolve: {exc}"

    try:
        full.relative_to(root)
    except ValueError:
        return None, f"outside the work tree ({root})"

    if not full.exists():
        return None, "does not exist"
    if full.is_dir():
        return None, "is a directory — this removes files, never trees"
    if not full.is_file():
        return None, "is not a regular file"

    rel = full.relative_to(root).as_posix()

    if git("ls-files", "--error-unmatch", "--", rel, cwd=root).returncode == 0:
        return None, "is tracked — use `git checkout -- <path>` to restore it instead"

    # `check-ignore` exits 0 when the path IS ignored. Ignored is not the same as
    # disposable: .env and every local credential file is ignored.
    if git("check-ignore", "-q", "--", rel, cwd=root).returncode == 0:
        return None, "is git-ignored — ignored files are local config, not throwaways"

    return full, ""


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Delete an untracked throwaway file. Refuses anything else.")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--apply", action="store_true",
                    help="actually remove; without it nothing is deleted")
    args = ap.parse_args()

    root = work_tree()
    if root is None:
        print("discard-untracked: REFUSING — not inside a git work tree", file=sys.stderr)
        return 2

    ok: list[pathlib.Path] = []
    refused: list[str] = []
    for p in args.paths:
        full, why = classify(p, root)
        if full is None:
            refused.append(f"{p}: {why}")
        else:
            ok.append(full)

    # Two passes: refuse before removing anything. A partial clean is worse than
    # none, because the operator then has to work out which half ran.
    if refused:
        print("discard-untracked: REFUSING — nothing was removed:", file=sys.stderr)
        for r in refused:
            print(f"    {r}", file=sys.stderr)
        return 2

    if not ok:
        print("discard-untracked: nothing to do")
        return 1

    verb = "removed" if args.apply else "would remove"
    for full in ok:
        if args.apply:
            try:
                full.unlink()
            except OSError as exc:
                print(f"discard-untracked: failed to remove {full}: {exc}", file=sys.stderr)
                return 2
        print(f"  {verb} {full.relative_to(root).as_posix()}")
    if not args.apply:
        print("discard-untracked: dry run — pass --apply to remove")
    return 0


if __name__ == "__main__":
    sys.exit(main())
