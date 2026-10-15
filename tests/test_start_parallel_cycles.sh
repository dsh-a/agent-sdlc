#!/usr/bin/env bash
# Tests for .claude/skills/cycle/start-parallel-cycles.sh.
#
# The run-level gate log rotates on every real run, reaped or not: unrotated,
# two runs' evidence commingles and a gate report charges the previous run's
# permission asks to the current one.
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

# The root has a space, as a Windows profile path can, so every path below does.
R="$(mktemp -d)/with space"; BIN="$R/bin"; mkdir -p "$BIN"

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
  # Sliced stories, for partial checkout: 401 touches health, 403 touches other.
  *"issue view 401"*) printf '%s\n' "health" "## Acceptance Criteria" "1. a" "2. b" "" "## Slices" \
                        '1. Model — `lib/domain/health/` — AC 1' '2. Screen — `lib/ui/health/view.txt` — AC 2' ;;
  *"issue view 403"*) printf '%s\n' "other" "## Acceptance Criteria" "1. a" "" "## Slices" \
                        '1. Other — `lib/other/` — all ACs' ;;
  *"issue view"*) echo "a stubbed issue title" ;;
  *"repo view"*)  echo "dsh-a/stub" ;;
  *) echo "" ;;
esac
exit 0
STUB
chmod +x "$BIN/omp" "$BIN/gh"
export PATH="$BIN:$PATH"

# An origin repo with a base branch, and a clones root carrying a previous run's
# evidence and no clones to reap.
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
sys.path.insert(0, str(fw / ".claude/skills/cycle"))
import git_bash
hooks = sorted(p.name for p in (fw / ".claude/hooks").glob("*.py"))
grants = subprocess.run([git_bash.bash(), (fw / "deploy.sh").as_posix(), "grants"],
                        capture_output=True, text=True).stdout
allow = [m.group(1) for m in re.finditer(r'"(Bash\([^"]+\))",', grants)]
# ... and wired as the framework's sample wires them, on every handled event.
wiring = json.loads((fw / ".claude/settings.json.sample").read_text())["hooks"]
wiring.setdefault("PreToolUse", []).append({"matcher": "*", "hooks": [
    {"type": "command", "command": f"python3 .claude/hooks/{h}"} for h in hooks]})
print(json.dumps({"permissions": {"allow": allow}, "hooks": wiring}, indent=2))
PY
cp "$ROOT_DIR/.omp/agent-config.md" "$REPO/.omp/agent-config.md"
# ... and every command in its § Project Commands table granted.
bash "$ROOT_DIR/deploy.sh" grants --apply "$REPO" >/dev/null
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
# Every command the run prints pastes as printed: with the clones root under a
# path with a space, each line parses and each path arrives as one argument.
args_of() { bash -c 'a() { printf "%s\n" "$@"; }; eval "a $1"' _ "$1"; }
cmds="$(printf '%s\n' "$out" | sed -n -e 's/^ *\(cd .* && claude .*\)/\1/p' \
          -e 's/^ *\(python3 \.claude\/.*\)/\1/p' -e 's/^ *\(bash \.claude\/.*\)/\1/p')"
chk "the run prints its by-hand and follow-up commands" "$(printf '%s\n' "$cmds" | grep -c .)" 5
unparsed=0
while IFS= read -r c; do
  bash -n -c "$c" 2>/dev/null || unparsed=$((unparsed+1))
done <<< "$cmds"
chk "  ... each parses" "$unparsed" 0
chk "  ... a slot's cd names it as one argument" \
    "$(args_of "$(printf '%s\n' "$cmds" | grep -m1 '^cd ' | sed 's/ && .*//')" | sed -n 2p)" "$CLONES/app-slot-1"
chk "  ... as do --log, --root and sweep --root" \
    "$(printf '%s\n' "$cmds" | grep -v '^cd ' | while IFS= read -r c; do args_of "$c" | grep -c -x -e "$CLONES" -e "$CLONES/gate-log.tsv"; done | tr '\n' ' ')" "1 1 1 "
chk "  ... and creates one clone per issue" \
    "$(git -C "$REPO" worktree list | tail -n +2 | wc -l | tr -d ' ')" 2

# Nothing is reaped — there is nothing to reap — and the previous run's log is
# still moved aside.
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
    "$(grep -c "gate_log=$CLONES/gate-log.tsv" "$CLONES"/app-slot-1/agent_states/.fanout-clone)" 1
chk "  ... and the issue it was created for" \
    "$(grep -c '^issue=101$' "$CLONES"/app-slot-1/agent_states/.fanout-clone)" 1

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
chk "  ... and keeps the pool: slot 1 reused, slot 2 left for a later run" \
    "$(git -C "$REPO" worktree list | tail -n +2 | wc -l | tr -d ' ')" 2

# --dry-run must still change nothing at all.
BEFORE="$(ls "$CLONES" | sort | cksum)"
bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" \
     --no-sync --dry-run 104 >/dev/null 2>&1
chk "--dry-run rotates nothing" "$(ls "$CLONES" | sort | cksum)" "$BEFORE"

# The telemetry archive rotates for the same reason the gate log does: clone
# names repeat every run, so unrotated, Finalize's copies pile up in a directory
# labelled as one clone's telemetry.
mkdir -p "$CLONES/telemetry/app-c1"
echo '{"ts":"old"}' > "$CLONES/telemetry/app-c1/orchestrator.jsonl"
sleep 1
out="$(bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" \
       --no-sync --no-launch --no-claim 105 2>&1)"
chk "a real run rotates the telemetry archive" \
    "$(ls -d "$CLONES"/telemetry-* 2>/dev/null | wc -l | tr -d ' ')" 1
chk "  ... and says so" "$(printf '%s' "$out" | grep -c 'archived telemetry/')" 1
chk "the launch output cites no internal plan or evidence notes" \
    "$(printf '%s' "$out" | grep -cE 'plan §|evidence-run')" 0
chk "  ... leaving the live directory clear for this run" \
    "$([ -e "$CLONES/telemetry/app-c1/orchestrator.jsonl" ] && echo yes || echo no)" no
chk "  ... with the previous run's events intact under the archive" \
    "$(cat "$CLONES"/telemetry-*/app-c1/orchestrator.jsonl 2>/dev/null)" '{"ts":"old"}'

# ---------------------------------------------------------- file overlap
#
# The launcher is the only place that knows every issue before any work starts.
# Two cycles editing one region of one file leave the second PR conflicted, and
# nothing owns a rebase after a cycle ends. This does not refuse — an overlap can
# merge clean — it makes the pair visible while it is still cheap to change.
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
    "$(printf '%s' "$out" | grep -c 'would use 3 of 3 slot')" 1

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
# The launcher inhibits system sleep for a run's duration, and only when it
# launches; without that guard every `tests/check.py` would leave a real 8-hour
# `caffeinate` orphaned on the developer's machine. A test suite must not change
# the power state of the host running it.
before_caf="$(pgrep -f 'caffeinate -dimsu' 2>/dev/null | wc -l | tr -d ' ')"
bash "$S" --repo "$REPO" --base develop --clones-root "$CLONES" --no-launch 1 >/dev/null 2>&1
after_caf="$(pgrep -f 'caffeinate -dimsu' 2>/dev/null | wc -l | tr -d ' ')"
chk "no sleep inhibitor is spawned without a launch" "$after_caf" "$before_caf"

# Asserted as a count rather than on the message, because a fixture that aborts
# at preflight never reaches the awake block at all — the message assertion would
# pass or fail for reasons unrelated to the guard. The count is what has teeth:
# an unguarded run leaks one inhibitor per `check.py`.

# --- --stop-awake ---------------------------------------------------------
#
# The --awake bound is a ceiling, not a lifetime: a run that finishes early
# leaves the inhibitor holding the machine awake, and nothing knows a run has
# ended — so this is the explicit way to say so.
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
# Reaping refuses on a clone with uncommitted work. "Uncommitted changes" alone
# sends the operator to their own repo, which is clean, because that is the tree
# they were just in — the clones root is not somewhere they are thinking about.
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
    source /dev/stdin <<<"$(sed -n "/^clone_op()/,/^}/p; /^dirty_clone_report()/,/^}/p" '"$S"')"
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

# --- no omp: a plain git worktree, rebuilt to the same working state ---------
#
# Claude Code alone, and every Windows machine, has no omp, and the launcher
# still runs there. A git worktree shares the repo's config, so origin survives
# (the property omp was chosen for); what it lacks is the untracked half, which
# the launcher must rebuild or every clone runs with no framework at all.
NR="$R/noomp"; mkdir -p "$NR"
git clone -q "$REPO" "$NR/app"; git -C "$NR/app" config user.email t@t
git -C "$NR/app" config user.name t
git -C "$NR/app" remote set-url origin https://github.com/acme/app.git
echo '{"permissions":{"allow":["Bash(make test*)"]}}' > "$NR/app/.claude/settings.local.json"
echo .claude/settings.local.json >> "$NR/app/.git/info/exclude"   # ignored, as Claude Code's is
bash "$ROOT_DIR/deploy.sh" link "$NR/app" >/dev/null 2>&1
# --cloner git selects the no-omp path while the stub omp stays on PATH, so the
# case runs the same git, bash and python3 as every other case on any host.
out="$(bash "$S" --repo "$NR/app" --base develop --cloner git \
        --clones-root "$NR/cycles" --no-sync --no-launch --no-claim 101 2>&1)"; rc=$?
C1="$NR/cycles/app-slot-1"
chk "without omp the launcher still creates clones" "$rc|$([ -d "$C1" ] && echo yes)" "0|yes"
chk "  ... saying it used git worktree add" "$(printf '%s' "$out" | grep -c 'via git worktree add')" 1
chk "  ... and what that does not reproduce" "$(printf '%s' "$out" | grep -c 'build caches start cold')" 1
chk "  ... keeping the real origin, so gh works inside" \
    "$(git -C "$C1" remote get-url origin 2>/dev/null)" https://github.com/acme/app.git
chk "  ... with the framework linked in" \
    "$([ -L "$C1/.claude/skills/cycle" ] && [ -L "$C1/.claude/hooks/gate-log.py" ] && echo yes)" yes
chk "  ... and the untracked per-project settings copied" \
    "$(cat "$C1/.claude/settings.local.json" 2>/dev/null)" '{"permissions":{"allow":["Bash(make test*)"]}}'
chk "  ... a deployment check passes inside the clone" \
    "$(bash "$ROOT_DIR/deploy.sh" check "$C1" >/dev/null 2>&1; echo $?)" 0
# A missing clone makes `git -C` fail with no output, which would count as clean.
st="$(git -C "$C1" status --porcelain -- ':!agent_states' 2>&1)"; rc=$?
chk "  ... and the clone is clean" "$([ -d "$C1" ] && echo yes)|$rc|$(printf '%s' "$st" | grep -c .)" "yes|0|0"

# --- a failed clone step names its cause -------------------------------------
#
# Each clone step runs quietly; when one fails, the refusal carries the tail of
# what that step printed, so the operator sees the cause without a second command.
REAL_GIT="$(command -v git)"
FAIL_BIN="$R/bin-fail"; mkdir -p "$FAIL_BIN"
cat > "$FAIL_BIN/git" <<STUB
#!/usr/bin/env bash
if [ "\${3:-} \${4:-}" = "worktree add" ]; then
  for k in \$(seq 1 30); do echo "noise line \$k"; done
  echo "fatal: stubbed worktree refusal" >&2; exit 128
fi
exec "$REAL_GIT" "\$@"
STUB
cat > "$FAIL_BIN/omp" <<'STUB'
#!/usr/bin/env bash
[ "${1:-} ${2:-}" = "worktree add" ] && { echo "omp: stubbed worktree refusal" >&2; exit 1; }
exit 0
STUB
chmod +x "$FAIL_BIN/git" "$FAIL_BIN/omp"
# A deployed project of its own per case: the launcher refuses while another
# worktree exists, and a failed clone may leave one behind.
fresh_app() {
  git clone -q "$REPO" "$1"; git -C "$1" config user.email t@t; git -C "$1" config user.name t
  bash "$ROOT_DIR/deploy.sh" link "$1" >/dev/null 2>&1
}

fresh_app "$R/gitfail/app"
out="$(PATH="$FAIL_BIN:$PATH" bash "$S" --repo "$R/gitfail/app" --base develop --cloner git \
        --clones-root "$R/gitfail/cycles" --no-sync --no-launch --no-claim 101 2>&1)"; rc=$?
chk "a failed git worktree add refuses with git's own message" \
    "$rc|$(printf '%s' "$out" | grep -c 'git worktree add failed')|$(printf '%s' "$out" | grep -c '^    fatal: stubbed worktree refusal$')" "1|1|1"
chk "  ... showing only the tail of a long output" \
    "$(printf '%s' "$out" | grep -c 'noise line 1$')|$(printf '%s' "$out" | grep -c 'noise line 30$')" "0|1"

fresh_app "$R/ompfail/app"
out="$(PATH="$FAIL_BIN:$PATH" bash "$S" --repo "$R/ompfail/app" --base develop --cloner omp \
        --clones-root "$R/ompfail/cycles" --no-sync --no-launch --no-claim 101 2>&1)"; rc=$?
chk "a failed omp worktree add refuses with omp's own message" \
    "$rc|$(printf '%s' "$out" | grep -c 'omp worktree add failed')|$(printf '%s' "$out" | grep -c '^    omp: stubbed worktree refusal$')" "1|1|1"

# A framework whose deploy.sh passes `check` and fails `link`: the launcher finds
# its framework from its own location, so a copy of it sits inside that framework.
FFW="$R/fw-linkfail"; mkdir -p "$FFW/.claude/skills/cycle"
cp "$S" "$FFW/.claude/skills/cycle/"
cat > "$FFW/deploy.sh" <<'STUB'
#!/usr/bin/env bash
[ "${1:-}" = link ] && { echo "cannot create symlink: Developer Mode is off" >&2; exit 1; }
exit 0
STUB
chmod +x "$FFW/deploy.sh"
fresh_app "$R/linkfail/app"
out="$(bash "$FFW/.claude/skills/cycle/start-parallel-cycles.sh" --repo "$R/linkfail/app" --base develop \
        --cloner git --clones-root "$R/linkfail/cycles" --no-sync --no-launch --no-claim 101 2>&1)"; rc=$?
chk "a failed deploy.sh link refuses with deploy.sh's own message" \
    "$rc|$(printf '%s' "$out" | grep -c 'deploy.sh link failed')|$(printf '%s' "$out" | grep -c '^    cannot create symlink: Developer Mode is off$')" "1|1|1"
line="$(printf '%s\n' "$out" | sed -n 's/.* — run: //p')"
bash -c "$line" >/dev/null 2>&1
chk "  ... naming a check command that runs as printed" "$?" 0

# Only the flag selects the cloner: a CLONER left in the operator's shell does not.
out="$(CLONER=git bash "$S" --repo "$NR/app" --base develop \
        --clones-root "$NR/cycles" --no-sync --dry-run 102 2>&1)"
chk "CLONER in the environment is ignored; omp on PATH is used" \
    "$(printf '%s' "$out" | grep -c 'via omp worktree add')" 1

# Any other value refuses with the usage line.
out="$(bash "$S" --repo "$NR/app" --cloner svn --dry-run 102 2>&1)"; rc=$?
chk "--cloner svn refuses with usage" \
    "$rc|$(printf '%s' "$out" | grep -c "cloner must be git or omp (got 'svn')")|$(printf '%s' "$out" | grep -c 'Usage:')" "1|1|1"

# Asking for omp where none is installed names omp, not a later symptom. The
# PATH here holds only a git stub: nothing runs it before the refusal.
NO_OMP="$R/bin-git-only"; mkdir -p "$NO_OMP"
printf '#!/bin/sh\nexit 0\n' > "$NO_OMP/git"; chmod +x "$NO_OMP/git"
out="$(PATH="$NO_OMP" "$(command -v bash)" "$S" --repo "$NR/app" --cloner omp --dry-run 102 2>&1)"; rc=$?
chk "--cloner omp without omp installed refuses, naming omp" \
    "$rc|$(printf '%s' "$out" | grep -c 'cloner omp, but omp is not installed')" "1|1"

# --- the worktree pool --------------------------------------------------------
#
# Slots are reset in place between runs, not recreated, so their ignored build
# output stays warm. Every safety check that guards removal guards a reset too:
# the reset must never discard uncommitted work.
P="$R/pool/app"; PC="$R/pool/cycles"
fresh_app "$P"
printf 'build/\n' >> "$P/.gitignore"
sed -i.bak 's/^| parallel_slots | `3` |/| parallel_slots | `2` |/' "$P/.omp/agent-config.md"
rm -f "$P/.omp/agent-config.md.bak"
git -C "$P" commit -qam "pool fixture: two slots, build/ ignored"
mkdir -p "$PC"; PCP="$(cd "$PC" && pwd -P)"
S1="$PC/app-slot-1"; S2="$PC/app-slot-2"
launch() { bash "$S" --repo "$P" --base develop --clones-root "$PC" --cloner git \
             --no-sync --no-launch --no-claim "$@" 2>&1; }
inode() { ls -di "$1" 2>/dev/null | awk '{print $1}'; }
wtlist() { git -C "$P" worktree list --porcelain | cksum; }
heads() { for s in "$S1" "$S2"; do git -C "$s" rev-parse HEAD 2>/dev/null; done | cksum; }

out="$(launch 301 302)"; rc=$?
chk "first launch creates one slot per issue" \
    "$rc|$([ -d "$S1" ] && [ -d "$S2" ] && echo yes)" "0|yes"
chk "  ... printing which issue runs in which slot" \
    "$(printf '%s' "$out" | grep -c '#301 → app-slot-1  created')|$(printf '%s' "$out" | grep -c '#302 → app-slot-2  created')" "1|1"
chk "  ... recording it in the run provenance" \
    "$(grep -c "^# slot app-slot-1 issue 301 created $S1$" "$PC/run-provenance.txt")" 1
chk "  ... and in the slot's own marker" \
    "$(grep -c '^clone=app-slot-1$' "$S1/agent_states/.fanout-clone")|$(grep -c '^slot=1$' "$S1/agent_states/.fanout-clone")" "1|1"
chk "  ... and prints the pool's disk footprint" \
    "$(printf '%s' "$out" | grep -c 'pool disk footprint [0-9]* MB across 2 of 2 slot(s)')" 1

# A cycle ran in slot 1: build output, a feature branch with a commit on it, and
# state left in agent_states.
INODE1="$(inode "$S1")"
mkdir -p "$S1/build"; echo warm > "$S1/build/cache.bin"
git -C "$S1" checkout -q -b feat/301-thing
echo feature > "$S1/feature.txt"; git -C "$S1" add feature.txt; git -C "$S1" commit -qm feature
FEAT_SHA="$(git -C "$S1" rev-parse HEAD)"
echo stale > "$S1/agent_states/cycle-state-old.md"
mkdir -p "$PC/.reapable"; echo '{}' > "$PC/.reapable/app-slot-1.json"

out="$(launch 303 304)"; rc=$?
chk "a second launch reuses the slots" "$rc|$(inode "$S1")" "0|$INODE1"
chk "  ... and says so" "$(printf '%s' "$out" | grep -c '#303 → app-slot-1  reused')" 1
chk "  ... ignored build output survives the reset" "$(cat "$S1/build/cache.bin" 2>/dev/null)" warm
chk "  ... the slot is detached at the base" \
    "$(git -C "$S1" rev-parse HEAD)|$(git -C "$S1" symbolic-ref -q HEAD || echo detached)" \
    "$(git -C "$P" rev-parse develop)|detached"
chk "  ... the previous feature branch survives, commit intact" \
    "$(git -C "$P" rev-parse --verify -q feat/301-thing)" "$FEAT_SHA"
chk "  ... agent_states is cleared and the marker names the new issue" \
    "$([ -e "$S1/agent_states/cycle-state-old.md" ] && echo stale || echo cleared)|$(grep -c '^issue=303$' "$S1/agent_states/.fanout-clone")" "cleared|1"
chk "  ... the stale reapable marker is dropped" \
    "$([ -e "$PC/.reapable/app-slot-1.json" ] && echo yes || echo no)" no
chk "  ... and the slot is clean" "$(git -C "$S1" status --porcelain -- ':!agent_states' | wc -l | tr -d ' ')" 0

# Tracked edits in a slot are uncommitted work: the run stops and keeps them.
echo "edited by hand" >> "$S1/README.md"
B_WT="$(wtlist)"; B_HEADS="$(heads)"; B_LS="$(ls "$PC" | cksum)"
out="$(launch 305)"; rc=$?
chk "a tracked change in a slot stops the run" \
    "$rc|$(printf '%s' "$out" | grep -c 'app-slot-1 has 1 uncommitted change(s). Nothing was removed or reset.')" "1|1"
chk "  ... and the change is not lost" "$(tail -n 1 "$S1/README.md")" "edited by hand"
chk "  ... with no slot, worktree or run artifact changed" \
    "$(wtlist)|$(heads)|$(ls "$PC" | cksum)" "$B_WT|$B_HEADS|$B_LS"
out="$(launch --fresh 305)"; rc=$?
chk "  ... and --fresh stops on it too" "$rc|$(tail -n 1 "$S1/README.md")" "1|edited by hand"
git -C "$S1" checkout -q -- README.md

# Untracked files that git does not ignore are uncommitted work as well.
echo notes > "$S2/notes.txt"
out="$(launch 305 306)"; rc=$?
chk "an untracked, unignored file in a slot stops the run" \
    "$rc|$(printf '%s' "$out" | grep -c 'app-slot-2 has 1 uncommitted change')" "1|1"
chk "  ... and the file is kept" "$(cat "$S2/notes.txt" 2>/dev/null)" notes
chk "  ... and slot 1, checked first, was not reset either" "$(git -C "$S1" status --porcelain -- ':!agent_states' | wc -l | tr -d ' ')|$(cat "$S1/build/cache.bin")" "0|warm"
# A slot this run does not use is not this run's to check.
out="$(launch 305)"; rc=$?
chk "  ... while a run that uses only slot 1 proceeds" "$rc|$(cat "$S2/notes.txt" 2>/dev/null)" "0|notes"
mv "$S2/notes.txt" "$R/pool/notes.txt"

# Commits that only a detached HEAD reaches would be orphaned by the reset.
git -C "$S1" checkout -q --detach
echo orphan > "$S1/orphan.txt"; git -C "$S1" add orphan.txt; git -C "$S1" commit -qm orphan
ORPHAN="$(git -C "$S1" rev-parse HEAD)"
out="$(launch 307)"; rc=$?
chk "commits only a detached HEAD holds stop the run" \
    "$rc|$(printf '%s' "$out" | grep -c 'detached HEAD whose commits no branch holds')|$(git -C "$S1" rev-parse HEAD)" "1|1|$ORPHAN"
git -C "$S1" branch keep/orphan

# A session still running inside a slot.
bash -c 'sleep 30; true' "$PCP/app-slot-1" & HOLDER=$!
sleep 0.3
out="$(launch 308)"; rc=$?
kill "$HOLDER" 2>/dev/null; wait "$HOLDER" 2>/dev/null
chk "a live process holding a slot stops the run" \
    "$rc|$(printf '%s' "$out" | grep -c 'app-slot-1 still has processes attached')|$(git -C "$S1" rev-parse HEAD)" "1|1|$ORPHAN"

# Dry run describes reuse vs create per slot and changes nothing.
git -C "$P" worktree remove --force "$S2"
B_WT="$(wtlist)"; B_LS="$(ls -la "$PC" | cksum)"; B_H1="$(git -C "$S1" rev-parse HEAD)"
out="$(bash "$S" --repo "$P" --base develop --clones-root "$PC" --cloner git --no-sync --dry-run 309 310 2>&1)"; rc=$?
chk "--dry-run says which slot is reused and which created" \
    "$rc|$(printf '%s' "$out" | grep -c '#309 → app-slot-1  reuse — reset to develop')|$(printf '%s' "$out" | grep -c '#310 → app-slot-2  create')" "0|1|1"
chk "  ... states the footprint" "$(printf '%s' "$out" | grep -c 'pool disk footprint now [0-9]* MB across 1 of 2')" 1
chk "  ... and changes nothing" "$(wtlist)|$(ls -la "$PC" | cksum)|$(git -C "$S1" rev-parse HEAD)" "$B_WT|$B_LS|$B_H1"

out="$(launch 309 310)"; rc=$?
chk "a missing slot is created beside a reused one" \
    "$rc|$(printf '%s' "$out" | grep -c '#309 → app-slot-1  reused')|$(printf '%s' "$out" | grep -c '#310 → app-slot-2  created')|$(cat "$S1/build/cache.bin")" "0|1|1|warm"

out="$(launch 311 312 313)"; rc=$?
chk "more issues than slots stops, naming the setting" \
    "$rc|$(printf '%s' "$out" | grep -c '3 issues, but the pool has 2 slot(s). Nothing was changed.')|$(printf '%s' "$out" | grep -c 'parallel_slots')" "1|1|1"

# --fresh recreates every slot from scratch, build output and all.
out="$(launch --fresh 314 315)"; rc=$?
chk "--fresh recreates the slots" \
    "$rc|$(printf '%s' "$out" | grep -c 'app-slot-1  created')|$([ -e "$S1/build/cache.bin" ] && echo warm || echo cold)" "0|1|cold"
chk "  ... keeping every branch" \
    "$(git -C "$P" rev-parse -q --verify feat/301-thing)|$(git -C "$P" rev-parse -q --verify keep/orphan)" "$FEAT_SHA|$ORPHAN"

# Per-issue clones from before the pool, and slots beyond a lowered
# parallel_slots, are reaped under the same checks.
git -C "$P" worktree add -q --detach "$PC/app-c1" develop
git -C "$P" worktree add -q --detach "$PC/app-slot-3" develop
echo wip > "$PC/app-c1/wip.txt"
out="$(launch 316)"; rc=$?
chk "a dirty legacy clone stops the run, nothing removed" \
    "$rc|$(printf '%s' "$out" | grep -c 'app-c1 has 1 uncommitted change')|$(cat "$PC/app-c1/wip.txt")|$([ -d "$PC/app-slot-3" ] && echo yes)" "1|1|wip|yes"
mv "$PC/app-c1/wip.txt" "$R/pool/wip.txt"
out="$(launch --no-reap 316)"; rc=$?
chk "--no-reap leaves them and refuses over them" \
    "$rc|$([ -d "$PC/app-c1" ] && echo yes)|$(printf '%s' "$out" | grep -c 'existing worktree(s) outside the pool')" "1|yes|1"
out="$(launch 316)"; rc=$?
chk "clean legacy clones and surplus slots are reaped" \
    "$rc|$([ -e "$PC/app-c1" ] && echo kept || echo gone)|$([ -e "$PC/app-slot-3" ] && echo kept || echo gone)|$(printf '%s' "$out" | grep -c 'reaped 2 clone(s) outside the pool')" "0|gone|gone|1"
chk "  ... leaving the pool in place" "$([ -d "$S1" ] && [ -d "$S2" ] && echo yes)" yes

# A directory at a slot's path that is not one of this repo's worktrees.
git -C "$P" worktree remove --force "$S2"; mkdir -p "$S2"; echo x > "$S2/stray"
out="$(launch 317 318)"; rc=$?
chk "a non-worktree directory at a slot path stops the run, untouched" \
    "$rc|$(printf '%s' "$out" | grep -c 'exists but is not a worktree')|$(cat "$S2/stray")" "1|1|x"
mv "$S2" "$R/pool/stray-slot"

# The omp cloner reuses a slot the same way.
out="$(bash "$S" --repo "$P" --base develop --clones-root "$PC" --cloner omp \
        --no-sync --no-launch --no-claim 319 320 2>&1)"; rc=$?
chk "the omp cloner creates a missing slot and reuses an existing one" \
    "$rc|$(printf '%s' "$out" | grep -c '#319 → app-slot-1  reused')|$(printf '%s' "$out" | grep -c '#320 → app-slot-2  created')" "0|1|1"
chk "  ... a reused slot gets the framework linked" "$([ -L "$S1/.claude/skills/cycle" ] && echo yes)" yes

# --- partial checkout (sparse_clones) ----------------------------------------
#
# Off by default: a project that has not opted in gets the full checkout it
# always did, and its git config is not touched. Opted in, a slot holds its
# story's slice areas plus always_checkout; a story without slices, and every
# slot once the option is off again, gets a full checkout.
SP="$R/partial/app"; SPC="$R/partial/cycles"
fresh_app "$SP"
mkdir -p "$SP/lib/domain/health" "$SP/lib/ui/health" "$SP/lib/other" "$SP/ci"
echo m > "$SP/lib/domain/health/model.txt"; echo v > "$SP/lib/ui/health/view.txt"
echo z > "$SP/lib/other/z.txt"; echo c > "$SP/ci/build.yml"
printf 'build/\n' >> "$SP/.gitignore"
git -C "$SP" add -A; git -C "$SP" commit -qm "sparse fixture"
SS1="$SPC/app-slot-1"; SS2="$SPC/app-slot-2"
slaunch() { bash "$S" --repo "$SP" --base develop --clones-root "$SPC" --no-sync --no-launch --no-claim "$@" 2>&1; }
# Tracked files a checkout lacks on disk: 0 is a full checkout.
missing() { (cd "$1" && git ls-files | while IFS= read -r f; do [ -e "$f" ] || echo "$f"; done) | wc -l | tr -d ' '; }
is_sparse() { [ "$(git -C "$1" config --get core.sparseCheckout)" = true ] && echo sparse || echo full; }
set_row() {  # name value: rewrite one Cycle Options value and commit it
  sed -i.bak 's/^| '"$1"' | `[^`]*` |/| '"$1"' | `'"$2"'` |/' "$SP/.omp/agent-config.md"
  rm -f "$SP/.omp/agent-config.md.bak"; git -C "$SP" commit -qam "$1=$2"
}
SP_CFG="$(cksum < "$SP/.git/config")"

chk "the framework config ships sparse_clones off" \
    "$(grep -c '^| sparse_clones | `false` |' "$ROOT_DIR/.omp/agent-config.md")" 1

out="$(slaunch 401 402)"; rc=$?
chk "off (the default row): a sliced story's slot is a full checkout" \
    "$rc|$(missing "$SS1")|$(is_sparse "$SS1")|$(missing "$SS2")" "0|0|full|0"
chk "  ... the launch never mentions partial checkout" "$(printf '%s' "$out" | grep -ci sparse)" 0
chk "  ... new slots come from the cloner as before" "$(printf '%s' "$out" | grep -c 'via omp worktree add')" 1
chk "  ... and the repository's git config is untouched" "$(cksum < "$SP/.git/config")" "$SP_CFG"
sed -i.bak '/^| sparse_clones |/d' "$SP/.omp/agent-config.md"; rm -f "$SP/.omp/agent-config.md.bak"
git -C "$SP" commit -qam "no sparse_clones row"
out="$(slaunch 401 402)"; rc=$?
chk "off (a config without the row): reused slots stay full" \
    "$rc|$(missing "$SS1")|$(is_sparse "$SS1")|$(printf '%s' "$out" | grep -ci sparse)" "0|0|full|0"
chk "  ... and the git config is still untouched" "$(cksum < "$SP/.git/config")" "$SP_CFG"
git -C "$SP" revert --no-edit HEAD >/dev/null

set_row sparse_clones true; set_row always_checkout 'ci\/'
out="$(slaunch --fresh 401 402)"; rc=$?
chk "on: new slots are made with git worktree add, saying why omp is not used" \
    "$rc|$(printf '%s' "$out" | grep -c 'Preparing slots (via git worktree add')|$(printf '%s' "$out" | grep -c 'omp worktree add copies the whole working tree')" "0|1|1"
L1="$(git -C "$SS1" sparse-checkout list 2>/dev/null | tr '\n' ' ')"
chk "  ... a sliced story's slot holds its slice areas and always_checkout" \
    "$(is_sparse "$SS1")|$(printf '%s' "$L1" | grep -c 'lib/domain/health lib/ui/health')|$(printf '%s' "$L1" | grep -c '^\.claude \.omp .* ci ')" "sparse|1|1"
chk "  ... with their files on disk, and root files" \
    "$(cat "$SS1/lib/ui/health/view.txt")|$(cat "$SS1/ci/build.yml")|$(cat "$SS1/README.md")" "v|c|app"
chk "  ... and nothing outside the set" "$([ -e "$SS1/lib/other/z.txt" ] && echo present || echo absent)" absent
chk "  ... the launch names the set" "$(printf '%s' "$out" | grep -c '#401 → app-slot-1  sparse: .*lib/domain/health')" 1
chk "  ... the slot is clean and its deployment checks out" \
    "$(git -C "$SS1" status --porcelain -- ':!agent_states' | wc -l | tr -d ' ')|$(bash "$ROOT_DIR/deploy.sh" check "$SS1" >/dev/null 2>&1; echo $?)" "0|0"
chk "  ... and the run provenance records it" "$(grep -c '^# sparse app-slot-1 .*lib/ui/health' "$SPC/run-provenance.txt")" 1
chk "a story without slices gets a full checkout, and the launch says so" \
    "$(is_sparse "$SS2")|$(missing "$SS2")|$(printf '%s' "$out" | grep -c '#402 → app-slot-2  full checkout: the story has no `## Slices`')" "full|0|1"
chk "the primary checkout stays full" "$(is_sparse "$SP")|$(missing "$SP")" "full|0"

# A reused slot has its set replaced at reset; ignored build output stays.
mkdir -p "$SS1/build"; echo warm > "$SS1/build/cache.bin"
out="$(slaunch 403)"; rc=$?
L1="$(git -C "$SS1" sparse-checkout list 2>/dev/null | tr '\n' ' ')"
chk "reset replaces a reused slot's set" \
    "$rc|$(printf '%s' "$L1" | grep -c 'lib/other')|$(printf '%s' "$L1" | grep -c 'health')" "0|1|0"
chk "  ... the new area is on disk and the old one is gone" \
    "$(cat "$SS1/lib/other/z.txt")|$([ -e "$SS1/lib/domain/health/model.txt" ] && echo present || echo absent)" "z|absent"
chk "  ... build output survives" "$(cat "$SS1/build/cache.bin")" warm
chk "  ... and the slot is clean" "$(git -C "$SS1" status --porcelain -- ':!agent_states' | wc -l | tr -d ' ')" 0

out="$(slaunch 402)"; rc=$?
chk "a sparse slot given a story without slices returns to full" \
    "$rc|$(is_sparse "$SS1")|$(missing "$SS1")|$(printf '%s' "$out" | grep -c '#402 → app-slot-1  full checkout')" "0|full|0|1"

# Dry run states each slot's set and changes nothing.
slaunch 401 >/dev/null
B_WT="$(git -C "$SP" worktree list --porcelain | cksum)"; B_L1="$(git -C "$SS1" sparse-checkout list | cksum)"
out="$(bash "$S" --repo "$SP" --base develop --clones-root "$SPC" --no-sync --dry-run 403 402 2>&1)"; rc=$?
chk "--dry-run states each slot's checkout" \
    "$rc|$(printf '%s' "$out" | grep -c '#403 → app-slot-1  sparse: .*lib/other')|$(printf '%s' "$out" | grep -c '#402 → app-slot-2  full checkout')" "0|1|1"
chk "  ... and changes nothing" \
    "$(git -C "$SP" worktree list --porcelain | cksum)|$(git -C "$SS1" sparse-checkout list | cksum)" "$B_WT|$B_L1"

# omp worktree add copies the whole tree, so asking for it outright refuses.
out="$(slaunch --cloner omp 403)"; rc=$?
chk "on with --cloner omp refuses, naming both ways out" \
    "$rc|$(printf '%s' "$out" | grep -c 'sparse_clones is true')|$(printf '%s' "$out" | grep -c 'pass --cloner git')" "1|1|1"
chk "  ... with nothing changed" \
    "$(git -C "$SP" worktree list --porcelain | cksum)|$(git -C "$SS1" sparse-checkout list | cksum)" "$B_WT|$B_L1"

# Turned off again: a slot that was sparse is returned to a full checkout.
set_row sparse_clones false
out="$(slaunch 401)"; rc=$?
chk "on → off returns a sparse slot to a full checkout" \
    "$rc|$(is_sparse "$SS1")|$(missing "$SS1")|$(cat "$SS1/lib/other/z.txt")" "0|full|0|z"
chk "  ... and says so" "$(printf '%s' "$out" | grep -c 'app-slot-1 returned to a full checkout')" 1
out="$(slaunch 401)"
chk "  ... after which a launch is silent about it again" "$(printf '%s' "$out" | grep -ci sparse)" 0

# --help prints the whole header comment, through the last flag line, without
# its comment markers, and no code: the same form as deploy.sh --help.
out="$(bash "$S" --help 2>&1)"; rc=$?
chk "--help prints the header through its last flag line" \
    "$rc|$(printf '%s' "$out" | grep -c -- '^Flags: --repo DIR')|$(printf '%s' "$out" | grep -c -- '--no-reap --no-sync --dry-run --no-launch --no-claim')|$(printf '%s' "$out" | grep -c 'set -uo pipefail')" "0|1|1|0"
chk "  ... with no comment markers" "$(printf '%s\n' "$out" | grep -c '^#')" 0
chk "  ... ending on the header's last comment line" \
    "$(printf '%s\n' "$out" | tail -n 1)" "$(grep -B1 -m1 '^set -uo pipefail' "$S" | head -n 1 | sed 's/^# \{0,1\}//')"

printf '\nstart-parallel-cycles: %s\n' \
  "$([ $FAILED = 0 ] && echo 'all checks passed.' || echo 'FAILURES above.')"
exit $FAILED
