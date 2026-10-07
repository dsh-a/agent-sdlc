#!/usr/bin/env bash
# sync-gitignore.sh — keep the agent-sdlc managed block in .gitignore current.
#
# Runs at cycle startup. Writes a fenced block listing the runtime artifacts a
# cycle produces, plus — only when a docs vault is configured — the three
# vault-class paths that are symlinks rather than real directories.
#
# **The rule that matters: never strip on uncertainty.** This edits a *tracked*
# file, and dropping the vault lines has a loud consequence — `cycle_reports`,
# `agent_tasks/reports`, `agent_tasks/prds` and `product` become untracked symlinks, the
# tree goes dirty, and committing that pulls vault-class artifacts back into the
# app repo, which is the exact thing the vault exists to prevent. So an
# unreadable config preserves whatever vault lines are already there and says so.
# Only a config that was actually read, and actually has no vault_root, removes
# them.
#
# This was inlined in SKILL.md and could not tell "no vault configured" from
# "could not read the config". It stripped the block twice in a deployment where
# vault_root was set the whole time.
#
# Paths resolve from the git root, not the working directory: a cycle invoked
# from a subdirectory would otherwise read no config, conclude no vault, and
# strip.
#
# Usage: sync-gitignore.sh [--check]    (--check reports drift, writes nothing)
# Exit: 0 done or in sync, 1 refused, 2 drift found (--check only).

set -uo pipefail

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

BEGIN="# >>> agent-sdlc (managed — do not edit) >>>"
END="# <<< agent-sdlc <<<"
VAULT_PATHS="cycle_reports
agent_tasks/reports
agent_tasks/prds
product"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "sync-gitignore: not in a git repo — nothing to do" >&2; exit 0; }
GI="$ROOT/.gitignore"
CFG="$ROOT/.omp/agent-config.md"

# Whatever vault lines the current block already carries.
existing_vault() {
  [ -f "$GI" ] || return 0
  awk -v b="$BEGIN" -v e="$END" '$0==b{i=1;next} $0==e{i=0} i' "$GI" \
    | grep -Fx -f <(printf '%s\n' "$VAULT_PATHS") 2>/dev/null || true
}

if [ -r "$CFG" ]; then
  VAULT_ROOT="$(awk -F'|' '/^\| *vault_root *\|/{gsub(/^[ \t]+|[ \t]+$/,"",$3); print $3; exit}' "$CFG")"
  if [ -n "$VAULT_ROOT" ]; then
    WANT="$VAULT_PATHS"
  else
    WANT=""          # positively known: no vault, so the paths are real dirs
  fi
else
  # Unknown, not absent. Keep what is there rather than guessing.
  WANT="$(existing_vault)"
  printf 'sync-gitignore: %s unreadable — keeping the vault lines already present.\n' "$CFG" >&2
fi

NEW="$(printf '%s\n%s\n%s\n' "$BEGIN" "agent_states/
agent_tasks/tasks-*.md" "$END")"
[ -z "$WANT" ] || NEW="$(printf '%s\n%s\n%s\n%s\n' "$BEGIN" "agent_states/
agent_tasks/tasks-*.md" "$WANT" "$END")"

OLD=""
[ -f "$GI" ] && OLD="$(awk -v b="$BEGIN" -v e="$END" '$0==b{i=1} i{print} $0==e{i=0}' "$GI")"

if [ "$OLD" = "$NEW" ]; then
  [ "$CHECK" = 1 ] && echo "sync-gitignore: in sync"
  exit 0
fi

if [ "$CHECK" = 1 ]; then
  echo "sync-gitignore: managed block is out of date"
  exit 2
fi

TMP="$(mktemp)" || { echo "sync-gitignore: mktemp failed" >&2; exit 1; }
{
  # Everything outside the block, with trailing blank lines collapsed.
  [ -f "$GI" ] && awk -v b="$BEGIN" -v e="$END" '$0==b{i=1} !i{print} $0==e{i=0}' "$GI" \
    | awk 'NF{for(;n>0;n--)print"";print;next}{n++}'
  printf '\n%s\n' "$NEW"
} > "$TMP" && mv "$TMP" "$GI"
exit 0
