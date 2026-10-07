#!/usr/bin/env bash
# run-suite.sh — start a long command, poll it, read a bounded tail. One stove.
#
# Exists because of two measured facts (evidence-run2 F1):
#
#   * An agent is killed after 600s without progress, and the progress clock is
#     time between *tool results*. A single Bash call that blocks for the whole
#     of `flutter test` therefore dies — three agents were killed this way, one
#     of them the salvage agent sent to recover the first.
#   * The full suite takes 2m39s solo at 343% CPU. Three fan-out clones running
#     it at once each stretch to roughly eight minutes, which is how a 600s limit
#     gets crossed without anything being wrong.
#
# So: `start` returns immediately, `check` is one quick call the agent can make
# as often as it likes, and each check resets the progress clock. The waiting is
# still real — it just stops looking like a hang.
#
# The lock is the second half. Under a fan-out every clone shares one machine, so
# only one full suite runs at a time; the others queue. Three eight-minute
# fights become three two-and-a-half-minute turns, and nothing starves.
#
#   run-suite.sh start  <name> -- flutter test
#   run-suite.sh check  <name> [--lines N]
#   run-suite.sh wait   <name> [--timeout S]   # orchestrator only — this blocks
#   run-suite.sh log    <name>                 # full path to the output
#
# `check` exits 0 done-and-passed, 2 done-and-failed, 3 still running or queued.
# Output is bounded by default: the suite prints ~18,800 lines / 2.1 MB, and no
# agent needs that in its context to learn that 3,591 tests passed.
#
# Three exit states, not two — **do not poll with a boolean.** Shell treats every
# non-zero alike, so `until ! run-suite.sh check <name>` exits *immediately*: 3
# means still running, `!` makes that true, and "still running" becomes the stop
# condition. An orchestrator wrote exactly that in fan-out 6 and reported a suite
# as finished with ~70s left on it. A pipeline hides the same thing the other
# way: under `set -o pipefail`, `check | grep -q PASS` returns check's 3 rather
# than grep's verdict. Branch on the code:
#
#   while :; do
#     run-suite.sh check "$n" >/dev/null; rc=$?
#     [ "$rc" = 3 ] || break          # 0 passed, 2 failed, anything else is real
#     sleep 20
#   done

set -uo pipefail

# A lock is broken only when its holder is provably gone. Age alone is not
# evidence: the whole premise of this script is that a run stretches under
# contention, so "old" and "abandoned" are exactly the two states an age test
# cannot tell apart. The age bound remains as a backstop for a holder whose pid
# was reused or never recorded.
STALE_LOCK_S=7200
POLL_S=5

usage() { sed -n '2,43p' "$0"; exit "${1:-0}"; }
die() { printf 'run-suite: %s\n' "$*" >&2; exit 1; }

CMD_NAME="${1:-}"; shift 2>/dev/null || true
NAME="${1:-}"; shift 2>/dev/null || true
case "$CMD_NAME" in ''|-h|--help) usage 0 ;; esac
[ -n "$NAME" ] || die "no name given. Example: run-suite.sh start phase3 -- flutter test"
case "$NAME" in *[!A-Za-z0-9._-]*) die "name may only contain letters, digits, . _ -" ;; esac

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not in a git repo"
MARKER="$ROOT/agent_states/.fanout-clone"
STATE="$ROOT/agent_states/suite/$NAME"

# The lock must be shared by every clone of one fan-out, so it lives beside the
# run's other artifacts rather than inside any one clone. Solo runs lock against
# themselves, which costs nothing and keeps one code path.
LOCK_ROOT="$ROOT/agent_states"
if [ -f "$MARKER" ]; then
  gl="$(awk -F= '/^gate_log=/{print $2; exit}' "$MARKER" 2>/dev/null)"
  [ -n "$gl" ] && [ -d "$(dirname "$gl")" ] && LOCK_ROOT="$(dirname "$gl")"
fi
LOCK="$LOCK_ROOT/.suite.lock"

case "$CMD_NAME" in
start)
  [ "${1:-}" = "--" ] && shift || die "expected -- before the command"
  [ $# -gt 0 ] || die "no command given after --"
  # Refuse rather than clobber. Two callers using one name is a caller bug, but
  # `rm -rf` would make it a silent data race: the loser's completion lands in a
  # directory the winner recreated, and it polls a run that never resolves.
  if [ -d "$STATE" ] && [ -f "$STATE/started_at" ] && [ ! -f "$STATE/rc" ]; then
    holder="$(cat "$STATE/pid" 2>/dev/null || echo)"
    if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
      die "a run named '$NAME' is already in flight (pid $holder). Use a different name."
    fi
  fi
  rm -rf "$STATE" 2>/dev/null
  mkdir -p "$STATE" || die "cannot create $STATE"
  printf '%s\n' "$*" > "$STATE/cmd"
  date -u +%s > "$STATE/queued_at"

  # The waiter holds the lock only while the command runs, and releases it on any
  # exit path — a lock leaked by a killed agent would stall every other clone.
  nohup bash -c '
    STATE="$1"; LOCK="$2"; STALE="$3"; POLL="$4"; shift 4
    while ! mkdir "$LOCK" 2>/dev/null; do
      if [ -d "$LOCK" ]; then
        holder="$(cat "$LOCK/pid" 2>/dev/null || echo)"
        # Dead holder -> the lock is genuinely abandoned, whatever its age.
        if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
          rm -f "$LOCK/pid" 2>/dev/null; rmdir "$LOCK" 2>/dev/null; continue
        fi
        # No pid recorded, or a pid that may have been reused: fall back to age.
        if [ -z "$holder" ]; then
          age=$(( $(date -u +%s) - $(stat -f %m "$LOCK" 2>/dev/null || stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
          [ "$age" -gt "$STALE" ] && rmdir "$LOCK" 2>/dev/null && continue
        fi
      fi
      sleep "$POLL"
    done
    trap "rm -f \"$LOCK/pid\" 2>/dev/null; rmdir \"$LOCK\" 2>/dev/null" EXIT INT TERM
    echo $$ > "$LOCK/pid"
    echo $$ > "$STATE/pid"
    date -u +%s > "$STATE/started_at"
    ( eval "$*" ) > "$STATE/out" 2>&1
    echo $? > "$STATE/rc"
    date -u +%s > "$STATE/ended_at"
  ' _ "$STATE" "$LOCK" "$STALE_LOCK_S" "$POLL_S" "$@" >/dev/null 2>&1 &
  disown 2>/dev/null

  echo "run-suite: started '$NAME' — poll with: run-suite.sh check $NAME"
  ;;

check|wait)
  [ -d "$STATE" ] || die "no such run '$NAME' (nothing started)"
  LINES=15; TIMEOUT=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --lines) LINES="${2:-15}"; shift 2 ;;
      --timeout) TIMEOUT="${2:-0}"; shift 2 ;;
      *) shift ;;
    esac
  done

  if [ "$CMD_NAME" = wait ]; then
    began="$(date -u +%s)"
    while [ ! -f "$STATE/rc" ]; do
      [ "$TIMEOUT" -gt 0 ] && [ $(( $(date -u +%s) - began )) -ge "$TIMEOUT" ] && break
      sleep "$POLL_S"
    done
  fi

  now="$(date -u +%s)"
  if [ -f "$STATE/rc" ]; then
    rc="$(cat "$STATE/rc")"
    el=$(( $(cat "$STATE/ended_at" 2>/dev/null || echo "$now") - $(cat "$STATE/started_at" 2>/dev/null || echo "$now") ))
    printf 'run-suite: %s — %s in %ss\n' "$NAME" "$([ "$rc" = 0 ] && echo PASSED || echo "FAILED (exit $rc)")" "$el"
    tail -n "$LINES" "$STATE/out" 2>/dev/null
    [ "$rc" = 0 ] || printf '\nFull output: %s\n' "$STATE/out"
    [ "$rc" = 0 ] && exit 0 || exit 2
  elif [ -f "$STATE/started_at" ]; then
    printf 'run-suite: %s — RUNNING for %ss\n' "$NAME" "$(( now - $(cat "$STATE/started_at") ))"
    tail -n 3 "$STATE/out" 2>/dev/null
    exit 3
  else
    printf 'run-suite: %s — QUEUED for %ss (another clone holds the lock)\n' \
      "$NAME" "$(( now - $(cat "$STATE/queued_at" 2>/dev/null || echo "$now") ))"
    exit 3
  fi
  ;;

log) [ -d "$STATE" ] || die "no such run '$NAME'"; printf '%s\n' "$STATE/out" ;;
*) usage 1 ;;
esac
