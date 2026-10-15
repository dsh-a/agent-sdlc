#!/usr/bin/env bash
# start-parallel-cycles.sh — set up and launch N parallel /cycle runs, one pool slot each.
#
# The entry point behind `/cycle --parallel <issue> <issue> ...`. Parallelism that
# needs nine hand-typed commands is not a feature; this is the one command.
#
# What it does, in order:
#   1. Preflight — refuses unless the tree is genuinely quiet (see CONTRACT below)
#   2. One pool slot per issue (<clones-root>/<repo>-slot-K, K up to parallel_slots in
#      .omp/agent-config.md § Cycle Options). An existing slot is reset to the base in
#      place, keeping its ignored build output; a missing one is created detached, via
#      `omp worktree add` (preserves origin so gh works), or `git worktree add` +
#      deploy.sh link where omp is not installed or --cloner git. With sparse_clones
#      on, a slot checks out only the directories sparse-set.py derives from its
#      story's ## Slices, new slots come from git, and a slot without slices is full
#   3. Clears each slot's agent_states/
#   4. Claims each issue by assignment
#   5. Records framework SHA + disk baseline, initialises the gate log
#   6. Opens a terminal per clone running the cycle
#
# CONTRACT — this script REFUSES loudly and exits non-zero when a precondition fails.
# Proceeding from a dirty or busy tree does not degrade the run, it contaminates it:
# a clone copies the working tree, uncommitted changes included.
#
# Local work happens before remote work: clones are created before issues are claimed,
# so a failure part-way leaves nothing assigned on GitHub. Nothing is ever auto-deleted
# — on failure it reports exactly what exists and stops.
#
# Usage:
#   start-parallel-cycles.sh 419 404 378
#   start-parallel-cycles.sh --dry-run 419 404 378
#   start-parallel-cycles.sh --no-launch 419 404 378     # set up, print commands, don't open windows
#   start-parallel-cycles.sh --harness omp 419 404
#   start-parallel-cycles.sh --cloner git 419 404         # plain git worktrees, omp or not
#   start-parallel-cycles.sh --fresh 419 404              # recreate every slot from scratch
#
# Flags: --repo DIR --base BRANCH --clones-root DIR --harness claude|omp
#        --cloner git|omp  clone mechanism (default: omp when installed, else git)
#        --fresh        remove every pool slot and create the ones this run uses
#        --mode full|lean|hotfix   override every story's Depth (normally omitted)
#        --max-agents N --windows
#        --awake H      inhibit system sleep for H hours (default 8; 0 = off)
#        --no-awake     do not inhibit system sleep
#        --stop-awake   end a running sleep inhibitor and exit
#        --no-reap --no-sync --dry-run --no-launch --no-claim
#
# Reusing the pool, reaping clones under the root that are not pool slots, and
# fast-forwarding the base are ON by default, because each is something this
# script would otherwise simply refuse over, and making the operator fix by hand
# what the script can verify and fix itself is the "remembered ritual" failure.
#
# None of them improvises. Every slot this run resets or removes, and every clone
# it reaps, is checked before any is touched; uncommitted work (untracked files
# included), an unfinished merge/rebase/cherry-pick, commits only a detached HEAD
# reaches, or an attached session stops the run with nothing changed. A slot's
# feature branch lives in the repo and is never deleted. --sync refuses a dirty
# tree and takes only a fast-forward. --no-reap leaves clones outside the pool in
# place (the run then refuses over them); --no-sync leaves the base as it is.
#
# More issues than parallel_slots stops before any change. Disk use is fixed at
# the pool: N × (checkout + build output); the launch prints it.
#
# --mode is OPTIONAL and overrides every story's own depth. Leave it off: each
# issue carries a `Depth` board field (full|lean|hotfix) set by /refine, so a
# bundle can mix depths and every clone gets the one its story was refined to.
# Preflight refuses if the board has the field and an issue has no value, rather
# than letting N clones park on a question at Phase 1A.
#
# Pass --mode only for a deliberately uniform measured run. --mode hotfix is
# refused for more than one issue: it skips Gate 1, Gate 2 and review, and forces
# verify to lite — which also skips verify's falsification re-run. A fan-out in
# hotfix mode exercises almost none of the machinery a fan-out is usually run to
# observe.
#
# Cycles open as tabs in the current window where the terminal supports it
# (Ghostty); --windows forces separate windows.
#
# --max-agents is advisory only — it prints an instruction for you to pass on, and
# nothing under Claude Code enforces it. Omit it to run uncapped (the default).
set -uo pipefail

# MAX_AGENTS is deliberately EMPTY by default: uncapped is what fan-out actually
# runs, and a default cap would silently contaminate the uncapped baseline a cap
# is evaluated against.
REPO="" BASE="" ROOT="$HOME/dev/cycles" HARNESS="claude" MAX_AGENTS="" MODE="" TABS=1
REAP=1 SYNC=1 AWAKE_HOURS=8 STOP_AWAKE=0 CLONER="" FRESH=0
DRY=0 LAUNCH=1 CLAIM=1 ISSUES=()

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --base) BASE="${2:-}"; shift 2 ;;
    --clones-root) ROOT="${2:-}"; shift 2 ;;
    --harness) HARNESS="${2:-}"; shift 2 ;;
    --cloner) CLONER="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --windows) TABS=0; shift ;;
    --awake) AWAKE_HOURS="${2:-8}"; shift 2 ;;
    --no-awake) AWAKE_HOURS=0; shift ;;
    --stop-awake) STOP_AWAKE=1; shift ;;
    --reap) REAP=1; shift ;;          # accepted for explicitness; already the default
    --sync) SYNC=1; shift ;;
    --no-reap) REAP=0; shift ;;
    --fresh) FRESH=1; shift ;;
    --no-sync) SYNC=0; shift ;;
    --max-agents) MAX_AGENTS="${2:-}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --no-launch) LAUNCH=0; shift ;;
    --no-claim) CLAIM=0; shift ;;
    -h|--help) awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; exit 0 ;;
    -*) echo "start-parallel-cycles: unknown flag '$1'" >&2; exit 2 ;;
    *) ISSUES+=("$1"); shift ;;
  esac
done



die() { printf 'start-parallel-cycles: REFUSING — %s\n' "$*" >&2; exit 1; }
say() { printf '  %s\n' "$*"; }
step() { printf '\n▸ %s\n' "$*"; }
# A word for a printed command, quoted so it pastes into bash or zsh as one
# argument: a path with a space or a quote is single-quoted, a plain one is not.
q() {
  local sq="'\\''"
  case "$1" in
    ''|*[!A-Za-z0-9_./:@%+=,-]*) printf "'%s'" "${1//\'/$sq}" ;;
    *) printf '%s' "$1" ;;
  esac
}
# A command's output as bash reads it: LF lines. See deploy.sh's strip_cr.
strip_cr() { "$@" | tr -d '\r'; return "${PIPESTATUS[0]}"; }
# The captured output of a failed step, indented to sit under a die message. Its
# last lines carry the error; CR is dropped so a Windows tool's lines print whole.
failed_output() { strip_cr printf '%s\n' "${1:-(no output)}" | tail -n 20 | sed 's/^/    /'; }

# The git operation a clone is in the middle of: merge, rebase, cherry-pick, or
# nothing. `.git` in a linked worktree is a *file* pointing at the real git dir,
# so `$wt/.git/MERGE_HEAD` finds nothing; ask git where its dir is.
# --absolute-git-dir, not a "starts with /" test: Git for Windows prints `C:/...`.
clone_op() {
  local gd
  gd="$(git -C "$1" rev-parse --absolute-git-dir 2>/dev/null)" || return 0
  if   [ -e "$gd/MERGE_HEAD" ];       then echo merge
  elif [ -d "$gd/rebase-merge" ] || [ -d "$gd/rebase-apply" ]; then echo rebase
  elif [ -e "$gd/CHERRY_PICK_HEAD" ]; then echo cherry-pick
  fi
}

# Why a leftover clone is dirty, in enough detail to act on.
#
# "Uncommitted changes" alone sends the operator to their own repo, which is
# clean, because that is the tree they were just working in; the path is a clones
# root they have no reason to be thinking about.
#
# So the report says three things: that this is a *clone* and not the repo, whose
# branch it is and how old, and — when git is mid-operation — the exact command
# that ends it. An interrupted merge, rebase or cherry-pick is
# the common case here, because that is what a cycle that died mid-Phase-4 leaves
# behind, and `--abort` is both the right answer and not the one that comes to
# mind when the message says "commit or discard".
dirty_clone_report() {
  local wt="$1" branch when n out op
  # A fan-out clone is created detached, so `--abbrev-ref HEAD` says "HEAD" for
  # the common case and names nothing. Report the sha then, which at least
  # identifies it; a named branch means a cycle got as far as creating one.
  branch="$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null)" || branch=""
  if [ -z "$branch" ] || [ "$branch" = "HEAD" ]; then
    branch="detached at $(git -C "$wt" rev-parse --short HEAD 2>/dev/null || echo '?')"
  else
    branch="branch $branch"
  fi
  when="$(git -C "$wt" log -1 --format=%cs 2>/dev/null)" || when="?"
  n="$(git -C "$wt" status --porcelain -- ':!agent_states' 2>/dev/null | wc -l | tr -d ' ')"
  op="$(clone_op "$wt")"

  out="$wt has $n uncommitted change(s). Nothing was removed or reset.
             This is a fan-out CLONE under $ROOT, not your repo — $REPO is
             not what this is about, and is probably clean.
             Clone is $branch, last commit $when."
  if [ -n "$op" ]; then
    out="$out
             A $op is in progress here and was never finished. End it with:
               git -C $(q "$wt") $op --abort
             That returns the branch to its last commit and touches no remote,
             so anything already pushed — and any PR on it — is unaffected."
  else
    out="$out
             Commit or discard them, then re-run:
               git -C $(q "$wt") status"
  fi
  printf '%s\n' "$out"
}

# `--stop-awake` is the teardown half. The --awake bound is a ceiling, not a
# lifetime: a run that finishes early leaves the inhibitor holding the machine
# awake, and nothing in the pipeline knows a run has ended, so this is the
# explicit way to say so.
if [ "$STOP_AWAKE" = 1 ]; then
  STOPPED=0
  P="$(cat "$ROOT/awake.pid" 2>/dev/null || true)"
  if [ -n "$P" ] && ps -p "$P" -o comm= 2>/dev/null | grep -q caffeinate; then
    kill "$P" 2>/dev/null && { say "stopped the sleep inhibitor (pid $P)"; STOPPED=1; }
  fi
  # The pid file can be gone while the process is not — a crash between the two,
  # or a hand-edited clones root. Reporting "none running" then mistakes a
  # missing record for a missing process. Fall back to matching our own flag
  # signature, and say which route found it.
  if [ "$STOPPED" = 0 ]; then
    for Q in $(pgrep -f 'caffeinate -dimsu -t' 2>/dev/null || true); do
      kill "$Q" 2>/dev/null && { say "stopped an inhibitor with no pid file (pid $Q)"; STOPPED=1; }
    done
  fi
  [ "$STOPPED" = 0 ] && say "no sleep inhibitor is running"
  rm -f "$ROOT/awake.pid"
  exit 0
fi

[ ${#ISSUES[@]} -gt 0 ] || die "no issues given. Usage: start-parallel-cycles.sh 419 404 378"
for i in "${ISSUES[@]}"; do
  case "$i" in ''|*[!0-9]*) die "'$i' is not an issue number" ;; esac
done
case "$MODE" in
  ''|full|lean|hotfix) ;;
  *) die "--mode must be full, lean or hotfix (got '$MODE')" ;;
esac
case "$CLONER" in
  ''|git|omp) ;;
  *) die "--cloner must be git or omp (got '$CLONER')
             Usage: start-parallel-cycles.sh [--cloner git|omp] 419 404 378" ;;
esac

[ -n "$REPO" ] || REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not in a git repo (pass --repo)"
command -v git >/dev/null 2>&1 || die "git not found"
# Clone mechanism. `omp worktree add` copies the whole working tree — framework
# links, settings, vault links, warm build caches — copy-on-write on APFS
# (sd-wire § 5c), so it stays first choice wherever omp is installed. Without
# omp (Claude Code alone, and Windows, where NTFS has no cheap whole-tree copy)
# a plain `git worktree add` keeps origin just as well — a worktree shares the
# repo's config, which is what a `git clone --local` gets wrong — and the
# untracked half is rebuilt: framework links by deploy.sh, per-project config
# copied, vault links by each cycle's own vault link guard. --cloner picks
# one outright, so an operator with omp can still ask for plain worktrees.
#
# Partial checkout (sparse_clones) is git only: omp copies the whole working
# tree, which is the opposite of a partial one. With it on, new slots use git,
# and an explicit --cloner omp refuses.
SPARSE="$(awk -F'|' '/^\| *sparse_clones *\|/{gsub(/[ \t`]/,"",$3); print $3; exit}' \
          "$REPO/.omp/agent-config.md" 2>/dev/null)"
[ -n "$SPARSE" ] || SPARSE=false
case "$SPARSE" in
  true|false) ;;
  *) die "sparse_clones must be true or false (got '$SPARSE').
             Set it in $REPO/.omp/agent-config.md § Cycle Options." ;;
esac
if [ -z "$CLONER" ]; then
  if [ "$SPARSE" = true ]; then CLONER=git
  elif command -v omp >/dev/null 2>&1; then CLONER=omp; else CLONER=git; fi
elif [ "$CLONER" = omp ]; then
  [ "$SPARSE" = false ] || die "--cloner omp, but sparse_clones is true. omp worktree add copies the whole
             working tree, so it cannot make a partial checkout. Nothing was changed.
             Drop --cloner omp (or pass --cloner git), or set sparse_clones to false in
             $REPO/.omp/agent-config.md § Cycle Options."
  command -v omp >/dev/null 2>&1 || die "--cloner omp, but omp is not installed (pass --cloner git)"
fi
[ "$CLAIM" = 0 ] || command -v gh >/dev/null 2>&1 || die "gh not found (or pass --no-claim)"

# base_branch from the deployment's config, unless overridden
if [ -z "$BASE" ]; then
  BASE="$(awk -F'|' '/^\| *base_branch *\|/{gsub(/^[ \t]+|[ \t]+$/,"",$3); print $3; exit}' \
          "$REPO/.omp/agent-config.md" 2>/dev/null)"
  [ -n "$BASE" ] || BASE="main"
fi

# Pool size, from the deployment's config. A project config without the row
# takes the framework default.
SLOTS="$(awk -F'|' '/^\| *parallel_slots *\|/{gsub(/[ \t`]/,"",$3); print $3; exit}' \
          "$REPO/.omp/agent-config.md" 2>/dev/null)"
[ -n "$SLOTS" ] || SLOTS=3
case "$SLOTS" in
  ''|*[!0-9]*|0*) die "parallel_slots must be a positive whole number (got '$SLOTS').
             Set it in $REPO/.omp/agent-config.md § Cycle Options." ;;
esac
[ "${#ISSUES[@]}" -le "$SLOTS" ] || die "${#ISSUES[@]} issues, but the pool has $SLOTS slot(s). Nothing was changed.
             Run at most $SLOTS at once, or raise parallel_slots in
             $REPO/.omp/agent-config.md § Cycle Options (each slot costs a checkout plus its build output)."
SLOT_PREFIX="$(basename "$REPO")-slot-"

# ---------------------------------------------------------------- preflight
step "Preflight ($REPO)"

# --sync first: it is what makes the branch and freshness checks below pass, and
# it must see a clean tree before it moves anything.
# --dry-run must not mutate. Reap and sync run before the dry-run exit below, so
# without this a "dry" run would delete the previous run's clones and move the
# base branch — the two most destructive things this script does.
WOULD_REAP=0
if [ "$DRY" = 1 ]; then
  [ "$SYNC" = 0 ] || say "would sync $BASE (skipped: --dry-run)"
  [ "$REAP" = 0 ] || { say "would reap clones outside the pool under $ROOT (skipped: --dry-run)"; WOULD_REAP=1; }
  SYNC=0 REAP=0
fi

if [ "$SYNC" = 1 ]; then
  D="$(git -C "$REPO" status --porcelain | wc -l | tr -d ' ')"
  [ "$D" = "0" ] || die "--sync needs a clean tree; $D uncommitted change(s) in $REPO."
  git -C "$REPO" checkout -q "$BASE" 2>/dev/null || die "--sync could not check out '$BASE'."
  # --ff-only: a merge or rebase here would be this script inventing history.
  git -C "$REPO" pull -q --ff-only 2>/dev/null \
    || die "--sync could not fast-forward '$BASE'. Reconcile it by hand."
  say "synced $BASE to $(git -C "$REPO" rev-parse --short HEAD)"
fi

# ------------------------------------------------------------------- pool
#
# Cycles run in a fixed pool of worktrees, <root>/<repo>-slot-1 … -slot-N, and
# a slot is reset in place rather than recreated: checkout and cold build are
# paid once per slot, ignored build output stays warm, and disk use stays at N
# slots. The repo name in the slot name keeps two projects that share a clones
# root out of each other's slots.
#
# Every slot this run touches, and every clone it removes, passes check_clone
# first; all checks run before any change, so a refusal leaves the previous run
# exactly as it was and the operator can fix the one slot and re-run.
ROOT_P="$(cd "$ROOT" 2>/dev/null && pwd -P)" || ROOT_P="$ROOT"
# Compare resolved paths: `git worktree list` reports the physical path, so on
# macOS a clones root under /var arrives as /private/var.
phys() { (cd "$1" 2>/dev/null && pwd -P) || printf '%s' "$1"; }
slot_index() {  # physical path -> K, when it is this pool's slot K directly under the root
  local name k
  [ "$(dirname "$1")" = "$ROOT_P" ] || return 1
  name="$(basename "$1")"
  case "$name" in "$SLOT_PREFIX"*) k="${name#"$SLOT_PREFIX"}" ;; *) return 1 ;; esac
  case "$k" in ''|*[!0-9]*|0*) return 1 ;; esac
  printf '%s' "$k"
}
worktrees() { git -C "$REPO" worktree list --porcelain | sed -n 's/^worktree //p' | tail -n +2; }

# Refuses, and exits, when removing or resetting a clone could lose work. A clone
# is a linked worktree, so its branches live in $REPO and survive either; what is
# at risk is uncommitted work, an unfinished git operation, commits that only a
# detached HEAD reaches, and a session still running inside it.
# agent_states/ is excluded from the dirty test: it is framework scratch the
# cycle owns and clears, and this script writes the .fanout-clone marker into it.
check_clone() {
  local wt="$1" wt_p holders h kids head
  wt_p="$(phys "$wt")"
  if [ -d "$wt" ]; then
    if [ -n "$(git -C "$wt" status --porcelain -- ':!agent_states' 2>/dev/null)" ] \
       || [ -n "$(clone_op "$wt")" ]; then
      die "$(dirty_clone_report "$wt")"
    fi
    if ! git -C "$wt" symbolic-ref -q HEAD >/dev/null 2>&1; then
      head="$(git -C "$wt" rev-parse HEAD 2>/dev/null)"
      if [ -n "$head" ] && [ -z "$(git -C "$wt" for-each-ref --count=1 --contains "$head" \
                                     refs/heads refs/remotes refs/tags 2>/dev/null)" ]; then
        die "$wt is on a detached HEAD whose commits no branch holds. Nothing was removed or reset.
             Keep them on a branch, then re-run:
               git -C $(q "$wt") branch <name>"
      fi
    fi
  fi
  # Match on the clone path, then follow children: the path appears in a
  # terminal's argv but not in the session's own — `claude "/cycle 442"` carries
  # no directory — so matching alone hides the live session inside it.
  holders="$(pgrep -f "$wt_p" 2>/dev/null || true)"
  for h in $holders; do
    kids="$(pgrep -P "$h" 2>/dev/null || true)"
    [ -n "$kids" ] && holders="$holders
$kids"
  done
  holders="$(printf '%s\n' "$holders" | grep -v '^$' | sort -u || true)"
  if [ -n "$holders" ]; then
    printf 'start-parallel-cycles: REFUSING — %s still has processes attached:\n' "$wt_p" >&2
    # shellcheck disable=SC2086
    ps -o pid=,etime=,command= -p $(echo "$holders" | tr '\n' ' ') 2>/dev/null \
      | cut -c1-160 | sed 's/^/    /' >&2
    printf '    Close the session, or kill the leftovers:  kill %s\n' "$(echo "$holders" | tr '\n' ' ')" >&2
    printf '    Nothing was removed or reset.\n' >&2
    exit 1
  fi
}

remove_clone() {
  git -C "$REPO" worktree remove --force "$1" 2>/dev/null \
    || die "could not remove $1 — remove it by hand."
  rm -f "$ROOT/.reapable/$(basename "$1").json"
}

# Disk held by the pool's slots, in KB. `du` counts every block a slot names, so
# on APFS a copy-on-write omp slot reads larger than the space it really takes.
pool_kb() {
  local k kb=0 s
  for ((k = 1; k <= SLOTS; k++)); do
    [ -d "$ROOT/$SLOT_PREFIX$k" ] || continue
    s="$(du -sk "$ROOT/$SLOT_PREFIX$k" 2>/dev/null | awk '{print $1}')"
    kb=$((kb + ${s:-0}))
  done
  echo "$kb"
}
pool_footprint() {  # [kb] -> "<MB> MB across <n> of <N> slot(s) under <root>"
  local kb="${1:-$(pool_kb)}" k have=0
  for ((k = 1; k <= SLOTS; k++)); do [ -d "$ROOT/$SLOT_PREFIX$k" ] && have=$((have+1)); done
  echo "$((kb / 1024)) MB across $have of $SLOTS slot(s) under $ROOT"
}

# Classify what exists under the root: pool slots (1..N), and everything else —
# per-issue clones from before the pool, or slots beyond a lowered parallel_slots.
SLOT_HAS=() EXTRA=()
while IFS= read -r wt; do
  [ -n "$wt" ] || continue
  wt_p="$(phys "$wt")"
  case "$wt_p" in "$ROOT_P"/*) ;; *) continue ;; esac
  if k="$(slot_index "$wt_p")" && [ "$k" -le "$SLOTS" ]; then
    [ -d "$wt" ] && SLOT_HAS[$k]=1
  else
    EXTRA+=("$wt")
  fi
done < <(worktrees)

# Per slot: reuse | create | recreate (--fresh) | drop (--fresh, unused this run) | untouched.
SLOT_ACT=()
for ((k = 1; k <= SLOTS; k++)); do
  C="$ROOT/$SLOT_PREFIX$k"
  if [ "$k" -le "${#ISSUES[@]}" ]; then
    if [ "${SLOT_HAS[$k]:-}" = 1 ]; then
      if [ "$FRESH" = 1 ]; then SLOT_ACT[$k]=recreate; else SLOT_ACT[$k]=reuse; fi
    else
      [ -e "$C" ] && die "$C exists but is not a worktree of $REPO. Nothing was changed.
             Move it aside, or pass --clones-root."
      SLOT_ACT[$k]=create
    fi
  elif [ "$FRESH" = 1 ] && [ "${SLOT_HAS[$k]:-}" = 1 ]; then
    SLOT_ACT[$k]=drop
  fi
done

for ((k = 1; k <= SLOTS; k++)); do
  case "${SLOT_ACT[$k]:-}" in reuse|recreate|drop) check_clone "$ROOT/$SLOT_PREFIX$k" ;; esac
done
if [ "$REAP" = 1 ] || [ "$WOULD_REAP" = 1 ]; then
  for wt in ${EXTRA[@]+"${EXTRA[@]}"}; do check_clone "$wt"; done
fi

if [ "$DRY" = 0 ]; then
  for ((k = 1; k <= SLOTS; k++)); do
    case "${SLOT_ACT[$k]:-}" in recreate|drop) remove_clone "$ROOT/$SLOT_PREFIX$k" ;; esac
  done
  reaped=0
  if [ "$REAP" = 1 ]; then
    for wt in ${EXTRA[@]+"${EXTRA[@]}"}; do remove_clone "$wt"; reaped=$((reaped+1)); done
  fi
  git -C "$REPO" worktree prune 2>/dev/null
  [ "$reaped" = 0 ] || say "reaped $reaped clone(s) outside the pool from $ROOT"
fi

CUR="$(git -C "$REPO" branch --show-current 2>/dev/null)"
if [ "$CUR" != "$BASE" ]; then
  [ "$DRY" = 1 ] && [ "$WOULD_REAP" = 1 ] \
    && say "on branch '$CUR' — the real run would check out '$BASE' first" \
    || die "on branch '$CUR', expected base '$BASE'. A clone copies the working
             tree, so all $((${#ISSUES[@]})) cycles would start from the wrong place."
fi

DIRTY="$(git -C "$REPO" status --porcelain | wc -l | tr -d ' ')"
[ "$DIRTY" = "0" ] || die "$DIRTY uncommitted change(s) in $REPO. They would be copied into every clone.
             Commit, stash, or discard them first."

STATES="$(ls "$REPO"/agent_states/cycle-state-*.md 2>/dev/null | wc -l | tr -d ' ')"
[ "$STATES" = "0" ] || die "$STATES cycle-state file(s) present — a cycle may be live, and clones
             inherit agent_states/. Run clear-agent-states.py, or wait."

# Worktrees outside the pool. Pool slots are expected; anything else may be a
# running agent's.
WT=0
while IFS= read -r wt; do
  [ -n "$wt" ] || continue
  if k="$(slot_index "$(phys "$wt")")" && [ "$k" -le "$SLOTS" ]; then continue; fi
  WT=$((WT+1))
done < <(worktrees)
if [ "$WT" != "0" ]; then
  # Under --dry-run the reap that would have cleared the clones under the root
  # was skipped, so refusing over them would report a blocker the real run does
  # not have.
  if [ "$WOULD_REAP" = 1 ] && [ "$WT" -le "${#EXTRA[@]}" ]; then
    say "$WT existing worktree(s) outside the pool — the real run would reap them first"
  else
    die "$WT existing worktree(s) outside the pool. Agents may be running; finish or prune them first."
  fi
fi

AVAIL_KB="$(df -k "$REPO" | tail -1 | awk '{print $4}')"
[ "$AVAIL_KB" -gt 5242880 ] || die "only $((AVAIL_KB/1024)) MB free — under the 5 GB floor."

say "branch $BASE, clean, no live state, no worktrees outside the pool"
say "mode ${MODE:-per-story — from each issue Depth field}"
say "$((AVAIL_KB/1024/1024)) GB free"

# -P: resolve symlinks. Skills are deployed by symlinking a central framework
# checkout into the project, so the logical path walks back up into the *project*
# and would record it as the framework. The framework SHA is the point of this
# record.
FW_ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd -P)"
FW_SHA="$(git -C "$FW_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
FW_DIRTY="$(git -C "$FW_ROOT" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
say "framework $FW_ROOT @ $FW_SHA${FW_DIRTY:+ (${FW_DIRTY} uncommitted)}"
[ "${FW_DIRTY:-0}" = "0" ] || printf '  ! framework has uncommitted changes — deployments resolve to
    the working tree, so every cycle will run against them.\n'

# Deployment integrity. A refusal, not a warning, unlike the gate-capture check
# below — and the difference is worth stating. An *unregistered* hook is a project
# choice: the run is valid, just unmeasured. A *broken link* is not a choice, it
# is a deployment that looks wired and is not, and the remedy is one command.
#
# Registration is what the check below tests, and it is the weaker signal: a
# settings.json naming gate-log.py whose path no longer resolves passes it. A
# dangling hook fails open — the harness treats a hook error as non-fatal — so
# telemetry, gate capture and the credential guard stop with nothing said. That
# is how a fan-out comes back unmeasured while every preflight line reads green.
if [ -x "$FW_ROOT/deploy.sh" ]; then
  if DEP_OUT="$(bash "$FW_ROOT/deploy.sh" check "$REPO" 2>&1)"; then
    say "deployment    $(printf '%s' "$DEP_OUT" | sed -n 's/^  \([0-9]*\/[0-9]* correct\).*/\1/p')"
  else
    printf '%s\n' "$DEP_OUT" | sed 's/^/  /' >&2
    die "deployment is incomplete — fix it before measuring a run:
             bash $(q "$FW_ROOT/deploy.sh") link $(q "$REPO")"
  fi
else
  say "deployment    not checked (no deploy.sh in $FW_ROOT)"
fi

# Gate capture is automatic only when the hook is registered; gates logged by
# hand depend on discipline. A warning, not a refusal: the hook is Claude Code
# only, and a run without it is valid — just unmeasured. Say which, before the
# run rather than after.
if [ "$HARNESS" = "claude" ]; then
  if grep -q 'gate-log.py' "$REPO/.claude/settings.json" 2>/dev/null; then
    say "gate capture wired"
  else
    printf '  ! gate-log hook not registered in %s — gate wait will NOT be captured.\n' \
      "$REPO/.claude/settings.json"
    printf '    Wire it as settings.json.sample does (five events), or accept an unmeasured run.\n'
  fi
else
  say "gate capture: unavailable under $HARNESS (Claude Code hook only)"
fi

# ------------------------------------------------------------------- depth
#
# --mode is a launch-time flag and can hold exactly one value; blast radius is a
# fact about the issue. So depth lives on the story, in the board's `Depth` field,
# written by /refine when someone had actually read the body. The launcher's job
# is to notice a gap BEFORE spawning N sessions — an unset Depth parks every clone
# on a question at Phase 1A, which is the failure this check exists to prevent.
#
# It refuses only when the board HAS the field and an issue lacks a value. A board
# without the field is not an error: those cycles fall back to /cycle's own
# heuristics.
if [ -n "$MODE" ]; then
  [ "$MODE" != hotfix ] || [ ${#ISSUES[@]} -le 1 ] || \
    die "--mode hotfix with ${#ISSUES[@]} issues. hotfix skips Gate 1, Gate 2 and review and forces
             verify to lite, so a clone exercises almost none of what a fan-out is run to observe.
             Run hotfixes sequentially, or drop --mode and let each story's Depth decide."
  say "depth         --mode $MODE overrides every story's Depth"
elif ! command -v gh >/dev/null 2>&1; then
  say "depth         not checked (no gh) — each cycle resolves its own"
else
  # Only the Artifact Paths table row, never the prose above it that shows the
  # `project:<owner>/<number>` placeholder — matching that yields a literal
  # "<owner>" and every lookup below then silently finds nothing.
  BOARD="$(awk '/^\|/ && /Roadmap/ && match($0, /project:[A-Za-z0-9_.-]+\/[0-9]+/) \
                { print substr($0, RSTART+8, RLENGTH-8); exit }' \
           "$REPO/.omp/agent-config.md" 2>/dev/null)"
  if [ -z "$BOARD" ]; then
    say "depth         no board in agent-config — each cycle resolves its own"
  else
    B_OWNER="${BOARD%%/*}"; B_NUM="${BOARD##*/}"
    if ! gh project field-list "$B_NUM" --owner "$B_OWNER" --format json 2>/dev/null \
         | grep -q '"name":"Depth"'; then
      say "depth         board $BOARD has no Depth field — each cycle will ask"
    else
      MISSING="$(gh project item-list "$B_NUM" --owner "$B_OWNER" --format json --limit 1000 2>/dev/null \
        | strip_cr python3 -c '
import json,sys
want=set(sys.argv[1:])
have={}
for it in json.load(sys.stdin).get("items",[]):
    n=it.get("content",{}).get("number")
    if n is not None: have[str(n)]=(it.get("depth") or "").strip()
print(" ".join(sorted(i for i in want if not have.get(i))))
' "${ISSUES[@]}")"
      if [ -n "$MISSING" ]; then
        die "no Depth set on issue(s): $MISSING
             Depth (full|lean|hotfix) is set by /refine at Step 8 and is part of the Definition of
             Ready. Without it every clone stops and asks at Phase 1A. Refine those issues, set the
             field by hand, or pass --mode to override all of them."
      fi
      say "depth         per-story, from board $BOARD"
    fi
  fi
fi

# ------------------------------------------------------------ file overlap
#
# Two cycles editing one file is not always bad: two clones appending tests to
# one file merge without a conflict. One deleting a region the other added to
# leaves the second PR conflicted, and nothing in the pipeline owns a rebase
# after a cycle ends.
#
# The launcher is the only place that knows every issue before any work starts.
# It says so here rather than deciding: refuse, sequence, or start knowingly is
# the operator's call, and a pair that looks overlapping may not conflict at all.
#
# Read the signal as "these two issues work in the same area", NOT as "these two
# will collide in this file": a flagged pair can auto-merge the named file and
# conflict in one neither issue mentions, such as a README both cycles document
# in. Anything that later sequences on this output must sequence the *pair*, not
# the named file.
# Recorded in run-provenance.txt so a later evidence pass can tell "we knew" from
# "we found out".
#
# Stack-neutral by construction: a token counts as a file only if `git ls-files`
# knows it. A regex tuned to one language would silently see nothing in a repo
# that does not use it, which is the failure mode this project keeps finding in
# hand-written lists.
OVERLAP_DIR="$(mktemp -d)"
OVERLAP_FOUND=0
# Each body is kept in $OVERLAP_DIR/body-<issue>; partial checkout reads its
# `## Slices` from there.
if command -v gh >/dev/null 2>&1; then
  for i in "${ISSUES[@]}"; do
    gh issue view "$i" --repo "$(cd "$REPO" && gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)" \
       --json body,title -q '.title + "\n" + .body' 2>/dev/null > "$OVERLAP_DIR/body-$i"
    grep -oE '[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)+\.[A-Za-z0-9]+' "$OVERLAP_DIR/body-$i" \
      | sort -u \
      | while read -r f; do
          git -C "$REPO" ls-files --error-unmatch -- "$f" >/dev/null 2>&1 && printf '%s\n' "$f"
        done > "$OVERLAP_DIR/$i" 2>/dev/null || true
  done
  a=0
  for i in "${ISSUES[@]}"; do
    a=$((a+1)); b=0
    for j in "${ISSUES[@]}"; do
      b=$((b+1))
      [ "$b" -le "$a" ] && continue
      shared="$(comm -12 "$OVERLAP_DIR/$i" "$OVERLAP_DIR/$j" 2>/dev/null)"
      if [ -n "$shared" ]; then
        if [ "$OVERLAP_FOUND" = 0 ]; then
          step "File overlap between issues"
          OVERLAP_FOUND=1
        fi
        say "#$i and #$j both name:"
        printf '%s\n' "$shared" | while read -r f; do [ -n "$f" ] && say "    $f"; done
        printf '  overlap\t%s\t%s\t%s\n' "$i" "$j" "$(printf '%s' "$shared" | tr '\n' ',')" \
          >> "$OVERLAP_DIR/.provenance"
      fi
    done
  done
  [ "$OVERLAP_FOUND" = 1 ] && \
    say "not a refusal — an overlap can merge clean. Sequence them, drop one, or start knowing."
fi

# --------------------------------------------------------- partial checkout
#
# With sparse_clones on, each slot checks out the directories sparse-set.py
# derives from its story; $OVERLAP_DIR/sparse-<slot> holds them, one per line.
# A story with no usable set gets a full checkout, and the launch says why.
SPARSE_PY="$FW_ROOT/.claude/skills/cycle/sparse-set.py"
SPARSE_LOG=""
if [ "$SPARSE" = true ]; then
  step "Partial checkout (sparse_clones)"
  say "new slots via git worktree add: omp worktree add copies the whole working tree"
  n=0
  for i in "${ISSUES[@]}"; do
    n=$((n+1)); pf="$OVERLAP_DIR/plan-$n"
    if [ ! -s "$OVERLAP_DIR/body-$i" ]; then
      printf 'full\tissue #%s could not be read with gh\n' "$i" > "$pf"
    elif ! strip_cr python3 "$SPARSE_PY" plan --repo "$REPO" --base "$BASE" \
              --body "$OVERLAP_DIR/body-$i" > "$pf" 2>"$pf.err"; then
      printf 'full\tsparse-set.py failed: %s\n' "$(tail -n 1 "$pf.err")" > "$pf"
    fi
    if grep -q '^full' "$pf"; then
      why="$(awk -F'\t' '$1 == "full" { print $2; exit }' "$pf")"
      say "#$i → $SLOT_PREFIX$n  full checkout: $why"
      SPARSE_LOG="$SPARSE_LOG# sparse $SLOT_PREFIX$n full: $why
"
    else
      awk -F'\t' '$1 == "dir" { print $2 }' "$pf" > "$OVERLAP_DIR/sparse-$n"
      dirs="$(tr '\n' ' ' < "$OVERLAP_DIR/sparse-$n" | sed 's/ $//')"
      say "#$i → $SLOT_PREFIX$n  sparse: $dirs"
      awk -F'\t' '$1 == "note" { print "    " $2 }' "$pf"
      SPARSE_LOG="$SPARSE_LOG# sparse $SLOT_PREFIX$n $dirs
"
    fi
  done
fi

if [ "$DRY" = 1 ]; then
  [ "$OVERLAP_FOUND" = 0 ] && say "no file overlap between the named issues"
  if [ "$AWAKE_HOURS" = "0" ]; then
    say "would NOT inhibit system sleep (--no-awake)"
  elif command -v caffeinate >/dev/null 2>&1; then
    say "would inhibit system sleep for ${AWAKE_HOURS}h"
  else
    say "! would NOT inhibit system sleep — no caffeinate on this host"
  fi
  step "Dry run — would use ${#ISSUES[@]} of $SLOTS slot(s) under $ROOT via $CLONER worktree add"
  n=0
  for i in "${ISSUES[@]}"; do
    n=$((n+1))
    case "${SLOT_ACT[$n]}" in
      reuse)    how="reuse — reset to $BASE, ignored build output kept" ;;
      recreate) how="recreate — --fresh" ;;
      *)        how="create" ;;
    esac
    say "#$i → $SLOT_PREFIX$n  $how  ($ROOT/$SLOT_PREFIX$n)"
  done
  for ((k = 1; k <= SLOTS; k++)); do
    [ "${SLOT_ACT[$k]:-}" = drop ] && say "would remove $ROOT/$SLOT_PREFIX$k (--fresh; created again when a run needs it)"
  done
  if [ "$WOULD_REAP" = 1 ]; then
    for wt in ${EXTRA[@]+"${EXTRA[@]}"}; do say "would remove $wt (outside the pool)"; done
  fi
  say "pool disk footprint now $(pool_footprint)"
  exit 0
fi

mkdir -p "$ROOT" || die "cannot create clones root $ROOT"

# ----------------------------------------------------- slots (local, reversible)
# The per-project files a cycle needs that a project may keep untracked.
CONFIG_FILES=".claude/settings.json .claude/settings.local.json .omp/agent-config.md"

link_framework() {
  out="$(bash "$FW_ROOT/deploy.sh" link "$1" 2>&1)" \
    || die "deploy.sh link failed for $1 — run: bash $(q "$FW_ROOT/deploy.sh") check $(q "$1")
$(failed_output "$out")"
}

# Clears agent_states/ in the slot's own tree (the script finds it from the cwd),
# archiving a fan-out slot's telemetry to the run root first.
clear_states() {
  (cd "$1" && python3 "$FW_ROOT/.claude/skills/cycle/clear-agent-states.py" --all) >/dev/null 2>&1 || true
}

# Narrows, replaces or widens a slot's checkout once it is at the base. With a
# planned set, cone mode holds exactly those directories, replacing any earlier
# set. Without one, a slot that was sparse returns to a full checkout, and a full
# slot is left alone: a project that never turns sparse_clones on runs no
# sparse-checkout command and keeps its git config as it was.
apply_sparse() {
  local C="$1" k="$2" list="$OVERLAP_DIR/sparse-$2"
  if [ "$SPARSE" = true ] && [ -s "$list" ]; then
    out="$(git -C "$C" sparse-checkout set --cone --stdin < "$list" 2>&1)" \
      || die "could not set the sparse checkout of $C. Slots so far: ${CLONES[*]:-none}
$(failed_output "$out")"
  elif [ "$(git -C "$C" config --get core.sparseCheckout 2>/dev/null)" = true ]; then
    out="$(git -C "$C" sparse-checkout disable 2>&1)" \
      || die "could not return $C to a full checkout. Slots so far: ${CLONES[*]:-none}
$(failed_output "$out")"
    say "$SLOT_PREFIX$k returned to a full checkout"
  fi
}

create_slot() {
  local C="$1" k="$2" f
  # --detach and NO -b: /cycle creates the feature branch itself at Phase 2B, and the
  # slot cannot be on $BASE because the primary has it checked out.
  if [ "$CLONER" = omp ]; then
    out="$(omp worktree add --detach --cwd "$REPO" "$C" "$BASE" 2>&1)" \
      || die "omp worktree add failed for $C. Slots so far: ${CLONES[*]:-none}
$(failed_output "$out")"
  else
    # A partial slot is created empty, given its set, then checked out, so files
    # outside the set are never written.
    if [ "$SPARSE" = true ] && [ -s "$OVERLAP_DIR/sparse-$k" ]; then
      out="$( { git -C "$REPO" worktree add -q --no-checkout --detach "$C" "$BASE" \
                && git -C "$C" sparse-checkout set --cone --stdin < "$OVERLAP_DIR/sparse-$k" \
                && git -C "$C" checkout -q --detach "$BASE"; } 2>&1)"
    else
      out="$(git -C "$REPO" worktree add -q --detach "$C" "$BASE" 2>&1)"
    fi \
      || die "git worktree add failed for $C. Slots so far: ${CLONES[*]:-none}
$(failed_output "$out")"
    # A worktree carries tracked files only; copy the untracked config when absent.
    for f in $CONFIG_FILES; do
      if [ -f "$REPO/$f" ] && [ ! -e "$C/$f" ]; then
        mkdir -p "$(dirname "$C/$f")" && cp "$REPO/$f" "$C/$f"
      fi
    done
    link_framework "$C"
  fi
  clear_states "$C"
}

# Reset an existing slot to the base without recreating it. `clean -fd` without
# -x removes untracked files and keeps ignored ones, so build output stays warm.
# The same for both cloners: omp has no refresh of its own, and what it copied at
# creation besides config and framework links (.env, caches) is kept as it was;
# --fresh copies it again.
reset_slot() {
  local C="$1" k="$2" f
  # Checked again immediately before the reset, so nothing written since the
  # check pass is discarded.
  check_clone "$C"
  clear_states "$C"
  out="$( { git -C "$C" checkout -q --detach "$BASE" \
            && git -C "$C" reset -q --hard \
            && git -C "$C" clean -q -fd; } 2>&1)" \
    || die "could not reset $C to $BASE. Slots so far: ${CLONES[*]:-none}
$(failed_output "$out")"
  apply_sparse "$C" "$k"
  # Untracked config follows the primary, which holds the current copy.
  for f in $CONFIG_FILES; do
    if [ -f "$REPO/$f" ] && ! git -C "$REPO" ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
      mkdir -p "$(dirname "$C/$f")" && cp "$REPO/$f" "$C/$f"
    fi
  done
  [ -f "$FW_ROOT/deploy.sh" ] && link_framework "$C"
  return 0
}

step "Preparing slots (via $CLONER worktree add for new slots)"
[ "$CLONER" = git ] && say "git worktree: new slots get tracked files, framework links and per-project config;
             build caches start cold, and other untracked files (.env, ...) are not copied"
CLONES=() SLOT_LOG="" ; n=0
for i in "${ISSUES[@]}"; do
  n=$((n+1)); C="$ROOT/$SLOT_PREFIX$n"
  if [ "${SLOT_ACT[$n]}" = reuse ]; then reset_slot "$C" "$n"; how=reused
  else create_slot "$C" "$n"; how=created
  fi
  rm -f "$ROOT/.reapable/$SLOT_PREFIX$n.json"
  # A slot is a linked worktree of $REPO, so the telemetry hook's `--git-common-dir`
  # resolution points at $REPO and every slot would commingle its events there.
  # This marker tells the hook the slot owns its own telemetry.
  # Written after the clear, and clear-agent-states.py preserves it thereafter.
  # gate_log: the Stop/UserPromptSubmit hook appends every gate wait here as well
  # as to the slot's own log, so one file holds the whole run.
  # slot: tells reap-clones.sh finish to keep the build output warm.
  mkdir -p "$C/agent_states" && printf 'issue=%s\nclone=%s\nslot=%s\norigin=%s\ngate_log=%s\ncreated=%s\n' \
    "$i" "$SLOT_PREFIX$n" "$n" "$REPO" "$ROOT/gate-log.tsv" "$(date -u +%FT%TZ)" > "$C/agent_states/.fanout-clone"
  CLONES+=("$C"); say "#$i → $SLOT_PREFIX$n  $how  $C"
  SLOT_LOG="$SLOT_LOG# slot $SLOT_PREFIX$n issue $i $how $C
"
done
POOL_KB="$(pool_kb)"
say "pool disk footprint $(pool_footprint "$POOL_KB")"

# ---------------------------------------------- claim (remote, after local work)
if [ "$CLAIM" = 1 ]; then
  step "Claiming issues"
  ME="$(gh api user -q .login 2>/dev/null || echo '')"
  for i in "${ISSUES[@]}"; do
    A="$(cd "$REPO" && gh issue view "$i" --json assignees -q '[.assignees[].login]|join(",")' 2>/dev/null || echo "?")"
    if [ "$A" = "?" ]; then
      printf '  ! #%s could not be read — assign it by hand\n' "$i"
    elif [ -z "$A" ]; then
      (cd "$REPO" && gh issue edit "$i" --add-assignee @me >/dev/null 2>&1) \
        && say "#$i claimed" || printf '  ! #%s claim failed — assign it by hand\n' "$i"
    elif [ -n "$ME" ] && [ "$A" = "$ME" ]; then
      # Already ours — a re-run, or claimed by hand beforehand. Not a conflict.
      say "#$i already claimed by you"
    else
      printf '  ! #%s is assigned to %s — someone else may be working it. Not claiming.\n' "$i" "$A"
    fi
  done
fi

# ------------------------------------------------------------- run artifacts
#
# Rotate here, not in the reap block. This is the first point at which the run is
# certain to happen: preflight has passed, the clones exist, the issues are
# claimed. Rotating earlier would scatter the previous run's evidence on a run
# that then refuses; rotating on reaping would miss every run whose clones are
# already gone.
#
# Unconditional on the files existing, not on anything else. A log that spans two
# runs is the same conflation the telemetry aggregator warns about, and it is
# worse here because nothing in the output says so — the numbers just come out
# wrong and plausible.
GATELOG="$ROOT/gate-log.tsv"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
for f in "$GATELOG" "$ROOT/run-provenance.txt"; do
  [ -f "$f" ] || continue
  mv "$f" "${f%.*}-$ts.${f##*.}" \
    && say "archived $(basename "$f") → $(basename "${f%.*}-$ts.${f##*.}")"
done

# The telemetry archive rotates for the same reason. Finalize copies each clone's
# events into $ROOT/telemetry/<clone>/ and the clone names repeat every run, so
# unrotated, one directory accumulates every run while claiming to be one
# clone's, and `--events` pointed at it compares one run against the sum of all.
# Only when it holds a file: resetting a slot archives into it, and an archive
# of nothing is not a run's telemetry.
if [ -n "$(find "$ROOT/telemetry" -type f 2>/dev/null | head -n 1)" ]; then
  mv "$ROOT/telemetry" "$ROOT/telemetry-$ts" \
    && say "archived telemetry/ → telemetry-$ts/" \
    || say "! could not rotate telemetry/ — this run's events will commingle with the last"
fi
{
  printf '# run started %s\n' "$(date -u +%FT%TZ)"
  printf '# framework %s @ %s\n' "$FW_ROOT" "$FW_SHA"
  printf '# base %s @ %s\n' "$BASE" "$(git -C "$REPO" rev-parse --short HEAD)"
  printf '# disk_avail_kb_before %s\n' "$AVAIL_KB"
  printf '# pool_slots %s\n# pool_kb %s\n' "$SLOTS" "$POOL_KB"
  printf '%s' "$SLOT_LOG" "$SPARSE_LOG"
  if [ -s "$OVERLAP_DIR/.provenance" ]; then
    sed 's/^ *//' "$OVERLAP_DIR/.provenance" | sed 's/^/# /'
  else
    printf '# overlap none\n'
  fi
} >> "$ROOT/run-provenance.txt"
step "Run artifacts"
say "gate log      $GATELOG  (written automatically by the gate-log hook)"
say "provenance    $ROOT/run-provenance.txt"

# ---------------------------------------------------------------- launch
CMD_FOR() {  # $1 = clone dir, $2 = issue. The cd is for the printed by-hand form;
             # open-terminal.sh also cds, and doing it twice is harmless.
  local m="" ; [ -z "$MODE" ] || m=" --mode $MODE"
  case "$HARNESS" in
    omp) printf 'cd %s && omp "/cycle %s%s"' "$(q "$1")" "$2" "$m" ;;
    *)   printf 'cd %s && claude "/cycle %s%s"' "$(q "$1")" "$2" "$m" ;;
  esac
}

# ------------------------------------------------------------------- awake
#
# A machine that sleeps mid-run kills its cycles: the session dies with "Your
# computer went to sleep mid-response", or on wake with a tool timeout and "Not
# logged in".
#
# This is bounded on purpose. An unbounded caffeinate outlives the run and keeps
# a laptop awake for days, so it self-terminates and leaves a pid file that a
# later run reaps.
#
# Honest limits, because a guard that is trusted further than it works is worse
# than none: `caffeinate` cannot keep a Mac awake with the lid closed on battery,
# and this is macOS-only. On anything else the run is told it is unprotected
# rather than left to assume otherwise.
# Only when cycles are actually being launched. `--no-launch` sets things up and
# prints commands; there is no run to protect, and the test suite exercises the
# launcher that way, so without this guard every `tests/check.py` would leave a
# real 8-hour sleep inhibitor orphaned on the developer's machine.
AWAKE_PID_FILE="$ROOT/awake.pid"
if [ "$AWAKE_HOURS" != "0" ] && [ "$LAUNCH" = 1 ] && [ -z "${CYCLE_NO_AWAKE:-}" ]; then
  if command -v caffeinate >/dev/null 2>&1; then
    if [ -f "$AWAKE_PID_FILE" ]; then
      OLD="$(cat "$AWAKE_PID_FILE" 2>/dev/null || true)"
      if [ -n "$OLD" ] && ps -p "$OLD" -o comm= 2>/dev/null | grep -q caffeinate; then
        kill "$OLD" 2>/dev/null && say "stopped a previous sleep inhibitor (pid $OLD)"
      fi
      rm -f "$AWAKE_PID_FILE"
    fi
    caffeinate -dimsu -t "$((AWAKE_HOURS * 3600))" >/dev/null 2>&1 &
    printf '%s\n' "$!" > "$AWAKE_PID_FILE"
    say "sleep inhibited for ${AWAKE_HOURS}h (pid $!) — stop early with: kill \$(cat $AWAKE_PID_FILE)"
    say "  note: this does not hold with the lid closed on battery."
  else
    say "! no caffeinate on this host — system sleep is NOT inhibited."
    say "  A machine that sleeps mid-run kills its cycles."
  fi
elif [ "$LAUNCH" != 1 ]; then
  say "--no-launch: nothing to keep awake; system sleep is NOT inhibited."
else
  say "--no-awake: system sleep is NOT inhibited."
fi

step "Launching"
if [ "$LAUNCH" = 0 ]; then
  printf '  --no-launch: run each of these in its own terminal.\n\n'
  n=0; for i in "${ISSUES[@]}"; do n=$((n+1)); printf '    %s\n' "$(CMD_FOR "${CLONES[$((n-1))]}" "$i")"; done
else
  # Window opening is open-terminal.sh's job — one copy of the OS and emulator
  # detection, shared with whatever else needs a window.
  OPENER="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/open-terminal.sh"
  opened=0; n=0
  for i in "${ISSUES[@]}"; do
    n=$((n+1)); C="${CLONES[$((n-1))]}"
    [ "$TABS" = 1 ] && TABFLAG=(--tab) || TABFLAG=()
    # Title with the issue's own words. Five windows named c1..c5 tell you
    # nothing about which is which, and a fan-out is watched by switching
    # between them. Truncated so a tab bar stays readable; falls back to the
    # bare number if `gh` cannot answer, because a missing title must not stop
    # a window opening.
    IT="$(cd "$REPO" && gh issue view "$i" --json title -q .title 2>/dev/null || true)"
    [ -n "$IT" ] && WTITLE="#$i ${IT:0:48}" || WTITLE="cycle #$i"
    if bash "$OPENER" "${TABFLAG[@]}" --cwd "$C" --title "$WTITLE" -- "$(CMD_FOR "$C" "$i")"; then
      opened=$((opened+1))
    fi
  done
  if [ "$opened" -lt "${#ISSUES[@]}" ]; then
    printf '  ! opened %s of %s windows. Run the rest by hand:\n\n' "$opened" "${#ISSUES[@]}"
    n=0; for i in "${ISSUES[@]}"; do n=$((n+1)); printf '    %s\n' "$(CMD_FOR "${CLONES[$((n-1))]}" "$i")"; done
  else
    say "$opened terminal(s) opened"
  fi
fi

if [ -n "$MAX_AGENTS" ]; then
  AGENT_CAP_NOTE="  · Cap each orchestrator's Phase-3 wave at $MAX_AGENTS agents. Nothing enforces this
    under Claude Code, so whether it holds is itself the measurement.
    NOTE: this makes the run a CAPPED trial — it cannot serve as the uncapped baseline."
else
  AGENT_CAP_NOTE="  · No agent cap — uncapped is the default and the realistic case. Peak concurrent
    agents is the measurement; do not instruct a cap mid-run, since a
    half-remembered one contaminates the baseline a capped comparison later needs."
fi

cat <<EOF

▸ During the run
  · Phase-3 agents run in the clone directly — NO nested worktree isolation. Under
    Claude Code it provisions at the default branch and under the primary repo, not the
    clone. The clone is already the isolation.
$AGENT_CAP_NOTE
  · Gate waits record themselves — nothing to log by hand. Read them any time with
    python3 .claude/skills/cycle/gate-report.py --log $(q "$GATELOG")
  · Is anything dead? A killed cycle logs the same row as a thinking one, so ask:
    python3 .claude/skills/cycle/cycle-health.py --root $(q "$ROOT")
  · Sample \`df -k $(q "$REPO") | tail -1\` MID-WAVE, while agents run.
  · Do not edit $FW_ROOT while cycles are live.

▸ Afterwards
  Slots stay for the next run, which resets them in place and keeps their build output.
  To give the disk back, remove finished slots (the next run recreates them cold):
    bash .claude/skills/cycle/reap-clones.sh sweep --root $(q "$ROOT") --apply
EOF
