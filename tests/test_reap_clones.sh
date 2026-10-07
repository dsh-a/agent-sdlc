#!/usr/bin/env bash
# Tests for .claude/skills/cycle/reap-clones.sh.
#
# The script deletes directories and removes worktrees, so every test here is
# about a boundary: what it refuses to touch (anything outside a fan-out clone,
# anything git does not call ignored), and what it refuses to remove (a clone
# whose HEAD moved, is dirty, or still has a process in it).
set -uo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.claude/skills/cycle/reap-clones.sh"
FAILED=0
ok() { printf 'ok    %s\n' "$1"; }
bad() { printf 'FAIL  %s\n     %s\n' "$1" "${2:-}"; FAILED=1; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want [$3] got [$2]"; fi; }

# A fan-out clone is a linked worktree of an origin repo, with the launcher's
# marker in it. Rebuild that shape rather than mocking it.
setup() {
  R="$(mktemp -d)"; ORIGIN="$R/origin"; ROOT="$R/cycles"
  mkdir -p "$ORIGIN" "$ROOT"
  git init -q "$ORIGIN"; cd "$ORIGIN"
  git config user.email t@t; git config user.name t
  printf 'build/\n.dart_tool/\nagent_states/\n' > .gitignore
  mkdir -p bin; echo 'tracked source' > bin/tool.sh      # committed, NOT ignored
  git add .gitignore bin; git commit -qm init
  git worktree add -q -b 443/x "$ROOT/c1" >/dev/null 2>&1
  WT="$ROOT/c1"
  mkdir -p "$WT/agent_states" "$WT/build/x" "$WT/.dart_tool" "$WT/node_modules"
  touch "$WT/agent_states/.fanout-clone"
  dd if=/dev/zero of="$WT/build/x/blob" bs=1024 count=600 2>/dev/null
}
setup

# finish refuses outside a fan-out clone — the origin's build output belongs to
# whoever is working in it.
mkdir -p "$ORIGIN/build"; (cd "$ORIGIN" && bash "$S" finish --apply >/dev/null 2>&1)
chk "finish refuses in a non-clone checkout" "$?" 1
chk "  ... and left its build/ alone" "$([ -d "$ORIGIN/build" ] && echo yes)" yes

cd "$WT"
out="$(bash "$S" finish 2>&1)"
chk "finish dry-run deletes nothing" "$([ -d "$WT/build" ] && echo yes)" yes
chk "  ... but says what it would delete" "$(echo "$out" | grep -c 'would delete build')" 1
chk "  ... and writes no marker" "$([ -e "$ROOT/.reapable/c1.json" ] && echo yes || echo no)" no

out="$(bash "$S" finish --apply 2>&1)"
chk "finish deletes gitignored build output" "$([ -d "$WT/build" ] && echo yes || echo no)" no
chk "  ... and .dart_tool" "$([ -d "$WT/.dart_tool" ] && echo yes || echo no)" no
# node_modules is a candidate by name but this repo does not ignore it.
chk "  ... keeps a candidate git does not ignore" "$([ -d "$WT/node_modules" ] && echo yes || echo no)" yes
chk "  ... and says why" "$(echo "$out" | grep -c 'kept node_modules (not gitignored)')" 1
chk "  ... never touches tracked bin/" "$([ -f "$WT/bin/tool.sh" ] && echo yes || echo no)" yes
chk "  ... leaves agent_states alone" "$([ -f "$WT/agent_states/.fanout-clone" ] && echo yes || echo no)" yes
chk "  ... and writes the marker at the clones root" "$([ -f "$ROOT/.reapable/c1.json" ] && echo yes || echo no)" yes
chk "  ... recording the head sha" \
    "$(grep -c "\"head\":\"$(git -C "$WT" rev-parse HEAD)\"" "$ROOT/.reapable/c1.json")" 1

# A symlinked candidate must never be followed out of the tree.
setup; cd "$WT"
mkdir -p "$R/outside"; touch "$R/outside/precious"; rm -rf "$WT/.dart_tool"
ln -s "$R/outside" "$WT/.dart_tool"
bash "$S" finish --apply >/dev/null 2>&1
chk "a symlinked candidate is skipped, not followed" "$([ -f "$R/outside/precious" ] && echo yes || echo no)" yes

# sweep
setup; cd "$WT"; bash "$S" finish --apply >/dev/null 2>&1
out="$(bash "$S" sweep --root "$ROOT" 2>&1)"
chk "sweep dry-run removes nothing" "$([ -d "$WT" ] && echo yes)" yes
chk "  ... but names the clone" "$(echo "$out" | grep -c 'would remove')" 1

# A commit on top of the finished one is the normal case, not a divergence: the
# cycle writes its changelog fragment at step 10, after Finalize has written the
# marker at step 7. Refusing it meant sweeping nothing (evidence-run5 J3).
echo more > "$WT/f"; git -C "$WT" add f; git -C "$WT" commit -qm "changelog fragment"
out="$(bash "$S" sweep --root "$ROOT" --apply 2>&1)"
chk "sweep accepts a commit made after Finalize" "$([ -d "$WT" ] && echo yes || echo no)" no
chk "  ... and the branch still survives" \
    "$(git -C "$ORIGIN" branch --list 443/x | wc -l | tr -d ' ')" 1

# Rewritten history is still refused — the marked commit is no longer reachable,
# so this is not the tree that was declared finished.
setup; cd "$WT"; bash "$S" finish --apply >/dev/null 2>&1
git -C "$WT" commit -q --amend -m "rewritten after Finalize"
out="$(bash "$S" sweep --root "$ROOT" --apply 2>&1)"
chk "sweep refuses a HEAD that does not descend from the finished commit" \
    "$([ -d "$WT" ] && echo yes || echo no)" yes
chk "  ... and says why" "$(echo "$out" | grep -c 'not a descendant')" 1

# Uncommitted work is the operator's to resolve, not the sweeper's.
setup; cd "$WT"; bash "$S" finish --apply >/dev/null 2>&1
echo dirty > "$WT/untracked"
out="$(bash "$S" sweep --root "$ROOT" --apply 2>&1)"
chk "sweep skips a dirty clone" "$([ -d "$WT" ] && echo yes)" yes
chk "  ... and says so" "$(echo "$out" | grep -c 'uncommitted changes')" 1
# agent_states churn must not count as dirty — the marker itself lives there.
rm "$WT/untracked"; touch "$WT/agent_states/scratch"
bash "$S" sweep --root "$ROOT" --apply >/dev/null 2>&1
chk "agent_states churn does not block a sweep" "$([ -d "$WT" ] && echo yes || echo no)" no

# The branch is the thing that carries the work; removal must not touch it.
chk "the feature branch survives removal" "$(git -C "$ORIGIN" branch --list 443/x | wc -l | tr -d ' ')" 1
chk "  ... and the marker is cleared" "$([ -e "$ROOT/.reapable/c1.json" ] && echo yes || echo no)" no

# An unmarked clone is invisible to sweep — that is the launcher reap's job.
setup
out="$(bash "$S" sweep --root "$ROOT" --apply 2>&1)"
chk "sweep ignores an unmarked clone" "$([ -d "$WT" ] && echo yes)" yes
chk "  ... reporting nothing marked" "$(echo "$out" | grep -c 'nothing has been marked')" 1

chk "sweep needs a root outside a clone" \
    "$(cd "$ORIGIN" && bash "$S" sweep >/dev/null 2>&1; echo $?)" 1
chk "unknown command refuses" "$(bash "$S" frobnicate >/dev/null 2>&1; echo $?)" 1

printf '\nreap-clones: %s\n' "$([ $FAILED = 0 ] && echo 'all checks passed.' || echo 'FAILURES above.')"
exit $FAILED
