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
PATTERNS='bloomerang|dalton\.shultz@|dmoney|sk-or-v1-|sk-[A-Za-z0-9]{24}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_|AKIA[0-9A-Z]{16}|xox[baprs]-|-----BEGIN [A-Z ]*PRIVATE KEY'

fail=0

# 1) file content in the tree being pushed (exclude this script so its own
#    pattern list doesn't trip the gate)
if git grep -inE "$PATTERNS" "$REF" -- . ':(exclude)scripts/scrub-gate.sh' 2>/dev/null | grep -q .; then
  echo "✖ scrub-gate: forbidden content in files at $REF:"
  git grep -inE "$PATTERNS" "$REF" -- . ':(exclude)scripts/scrub-gate.sh' 2>/dev/null | sed 's/^/    /' | head -20
  fail=1
fi

# 2) commit messages in the outgoing range
if [ -n "$RANGE" ]; then
  if git log --format='%H %B' "$RANGE" 2>/dev/null | grep -inE "$PATTERNS" | grep -q .; then
    echo "✖ scrub-gate: forbidden content in commit messages ($RANGE):"
    git log --format='%H %B' "$RANGE" 2>/dev/null | grep -inE "$PATTERNS" | sed 's/^/    /' | head -20
    fail=1
  fi
fi

if [ "$fail" -ne 0 ]; then
  echo "Push blocked by scrub-gate. Remove the above before pushing to the public repo."
  exit 1
fi
echo "✓ scrub-gate: clean ($REF)"
exit 0
