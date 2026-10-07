#!/usr/bin/env bash
# reap-clones.sh — end-of-cycle teardown for fan-out clones.
#
# Two subcommands, because end-of-cycle teardown cannot be one action:
#
#   finish   run *inside* a clone at Finalize. Deletes regenerable build output
#            and marks the clone reapable. Does not remove the clone.
#   sweep    run from anywhere. Removes clones that `finish` marked, after
#            re-checking that nothing has changed since.
#
# The split exists because a cycle cannot remove the worktree its own shell is
# standing in. On macOS the unlink even succeeds, which is worse than failing:
# the session keeps running with a cwd that no longer exists and every later
# command fails against it. So the cycle shrinks and declares; something outside
# it removes.
#
# Shrinking is where nearly all of the win is. Measured on a fan-out 4 clone:
# 1.8G total, of which build/ is 1.5G and .dart_tool/ is 270M — the checkout
# itself is ~30M across 959 tracked files. `finish` reclaims ~98% immediately,
# from inside, with no worktree removal involved. That is what makes it safe to
# leave `sweep` human-triggered instead of running a daemon that polls GitHub:
# the husk left behind is 30M, so nothing is urgent.
#
# `sweep` is deliberately NOT merge-aware. Whether a PR merged is a fact about
# the PR, not about the clone — some branches are not merged for a long time and
# some never are, and a clone may not outlive either. The branch is what carries
# the work: a clone is a linked worktree, so its branch lives in the origin
# repository's .git and survives removal untouched. Removing a clone discards a
# checkout, never a commit.
#
# `sweep` is also not the launcher's reap and does not replace it.
# start-parallel-cycles.sh removes *every* clone under the root before a run,
# marked or not, because a cycle that crashed before Finalize leaves an unmarked
# clone that must not block the next launch. This sweep is the conservative
# between-runs pass: only what a cycle explicitly declared finished.
#
#   reap-clones.sh finish                  # inside a clone, at Finalize
#   reap-clones.sh sweep                   # list what would go, remove nothing
#   reap-clones.sh sweep --apply           # remove it
#   reap-clones.sh sweep --root <dir>      # default: the clones root of this clone
#
# Exit codes: 0 = done, 1 = refused, 2 = partial failure.

set -u

PROG=reap-clones
APPLY=0
ROOT=""

say()  { printf '%s: %s\n' "$PROG" "$*" >&2; }
die()  { printf '%s: %s\n' "$PROG" "$*" >&2; exit 1; }
fail() { printf '%s: %s\n' "$PROG" "$*" >&2; exit 2; }

MARKER_DIR=".reapable"
FANOUT_MARKER="agent_states/.fanout-clone"

# Regenerable build output, by directory name. Stack-agnostic on purpose: the
# framework core is language-neutral, so rather than encode one stack's layout
# this lists the usual suspects and then filters them — see below. A name here
# is a *candidate*, not a decision.
CANDIDATES="build .dart_tool node_modules target .gradle Pods DerivedData
__pycache__ .pytest_cache .venv obj bin .next dist .parcel-cache"

# ---------------------------------------------------------------- finish

cmd_finish() {
  git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository."
  TOP="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "could not resolve the work tree."
  TOP="$(cd "$TOP" && pwd -P)"

  # The whole script only ever acts on a fan-out clone. A normal checkout's
  # build output belongs to the person working in it, not to a cycle.
  [ -f "$TOP/$FANOUT_MARKER" ] \
    || die "$TOP is not a fan-out clone (no $FANOUT_MARKER). Nothing to do."

  BR="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" || fail "could not read HEAD."
  SHA="$(git rev-parse HEAD 2>/dev/null)" || fail "could not resolve HEAD sha."

  freed=0
  removed=""
  for name in $CANDIDATES; do
    d="$TOP/$name"
    # Never follow a symlink out of the tree, and never treat a file as a dir.
    [ -d "$d" ] || continue
    [ -L "$d" ] && { say "skipped $name (symlink)"; continue; }
    # The filter that makes the candidate list safe: delete only what git itself
    # says is ignored. Anything tracked, or untracked but not ignored, is
    # somebody's work — `bin/` and `obj/` are build output in one project and
    # committed source in another, and this is the check that tells them apart.
    git -C "$TOP" check-ignore -q "$name" 2>/dev/null \
      || { say "kept $name (not gitignored)"; continue; }
    sz="$(du -sk "$d" 2>/dev/null | awk '{print $1}')"; sz="${sz:-0}"
    if [ "$APPLY" = 0 ]; then
      say "would delete $name ($((sz/1024))M)"
    else
      rm -rf -- "$d" 2>/dev/null || { say "could not delete $name"; continue; }
      say "deleted $name ($((sz/1024))M)"
    fi
    freed=$((freed+sz))
    removed="$removed $name"
  done

  # agent_states is gitignored too, and is deliberately not a candidate: it is
  # the cycle's own telemetry and clear-agent-states.py owns its lifecycle.

  ROOT_P="$(dirname "$TOP")"
  MD="$ROOT_P/$MARKER_DIR"
  CLONE="$(basename "$TOP")"

  if [ "$APPLY" = 0 ]; then
    say "would mark $CLONE reapable in $MD"
    say "would reclaim $((freed/1024))M"
    return 0
  fi

  mkdir -p "$MD" 2>/dev/null || fail "could not create $MD"
  # The marker lives at the clones root, not inside the clone, so that it
  # survives anything done to the clone afterwards and `sweep` can enumerate
  # finished cycles without entering each one. The head sha is the interesting
  # field: `sweep` re-checks it, so a clone that gained a commit after Finalize
  # is no longer the clone that was declared done.
  printf '{"clone":"%s","branch":"%s","head":"%s","finished_at":"%s","freed_kb":%s}\n' \
    "$CLONE" "$BR" "$SHA" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$freed" \
    > "$MD/$CLONE.json" || fail "could not write the reapable marker."

  say "marked $CLONE reapable ($BR @ ${SHA:0:8})"
  say "reclaimed $((freed/1024))M; the clone is now a ~30M husk awaiting sweep"
}

# ---------------------------------------------------------------- sweep

# Processes attached to a path. Match on the path, then follow children: the
# clone path appears in a terminal's argv but not in the session's own —
# `claude "/cycle 442"` carries no directory — so matching alone reports
# terminal plumbing and hides the live session inside it.
holders_of() {
  local p="$1" h kids all=""
  all="$(pgrep -f "$p" 2>/dev/null || true)"
  for h in $all; do
    kids="$(pgrep -P "$h" 2>/dev/null || true)"
    [ -n "$kids" ] && all="$all
$kids"
  done
  printf '%s\n' "$all" | grep -v '^$' | sort -u || true
}

cmd_sweep() {
  if [ -z "$ROOT" ]; then
    git rev-parse --git-dir >/dev/null 2>&1 \
      || die "no --root given and not inside a repository."
    TOP="$(cd "$(git rev-parse --show-toplevel)" && pwd -P)"
    [ -f "$TOP/$FANOUT_MARKER" ] \
      || die "no --root given and this is not a fan-out clone. Pass --root <clones-root>."
    ROOT="$(dirname "$TOP")"
  fi
  ROOT_P="$(cd "$ROOT" 2>/dev/null && pwd -P)" || die "--root '$ROOT' does not exist."
  MD="$ROOT_P/$MARKER_DIR"

  [ -d "$MD" ] || { say "no $MARKER_DIR/ under $ROOT_P — nothing has been marked finished."; exit 0; }

  # Two passes, as in the launcher's reap: check everything before removing
  # anything, so a refusal leaves the previous state intact rather than
  # half-swept, and the operator can fix the one clone and re-run.
  CANDS=()
  for m in "$MD"/*.json; do
    [ -e "$m" ] || continue
    CLONE="$(basename "$m" .json)"
    WT="$ROOT_P/$CLONE"

    if [ ! -d "$WT" ]; then
      say "$CLONE: already gone — dropping its marker"
      [ "$APPLY" = 1 ] && rm -f -- "$m"
      continue
    fi

    WANT="$(sed -n 's/.*"head":"\([0-9a-f]*\)".*/\1/p' "$m")"
    HAVE="$(git -C "$WT" rev-parse HEAD 2>/dev/null || true)"
    # Accept a descendant, not only an exact match. The marked commit is the
    # cycle's state when it declared itself finished; commits *on top of* it are
    # the same line of work carried forward, and refusing them refuses the normal
    # case. Measured in fan-out 5 (J3): c1 was skipped because the changelog
    # fragment lands after Finalize, and two sibling clones committed theirs
    # before it — same skill, same mode, two orderings.
    #
    # An unrelated tree is still refused: --is-ancestor is false for anything
    # that does not descend from the marked commit, which is the property that
    # matters. A rewritten history fails it too, correctly.
    if [ -z "$WANT" ] || [ -z "$HAVE" ]; then
      say "$CLONE: SKIP — cannot resolve HEAD (marked ${WANT:0:8}, now ${HAVE:0:8})"
      continue
    fi
    if [ "$WANT" != "$HAVE" ] \
       && ! git -C "$WT" merge-base --is-ancestor "$WANT" "$HAVE" 2>/dev/null; then
      say "$CLONE: SKIP — HEAD is not a descendant of the finished commit (marked ${WANT:0:8}, now ${HAVE:0:8})"
      continue
    fi

    # Same exclusion the launcher uses: agent_states is framework scratch the
    # cycle owns, and the fan-out marker itself lives in it.
    if [ -n "$(git -C "$WT" status --porcelain -- ':!agent_states' 2>/dev/null)" ]; then
      say "$CLONE: SKIP — uncommitted changes. Commit or discard them first."
      continue
    fi

    H="$(holders_of "$WT")"
    if [ -n "$H" ]; then
      say "$CLONE: SKIP — processes still attached:"
      # shellcheck disable=SC2086
      ps -o pid=,etime=,command= -p $(echo "$H" | tr '\n' ' ') 2>/dev/null \
        | cut -c1-140 | sed 's/^/      /' >&2
      continue
    fi

    CANDS+=("$CLONE")
  done

  [ ${#CANDS[@]} -eq 0 ] && { say "nothing to sweep."; exit 0; }

  if [ "$APPLY" = 0 ]; then
    for c in "${CANDS[@]}"; do say "would remove $ROOT_P/$c"; done
    say "${#CANDS[@]} clone(s) ready. Re-run with --apply to remove them."
    exit 0
  fi

  n=0
  for c in "${CANDS[@]}"; do
    WT="$ROOT_P/$c"
    # Ask the worktree itself which repository owns it, rather than assuming.
    OWNER="$(git -C "$WT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
    OWNER="$(dirname "${OWNER:-}")"
    if [ -n "$OWNER" ] && [ -d "$OWNER" ]; then
      git -C "$OWNER" worktree remove --force "$WT" 2>/dev/null \
        || { say "could not remove $c — remove it by hand."; continue; }
      git -C "$OWNER" worktree prune 2>/dev/null
    else
      say "could not find the owning repository for $c — left in place."
      continue
    fi
    rm -f -- "$MD/$c.json"
    say "removed $c"
    n=$((n+1))
  done
  say "swept $n clone(s) from $ROOT_P"
}

# ---------------------------------------------------------------- args

CMD=""
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    --root) ROOT="${2:-}"; [ -n "$ROOT" ] || die "--root needs a directory."; shift 2 ;;
    -h|--help) sed -n '3,40p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) die "unknown option '$1'. Commands: finish | sweep" ;;
    *) [ -z "$CMD" ] || die "unexpected argument '$1'."; CMD="$1"; shift ;;
  esac
done

case "$CMD" in
  finish) cmd_finish ;;
  sweep)  cmd_sweep ;;
  "")     die "no command. Usage: $PROG finish | $PROG sweep [--apply]" ;;
  *)      die "unknown command '$CMD'. Usage: $PROG finish | $PROG sweep [--apply]" ;;
esac
