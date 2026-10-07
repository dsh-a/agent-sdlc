#!/usr/bin/env bash
# Tests for .claude/skills/cycle/start-parallel-cycles.sh.
#
# The launcher had no test until fan-out 5, where it produced a P1: the run-level
# gate log was not rotated, so two runs' evidence commingled and a gate report
# attributed the previous run's 18h28m of permission asks to the current one
# (evidence-run5 J2). Rotation had been conditioned on reaping, and the clones
# had been removed by hand, so nothing rotated.
#
# `omp` and `gh` are stubbed on PATH. --no-launch and --no-claim keep it off the
# terminal and off GitHub, so everything below is local and reversible.
set -uo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
S="$ROOT_DIR/.claude/skills/cycle/start-parallel-cycles.sh"
FAILED=0
ok() { printf 'ok    %s\n' "$1"; }
bad() { printf 'FAIL  %s\n     %s\n' "$1" "${2:-}"; FAILED=1; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want [$3] got [$2]"; fi; }

R="$(mktemp -d)"; BIN="$R/bin"; mkdir -p "$BIN"

# omp worktree add -> plain git worktree add. The launcher uses omp because it
# preserves the origin remote so gh works inside a clone; for these tests the
# git equivalent is what matters.
cat > "$BIN/omp" <<'STUB'
#!/usr/bin/env bash
if [ "${1:-}" = "worktree" ] && [ "${2:-}" = "add" ]; then
  shift 2; CWD=""; ARGS=()
  while [ $# -gt 0 ]; do
    case "$1" in --cwd) CWD="$2"; shift 2 ;; *) ARGS+=("$1"); shift ;; esac
  done
  exec git -C "$CWD" worktree add "${ARGS[@]}"
fi
exit 0
STUB
# gh is only consulted for issue titles and claiming; --no-claim covers the writes.
cat > "$BIN/gh" <<'STUB'
#!/usr/bin/env bash
# Issue bodies are what overlap detection reads. 201 and 202 share a file; 203
# names one of its own; 204 names a path that is not tracked, which must not
# count as an overlap with anything.
case "$*" in
  *"issue view 201"*) echo "shared work"; echo "touches src/shared.txt and src/only201.txt" ;;
  *"issue view 202"*) echo "other work";  echo "touches src/shared.txt" ;;
  *"issue view 203"*) echo "unrelated";   echo "touches src/only203.txt" ;;
  *"issue view 204"*) echo "ghost";       echo "touches src/does_not_exist.txt" ;;
  *"issue view"*) echo "a stubbed issue title" ;;
  *"repo view"*)  echo "dsh-a/stub" ;;
  *) echo "" ;;
esac
exit 0
STUB
chmod +x "$BIN/omp" "$BIN/gh"
export PATH="$BIN:$PATH"

# An origin repo with a base branch, and a clones root carrying a previous run's
# evidence — the exact state fan-out 5 launched into.
REPO="$R/app"; CLONES="$R/cycles"
mkdir -p "$REPO" "$CLONES"
git init -q -b develop "$REPO"
git -C "$REPO" config user.email t@t; git -C "$REPO" config user.name t
echo app > "$REPO/README.md"
mkdir -p "$REPO/.claude" "$REPO/.omp"
# A properly deployed project, which is what the launcher's preflight requires:
# every framework hook wired and every framework script granted. Generated from
# the framework rather than written out, so adding a hook or a script does not
# silently make this fixture stale — the drift this suite's sibling exists for.
python3 - "$ROOT_DIR" > "$REPO/.claude/settings.json" <<'PY'
import json, pathlib, re, subprocess, sys
fw = pathlib.Path(sys.argv[1])
hooks = sorted(p.name for p in (fw / ".claude/hooks").glob("*.py"))
grants = subprocess.run(["bash", str(fw / "deploy.sh"), "grants"],
                        capture_output=True, text=True).stdout
allow = [m.group(1) for m in re.finditer(r'"(Bash\([^"]+\))",', grants)]
print(json.dumps({
    "permissions": {"allow": allow},
    "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
        {"type": "command", "command": f"python3 .claude/hooks/{h}"} for h in hooks]}]},
}, indent=2))
PY
cp "$ROOT_DIR/.omp/agent-config.md" "$REPO/.omp/agent-config.md"
git -C "$REPO" add -A; git -C "$REPO" commit -qm init

# Deploy the framework into it, exactly as a real project is. The launcher now
# refuses on an incomplete deployment, and a synthetic project that was never
# deployed is not the case worth testing. HOME is sandboxed so `link` cannot
# touch the real ~/.claude/skills.
export HOME="$R/home"; mkdir -p "$HOME"
# The links must be ignored, or the launcher refuses on a dirty tree — which is
# what a real project does with `deploy.sh gitignore`, so use it here too.
bash "$ROOT_DIR/deploy.sh" gitignore > "$REPO/.gitignore"
git -C "$REPO" add .gitignore; git -C "$REPO" commit -qm ignore
bash "$ROOT_DIR/deploy.sh" link "$REPO" >/dev/null 2>&1 \
  || { echo "FAIL  could not deploy the framework into the test project"; exit 1; }
[ -z "$(git -C "$REPO" status --porcelain)" ] \
  || { echo "FAIL  deployment left the project dirty"; git -C "$REPO" status --short; exit 1; }

printf 'raised_at\tanswered_at\n2026-09-10T04:08:38Z\t-\n' > "$CLONES/gate-log.tsv"
printf '# run started 2026-09-10T04:41:01Z\n' > "$CLONES/run-provenance.txt"
PREV_LOG_SUM="$(cksum < "$CLONES/gate-log.tsv")"

out="$(bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" \
        --no-sync --no-launch --no-claim 101 102 2>&1)"; rc=$?

chk "launcher succeeds with no clones to reap" "$rc" 0
chk "  ... and creates one clone per issue" \
    "$(git -C "$REPO" worktree list | tail -n +2 | wc -l | tr -d ' ')" 2

# The regression under test. Nothing was reaped — there was nothing to reap —
# and the previous run's log must still be moved aside.
chk "rotates the previous run's gate log even when nothing was reaped" \
    "$(ls "$CLONES" | grep -c '^gate-log-.*\.tsv$')" 1
chk "  ... and its provenance" \
    "$(ls "$CLONES" | grep -c '^run-provenance-.*\.txt$')" 1
chk "  ... preserving the old content, not deleting it" \
    "$(cat "$CLONES"/gate-log-*.tsv | cksum)" "$PREV_LOG_SUM"
chk "  ... leaving no rows from the previous run in the live log" \
    "$(grep -c '2026-09-10' "$CLONES/gate-log.tsv" 2>/dev/null || echo 0)" 0
chk "  ... and the new provenance names only this run" \
    "$(grep -c '2026-09-10T04:41:01Z' "$CLONES/run-provenance.txt")" 0

# Markers are what tell the telemetry hooks a clone owns its own events.
chk "each clone gets a fan-out marker" \
    "$(ls "$CLONES"/*/agent_states/.fanout-clone 2>/dev/null | wc -l | tr -d ' ')" 2
chk "  ... naming the run-level gate log" \
    "$(grep -c "gate_log=$CLONES/gate-log.tsv" "$CLONES"/app-c1/agent_states/.fanout-clone)" 1
chk "  ... and the issue it was created for" \
    "$(grep -c '^issue=101$' "$CLONES"/app-c1/agent_states/.fanout-clone)" 1

# A second run must rotate again rather than append to the first. Simulate the
# cycles having run: with --no-launch nothing writes gate-log.tsv, so without
# this the second run has nothing to rotate and the check is vacuous.
sleep 1
printf 'raised_at\tanswered_at\n2026-09-11T13:37:22Z\t-\n' > "$CLONES/gate-log.tsv"
bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" \
     --no-sync --no-launch --no-claim 103 >/dev/null 2>&1
chk "a repeat run rotates again" "$(ls "$CLONES" | grep -c '^gate-log-.*\.tsv$')" 2
chk "  ... and the second run's log starts empty of the first's rows" \
    "$(grep -c '2026-09-11T13:37:22Z' "$CLONES/gate-log.tsv" 2>/dev/null || echo 0)" 0
chk "  ... and reaps the previous clones" \
    "$(git -C "$REPO" worktree list | tail -n +2 | wc -l | tr -d ' ')" 1

# --dry-run must still change nothing at all.
BEFORE="$(ls "$CLONES" | sort | cksum)"
bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" \
     --no-sync --dry-run 104 >/dev/null 2>&1
chk "--dry-run rotates nothing" "$(ls "$CLONES" | sort | cksum)" "$BEFORE"

# The telemetry archive rotates for the same reason the gate log does, and did
# not: clone names repeat every run, so Finalize's copies pile up in one
# directory. Measured: four sessions and 989 events in a directory labelled as
# one clone's telemetry.
mkdir -p "$CLONES/telemetry/app-c1"
echo '{"ts":"old"}' > "$CLONES/telemetry/app-c1/orchestrator.jsonl"
sleep 1
out="$(bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" \
       --no-sync --no-launch --no-claim 105 2>&1)"
chk "a real run rotates the telemetry archive" \
    "$(ls -d "$CLONES"/telemetry-* 2>/dev/null | wc -l | tr -d ' ')" 1
chk "  ... and says so" "$(printf '%s' "$out" | grep -c 'archived telemetry/')" 1
chk "  ... leaving the live directory clear for this run" \
    "$([ -e "$CLONES/telemetry/app-c1/orchestrator.jsonl" ] && echo yes || echo no)" no
chk "  ... with the previous run's events intact under the archive" \
    "$(cat "$CLONES"/telemetry-*/app-c1/orchestrator.jsonl 2>/dev/null)" '{"ts":"old"}'

# ---------------------------------------------------------- file overlap
#
# The launcher is the only place that knows every issue before any work starts.
# Fan-out 8 started two cycles that edited one region of one file; the second PR
# is still open and conflicted, because nothing owns a rebase after a cycle ends.
# This does not refuse — fan-out 7's overlap merged clean — it makes the pair
# visible while it is still cheap to change.
mkdir -p "$REPO/src"
echo x > "$REPO/src/shared.txt"; echo x > "$REPO/src/only201.txt"
echo x > "$REPO/src/only203.txt"
git -C "$REPO" add -A >/dev/null 2>&1
git -C "$REPO" commit -qm "overlap fixture" >/dev/null 2>&1

out="$(bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" --no-sync --dry-run 201 202 203 2>&1)"
chk "an overlapping pair is reported" "$(printf '%s' "$out" | grep -c '#201 and #202')" 1
chk "  ... naming the shared file" "$(printf '%s' "$out" | grep -c 'src/shared.txt')" 1
chk "  ... and not a file only one of them names" \
    "$(printf '%s' "$out" | grep -c 'src/only201.txt')" 0
chk "  ... not pairing the unrelated issue" \
    "$(printf '%s' "$out" | grep -cE '#203 and |and #203 both')" 0
chk "  ... and saying it is not a refusal" \
    "$(printf '%s' "$out" | grep -c 'not a refusal')" 1
chk "  ... while still proceeding to the dry run" \
    "$(printf '%s' "$out" | grep -c 'would create 3')" 1

out="$(bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" --no-sync --dry-run 201 203 2>&1)"
chk "no overlap is stated positively, not by silence" \
    "$(printf '%s' "$out" | grep -c 'no file overlap')" 1

# A path an issue names but git does not track is not a file. Tying this to
# `git ls-files` is what keeps the check stack-neutral: a regex tuned to one
# language sees nothing in a repo that does not use it.
out="$(bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" --no-sync --dry-run 201 204 2>&1)"
chk "an untracked path is not counted as overlap" \
    "$(printf '%s' "$out" | grep -c 'no file overlap')" 1

# --- the sleep inhibitor must not leak out of a test ---------------------
#
# The launcher inhibits system sleep for a run's duration. Before this guard,
# every `tests/check.py` spawned a real 8-hour `caffeinate` on the developer's
# machine, and three had accumulated as orphans before the first real run — the
# M16 stale-state failure arriving inside the fix for a different one. A test
# suite must not change the power state of the host running it.
before_caf="$(pgrep -f 'caffeinate -dimsu' 2>/dev/null | wc -l | tr -d ' ')"
bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" --no-launch 1 >/dev/null 2>&1
after_caf="$(pgrep -f 'caffeinate -dimsu' 2>/dev/null | wc -l | tr -d ' ')"
chk "no sleep inhibitor is spawned without a launch" "$after_caf" "$before_caf"

# Asserted as a count rather than on the message, because a fixture that aborts
# at preflight never reaches the awake block at all — the message assertion would
# pass or fail for reasons unrelated to the guard. The count is what has teeth:
# three inhibitors leaked from three `check.py` runs before this guard existed,
# and none since.

# --- --stop-awake ---------------------------------------------------------
#
# Round 11 finished in an hour with --awake 10 and left nine hours of inhibitor
# behind, holding a laptop awake for a round that no longer existed. The bound is
# a ceiling, not a lifetime, and nothing knows a round has ended — so this is the
# explicit way to say so.
mkdir -p "$CLONES"
out="$(bash "$S" --clones-root "$CLONES" --stop-awake 2>&1)"; rc=$?
chk "--stop-awake exits 0 with nothing running" "$rc" 0
chk "  ... and says so rather than claiming a kill" \
    "$(printf '%s' "$out" | grep -c 'no sleep inhibitor is running')" 1

# It must run before any work: ending a round must not reap the round.
out="$(bash "$S" --clones-root "$CLONES" --stop-awake 2>&1)"
chk "  ... and does no preflight, no sync, no reaping" \
    "$(printf '%s' "$out" | grep -cE 'Preflight|reaped|synced')" 0

# A pid file naming a process that is not ours must not be killed.
echo 99999999 > "$CLONES/awake.pid"
out="$(bash "$S" --clones-root "$CLONES" --stop-awake 2>&1)"
chk "a stale pid file is not mistaken for a running inhibitor" \
    "$(printf '%s' "$out" | grep -c 'no sleep inhibitor is running')" 1
[ -f "$CLONES/awake.pid" ] && bad "the stale pid file is cleared" "still present" \
                          || ok "the stale pid file is cleared"

# --------------------------------------------- the dirty-clone refusal ----
#
# Reaping refuses on a clone with uncommitted work, which is right. What was
# wrong was the message: "<path> has uncommitted changes. Commit or discard
# them." sends the operator to their own repo, which is clean, because that is
# the tree they were just in — the clones root is not somewhere they are
# thinking about. It cost three straight launches against a month-old clone
# from an unrelated open PR, holding an abandoned merge.
#
# So the refusal must say it is a clone, name the primary repo as *not* the
# problem, and when git is mid-operation give the `--abort` that ends it —
# which is not the command "commit or discard" brings to mind.
DC="$R/dirty"; mkdir -p "$DC/clones"
git init -q -b develop "$DC/origin"
git -C "$DC/origin" config user.email t@t; git -C "$DC/origin" config user.name t
echo base > "$DC/origin/f.txt"; git -C "$DC/origin" add -A
git -C "$DC/origin" commit -qm base
git -C "$DC/origin" checkout -q -b feat
echo theirs > "$DC/origin/f.txt"; git -C "$DC/origin" commit -qam theirs
git -C "$DC/origin" checkout -q develop
echo ours > "$DC/origin/f.txt"; git -C "$DC/origin" commit -qam ours

# The helper is sourced rather than driven through a full launch: the refusal is
# a pure function of one clone's state, and a full launch would need an origin,
# a deployment and a board just to reach it.
dc_report() {
  ROOT="$DC/clones" REPO="$DC/origin" bash -c '
    source /dev/stdin <<<"$(sed -n "/^dirty_clone_report()/,/^}/p" '"$S"')"
    dirty_clone_report "'"$1"'"'
}

git -C "$DC/origin" worktree add -q "$DC/clones/app-c1" feat
git -C "$DC/clones/app-c1" merge develop >/dev/null 2>&1 || true
out="$(dc_report "$DC/clones/app-c1")"
chk "the dirty-clone refusal says it is a clone, not the repo" \
    "$(printf '%s' "$out" | grep -c 'fan-out CLONE')" 1
chk "  ... and names the primary repo as the thing it is NOT about" \
    "$(printf '%s' "$out" | grep -c "$DC/origin is")" 1
chk "  ... and counts the changes" \
    "$(printf '%s' "$out" | grep -c 'has 1 uncommitted change')" 1
chk "  ... and says nothing was removed" \
    "$(printf '%s' "$out" | grep -c 'Nothing was removed')" 1
chk "  ... and names an interrupted merge" \
    "$(printf '%s' "$out" | grep -c 'A merge is in progress')" 1
chk "  ... handing over the abort, which is not 'commit or discard'" \
    "$(printf '%s' "$out" | grep -c 'merge --abort')" 1
# `.git` in a linked worktree is a FILE pointing elsewhere, so a naive
# $wt/.git/MERGE_HEAD test finds nothing and reports a plain dirty tree.
chk "  ... detecting it via rev-parse, not \$wt/.git/MERGE_HEAD" \
    "$(printf '%s' "$out" | grep -c 'Commit or discard')" 0

git -C "$DC/origin" worktree add -q "$DC/clones/app-c3" -b cp develop
git -C "$DC/clones/app-c3" cherry-pick feat >/dev/null 2>&1 || true
chk "an interrupted cherry-pick is named too, with its own abort" \
    "$(dc_report "$DC/clones/app-c3" | grep -c 'cherry-pick --abort')" 1

# No operation in progress: plain edits get the plain instruction.
git -C "$DC/origin" worktree add -q --detach "$DC/clones/app-c2" develop
echo scratch > "$DC/clones/app-c2/f.txt"; echo extra > "$DC/clones/app-c2/new.txt"
out="$(dc_report "$DC/clones/app-c2")"
chk "plain uncommitted edits get 'commit or discard', no phantom abort" \
    "$(printf '%s' "$out" | grep -c 'Commit or discard')" 1
chk "  ... and no --abort is suggested" \
    "$(printf '%s' "$out" | grep -c -- '--abort')" 0
# A fan-out clone is created detached, so this is the common shape, and
# `--abbrev-ref HEAD` returning "HEAD" would name nothing.
chk "  ... and a detached clone reports its sha, not the word HEAD" \
    "$(printf '%s' "$out" | grep -c 'detached at')" 1
chk "  ... never 'branch HEAD'" \
    "$(printf '%s' "$out" | grep -c 'branch HEAD')" 0

printf '\nstart-parallel-cycles: %s\n' \
  "$([ $FAILED = 0 ] && echo 'all checks passed.' || echo 'FAILURES above.')"
exit $FAILED
