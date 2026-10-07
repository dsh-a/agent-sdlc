#!/usr/bin/env bash
# Tests for .claude/skills/cycle/run-suite.sh.
#
# The properties that matter are both about *not blocking*: `start` must return
# fast enough that the caller's progress clock never runs down (three agents were
# killed by a 600s watchdog while a bare `flutter test` blocked their only tool
# call), and `check` must stay cheap however long the work takes. The lock is the
# other half — under a fan-out, clones must take turns rather than fight for one
# CPU.
set -uo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.claude/skills/cycle/run-suite.sh"
FAILED=0
ok() { printf 'ok    %s\n' "$1"; }
bad() { printf 'FAIL  %s\n     %s\n' "$1" "${2:-}"; FAILED=1; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want [$3] got [$2]"; fi; }

R="$(mktemp -d)"; git init -q "$R"; cd "$R"

# start must return immediately even for slow work.
t0=$(date +%s)
bash "$S" start slow -- 'sleep 8; echo finished' >/dev/null 2>&1
t1=$(date +%s)
chk "start returns immediately (<3s) for slow work" "$([ $((t1-t0)) -lt 3 ] && echo yes || echo no)" yes

# Immediately after a non-blocking start there are two correct answers, because
# `start` returns before the background worker has taken the lock: QUEUED until
# it writes started_at, RUNNING after. Both exit 3. This asserted RUNNING and so
# raced the worker — it passed on a quiet laptop for months and failed the first
# time it ran on a CI runner, which is the whole argument for gating on it.
out="$(bash "$S" check slow 2>&1)"; rc=$?
chk "check reports an in-flight state right after start" \
    "$(echo "$out" | grep -cE 'RUNNING|QUEUED')" 1
chk "  ... and exits 3 for not-finished" "$rc" 3

# Then the transition itself, without a race: wait for the worker to take the
# lock, and only then require the word. Bounded so a genuinely stuck worker
# fails the test rather than hanging it.
# `case` on a command substitution, not `check | grep -q`: this file runs with
# `pipefail`, so that pipeline takes check's exit 3 rather than grep's 0 and the
# `&& break` never fires — the loop then outlives the 8s job and asserts RUNNING
# after it has finished. Same family as the zsh glob in evidence-run2 F2: the
# test harness's own shell settings changed what the test measured.
for _ in $(seq 1 40); do
  case "$(bash "$S" check slow 2>&1)" in *RUNNING*) break ;; esac
  sleep 0.25
done
out="$(bash "$S" check slow 2>&1)"; rc=$?
chk "  ... and reports RUNNING once the worker holds the lock" \
    "$(echo "$out" | grep -c RUNNING)" 1
chk "  ... still exiting 3" "$rc" 3

# check must stay cheap — it is called repeatedly to keep the clock alive.
t0=$(date +%s); bash "$S" check slow >/dev/null 2>&1; t1=$(date +%s)
chk "check is cheap (<2s)" "$([ $((t1-t0)) -lt 2 ] && echo yes || echo no)" yes

bash "$S" wait slow --timeout 30 >/dev/null 2>&1
out="$(bash "$S" check slow 2>&1)"; rc=$?
chk "finished run reports PASSED" "$(echo "$out" | grep -c PASSED)" 1
chk "  ... exits 0" "$rc" 0
chk "  ... and shows the command's output" "$(echo "$out" | grep -c finished)" 1

# Failure must be distinguishable from success by exit code, not by reading prose.
bash "$S" start bad -- 'echo oops; exit 7' >/dev/null 2>&1
bash "$S" wait bad --timeout 20 >/dev/null 2>&1
out="$(bash "$S" check bad 2>&1)"; rc=$?
chk "failure exits 2" "$rc" 2
chk "  ... names the exit code" "$(echo "$out" | grep -c 'exit 7')" 1
chk "  ... and points at the full log" "$(echo "$out" | grep -c 'Full output')" 1

# Output bounding: the real suite prints ~18,800 lines and no agent needs them.
bash "$S" start noisy -- 'for i in $(seq 1 5000); do echo "line $i"; done' >/dev/null 2>&1
bash "$S" wait noisy --timeout 60 >/dev/null 2>&1
n="$(bash "$S" check noisy 2>/dev/null | wc -l | tr -d ' ')"
chk "check bounds output by default" "$([ "$n" -lt 25 ] && echo yes || echo no)" yes
chk "  ... but the full log is kept" "$(wc -l < "$(bash "$S" log noisy)" | tr -d ' ')" 5000

# The lock: one at a time, and it must release.
bash "$S" start lockA -- 'sleep 6; echo A' >/dev/null 2>&1
bash "$S" start lockB -- 'echo B' >/dev/null 2>&1
sleep 1
chk "second run queues behind the first" "$(bash "$S" check lockB 2>&1 | grep -c QUEUED)" 1
bash "$S" wait lockB --timeout 40 >/dev/null 2>&1
chk "  ... then runs once the lock frees" "$(bash "$S" check lockB 2>&1 | grep -c PASSED)" 1
chk "  ... and the lock is released" "$([ -d "$R/agent_states/.suite.lock" ] && echo held || echo free)" free

# A fan-out clone locks against its clones root, not its own tree, or the clones
# would not contend with each other at all.
mkdir -p "$R/agent_states" "$R/../shared"
printf 'gate_log=%s/gate-log.tsv\n' "$(cd "$R/.." && pwd)/shared" > "$R/agent_states/.fanout-clone"
bash "$S" start fan -- 'sleep 3' >/dev/null 2>&1
sleep 1
chk "fan-out clone locks at the clones root" \
  "$([ -d "$(cd "$R/.." && pwd)/shared/.suite.lock" ] && echo yes || echo no)" yes
bash "$S" wait fan --timeout 30 >/dev/null 2>&1
# Drop the marker again: it redirects the lock, and later cases assert on the
# in-repo lock path. (Leaving it here made a SIGKILL case look like a pass.)
rm -f "$R/agent_states/.fanout-clone"

chk "unknown name is an error, not a silent pass" \
  "$(bash "$S" check nope >/dev/null 2>&1; echo $?)" 1

# --- the paths the mechanism exists for -------------------------------------

# A killed holder must not strand every other clone. SIGKILL cannot be trapped,
# so the EXIT trap does not run and the lock dir survives its owner — the one
# case an age-based staleness test gets wrong, and the founding scenario of this
# whole change (an agent killed mid-test-run).
bash "$S" start victim -- 'sleep 120' >/dev/null 2>&1
sleep 2
vpid="$(cat "$R/agent_states/suite/victim/pid" 2>/dev/null || echo)"
chk "a running job records its pid" "$([ -n "$vpid" ] && echo yes || echo no)" yes
kill -9 "$vpid" 2>/dev/null
sleep 1
chk "  ... SIGKILL leaves the lock behind (trap cannot fire)" \
  "$([ -d "$R/agent_states/.suite.lock" ] && echo held || echo free)" held
bash "$S" start after-kill -- 'echo recovered' >/dev/null 2>&1
bash "$S" wait after-kill --timeout 40 >/dev/null 2>&1
chk "  ... but the next run breaks it and proceeds" \
  "$(bash "$S" check after-kill 2>&1 | grep -c PASSED)" 1

# Two callers on one name must not silently corrupt each other's state. verify
# and review were both told to use the name "verify" on the fallback path.
bash "$S" start dup -- 'sleep 8' >/dev/null 2>&1
sleep 1
out="$(bash "$S" start dup -- 'echo second' 2>&1)"; rc=$?
chk "a second start on a live name refuses" "$rc" 1
chk "  ... and says why" "$(echo "$out" | grep -c 'already in flight')" 1
chk "  ... leaving the first run intact" "$(bash "$S" check dup 2>&1 | grep -c 'RUNNING\|PASSED')" 1
bash "$S" wait dup --timeout 30 >/dev/null 2>&1

# Reusing a name after the run finished is fine — that is not a collision.
bash "$S" start dup -- 'echo reused' >/dev/null 2>&1
bash "$S" wait dup --timeout 30 >/dev/null 2>&1
chk "a finished name can be reused" "$(bash "$S" check dup 2>&1 | grep -c reused)" 1

[ "$FAILED" = 0 ] && { echo; echo "run-suite: all checks passed."; } || { echo; echo "run-suite: FAILURES"; }
exit $FAILED
