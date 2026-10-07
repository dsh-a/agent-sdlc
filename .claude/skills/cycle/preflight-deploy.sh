#!/usr/bin/env bash
# preflight-deploy.sh — verify this project's framework deployment, from inside a cycle.
#
# `deploy.sh check` already does the work. This exists because of *how* a cycle
# has to call it.
#
# The check used to be a `!`...`` bash substitution in SKILL.md, composing a
# shell pipeline that derived the framework path and invoked a script outside the
# project. In fan-out 6 the auto-mode classifier refused to expand that line in
# one session out of five — same string, same settings, same minute — with
# `[Code from External]`. A denied `!`...`` does not degrade: it aborts the whole
# slash command, so that cycle received no skill body at all and sat idle until a
# human noticed. The orchestrator's hand-rolled retry was refused too, as
# `[Auto-Mode Bypass]`, because an out-of-tree absolute path matches no grant.
#
# So the call becomes what the other scoped scripts already are: one short,
# project-relative command that a project can grant by name
# (`Bash(bash .claude/skills/cycle/preflight-deploy.sh*)`), invoked from the skill
# *body* where a refusal is a reported finding rather than a silent abort.
#
#   preflight-deploy.sh [project]
#
# `project` defaults to the current directory. Exit codes: 0 correct, 1 problems
# found, 2 framework not reachable.

set -uo pipefail

TARGET="${1:-.}"

# The script is reached through the deployed symlink `.claude/skills/cycle/`, so
# resolving its own directory physically lands in the framework checkout. A
# *copied* skill directory lands in the project instead and finds no deploy.sh —
# which is the right answer, because a copy is exactly the stale-deployment bug
# this check exists to catch.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd -P)" || HERE=
FW="$(cd "${HERE:-.}/../../.." 2>/dev/null && pwd -P)" || FW=

if [ -z "$FW" ] || [ ! -x "$FW/deploy.sh" ]; then
  echo "  deploy.sh not reachable from ${HERE:-unknown} — framework path could not be derived"
  echo "PREFLIGHT: unreachable"
  exit 2
fi

OUT="$(bash "$FW/deploy.sh" check "$TARGET" 2>&1)"
RC=$?

printf '%s\n' "$OUT" | tail -6

# Telemetry an earlier cycle left behind. Finalize clears `agent_states/events/`,
# but a cycle that was interrupted never reaches Finalize, and the next cycle
# then reports the leftovers as its own: one run quoted 2 sessions spanning 451h
# and 2,098 orchestrator tool calls — three weeks of unrelated work — in the two
# most quantitative sections of its report.
#
# Checked here rather than in the skill because it is mechanical and this script
# is already the orchestrator's first action, and because the skill sits at its
# context ceiling: a paragraph there costs every cycle, a line here costs none.
STALE=$(ls "$TARGET/agent_states/events" 2>/dev/null | wc -l | tr -d " ")
if [ "${STALE:-0}" -gt 0 ]; then
  echo "  STALE TELEMETRY: $STALE event file(s) from a cycle that never reached Finalize."
  echo "  Clear them before Phase 3 (the Finalize monitor holds clear-agent-states.py),"
  echo "  or report telemetry as not collected rather than quoting it."
fi

case "$RC" in
  0) echo "PREFLIGHT: ok" ;;
  *) echo "PREFLIGHT: problems — fix with: bash $FW/deploy.sh link $TARGET" ;;
esac

exit "$RC"
