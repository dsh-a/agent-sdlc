#!/usr/bin/env bash
# Tests for .claude/skills/cycle/sync-gitignore.sh.
#
# The dangerous direction is deletion: the managed block lives in a TRACKED file,
# and dropping the vault lines makes cycle_reports / agent_tasks/reports /
# agent_tasks/prds show up untracked, dirtying the tree and inviting a commit that
# pulls vault-class artifacts into the app repo. That happened twice in a real
# deployment whose vault_root was set the whole time, so "unreadable config keeps
# what is there" is the property this file exists to pin.
set -uo pipefail
SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.claude/skills/cycle/sync-gitignore.sh"
FAILED=0
ok() { printf 'ok    %s\n' "$1"; }
bad() { printf 'FAIL  %s\n     %s\n' "$1" "${2:-}"; FAILED=1; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want [$3] got [$2]"; fi; }

mkrepo() {  # $1 = vault_root value, empty for none; omit arg 2 to write a config
  R="$(mktemp -d)"; mkdir -p "$R/.omp"
  git init -q "$R"
  printf 'build/\nnode_modules/\n' > "$R/.gitignore"
  if [ "${2:-yes}" = yes ]; then
    { printf '## Docs Vault\n\n| Field | Value | Description |\n|---|---|---|\n'
      printf '| vault_root | %s | Absolute path. |\n' "$1"
      printf '| app_slug | demo | Sub-dir. |\n'; } > "$R/.omp/agent-config.md"
  fi
  # Commit it: the real file is tracked, which is what makes a bad strip dirty
  # the tree and tempt someone into committing vault artifacts.
  git -C "$R" -c user.email=t@t -c user.name=t add -A >/dev/null 2>&1
  git -C "$R" -c user.email=t@t -c user.name=t commit -qm init >/dev/null 2>&1
  printf '%s' "$R"
}
block() { awk '/^# >>> agent-sdlc/{i=1} i{print} /^# <<< agent-sdlc/{i=0}' "$1/.gitignore"; }
has() { grep -qFx "$2" <(block "$1") && echo yes || echo no; }

# 1. Vault configured -> vault lines present.
R="$(mkrepo /tmp/vault)"; ( cd "$R" && bash "$SCRIPT" >/dev/null 2>&1 )
check "vault configured adds cycle_reports" "$(has "$R" cycle_reports)" yes
check "  ... and agent_tasks/prds" "$(has "$R" agent_tasks/prds)" yes
check "  ... and keeps pre-existing entries" "$(grep -c '^build/$' "$R/.gitignore")" 1

# 2. Idempotent.
B1="$(block "$R")"; ( cd "$R" && bash "$SCRIPT" >/dev/null 2>&1 ); B2="$(block "$R")"
check "second run changes nothing" "$B1" "$B2"

# 3. THE REGRESSION: config unreadable -> vault lines survive.
git -C "$R" -c user.email=t@t -c user.name=t commit -qam synced >/dev/null 2>&1
mv "$R/.omp/agent-config.md" "$R/.omp/agent-config.md.bak"
( cd "$R" && bash "$SCRIPT" >/dev/null 2>&1 )
check "unreadable config KEEPS cycle_reports" "$(has "$R" cycle_reports)" yes
check "  ... keeps agent_tasks/reports" "$(has "$R" agent_tasks/reports)" yes
check "  ... and leaves the tree clean" "$(cd "$R" && git status --porcelain -- .gitignore | wc -l | tr -d ' ')" 0

# 4. Positively no vault -> lines removed (the legitimate deletion).
mv "$R/.omp/agent-config.md.bak" "$R/.omp/agent-config.md"
sed -i.bak 's#| vault_root | /tmp/vault |#| vault_root |  |#' "$R/.omp/agent-config.md"
( cd "$R" && bash "$SCRIPT" >/dev/null 2>&1 )
check "empty vault_root removes cycle_reports" "$(has "$R" cycle_reports)" no
check "  ... but keeps agent_states/" "$(has "$R" agent_states/)" yes

# 5. Run from a subdirectory: resolves via the git root, not the cwd.
R2="$(mkrepo /tmp/vault)"; mkdir -p "$R2/lib/deep"
( cd "$R2/lib/deep" && bash "$SCRIPT" >/dev/null 2>&1 )
check "works from a subdirectory" "$(has "$R2" cycle_reports)" yes
check "  ... and writes no nested .gitignore" "$([ -f "$R2/lib/deep/.gitignore" ] && echo yes || echo no)" no

# 6. No config at all, no prior block -> adds nothing vault-ish, still safe.
R3="$(mkrepo "" no)"; ( cd "$R3" && bash "$SCRIPT" >/dev/null 2>&1 )
check "no config, no prior block: no vault lines invented" "$(has "$R3" cycle_reports)" no
check "  ... base entries still written" "$(has "$R3" agent_states/)" yes

# 7. --check reports drift without writing.
R4="$(mkrepo /tmp/vault)"; ( cd "$R4" && bash "$SCRIPT" --check >/dev/null 2>&1 ); rc=$?
check "--check flags drift" "$rc" 2
check "  ... and writes nothing" "$(has "$R4" cycle_reports)" no

[ "$FAILED" = 0 ] && echo && echo "sync-gitignore: all checks passed." || { echo; echo "sync-gitignore: FAILURES"; }
exit $FAILED
