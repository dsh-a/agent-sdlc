#!/usr/bin/env bash
# start-parallel-cycles.sh — set up and launch N parallel /cycle runs, one clone each.
#
# The entry point behind `/cycle --parallel <issue> <issue> ...`. Parallelism that
# needs nine hand-typed commands is not a feature; this is the one command.
#
# What it does, in order:
#   1. Preflight — refuses unless the tree is genuinely quiet (see CONTRACT below)
#   2. One detached clone per issue, via `omp worktree add` (preserves origin so gh works)
#   3. Clears each clone's inherited agent_states/
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
#
# Flags: --repo DIR --base BRANCH --clones-root DIR --harness claude|omp
#        --mode full|lean|hotfix   override every story's Depth (normally omitted)
#        --max-agents N --windows
#        --awake H      inhibit system sleep for H hours (default 8; 0 = off)
#        --no-awake     do not inhibit system sleep
#        --stop-awake   end a running sleep inhibitor and exit
#        --no-reap --no-sync --dry-run --no-launch --no-claim
#
# Reaping the previous run's clones and fast-forwarding the base are ON by
# default, because both are things this script would otherwise simply refuse over
# — a leftover clone or a stale branch stops the run, and making the operator fix
# by hand what the script can verify and fix itself is the "remembered ritual"
# failure this project keeps rediscovering.
#
# Safety is unchanged: neither improvises. --reap checks every clone before
# removing any and refuses on uncommitted work or an attached session; --sync
# refuses a dirty tree and takes only a fast-forward. Opt out with --no-reap /
# --no-sync when you want the previous run's clones or base left exactly as they
# are.
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
# (Ghostty today); --windows forces separate windows.
#
# --max-agents is advisory only — it prints an instruction for you to pass on, and
# nothing under Claude Code enforces it. Omit it to run uncapped (the default).
set -uo pipefail

# MAX_AGENTS is deliberately EMPTY by default: uncapped is what fan-out actually
# runs, and a default cap would silently contaminate the uncapped baseline the plan
# needs before a cap can be evaluated at all (plan §18.1, Q-D1).
REPO="" BASE="" ROOT="$HOME/dev/cycles" HARNESS="claude" MAX_AGENTS="" MODE="" TABS=1
REAP=1 SYNC=1 AWAKE_HOURS=8 STOP_AWAKE=0
DRY=0 LAUNCH=1 CLAIM=1 ISSUES=()

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --base) BASE="${2:-}"; shift 2 ;;
    --clones-root) ROOT="${2:-}"; shift 2 ;;
    --harness) HARNESS="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --windows) TABS=0; shift ;;
    --awake) AWAKE_HOURS="${2:-8}"; shift 2 ;;
    --no-awake) AWAKE_HOURS=0; shift ;;
    --stop-awake) STOP_AWAKE=1; shift ;;
    --reap) REAP=1; shift ;;          # accepted for explicitness; already the default
    --sync) SYNC=1; shift ;;
    --no-reap) REAP=0; shift ;;
    --no-sync) SYNC=0; shift ;;
    --max-agents) MAX_AGENTS="${2:-}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --no-launch) LAUNCH=0; shift ;;
    --no-claim) CLAIM=0; shift ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    -*) echo "start-parallel-cycles: unknown flag '$1'" >&2; exit 2 ;;
    *) ISSUES+=("$1"); shift ;;
  esac
done



die() { printf 'start-parallel-cycles: REFUSING — %s\n' "$*" >&2; exit 1; }
say() { printf '  %s\n' "$*"; }
step() { printf '\n▸ %s\n' "$*"; }

# Why a leftover clone is dirty, in enough detail to act on.
#
# This refusal used to read "<path> has uncommitted changes. Commit or discard
# them, then re-run." — true, and reliably misread. The word "uncommitted" sends
# the operator to their own repo, which is clean, because that is the tree they
# were just working in; the path is a clones root they have no reason to be
# thinking about. Measured once for real: a month-old clone from an unrelated
# open PR, holding an abandoned `git merge` stopped on a conflict, refused three
# launches in a row while the operator re-checked a primary tree that was never
# the problem.
#
# So the report says three things the old one did not: that this is a *clone* and
# not the repo, whose branch it is and how old, and — when git is mid-operation —
# the exact command that ends it. An interrupted merge, rebase or cherry-pick is
# the common case here, because that is what a cycle that died mid-Phase-4 leaves
# behind, and `--abort` is both the right answer and not the one that comes to
# mind when the message says "commit or discard".
dirty_clone_report() {
  local wt="$1" gd branch when n out op=""
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

  # `.git` in a linked worktree is a *file* pointing at the real git dir, so
  # testing `$wt/.git/MERGE_HEAD` finds nothing and the interrupted merge this
  # function exists to name goes unreported. Ask git where its dir is.
  gd="$(git -C "$wt" rev-parse --git-dir 2>/dev/null)"
  case "$gd" in /*) ;; *) gd="$wt/$gd" ;; esac
  if   [ -e "$gd/MERGE_HEAD" ];       then op="merge"
  elif [ -d "$gd/rebase-merge" ] || [ -d "$gd/rebase-apply" ]; then op="rebase"
  elif [ -e "$gd/CHERRY_PICK_HEAD" ]; then op="cherry-pick"
  fi

  out="$wt has $n uncommitted change(s). Nothing was removed.
             This is a fan-out CLONE under $ROOT, not your repo — $REPO is
             not what this is about, and is probably clean.
             Clone is $branch, last commit $when."
  if [ -n "$op" ]; then
    out="$out
             A $op is in progress here and was never finished. End it with:
               git -C $wt $op --abort
             That returns the branch to its last commit and touches no remote,
             so anything already pushed — and any PR on it — is unaffected."
  else
    out="$out
             Commit or discard them, then re-run:
               git -C $wt status"
  fi
  printf '%s\n' "$out"
}

# `--stop-awake` is the teardown half. Round 11 finished in an hour with
# `--awake 10`, leaving nine hours of inhibitor behind holding a laptop awake for
# a round that no longer existed. The bound is a ceiling, not a lifetime, and
# nothing in the pipeline knows a round has ended — so until something does, this
# is the explicit way to say so.
if [ "$STOP_AWAKE" = 1 ]; then
  STOPPED=0
  P="$(cat "$ROOT/awake.pid" 2>/dev/null || true)"
  if [ -n "$P" ] && ps -p "$P" -o comm= 2>/dev/null | grep -q caffeinate; then
    kill "$P" 2>/dev/null && { say "stopped the sleep inhibitor (pid $P)"; STOPPED=1; }
  fi
  # The pid file can be gone while the process is not — a crash between the two,
  # or a hand-edited clones root. Reporting "none running" in that state is the
  # M16 failure exactly: mistaking a missing record for a missing process. Fall
  # back to matching our own flag signature, and say which route found it.
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

[ -n "$REPO" ] || REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not in a git repo (pass --repo)"
command -v git >/dev/null 2>&1 || die "git not found"
command -v omp >/dev/null 2>&1 || die "omp not found — clone creation uses 'omp worktree add', which is
             the only mechanism verified to preserve origin so gh resolves inside a clone"
[ "$CLAIM" = 0 ] || command -v gh >/dev/null 2>&1 || die "gh not found (or pass --no-claim)"

# base_branch from the deployment's config, unless overridden
if [ -z "$BASE" ]; then
  BASE="$(awk -F'|' '/^\| *base_branch *\|/{gsub(/^[ \t]+|[ \t]+$/,"",$3); print $3; exit}' \
          "$REPO/.omp/agent-config.md" 2>/dev/null)"
  [ -n "$BASE" ] || BASE="main"
fi

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
  [ "$REAP" = 0 ] || { say "would reap clones under $ROOT (skipped: --dry-run)"; WOULD_REAP=1; }
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

# --reap next: the worktree check below refuses on any leftover clone.
if [ "$REAP" = 1 ]; then
  reaped=0
  # Compare resolved paths: `git worktree list` reports the physical path, so on
  # macOS a clones-root under /var arrives as /private/var and a plain prefix test
  # silently matches nothing — reaping quietly becomes a no-op.
  ROOT_P="$(cd "$ROOT" 2>/dev/null && pwd -P)" || ROOT_P="$ROOT"
  # Two passes. Checking everything before removing anything means a refusal
  # leaves the previous run exactly as it was, rather than half-reaped — the
  # operator can then fix the one dirty clone and re-run the same command.
  CANDIDATES=()
  while read -r _ wt; do
    [ -n "$wt" ] || continue
    wt_p="$(cd "$wt" 2>/dev/null && pwd -P)" || wt_p="$wt"
    case "$wt_p" in "$ROOT_P"/*) ;; *) continue ;; esac
    # A clone is a linked worktree, so its feature branch lives in $REPO and
    # survives removal. Only uncommitted work is actually at risk — refuse on it
    # rather than deciding for the operator what is disposable.
    # agent_states/ is excluded: it is framework scratch the cycle owns and clears,
    # and this script writes the .fanout-clone marker into it itself. A deployment
    # that has not run the gitignore block regenerator would otherwise see every
    # clone as dirty and never be able to reap one.
    if [ -d "$wt" ] && [ -n "$(git -C "$wt" status --porcelain -- ':!agent_states' 2>/dev/null)" ]; then
      die "$(dirty_clone_report "$wt")"
    fi
    # Full path, not basename: a short name like "myapp-c1" matches far too much.
    # Report what matched — "something is running" is not an actionable refusal,
    # and the thing holding a clone is often not a session at all. Measured: a
    # flutter_tester from the previous run was still alive a day later, inside a
    # Phase-3 worktree the janitor had already deleted.
    # Match on the clone path, then follow children. The path appears in the
    # terminal's argv but NOT in the session's own — `claude "/cycle 442"` carries
    # no directory — so matching alone reports three lines of terminal plumbing and
    # hides the one process that matters. An operator reading that reasonably
    # concludes the window is stale chrome and kills it, when a live cycle is
    # parked inside.
    HOLDERS="$(pgrep -f "$wt_p" 2>/dev/null || true)"
    for h in $HOLDERS; do
      kids="$(pgrep -P "$h" 2>/dev/null || true)"
      [ -n "$kids" ] && HOLDERS="$HOLDERS
$kids"
    done
    HOLDERS="$(printf '%s\n' "$HOLDERS" | grep -v '^$' | sort -u || true)"
    if [ -n "$HOLDERS" ]; then
      printf 'start-parallel-cycles: REFUSING — %s still has processes attached:\n' "$wt_p" >&2
      # shellcheck disable=SC2086
      ps -o pid=,etime=,command= -p $(echo "$HOLDERS" | tr '\n' ' ') 2>/dev/null \
        | cut -c1-160 | sed 's/^/    /' >&2
      printf '    Close the session, or kill the leftovers:  kill %s\n' "$(echo "$HOLDERS" | tr '\n' ' ')" >&2
      printf '    Nothing was removed.\n' >&2
      exit 1
    fi
    CANDIDATES+=("$wt")
  done < <(git -C "$REPO" worktree list --porcelain | awk '/^worktree /{print $1, $2}')

  for wt in ${CANDIDATES[@]+"${CANDIDATES[@]}"}; do
    git -C "$REPO" worktree remove --force "$wt" 2>/dev/null \
      || die "could not remove $wt — remove it by hand."
    reaped=$((reaped+1))
  done
  git -C "$REPO" worktree prune 2>/dev/null
  [ "$reaped" = 0 ] || say "reaped $reaped clone(s) from $ROOT"

  # Rotation used to live here, conditioned on `reaped > 0`. It has moved to just
  # before the clones are created — see § run artifacts. Reaping is not the event
  # that starts a new run, and tying the two together meant a run whose clones had
  # already been removed by hand (`reap-clones.sh sweep`) rotated nothing and
  # appended to its predecessor's log. Measured in fan-out 5 (J2): two runs
  # commingled, and the first gate report attributed fan-out 4's 18h28m of
  # permission asks to fan-out 5.
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

WT="$(git -C "$REPO" worktree list | tail -n +2 | wc -l | tr -d ' ')"
if [ "$WT" != "0" ]; then
  # Under --dry-run the reap that would have cleared these was skipped, so
  # refusing over them would report a blocker the real run does not have.
  [ "$WOULD_REAP" = 1 ] \
    && say "$WT existing worktree(s) — the real run would reap them first" \
    || die "$WT existing worktree(s). Agents may be running; finish or prune them first."
fi

AVAIL_KB="$(df -k "$REPO" | tail -1 | awk '{print $4}')"
[ "$AVAIL_KB" -gt 5242880 ] || die "only $((AVAIL_KB/1024)) MB free — under the 5 GB floor."

say "branch $BASE, clean, no live state, no worktrees"
say "mode ${MODE:-per-story — from each issue Depth field}"
say "$((AVAIL_KB/1024/1024)) GB free"

# -P: resolve symlinks. Skills are deployed by symlinking a central framework
# checkout into the project, so the logical path walks back up into the *project*
# and records it as the framework — which is what run-provenance.txt said after
# fan-out 1 (evidence-run1 E6). The framework SHA is the point of this record.
FW_ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd -P)"
FW_SHA="$(git -C "$FW_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
FW_DIRTY="$(git -C "$FW_ROOT" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
say "framework $FW_ROOT @ $FW_SHA${FW_DIRTY:+ (${FW_DIRTY} uncommitted)}"
[ "${FW_DIRTY:-0}" = "0" ] || printf '  ! framework has uncommitted changes — deployments resolve to
    the working tree, so every cycle will run against them (plan §3.7).\n'

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
#
# Measured 2026-09-11: one deployment was missing 19 of 27 scaffold patterns and
# nothing had ever reported it.
if [ -x "$FW_ROOT/deploy.sh" ]; then
  if DEP_OUT="$(bash "$FW_ROOT/deploy.sh" check "$REPO" 2>&1)"; then
    say "deployment    $(printf '%s' "$DEP_OUT" | sed -n 's/^  \([0-9]*\/[0-9]* correct\).*/\1/p')"
  else
    printf '%s\n' "$DEP_OUT" | sed 's/^/  /' >&2
    die "deployment is incomplete — fix it before measuring a run:
             bash $FW_ROOT/deploy.sh link $REPO"
  fi
else
  say "deployment    not checked (no deploy.sh in $FW_ROOT)"
fi

# Gate capture is what fan-out 1 lost by relying on discipline (evidence-run1 E7).
# A warning, not a refusal: the hook is Claude Code only, and a run without it is
# valid — just unmeasured. Say which, before the run rather than after.
if [ "$HARNESS" = "claude" ]; then
  if grep -q 'gate-log.py' "$REPO/.claude/settings.json" 2>/dev/null; then
    say "gate capture wired"
  else
    printf '  ! gate-log hook not registered in %s — gate wait will NOT be captured.\n' \
      "$REPO/.claude/settings.json"
    printf '    Add it under hooks.Stop and hooks.UserPromptSubmit, or accept an unmeasured run.\n'
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
# without the field is an older deployment, not an error: those cycles fall back to
# /cycle's own heuristics, which is the previous behaviour.
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
        | python3 -c '
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
# Two cycles editing one file is not hypothetical and it is not always bad. In
# fan-out 7 two clones appended tests to `program_detail_view_test.dart` and git
# merged them without a conflict. In fan-out 8 one clone deleted the region
# another added to, in `settings_view.dart`, and the second PR is still open and
# conflicted — nothing in the pipeline owns a rebase after a cycle ends, so it
# simply stopped.
#
# The launcher is the only place that knows every issue before any work starts.
# It says so here rather than deciding: refuse, sequence, or start knowingly is
# the operator's call, and a pair that looks overlapping may not conflict at all.
#
# Read the signal as "these two issues work in the same area", NOT as "these two
# will collide in this file". Round 11 is the worked example: this check named
# #206 and #207 over `supabase/tests/rls_sweep_s2_test.sql`, the pair did
# conflict — and that file auto-merged cleanly. The conflict was in
# `supabase/tests/README.md`, which neither issue mentions and both cycles
# documented their new test in. The pairing was right; the named file was not the
# reason. Anything that later sequences on this output must sequence the *pair*,
# because sequencing only the named file would have let this pair run.
# Recorded in run-provenance.txt so a later evidence pass can tell "we knew" from
# "we found out".
#
# Stack-neutral by construction: a token counts as a file only if `git ls-files`
# knows it. A regex tuned to one language would silently see nothing in a repo
# that does not use it, which is the failure mode this project keeps finding in
# hand-written lists.
OVERLAP_DIR="$(mktemp -d)"
OVERLAP_FOUND=0
if command -v gh >/dev/null 2>&1; then
  for i in "${ISSUES[@]}"; do
    gh issue view "$i" --repo "$(cd "$REPO" && gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)" \
       --json body,title -q '.title + "\n" + .body' 2>/dev/null \
      | grep -oE '[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)+\.[A-Za-z0-9]+' \
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
    say "not a refusal — fan-out 7's overlap merged clean. Sequence them, drop one, or start knowing."
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
  step "Dry run — would create ${#ISSUES[@]} clone(s) under $ROOT"
  n=0; for i in "${ISSUES[@]}"; do n=$((n+1)); say "c$n → $ROOT/$(basename "$REPO")-c$n  (issue #$i)"; done
  exit 0
fi

mkdir -p "$ROOT" || die "cannot create clones root $ROOT"

# ---------------------------------------------------- clones (local, reversible)
step "Creating clones"
CLONES=() ; n=0
for i in "${ISSUES[@]}"; do
  n=$((n+1)); C="$ROOT/$(basename "$REPO")-c$n"
  [ -e "$C" ] && die "$C already exists. Remove it (git worktree remove) or use --clones-root."
  # --detach and NO -b: /cycle creates the feature branch itself at Phase 2B, and the
  # clone cannot be on $BASE because the primary has it checked out.
  omp worktree add --detach --cwd "$REPO" "$C" "$BASE" >/dev/null 2>&1 \
    || die "omp worktree add failed for $C. Clones so far: ${CLONES[*]:-none}"
  python3 "$C/.claude/skills/cycle/clear-agent-states.py" --all >/dev/null 2>&1 || true
  # A clone is a linked worktree of $REPO, so the telemetry hook's `--git-common-dir`
  # resolution points at $REPO and every clone commingles its events there
  # (evidence-run1 E1). This marker tells the hook the clone owns its own telemetry.
  # Written after the clear, and clear-agent-states.py preserves it thereafter.
  # gate_log: the Stop/UserPromptSubmit hook appends every gate wait here as well
  # as to the clone's own log, so one file holds the whole run (evidence-run1 E7).
  mkdir -p "$C/agent_states" && printf 'issue=%s\nclone=c%s\norigin=%s\ngate_log=%s\ncreated=%s\n' \
    "$i" "$n" "$REPO" "$ROOT/gate-log.tsv" "$(date -u +%FT%TZ)" > "$C/agent_states/.fanout-clone"
  CLONES+=("$C"); say "c$n  #$i  $C"
done

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
# that then refuses; rotating on reaping missed every run whose clones were
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

# The telemetry archive rotates for the same reason and did not, which is J2 in a
# second directory. Finalize copies each clone's events into
# $ROOT/telemetry/<clone>/, the clone names repeat every run, and nothing cleared
# it — so one directory accumulated four sessions and 989 events across four days
# while claiming to be one clone's telemetry. The aggregator's session warning
# does fire, so no report was misled; but pointing `--events` at it silently
# compares one round against the sum of every round, which is exactly the trap
# that made a cache figure three rounds wide earlier in this project.
if [ -d "$ROOT/telemetry" ] && [ -n "$(ls -A "$ROOT/telemetry" 2>/dev/null)" ]; then
  mv "$ROOT/telemetry" "$ROOT/telemetry-$ts" \
    && say "archived telemetry/ → telemetry-$ts/" \
    || say "! could not rotate telemetry/ — this run's events will commingle with the last"
fi
{
  printf '# run started %s\n' "$(date -u +%FT%TZ)"
  printf '# framework %s @ %s\n' "$FW_ROOT" "$FW_SHA"
  printf '# base %s @ %s\n' "$BASE" "$(git -C "$REPO" rev-parse --short HEAD)"
  printf '# disk_avail_kb_before %s\n' "$AVAIL_KB"
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
    omp) printf 'cd %q && omp "/cycle %s%s"' "$1" "$2" "$m" ;;
    *)   printf 'cd %q && claude "/cycle %s%s"' "$1" "$2" "$m" ;;
  esac
}

# ------------------------------------------------------------------- awake
#
# Round 9 lost three of five cycles to the machine they ran on. c2 and c3 died
# with "API Error: Your computer went to sleep mid-response"; c5 died reporting a
# 120-second tool timeout 15m46s after issuing the command, then "Not logged in ·
# Please run /login" — a wake artefact, not a separate fault. Two cycles finished
# and three were killed, and nothing here guarded against it.
#
# This is bounded on purpose. An unbounded caffeinate outlives the run, keeps a
# laptop awake for days and is exactly the kind of stale state M16 is about, so
# it self-terminates and leaves a pid file that a later run reaps.
#
# Honest limits, because a guard that is trusted further than it works is worse
# than none: `caffeinate` cannot keep a Mac awake with the lid closed on battery,
# and this is macOS-only. On anything else the run is told it is unprotected
# rather than left to assume otherwise.
# Only when cycles are actually being launched. `--no-launch` sets things up and
# prints commands; there is no run to protect, and the test suite exercises the
# launcher that way. Without this guard every `tests/check.py` spawned a real
# 8-hour sleep inhibitor on the developer's machine — three had accumulated as
# orphans before the first real run, which is the M16 stale-state failure
# arriving inside the fix for a different one.
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
    say "  Round 9 lost 3 of 5 cycles to the machine sleeping mid-run."
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
  # detection, shared with whatever else needs a window. This used to be a second,
  # worse copy inlined here: no iTerm path, and every Linux emulator invoked the
  # same way whether or not that was right.
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
    under Claude Code, so whether it holds is itself the measurement (plan §18.1, Q-D2).
    NOTE: this makes the run a CAPPED trial — it cannot serve as the uncapped baseline."
else
  AGENT_CAP_NOTE="  · No agent cap — uncapped is the default and the realistic case. Peak concurrent
    agents is the measurement (plan §18.1, Q-D1); do not instruct a cap mid-run, since a
    half-remembered one contaminates the baseline a capped comparison later needs."
fi

cat <<EOF

▸ During the run
  · Phase-3 agents run in the clone directly — NO nested worktree isolation. Under
    Claude Code it provisions at the default branch and under the primary repo, not the clone
    (plan §3.9, evidence-run1 E2). The clone is already the isolation.
$AGENT_CAP_NOTE
  · Gate waits record themselves — nothing to log by hand. Read them any time with
    python3 .claude/skills/cycle/gate-report.py --log $GATELOG
  · Is anything dead? A killed cycle logs the same row as a thinking one, so ask:
    python3 .claude/skills/cycle/cycle-health.py --root $ROOT
  · Sample \`df -k $REPO | tail -1\` MID-WAVE, while agents run. At rest a clone is ~4 MB.
  · Do not edit $FW_ROOT while cycles are live (plan §3.7).

▸ Teardown, per clone, once its PR is open and pushed
  git -C $REPO worktree remove <clone>
EOF
