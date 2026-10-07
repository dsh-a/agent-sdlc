#!/usr/bin/env bash
# Tests for .claude/skills/cycle/preflight-deploy.sh.
#
# The shim exists because a cycle's *first* action must be a short,
# project-relative, grantable command — the substituted form it replaces was
# refused by the auto-mode classifier in one fan-out session out of five, which
# aborted that whole run. So the properties under test are the ones that make it
# safe to call blind: it finds the framework through the deployed symlink and
# nowhere else, it distinguishes "correct" from "broken" from "cannot tell", and
# it never exits 0 on any of the last two.
set -uo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
FAILED=0
ok() { printf 'ok    %s\n' "$1"; }
bad() { printf 'FAIL  %s\n     %s\n' "$1" "${2:-}"; FAILED=1; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want [$3] got [$2]"; fi; }

# -P: mktemp hands back /var/... on macOS, a symlink to /private/var, and the
# shim resolves with `pwd -P`. Comparing unresolved paths is the same trap the
# reap documents.
R="$(cd "$(mktemp -d)" && pwd -P)"

# A miniature framework: small manifest, exact assertions. It carries the real
# deploy.sh and the real shim, so what is under test is the pair.
FW="$R/fw"
mkdir -p "$FW"/.claude/{skills/cycle,hooks,agents/scaffold,packs/flutter} "$FW"/.omp/agents
git init -q "$FW"; git -C "$FW" config user.email t@t; git -C "$FW" config user.name t
echo skill > "$FW/.claude/skills/cycle/SKILL.md"
echo hook  > "$FW/.claude/hooks/gate-log.py"
echo pat   > "$FW/.claude/agents/scaffold/interface.md"
echo pack  > "$FW/.claude/packs/flutter/conventions.md"
echo agent > "$FW/.omp/agents/verify.md"
printf '## Active Pack\n## Artifact Paths\n## Model Versions — **omp only**\n' \
  > "$FW/.omp/agent-config.md"
cp "$ROOT_DIR/deploy.sh" "$FW/deploy.sh"; chmod +x "$FW/deploy.sh"
cp "$ROOT_DIR/.claude/skills/cycle/preflight-deploy.sh" "$FW/.claude/skills/cycle/"
chmod +x "$FW/.claude/skills/cycle/preflight-deploy.sh"
git -C "$FW" add -A; git -C "$FW" commit -qm fw

P="$R/proj"; mkdir -p "$P/.claude" "$P/.omp"
git init -q "$P"
echo '{}' > "$P/.claude/settings.json"
printf '## Active Pack\n## Artifact Paths\n## Model Versions\n' > "$P/.omp/agent-config.md"
bash "$FW/deploy.sh" link "$P" >/dev/null 2>&1
chk "fixture deploys cleanly" "$?" 0

SHIM=".claude/skills/cycle/preflight-deploy.sh"

# --- a correct deployment -------------------------------------------------
#
# Invoked exactly as SKILL.md tells the orchestrator to invoke it: relative
# path, no argument, from the project root.
cd "$P"
out="$(bash "$SHIM" 2>&1)"; rc=$?
chk "ok on a correct deployment" "$rc" 0
chk "  ... says PREFLIGHT: ok" "$(printf '%s' "$out" | tail -1)" "PREFLIGHT: ok"
chk "  ... and passes deploy.sh's summary through" \
    "$(printf '%s' "$out" | grep -c 'correct')" 1
chk "  ... naming the framework it checked against" \
    "$(printf '%s' "$out" | grep -c "$FW")" 1

# The verdict is the LAST line, always — the orchestrator reads it positionally.
chk "verdict is the final line" \
    "$(printf '%s' "$out" | tail -1 | grep -c '^PREFLIGHT: ')" 1

# --- the failure the check exists for -------------------------------------
#
# A dangling hook link. This is the silent one: the harness treats a hook error
# as non-fatal, so telemetry and gate capture stop with nothing said.
rm -f "$P/.claude/hooks/gate-log.py"
ln -s "$FW/.claude/hooks/does-not-exist.py" "$P/.claude/hooks/gate-log.py"
out="$(bash "$SHIM" 2>&1)"; rc=$?
chk "non-zero on a dangling link" "$rc" 1
chk "  ... says PREFLIGHT: problems" \
    "$(printf '%s' "$out" | tail -1 | grep -c '^PREFLIGHT: problems')" 1
chk "  ... and prints a repair command naming the project" \
    "$(printf '%s' "$out" | tail -1 | grep -c "deploy.sh link")" 1

# A COPY is a failure too: a copied hook goes stale invisibly, which is the bug
# that made a whole fan-out log every row unclassified while looking healthy.
rm -f "$P/.claude/hooks/gate-log.py"
cp "$FW/.claude/hooks/gate-log.py" "$P/.claude/hooks/gate-log.py"
out="$(bash "$SHIM" 2>&1)"; rc=$?
chk "non-zero on a copied hook" "$rc" 1
chk "  ... reported, not swallowed" \
    "$(printf '%s' "$out" | tail -1 | grep -c '^PREFLIGHT: problems')" 1

# Repaired, and the verdict goes back to ok — a preflight that latches failure
# would block every later cycle in the clone.
rm -f "$P/.claude/hooks/gate-log.py"
bash "$FW/deploy.sh" link "$P" >/dev/null 2>&1
out="$(bash "$SHIM" 2>&1)"; rc=$?
chk "ok again once repaired" "$rc" 0
chk "  ... verdict clears" "$(printf '%s' "$out" | tail -1)" "PREFLIGHT: ok"

# --- explicit target ------------------------------------------------------
#
# The launcher and a human may both want to check a project they are not in.
cd "$R"
out="$(bash "$P/$SHIM" "$P" 2>&1)"; rc=$?
chk "accepts an explicit project argument" "$rc" 0
chk "  ... checking the named project, not the cwd" \
    "$(printf '%s' "$out" | grep -c "$P")" 1

# --- cannot tell ----------------------------------------------------------
#
# A *copied* skill directory resolves to the project, finds no deploy.sh three
# levels up, and must say so rather than report a pass. This is the important
# negative: a copied deployment is precisely what the check exists to catch, so
# a copy that silently self-certifies would defeat the whole mechanism.
C="$R/copied"; mkdir -p "$C/.claude/skills/cycle"
git init -q "$C"
cp "$FW/.claude/skills/cycle/preflight-deploy.sh" "$C/$SHIM"
cd "$C"
out="$(bash "$SHIM" 2>&1)"; rc=$?
chk "refuses when the framework is not above it" "$rc" 2
chk "  ... says PREFLIGHT: unreachable" \
    "$(printf '%s' "$out" | tail -1)" "PREFLIGHT: unreachable"
chk "  ... and does not claim a pass" "$(printf '%s' "$out" | grep -c 'PREFLIGHT: ok')" 0
chk "  ... naming where it looked" "$(printf '%s' "$out" | grep -c "$C")" 1

# Same shape, but deploy.sh present and not executable — reachable is about
# runnability, not existence.
C2="$R/notexec"; mkdir -p "$C2/.claude/skills/cycle"
git init -q "$C2"
cp "$FW/.claude/skills/cycle/preflight-deploy.sh" "$C2/$SHIM"
cp "$FW/deploy.sh" "$C2/deploy.sh"; chmod -x "$C2/deploy.sh"
cd "$C2"
out="$(bash "$SHIM" 2>&1)"; rc=$?
chk "refuses a non-executable deploy.sh" "$rc" 2
chk "  ... as unreachable, not as a pass" \
    "$(printf '%s' "$out" | tail -1)" "PREFLIGHT: unreachable"

# --- it changes nothing ---------------------------------------------------
#
# A preflight that repaired what it found would hide the drift it exists to
# report, and would write into a project during a run.
cd "$P"
before="$(find "$P" -maxdepth 3 | sort | shasum)"
bash "$SHIM" >/dev/null 2>&1
after="$(find "$P" -maxdepth 3 | sort | shasum)"
chk "leaves the project untouched" "$before" "$after"

cd "$R"; rm -rf "$R"
[ "$FAILED" = 0 ] && printf '\nall preflight-deploy tests passed\n'
exit "$FAILED"
