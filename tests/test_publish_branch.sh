#!/usr/bin/env bash
# Tests for .claude/skills/cycle/publish-branch.sh.
#
# The script exists to be *granted*, so what matters is that no argument reaches
# a wider operation than the grant implies. Every test below is a refusal: the
# push path is pinned to origin/HEAD with no force and no refspec, so the only
# things left to get wrong are which branch it will push and what can be
# smuggled through the one free argument.
set -uo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.claude/skills/cycle/publish-branch.sh"
FAILED=0
ok() { printf 'ok    %s\n' "$1"; }
bad() { printf 'FAIL  %s\n     %s\n' "$1" "${2:-}"; FAILED=1; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want [$3] got [$2]"; fi; }
# Run the script and report "<exit> <matched?>" so one line asserts both.
try() { out="$(bash "$S" "$@" 2>&1)"; printf '%s' "$?"; }
says() { out="$(bash "$S" "$@" 2>&1)"; printf '%s' "$out"; }

R="$(mktemp -d)"; cd "$R"
git init -q .; git config user.email t@t; git config user.name t
echo x > a; git add a; git commit -qm init

# Outside a repository there is nothing to push; this must not fall through to
# some ambient repo further up the tree.
OUT="$(cd / && bash "$S" push 2>&1)"
chk "outside a repo refuses" "$(echo "$OUT" | grep -c 'not inside a git repository')" 1

# Integration branches. This is the hazard `Bash(git push*)` cannot see: the
# grant reads the same whether HEAD is a cycle branch or develop.
for b in main master develop staging release/1.2 hotfix/x; do
  git checkout -q -B "$b"
  chk "refuses to push integration branch '$b'" "$(try push)" 1
done

git checkout -q -B 443/defer-programs-body
chk "a cycle branch is not refused as integration" \
    "$(says --dry-run push | grep -c 'refusing to push integration')" 0

# No origin: better to refuse than to let git pick a remote by inference.
chk "no origin remote refuses" "$(try --dry-run push)" 1
git remote add origin https://example.invalid/r.git

chk "dry-run push is allowed" "$(try --dry-run push)" 0
chk "  ... and names the exact command" \
    "$(says --dry-run push | grep -c 'git push -u origin HEAD')" 1
chk "  ... with no force in it" "$(says --dry-run push | grep -ci 'force')" 0

# A detached HEAD pushes under a name nobody chose.
git checkout -q --detach
chk "detached HEAD refuses" "$(try push)" 1
git checkout -q 443/defer-programs-body

# Argument discipline: the command words take no free arguments at all, so no
# extra token can ride along into git.
chk "push takes no arguments" "$(try push origin)" 1
chk "unknown command refuses" "$(try frobnicate)" 1
chk "unknown option refuses" "$(try --force push)" 1
chk "ci needs a workflow name" "$(try --dry-run ci)" 1
chk "ci takes exactly one argument" "$(try --dry-run ci ci.yml extra)" 1

# The workflow name is the only free argument. It reaches `gh`, not a shell, but
# it is charset-checked anyway so it cannot become a path or a second command.
for w in 'a;rm -rf /' '../ci.yml' '.hidden' 'a b' 'x$(id)' 'a&&b' '/etc/passwd'; do
  chk "rejects workflow name '$w'" "$(try --dry-run ci "$w")" 1
done
chk "accepts a plain workflow file name" "$(try --dry-run ci ci.yml)" 0

# --ref, not -f ref=. Fan-out 4 dispatched with -f three times and every run was
# attributed to the base branch, so the sha lookup found nothing.
chk "dispatches with --ref" "$(says --dry-run ci ci.yml | grep -c -- '--ref 443/defer-programs-body')" 1
chk "  ... and not with -f ref=" "$(says --dry-run ci ci.yml | grep -c -- '-f ref=')" 0

# --dry-run must reach no network and mutate nothing.
chk "dry-run pushes nothing" "$(git -C "$R" log --oneline origin/443/defer-programs-body 2>/dev/null | wc -l | tr -d ' ')" 0

printf '\npublish-branch: %s\n' "$([ $FAILED = 0 ] && echo 'all checks passed.' || echo 'FAILURES above.')"
exit $FAILED
