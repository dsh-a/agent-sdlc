#!/usr/bin/env bash
# scrub-gate — block private/company data from reaching the public repo.
# Usage: scrub-gate.sh [<tree-ish>] [<commit-range>]
#   scans the file content at <tree-ish> (default HEAD) and the commit messages
#   in <commit-range> (optional) for forbidden patterns.
# Wired as a pre-push hook via .githooks/pre-push. Enable: git config core.hooksPath .githooks
set -uo pipefail

REF="${1:-HEAD}"
RANGE="${2:-}"

# Anything here must never land in the public repo. Extend as needed.
#
# Three groups, kept separate because they fail for different reasons and a
# future maintainer needs to know which:
#
#   IDENTITY   company and personal identifiers.
#   SECRETS    credential shapes. `OPENROUTER_API_KEY` and friends are env-var
#              NAMES and deliberately absent — naming the variable is how the
#              docs tell you to supply a key without ever carrying one.
#   PRIVATE    content that is framework-shaped but not framework: the operator's
#              own application name, which appeared only as an example vault repo
#              and leaks which product this was built against, and personal
#              career tooling that rode along in the public core for months
#              because nothing checked. Both were removed; this is the guard that
#              keeps them out, since "we remember not to" is not a control.
IDENTITY='bloomerang|dalton\.shultz@|dmoney'
SECRETS='sk-or-v1-|sk-[A-Za-z0-9]{24}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_|AKIA[0-9A-Z]{16}|xox[baprs]-|-----BEGIN [A-Z ]*PRIVATE KEY'
PRIVATE='ocelot|career-braindump|resume-tailor|job-scout'
PATTERNS="$IDENTITY|$SECRETS|$PRIVATE"

# Paths that must not exist in the public tree at all. The content patterns above
# already catch these skills by the `name:` in their own frontmatter, but a path
# check does not depend on a file describing itself — a re-add with the body
# rewritten, or a directory carrying only assets, still fails here.
FORBIDDEN_PATHS='^\.claude/skills/(career-braindump|resume-tailor|job-scout)/'

fail=0

# 0) forbidden paths in the tree being pushed
if git ls-tree -r --name-only "$REF" 2>/dev/null | grep -qE "$FORBIDDEN_PATHS"; then
  echo "✖ scrub-gate: forbidden paths at $REF:"
  git ls-tree -r --name-only "$REF" 2>/dev/null | grep -E "$FORBIDDEN_PATHS" | sed 's/^/    /' | head -20
  echo "    These are private-only. They belong in agent-sdlc-private, not the public core."
  fail=1
fi

# 1) file content in the tree being pushed (exclude this script so its own
#    pattern list doesn't trip the gate)
#
# Capture into a variable and test that, rather than `… | grep -q .`. Under
# `set -o pipefail` that idiom FAILS OPEN: `grep -q` exits 0 on its first match,
# SIGPIPE kills `git grep`, and the pipeline's status becomes 141 — so the `if`
# does not take the branch and the gate prints "clean". It only misbehaves once
# the match set is big enough to still be writing when grep leaves, which is to
# say: it passed small leaks through as failures and large ones as clean.
# Verified on a tree with ~70 matches.
HITS="$(git grep -inE "$PATTERNS" "$REF" -- . ':(exclude)scripts/scrub-gate.sh' 2>/dev/null || true)"
if [ -n "$HITS" ]; then
  echo "✖ scrub-gate: forbidden content in files at $REF:"
  printf '%s\n' "$HITS" | sed 's/^/    /' | head -20
  fail=1
fi

# 2) commit messages in the outgoing range. Same capture-then-test shape, for the
#    same reason — and note the message scan is why a commit that *removes*
#    private content must not name it in its subject or body either.
if [ -n "$RANGE" ]; then
  MSGHITS="$(git log --format='%H %B' "$RANGE" 2>/dev/null | grep -inE "$PATTERNS" || true)"
  if [ -n "$MSGHITS" ]; then
    echo "✖ scrub-gate: forbidden content in commit messages ($RANGE):"
    printf '%s\n' "$MSGHITS" | sed 's/^/    /' | head -20
    fail=1
  fi
fi

if [ "$fail" -ne 0 ]; then
  echo "Push blocked by scrub-gate. Remove the above before pushing to the public repo."
  exit 1
fi
echo "✓ scrub-gate: clean ($REF)"
exit 0
