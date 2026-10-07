#!/usr/bin/env bash
# publish-branch.sh — push the current cycle branch and dispatch its CI run.
#
# Exists because the permission layer cannot express this grant. MyApp already
# allows `Bash(git push -u origin HEAD)` and `Bash(git add *)`, and both were
# prompted anyway all through fan-out 4: agents working inside a clone prefix
# their commands with `cd <clone>`, and a compound command matches no prefix
# grant. Measured: 18.5h of dialog wait across 6 asks in one run — 8h03m, 7h13m
# and 2h57m on the three largest — against 1.6h of real gate wait. The same
# shape as the probe-12 `rm -f … && python3 …` denial.
#
# Widening the grant is the wrong trade, and for the same reason
# clear-agent-states.py exists: a glob permission is a string match against a
# command, satisfied by a `cd ..` first, a shell-expanded variable, or a
# refspec the author never pictured. `Bash(git push*)` grants `git push
# --force origin HEAD:develop`.
#
# A narrow allow would not have worked anyway. MyApp's settings carry
# `allow: Bash(git push -u origin HEAD)` *and* `ask: Bash(git push *)`, and a
# broad ask shadows a narrow allow — most-specific does not win, the same rule
# that stops clear-agent-states.py being replaced by `Bash(rm agent_states/*)`.
# So that push prompted on every cycle for two independent reasons, and removing
# the `cd` prefix would have fixed only one of them. This script's own path
# matches no ask or deny pattern, which is what actually makes it grantable.
#
# This script is the narrower boundary. It takes no argument that can widen its
# scope: the remote is always `origin`, the refspec is always `HEAD`, there is
# no force in any form, and it refuses outright on a detached HEAD or an
# integration branch. The only free argument is a workflow name, charset-checked
# and passed to `gh workflow run`, which cannot reach the filesystem.
#
#   publish-branch.sh push              # push current branch to origin
#   publish-branch.sh ci <workflow>     # push, dispatch CI, print the run id
#   publish-branch.sh --dry-run ...     # print what would run, change nothing
#
# `ci` prints the run id on stdout and nothing else there, so a caller can
# capture it directly. Empty stdout means the dispatch failed to produce a run
# attributable to this commit — treat that as a failed dispatch and fall back to
# a local suite run, exactly as the skill already says.
#
# Exit codes: 0 = done, 1 = refused, 2 = the operation failed.

set -u

PROG=publish-branch
DRY=0

say()  { printf '%s: %s\n' "$PROG" "$*" >&2; }
die()  { printf '%s: %s\n' "$PROG" "$*" >&2; exit 1; }
fail() { printf '%s: %s\n' "$PROG" "$*" >&2; exit 2; }

# Integration branches. Pushing a cycle's work onto one of these is the hazard a
# `Bash(git push*)` grant cannot see, so it is refused here rather than trusted
# to never be constructed. A person who genuinely means to push develop can do
# it by hand; that is the point of a scoped script.
is_integration() {
  case "$1" in
    main|master|develop|dev|staging|production|release|release/*|hotfix/*) return 0 ;;
    *) return 1 ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '3,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --) shift; break ;;
    -*) die "unknown option '$1'. Commands: push | ci <workflow>" ;;
    *) break ;;
  esac
done

CMD="${1:-}"
[ -n "$CMD" ] || die "no command. Usage: $PROG push | $PROG ci <workflow>"
shift

git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository."

# --show-current is empty on a detached HEAD, which is exactly the case worth
# refusing: `git push -u origin HEAD` from a detached HEAD pushes a commit under
# whatever name the remote infers, and no cycle should ever be in that state.
BR="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" || fail "could not read HEAD."
[ -n "$BR" ] && [ "$BR" != "HEAD" ] \
  || die "HEAD is detached. A cycle branch must be checked out by name."

is_integration "$BR" \
  && die "refusing to push integration branch '$BR'. This script publishes cycle
             branches only; push an integration branch by hand if you mean to."

git remote get-url origin >/dev/null 2>&1 || die "no 'origin' remote in this repository."

SHA="$(git rev-parse HEAD 2>/dev/null)" || fail "could not resolve HEAD sha."

do_push() {
  if [ "$DRY" = 1 ]; then
    say "would run: git push -u origin HEAD   (branch '$BR' @ ${SHA:0:8})"
    return 0
  fi
  git push -u origin HEAD >&2 || fail "git push failed for '$BR'."
  say "pushed '$BR' @ ${SHA:0:8} to origin"
}

case "$CMD" in
  push)
    [ $# -eq 0 ] || die "'push' takes no arguments."
    do_push
    ;;

  ci)
    WF="${1:-}"
    [ -n "$WF" ] || die "'ci' needs a workflow name, e.g. 'ci' ci.yml"
    shift
    [ $# -eq 0 ] || die "'ci' takes exactly one argument."
    # A workflow name reaches `gh`, not a shell, but keep it to the shape a
    # filename actually has so nothing else can be smuggled through.
    case "$WF" in
      *[!A-Za-z0-9._-]*) die "workflow name '$WF' has characters outside [A-Za-z0-9._-]." ;;
      .*|*/*) die "workflow name '$WF' must be a bare file name." ;;
    esac
    command -v gh >/dev/null 2>&1 || fail "gh is not installed."

    do_push

    # --ref, not `-f ref=`. `-f` passes a workflow *input*; it does not choose
    # the git ref the run is attributed to. Measured in fan-out 4: runs
    # 34440472289 and 34440473484 both came back headBranch=develop,
    # headSha=68e95e10 — the pre-cycle base — so the SHA-scoped lookup below
    # found nothing and every cycle silently fell back to a local suite run.
    # The workflow's own `inputs.ref || github.ref` checkout fallback means
    # --ref alone now selects the right code *and* reports it.
    if [ "$DRY" = 1 ]; then
      say "would run: gh workflow run $WF --ref $BR"
      say "would resolve the run id for $WF on '$BR' @ ${SHA:0:8}"
      exit 0
    fi

    gh workflow run "$WF" --ref "$BR" >&2 || fail "could not dispatch $WF on '$BR'."
    say "dispatched $WF on '$BR'"

    # GitHub does not create the run synchronously. Poll rather than sleeping a
    # fixed 8s: under fan-out three cycles dispatch within seconds of each other
    # and a fixed wait is either wasteful or short.
    RUN=""
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      sleep 3
      # Scope by branch AND head sha. An unscoped --limit 1 hands one cycle
      # another's run id, and that misattribution is silent: the agents would
      # poll a real, green run for a commit they never audited.
      RUN="$(gh run list --workflow="$WF" --branch "$BR" --limit 10 \
               --json databaseId,headSha \
               -q "[.[] | select(.headSha==\"$SHA\") | .databaseId] | max // empty" \
             2>/dev/null || true)"
      [ -n "$RUN" ] && break
    done

    if [ -z "$RUN" ]; then
      say "no run attributable to ${SHA:0:8} after 30s — treat as a failed dispatch"
      exit 0   # stdout stays empty; the caller falls back to a local suite run
    fi
    say "run id $RUN"
    printf '%s\n' "$RUN"
    ;;

  *)
    die "unknown command '$CMD'. Usage: $PROG push | $PROG ci <workflow>"
    ;;
esac
